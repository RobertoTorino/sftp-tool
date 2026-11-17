# SPDX-License-Identifier: GPL-3.0-or-later
"""tools/build_windows_exe.py: what it hands PyInstaller, and that the release workflow builds it.
PyInstaller itself is not run here: it only builds for the system it runs on, and the release job does that."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_windows_exe", ROOT / "tools" / "build_windows_exe.py")
bwe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bwe)


def test_the_package_logo_and_fonts_are_where_the_build_takes_them():
    assert (ROOT / bwe.PACKAGE / "__main__.py").is_file()
    assert (ROOT / "images" / f"{bwe.app_id(ROOT)}.webp").is_file()
    assert sorted((ROOT / bwe.FONTS).glob("*.ttf")) and sorted((ROOT / bwe.FONTS).glob("*LICENSE*"))


def test_asset_names_follow_app_id_and_version():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert bwe.app_id(ROOT) == "sftp-tools"
    assert bwe.asset_name("sftp-tools", version) == f"sftp-tools-{version}-windows.zip"


def test_launcher_calls_the_packages_main():
    source = bwe.launcher_source()
    assert "from sftp_tools.__main__ import main" in source
    assert source.rstrip().endswith("sys.exit(main())")
    compile(source, "launcher.py", "exec")


def test_pyinstaller_gets_one_windowed_exe_with_the_logo_and_fonts(tmp_path):
    args = bwe.pyinstaller_args(tmp_path / "src", tmp_path / "run.py", tmp_path / "src" / "images" / "logo.webp",
                                tmp_path / "work", tmp_path / "dist", sep=";")
    assert args[0] == str(tmp_path / "run.py")
    assert {"--onefile", "--windowed"} <= set(args)
    assert args[args.index("--name") + 1] == "SFTP-Tools"
    assert args[args.index("--paths") + 1] == str(tmp_path / "src")
    add_data = [args[i + 1] for i, a in enumerate(args) if a == "--add-data"]
    assert add_data == [f"{tmp_path / 'src' / 'images'};images",
                        f"{tmp_path / 'src' / 'sftp_tools' / 'core' / 'fonts'};sftp_tools/core/fonts"]
    collected = [args[i + 1] for i, a in enumerate(args) if a in ("--collect-submodules", "--collect-all")]
    assert collected == ["sftp_tools", "paramiko"]


def test_the_release_workflow_builds_and_publishes_the_exe_of_its_tag():
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "runs-on: windows-latest" in workflow and "tools/build_windows_exe.py" in workflow
    assert "gh release create" in workflow and "VERSION" in workflow


def _names(dists):
    return {bwe._key(d.metadata["Name"]) for d in dists}


def test_bundled_distributions_follow_the_requirements_as_installed(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("# SPDX-License-Identifier: GPL-3.0-or-later\npytest>=8   # a comment\n"
                            'no-such-package-here\npyyaml; python_version < "3"\n', encoding="utf-8")
    names = _names(bwe.bundled_distributions(requirements))
    assert {"pytest", "pluggy", "iniconfig", "packaging"} <= names       # pytest and what it requires
    assert "no-such-package-here" not in names                          # not installed here: not bundled
    assert "pyyaml" not in names                                        # its marker is false
    assert "hypothesis" not in names                                    # pytest's extra "dev" only


def test_notices_hold_the_others_then_each_package_with_its_license(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("pytest\n", encoding="utf-8")
    font = tmp_path / "Inter-LICENSE.txt"
    font.write_text("SIL Open Font License 1.1\n", encoding="utf-8")
    dists = bwe.bundled_distributions(requirements)
    text = bwe.notices_text("Test-App", dists, [("Font: Inter", font)])
    assert text.startswith("Test-App carries the third-party software below.")
    assert text.index("Font: Inter") < text.index("SIL Open Font License 1.1") < text.index("pytest ")
    pytest_dist = next(d for d in dists if bwe._key(d.metadata["Name"]) == "pytest")
    assert f"pytest {pytest_dist.version} (MIT)" in text
    assert "Permission is hereby granted, free of charge" in text      # pytest's MIT license text


def test_python_license_is_found_or_the_build_stops():
    try:
        path = bwe.python_license()
    except SystemExit as error:
        assert "LICENSE.txt" in str(error)
    else:
        assert "PYTHON SOFTWARE FOUNDATION" in path.read_text(encoding="utf-8", errors="replace").upper()
