"""Read-only fetch of the bug-report channel: new messages -> their .zip attachments -> a private folder OUTSIDE the repo.

    python tests/tools/fetch_reports.py [--list-only] [--all | --since MESSAGE_ID] [--channel-id ID] [--inbox DIR] [--no-extract]

What it does: GET /channels/{id}/messages (Discord REST v10, ``Authorization: Bot <token>``), remember the last message id in a cursor file next to the
inbox, download attachments that are .zip, <= 8 MB and hosted on Discord's CDN, check each archive for zip-slip/bombs and unpack it into the inbox.
What it never does: POST or send anything, print or log the token or the webhook address, follow a redirect, run anything from a package, or read
message text into its output.  Everything in a message is DATA FROM STRANGERS.

Secrets (both outside any Git tree; the tool refuses a file inside one):
    bot token       %USERPROFILE%\\.vntext-secrets\\discord_bot_token.txt   or env VNTEXT_REPORT_BOT_TOKEN_FILE   (View Channel + Read Message History)
    webhook (only to learn the channel id, via one GET)  report_webhook.txt  or env VNTEXT_REPORT_WEBHOOK_FILE; skip with --channel-id
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

API_BASE = "https://discord.com/api/v10"
CDN_HOSTS = ("cdn.discordapp.com", "media.discordapp.net")
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024
MAX_ZIP_MEMBERS = 400
MAX_UNPACKED_BYTES = 96 * 1024 * 1024
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_RATIO = 200
PAGE = 100
MAX_PAGES = 50
RETRIES_429 = 6
TIMEOUT = 30
DEFAULT_INBOX = Path(r"C:\vj\reports-inbox")
SECRETS = Path.home() / ".vntext-secrets"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")
_SNOWFLAKE = re.compile(r"^\d{5,25}$")
_WEBHOOK = re.compile(r"^https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/(\d{5,30})/([A-Za-z0-9_\-]{20,120})$")


class FetchError(Exception):
    """A message that is safe to print (never holds a secret)."""


def inside_git_tree(path: Path) -> bool:
    try:
        current = path.resolve()
    except OSError:
        return True
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return True
    return False


def read_secret_line(path: Path, what: str) -> str:
    if inside_git_tree(path):
        raise FetchError(f"{what}: file is inside a Git tree; move it out (for example to %USERPROFILE%\\.vntext-secrets)")
    try:
        lines = [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    except OSError:
        raise FetchError(f"{what}: file not readable") from None
    if len(lines) != 1:
        raise FetchError(f"{what}: the file must hold exactly one line")
    return lines[0]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


class Http:
    """Tiny GET-only client; the opener never follows redirects.  ``sleep`` is injectable so tests do not wait."""

    def __init__(self, sleep: Callable[[float], None] = time.sleep):
        self.opener = urllib.request.build_opener(_NoRedirect)
        self.sleep = sleep

    def get(self, url: str, headers: dict[str, str], *, limit: int | None = None) -> tuple[int, bytes]:
        for attempt in range(RETRIES_429 + 1):
            request = urllib.request.Request(url, headers={"User-Agent": "VNTextReportReader/1", **headers}, method="GET")
            try:
                with self.opener.open(request, timeout=TIMEOUT) as response:
                    data = response.read(limit + 1) if limit is not None else response.read()
                    if limit is not None and len(data) > limit:
                        raise FetchError("download larger than the allowed size")
                    return response.status, data
            except urllib.error.HTTPError as error:
                if error.code == 429 and attempt < RETRIES_429:
                    wait = 1.0
                    try:
                        wait = float(error.headers.get("Retry-After") or json.loads(error.read() or b"{}").get("retry_after") or 1.0)
                    except (ValueError, TypeError):
                        pass
                    self.sleep(min(max(wait, 0.0), 60.0))
                    continue
                raise FetchError(f"HTTP {error.code}") from None
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                raise FetchError("network error: " + type(error).__name__) from None
        raise FetchError("rate limited too many times")


def channel_id_from_webhook(http: Http, webhook_url: str, base: str) -> str:
    m = _WEBHOOK.match(webhook_url)
    if not m:
        raise FetchError("webhook file does not hold a Discord webhook address")
    status, data = http.get(f"{base}/webhooks/{m.group(1)}/{m.group(2)}", {})        # read-only metadata; the address is never printed
    try:
        channel = str(json.loads(data).get("channel_id") or "")
    except (ValueError, AttributeError):
        channel = ""
    if not _SNOWFLAKE.match(channel):
        raise FetchError("webhook metadata has no channel id; pass --channel-id")
    return channel


def fetch_messages(http: Http, base: str, token: str, channel_id: str, after: str | None) -> list[dict]:
    """All messages newer than ``after`` (oldest first), page by page."""
    collected: list[dict] = []
    cursor = after
    for _ in range(MAX_PAGES):
        query = {"limit": str(PAGE)}
        if cursor:
            query["after"] = cursor
        status, data = http.get(f"{base}/channels/{channel_id}/messages?" + urllib.parse.urlencode(query), {"Authorization": "Bot " + token})
        try:
            batch = json.loads(data)
        except ValueError:
            raise FetchError("unexpected answer from the API") from None
        if not isinstance(batch, list):
            raise FetchError("unexpected answer from the API")
        batch = [m for m in batch if isinstance(m, dict) and _SNOWFLAKE.match(str(m.get("id", "")))]
        collected.extend(batch)
        if len(batch) < PAGE:
            break
        cursor = str(max(int(m["id"]) for m in batch))
    collected.sort(key=lambda m: int(m["id"]))
    return collected


def safe_name(name: str) -> str:
    base = _SAFE_NAME.sub("_", os.path.basename(str(name or "")))[:80].strip("._") or "report"
    return base


def attachment_problem(att: dict, allowed_hosts: tuple[str, ...], allow_http: bool) -> str:
    name = str(att.get("filename") or "")
    if not name.lower().endswith(".zip"):
        return "not a .zip"
    size = att.get("size")
    if not isinstance(size, int) or size < 0 or size > MAX_ATTACHMENT_BYTES:
        return "larger than 8 MB"
    parsed = urllib.parse.urlparse(str(att.get("url") or ""))
    if parsed.scheme != "https" and not (allow_http and parsed.scheme == "http"):
        return "address is not https"
    if (parsed.hostname or "") not in allowed_hosts:
        return "host is not Discord's CDN"
    return ""


def zip_problem(path: Path) -> str:
    """'' when the archive is safe to unpack (no traversal, absolute paths, links, bombs); otherwise the reason."""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ZIP_MEMBERS:
                return "too many members"
            total = 0
            seen: set[str] = set()
            for info in infos:
                name = info.filename.replace("\\", "/")
                parts = [p for p in name.split("/") if p]
                if name.startswith("/") or re.match(r"^[A-Za-z]:", name) or ".." in parts or "\x00" in name:
                    return "unsafe member name"
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    return "symbolic link member"
                if info.flag_bits & 0x1:
                    return "encrypted member"
                key = name.casefold()
                if key in seen:
                    return "duplicate member name"
                seen.add(key)
                if info.file_size > MAX_MEMBER_BYTES:
                    return "member too large"
                if info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
                    return "suspicious compression ratio"
                if info.file_size > 1024 * 1024 and info.compress_size == 0:
                    return "suspicious compression ratio"
                total += info.file_size
                if total > MAX_UNPACKED_BYTES:
                    return "unpacked size too large"
            return ""
    except (zipfile.BadZipFile, OSError):
        return "not a valid zip"


def unpack(path: Path, dest: Path) -> int:
    """Unpack by streaming with a hard byte cap per member (the declared sizes were already checked; this guards lying headers)."""
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    written_total = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            target = (dest / info.filename.replace("\\", "/")).resolve()
            if root != target and root not in target.parents:
                raise FetchError("member escapes the inbox")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as src, target.open("wb") as out:
                written = 0
                while chunk := src.read(1024 * 256):
                    written += len(chunk)
                    written_total += len(chunk)
                    if written > MAX_MEMBER_BYTES or written_total > MAX_UNPACKED_BYTES:
                        raise FetchError("unpacked size exceeds the limit")
                    out.write(chunk)
    return written_total


def _clip(value: object, limit: int = 60) -> str:
    return re.sub(r"[^\x20-\x7e]", "?", str(value))[:limit]


def summarise_report(directory: Path) -> str:
    """A short line from the masked report.json (kinds and counts only); never message text, file names inside the package or paths."""
    target = directory / "report.json"
    if not target.is_file():
        return "no report.json"
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "report.json unreadable"
    if not isinstance(data, dict):
        return "report.json unexpected"
    parts = []
    env = data.get("environment") if isinstance(data.get("environment"), dict) else {}
    parts.append("app " + _clip(env.get("app_version") or "?", 12))
    status = data.get("extract_status") if isinstance(data.get("extract_status"), dict) else {}
    if status.get("status"):
        parts.append("extract " + _clip(status.get("status"), 12))
    gerr = data.get("game_error") if isinstance(data.get("game_error"), dict) else {}
    if gerr.get("kind"):
        parts.append("game_error " + _clip(gerr.get("kind"), 24) + " lines=" + _clip(len(gerr.get("broken_overlay_lines") or []), 6))
    pr = data.get("patch_report") if isinstance(data.get("patch_report"), dict) else {}
    if "patched" in pr:
        parts.append("patched " + _clip(pr.get("patched"), 8))
    return "; ".join(parts)


def load_cursor(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def run(args: argparse.Namespace, *, http: Http | None = None, out: Callable[[str], None] = print, base: str = API_BASE,
        allowed_hosts: tuple[str, ...] = CDN_HOSTS, allow_http: bool = False) -> int:
    http = http or Http()
    inbox = Path(args.inbox)
    if inside_git_tree(inbox):
        raise FetchError("the inbox must be OUTSIDE any Git tree")
    token_file = Path(os.environ.get("VNTEXT_REPORT_BOT_TOKEN_FILE") or (SECRETS / "discord_bot_token.txt"))
    token = read_secret_line(token_file, "bot token")
    channel = args.channel_id
    if not channel:
        webhook_file = Path(os.environ.get("VNTEXT_REPORT_WEBHOOK_FILE") or (SECRETS / "report_webhook.txt"))
        channel = channel_id_from_webhook(http, read_secret_line(webhook_file, "webhook"), base)
    if not _SNOWFLAKE.match(str(channel)):
        raise FetchError("channel id is not valid")
    cursor_file = inbox / ".cursor.json"
    state = load_cursor(cursor_file)
    after = None if args.all else (args.since or state.get(str(channel)))
    messages = fetch_messages(http, base, token, str(channel), after)
    inbox.mkdir(parents=True, exist_ok=True)
    out(f"{len(messages)} new message(s)" + (" (cursor ignored)" if args.all else ""))
    newest = after
    for message in messages:
        mid = str(message["id"])
        newest = mid if newest is None or int(mid) > int(newest) else newest
        stamp = _clip(message.get("timestamp") or "?", 32)
        attachments = [a for a in (message.get("attachments") or []) if isinstance(a, dict)]
        if not attachments:
            out(f"- {mid} {stamp} (no attachment)")
            continue
        for index, att in enumerate(attachments):
            name = safe_name(att.get("filename"))
            problem = attachment_problem(att, allowed_hosts, allow_http)
            head = f"- {mid} {stamp} {name} {_clip(att.get('size'), 12)} bytes"
            if problem:
                out(f"{head}  SKIPPED: {problem}")
                continue
            if args.list_only:
                out(f"{head}  (list only)")
                continue
            folder = inbox / mid
            folder.mkdir(parents=True, exist_ok=True)
            _status, data = http.get(str(att["url"]), {}, limit=MAX_ATTACHMENT_BYTES)
            zip_path = folder / f"{index}-{name}"
            zip_path.write_bytes(data)
            issue = zip_problem(zip_path)
            if issue:
                out(f"{head}  REJECTED: {issue} (kept as {zip_path.name}, not unpacked)")
                continue
            if args.no_extract:
                out(f"{head}  saved {zip_path}")
                continue
            target = folder / f"{index}-unpacked"
            unpack(zip_path, target)
            out(f"{head}  -> {target}  [{summarise_report(target)}]")
    if not args.list_only and newest and not args.all:
        state[str(channel)] = newest
        cursor_file.write_text(json.dumps(state), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list-only", action="store_true", help="show new messages and attachments; download nothing, keep the cursor")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--all", action="store_true", help="ignore the saved cursor and read the whole channel history (the cursor is not changed)")
    group.add_argument("--since", default=None, help="only messages after this message id")
    ap.add_argument("--channel-id", default=None)
    ap.add_argument("--inbox", default=str(DEFAULT_INBOX))
    ap.add_argument("--no-extract", action="store_true", help="save the zip but do not unpack it")
    args = ap.parse_args(argv)
    try:
        return run(args)
    except FetchError as error:
        print("fetch_reports: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
