# -*- coding: utf-8 -*-
"""Normalize module header: coding, docstring, __future__, then bootstrap."""
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
TESTS, ROOT, LIB = bootstrap(__file__)"""

HARNESS = """sys.path.insert(0, str(TESTS / "harness" / "crash"))
sys.path.insert(0, str(TESTS / "harness" / "vh_parity"))
sys.path.insert(0, str(TESTS / "harness" / "naninovel"))"""

SKIP_LINE_PREFIXES = (
    "import sys",
    "from pathlib import Path",
    "def _tests_lib_on_path",
    "    cur = Path(__file__)",
    "    while cur.name",
    "        cur = cur.parent",
    '    lib = cur / "lib"',
    "    p = str(lib)",
    "    if p not in sys.path",
    "        sys.path.insert(0, p)",
    "_tests_lib_on_path()",
    "from bootstrap import bootstrap",
    "TESTS, ROOT, LIB = bootstrap",
    'sys.path.insert(0, str(TESTS / "harness"',
)


def needs_harness(path: Path) -> bool:
    return path.relative_to(TESTS).parts[0] == "harness"


def is_junk_line(line: str) -> bool:
    if line.strip() == "":
        return True
    return any(line.startswith(p) for p in SKIP_LINE_PREFIXES)


def tail_after_bootstrap(src: str) -> str:
    token = "TESTS, ROOT, LIB = bootstrap(__file__)\n"
    if token not in src:
        return src
    tail = src.rsplit(token, 1)[-1]
    lines = tail.splitlines(keepends=True)
    i = 0
    while i < len(lines) and is_junk_line(lines[i]):
        i += 1
    return "".join(lines[i:]).lstrip("\n")


def extract_meta_and_body(src: str) -> tuple[str, str, str, str]:
    body = tail_after_bootstrap(src)

    coding = ""
    if re.match(r"^#.*coding[:=]", body):
        line, _, body = body.partition("\n")
        coding = line + "\n"

    doc = ""
    s = body.lstrip("\n")
    if s.startswith('"""') or s.startswith("'''"):
        q = s[:3]
        end = s.find(q, 3)
        if end != -1:
            doc = s[: end + 3] + "\n"
            body = s[end + 3 :]
            if body.startswith("\n"):
                body = body[1:]

    future = ""
    while True:
        s = body.lstrip("\n")
        if not s.startswith("from __future__"):
            break
        line, _, _ = s.partition("\n")
        future += line + "\n"
        body = s[len(line) + 1 :]

    # meta may also exist before bootstrap in original mangled file
    head = src.split("TESTS, ROOT, LIB = bootstrap(__file__)")[0]
    if not coding and re.search(r"^#.*coding[:=]", head, re.M):
        coding = re.search(r"^#.*coding[:=].*$", head, re.M).group(0) + "\n"
    if not doc:
        m = re.search(r'^\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')', head, re.M)
        if m:
            doc = m.group(1) + "\n"
    if not future:
        m = re.search(r"^from __future__ import[^\n]+", head, re.M)
        if m:
            future = m.group(0) + "\n"

    lines = body.splitlines(keepends=True)
    i = 0
    while i < len(lines) and is_junk_line(lines[i]):
        i += 1
    body = "".join(lines[i:]).lstrip("\n")
    return coding, doc, future, body


def fix_file(path: Path) -> bool:
    if path.name in ("bootstrap.py", "work_paths.py", "__init__.py"):
        return False
    raw = path.read_text(encoding="utf-8")
    if "bootstrap(__file__)" not in raw and path.parent.name != "unit":
        return False
    if "bootstrap(__file__)" not in raw:
        return False

    coding, doc, future, body = extract_meta_and_body(raw)
    chunks = [c.rstrip("\n") for c in (coding, doc, future) if c]
    chunks.append(PREAMBLE)
    if needs_harness(path):
        chunks.append(HARNESS)
    if body.strip():
        chunks.append(body.rstrip("\n"))
    new_text = "\n\n".join(chunks) + "\n"
    if new_text != raw:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main() -> int:
    skip = {
        "reorganize_tests_layout.py",
        "fix_bootstrap_order.py",
        "add_lib_preamble.py",
        "normalize_test_headers.py",
    }
    n = 0
    for folder in ("unit", "lib", "tools", "harness"):
        for path in sorted((TESTS / folder).rglob("*.py")):
            if path.name in skip:
                continue
            if fix_file(path):
                n += 1
                print(path.relative_to(TESTS))
    print(f"normalized {n} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
