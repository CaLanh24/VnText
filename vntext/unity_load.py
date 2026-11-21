"""UnityPy.load that never leaves the game file open after a failed load (a leaked handle blocks uninstall/rename of the game folder on Windows)."""
from __future__ import annotations

import gc


def unity_load(path):
    import UnityPy
    failure: BaseException | None = None
    try:
        return UnityPy.load(str(path))
    except (KeyboardInterrupt, SystemExit, MemoryError):
        raise
    except Exception as exc:  # noqa: BLE001
        # The failed parse's frames (and the open file they reference) live as long as this exception's traceback does, so collecting inside the
        # handler frees nothing.  Re-raise a fresh exception of the same type that carries no traceback, then collect once the handler has ended.
        try:
            failure = type(exc)(*exc.args)
        except Exception:  # noqa: BLE001
            failure = RuntimeError(f"{type(exc).__name__}: {exc}")
    gc.collect()
    raise failure
