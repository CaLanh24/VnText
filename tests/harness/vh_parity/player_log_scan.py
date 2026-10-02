# -*- coding: utf-8 -*-

"""Fail-closed scanner for Unity Player.log evidence."""

from __future__ import annotations

import re
from pathlib import Path


def scan_player_log(path: Path) -> dict:
    """Read a Player.log and classify runtime evidence for a play route.

    A permission exception is an environment precondition failure and is
    therefore ``NOT_TESTABLE``. Other runtime error markers are ``FAIL``.
    Screenshots are deliberately not considered here.
    """
    if not path.is_file():
        return {
            "missing": True,
            "status": "NOT_TESTABLE",
            "reasons": ["player_log_missing"],
            "markers": {},
            "error_lines": [],
            "tail": "",
        }

    text = path.read_text(encoding="utf-8", errors="ignore")
    lower = text.lower()
    lines = text.splitlines()
    markers = {
        # Existing diagnostic markers retained for crash-investigation users.
        "serialization_layout": "serialization layout" in lower,
        "unity_ui_text": "unityengine.ui.text" in lower,
        "naninovel_script": "naninovel.script" in lower,
        "nscripts_init": "nscripts/init" in lower,
        "exception": bool(re.search(r"\b[\w.]*exception\b", lower)),
        "unobserved_task_exception": "unobservedtaskexception" in lower,
        "unauthorized_access_exception": "unauthorizedaccessexception" in lower,
        "stacktrace": "stacktrace" in lower or "stack trace" in lower,
        "fatal": bool(re.search(r"\bfatal\b", lower)),
        "crash_marker": "crash!!!" in lower,
        "corruption": "corrupt" in lower,
        "resources_corrupted": "resources.assets" in lower and "corrupt" in lower,
        "out_of_bounds": bool(
            re.search(r"out\s+of\s+bounds|index\s+out\s+of\s+range|\boob\b", lower)
        ),
        "position_oob": "position out of bounds" in lower,
        "sigsegv": "sigsegv" in lower,
        "abort": "abort()" in lower or "abort " in lower,
        "access_violation": "access violation" in lower,
    }

    error_lines = [
        line
        for line in lines
        if any(
            marker in line.lower()
            for marker in (
                "error",
                "exception",
                "fatal",
                "crash!!!",
                "corrupt",
                "failed to load",
                "out of bounds",
                "out of range",
                "access violation",
                "abort",
            )
        )
    ]
    serialization_lines = [
        line for line in lines if "serialization layout" in line.lower()
    ]
    reasons: list[str] = []
    if markers["unauthorized_access_exception"]:
        reason = "UnauthorizedAccessException"
        if "c:\\gamedata" in lower:
            reason += ": external game-data write permission prerequisite"
        reasons.append(reason)
    if markers["unobserved_task_exception"]:
        reasons.append("UnobservedTaskException")
    if markers["exception"] and not markers["unauthorized_access_exception"]:
        reasons.append("Exception")
    for key, label in (
        ("fatal", "Fatal"),
        ("crash_marker", "Crash!!!"),
        ("corruption", "corruption"),
        ("out_of_bounds", "out-of-bounds"),
        ("stacktrace", "stacktrace"),
        ("sigsegv", "SIGSEGV"),
        ("abort", "abort"),
        ("access_violation", "access violation"),
    ):
        if markers[key]:
            reasons.append(label)

    not_testable = markers["unauthorized_access_exception"]
    status = "NOT_TESTABLE" if not_testable else ("FAIL" if reasons else "PASS")
    return {
        "missing": False,
        "bytes": len(text.encode("utf-8", errors="ignore")),
        "lines": len(lines),
        "status": status,
        "reasons": reasons,
        "markers": markers,
        "serialization_lines": serialization_lines[:20],
        "error_lines": error_lines[:40],
        "tail": "\n".join(lines[-40:]),
    }
