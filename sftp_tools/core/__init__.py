# SPDX-License-Identifier: GPL-3.0-or-later
"""The app's base: look (theme, widgets), bootstrap (app, settings) and the per-app constants. It began as a copy of
the BC250 Bazzite Suite's shared code (core 4.0.0) and is this repository's own now.
The app passes its constants in as an AppInfo; nothing here imports the app."""

__version__ = "4.0.0"

from .appinfo import SUITE_MANUAL_URL, SUITE_REPO_URL, AppInfo
from .text import fill, fmt, plain_tooltip, window_title

__all__ = ["AppInfo", "SUITE_MANUAL_URL", "SUITE_REPO_URL", "fill", "fmt", "plain_tooltip",
           "window_title", "__version__"]
