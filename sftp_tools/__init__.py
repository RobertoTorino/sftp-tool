# SPDX-License-Identifier: GPL-3.0-or-later
"""SFTP Tools for Windows: browse and transfer files over SFTP, and manage the OpenSSH server (sshd) of a Linux host
from a Windows computer."""

APP_NAME = "SFTP Tools"
APP_ID = "sftp-tools"
__version__ = "2.2.0"

from pathlib import Path

from .core import AppInfo

ROOT = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT / "images" / f"{APP_ID}.webp"

# Settings, profiles in ~/.config/sftp-tools/, the log in ~/.local/share/sftp-tools/ (moved there from the
# bc250-sftp-tools folders of the releases made in the BC250 Bazzite Suite: settings.move_old_folders)
INFO = AppInfo(app_id=APP_ID, name=APP_NAME, version=__version__, logo=LOGO_PATH, tag_prefix="v",
               settings_ini=True)

__all__ = ["APP_ID", "APP_NAME", "INFO", "LOGO_PATH", "ROOT", "__version__"]
