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

    def test_renpy_installer_delivery_carries_exact_source_identity(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix="vntext-renpy-installer-") as temp:
            base = Path(temp)
            game, csv_path, manifest_path = self._renpy_package(base)
            installer = base / "VNTextPatchInstaller.exe"
            installer.write_bytes(b"installer fixture")
            completed = []
            with patch("vntext.app_tasks._find_patch_installer", return_value=installer):
                run_patch_task(csv_path, manifest_path, str(game), str(base), progress=lambda _: None,
                               log=lambda _: None, complete=completed.append, patch_out_override=base / "patch")
            self.assertTrue(completed[-1]["ok"], completed[-1])
            self.assertEqual("renpy_installer", completed[-1]["patch_delivery"])
            manifest = json.loads((base / "patch/patch_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("renpy", manifest["engine"])
            self.assertTrue(manifest["game_checks"])
            self.assertEqual(b"installer fixture", (base / "patch/VNTextPatchInstaller.exe").read_bytes())

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
                include_installer=False,
            )

            self.assertEqual(len(completed), 1)
            self.assertTrue(completed[0]["ok"], completed[0])
            self.assertEqual(completed[0]["patch_engine"], "renpy")
            self.assertEqual(completed[0]["patch_delivery"], "renpy_native_overlay")
            payload = patch_out / "COPY_TO_GAME_ROOT"
            from vntext.renpy_font_support import FALLBACK_SHA256
            font_stem = f"game/tl/vietnamese/vntext_font_{FALLBACK_SHA256[:16]}"
            self.assertEqual(
                sorted(path.relative_to(payload).as_posix() for path in payload.rglob("*") if path.is_file()),
                ["game/tl/vietnamese/vntext.rpy", font_stem + ".license.txt", font_stem + ".ttf", "game/zzz_vntext_vietnamese.rpy"],
            )
            # the generated bundled font and its licence are the verified bytes, bound to the generation result
            self.assertEqual(hashlib.sha256((payload / (font_stem + ".ttf")).read_bytes()).hexdigest(), FALLBACK_SHA256)
            self.assertEqual((payload / (font_stem + ".license.txt")).read_bytes(), (Path(__file__).resolve().parents[2] / "vntext/fonts/DejaVuSans.txt").read_bytes())
            self.assertEqual(json.loads((patch_out / "font_preflight.json").read_text(encoding="utf-8"))["payload_font"], font_stem + ".ttf")
            self.assertFalse((patch_out / "VNTextPatchInstaller.exe").exists())
            self.assertFalse((patch_out / "patch_manifest.json").exists())
            self.assertTrue((patch_out / "HUONG_DAN_CAI_PATCH.txt").is_file())
            self.assertNotIn("VNTextPatchInstaller.exe", completed[0]["patch_install_instructions"])
            self.assertNotIn("Unity", completed[0]["patch_install_instructions"])
            self.assertNotIn("installer", completed[0]["patch_install_instructions"].casefold())
            self.assertTrue(any("thư mục bản Việt hóa hợp lệ" in line for line in logs))

            installed = base / "approved-renpy-copy"
            shutil.copytree(payload, installed)
            self.assertIn('translate vietnamese start_a:', (installed / "game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8"))
            self.assertTrue((installed / "game/zzz_vntext_vietnamese.rpy").is_file())
            self.assertEqual((game / "game/script.rpy").read_text(encoding="utf-8"), 'label start:\n    "Hello [name]"\n')

    def test_unity_task_keeps_installer_delivery(self, installer_available=True):
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
                json.dumps({"entries": [{"key": "k", "source_text": "Hello", "import_method": "plain_text_line"}]}),
                encoding="utf-8",
            )
            installer = base / "VNTextPatchInstaller.exe"
            installer.write_bytes(b"unity-installer")
            patch_out = base / "patch"

            def fake_apply(_csv, _manifest, _game, output, _progress, replacement_font=None):
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
                "vntext.app_tasks._find_patch_installer", return_value=installer if installer_available else None
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
            if installer_available:
                self.assertEqual((patch_out / "VNTextPatchInstaller.exe").read_bytes(), installer.read_bytes())
            else:
                self.assertFalse((patch_out / "VNTextPatchInstaller.exe").exists())
                self.assertIn("Chưa sẵn sàng", completed[0]["patch_install_instructions"])
                self.assertNotIn("Mở VNTextPatchInstaller.exe", completed[0]["summary"])
            self.assertEqual(completed[0]["patch_delivery"], "unity_installer")

    def test_patch_content_label_names_what_was_patched_not_the_engine(self):
        from vntext.app_tasks import _patch_content_label

        self.assertEqual("Bản Việt hóa văn bản thường", _patch_content_label({"results": [{"method": "plain_text_line"}]}))
        self.assertEqual("Patch Unity/Naninovel", _patch_content_label(
            {"results": [{"method": "unity_textasset_line"}, {"method": "naninovel_script_string"}]}))
        self.assertEqual("Patch", _patch_content_label({"results": [{"method": "plain_text_line"}, {"method": "unity_ui_text"}]}))
        self.assertEqual("Patch", _patch_content_label(None))
        self.assertEqual("Patch", _patch_content_label({"results": []}))

    def test_missing_unity_installer_is_not_reported_ready_to_install(self):
        self.test_unity_task_keeps_installer_delivery(installer_available=False)

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


