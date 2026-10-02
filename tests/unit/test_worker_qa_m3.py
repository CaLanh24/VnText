"""QA Milestone 3 — full workflow on safe game copy in tests/golden/_work."""

from __future__ import annotations

import sys
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

import csv
import json
import time
import unittest
from pathlib import Path

if str(ROOT / "tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "tests"))

from vntext.mt_ct2 import model_status
from vntext_worker.protocol import PROTOCOL_VERSION
from worker_test_lib import (
    GAME_COPY,
    MODEL_DIR,
    WORK_ROOT,
    assert_under_work,
    complete_for,
    game_copy_asset,
    read_ready,
    run_task,
    start_worker,
    stop_worker,
    venv_python,
)
from work_paths import work_temp_dir

QA_ROOT = work_temp_dir("qa_m3")
PACKAGE = QA_ROOT / "package"


class WorkerQaM3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not venv_python().is_file():
            raise RuntimeError("venv python missing — cannot run QA M3")
        if not (MODEL_DIR / "model.bin").is_file():
            raise RuntimeError(f"model missing: {MODEL_DIR} — chạy ensure_model trước")
        assert_under_work(GAME_COPY)

    def setUp(self):
        QA_ROOT.mkdir(parents=True, exist_ok=True)

    def test_model_status_ready(self):
        status = model_status(MODEL_DIR)
        self.assertTrue(status["ready"])
        self.assertTrue((MODEL_DIR / "model.bin").is_file())

    def test_model_missing_returns_error_without_hang(self):
        mini_pkg = QA_ROOT / "model_err_pkg"
        mini_pkg.mkdir(parents=True, exist_ok=True)
        fields = [
            "key", "source_text", "translation", "context", "file_path",
            "object_info", "import_method", "safety", "backend", "byte_limit", "patch_note",
        ]
        with (mini_pkg / "translation.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\r\n")
            writer.writeheader()
            writer.writerow(
                {
                    "key": "k1",
                    "source_text": "Hello world",
                    "translation": "",
                    "context": "line:1",
                    "file_path": "x.txt",
                    "import_method": "plain_text_line",
                    "safety": "safe",
                    "backend": "plain_text",
                }
            )

        proc = start_worker(
            {
                "VNTEXT_CT2_MODEL": str(QA_ROOT / "missing_model"),
                "VNTEXT_CT2_NO_DOWNLOAD": "1",
            }
        )
        try:
            read_ready(proc, timeout=45)
            events = run_task(
                proc,
                "qa-model-err",
                "translate",
                {"out": str(mini_pkg)},
                timeout=30,
            )
            done = complete_for(events, "qa-model-err")
            self.assertFalse(done.get("ok", True))
            err = (done.get("error") or "").lower()
            self.assertTrue("ctranslate2" in err or "model" in err)
        finally:
            stop_worker(proc)

    def test_full_workflow_game_copy(self):
        src = game_copy_asset()
        out = PACKAGE
        proc = start_worker()
        try:
            read_ready(proc, timeout=60)
            extract = complete_for(
                run_task(
                    proc,
                    "qa-extract",
                    "extract",
                    {
                        "src": str(src),
                        "out": str(out),
                        "mode": "deep",
                        "level": "balanced",
                        "separate_review": True,
                    },
                    timeout=120,
                ),
                "qa-extract",
            )
            self.assertTrue(extract.get("ok"), extract.get("error"))
            csv_path = out / "translation.csv"
            self.assertTrue(csv_path.is_file())
            with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertGreater(len(rows), 0)

            translate = complete_for(
                run_task(proc, "qa-translate", "translate", {"out": str(out)}, timeout=180),
                "qa-translate",
            )
            self.assertTrue(translate.get("ok"), translate.get("error"))
            with csv_path.open(encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.DictReader(fh))
            translated = sum(1 for r in rows if str(r.get("translation") or "").strip())
            self.assertGreater(translated, 0, "translation.csv phải có ít nhất một bản dịch")

            patch = complete_for(
                run_task(
                    proc,
                    "qa-patch",
                    "patch",
                    {"src": str(src), "out": str(out)},
                    timeout=120,
                ),
                "qa-patch",
            )
            self.assertTrue(patch.get("ok"), patch.get("error"))
            patched = out / "Patch_Viet_Hoa" / "COPY_TO_GAME_ROOT"
            self.assertTrue(patched.is_dir())
            self.assertTrue(any(patched.rglob("*")))
        finally:
            stop_worker(proc)

    def _extract_package(self, proc, out: Path) -> None:
        src = game_copy_asset()
        extract = complete_for(
            run_task(
                proc,
                f"qa-extract-{out.name}",
                "extract",
                {
                    "src": str(src),
                    "out": str(out),
                    "mode": "deep",
                    "level": "balanced",
                    "separate_review": True,
                },
                timeout=120,
            ),
            f"qa-extract-{out.name}",
        )
        self.assertTrue(extract.get("ok"), extract.get("error"))

    def test_workflow_second_run(self):
        out = QA_ROOT / "package_run2"
        src = game_copy_asset()
        proc = start_worker()
        try:
            read_ready(proc, timeout=60)
            self._extract_package(proc, out)
            for idx in (1, 2):
                translate = complete_for(
                    run_task(proc, f"qa-tr-{idx}", "translate", {"out": str(out)}, timeout=180),
                    f"qa-tr-{idx}",
                )
                self.assertTrue(translate.get("ok"), translate.get("error"))
                patch = complete_for(
                    run_task(
                        proc,
                        f"qa-pa-{idx}",
                        "patch",
                        {"src": str(src), "out": str(out)},
                        timeout=120,
                    ),
                    f"qa-pa-{idx}",
                )
                self.assertTrue(patch.get("ok"), patch.get("error"))
        finally:
            stop_worker(proc)

    def test_cancel_during_translate(self):
        out = QA_ROOT / "cancel_pkg"
        rows = [
            {
                "key": f"k{i}",
                "source_text": f"Line {i}: Hello traveler number {i}",
                "translation": "",
                "context": "line:1",
                "file_path": "sample.txt",
                "import_method": "plain_text_line",
                "safety": "safe",
                "backend": "plain_text",
            }
            for i in range(10)
        ]
        fields = list(rows[0].keys()) + ["object_info", "byte_limit", "patch_note"]
        out.mkdir(parents=True, exist_ok=True)
        with (out / "translation.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\r\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({name: row.get(name, "") for name in fields})
        (out / "manifest.json").write_text(
            json.dumps(
                {
                    "entries": [
                        {
                            **row,
                            "locator": {"kind": "plain_text_line", "line": index + 1},
                            "duplicate_locations": [],
                            "review_only": False,
                        }
                        for index, row in enumerate(rows)
                    ],
                    "technical_skipped": [],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        proc = start_worker({"VNTEXT_CT2_TEST_DELAY_MS": "300"})
        try:
            assert proc.stdin is not None
            read_ready(proc, timeout=60)
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": "qa-cancel",
                        "task": "translate",
                        "params": {"out": str(out)},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            time.sleep(0.4)
            proc.stdin.write(json.dumps({"v": PROTOCOL_VERSION, "type": "cancel", "id": "qa-cancel"}) + "\n")
            proc.stdin.flush()
            deadline = time.time() + 25
            done = None
            while time.time() < deadline:
                line = proc.stdout.readline()
                if not line:
                    break
                msg = json.loads(line)
                if msg.get("type") == "complete" and msg.get("id") == "qa-cancel":
                    done = msg
                    break
            self.assertIsNotNone(done)
            self.assertFalse(done.get("ok", True))
            self.assertIn("cancel", (done.get("error") or "").lower())
        finally:
            stop_worker(proc)

    def test_worker_killed_then_new_worker(self):
        proc = start_worker()
        try:
            read_ready(proc, timeout=60)
            assert proc.stdin is not None
            proc.stdin.write(
                json.dumps(
                    {
                        "v": PROTOCOL_VERSION,
                        "type": "run",
                        "id": "qa-kill",
                        "task": "sample",
                        "params": {"steps": 50, "delay_ms": 200},
                    }
                )
                + "\n"
            )
            proc.stdin.flush()
            time.sleep(0.25)
            proc.kill()
            proc.wait(timeout=5)
        finally:
            stop_worker(proc)

        proc2 = start_worker()
        try:
            read_ready(proc2, timeout=60)
            done = complete_for(
                run_task(proc2, "qa-after-kill", "sample", {"steps": 2, "delay_ms": 20}, timeout=30),
                "qa-after-kill",
            )
            self.assertTrue(done.get("ok"), done.get("error"))
        finally:
            stop_worker(proc2)

    def test_translate_missing_csv(self):
        proc = start_worker()
        try:
            read_ready(proc, timeout=60)
            done = complete_for(
                run_task(
                    proc,
                    "qa-no-csv",
                    "translate",
                    {"out": str(QA_ROOT / "no_such_package")},
                    timeout=30,
                ),
                "qa-no-csv",
            )
            self.assertFalse(done.get("ok", True))
            self.assertTrue(done.get("error"))
        finally:
            stop_worker(proc)

    def test_translate_empty_csv(self):
        empty_pkg = QA_ROOT / "empty_pkg"
        empty_pkg.mkdir(parents=True, exist_ok=True)
        fields = [
            "key", "source_text", "translation", "context", "file_path",
            "object_info", "import_method", "safety", "backend", "byte_limit", "patch_note",
        ]
        with (empty_pkg / "translation.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            csv.DictWriter(fh, fieldnames=fields, lineterminator="\r\n").writeheader()

        proc = start_worker()
        try:
            read_ready(proc, timeout=60)
            done = complete_for(
                run_task(proc, "qa-empty", "translate", {"out": str(empty_pkg)}, timeout=30),
                "qa-empty",
            )
            self.assertFalse(done.get("ok", True))
            self.assertIn("dòng", (done.get("error") or "").lower())
        finally:
            stop_worker(proc)

    def test_patch_without_translations_fails(self):
        bare_pkg = QA_ROOT / "bare_pkg"
        bare_pkg.mkdir(parents=True, exist_ok=True)
        fields = [
            "key", "source_text", "translation", "context", "file_path",
            "object_info", "import_method", "safety", "backend", "byte_limit", "patch_note",
        ]
        with (bare_pkg / "translation.csv").open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\r\n")
            writer.writeheader()
            writer.writerow(
                {
                    "key": "k1",
                    "source_text": "Hello",
                    "translation": "",
                    "context": "line:1",
                    "file_path": "x.txt",
                    "import_method": "plain_text_line",
                    "safety": "safe",
                    "backend": "plain_text",
                }
            )
        (bare_pkg / "manifest.json").write_text('{"entries":[]}', encoding="utf-8")

        proc = start_worker()
        try:
            read_ready(proc, timeout=60)
            done = complete_for(
                run_task(
                    proc,
                    "qa-patch-bare",
                    "patch",
                    {"src": str(game_copy_asset()), "out": str(bare_pkg)},
                    timeout=30,
                ),
                "qa-patch-bare",
            )
            self.assertFalse(done.get("ok", True))
            self.assertIn("bản dịch", (done.get("error") or "").lower())
        finally:
            stop_worker(proc)


if __name__ == "__main__":
    unittest.main()
