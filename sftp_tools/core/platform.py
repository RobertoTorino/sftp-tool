# SPDX-License-Identifier: GPL-3.0-or-later
"""Desktop integration: XDG folders, opening files/URLs, and starting a command in a visible terminal window.

launch_in_terminal() is the bisect GUIs' terminal.py (identical in cu, cores and gpu-oc), plus an optional exit
file: the shell writes the command's exit status there when it ends, so a caller that cannot wait for the detached
terminal (the portal running an installer) can still tell when, and how, it finished.

The Windows side, for the development apps on Windows and BC-250 SFTP Tools' Windows executable: open_path() with the
file's own program and a PowerShell window for launch_in_terminal(). data_home(), config_home(), bin_home() and
xdg_open() return what they always did, on Windows too: the Windows executable keeps its files where they are."""

from __future__ import annotations

import base64
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path, PurePath

WINDOWS = sys.platform == "win32"
# Windows' process flags (subprocess has them only on Windows; the values let the tests run the Windows side anywhere)
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10)
NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

# (binary, args-builder) in order of preference. Each builder takes the shell command string
# (already quoted for `bash -lc`) and returns the full argv to exec that terminal with.
_TERMINALS = [
    ("konsole", lambda cmd: ["konsole", "-e", "bash", "-lc", cmd]),
    ("gnome-terminal", lambda cmd: ["gnome-terminal", "--", "bash", "-lc", cmd]),
    ("ptyxis", lambda cmd: ["ptyxis", "--", "bash", "-lc", cmd]),
    ("xfce4-terminal", lambda cmd: ["xfce4-terminal", "-e", f"bash -lc {subprocess.list2cmdline([cmd])}"]),
    ("foot", lambda cmd: ["foot", "bash", "-lc", cmd]),
    ("alacritty", lambda cmd: ["alacritty", "-e", "bash", "-lc", cmd]),
    ("kitty", lambda cmd: ["kitty", "bash", "-lc", cmd]),
    ("x-terminal-emulator", lambda cmd: ["x-terminal-emulator", "-e", f"bash -lc {subprocess.list2cmdline([cmd])}"]),
    ("xterm", lambda cmd: ["xterm", "-e", "bash", "-lc", cmd]),
]


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")


def config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def bin_home() -> Path:
    return Path(os.environ.get("XDG_BIN_HOME") or Path.home() / ".local" / "bin")



def private(text: str | PurePath) -> str:
    """*text* (a path, a message, a log line) with the user's folders written as Windows writes them for anyone:
    %LOCALAPPDATA%, %APPDATA% and %USERPROFILE% (Linux: ~ for the home folder), so the user's name never shows on the
    screen or in a log (owner, 29-10-2026: the privacy rule, "we don't do that anywhere"). Every place in the text,
    whatever its case on Windows."""
    text = str(text)
    if WINDOWS:
        folders = [(name, os.environ.get(name, "")) for name in ("LOCALAPPDATA", "APPDATA", "USERPROFILE")]
        folders.append(("USERPROFILE", str(Path.home())))
        for name, folder in sorted(((n, f.rstrip("\\/")) for n, f in folders if f), key=lambda nf: -len(nf[1])):
            if len(folder) > 3:                         # never a drive's root
                text = re.sub(re.escape(folder) + r"(?=[\\/]|\b|$)", lambda _m, n=name: f"%{n}%", text,
                              flags=re.IGNORECASE)
        return text
    home = str(Path.home()).rstrip("/")
    return re.sub(re.escape(home) + r"(?=/|\b|$)", "~", text) if len(home) > 1 else text


def expand(path: str) -> Path:
    """"~/.local/bin/x" and "$XDG_DATA_HOME/…" style paths, as written in a manifest."""
    return Path(os.path.expandvars(os.path.expanduser(path)))


