"""Production source must not contain test-fixture identities or local game paths."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_LITERALS = (
    "SampleGame",
    "SampleGame_Data",
    "sample_fixture_id",
    "C:\\Users\\example-user",
    "E:\\game_copy",
)


class CoverageNoProdPathIdTests(unittest.TestCase):
    def test_runtime_source_has_no_test_fixture_identity_literals(self):
        hits = []
        for root_name in ("vntext", "vntext_worker", "wpf_app", "release"):
            root = ROOT / root_name
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                # Build outputs are ignored local artifacts, not runtime
                # source. They can contain machine-specific file lists.
                relative_parts = path.relative_to(ROOT).parts
                if any(
                    part.lower() in {"bin", "obj", "__pycache__"}
                    or part.lower().endswith(".tests")
                    for part in relative_parts
                ):
                    continue
                if not path.is_file() or path.suffix.lower() not in {".py", ".cs", ".ps1", ".bat", ".json", ".txt"}:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                for literal in FORBIDDEN_LITERALS:
                    if literal.casefold() in text.casefold():
                        hits.append(f"{path.relative_to(ROOT).as_posix()}: {literal}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
