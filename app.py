"""Headless release-verification CLI for the Python backend.

The shipped desktop UI is the WPF application (``wpf_app``); the legacy
Tk/Qt/QML Python UIs were removed on 2026-11-25. This entry only keeps the
``--release-*`` verification modes used by release tooling.
"""
from __future__ import annotations

import sys

from vntext.runtime_paths import configure_runtime

configure_runtime()

_RELEASE_MODES = ("--release-verify", "--release-verify-update", "--release-version")


def _release_cli_mode() -> str | None:
    for arg in sys.argv[1:]:
        if arg in _RELEASE_MODES:
            return arg
    return None


def main() -> None:
    mode = _release_cli_mode()
    if mode is None:
        raise SystemExit(
            "VNText Studio: the desktop UI is the WPF app (wpf_app/VNText.Studio.App). "
            "This script only accepts " + ", ".join(_RELEASE_MODES) + "."
        )
    from vntext import release_verify

    if mode == "--release-verify":
        raise SystemExit(release_verify.run_release_verify())
    if mode == "--release-verify-update":
        raise SystemExit(release_verify.run_release_verify_update())
    raise SystemExit(release_verify.run_release_version())


if __name__ == "__main__":
    main()
