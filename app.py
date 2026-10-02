"""Legacy Python GUI entry kept for compatibility integrations.

The shipped/default launcher is the WPF application. QML is available only
when explicitly selected and is not a shipping default.
"""
from __future__ import annotations

import os
import sys

from vntext.runtime_paths import configure_runtime, is_frozen

configure_runtime()

_RELEASE_MODES = {
    "--release-verify",
    "--release-verify-update",
    "--release-verify-qml",
    "--release-version",
}


def _release_cli_mode() -> str | None:
    for arg in sys.argv[1:]:
        if arg in _RELEASE_MODES:
            return arg
    return None


def _ui_backend() -> str:
    """qt | tk | explicit legacy qml."""
    return (os.environ.get("VNTEXT_UI") or "tk").strip().lower()


def _launch_qml() -> int:
    from qml_ui.bridge import launch_app

    return launch_app(VERSION)


def _launch_qml_preview() -> int:
    return _launch_qml()


if is_frozen() and _release_cli_mode() is None:
    from vntext.app_update import apply_pending_update_on_startup

    if apply_pending_update_on_startup() == "restarting":
        sys.exit(0)

from vntext_studio import VERSION


def _launch_tk() -> None:
    from vntext_studio import VNTextApp

    app = VNTextApp()
    if is_frozen():
        from vntext.app_update import maybe_prompt_update

        maybe_prompt_update(app, VERSION)
    app.mainloop()


def _launch_qt() -> int:
    from vntext.app_update import maybe_prompt_update
    from vntext.qt_app import launch_qt_window

    app, win = launch_qt_window(VERSION)
    if is_frozen():
        maybe_prompt_update(win, VERSION)
    win.show()
    return app.exec()


def main() -> None:
    mode = _release_cli_mode()
    if mode:
        from vntext import release_verify

        if mode == "--release-verify":
            raise SystemExit(release_verify.run_release_verify())
        if mode == "--release-verify-update":
            raise SystemExit(release_verify.run_release_verify_update())
        if mode == "--release-verify-qml":
            raise SystemExit(release_verify.run_release_verify_qml())
        if mode == "--release-version":
            raise SystemExit(release_verify.run_release_version())

    backend = _ui_backend()
    if backend in ("qml", "qml-preview", "quick"):
        try:
            raise SystemExit(_launch_qml())
        except ImportError:
            if backend in ("qml", "qml-preview", "quick", "auto", ""):
                raise SystemExit(_launch_qt())
            raise
    if backend in ("tk", "tkinter"):
        _launch_tk()
        return
    if backend in ("qt", "pyside6"):
        try:
            raise SystemExit(_launch_qt())
        except ImportError:
            raise SystemExit(_launch_qml())
    if backend in ("auto", ""):
        try:
            raise SystemExit(_launch_qml())
        except ImportError:
            try:
                raise SystemExit(_launch_qt())
            except ImportError:
                _launch_tk()
                return
    _launch_tk()


if __name__ == "__main__":
    main()