class RenpyOverlayFontPayloadTests(unittest.TestCase):
    """The native overlay validator accepts the generator's own font (+ bundled licence) and nothing else."""

    BUNDLED = Path(__file__).resolve().parents[2] / "vntext/fonts/DejaVuSans.ttf"
    LICENCE = Path(__file__).resolve().parents[2] / "vntext/fonts/DejaVuSans.txt"
    BASE = ("game/tl/vietnamese/vntext.rpy", "game/zzz_vntext_vietnamese.rpy")

    def _payload(self, base: Path, *, font: bytes | None = None, licence: bytes | None = None, report: dict | None = None, name: str | None = None) -> Path:
        out = base / "patch"
        root = out / "COPY_TO_GAME_ROOT"
        for rel in self.BASE:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(b"translate vietnamese strings:\n")
        digest = hashlib.sha256(font).hexdigest() if font is not None else ""
        stem = f"game/tl/vietnamese/vntext_font_{digest[:16]}"
        if font is not None:
            (root / (name or stem + ".ttf")).write_bytes(font)
        if licence is not None:
            (root / (stem + ".license.txt")).write_bytes(licence)
        if report is not None:
            body = {"sha256": digest, "payload_font": stem + ".ttf"}
            body.update(report)
            (out / "font_preflight.json").write_text(json.dumps(body), encoding="utf-8")
        return out

    def _check(self, out: Path):
        from vntext.app_tasks import _validate_renpy_overlay_output
        return _validate_renpy_overlay_output(out)

    def test_no_font_payload_keeps_the_two_file_layout(self):
        with tempfile.TemporaryDirectory(prefix="vntext-renpy-nofont-") as temp:
            out = self._payload(Path(temp))
            self.assertEqual(out / "COPY_TO_GAME_ROOT", self._check(out))
            with_report = self._payload(Path(temp) / "b", report={"sha256": "", "payload_font": ""})     # report without a payload font = no font
            self.assertEqual(with_report / "COPY_TO_GAME_ROOT", self._check(with_report))

    def test_bundled_font_with_its_verified_licence_is_accepted(self):
        with tempfile.TemporaryDirectory(prefix="vntext-renpy-bundled-") as temp:
            out = self._payload(Path(temp), font=self.BUNDLED.read_bytes(), licence=self.LICENCE.read_bytes(), report={})
            self.assertEqual(out / "COPY_TO_GAME_ROOT", self._check(out))

    def test_custom_font_is_accepted_without_a_bundled_licence(self):
        with tempfile.TemporaryDirectory(prefix="vntext-renpy-custom-") as temp:
            out = self._payload(Path(temp), font=b"custom font fixture bytes", report={})
            self.assertEqual(out / "COPY_TO_GAME_ROOT", self._check(out))

    def test_stale_foreign_or_unbound_font_payload_is_rejected(self):
        font = self.BUNDLED.read_bytes()
        cases = {}
        with tempfile.TemporaryDirectory(prefix="vntext-renpy-reject-") as temp:
            root = Path(temp)
            # a font with no generation result at all
            cases["font without report"] = self._payload(root / "a", font=font, licence=self.LICENCE.read_bytes())
            # report names the font, bytes differ (stale / tampered)
            tampered = self._payload(root / "b", font=font, licence=self.LICENCE.read_bytes(), report={})
            (tampered / "COPY_TO_GAME_ROOT/game/tl/vietnamese" / f"vntext_font_{hashlib.sha256(font).hexdigest()[:16]}.ttf").write_bytes(font + b"x")
            cases["bytes differ from the report"] = tampered
            # a second, foreign font next to the generated one
            extra = self._payload(root / "c", font=font, licence=self.LICENCE.read_bytes(), report={})
            (extra / "COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext_font_0000000000000000.ttf").write_bytes(b"older")
            cases["stale second font"] = extra
            # the report points outside the allowed name pattern
            cases["foreign name"] = self._payload(root / "d", font=font, licence=self.LICENCE.read_bytes(), report={"payload_font": "game/evil.ttf"})
            # bundled font without its licence / with an altered licence
            cases["missing licence"] = self._payload(root / "e", font=font, report={})
            cases["altered licence"] = self._payload(root / "f", font=font, licence=b"not the licence", report={})
            # licence without any font
            only_licence = self._payload(root / "g")
            (only_licence / "COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext_font_3fdf69cabf06049e.license.txt").write_bytes(self.LICENCE.read_bytes())
            cases["licence without font"] = only_licence
            # report names a font that is not staged
            missing = self._payload(root / "h", font=font, report={})
            (missing / "COPY_TO_GAME_ROOT/game/tl/vietnamese" / f"vntext_font_{hashlib.sha256(font).hexdigest()[:16]}.ttf").unlink()
            cases["named font not staged"] = missing
            # a custom (non-bundled) font may not drag a bundled licence in
            custom = self._payload(root / "i", font=b"custom bytes", licence=self.LICENCE.read_bytes(), report={})
            cases["custom font with a bundled licence"] = custom
            for label, out in cases.items():
                with self.subTest(label), self.assertRaises(RuntimeError):
                    self._check(out)


