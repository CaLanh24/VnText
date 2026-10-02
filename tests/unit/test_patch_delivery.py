from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vntext.app_tasks import run_patch_task
from vntext.entry import Entry
from vntext.package_io import read_csv_rows_file, write_csv_rows_file, write_package
from vntext.patch_pipeline import detect_patch_engine
from vntext.patchability import make_renpy_contract


class PatchDeliveryTests(unittest.TestCase):
    @staticmethod
    def _renpy_package(base: Path) -> tuple[Path, Path, Path]:
        game = base / "game"
        source = game / "game" / "script.rpy"
        source.parent.mkdir(parents=True)
        source.write_text('label start:\n    "Hello [name]"\n', encoding="utf-8")
        relative = "game/script.rpy"
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        entry = Entry(
            source_text="Hello [name]",
            file_path=relative,
            context="RenPy:game/script.rpy:2:start_a",
            import_method="renpy_dialogue",
            safety="safe",
            locator={"native_id": "start_a", "unit_type": "dialogue"},
            backend="renpy_loose_source",
            patch_proof={field: True for field in ("reader", "writer", "preflight", "reopen", "semantic_verify")},
            native_contract=make_renpy_contract(
                method="renpy_dialogue",
                backend="renpy_loose_source",
                unit_type="dialogue",
                source_text="Hello [name]",
                file_path=relative,
                source_sha256=source_hash,
                template_sha256=hashlib.sha256(b"template").hexdigest(),
                native_id="start_a",
                source_line=2,
            ),
        ).finalize()
        package = base / "package"
        write_package(
            str(package),
            [entry],
            [],
            {"engine": "RENPY_LOOSE_SOURCE", "mode": "deep", "main_entries": 1},
            separate_review=True,
            enforce_symmetry=True,
        )
        fields, rows = read_csv_rows_file(package / "translation.csv")
        rows[0]["translation"] = "Xin chào [name]"
        write_csv_rows_file(package / "translation.csv", fields, rows)
        return game, package / "translation.csv", package / "manifest.json"

    def test_run_patch_task_delivers_renpy_overlay_without_unity_installer(self):
        with tempfile.TemporaryDirectory(prefix="vntext-patch-delivery-renpy-") as temp:
            base = Path(temp)
            game, csv_path, manifest_path = self._renpy_package(base)
            patch_out = base / "Patch_Viet_Hoa"
            completed: list[dict] = []
            logs: list[str] = []

            run_patch_task(
                csv_path,
                manifest_path,
                str(game),
                str(base),
                progress=lambda _event: None,
                log=logs.append,
                complete=completed.append,
                patch_out_override=patch_out,
            )

            self.assertEqual(len(completed), 1)
            self.assertTrue(completed[0]["ok"], completed[0])
            self.assertEqual(completed[0]["patch_engine"], "renpy")
            self.assertEqual(completed[0]["patch_delivery"], "renpy_native_overlay")
            payload = patch_out / "COPY_TO_GAME_ROOT"
            self.assertEqual(
                sorted(path.relative_to(payload).as_posix() for path in payload.rglob("*") if path.is_file()),
                ["game/tl/vietnamese/vntext.rpy", "game/zzz_vntext_vietnamese.rpy"],
            )
            self.assertFalse((patch_out / "VNTextPatchInstaller.exe").exists())
            self.assertFalse((patch_out / "patch_manifest.json").exists())
            self.assertTrue((patch_out / "HUONG_DAN_CAI_PATCH.txt").is_file())
            self.assertNotIn("VNTextPatchInstaller.exe", completed[0]["patch_install_instructions"])
            self.assertNotIn("Unity", completed[0]["patch_install_instructions"])
            self.assertNotIn("installer", completed[0]["patch_install_instructions"].casefold())
            self.assertTrue(any("overlay hợp lệ" in line for line in logs))

            installed = base / "approved-renpy-copy"
            shutil.copytree(payload, installed)
            self.assertIn('translate vietnamese start_a:', (installed / "game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8"))
            self.assertTrue((installed / "game/zzz_vntext_vietnamese.rpy").is_file())
            self.assertEqual((game / "game/script.rpy").read_text(encoding="utf-8"), 'label start:\n    "Hello [name]"\n')

    def test_unity_task_keeps_installer_delivery(self):
        with tempfile.TemporaryDirectory(prefix="vntext-patch-delivery-unity-") as temp:
            base = Path(temp)
            game = base / "game"
            game.mkdir()
            package = base / "package"
            package.mkdir()
            csv_path = package / "translation.csv"
            manifest_path = package / "manifest.json"
            csv_path.write_text("key,source_text,translation\nk,Hello,Xin chao\n", encoding="utf-8")
            manifest_path.write_text(
                json.dumps({"entries": [{"key": "k", "import_method": "plain_text_line"}]}),
                encoding="utf-8",
            )
            installer = base / "VNTextPatchInstaller.exe"
            installer.write_bytes(b"unity-installer")
            patch_out = base / "patch"

            def fake_apply(_csv, _manifest, _game, output, _progress):
                output = Path(output)
                (output / "COPY_TO_GAME_ROOT").mkdir(parents=True)
                (output / "COPY_TO_GAME_ROOT" / "dialogue.txt").write_text("Xin chao\n", encoding="utf-8")
                (output / "patch_verification.json").write_text(
                    json.dumps({"counts": {"PASS": 1}, "results": [{"status": "PASS"}]}),
                    encoding="utf-8",
                )
                (output / "import_report.txt").write_text("patch_verification_status: PASS\n", encoding="utf-8")

            completed: list[dict] = []
            with patch("vntext.app_tasks.apply_translation_package", fake_apply), patch(
                "vntext.app_tasks._find_patch_installer", return_value=installer
            ):
                run_patch_task(
                    csv_path,
                    manifest_path,
                    str(game),
                    str(base),
                    progress=lambda _event: None,
                    log=lambda _line: None,
                    complete=completed.append,
                    patch_out_override=patch_out,
                    write_manifest_file=False,
                )

            self.assertTrue(completed[0]["ok"], completed[0])
            self.assertEqual(completed[0]["patch_engine"], "unity")
            self.assertTrue((patch_out / "VNTextPatchInstaller.exe").read_bytes() == installer.read_bytes())
            self.assertEqual(completed[0]["patch_delivery"], "unity_installer")

    def test_invalid_renpy_route_never_falls_back_to_unity(self):
        with tempfile.TemporaryDirectory(prefix="vntext-patch-delivery-invalid-") as temp:
            base = Path(temp)
            package = base / "package"
            package.mkdir()
            csv_path = package / "translation.csv"
            manifest_path = package / "manifest.json"
            csv_path.write_text("key,source_text,translation\nk,Hello,Xin chao\n", encoding="utf-8")
            manifest_path.write_text(
                json.dumps(
                    {
                        "stats": {"engine": "RENPY_LOOSE_SOURCE"},
                        "entries": [
                            {"key": "k", "import_method": "renpy_dialogue", "backend": "renpy_loose_source"},
                            {"key": "u", "import_method": "plain_text_line", "backend": "plain_text"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            self.assertRaisesRegex(ValueError, "mixed Ren'Py/Unity", detect_patch_engine, json.loads(manifest_path.read_text()))

            applied = False

            def fake_apply(*_args):
                nonlocal applied
                applied = True

            completed: list[dict] = []
            with patch("vntext.app_tasks.apply_translation_package", fake_apply):
                run_patch_task(
                    csv_path,
                    manifest_path,
                    str(base / "game"),
                    str(base),
                    progress=lambda _event: None,
                    log=lambda _line: None,
                    complete=completed.append,
                    patch_out_override=base / "patch",
                )
            self.assertFalse(applied)
            self.assertFalse(completed[0]["ok"])
            self.assertNotIn("VNTextPatchInstaller.exe", str(completed[0].get("summary", "")))

    def test_compiled_only_route_is_not_unity_delivery(self):
        manifest = {"stats": {"engine": "RENPY_COMPILED_ONLY"}, "entries": []}
        with self.assertRaisesRegex(ValueError, "compiled-only"):
            detect_patch_engine(manifest)


if __name__ == "__main__":
    unittest.main()
