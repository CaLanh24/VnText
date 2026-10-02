from __future__ import annotations

import json
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vntext.patch_renpy import RenPyPatchError, apply_renpy_translation_package
from vntext.package_io import CSV_FIELDS, read_csv_rows_file, write_csv_rows_file
from vntext.entry import Entry
from vntext.patch_pipeline import apply_translation_package
from vntext.patchability import make_renpy_contract, validate_renpy_contract


def _native_contract(entry: dict, source_sha256: str) -> dict:
    method = str(entry["import_method"])
    unit_type = "dialogue" if method == "renpy_dialogue" else "string"
    locator = dict(entry["locator"])
    return make_renpy_contract(
        method=method,
        backend="renpy_loose_source",
        unit_type=unit_type,
        source_text=entry["source_text"],
        file_path=entry["file_path"],
        source_sha256=source_sha256,
        template_sha256=hashlib.sha256(b"generated-template").hexdigest(),
        native_id=str(locator.get("native_id") or ""),
        source_line=2,
        speaker=str(entry.get("object_info", "") or ""),
    )


def _native_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


class RenPyPatchTests(unittest.TestCase):
    @staticmethod
    def _renpy_pair(out: Path) -> tuple[Path, Path]:
        payload = out / "COPY_TO_GAME_ROOT"
        return (
            payload / "game/tl/vietnamese/vntext.rpy",
            payload / "game/zzz_vntext_vietnamese.rpy",
        )

    def _renpy_pair_bytes(self, out: Path) -> dict[str, bytes]:
        target, activation = self._renpy_pair(out)
        return {"target": target.read_bytes(), "activation": activation.read_bytes()}

    def _assert_no_renpy_staging(self, out: Path) -> None:
        if out.exists():
            self.assertFalse(any(path.name.startswith(".renpy-overlay-") for path in out.rglob("*")))

    @staticmethod
    def _set_translation(csv: Path, key: str, value: str) -> None:
        fields, rows = read_csv_rows_file(csv)
        for row in rows:
            if row.get("key") == key:
                row["translation"] = value
        write_csv_rows_file(csv, fields, rows)

    def _existing_string_mapping(self, game: Path, source: str, translation: str, *, complete: bool = True) -> Path:
        path = game / "game" / "tl" / "vietnamese" / "existing.rpy"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = 'translate vietnamese strings:\n\n    old "' + source + '"\n'
        if complete:
            content += '    new "' + translation + '"\n'
        path.write_text(content, encoding="utf-8")
        return path

    def _package(self, base: Path, *, conflict: bool = False):
        game = base / "gamecopy"; (game / "game").mkdir(parents=True)
        (game / "game" / "script.rpy").write_text('label start:\n    "Hello [name]"\n    $ title = _("Open")\n', encoding="utf-8")
        source_sha256 = hashlib.sha256((game / "game/script.rpy").read_bytes()).hexdigest()
        entries = [{"key":"d", "source_text":"Hello [name]", "file_path":"game/script.rpy", "import_method":"renpy_dialogue", "locator":{"native_id":"start_a", "unit_type":"dialogue"}}, {"key":"s", "source_text":"Open", "file_path":"game/script.rpy", "import_method":"renpy_string", "locator":{"source":"Open", "unit_type":"string"}}]
        if conflict: entries.append({"key":"s2", "source_text":"Open", "file_path":"game/script.rpy", "import_method":"renpy_string", "locator":{"source":"Open", "unit_type":"string"}})
        for entry in entries:
            entry["backend"] = "renpy_loose_source"
            entry["object_info"] = ""
            entry["native_contract"] = _native_contract(entry, source_sha256)
        manifest = base / "manifest.json"; manifest.write_text(json.dumps({"entries":entries}), encoding="utf-8")
        translations = []
        for entry in entries:
            row = {field:"" for field in CSV_FIELDS}; row.update(entry); row["translation"] = "Xin chào [name]" if entry["key"] == "d" else ("Mở" if entry["key"] == "s" else "Bật") ; translations.append(row)
        csv = base / "translation.csv"; write_csv_rows_file(csv, CSV_FIELDS, translations)
        return game, csv, manifest

    def test_native_contract_manifest_roundtrip_ignores_context_and_provenance_for_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = base / "script.rpy"
            source.write_text('"Hello"\n', encoding="utf-8")
            data = {
                "key": "d",
                "source_text": "Hello",
                "file_path": "script.rpy",
                "import_method": "renpy_dialogue",
                "locator": {"native_id": "hello_id", "unit_type": "dialogue"},
                "backend": "renpy_loose_source",
                "object_info": "",
            }
            entry = Entry(
                data["source_text"],
                data["file_path"],
                "RenPy:script.rpy:1",
                import_method=data["import_method"],
                backend=data["backend"],
                locator=data["locator"],
                native_contract=_native_contract(data, hashlib.sha256(source.read_bytes()).hexdigest()),
            ).finalize()
            manifest_entry = json.loads(json.dumps(entry.to_manifest(), ensure_ascii=False))
            self.assertEqual(validate_renpy_contract(manifest_entry), "")
            fingerprint = manifest_entry["native_contract"]["fingerprint"]
            manifest_entry["native_contract"]["provenance"]["source_line"] = 999
            manifest_entry["native_contract"]["context"]["speaker"] = "other"
            self.assertEqual(manifest_entry["native_contract"]["fingerprint"], fingerprint)
            self.assertEqual(validate_renpy_contract(manifest_entry), "")

    def test_duplicate_source_text_with_distinct_native_ids_stays_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            document = json.loads(manifest.read_text(encoding="utf-8"))
            first = next(item for item in document["entries"] if item["key"] == "d")
            duplicate = json.loads(json.dumps(first))
            duplicate["key"] = "d2"
            duplicate["locator"]["native_id"] = "start_b"
            duplicate["native_contract"] = _native_contract(duplicate, first["native_contract"]["precondition"]["source_sha256"])
            document["entries"].append(duplicate)
            manifest.write_text(json.dumps(document), encoding="utf-8")
            fields, rows = read_csv_rows_file(csv)
            duplicate_row = {field: "" for field in fields}
            duplicate_row.update(duplicate)
            duplicate_row["translation"] = "Xin chào [name]"
            rows.append(duplicate_row)
            write_csv_rows_file(csv, fields, rows)
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            overlay = (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
            self.assertIn("translate vietnamese start_a:", overlay)
            self.assertIn("translate vietnamese start_b:", overlay)

    def test_writes_overlay_without_touching_source(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base); original = (game / "game/script.rpy").read_bytes()
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            overlay = (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
            self.assertIn("translate vietnamese start_a:", overlay); self.assertIn('new "Mở"', overlay)
            self.assertEqual(
                (base / "out/COPY_TO_GAME_ROOT/game/zzz_vntext_vietnamese.rpy").read_text(encoding="utf-8"),
                'init 999 python:\n    config.language = "vietnamese"\n',
            )
            self._assert_no_renpy_staging(base / "out")
            verification = json.loads((base / "out/patch_verification.json").read_text(encoding="utf-8"))
            self.assertEqual(verification["counts"], {"PASS": 2, "FAIL": 0})
            self.assertEqual([item["status"] for item in verification["results"]], ["PASS", "PASS"])
            self.assertEqual((game / "game/script.rpy").read_bytes(), original)

    def test_activation_write_failure_on_clean_target_leaves_no_overlay(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            out = base / "out"
            original_write_text = Path.write_text

            def fail_activation(path, data, *args, **kwargs):
                if path.name == "zzz_vntext_vietnamese.rpy":
                    raise OSError("injected activation write failure")
                return original_write_text(path, data, *args, **kwargs)

            with patch.object(Path, "write_text", new=fail_activation):
                with self.assertRaisesRegex(RenPyPatchError, "activation"):
                    apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))

            payload = out / "COPY_TO_GAME_ROOT"
            self.assertFalse((payload / "game/tl/vietnamese/vntext.rpy").exists())
            self.assertFalse((payload / "game/zzz_vntext_vietnamese.rpy").exists())
            self.assertFalse(any("renpy" in path.name.casefold() for path in out.rglob("*")))

    def test_overlay_generation_failure_on_clean_target_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            out = base / "out"
            with patch("vntext.patch_renpy._render_overlay", side_effect=RuntimeError("injected overlay generation failure")):
                with self.assertRaisesRegex(RenPyPatchError, "overlay generation"):
                    apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            self.assertFalse(out.exists())

    def test_overlay_stage_write_failure_on_clean_target_leaves_no_overlay(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            out = base / "out"
            original_write_text = Path.write_text

            def fail_overlay(path, data, *args, **kwargs):
                if path.name == "vntext.rpy":
                    raise OSError("injected overlay stage write failure")
                return original_write_text(path, data, *args, **kwargs)

            with patch.object(Path, "write_text", new=fail_overlay):
                with self.assertRaisesRegex(RenPyPatchError, "overlay staging write"):
                    apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            target, activation = self._renpy_pair(out)
            self.assertFalse(target.exists())
            self.assertFalse(activation.exists())
            self._assert_no_renpy_staging(out)

    def test_activation_generation_failure_on_clean_target_leaves_no_output(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            out = base / "out"
            with patch("vntext.patch_renpy._render_activation", side_effect=RuntimeError("injected activation generation failure")):
                with self.assertRaisesRegex(RenPyPatchError, "activation generation"):
                    apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            self.assertFalse(out.exists())

    def test_preexisting_inconsistent_overlay_pair_blocks_before_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            out = base / "out"
            target, activation = self._renpy_pair(out)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"previous overlay")
            with self.assertRaisesRegex(RenPyPatchError, "inconsistent"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            self.assertEqual(target.read_bytes(), b"previous overlay")
            self.assertFalse(activation.exists())
            self._assert_no_renpy_staging(out)

    def test_publish_failure_rolls_back_existing_pair_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base); out = base / "out"
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            previous = self._renpy_pair_bytes(out)
            self._set_translation(csv, "d", "Phiên bản mới [name]")
            real_replace = os.replace
            target, activation = self._renpy_pair(out)

            def fail_activation_publish(source, destination):
                if Path(destination) == activation and Path(source).name == activation.name:
                    raise OSError("injected activation publish failure")
                return real_replace(source, destination)

            with patch("vntext.patch_renpy.os.replace", side_effect=fail_activation_publish):
                with self.assertRaisesRegex(RenPyPatchError, "publish"):
                    apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            self.assertEqual(self._renpy_pair_bytes(out), previous)
            self._assert_no_renpy_staging(out)

    def test_publish_failure_on_clean_target_leaves_pair_clean(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base); out = base / "out"
            activation = self._renpy_pair(out)[1]
            real_replace = os.replace

            def fail_activation_publish(source, destination):
                if Path(destination) == activation and Path(source).name == activation.name:
                    raise OSError("injected activation publish failure")
                return real_replace(source, destination)

            with patch("vntext.patch_renpy.os.replace", side_effect=fail_activation_publish):
                with self.assertRaisesRegex(RenPyPatchError, "publish"):
                    apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            target, activation = self._renpy_pair(out)
            self.assertFalse(target.exists())
            self.assertFalse(activation.exists())
            self._assert_no_renpy_staging(out)

    def test_existing_pair_survives_activation_stage_write_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base); out = base / "out"
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            previous = self._renpy_pair_bytes(out)
            self._set_translation(csv, "d", "Phiên bản mới [name]")
            original_write_text = Path.write_text

            def fail_activation_stage(path, data, *args, **kwargs):
                if path.name == "zzz_vntext_vietnamese.rpy":
                    raise OSError("injected activation stage write failure")
                return original_write_text(path, data, *args, **kwargs)

            with patch.object(Path, "write_text", new=fail_activation_stage):
                with self.assertRaisesRegex(RenPyPatchError, "activation"):
                    apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            self.assertEqual(self._renpy_pair_bytes(out), previous)
            self._assert_no_renpy_staging(out)

    def test_rollback_failure_reports_residual_state(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base); out = base / "out"
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            self._set_translation(csv, "d", "Phiên bản mới [name]")
            target, activation = self._renpy_pair(out)
            real_replace = os.replace

            def fail_publish_and_restore(source, destination):
                if Path(destination) == activation:
                    raise OSError("injected activation publish and rollback failure")
                return real_replace(source, destination)

            with patch("vntext.patch_renpy.os.replace", side_effect=fail_publish_and_restore):
                with self.assertRaisesRegex(RenPyPatchError, "rollback failed.*residual"):
                    apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            self.assertTrue(target.is_file())
            self.assertFalse(activation.exists())
            self.assertTrue(any(path.name.startswith(".renpy-overlay-") for path in out.rglob("*")))

    def test_retry_succeeds_after_successful_rollback(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base); out = base / "out"
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            previous = self._renpy_pair_bytes(out)
            self._set_translation(csv, "d", "Phiên bản mới [name]")
            real_replace = os.replace
            target, activation = self._renpy_pair(out)
            failed = False

            def fail_once(source, destination):
                nonlocal failed
                if not failed and Path(destination) == activation and Path(source).name == activation.name:
                    failed = True
                    raise OSError("injected one-shot activation publish failure")
                return real_replace(source, destination)

            with patch("vntext.patch_renpy.os.replace", side_effect=fail_once):
                with self.assertRaises(RenPyPatchError):
                    apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            self.assertEqual(self._renpy_pair_bytes(out), previous)
            self._assert_no_renpy_staging(out)
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(out))
            self.assertIn('"Phiên bản mới [name]"', target.read_text(encoding="utf-8"))
            self.assertTrue(activation.is_file())

    def test_compiled_only_target_mapping_blocks_with_actionable_reason_and_no_output_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            compiled = game / "game" / "tl" / "vietnamese" / "compiled_only.rpyc"
            compiled.parent.mkdir(parents=True, exist_ok=True)
            compiled.write_bytes(b"compiled Ren'Py mapping")
            out = base / "out"
            out.mkdir()
            marker = out / "caller-owned.txt"
            marker.write_text("keep", encoding="utf-8")

            with self.assertRaises(RenPyPatchError) as raised:
                apply_translation_package(str(csv), str(manifest), str(game), str(out))

            reason = str(raised.exception)
            self.assertIn("compiled-only", reason)
            self.assertIn(str(compiled), reason)
            self.assertIn("corresponding loose .rpy/.rpym source", reason)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
            self.assertFalse((out / "COPY_TO_GAME_ROOT").exists())

    def test_paired_compiled_target_mapping_uses_inspectable_source_inventory(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            source = self._existing_string_mapping(game, "Open", "Mở")
            source.with_suffix(".rpyc").write_bytes(b"compiled counterpart")
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            overlay = (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")

        self.assertNotIn('old "Open"', overlay)

    def test_paired_compiled_target_mapping_with_unreadable_source_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            source = game / "game" / "tl" / "vietnamese" / "existing.rpy"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"\xff\xfe")
            source.with_suffix(".rpyc").write_bytes(b"compiled counterpart")
            with self.assertRaisesRegex(RenPyPatchError, "mapping source is unverifiable"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            self.assertFalse((base / "out/COPY_TO_GAME_ROOT").exists())

    def test_unrelated_compiled_script_outside_target_mapping_surface_does_not_block(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            (game / "game" / "unrelated.rpyc").write_bytes(b"compiled game script")
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            overlay = (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")

        self.assertIn("translate vietnamese start_a:", overlay)

    def test_equivalent_existing_string_mapping_is_already_satisfied(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            existing = self._existing_string_mapping(game, "Open", "Mở")
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            overlay = (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
            verification = json.loads((base / "out/patch_verification.json").read_text(encoding="utf-8"))

        self.assertNotIn('old "Open"', overlay)
        self.assertEqual(verification["already_satisfied"], 1)
        string_result = next(item for item in verification["results"] if item["key"] == "s")
        self.assertEqual(string_result["reason"], "already_satisfied")
        self.assertEqual(string_result["target"], str(existing))

    def test_different_existing_string_mapping_fails_closed_before_overlay(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            self._existing_string_mapping(game, "Open", "Khác")
            with self.assertRaisesRegex(RenPyPatchError, "string mapping conflict"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            self.assertFalse((base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").exists())

    def test_unverifiable_existing_string_mapping_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            self._existing_string_mapping(game, "Open", "Mở", complete=False)
            with self.assertRaisesRegex(RenPyPatchError, "unverifiable"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            self.assertFalse((base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").exists())

    def test_duplicate_string_identity_emits_one_overlay_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            document = json.loads(manifest.read_text(encoding="utf-8"))
            duplicate = json.loads(json.dumps(next(item for item in document["entries"] if item["key"] == "s")))
            duplicate["key"] = "s2"
            document["entries"].append(duplicate)
            manifest.write_text(json.dumps(document), encoding="utf-8")
            fields, rows = read_csv_rows_file(csv)
            duplicate_row = {field: "" for field in fields}; duplicate_row.update(duplicate); duplicate_row["translation"] = "Mở"
            rows.append(duplicate_row); write_csv_rows_file(csv, fields, rows)
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            overlay = (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")

        self.assertEqual(overlay.count('old "Open"'), 1)
        self.assertEqual(overlay.count('new "Mở"'), 1)

    def test_review_only_renpy_rows_do_not_block_dialogue_patch(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            document = json.loads(manifest.read_text(encoding="utf-8"))
            document["entries"].append({
                "key": "review",
                "source_text": "Ren'Py common",
                "file_path": "renpy/common/common.rpy",
                "import_method": "renpy_string",
                "review_only": True,
                "locator": {"source": "Ren'Py common", "unit_type": "string"},
            })
            manifest.write_text(json.dumps(document), encoding="utf-8")
            review_row = {field: "" for field in CSV_FIELDS}
            review_row.update({"key": "review", "source_text": "Ren'Py common", "import_method": "renpy_string"})
            write_csv_rows_file(base / "review_only.csv", CSV_FIELDS, [review_row])
            report = apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            verification = json.loads((base / "out/patch_verification.json").read_text(encoding="utf-8"))

        self.assertIn("review_only_skipped: 1", report)
        self.assertEqual(verification["review_only_skipped"], 1)
        self.assertEqual(verification["status"], "PASS")

    def test_legacy_extraction_locator_shape_is_rejected_without_native_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            document = json.loads(manifest.read_text(encoding="utf-8"))
            document["entries"][0]["locator"] = {"line": 2, "speaker": "", "native_id": "start_a"}
            document["entries"][1]["locator"] = {"line": 3, "source": "Open"}
            for entry in document["entries"]:
                entry.pop("native_contract", None)
            manifest.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(RenPyPatchError, "native contract blocked"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))

    def test_conflicting_string_translation_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base, conflict=True)
            with self.assertRaises(RenPyPatchError):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))

    def test_escaped_newline_source_is_a_valid_precondition(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game = base / "gamecopy"; (game / "game").mkdir(parents=True)
            (game / "game" / "script.rpy").write_text('label start:\n    "Line one.\\nLine two."\n', encoding="utf-8")
            entry = {"key":"d", "source_text":"Line one.\nLine two.", "file_path":"game/script.rpy", "import_method":"renpy_dialogue", "locator":{"native_id":"start_a", "unit_type":"dialogue"}, "backend":"renpy_loose_source", "object_info":""}
            entry["native_contract"] = _native_contract(entry, hashlib.sha256((game / "game/script.rpy").read_bytes()).hexdigest())
            manifest = base / "manifest.json"; manifest.write_text(json.dumps({"entries":[entry]}), encoding="utf-8")
            row = {field:"" for field in CSV_FIELDS}; row.update(entry); row["translation"]="Dòng một.\nDòng hai."
            csv = base / "translation.csv"; write_csv_rows_file(csv, CSV_FIELDS, [row])
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            overlay = (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
            self.assertIn('    # "Line one.\\nLine two."', overlay)
            self.assertIn('    "Dòng một.\\nDòng hai."', overlay)

    def test_multiline_dialogue_source_is_a_valid_precondition(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game = base / "gamecopy"; (game / "game").mkdir(parents=True)
            source_text = "First line. {w}Second line."
            (game / "game/script.rpy").write_text(
                'label start:\n    pc """\n        First line.\n        {w}Second line.\n    """\n',
                encoding="utf-8",
            )
            entry = {
                "key": "d",
                "source_text": source_text,
                "file_path": "game/script.rpy",
                "import_method": "renpy_dialogue",
                "locator": {"native_id": "start_a", "unit_type": "dialogue"},
                "backend": "renpy_loose_source",
                "object_info": "pc",
            }
            entry["native_contract"] = _native_contract(
                entry,
                hashlib.sha256((game / "game/script.rpy").read_bytes()).hexdigest(),
            )
            manifest = base / "manifest.json"
            manifest.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
            row = {field: "" for field in CSV_FIELDS}
            row.update(entry)
            row["translation"] = "Translated first line. {w}Translated second line."
            csv = base / "translation.csv"
            write_csv_rows_file(csv, CSV_FIELDS, [row])
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            overlay = (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")

            self.assertIn('    # pc "First line. {w}Second line."', overlay)
            self.assertIn('    pc "Translated first line. {w}Translated second line."', overlay)

    def test_exact_placeholder_tag_and_newline_translation_is_read_back(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game = base / "gamecopy"; (game / "game").mkdir(parents=True)
            source_text = "Line [name] {b}\nNext %(count)d"
            source_literal = source_text.replace("\n", "\\n")
            (game / "game/script.rpy").write_text(f'label start:\n    "{source_literal}"\n', encoding="utf-8")
            entry = {
                "key": "d",
                "source_text": source_text,
                "file_path": "game/script.rpy",
                "import_method": "renpy_dialogue",
                "locator": {"native_id": "start_a", "unit_type": "dialogue"},
                "backend": "renpy_loose_source",
                "object_info": "",
            }
            entry["native_contract"] = _native_contract(
                entry,
                hashlib.sha256((game / "game/script.rpy").read_bytes()).hexdigest(),
            )
            manifest = base / "manifest.json"; manifest.write_text(json.dumps({"entries": [entry]}), encoding="utf-8")
            row = {field: "" for field in CSV_FIELDS}; row.update(entry)
            row["translation"] = "Dòng [name] {b}\nTiếp %(count)d"
            csv = base / "translation.csv"; write_csv_rows_file(csv, CSV_FIELDS, [row])
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            overlay = (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
            self.assertIn(f"    # {_native_quote(source_text)}", overlay)
            self.assertIn(f"    {_native_quote(row['translation'])}", overlay)
            verification = json.loads((base / "out/patch_verification.json").read_text(encoding="utf-8"))
            self.assertEqual(verification["status"], "PASS")

    def test_context_and_enrichment_mutation_does_not_change_native_target(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            document = json.loads(manifest.read_text(encoding="utf-8"))
            document["entries"][0]["context"] = "tampered-context"
            document["entries"][0]["native_contract"]["context"] = {
                "speaker": "tampered-speaker",
                "enrichment": {"status": "MISMATCH", "authoritative": True},
            }
            document["entries"][0]["native_contract"]["provenance"]["source_line"] = 999
            manifest.write_text(json.dumps(document), encoding="utf-8")
            apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            overlay = (base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
            self.assertIn("translate vietnamese start_a:", overlay)
            self.assertNotIn("tampered-speaker", overlay)

    def test_duplicate_native_id_fails_before_overlay_write(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            document = json.loads(manifest.read_text(encoding="utf-8"))
            duplicate = json.loads(json.dumps(document["entries"][0]))
            duplicate["key"] = "d2"
            document["entries"].append(duplicate)
            manifest.write_text(json.dumps(document), encoding="utf-8")
            fields, rows = read_csv_rows_file(csv)
            duplicate_row = {field: "" for field in fields}; duplicate_row.update(duplicate)
            duplicate_row["translation"] = "Xin chào [name]"
            rows.append(duplicate_row); write_csv_rows_file(csv, fields, rows)
            with self.assertRaisesRegex(RenPyPatchError, "duplicate native"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))

    def test_tampered_overlay_readback_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            original_write_text = Path.write_text

            def tamper(path, data, *args, **kwargs):
                result = original_write_text(path, data, *args, **kwargs)
                if path.name == "vntext.rpy":
                    original_write_text(path, data.replace('"Xin chào [name]"', '"Tampered"'), *args, **kwargs)
                return result

            with patch.object(Path, "write_text", new=tamper):
                with self.assertRaisesRegex(RenPyPatchError, "read-back failed"):
                    apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"))
            verification = json.loads((base / "out/patch_verification.json").read_text(encoding="utf-8"))
            self.assertEqual(verification["status"], "FAIL")
            self.assertEqual(verification["counts"], {"PASS": 0, "FAIL": 2})

    def test_native_id_and_source_precondition_drift_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            original_manifest = manifest.read_text(encoding="utf-8")
            document = json.loads(original_manifest)
            document["entries"][0]["locator"]["native_id"] = "changed_id"
            manifest.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(RenPyPatchError, "native contract blocked"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out-id"))
            document = json.loads(original_manifest)
            document["entries"][0]["locator"]["unit_type"] = "string"
            manifest.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(RenPyPatchError, "native contract blocked"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out-unit"))
            manifest.write_text(original_manifest, encoding="utf-8")
            (game / "game/script.rpy").write_text('label changed:\n    "Different"\n', encoding="utf-8")
            with self.assertRaisesRegex(RenPyPatchError, "source precondition drift"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out-source"))

    def test_missing_or_malformed_native_locator_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); game, csv, manifest = self._package(base)
            original_manifest = manifest.read_text(encoding="utf-8")
            document = json.loads(original_manifest)
            document["entries"][0].pop("native_contract")
            manifest.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(RenPyPatchError, "native contract blocked"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out-missing"))

            document = json.loads(original_manifest)
            document["entries"][0]["locator"]["native_id"] = "not valid"
            manifest.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(RenPyPatchError, "native contract blocked"):
                apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out-malformed"))
