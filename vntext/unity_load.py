"""UnityPy.load that never leaves the game file open after a failed load (a leaked handle blocks uninstall/rename of the game folder on Windows)."""
from __future__ import annotations

import gc


def unity_load(path):
    import UnityPy
    try:
        return UnityPy.load(str(path))
    except BaseException:
        gc.collect()   # the failed parse still references the open file until its frames are collected
        raise
