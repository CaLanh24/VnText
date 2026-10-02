# -*- coding: utf-8 -*-
"""Ensure lib/ is on sys.path before bootstrap import."""
from __future__ import annotations

import re
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]

PREAMBLE = """import sys
from pathlib import Path

def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    p = str(lib)
    if p not in sys.path:
        sys.path.insert(0, p)

_tests_lib_on_path()
from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)
"""

HARNESS_TAIL = """sys.path.insert(0, str(TESTS / "harness" / "crash"))
sys.path.insert(0, str(TESTS / "harness" / "vh_parity"))
sys.path.insert(0, str(TESTS / "harness" / "naninovel"))
"""

OLD_BOOTSTRAP = re.compile(
    r"from bootstrap import bootstrap\s*\n"
    r"TESTS, ROOT, LIB = bootstrap\(__file__\)\s*\n"
    r"(?:import sys\s*\n)?"
    r"(?:sys\.path\.insert\(0, str\(TESTS / \"harness\".*\n)*",
    re.MULTILINE,
)


def needs_harness(path: Path) -> bool:
    rel = path.relative_to(TESTS).as_posix()
    return rel.startswith("harness/")


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "from bootstrap import bootstrap" not in text:
        return False
    text = OLD_BOOTSTRAP.sub("", text)
    block = PREAMBLE + ("\n" + HARNESS_TAIL if needs_harness(path) else "")
    # insert after docstring + __future__
    pos = 0
    if text.startswith('"""') or text.startswith("'''"):
        q = '"""' if text.startswith('"""') else "'''"
        end = text.find(q, 3)
        if end != -1:
            pos = end + 3
            if pos < len(text) and text[pos] == "\n":
                pos += 1
    future = ""
    rest_start = pos
    for line in text[pos:].splitlines(keepends=True):
        if line.startswith("from __future__"):
            future += line
            rest_start += len(line)
        elif line.strip() == "" and not future:
            rest_start += len(line)
        elif future:
            break
        else:
            break
    header = text[:pos] + future
    if header and not header.endswith("\n"):
        header += "\n"
    rest = text[rest_start:].lstrip("\n")
    new_text = header + "\n" + block + "\n" + rest
    if new_text != path.read_text(encoding="utf-8"):
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main() -> int:
    n = 0
    for folder in ("unit", "lib", "tools", "harness"):
        for path in (TESTS / folder).rglob("*.py"):
            if path.name in ("bootstrap.py", "reorganize_tests_layout.py", "fix_bootstrap_order.py", "add_lib_preamble.py"):
                continue
            if fix_file(path):
                n += 1
    print(f"patched {n} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
