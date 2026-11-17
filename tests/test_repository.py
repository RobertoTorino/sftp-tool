# SPDX-License-Identifier: GPL-3.0-or-later
"""The repository's version, and the folders of the releases made in the BC250 Bazzite Suite."""

from __future__ import annotations

from pathlib import Path

import sftp_tools
from sftp_tools import settings

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_the_version_file():
    assert sftp_tools.__version__ == (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def test_the_old_folders_move_once(tmp_path):
    old_config = tmp_path / "config" / settings.OLD_ID
    old_data = tmp_path / "data" / settings.OLD_ID
    old_config.mkdir(parents=True)
    old_data.mkdir(parents=True)
    (old_config / "profiles.json").write_text("{}", encoding="utf-8")
    (old_data / f"{settings.OLD_ID}.log").write_text("line\n", encoding="utf-8")
    settings.move_old_folders()
    assert (settings.config_dir() / "profiles.json").is_file() and not old_config.exists()
    assert settings.log_file().read_text(encoding="utf-8") == "line\n" and not old_data.exists()


def test_a_folder_of_this_app_is_never_overwritten(tmp_path):
    (tmp_path / "config" / settings.OLD_ID).mkdir(parents=True)
    settings.config_dir().mkdir(parents=True)
    (settings.config_dir() / "settings.json").write_text("{}", encoding="utf-8")
    settings.move_old_folders()
    assert (tmp_path / "config" / settings.OLD_ID).is_dir()
    assert (settings.config_dir() / "settings.json").is_file()
