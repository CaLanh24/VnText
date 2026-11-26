"""One-button bug report sending (0.1.35): obfuscated endpoint, preview-before-send in the app, a local fake server instead of the real channel,
size/rate limits, retries, Vietnamese errors, and no path/name/text leak in what is sent or printed."""
import email
import email.policy
import http.server
import json
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.request
import zipfile
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from vntext import report_upload

ROOT = Path(__file__).resolve().parents[2]
WORK = work_temp_dir("report-upload")
FAKE = "https://discord.com/api/webhooks/123456789012345678/" + "A" * 68
SECRET_GAME = "Sekret Game Name"
SECRET_FILE = "chapter_secret_ending.rpy"
SECRET_LINE = "You must never see this line of dialogue."


class _Server(http.server.ThreadingHTTPServer):
    statuses: list
    received: list


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self.server.received.append({"path": self.path, "type": self.headers.get("Content-Type"), "body": body})
        status = self.server.statuses.pop(0) if self.server.statuses else 204
        self.send_response(status)
        self.end_headers()

    def log_message(self, *_):
        pass


class _ToLocal(urllib.request.BaseHandler):
    """Routes every request to the local fake server, BEFORE the real HTTPS handler: nothing in these tests can reach the real channel."""
    handler_order = 10

    def __init__(self, port):
        self.port = port

    def https_open(self, request):
        local = urllib.request.Request(f"http://127.0.0.1:{self.port}/fake-webhook", data=request.data, method="POST", headers=dict(request.header_items()))
        return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(local, timeout=request.timeout)


def _no_network(test):
    """Every outbound connection in these tests must be the local fake server."""
    import socket
    real = socket.create_connection

    def guarded(address, *args, **kwargs):
        if address[0] not in ("127.0.0.1", "localhost"):
            raise AssertionError(f"test tried to reach the network: {address[0]}")
        return real(address, *args, **kwargs)
    patcher = __import__("unittest.mock", fromlist=["patch"]).patch("socket.create_connection", guarded)
    patcher.start(); test.addCleanup(patcher.stop)


def _bundle(folder: Path) -> Path:
    """A real bundle built by the product from a fake game whose names and text must never be sent."""
    from vntext.bug_report import build_report
    game = folder / SECRET_GAME
    (game / "game").mkdir(parents=True)
    (game / "renpy").mkdir(); (game / "lib").mkdir()
    (game / "Game.exe").write_bytes(b"MZ")
    (game / "game" / SECRET_FILE).write_text(f'label start:\n    "{SECRET_LINE}"\n    return\n', encoding="utf-8")
    return build_report(game, folder / "reports", log_lines=[f"Lỗi ở {game}\\game\\{SECRET_FILE}: \"{SECRET_LINE}\""], app_version="0.1.35")


class ReportUploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=WORK)
        self.base = Path(self.temp.name)
        self.server = _Server(("127.0.0.1", 0), _Handler)
        self.server.statuses, self.server.received = [], []
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.opener = urllib.request.build_opener(_ToLocal(self.server.server_address[1]))
        self.history = self.base / "history.json"
        _no_network(self)

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.temp.cleanup()

    def send(self, zip_path, **kwargs):
        kwargs.setdefault("history_path", self.history)
        return report_upload.send_report(zip_path, endpoint=FAKE, opener=self.opener, sleep=lambda *_: None, **kwargs)

    def test_endpoint_round_trips_obfuscated_and_never_plain(self):
        record = report_upload.encode_endpoint(FAKE)
        self.assertNotIn(b"discord", record)
        self.assertNotIn(b"webhooks", record)
        path = self.base / "report_endpoint.bin"; path.write_bytes(record)
        self.assertEqual(FAKE, report_upload.load_endpoint(path))
        path.write_bytes(b"{broken"); self.assertIsNone(report_upload.load_endpoint(path))
        self.assertIsNone(report_upload.load_endpoint(self.base / "absent.bin"))
        with self.assertRaises(ValueError):
            report_upload.encode_endpoint("https://example.com/hook")

    def test_a_sent_bundle_carries_the_zip_and_a_masked_summary_and_nothing_secret(self):
        bundle = _bundle(self.base)
        result = self.send(bundle)
        self.assertTrue(result["ok"], result)
        self.assertEqual(1, len(self.server.received))
        request = self.server.received[0]
        message = email.message_from_bytes(b"Content-Type: " + request["type"].encode() + b"\r\n\r\n" + request["body"], policy=email.policy.default)
        parts = {part.get_param("name", header="content-disposition"): part for part in message.iter_parts()}
        payload = json.loads(parts["payload_json"].get_content())
        attached = parts["files[0]"].get_payload(decode=True)
        self.assertEqual(bundle.read_bytes(), attached)
        self.assertIn("VNText Studio 0.1.35", payload["content"])
        self.assertEqual({"parse": []}, payload["allowed_mentions"])
        visible = payload["content"] + json.dumps(result, ensure_ascii=False) + parts["files[0]"].get_filename()
        with zipfile.ZipFile(bundle) as archive:
            visible += "".join(archive.read(name).decode("utf-8", "replace") for name in archive.namelist())
        for secret in (SECRET_GAME, SECRET_FILE, "chapter_secret", SECRET_LINE, str(self.base), FAKE, "webhooks/123456789012345678"):
            self.assertNotIn(secret, visible, secret)

    def test_rate_limit_size_limit_and_missing_configuration(self):
        bundle = _bundle(self.base)
        self.assertTrue(self.send(bundle, now=1000.0)["ok"])
        limited = self.send(bundle, now=1030.0)
        self.assertFalse(limited["ok"]); self.assertIn("chờ", limited["message"])
        for stamp in (1100.0, 1200.0, 1300.0, 1400.0):
            self.assertTrue(self.send(bundle, now=stamp)["ok"])
        self.assertIn("một giờ", self.send(bundle, now=1500.0)["message"])
        self.assertTrue(self.send(bundle, now=1000.0 + 3700)["ok"])
        big = self.base / "big.zip"; big.write_bytes(b"0" * (report_upload.MAX_BYTES + 1))
        self.assertIn("quá lớn", self.send(big)["message"])
        missing = report_upload.send_report(bundle, endpoint=None, history_path=self.history, opener=self.opener) \
            if not report_upload.is_configured() else {"ok": False, "message": "chưa được cấu hình"}
        self.assertFalse(missing["ok"]); self.assertIn("chưa được cấu hình", missing["message"])
        self.assertEqual(6, len(self.server.received))

    def test_retries_on_server_errors_then_reports_in_vietnamese_without_the_address(self):
        bundle = _bundle(self.base)
        self.server.statuses = [500, 503]
        self.assertTrue(self.send(bundle)["ok"])                       # third attempt succeeds
        self.assertEqual(3, len(self.server.received))
        self.history.unlink(missing_ok=True)
        self.server.statuses = [502, 502, 502]
        failed = self.send(bundle)
        self.assertFalse(failed["ok"]); self.assertIn("mã 502", failed["message"]); self.assertNotIn("discord", failed["message"])
        self.server.statuses = [404]
        rejected = self.send(bundle)
        self.assertIn("từ chối", rejected["message"])
        self.assertEqual(3 + 3 + 1, len(self.server.received))      # a 4xx is not retried

    def test_network_failure_is_a_clear_message(self):
        bundle = _bundle(self.base)
        port = self.server.server_address[1]
        self.server.shutdown(); self.server.server_close()
        result = report_upload.send_report(bundle, endpoint=FAKE, opener=urllib.request.build_opener(_ToLocal(port)), sleep=lambda *_: None,
                                           history_path=self.history)
        self.assertFalse(result["ok"]); self.assertIn("lỗi mạng", result["message"])
        self.server = _Server(("127.0.0.1", 0), _Handler); self.server.statuses, self.server.received = [], []
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def test_cli_status_and_build_embedding_never_print_the_address(self):
        done = subprocess.run([sys.executable, "-X", "utf8", "-m", "vntext.report_upload_cli", str(self._params({"action": "status"}))], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8")
        self.assertEqual({"ok": True, "configured": report_upload.is_configured()}, json.loads(done.stdout.strip().splitlines()[-1]))
        secrets = Path(tempfile.mkdtemp(dir=str(Path.home()))) / "hook.txt"       # outside any Git tree
        try:
            out = self.base / "staged" / "report_endpoint.bin"
            for content, configured in ((FAKE + "\n", True), ("", False), ("https://example.com/x\n", False), (FAKE + "\n" + FAKE + "\n", False)):
                secrets.write_text(content, encoding="utf-8")
                env = dict(__import__("os").environ, VNTEXT_REPORT_WEBHOOK_FILE=str(secrets))
                done = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "release" / "embed_report_endpoint.py"), "--out", str(out),
                                       "--worker-src", str(ROOT / "vntext")], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(0, done.returncode, done.stderr)
                self.assertNotIn("discord", done.stdout + done.stderr)
                self.assertEqual(configured, out.is_file(), (content, done.stdout))
                if configured:
                    self.assertEqual(FAKE, report_upload.load_endpoint(out))
                    self.assertNotIn(b"discord.com/api", out.read_bytes())
            inside = ROOT / "TEST_RUN" / "tmp" / "hook-inside-repo.txt"
            inside.write_text(FAKE, encoding="utf-8")
            try:
                env = dict(__import__("os").environ, VNTEXT_REPORT_WEBHOOK_FILE=str(inside))
                done = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "release" / "embed_report_endpoint.py"), "--out", str(out),
                                       "--worker-src", str(ROOT / "vntext")], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
                self.assertIn("inside a Git work tree", done.stdout)
                self.assertFalse(out.is_file())
            finally:
                inside.unlink(missing_ok=True)
        finally:
            secrets.unlink(missing_ok=True); secrets.parent.rmdir()

    def _params(self, data) -> Path:
        path = self.base / "params.json"; path.write_text(json.dumps(data), encoding="utf-8"); return path


class AppWiringTests(unittest.TestCase):
    def test_send_needs_a_preview_and_an_explicit_yes(self):
        vm = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.ExtractRunLog.cs").read_text(encoding="utf-8")
        send = vm[vm.index("private async void SendBugReport()"):]
        send = send[:send.index("\n    }\n")]
        self.assertIn("MessageBoxButton.YesNo", send)
        self.assertLess(send.index("MessageBoxResult.Yes"), send.index("BugReportProcess.SendAsync"))
        self.assertIn("UiText.Translate(BugReportPrivacyLine)", send)
        self.assertIn('BugReportPrivacyLine = "Gói đã ẩn danh sẽ được gửi tới nhà phát triển. Không có tên game/tệp/nội dung thoại/đường dẫn."', vm)
        xaml = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").read_text(encoding="utf-8")
        self.assertIn("SendBugReportCommand", xaml)
        self.assertIn("ReportSendAvailable", xaml)

    def test_the_source_tree_never_holds_a_plain_webhook_address(self):
        hits = []
        for path in list((ROOT / "vntext").rglob("*.py")) + list((ROOT / "wpf_app").rglob("*.cs")) + list((ROOT / "release").rglob("*.p*")):
            if "discord.com/api/webhooks" in path.read_text(encoding="utf-8", errors="ignore"):
                hits.append(str(path))
        self.assertEqual([], hits)
        self.assertFalse((ROOT / "vntext" / "report_endpoint.bin").exists())


if __name__ == "__main__":
    unittest.main()
