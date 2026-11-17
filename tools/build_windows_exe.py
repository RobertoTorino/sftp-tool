#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build the Windows executable of SFTP Tools from the checkout:

    python tools/build_windows_exe.py <out-dir>

Run it on Windows (PyInstaller builds for the system it runs on) with requirements.txt, pyinstaller and pillow
installed. <out-dir> gets sftp-tools-<version>-windows.zip (the one-file .exe, LICENSE, THIRD-PARTY-NOTICES.txt and
MANUAL.md, the README) and sftp-tools-<version>-windows.zip.sha256. The release workflow publishes both.

The exe carries Python, Qt and the app's Python packages; their licenses (PSF, LGPL, BSD, Apache, ...) ask for their
notices to go with it. THIRD-PARTY-NOTICES.txt holds them: Python's license, every package requirements.txt pulls in
as installed where the build runs (with their license files from the package metadata), and the license of the
fonts the app registers."""

from __future__ import annotations

import hashlib
import os
import re
import sys
import sysconfig
import tempfile
import zipfile
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = "sftp_tools"
EXE_NAME = "SFTP-Tools"
FONTS = f"{PACKAGE}/core/fonts"


def app_id(src: Path, package: str = PACKAGE) -> str:
    text = (src / package / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_ID\s*=\s*"([^"]+)"', text, re.M)
    if match is None:
        raise SystemExit(f"{package}/__init__.py has no APP_ID")
    return match.group(1)


def asset_name(app_id_: str, version: str) -> str:
    return f"{app_id_}-{version}-windows.zip"


def launcher_source(package: str = PACKAGE) -> str:
    """PyInstaller wants a script; the package's __main__ uses relative imports, so a script calls its main()."""
    return f"import sys\n\nfrom {package}.__main__ import main\n\nsys.exit(main())\n"


def pyinstaller_args(src: Path, launcher: Path, icon: Path, work: Path, dist: Path, sep: str = os.pathsep) -> list[str]:
    return [
        str(launcher),
        "--onefile", "--windowed", "--noconfirm", "--clean", "--noupx",
        "--name", EXE_NAME,
        "--distpath", str(dist), "--workpath", str(work), "--specpath", str(work),
        "--paths", str(src),
        "--icon", str(icon),
        "--collect-submodules", PACKAGE,
        "--collect-all", "paramiko",
        # Read from next to the package, as in a checkout: the logo, and the fonts the app registers.
        "--add-data", f"{src / 'images'}{sep}images",
        "--add-data", f"{src / FONTS}{sep}{FONTS}",
    ]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- Third-party notices -----------------------------------------------------------------------------------------

NOTICES = "THIRD-PARTY-NOTICES.txt"
LICENSE_FILE = re.compile(r"^(LICEN[CS]E|COPYING|NOTICE|AUTHORS)", re.I)


def _key(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def bundled_distributions(requirements: Path) -> list[metadata.Distribution]:
    """The packages the exe carries: the app's requirements and what they require in turn, as installed where the
    build runs. A requirement that is not installed there (another platform's, an extra's) is not bundled either."""
    from packaging.requirements import Requirement     # PyInstaller depends on it
    lines = (line.split("#")[0].strip() for line in requirements.read_text(encoding="utf-8").splitlines())
    todo = [Requirement(line) for line in lines if line]
    found: dict[str, metadata.Distribution] = {}
    while todo:
        req = todo.pop()
        if req.marker is not None and not req.marker.evaluate({"extra": ""}):
            continue
        if _key(req.name) in found:
            continue
        try:
            dist = metadata.distribution(req.name)
        except metadata.PackageNotFoundError:
            continue
        found[_key(req.name)] = dist
        todo += [Requirement(r) for r in dist.requires or []]
    return sorted(found.values(), key=lambda d: _key(d.metadata["Name"]))


def license_label(dist: metadata.Distribution) -> str:
    meta = dist.metadata
    label = meta.get("License-Expression") or meta.get("License") or ""
    if not label or "\n" in label or len(label) > 80:      # some packages put the whole text in License
        classifiers = [c.rsplit("::", 1)[-1].strip() for c in meta.get_all("Classifier") or []
                       if c.startswith("License ::")]
        label = ", ".join(classifiers) or "see below"
    return label


def license_texts(dist: metadata.Distribution) -> list[tuple[str, str]]:
    """(file name, text) of each license file in the package's metadata."""
    texts = []
    for file in dist.files or []:
        if ".dist-info" in str(file) and LICENSE_FILE.search(file.name):
            text = Path(file.locate()).read_text(encoding="utf-8", errors="replace")
            if text:
                texts.append((file.name, text.strip()))
    return texts


def python_license() -> Path:
    for folder in (Path(sys.base_prefix), Path(sysconfig.get_path("stdlib"))):
        if (folder / "LICENSE.txt").is_file():
            return folder / "LICENSE.txt"
    raise SystemExit("Python's LICENSE.txt was not found: the exe carries Python, so its notice must go with it")


def notices_text(exe_name: str, dists: list[metadata.Distribution], others: list[tuple[str, Path]]) -> str:
    """THIRD-PARTY-NOTICES.txt: *others* (name, license file) first, then each package with its license files."""
    rule = "=" * 78
    parts = [f"{exe_name} carries the third-party software below. Each part keeps its own license; their texts "
             "follow.\nThe app's own license is in LICENSE.\n"]
    parts += [f"{rule}\n{name}\n{rule}\n\n{path.read_text(encoding='utf-8', errors='replace').strip()}\n"
              for name, path in others]
    for dist in dists:
        head = f"{dist.metadata['Name']} {dist.version} ({license_label(dist)})"
        texts = license_texts(dist) or [("", "No license file in the package; see its project page.")]
        parts.append(f"{rule}\n{head}\n{rule}\n\n" + "\n\n".join(
            (f"--- {name} ---\n\n" if name and len(texts) > 1 else "") + text for name, text in texts) + "\n")
    return "\n".join(parts)


def build(out: Path, src: Path = ROOT) -> tuple[Path, Path]:
    version = (src / "VERSION").read_text(encoding="utf-8").strip()
    name = app_id(src)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        launcher = work / f"{EXE_NAME}.py"
        launcher.write_text(launcher_source(), encoding="utf-8")
        import PyInstaller.__main__ as pyinstaller      # only the build needs it
        pyinstaller.run(pyinstaller_args(src, launcher, src / "images" / f"{name}.webp", work / "build",
                                         work / "dist"))
        exe = next((work / "dist").glob(f"{EXE_NAME}*"), None)
        if exe is None:
            raise SystemExit("PyInstaller made no executable")
        fonts = sorted((src / FONTS).glob("*LICENSE*"))
        notices = notices_text(EXE_NAME, bundled_distributions(src / "requirements.txt"),
                               [(f"Python {sys.version.split()[0]}", python_license())]
                               + [(f"Font: {font.name.split('-')[0]}", font) for font in fonts])
        archive = out / asset_name(name, version)
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(exe, exe.name)
            zf.writestr(NOTICES, notices)
            zf.write(src / "LICENSE", "LICENSE")
            zf.write(src / "README.md", "MANUAL.md")
    checksum = out / f"{archive.name}.sha256"
    checksum.write_text(f"{sha256_of(archive)}  {archive.name}\n", encoding="utf-8")
    return archive, checksum


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    archive, checksum = build(Path(argv[0]))
    print(f"{archive}\n{checksum}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
