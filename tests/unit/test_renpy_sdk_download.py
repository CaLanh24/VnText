from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vntext import renpy_toolchain


class _Response(io.BytesIO):
    def __init__(self, payload: bytes, declared_length: int | None = None):
        super().__init__(payload)
        self.headers = {"Content-Length": str(declared_length if declared_length is not None else len(payload))}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class RenPySdkDownloadTests(unittest.TestCase):
    def test_download_hash_checks_then_atomically_installs_and_reports_progress(self):
        payload = b"pinned-sdk-archive"
        progress: list[tuple[int, int]] = []
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "sdk.zip"
            resolved_destination = destination.resolve()
            with (
                patch.object(renpy_toolchain.urllib.request, "urlopen", return_value=_Response(payload)) as urlopen,
                patch.object(renpy_toolchain, "SDK_SHA256", hashlib.sha256(payload).hexdigest()),
                patch.object(renpy_toolchain, "install_managed_sdk", return_value="installed") as install,
            ):
                result = renpy_toolchain.download_and_install_managed_sdk(
                    destination, is_cancelled=lambda: False,
                    progress=lambda received, total: progress.append((received, total)),
                )
            self.assertEqual("installed", result)
            self.assertEqual(payload, resolved_destination.read_bytes())
            self.assertEqual([(len(payload), len(payload))], progress)
            self.assertEqual(20, urlopen.call_args.kwargs["timeout"])
            install.assert_called_once_with(resolved_destination)
            self.assertEqual(["sdk.zip"], [path.name for path in Path(temp).iterdir()])

    def test_cancel_after_first_chunk_removes_partial_and_never_installs(self):
        payload = b"x" * (512 * 1024)
        cancelled = False

        def on_progress(_received: int, _total: int) -> None:
            nonlocal cancelled
            cancelled = True

        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "sdk.zip"
            with (
                patch.object(renpy_toolchain.urllib.request, "urlopen", return_value=_Response(payload)),
                patch.object(renpy_toolchain, "SDK_SHA256", hashlib.sha256(payload).hexdigest()),
                patch.object(renpy_toolchain, "install_managed_sdk") as install,
            ):
                with self.assertRaisesRegex(renpy_toolchain.RenPyToolchainError, "cancelled"):
                    renpy_toolchain.download_and_install_managed_sdk(
                        destination, is_cancelled=lambda: cancelled, progress=on_progress,
                    )
            install.assert_not_called()
            self.assertFalse(destination.exists())
            self.assertEqual([], list(Path(temp).iterdir()))

    def test_incomplete_download_is_rejected_and_partial_is_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "sdk.zip"
            with patch.object(
                renpy_toolchain.urllib.request, "urlopen", return_value=_Response(b"short", declared_length=20)
            ):
                with self.assertRaisesRegex(renpy_toolchain.RenPyToolchainError, "bị gián đoạn"):
                    renpy_toolchain.download_and_install_managed_sdk(destination, is_cancelled=lambda: False)
            self.assertFalse(destination.exists())
            self.assertEqual([], list(Path(temp).iterdir()))

    def test_timeout_removes_partial_and_user_retry_can_succeed(self):
        payload = b"retryable-sdk-archive"
        with tempfile.TemporaryDirectory() as temp:
            destination = (Path(temp) / "sdk.zip").resolve()
            with (
                patch.object(
                    renpy_toolchain.urllib.request,
                    "urlopen",
                    side_effect=[TimeoutError("simulated transfer timeout"), _Response(payload)],
                ) as urlopen,
                patch.object(renpy_toolchain, "SDK_SHA256", hashlib.sha256(payload).hexdigest()),
                patch.object(renpy_toolchain, "install_managed_sdk", return_value="installed") as install,
            ):
                with self.assertRaisesRegex(renpy_toolchain.RenPyToolchainError, "Không tải được"):
                    renpy_toolchain.download_and_install_managed_sdk(destination, is_cancelled=lambda: False)
                self.assertEqual([], list(Path(temp).iterdir()))
                result = renpy_toolchain.download_and_install_managed_sdk(destination, is_cancelled=lambda: False)
            self.assertEqual("installed", result)
            self.assertEqual(payload, destination.read_bytes())
            self.assertEqual(2, urlopen.call_count)
            install.assert_called_once_with(destination)
            self.assertEqual(["sdk.zip"], [path.name for path in Path(temp).iterdir()])


if __name__ == "__main__":
    unittest.main()
