"""Application extract preflight tests for generic Unity inventory evidence."""

from __future__ import annotations

import sys
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    value = str(lib)
    if value not in sys.path:
        sys.path.insert(0, value)


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

import csv
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from vntext.app_tasks import run_extract_task
from work_paths import work_temp_dir


WORK = work_temp_dir("unity_preflight")


class UnityPreflightTests(unittest.TestCase):
    def test_extract_writes_unity_inventory_before_package(self):
        with tempfile.TemporaryDirectory(dir=str(WORK), prefix="detected-") as name:
            root = Path(name)
            game = root / "SampleVN"
            data = game / "SampleVN_Data" / "StreamingAssets"
            data.mkdir(parents=True)
            (game / "SampleVN.exe").write_bytes(b"MZ fixture")
            (data / "dialogue").write_text("NPC: Hello from Unity\n", encoding="utf-8")
            output = root / "package"
            logs: list[str] = []
            completed: list[dict] = []
            events: list[dict] = []

            with patch(
                "vntext.unity_analyzer._sha256_file",
                side_effect=AssertionError("Extract preflight must not hash full payloads"),
            ) as hash_file:
                run_extract_task(
                    str(game),
                    str(output),
                    "deep",
                    "balanced",
                    True,
                    progress=events.append,
                    log=logs.append,
                    complete=completed.append,
                )
                hash_file.assert_not_called()

            self.assertTrue(completed and completed[-1]["ok"], completed)
            self.assertTrue(logs and logs[0].startswith("Unity analyzer: DETECTED"), logs)
            report_path = output / "unity_analysis.json"
            self.assertTrue(report_path.is_file())
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertTrue(report["inventory_complete"])
            self.assertTrue(report["unity"]["detected"])
            self.assertFalse(report["summary"]["sha256_enabled"])
            self.assertGreaterEqual(report["summary"]["resource_count"], 2)
            self.assertTrue(all(resource["sha256"] is None for resource in report["resources"]))
            steps = {event.get("step") for event in events}
            self.assertTrue({"unity_enumerate", "unity_classify"}.issubset(steps), steps)
            self.assertNotIn("unity_hash", steps)
            self.assertTrue((output / "manifest.json").is_file())

    def test_incomplete_unity_inventory_stops_extract(self):
        with tempfile.TemporaryDirectory(dir=str(WORK), prefix="incomplete-") as name:
            root = Path(name)
            game = root / "SampleVN"
            game.mkdir()
            output = root / "package"
            report = {
                "scan_root": str(game),
                "unity": {"detected": True, "status": "REVIEW_REQUIRED"},
                "inventory_complete": False,
                "scan_errors": [{"path": str(game / "locked.assets"), "error": "read failed"}],
                "resources": [],
                "summary": {"resource_count": 0, "unknown_resources": 0, "text_candidate_resources": 0},
            }
            completed: list[dict] = []

            with patch("vntext.unity_analyzer.analyze_unity_game", return_value=report):
                with patch("vntext.app_tasks.extract_project") as extract:
                    run_extract_task(
                        str(game),
                        str(output),
                        "deep",
                        "balanced",
                        True,
                        progress=lambda _info: None,
                        log=lambda _text: None,
                        complete=completed.append,
                    )

            extract.assert_not_called()
            self.assertTrue(completed and not completed[-1]["ok"], completed)
            self.assertIn("preflight", completed[-1]["error"].lower())
            self.assertFalse((output / "manifest.json").exists())

    def test_enumeration_and_read_errors_still_fail_closed_without_hashing(self):
        for error_kind in ("enumeration", "read"):
            with self.subTest(error_kind=error_kind):
                with tempfile.TemporaryDirectory(dir=str(WORK), prefix=f"{error_kind}-error-") as name:
                    root = Path(name)
                    game = root / "SampleVN"
                    data = game / "SampleVN_Data" / "StreamingAssets"
                    data.mkdir(parents=True)
                    (game / "SampleVN.exe").write_bytes(b"MZ fixture")
                    (data / "dialogue.txt").write_text("Hello from Unity\n", encoding="utf-8")
                    output = root / "package"
                    completed: list[dict] = []

                    if error_kind == "enumeration":
                        original_walk = os.walk

                        def walk_with_error(path, *args, **kwargs):
                            onerror = kwargs.get("onerror")
                            if onerror is not None:
                                onerror(PermissionError("synthetic enumeration error"))
                            yield from original_walk(path, *args, **kwargs)

                        inventory_patch = patch("vntext.unity_analyzer.os.walk", side_effect=walk_with_error)
                    else:
                        inventory_patch = patch(
                            "vntext.unity_analyzer._safe_read",
                            return_value=(b"", "synthetic read error"),
                        )

                    with inventory_patch, patch(
                        "vntext.unity_analyzer._sha256_file",
                        side_effect=AssertionError("Extract preflight must not hash full payloads"),
                    ) as hash_file:
                        run_extract_task(
                            str(game),
                            str(output),
                            "deep",
                            "balanced",
                            True,
                            progress=lambda _info: None,
                            log=lambda _text: None,
                            complete=completed.append,
                        )
                        hash_file.assert_not_called()

                    self.assertTrue(completed and not completed[-1]["ok"], completed)
                    self.assertIn("preflight", completed[-1]["error"].lower())
                    self.assertFalse((output / "unity_analysis.json").exists())
                    self.assertFalse((output / "manifest.json").exists())

    def test_extract_preflight_forwards_progress_and_cancel_during_classification(self):
        with tempfile.TemporaryDirectory(dir=str(WORK), prefix="cancel-classify-") as name:
            root = Path(name)
            game = root / "SampleVN"
            data = game / "SampleVN_Data" / "StreamingAssets"
            data.mkdir(parents=True)
            (game / "SampleVN.exe").write_bytes(b"MZ synthetic fixture")
            (data / "dialogue.txt").write_text("Hello from a synthetic fixture\n", encoding="utf-8")
            for index in range(40):
                (data / f"line-{index:02d}.txt").write_text(f"Hello {index}\n", encoding="utf-8")
            output = root / "package"
            events: list[dict] = []
            completed: list[dict] = []
            cancelled = False

            def progress(info: dict) -> None:
                nonlocal cancelled
                events.append(info)
                if info.get("step") == "unity_classify":
                    cancelled = True

            run_extract_task(
                str(game),
                str(output),
                "deep",
                "balanced",
                True,
                progress=progress,
                log=lambda _text: None,
                complete=completed.append,
                is_cancelled=lambda: cancelled,
            )

            steps = {event.get("step") for event in events}
            self.assertIn("unity_classify", steps)
            self.assertNotIn("unity_hash", steps)
            self.assertTrue(completed and not completed[-1]["ok"], completed)
            self.assertEqual(completed[-1]["error"], "cancelled")
            self.assertFalse((output / "unity_analysis.json").exists())
            self.assertFalse((output / "manifest.json").exists())

    def test_extract_keeps_preflight_file_set_and_existing_row_order(self):
        with tempfile.TemporaryDirectory(dir=str(WORK), prefix="inventory-reuse-") as name:
            root = Path(name)
            game = root / "SampleVN"
            data = game / "SampleVN_Data" / "StreamingAssets"
            nested = data / "a" / "deep"
            sibling = data / "b"
            nested.mkdir(parents=True)
            sibling.mkdir()
            (game / "SampleVN.exe").write_bytes(b"MZ synthetic fixture")
            (data / "z-first.txt").write_text("NPC: First line\n", encoding="utf-8")
            (data / "a" / "shallow.txt").write_text("NPC: Second line\n", encoding="utf-8")
            (nested / "nested.txt").write_text("NPC: Nested line\n", encoding="utf-8")
            (sibling / "sibling.txt").write_text("NPC: Sibling line\n", encoding="utf-8")
            expected_order = [
                str(path.relative_to(game))
                for path in game.rglob("*")
                if path.is_file() and path.suffix.lower() == ".txt"
            ]
            output = root / "package"
            completed: list[dict] = []
            late_file_added = False

            def add_file_after_preflight_inventory(info: dict) -> None:
                nonlocal late_file_added
                if not late_file_added and info.get("step") == "unity_classify":
                    (data / "late.txt").write_text("NPC: Late line\n", encoding="utf-8")
                    late_file_added = True

            run_extract_task(
                str(game),
                str(output),
                "deep",
                "balanced",
                True,
                progress=add_file_after_preflight_inventory,
                log=lambda _text: None,
                complete=completed.append,
            )

            self.assertTrue(completed and completed[-1]["ok"], completed)
            self.assertTrue(late_file_added)
            with (output / "translation.csv").open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["file_path"] for row in rows], expected_order)


if __name__ == "__main__":
    unittest.main()
