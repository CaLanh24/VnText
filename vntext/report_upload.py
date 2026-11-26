"""Send an anonymous bug report to the developer's report channel - only when the person presses "Gửi", never on its own.

The endpoint is not in the source tree.  A release build embeds it, lightly obfuscated, as ``vntext/report_endpoint.bin`` (see
``release/embed_report_endpoint.py`` and docs/REPORT_WEBHOOK.md); without that file the send button is hidden and everything else works.  The
obfuscation only keeps the address from being readable at a glance in the installed files: it cannot hide it from someone who extracts it.

Nothing here ever prints, logs or returns the endpoint.  Messages name the HTTP status or the network error class only.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

ENDPOINT_FILE = Path(__file__).resolve().parent / "report_endpoint.bin"
MAX_BYTES = 8 * 1024 * 1024
MIN_INTERVAL_SECONDS = 60
MAX_PER_HOUR = 5
TIMEOUT_SECONDS = 20
RETRIES = 2
_ENDPOINT_RE = re.compile(r"^https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d{5,30}/[A-Za-z0-9_\-]{20,120}$")
_KEY = hashlib.sha256(b"vntext-report-endpoint-v1").digest()


def _xor(data: bytes) -> bytes:
    return bytes(byte ^ _KEY[index % len(_KEY)] for index, byte in enumerate(data))


def encode_endpoint(url: str) -> bytes:
    """Release-build side: the obfuscated record written into the payload."""
    if not _ENDPOINT_RE.match(url):
        raise ValueError("not a report webhook address")
    return json.dumps({"v": 1, "d": base64.b64encode(_xor(url.encode("utf-8"))).decode("ascii")}).encode("ascii")


def load_endpoint(path: Path | None = None) -> str | None:
    path = Path(path) if path is not None else ENDPOINT_FILE
    try:
        record = json.loads(path.read_bytes())
        url = _xor(base64.b64decode(record["d"])).decode("utf-8")
    except (OSError, ValueError, KeyError, TypeError, UnicodeDecodeError):
        return None
    return url if record.get("v") == 1 and _ENDPOINT_RE.match(url) else None


def is_configured(path: Path | None = None) -> bool:
    return load_endpoint(path) is not None


def _rate_file() -> Path:
    root = os.environ.get("VNTEXT_DATA_ROOT") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(root) / "VNText" / "report_send_history.json"


def _rate_check(now: float, history: list[float]) -> str | None:
    recent = [stamp for stamp in history if now - stamp < 3600]
    if recent and now - max(recent) < MIN_INTERVAL_SECONDS:
        return f"Vừa gửi một gói báo lỗi; hãy chờ {int(MIN_INTERVAL_SECONDS - (now - max(recent))) + 1} giây rồi gửi lại."
    if len(recent) >= MAX_PER_HOUR:
        return f"Đã gửi {MAX_PER_HOUR} gói trong một giờ qua; hãy thử lại sau."
    return None


def _load_history(path: Path) -> list[float]:
    try:
        return [float(item) for item in json.loads(path.read_text(encoding="utf-8")) if isinstance(item, (int, float))]
    except (OSError, ValueError, TypeError):
        return []


def summary_from_report(zip_path: Path) -> dict:
    """Short, already-masked facts for the message, read only from the bundle's report.json (which the report builder anonymised)."""
    data = Path(zip_path).read_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        try:
            report = json.loads(archive.read("report.json"))
        except (KeyError, ValueError):
            report = {}
    detection = report.get("engine_detection") if isinstance(report.get("engine_detection"), dict) else {}
    environment = report.get("environment") if isinstance(report.get("environment"), dict) else {}
    status = report.get("extract_status") if isinstance(report.get("extract_status"), dict) else {}
    structure = report.get("structure") if isinstance(report.get("structure"), dict) else {}
    accounting = structure.get("native_accounting") if isinstance(structure.get("native_accounting"), dict) else {}

    def short(value, limit=60) -> str:
        text = re.sub(r"[^\w .:/+\-=()]", "", str(value or ""))       # codes, numbers and words only; masked fields stay masked
        return text[:limit]

    return {
        "app_version": short(environment.get("app_version"), 20),
        "engine": short(detection.get("engine"), 40),
        "status": short(status.get("status"), 20),
        "severity": short(status.get("severity"), 20),
        "errors": int(status.get("errors") or 0) if str(status.get("errors") or "0").isdigit() else 0,
        "limitations": [short(item.get("code"), 40) for item in (status.get("limitations") or []) if isinstance(item, dict)][:8],
        "unresolved_blocks": int(structure.get("unresolved_total") or 0) if isinstance(structure.get("unresolved_total"), int) else 0,
        "unaccounted_units": accounting.get("unaccounted_count") if isinstance(accounting.get("unaccounted_count"), int) else None,
        "bundle_sha256": hashlib.sha256(data).hexdigest()[:16],
        "bundle_bytes": len(data),
    }


