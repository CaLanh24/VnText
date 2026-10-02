# -*- coding: utf-8 -*-
"""Fix bootstrap block order: __future__ must be first."""
from __future__ import annotations

import re
from pathlib import Path

TESTS = Path(__file__).resolve().parents[1]

HARNESS_BLOCK = """sys.path.insert(0, str(TESTS / "harness" / "crash"))
sys.path.insert(0, str(TESTS / "harness" / "vh_parity"))
sys.path.insert(0, str(TESTS / "harness" / "naninovel"))
"""

BOOTSTRAP_SIMPLE = """from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)
"""

BOOTSTRAP_HARNESS = BOOTSTRAP_SIMPLE + "import sys\n" + HARNESS_BLOCK

BOOTSTRAP_RE = re.compile(
    r"from bootstrap import bootstrap\s*\n"
    r"TESTS, ROOT, LIB = bootstrap\(__file__\)\s*\n"
    r"(?:import sys\s*\n)?"
    r"(?:sys\.path\.insert\(0, str\(TESTS / \"harness\".*\n)*",
    re.MULTILINE,
)


def needs_harness(path: Path) -> bool:
    rel = path.relative_to(TESTS).as_posix()
    if rel.startswith("harness/"):
        return True
    if rel.startswith("tools/"):
        return False
    if rel.startswith("lib/"):
        return path.name not in ("bootstrap.py", "work_paths.py", "__init__.py")
    return False


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "from bootstrap import bootstrap" not in text:
        return False

    # Strip existing bootstrap block
    text = BOOTSTRAP_RE.sub("", text)

    # Strip duplicate path setup
    text = re.sub(
        r"if str\(ROOT\) not in sys\.path:.*\n\s*sys\.path\.insert\(0, str\(ROOT\)\)\n",
        "",
        text,
    )
    text = re.sub(
        r"if str\(TESTS\) not in sys\.path:.*\n\s*sys\.path\.insert\(0, str\(TESTS\)\)\n",
        "",
        text,
    )
    text = re.sub(
        r"^ROOT = Path\(__file__\)\.resolve\(\)\.parent\n",
        "",
        text,
        flags=re.MULTILINE,
    )

    bootstrap = BOOTSTRAP_HARNESS if needs_harness(path) else BOOTSTRAP_SIMPLE

    # Parse header: docstring + future
    pos = 0
    if text.startswith('"""') or text.startswith("'''"):
        q = '"""' if text.startswith('"""') else "'''"
        end = text.find(q, 3)
        if end != -1:
            pos = end + 3
            if pos < len(text) and text[pos] == "\n":
                pos += 1

    future_lines: list[str] = []
    rest_start = pos
    for line in text[pos:].splitlines(keepends=True):
        if line.startswith("from __future__"):
            future_lines.append(line)
            rest_start += len(line)
        elif line.strip() == "" and not future_lines:
            rest_start += len(line)
        elif future_lines:
            break
        else:
            break

    header = text[:pos] + "".join(future_lines)
    if header and not header.endswith("\n"):
        header += "\n"
    rest = text[rest_start:].lstrip("\n")

    # Remove stray duplicate imports at top of rest
    rest = re.sub(r"^import sys\n", "", rest, count=1, flags=re.MULTILINE)

    new_text = header + "\n" + bootstrap + "\n" + rest
    if new_text != path.read_text(encoding="utf-8"):
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main() -> int:
    changed = 0
    for folder in ("unit", "lib", "tools", "harness"):
        for path in (TESTS / folder).rglob("*.py"):
            if path.name in ("bootstrap.py", "reorganize_tests_layout.py", "fix_bootstrap_order.py"):
                continue
            if fix_file(path):
                changed += 1
                print(f"fixed {path.relative_to(TESTS)}")
    print(f"done, fixed {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
