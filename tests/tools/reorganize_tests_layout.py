# -*- coding: utf-8 -*-
"""One-shot move tests/*.py into lib/unit/harness/tools. Run from repo root."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]
ROOT = TESTS.parent

MOVES: dict[str, str] = {}

# lib
for name in (
    "work_paths.py",
    "worker_test_lib.py",
    "sample_unity_e2e_lib.py",
    "unity_patch_baseline.py",
    "titleui_fixture.py",
    "coverage_fixture.py",
    "coverage_e2e_lib.py",
    "data_unity3d_isolation.py",
    "addressables_bundle.py",
):
    MOVES[name] = "lib"

# tools
for name in (
    "cleanup_work_artifacts.py",
    "capture_golden.py",
    "capture_unity_patch_baseline.py",
):
    MOVES[name] = "tools"

# harness/crash
for name in (
    "run_crash_investigation.py",
    "probe_naninovel_grow.py",
    "play_naninovel_vh.py",
):
    MOVES[name] = "harness/crash"

# harness/naninovel
for name in ("bench_naninovel_apply.py", "bench_naninovel_en_vh.py"):
    MOVES[name] = "harness/naninovel"

# harness/vh_parity
for name in (
    "run_vh_parity_e2e.py",
    "run_vh_parity_play.py",
    "run_app_patch_defaultui_e2e.py",
    "vh_parity_defaultui_chrome.py",
    "vh_parity_batch_loop.py",
    "vh_parity_local_validate.py",
    "vh_parity_coverage_fill.py",
    "vh_parity_cache.py",
):
    MOVES[name] = "harness/vh_parity"

# unit: remaining test_*.py at tests root
for src in TESTS.glob("test_*.py"):
    if src.name not in MOVES:
        MOVES[src.name] = "unit"

BOOTSTRAP_BLOCK = """from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)
import sys
sys.path.insert(0, str(TESTS / "harness" / "crash"))
sys.path.insert(0, str(TESTS / "harness" / "vh_parity"))
sys.path.insert(0, str(TESTS / "harness" / "naninovel"))
"""

# Patterns to strip/replace in moved files
PATH_SETUP_RE = re.compile(
    r"(?:^ROOT = Path\(__file__\)\.resolve\(\)\.parent(?:\.parent)?\s*\n"
    r"(?:TESTS = .*\n)?"
    r"(?:if str\(ROOT\) not in sys\.path:.*\n)?"
    r"(?:\s*sys\.path\.insert\(0, str\(ROOT\)\)\s*\n)?"
    r"(?:if str\(TESTS\) not in sys\.path:.*\n)?"
    r"(?:\s*sys\.path\.insert\(0, str\(TESTS\)\)\s*\n)?"
    r")+",
    re.MULTILINE,
)

TESTS_PARENT_RE = re.compile(
    r"TESTS = Path\(__file__\)\.resolve\(\)\.parent\nROOT = TESTS\.parent\n",
    re.MULTILINE,
)


def patch_content(text: str, dest_rel: str) -> str:
    if dest_rel == "lib/work_paths.py":
        text = text.replace(
            "TESTS = Path(__file__).resolve().parent\nROOT = TESTS.parent",
            "LIB = Path(__file__).resolve().parent\nTESTS = LIB.parent\nROOT = TESTS.parent",
        )
        text = text.replace('ROOT / "tests" / "golden"', "TESTS / 'golden'")
        return text

    # Skip if already bootstrapped
    if "from bootstrap import bootstrap" in text:
        return text

    # Remove common manual path hacks at top (after future/docstring imports)
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("TESTS = Path(__file__)"):
            # skip TESTS/ROOT/sys.path block
            while i < len(lines) and (
                lines[i].startswith("TESTS =")
                or lines[i].startswith("ROOT =")
                or "sys.path.insert" in lines[i]
                or lines[i].strip() == ""
            ):
                i += 1
            continue
        if line.startswith("ROOT = Path(__file__)"):
            while i < len(lines) and (
                lines[i].startswith("ROOT =")
                or lines[i].startswith("TESTS =")
                or "sys.path.insert" in lines[i]
            ):
                i += 1
            continue
        out.append(line)
        i += 1
    text = "".join(out)

    # Insert bootstrap after module docstring / future imports
    insert_at = 0
    if text.startswith('"""') or text.startswith("'''"):
        q = '"""' if text.startswith('"""') else "'''"
        end = text.find(q, 3)
        if end != -1:
            insert_at = end + 3
            if insert_at < len(text) and text[insert_at] == "\n":
                insert_at += 1
    elif text.startswith("from __future__"):
        for j, ln in enumerate(text.splitlines(keepends=True)):
            insert_at += len(ln)
            if not ln.startswith("from __future__"):
                break

    text = text[:insert_at] + "\n" + BOOTSTRAP_BLOCK + text[insert_at:]
    return text


def main() -> int:
    for sub in ("lib", "unit", "tools", "harness/crash", "harness/naninovel", "harness/vh_parity"):
        (TESTS / sub).mkdir(parents=True, exist_ok=True)

    moved = 0
    for name, folder in MOVES.items():
        src = TESTS / name
        if not src.is_file():
            continue
        dest = TESTS / folder / name
        if dest.exists():
            continue
        text = src.read_text(encoding="utf-8")
        text = patch_content(text, f"{folder}/{name}")
        dest.write_text(text, encoding="utf-8")
        src.unlink()
        moved += 1
        print(f"moved {name} -> {folder}/")

    # touch lib __init__
    (TESTS / "lib" / "__init__.py").write_text("", encoding="utf-8")
    print(f"done, moved {moved} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