def _message(summary: dict, test_label: bool) -> dict:
    lines = [("TEST — " if test_label else "") + f"Báo lỗi VNText Studio {summary['app_version'] or '?'}",
             f"Engine: {summary['engine'] or '?'} · Trạng thái: {summary['status'] or '?'} ({summary['severity'] or '?'}) · Lỗi: {summary['errors']}"]
    if summary["limitations"]:
        lines.append("Cảnh báo: " + ", ".join(summary["limitations"]))
    if summary["unresolved_blocks"]:
        lines.append(f"Khối Ren'Py chưa xử lý: {summary['unresolved_blocks']}")
    if summary["unaccounted_units"]:
        lines.append(f"Đơn vị chưa tính: {summary['unaccounted_units']}")
    lines.append(f"Mã gói: {summary['bundle_sha256']} · {summary['bundle_bytes']:,} byte".replace(",", "."))
    return {"content": "\n".join(lines)[:1800], "allowed_mentions": {"parse": []}}


def _multipart(fields: dict, file_name: str, file_bytes: bytes) -> tuple[bytes, str]:
    boundary = "vntext-" + uuid.uuid4().hex
    body = io.BytesIO()
    for name, value in fields.items():
        body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\nContent-Type: application/json\r\n\r\n".encode())
        body.write(value.encode("utf-8") + b"\r\n")
    body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"files[0]\"; filename=\"{file_name}\"\r\n"
               "Content-Type: application/zip\r\n\r\n".encode())
    body.write(file_bytes + b"\r\n" + f"--{boundary}--\r\n".encode())
    return body.getvalue(), f"multipart/form-data; boundary={boundary}"


def send_report(zip_path, *, endpoint: str | None = None, test_label: bool = False, now: float | None = None, sleep=time.sleep,
                history_path: Path | None = None, opener=None) -> dict:
    """Post one bundle.  Returns {"ok": bool, "message": Vietnamese text}; never raises for network problems and never echoes the endpoint."""
    endpoint = endpoint or load_endpoint()
    if not endpoint or not _ENDPOINT_RE.match(endpoint):
        return {"ok": False, "message": "Bản này chưa được cấu hình kênh nhận báo lỗi; hãy dùng 'Tạo gói báo lỗi' rồi gửi tệp thủ công."}
    zip_path = Path(zip_path)
    if not zip_path.is_file() or zip_path.suffix.lower() != ".zip":
        return {"ok": False, "message": "Không tìm thấy gói báo lỗi để gửi; hãy tạo lại gói."}
    size = zip_path.stat().st_size
    if size > MAX_BYTES:
        return {"ok": False, "message": f"Gói báo lỗi quá lớn ({size:,} byte, tối đa {MAX_BYTES:,}); không gửi.".replace(",", ".")}
    now = time.time() if now is None else now
    history_path = history_path or _rate_file()
    history = _load_history(history_path)
    limited = _rate_check(now, history)
    if limited:
        return {"ok": False, "message": limited}
    summary = summary_from_report(zip_path)
    body, content_type = _multipart({"payload_json": json.dumps(_message(summary, test_label), ensure_ascii=False)},
                                    "vntext-bug-report-" + summary["bundle_sha256"] + ".zip", zip_path.read_bytes())
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler())
    last = ""
    for attempt in range(RETRIES + 1):
        request = urllib.request.Request(endpoint, data=body, method="POST",
                                         headers={"Content-Type": content_type, "User-Agent": "VNTextStudio-BugReport"})
        try:
            with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", 200)
            if 200 <= status < 300:
                history = [stamp for stamp in history if now - stamp < 3600] + [now]
                try:
                    history_path.parent.mkdir(parents=True, exist_ok=True)
                    history_path.write_text(json.dumps(history), encoding="utf-8")
                except OSError:
                    pass
                return {"ok": True, "message": f"Đã gửi gói báo lỗi tới nhà phát triển (mã gói {summary['bundle_sha256']}). Cảm ơn bạn!",
                        "bundle_sha256": summary["bundle_sha256"]}
            last = f"máy chủ trả mã {status}"
        except urllib.error.HTTPError as exc:
            last = f"máy chủ trả mã {exc.code}"
            if exc.code == 429 or exc.code >= 500:
                pass
            else:
                return {"ok": False, "message": f"Kênh nhận báo lỗi từ chối gói ({last}); có thể kênh đã bị đổi. Hãy dùng 'Tạo gói báo lỗi' và gửi thủ công."}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            reason = getattr(exc, "reason", exc)
            last = "hết thời gian chờ" if isinstance(reason, TimeoutError) or "timed out" in str(reason) else f"lỗi mạng ({type(reason).__name__})"
        if attempt < RETRIES:
            sleep(2 * (attempt + 1))
    return {"ok": False, "message": f"Chưa gửi được gói báo lỗi ({last}). Kiểm tra mạng rồi thử lại, hoặc gửi tệp thủ công."}
