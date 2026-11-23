"""Rebuild a stand-in game folder from an anonymous VNText bug report (report.json inside the zip, or the json itself).

The stand-in has the same folder structure, extensions, size classes, archive kinds and header markers, but stub contents, so engine detection, scans and
the journey can be replayed for a game nobody has.  Usage: python tests/tools/synth_from_report.py REPORT(.zip|.json) DEST_DIR
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

STUB_CAP = 4096
SCRIPT = b'label start:\n    "Hello"\n    return\n'
RPYC = b"RENPY RPC2" + b"\0" * 64


def load(report_path: str | Path) -> dict:
    path = Path(report_path)
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            return json.loads(archive.read("report.json"))
    return json.loads(path.read_text(encoding="utf-8"))


def _member_payload(extension: str) -> bytes:
    return SCRIPT if extension in {".rpy", ".rpym"} else RPYC if extension in {".rpyc", ".rpymc"} else b"x"


def _write_rpa(path: Path, summary: dict) -> None:
    from tests.unit.test_renpy_archive import write_rpa, write_rpa2
    members: dict[str, bytes] = {}
    for extension, count in (summary.get("extensions") or {}).items():
        ext = "" if extension == "(none)" else extension
        for index in range(min(int(count), 40)):
            members[f"m{index}{ext}"] = _member_payload(ext)
    if not members:
        members["m0.txt"] = b"x"
    (write_rpa2 if summary.get("version") == "2.0" else write_rpa)(path, members)


def synthesize(report: dict, dest: str | Path) -> Path:
    root = Path(dest)
    root.mkdir(parents=True, exist_ok=True)
    for entry in report["files"]:
        path = root / entry["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.casefold()
        rpa = entry.get("rpa")
        if suffix == ".rpa" and isinstance(rpa, dict) and "members" in rpa:
            _write_rpa(path, rpa)
        elif suffix == ".rpa":
            path.write_bytes(b"RPA-3.0 nonsense\n")        # unreadable/skipped archive: the failure shape is what matters
        elif suffix in {".rpy", ".rpym"}:
            path.write_bytes(SCRIPT)
        elif suffix in {".rpyc", ".rpymc"}:
            path.write_bytes(RPYC if entry.get("header") == "RPC2" else b"other")
        elif suffix in {".ttf", ".otf", ".ttc"}:
            head = bytes.fromhex(entry["header"]) if entry.get("header") else b"\0\1\0\0"
            path.write_bytes(head + b"\0" * 28)
        elif suffix in {".exe", ".dll"}:
            path.write_bytes(b"MZ" + b"\0" * 62)
        else:
            path.write_bytes(b"\0" * min(int(entry.get("size") or 0), STUB_CAP))
    return root


def synthesize_native_blocks(report: dict) -> str:
    """Template text (one block per recorded unsupported Ren'Py native block) rebuilt from the masked shapes of a schema-2 report."""
    from vntext.shape_mask import rebuild_text
    blocks = []
    for sample in (report.get("structure") or {}).get("renpy_native_blocks", []):
        # The surrounding lines are kept as comments: they show the neighbourhood without becoming blocks of their own.
        def around(key):
            return "".join(f"## {line}" + chr(10) for line in rebuild_text(sample.get(key) or []).splitlines() if line.strip())
        blocks.append(around("context_before") + rebuild_text(sample.get("shape") or []) + around("context_after"))
    return "\n".join(blocks)


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    root = synthesize(load(argv[1]), argv[2])
    print(f"stand-in layout written to {root}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    raise SystemExit(main(sys.argv))