class RenpyGeneratedFontDeliveryTests(unittest.TestCase):
    """Worker generate/package through run_patch_task with a synthetic game: custom font and no-font outcomes."""

    _renpy_package = staticmethod(PatchDeliveryTests._renpy_package)

    def _run(self, base: Path, *, font: str = "", prior_overlay: bool = False):
        game, csv_path, manifest_path = self._renpy_package(base)
        if prior_overlay:
            prior = game / "game/tl/vietnamese/vntext.rpy"
            prior.parent.mkdir(parents=True)
            prior.write_text('translate vietnamese strings:\n    old "Other"\n    new "Khac"\n', encoding="utf-8")
        patch_out = base / "Patch_Viet_Hoa"
        completed: list[dict] = []
        run_patch_task(csv_path, manifest_path, str(game), str(base), progress=lambda _e: None, log=lambda _l: None, complete=completed.append,
                       patch_out_override=patch_out, include_installer=False, replacement_font=font)
        return patch_out, completed

    def test_custom_font_is_delivered_without_the_bundled_licence(self):
        inter = Path(__file__).resolve().parents[2] / "wpf_app/VNText.Studio.App/Assets/Fonts/Inter-Regular.ttf"
        if not inter.is_file():
            self.skipTest("fixture font missing")
        with tempfile.TemporaryDirectory(prefix="vntext-renpy-customfont-") as temp:
            patch_out, completed = self._run(Path(temp), font=str(inter))
            self.assertTrue(completed[-1]["ok"], completed[-1])
            digest = hashlib.sha256(inter.read_bytes()).hexdigest()
            files = sorted(p.relative_to(patch_out / "COPY_TO_GAME_ROOT").as_posix() for p in (patch_out / "COPY_TO_GAME_ROOT").rglob("*") if p.is_file())
            self.assertEqual(["game/tl/vietnamese/vntext.rpy", f"game/tl/vietnamese/vntext_font_{digest[:16]}.ttf", "game/zzz_vntext_vietnamese.rpy"], files)

    def test_prior_overlay_without_a_font_keeps_the_two_file_layout(self):
        with tempfile.TemporaryDirectory(prefix="vntext-renpy-nofont-run-") as temp:
            patch_out, completed = self._run(Path(temp), prior_overlay=True)
            self.assertTrue(completed[-1]["ok"], completed[-1])
            files = sorted(p.relative_to(patch_out / "COPY_TO_GAME_ROOT").as_posix() for p in (patch_out / "COPY_TO_GAME_ROOT").rglob("*") if p.is_file())
            self.assertEqual(["game/tl/vietnamese/vntext.rpy", "game/zzz_vntext_vietnamese.rpy"], files)

    def test_rebuild_from_game_with_generated_bundled_font_overlay(self):
        with tempfile.TemporaryDirectory(prefix="vntext-renpy-rebuild-") as temp:
            base = Path(temp)
            game, csv_path, manifest_path = self._renpy_package(base)
            (game / "game/gui.rpy").write_text(
                'style navigation_button_text:\n    font "menu.ttf"\n'
                'style say_dialogue:\n    font "dialogue.otf"\n',
                encoding="utf-8",
            )
            completed = []
            for output in (base / "first", base / "second"):
                run_patch_task(csv_path, manifest_path, str(game), str(base),
                               progress=lambda _e: None, log=lambda _l: None, complete=completed.append,
                               patch_out_override=output, include_installer=False)
                self.assertTrue(completed[-1]["ok"], completed[-1])
                payload = output / "COPY_TO_GAME_ROOT"
                script = (payload / "game/tl/vietnamese/vntext.rpy").read_text(encoding="utf-8")
                report = json.loads((output / "font_preflight.json").read_text(encoding="utf-8"))
                self.assertIn("translate vietnamese style navigation_button_text:", script)
                self.assertIn("translate vietnamese style say_dialogue:", script)
                self.assertTrue((payload / report["payload_font"]).is_file())
                if output.name == "first":
                    shutil.copytree(payload, game, dirs_exist_ok=True)

    def test_rebuild_refuses_a_dynamic_translation_style(self):
        with tempfile.TemporaryDirectory(prefix="vntext-renpy-dynamic-style-") as temp:
            base = Path(temp)
            game, csv_path, manifest_path = self._renpy_package(base)
            prior = game / "game/tl/vietnamese/vntext.rpy"
            prior.parent.mkdir(parents=True)
            prior.write_text('translate vietnamese style default:\n    font lookup_font()\n', encoding="utf-8")
            completed = []
            run_patch_task(csv_path, manifest_path, str(game), str(base),
                           progress=lambda _e: None, log=lambda _l: None, complete=completed.append,
                           patch_out_override=base / "patch", include_installer=False)
            self.assertFalse(completed[-1]["ok"])
            self.assertIn("unverifiable existing font style block", str(completed[-1]))
