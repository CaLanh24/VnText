"""Compatibility facade and Tk launcher for VNText Studio.

Backend implementation lives in :mod:`vntext.app_backend`; this module keeps
the established import surface used by scripts and external integrations.
"""

from vntext.app_backend import *  # noqa: F401,F403 - compatibility re-export
from vntext.app_ui import RawCandidateReviewer, VNTextApp


if __name__ == "__main__":
    VNTextApp().mainloop()
