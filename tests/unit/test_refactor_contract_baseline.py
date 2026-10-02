"""Single reproducible contract snapshot for the generic public source tree.

The baseline is synthetic and contains no game, model, or translation corpus.
Normal test runs compare it and never mutate the checked-in file.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    for path in (str(cur.parent), str(lib)):
        if path not in sys.path:
            sys.path.insert(0, path)


_tests_lib_on_path()

from vntext.entry import Entry, make_key
from vntext.package_io import CSV_FIELDS
from vntext.traceability import canonical_identity_text
from vntext_worker.protocol import PROTOCOL_VERSION, emit_complete


ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "golden"
BASELINE = GOLDEN / "refactor_contract_baseline.json"
IDENTITY_FIELDS = ("key", "source_text", "import_method", "file_path", "context")
SIDE_CSVS = (
    "raw_candidates.csv",
    "review_only.csv",
    "raw_unpatchable.csv",
    "raw_candidates_rejected.csv",
    "technical_skipped.csv",
)


def _sha256(path: Path) -> str:
    # Keep source hashes stable across Git's Windows CRLF checkout conversion.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _digest_rows(rows: list[dict], fields: tuple[str, ...] = IDENTITY_FIELDS) -> str:
    payload = [
        [canonical_identity_text(row.get(field, "")) for field in fields]
        for row in rows
    ]
    payload.sort()
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read_csv(path: Path) -> tuple[list[str], list[dict]]:
    if not path.is_file():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def _report_fields(path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition(":")
        if sep and key in {
            "patched_lines",
            "skipped_lines",
            "duplicate_locations_patched_or_attempted",
        }:
            fields[key] = value.strip()
    return fields


def _worker_complete_payload() -> dict:
    output = io.StringIO()
    with redirect_stdout(output):
        emit_complete(
            "baseline",
            ok=True,
            summary="ok",
            complete=False,
            pending=2,
            review_only=3,
            blocked=4,
            translated=5,
            applied=6,
            copied_vi=7,
            pipeline_liveness=True,
        )
    return json.loads(output.getvalue())


def build_snapshot() -> dict:
    proof = {
        "reader": True,
        "writer": True,
        "preflight": True,
        "reopen": True,
        "semantic_verify": True,
    }
    main_entries = [
        Entry(
            source_text="Hello {name}\\n",
            file_path="dialogue.txt",
            context="line:0",
            import_method="plain_text_line",
            locator={"line": 0},
            patch_proof=proof,
        ).finalize(),
        Entry(
            source_text="Settings",
            file_path="Sample_Data/resources.assets",
            context="TextAsset:line:1",
            import_method="unity_textasset_line",
            locator={"path_id": 7, "line_index": 1},
            patch_proof=proof,
        ).finalize(),
    ]
    review_entry = Entry(
        source_text="Opaque payload",
        file_path="Sample_Data/resources.bin",
        context="offset:0",
        import_method="custom_binary_string",
        review_only=True,
    ).finalize()
    rows = [entry.to_csv_row() for entry in main_entries]
    manifest_entries = [entry.to_manifest() for entry in main_entries + [review_entry]]
    csv_fields = list(CSV_FIELDS)
    side_csvs = {
        name: {"exists": False, "fields": [], "rows": 0}
        for name in SIDE_CSVS
    }
    extract_stats = {
        "mode": "safe",
        "extract_level": "balanced",
        "files_scanned": 2,
        "main_entries": 2,
        "review_entries": 1,
        "translation_csv_keys": len(rows),
        "translation_csv_methods": {"plain_text_line": 1, "unity_textasset_line": 1},
        "technical_skipped_entries": 0,
    }
    return {
        "schema": 1,
        "csv_fields": CSV_FIELDS,
        "entry": {
            "key": main_entries[0].key,
            "csv_field_order": list(main_entries[0].to_csv_row()),
            "csv_row": main_entries[0].to_csv_row(),
            "manifest": main_entries[0].to_manifest(),
            "known_key": make_key("foo.txt", "line:1", "Xin chao the gioi", "plain_text_line"),
        },
        "extract": {
            "csv_fields": csv_fields,
            "rows": len(rows),
            "key_set_sha256": _digest_rows(rows, ("key",)),
            "identity_sha256": _digest_rows(rows),
            "manifest_format": 2,
            "manifest_entries": len(manifest_entries),
            "manifest_identity_sha256": _digest_rows(manifest_entries),
            "side_csvs": side_csvs,
            "stats": extract_stats,
        },
        "patch": {
            "translation_fields": csv_fields,
            "report": {
                "patched_lines": "1",
                "skipped_lines": "0",
                "duplicate_locations_patched_or_attempted": "0",
            },
            "stats": {"filled_plain_text_rows": 1, "patched_lines": "1", "skipped_lines": "0"},
        },
        "unity_patch": {
            "status": "external-fixture-only",
            "translation_fields": csv_fields,
            "report": {"patched_lines": "0", "skipped_lines": "0"},
        },
        "frozen_files": {
            "vntext/unity_fs.py": _sha256(ROOT / "vntext" / "unity_fs.py"),
            "vntext/addressables.py": _sha256(ROOT / "vntext" / "addressables.py"),
        },
        "worker_protocol": {
            "version": PROTOCOL_VERSION,
            "complete_payload": _worker_complete_payload(),
        },
    }


class RefactorContractBaselineTests(unittest.TestCase):
    def test_identity_digest_ignores_embedded_csv_line_ending_style(self):
        header = "key,source_text,translation,import_method,file_path,context"
        lf = (
            "\ufeff" + header + "\n"
            + 'row-1,"first line\nsecond line",,plain_text,f.txt,"ctx\nline"\n'
        ).encode("utf-8")
        crlf = (
            "\ufeff" + header + "\r\n"
            + 'row-1,"first line\r\nsecond line",,plain_text,f.txt,"ctx\r\nline"\r\n'
        ).encode("utf-8")

        with tempfile.TemporaryDirectory(prefix="vntext-baseline-identity-") as temp:
            root = Path(temp)
            lf_path = root / "lf.csv"
            crlf_path = root / "crlf.csv"
            lf_path.write_bytes(lf)
            crlf_path.write_bytes(crlf)
            _, lf_rows = _read_csv(lf_path)
            _, crlf_rows = _read_csv(crlf_path)

        self.assertNotEqual(lf_rows[0]["source_text"], crlf_rows[0]["source_text"])
        self.assertNotEqual(lf_rows[0]["context"], crlf_rows[0]["context"])
        self.assertEqual(_digest_rows(lf_rows), _digest_rows(crlf_rows))

    def test_current_contract_matches_phase1_snapshot(self):
        self.assertTrue(BASELINE.is_file(), f"missing {BASELINE}")
        expected = json.loads(BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(build_snapshot(), expected)


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        BASELINE.write_text(json.dumps(build_snapshot(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        unittest.main()
