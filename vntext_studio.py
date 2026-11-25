"""Compatibility facade for VNText Studio backend helpers.

Backend implementation lives in :mod:`vntext.app_backend`; this module keeps
the established import surface used by scripts, tools and the packaged worker
(version check). The legacy Tk/Qt/QML desktop UIs were removed (2026-11-25);
the shipped UI is the WPF application.
"""

from vntext.app_backend import *  # noqa: F401,F403 - compatibility re-export
