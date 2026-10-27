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
from vntext.app_tasks import _cancelled_patch_output_statement, run_patch_task
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


def _snapshot(root: Path) -> dict[str, tuple[str, str]]:
    """Every entry under root (files by content hash, links by target) so any change, deletion or addition shows."""
    import hashlib
    import os

    out: dict[str, tuple[str, str]] = {}
    isjunction = getattr(os.path, "isjunction", lambda _p: False)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for name in dirnames + filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink() or isjunction(path):
                out[rel] = ("link", os.readlink(path) if path.is_symlink() else "junction")
            elif path.is_dir():
                out[rel] = ("dir", "")
            else:
                out[rel] = ("file", hashlib.sha256(path.read_bytes()).hexdigest())
    return out


def _make_link(link: Path, target: Path) -> bool:
    try:
        link.symlink_to(target, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
        return made.returncode == 0


def _fake_apply(snapshots: list | None = None, cancel_in_verify: bool = False, foreign: str = "", link_to: Path | None = None):
    """Writes what the real writer writes (payload, backup, reports) and reports progress like it.

    ``foreign`` injects data the run did NOT write: ``nested`` (a user file below COPY_TO_GAME_ROOT) or ``samename``
    (user content in a file that carries an artifact name).  ``snapshots`` receives the tree right before the cancel.
    """

    def fake(_csv, _manifest, _game, output, progress):
        out = Path(output)
        if link_to is not None:
            assert _make_link(out / "COPY_TO_GAME_ROOT", link_to)
        else:
            (out / "COPY_TO_GAME_ROOT").mkdir(parents=True)
            (out / "COPY_TO_GAME_ROOT" / "dialogue.txt").write_text("Xin chao\n", encoding="utf-8")
        (out / "backup_original").mkdir()
        (out / "backup_original" / "dialogue.txt").write_text("Hello\n", encoding="utf-8")
        (out / "HUONG_DAN_CAI_PATCH.txt").write_text("guide\n", encoding="utf-8")
        if foreign == "nested":
            nested = out / "COPY_TO_GAME_ROOT" / "user" / "deep"
            nested.mkdir(parents=True)
            (nested / "notes.txt").write_text("user data below the payload\n", encoding="utf-8")
        if foreign == "samename":
            (out / "patch_manifest.json").write_text("USER CONTENT, same name as an artifact\n", encoding="utf-8")
        progress({"done": 1, "total": 3, "file": "Dang ghi patch manifest / kiem tra patch..."})
        if cancel_in_verify:
            if snapshots is not None:
                snapshots.append(_snapshot(out))
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
    def _assert_kept(self, completed, before, out):
        self.assertEqual(len(completed), 1, completed)
        self.assertFalse(completed[0]["ok"])
        self.assertEqual(completed[0]["error"], "cancelled")
        statement = completed[0]["patch_install_instructions"]
        self.assertIn("GIỮ NGUYÊN", statement)
        self.assertIn("chọn thư mục xuất trống mới", statement)
        self.assertNotIn("đã được dọn", statement)
        self.assertNotIn("dịch tiếp", statement)
        self.assertEqual(_snapshot(out), before, "a cancel must leave the output exactly as it was")

    def test_cancel_in_verification_keeps_the_output_byte_identical_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "patch-out"
            snaps: list = []
            completed, game = _run(root / "a", _Host(VERIFY_LABEL), _fake_apply(snaps, cancel_in_verify=True), out=out)
            self._assert_kept(completed, snaps[0], out)
            self.assertEqual((game / "dialogue.txt").read_text(encoding="utf-8"), "Hello\n")
            # the kept folder is non-empty, so the same path is refused; a NEW empty directory works
            again, _g = _run(root / "b", _Host(None), _fake_apply(), out=out)
            self.assertFalse(again[0]["ok"])
            self.assertIn("not empty", again[0]["error"])
            fresh, _g = _run(root / "c", _Host(None), _fake_apply(), out=root / "patch-out-2")
            self.assertTrue(fresh[0]["ok"], fresh[0])

    def test_nested_foreign_data_below_the_payload_is_never_touched(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "patch-out"
            snaps: list = []
            completed, _game = _run(
                Path(tmp) / "a", _Host(VERIFY_LABEL), _fake_apply(snaps, cancel_in_verify=True, foreign="nested"), out=out
            )
            self._assert_kept(completed, snaps[0], out)
            self.assertEqual(
                (out / "COPY_TO_GAME_ROOT" / "user" / "deep" / "notes.txt").read_text(encoding="utf-8"),
                "user data below the payload\n",
            )

    def test_user_content_under_an_artifact_name_is_never_touched(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "patch-out"
            snaps: list = []
            completed, _game = _run(
                Path(tmp) / "a", _Host(VERIFY_LABEL), _fake_apply(snaps, cancel_in_verify=True, foreign="samename"), out=out
            )
            self._assert_kept(completed, snaps[0], out)
            self.assertEqual(
                (out / "patch_manifest.json").read_text(encoding="utf-8"), "USER CONTENT, same name as an artifact\n"
            )

    def test_preexisting_empty_output_directory_keeps_whatever_the_run_wrote(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "my-empty-output"
            snaps: list = []
            completed, _game = _run(
                Path(tmp) / "a", _Host(VERIFY_LABEL), _fake_apply(snaps, cancel_in_verify=True), out=out, mkdir_out=True
            )
            self._assert_kept(completed, snaps[0], out)
            self.assertTrue(out.is_dir())

    def test_linked_directory_in_the_output_is_not_followed_and_stays(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "elsewhere"
            target.mkdir()
            (target / "precious.txt").write_text("user data", encoding="utf-8")
            probe = root / "probe"
            if not _make_link(probe, target):
                self.skipTest("neither symlinks nor junctions can be created for this account")
            probe.unlink() if probe.is_symlink() else probe.rmdir()
            out = root / "out"
            snaps: list = []
            completed, _game = _run(
                root / "a", _Host(VERIFY_LABEL), _fake_apply(snaps, cancel_in_verify=True, link_to=target), out=out
            )
            self._assert_kept(completed, snaps[0], out)
            self.assertEqual((target / "precious.txt").read_text(encoding="utf-8"), "user data")

    def test_statement_helper_is_read_only_and_honest_when_nothing_was_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "overlay"
            (out / "COPY_TO_GAME_ROOT").mkdir(parents=True)
            (out / "COPY_TO_GAME_ROOT" / "x.rpy").write_text("keep", encoding="utf-8")
            before = _snapshot(out)
            text = _cancelled_patch_output_statement(out)
            self.assertEqual(_snapshot(out), before)
            self.assertIn("GIỮ NGUYÊN", text)
            self.assertIn("trước khi ghi thư mục xuất", _cancelled_patch_output_statement(Path(tmp) / "never-created"))
            self.assertIn("trước khi ghi thư mục xuất", _cancelled_patch_output_statement(None))

    def test_cancel_before_the_final_progress_is_still_a_cancel_and_keeps_the_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "patch-out"
            completed, _game = _run(
                Path(tmp) / "a", _Host("Dang ghi patch manifest / kiem tra patch..."), _fake_apply(), out=out
            )
            self.assertEqual(completed[0]["error"], "cancelled")
            self.assertTrue((out / "COPY_TO_GAME_ROOT" / "dialogue.txt").is_file(), "nothing is deleted on cancel")
            self.assertIn("GIỮ NGUYÊN", completed[0]["patch_install_instructions"])


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


if __name__ == "__main__":
    unittest.main()
