"""Gate for the Impeccable UI hook: run it only when UI files are touched.

PostToolUse: scan the hook payload (tool input / patch text) for UI paths.
Stop: look at the working tree (git status) for changed UI paths.
Anything else exits 0 without starting Impeccable, so docs/Python edits stay
cheap and never trigger the launcher (which may fetch its engine binary).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UI_PATH = re.compile(r"(?:wpf_app[\\/][^\s\"']+\.(?:xaml|cs)|[^\s\"']+\.(?:html|css))\b", re.IGNORECASE)


def _changed_ui_files() -> bool:
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(UI_PATH.search(line[3:]) for line in out.splitlines())


def main() -> int:
    payload = sys.stdin.read()
    try:
        event = str(json.loads(payload).get("hook_event_name") or "")
    except (ValueError, AttributeError):
        event = ""
    touched = _changed_ui_files() if event == "Stop" else bool(UI_PATH.search(payload))
    if not touched:
        return 0
    verify = subprocess.run([sys.executable, str(ROOT / "release" / "verify_skill.py")],
                            capture_output=True, check=False)
    if verify.returncode != 0:
        return verify.returncode
    home = Path(os.path.expanduser("~")) / ".codex" / "skills" / "impeccable" / "scripts"
    launcher = [str(home / "impeccable.cmd")] if os.name == "nt" else [str(home / "impeccable")]
    if os.name == "nt":
        launcher = ["cmd", "/c", *launcher]
    return subprocess.run([*launcher, "hook"], input=payload, text=True, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
