"""Patch cancellation boundary: cancel during read-back verification, honest settlement of the run's own output,
too-late cancel, and the ownership invariant (never remove or change an output the run cannot prove it created)."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import vntext.patch_readback as patch_readback
from vntext.app_tasks import _settle_cancelled_patch_output, run_patch_task
from vntext.patch_pipeline import PATCH_FINAL_PROGRESS_LABEL
from vntext_worker.task_runners import WorkerCancelled

SLEEPER = "import sys,time; sys.stdin.read(); time.sleep(120)"
VERIFY_LABEL = "Dang kiem tra patch..."


def _package(root: Path) -> tuple[Path, Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    package = root / "package"
    package.mkdir()
    csv_path = package / "translation.csv"
    manifest_path = package / "manifest.json"
    csv_path.write_text("key,source_text,translation\nk,Hello,Xin chao\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps({"entries": [{"key": "k", "source_text": "Hello", "import_method": "plain_text_line"}]}),
        encoding="utf-8",
    )
    game = root / "game"
    game.mkdir()
    (game / "dialogue.txt").write_text("Hello\n", encoding="utf-8")
    return csv_path, manifest_path, game


def _fake_apply(cancel_in_verify: bool = False, foreign: bool = False):
    """Writes what the real writer writes (payload, backup, reports) and reports progress like it."""

    def fake(_csv, _manifest, _game, output, progress):
        out = Path(output)
        (out / "COPY_TO_GAME_ROOT").mkdir(parents=True)
        (out / "COPY_TO_GAME_ROOT" / "dialogue.txt").write_text("Xin chao\n", encoding="utf-8")
        (out / "backup_original").mkdir()
        (out / "backup_original" / "dialogue.txt").write_text("Hello\n", encoding="utf-8")
        (out / "HUONG_DAN_CAI_PATCH.txt").write_text("guide\n", encoding="utf-8")
        if foreign:
            (out / "user-notes.txt").write_text("not ours\n", encoding="utf-8")
        progress({"done": 1, "total": 3, "file": "Dang ghi patch manifest / kiem tra patch..."})
        if cancel_in_verify:
            progress({"done": 1, "total": 3, "file": VERIFY_LABEL})
        (out / "patch_verification.json").write_text(
            json.dumps({"counts": {"PASS": 1}, "results": [{"status": "PASS"}]}), encoding="utf-8"
        )
        (out / "import_report.txt").write_text("patch_verification_status: PASS\n", encoding="utf-8")
        progress({"done": 3, "total": 3, "file": PATCH_FINAL_PROGRESS_LABEL})

    return fake


class _Host:
    """Worker-like progress callback: raises the real WorkerCancelled once the host asked to cancel."""

    def __init__(self, cancel_when: str | None):
        self.cancel_when = cancel_when

    def progress(self, info: dict) -> None:
        if self.cancel_when and str(info.get("file") or "") == self.cancel_when:
            raise WorkerCancelled()


def _run(root: Path, host: _Host, fake, *, out: Path, mkdir_out: bool = False):
    csv_path, manifest_path, game = _package(root)
    if mkdir_out:
        out.mkdir()
    completed: list[dict] = []
    with patch("vntext.app_tasks.apply_translation_package", fake), patch(
        "vntext.app_tasks._find_patch_installer", return_value=None
    ):
        run_patch_task(
            csv_path, manifest_path, str(game), str(out),
            progress=host.progress, log=lambda _line: None, complete=completed.append,
            patch_out_override=out, write_manifest_file=False,
        )
    return completed, game


class VerificationCancelTests(unittest.TestCase):
    def test_cancel_during_readback_terminates_the_child_promptly(self):
        real_popen = subprocess.Popen
        spawned: list[subprocess.Popen] = []

        def sleeper(_cmd, **kwargs):
            child = real_popen([sys.executable, "-c", SLEEPER], **kwargs)
            spawned.append(child)
            return child

        calls = {"n": 0}

        def cancel_check():
            calls["n"] += 1
            if calls["n"] >= 2:
                raise WorkerCancelled()

        started = time.monotonic()
        with patch.object(patch_readback.subprocess, "Popen", sleeper), tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(WorkerCancelled):
                patch_readback.verify_patch_targets(
                    Path(tmp), Path(tmp), {}, timeout_seconds=90, cancel_check=cancel_check
                )
        self.assertLess(time.monotonic() - started, 15, "a cancel must not wait for the whole verification")
        self.assertEqual(len(spawned), 1)
        self.assertIsNotNone(spawned[0].poll(), "the verifier child must be reaped before the cancel propagates")

    def test_without_cancel_check_the_deadline_still_reports_timeout(self):
        real_popen = subprocess.Popen
        with patch.object(
            patch_readback.subprocess, "Popen",
            lambda _cmd, **kw: real_popen([sys.executable, "-c", SLEEPER], **kw),
        ), tempfile.TemporaryDirectory() as tmp:
            report = patch_readback.verify_patch_targets(Path(tmp), Path(tmp), {}, timeout_seconds=1)
        self.assertEqual(report["status"], patch_readback.TIMEOUT)


class CancelledOutputTests(unittest.TestCase):
    def test_cancel_in_verification_removes_the_runs_own_output_and_a_retry_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "patch-out"
            completed, game = _run(root / "a", _Host(VERIFY_LABEL), _fake_apply(cancel_in_verify=True), out=out)
            self.assertEqual(len(completed), 1, completed)
            self.assertFalse(completed[0]["ok"])
            self.assertEqual(completed[0]["error"], "cancelled")
            statement = completed[0]["patch_install_instructions"]
            self.assertIn("đã được dọn", statement)
            self.assertNotIn("dịch tiếp", statement)
            self.assertFalse(out.exists(), "the directory this run created must not survive a cancel")
            self.assertEqual((game / "dialogue.txt").read_text(encoding="utf-8"), "Hello\n")
            self.assertNotIn("patch_verification_report", completed[0])
            # the same output path is usable again because nothing complete-looking was left behind
            retry, _game = _run(root / "b", _Host(None), _fake_apply(), out=out)
            self.assertTrue(retry[0]["ok"], retry[0])
            self.assertTrue((out / "patch_verification.json").is_file())

    def test_preexisting_empty_output_directory_is_emptied_but_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "my-empty-output"
            completed, _game = _run(Path(tmp) / "a", _Host(VERIFY_LABEL), _fake_apply(cancel_in_verify=True), out=out, mkdir_out=True)
            self.assertEqual(completed[0]["error"], "cancelled")
            self.assertTrue(out.is_dir(), "a directory the user created stays")
            self.assertEqual(list(out.iterdir()), [])

    def test_foreign_entry_in_the_output_blocks_every_deletion(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "patch-out"
            completed, _game = _run(
                Path(tmp) / "a", _Host(VERIFY_LABEL), _fake_apply(cancel_in_verify=True, foreign=True), out=out
            )
            self.assertEqual(completed[0]["error"], "cancelled")
            self.assertIn("không phải do lần chạy này tạo", completed[0]["patch_install_instructions"])
            self.assertTrue((out / "user-notes.txt").is_file())
            self.assertTrue(
                (out / "COPY_TO_GAME_ROOT" / "dialogue.txt").is_file(), "nothing is deleted when ownership is not provable"
            )

    def test_unowned_output_is_never_touched(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "overlay"
            (out / "COPY_TO_GAME_ROOT").mkdir(parents=True)
            (out / "COPY_TO_GAME_ROOT" / "x.rpy").write_text("keep", encoding="utf-8")
            text = _settle_cancelled_patch_output(out, owned=False, created=False)
            self.assertTrue((out / "COPY_TO_GAME_ROOT" / "x.rpy").is_file())
            self.assertIn("giữ nguyên", text)

    def test_linked_directory_inside_the_output_is_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "elsewhere"
            target.mkdir()
            (target / "precious.txt").write_text("user data", encoding="utf-8")
            out = root / "out"
            out.mkdir()
            link = out / "COPY_TO_GAME_ROOT"
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                # No symlink privilege: a directory junction needs none and is what Windows users actually have.
                made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
                if made.returncode != 0:
                    self.skipTest("neither symlinks nor junctions can be created for this account")
            text = _settle_cancelled_patch_output(out, owned=True, created=True)
            self.assertTrue((target / "precious.txt").is_file())
            self.assertIn("không phải do lần chạy này tạo", text)


class LateCancelTests(unittest.TestCase):
    def test_cancel_first_seen_at_the_final_progress_is_reported_as_too_late(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "patch-out"
            completed, _game = _run(Path(tmp) / "a", _Host(PATCH_FINAL_PROGRESS_LABEL), _fake_apply(), out=out)
            self.assertEqual(len(completed), 1, completed)
            self.assertTrue(completed[0]["ok"], completed[0])
            self.assertNotEqual(completed[0].get("error"), "cancelled")
            self.assertTrue(completed[0]["summary"].startswith("Yêu cầu hủy đến quá muộn"), completed[0]["summary"])
            self.assertTrue((out / "patch_verification.json").is_file(), "a finished patch is kept as it is")
            self.assertTrue((out / "COPY_TO_GAME_ROOT" / "dialogue.txt").is_file())

    def test_uncancelled_run_has_no_late_cancel_wording(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed, _game = _run(Path(tmp) / "a", _Host(None), _fake_apply(), out=Path(tmp) / "patch-out")
            self.assertTrue(completed[0]["ok"])
            self.assertNotIn("quá muộn", completed[0]["summary"])

    def test_cancel_before_the_final_progress_is_still_a_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "patch-out"
            completed, _game = _run(
                Path(tmp) / "a", _Host("Dang ghi patch manifest / kiem tra patch..."), _fake_apply(), out=out
            )
            self.assertEqual(completed[0]["error"], "cancelled")
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