def xdg_open(target: str | Path) -> bool:
    """Open a file, folder or URL with the desktop's default handler; False when xdg-open is missing."""
    opener = shutil.which("xdg-open")
    if opener is None:
        return False
    subprocess.Popen([opener, str(target)], start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def open_path(target: str | Path) -> bool:
    """Open a file, folder or URL with its default program: os.startfile on Windows, xdg-open elsewhere. False when
    nothing could open it."""
    if not WINDOWS:
        return xdg_open(target)
    try:
        os.startfile(str(target))  # type: ignore[attr-defined]  # Windows only
    except OSError:
        return False
    return True


def show_in_folder(path: str | Path) -> bool:
    """The folder of the file at *path* in the file manager, with the file selected: Explorer on Windows, else the
    desktop's file manager over D-Bus (org.freedesktop.FileManager1, Dolphin on Bazzite), else the folder opened with
    xdg-open. False when nothing opened it. A saved screenshot shows itself so (owner, 06-11-2026)."""
    path = Path(path)
    if WINDOWS:
        # Explorer may take the front: without it, its window opened behind the full-screen app (owner, 07-11-2026)
        import ctypes
        windll = getattr(ctypes, "windll", None)        # None where Windows is only played (the tests on Linux)
        if windll is not None:
            windll.user32.AllowSetForegroundWindow(-1)
        try:
            # Explorer's own syntax: one argument, "/select," and the path; it exits with 1 even when it worked.
            subprocess.Popen(f'explorer /select,"{path}"', stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError:
            return open_path(path.parent)
        return True
    gdbus = shutil.which("gdbus")
    if gdbus is not None:
        try:
            done = subprocess.run([gdbus, "call", "--session", "--dest", "org.freedesktop.FileManager1",
                                   "--object-path", "/org/freedesktop/FileManager1",
                                   "--method", "org.freedesktop.FileManager1.ShowItems",
                                   f"['{path.resolve().as_uri()}']", ""],
                                  stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
            if done.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
    return xdg_open(path.parent)



# A window and its monitor as Windows has them, in the screen's own pixels (Qt's apps are per-monitor DPI aware): a
# full-screen window is placed on its monitor's rectangle exactly, as WindowManager does (owner, 07-11-2026: the
# portal's bottom row was cut off again on the TV). Rectangles are (left, top, width, height).
WS_CAPTION, WS_THICKFRAME = 0x00C00000, 0x00040000
SWP_NOACTIVATE, SWP_NOOWNERZORDER, SWP_FRAMECHANGED = 0x0010, 0x0200, 0x0020



# The device's own screen, as Windows reports its connection (owner, 07-11-2026: no screen found by its name, hardware
# changes): QueryDisplayConfig's output technology of each active screen, the built-in ones' top-left corners.
BUILT_IN = (0x80000000, 6, 11, 13)      # DISPLAYCONFIG_OUTPUT_TECHNOLOGY_ INTERNAL, LVDS, DISPLAYPORT_ and UDI_EMBEDDED




def _ps_quote(text: str | PurePath) -> str:
    """*text* as a PowerShell string literal: single quotes, a quote inside doubled."""
    return "'" + str(text).replace("'", "''") + "'"


def powershell_argv(script: str) -> list[str]:
    """powershell.exe running *script*, passed encoded (UTF-16LE, base64), so no quote, semicolon or ampersand in it
    reaches a command line parser."""
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return ["powershell.exe", "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded]


def powershell_command(command: str, *, keep_open: bool | str = True, exit_file: PurePath | None = None) -> str:
    """The PowerShell script launch_in_terminal() runs on Windows, as terminal_command() is bash's: the command,
    its status written to *exit_file*, and a "Press Enter" pause (always, only after a failure with
    keep_open="on_error", or none). The status is the last program's exit code, or 1 for an error PowerShell
    raised (errors stop the command, as bash's set -e would)."""
    lines = ["$ErrorActionPreference = 'Stop'", "$global:LASTEXITCODE = 0",
             f"try {{ {command} }} catch {{ Write-Host $_ -ForegroundColor Red; $global:LASTEXITCODE = 1 }}",
             "$s = [int]$LASTEXITCODE"]
    if exit_file is not None:
        lines.append(f"Set-Content -LiteralPath {_ps_quote(exit_file)} -Value $s -Encoding Ascii")
    pause = "Write-Host; Read-Host 'Press Enter to close' | Out-Null"
    if keep_open == "on_error":
        lines.append(f"if ($s -ne 0) {{ {pause} }}")
    elif keep_open:
        lines.append(pause)
    lines.append("exit $s")
    return "\n".join(lines)


def find_terminal() -> str | None:
    """Best-guess terminal emulator for this session, or None if none could be found."""
    env_term = os.environ.get("TERMINAL")
    if env_term and shutil.which(env_term):
        return env_term
    for name, _ in _TERMINALS:
        if shutil.which(name):
            return name
    return None


def terminal_command(shell_command: str, *, keep_open: bool | str = True,
                     exit_file: PurePath | None = None) -> str:
    """The shell line launch_in_terminal() runs: the command, its exit status written to *exit_file*, and a
    "Press Enter" pause so the window stays readable after the command ends (success, error or Ctrl+C).
    keep_open="on_error" pauses only when the command failed: a window whose command ended well closes by itself
    (the portal's installs, owner 26-10-2026), one that shows an error stays until Enter."""
    line = shell_command
    pause = "echo; read -rp 'Press Enter to close... ' _"
    # A subshell, so the status is the whole command's, also for "a && b" and an early exit.
    if keep_open == "on_error":
        written = f" echo $s > {shlex.quote(str(exit_file))};" if exit_file is not None else ""
        return f"( {line} ); s=$?;{written} [ \"$s\" = 0 ] || {{ {pause}; }}"
    if exit_file is not None:
        line = f"( {line} ); echo $? > {shlex.quote(str(exit_file))}"
    if keep_open:
        line = f"{line}; {pause}"
    return line


def launch_in_terminal(shell_command: str, *, keep_open: bool | str = True,
                       exit_file: PurePath | None = None) -> None:
    """Runs ``shell_command`` (a single already-quoted shell command line) in a new terminal window, detached from
    this process so closing the GUI doesn't touch it.

    Raises RuntimeError if no terminal emulator could be found.

    On Windows ``shell_command`` is a PowerShell command, run in a window of its own (Windows' default terminal:
    Windows Terminal on Windows 11) by powershell_command()."""
    if WINDOWS:
        subprocess.Popen(powershell_argv(powershell_command(shell_command, keep_open=keep_open, exit_file=exit_file)),
                         creationflags=NEW_CONSOLE | NEW_PROCESS_GROUP,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    line = terminal_command(shell_command, keep_open=keep_open, exit_file=exit_file)
    term = find_terminal()
    if term is None:
        raise RuntimeError(
            "No terminal emulator found (tried konsole, gnome-terminal, ptyxis, xfce4-terminal, "
            "foot, alacritty, kitty, x-terminal-emulator, xterm, and $TERMINAL)."
        )
    builder = dict(_TERMINALS).get(term)
    argv = builder(line) if builder else [term, "-e", "bash", "-lc", line]
    # start_new_session detaches it from this process group so it outlives the GUI.
    subprocess.Popen(argv, start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
