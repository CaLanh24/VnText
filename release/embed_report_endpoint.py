"""Release build step: embed the bug-report channel (obfuscated) into the staged worker, or build without the send button.

Reads ONE line from the secrets file outside the repository: %USERPROFILE%\\.vntext-secrets\\report_webhook.txt by default, or the file named by
VNTEXT_REPORT_WEBHOOK_FILE.  Never prints the address.  A missing/empty/invalid file, or a file inside a Git work tree, is not an error: the build
goes on without the endpoint (the app then hides "Gửi báo lỗi") and the reason is printed.  Exit code is 0 in every such case; 2 only for bad
arguments.  See docs/REPORT_WEBHOOK.md.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def secrets_file() -> Path:
    override = os.environ.get("VNTEXT_REPORT_WEBHOOK_FILE", "").strip()
    return Path(override) if override else Path.home() / ".vntext-secrets" / "report_webhook.txt"


def inside_git_tree(path: Path) -> bool:
    folder = path.resolve().parent
    try:
        done = subprocess.run(["git", "-C", str(folder), "rev-parse", "--is-inside-work-tree"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and done.stdout.strip() == b"true"


PLAIN_MARKERS = (b"discord.com/api/" + b"webhooks", b"discordapp.com/api/" + b"webhooks")   # split so this file never holds the marker itself


def scan_payload(root: Path) -> int:
    hits = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            if any(marker in data or marker.decode().encode("utf-16-le") in data for marker in PLAIN_MARKERS):
                hits.append(str(path.relative_to(root)))
    if hits:
        print("payload holds a plain webhook address in: " + ", ".join(hits[:10]))
        return 1
    print("payload scan: no plain webhook address")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", help="path of the report_endpoint.bin to write in the staged worker")
    parser.add_argument("--worker-src", help="the staged vntext package root (to import the encoder from the same source)")
    parser.add_argument("--scan", help="payload root: fail if a webhook address appears there in plain text")
    args = parser.parse_args(argv)
    if args.scan:
        return scan_payload(Path(args.scan))
    if not args.out or not args.worker_src:
        parser.error("--out and --worker-src are required")
    sys.path.insert(0, str(Path(args.worker_src).parent))
    from vntext.report_upload import encode_endpoint

    out = Path(args.out)
    out.unlink(missing_ok=True)
    source = secrets_file()

    def skip(reason: str) -> int:
        print(f"report endpoint: NOT CONFIGURED ({reason}); building without the 'Gửi báo lỗi' button.")
        return 0

    if not source.is_file():
        return skip("secrets file not found")
    if inside_git_tree(source):
        return skip("secrets file is inside a Git work tree; move it outside any repository")
    try:
        lines = [line.strip() for line in source.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError):
        return skip("secrets file unreadable")
    if len(lines) != 1:
        return skip("secrets file must hold exactly one line")
    try:
        record = encode_endpoint(lines[0])
    except ValueError:
        return skip("the line is not a Discord webhook address")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(record)
    print("report endpoint: CONFIGURED (embedded, obfuscated; address not printed).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
