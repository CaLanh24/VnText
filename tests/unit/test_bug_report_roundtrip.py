"""A bug report must carry enough structure to replay the engine verdict, and nothing that identifies a game."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tests.lib.work_paths import work_temp_dir
from tests.tools.synth_from_report import synthesize
from tests.unit.test_scan_layout_matrix import LAYOUTS
from vntext.bug_report import build_report, fingerprint, sanitise_text
from vntext.renpy_adapter import detect_engine


class BugReportRoundTripTests(unittest.TestCase):
    def test_stand_in_from_the_report_reproduces_the_engine_verdict_for_every_layout(self):
        base = work_temp_dir("bug-report-roundtrip")
        for name, (build, _allowed) in LAYOUTS.items():
            with self.subTest(layout=name), tempfile.TemporaryDirectory(dir=base) as temp:
                root = Path(temp) / "original"
                root.mkdir()
                build(root)
                report = fingerprint(root)
                stand_in = synthesize(report, Path(temp) / "stand-in")
                self.assertEqual(detect_engine(root).engine, detect_engine(stand_in).engine)

    def test_report_contains_no_names_contents_or_paths(self):
        base = work_temp_dir("bug-report-roundtrip")
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp) / "Secret Game Title"
            (root / "game").mkdir(parents=True)
            (root / "game" / "ChapterOne_Hello.rpy").write_text('label start:\n    "SECRET DIALOGUE"\n', encoding="utf-8")
            (root / "SecretGame.exe").write_bytes(b"MZ")
            bs = chr(92)
            lines = [f"Mục: ChapterOne_Hello.rpy trong {root}{bs}game", "C:" + bs + "Users" + bs + "someone" + bs + "x"]
            target = build_report(root, Path(temp) / "out", log_lines=lines)
            with zipfile.ZipFile(target) as archive:
                blob = b"".join(archive.read(n) for n in archive.namelist()).decode("utf-8", "replace")
            for secret in ("Secret Game Title", "SecretGame", "ChapterOne", "SECRET DIALOGUE", "someone", str(root)):
                self.assertNotIn(secret.casefold(), blob.casefold())
            self.assertEqual("RENPY_LOOSE_SOURCE", json.loads(zipfile.ZipFile(target).read("report.json"))["engine_detection"]["engine"])

    def test_sanitise_text_replaces_known_names_and_any_drive_path(self):
        bs = chr(92)
        out = sanitise_text("open D:" + bs + "x" + bs + "y.txt and Hidden_Name.rpy", Path("C:/g"), {"Hidden_Name.rpy"})
        self.assertNotIn("Hidden_Name", out)
        self.assertNotIn("D:" + bs + "x", out)


    def test_worker_task_builds_the_bundle_and_refuses_a_missing_game(self):
        from unittest.mock import patch
        from vntext_worker.task_runners import run_bug_report_worker
        base = work_temp_dir("bug-report-roundtrip")
        with tempfile.TemporaryDirectory(dir=base) as temp:
            game = Path(temp) / "g"
            (game / "game").mkdir(parents=True)
            (game / "game" / "script.rpy").write_text("label start:" + chr(10) + "    return" + chr(10), encoding="utf-8")
            done = []
            with patch("vntext_worker.task_runners.emit_complete", side_effect=lambda _id, **kw: done.append(kw)), patch("vntext_worker.task_runners.emit_progress"):
                run_bug_report_worker("t", {"src": str(game), "out": str(Path(temp) / "out"), "log_lines": ["a"]}, lambda: False)
                run_bug_report_worker("t", {"src": str(Path(temp) / "missing"), "out": str(Path(temp) / "out2")}, lambda: False)
            self.assertTrue(done[0]["ok"])
            self.assertTrue(list((Path(temp) / "out").glob("vntext-bug-report-*.zip")))
            self.assertFalse(done[1]["ok"])


if __name__ == "__main__":
    unittest.main()
