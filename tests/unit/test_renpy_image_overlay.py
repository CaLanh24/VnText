from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tests.lib.work_paths import work_temp_dir
from tests.unit.test_renpy_archive import write_rpa
from tests.unit import test_renpy_patch
from vntext import renpy_image_overlay as overlay
from vntext.app_tasks import _validate_renpy_overlay_output
from vntext.patch_output import write_renpy_patch_manifest
from vntext.patch_renpy import RenPyPatchError, apply_renpy_translation_package

WORK = work_temp_dir("renpy-image-overlay-tests")
SCREEN = """screen main_menu():
    imagemap:
        ground 'gui/overlay/menu.png'
        hover "gui/overlay/menu_hover.png"
        hotspot (10, 20, 60, 30) action Start()
        hotspot (10, 60, 60, 30) action Quit()
    imagebutton idle "gui/button.png" action NullAction()
"""
REGION = [8, 18, 70, 80]


def _base_image(color=(30, 60, 90), mode="RGB", size=(120, 100)) -> Image.Image:
    image = Image.new(mode, size)
    pixels = image.load()
    for x in range(size[0]):
        for y in range(size[1]):
            value = (color[0] + x % 17, color[1] + y % 13, color[2] + (x + y) % 11)
            pixels[x, y] = value + ((255,) if mode == "RGBA" else ())
    return image


def _png(image: Image.Image) -> bytes:
    import io
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def _localized(image: Image.Image, region=REGION) -> Image.Image:
    changed = image.copy()
    x, y, w, h = region
    changed.paste(Image.new(image.mode, (w, h), (240, 230, 170) + ((255,) if image.mode == "RGBA" else ())), (x, y))
    return changed


class RenPyImageOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior_tempdir = tempfile.tempdir
        tempfile.tempdir = str(WORK)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior_tempdir

    def _game(self, base: Path, *, archive: bool = False):
        game, csv, manifest = test_renpy_patch.RenPyPatchTests._package(None, base)
        (game / "game" / "screens.rpy").write_text(SCREEN, encoding="utf-8")
        members = {"gui/overlay/menu.png": _png(_base_image()), "gui/overlay/menu_hover.png": _png(_base_image((90, 60, 30))),
                   "gui/button.png": _png(_base_image((1, 2, 3), "RGBA", (20, 10)))}
        if archive:
            write_rpa(game / "game" / "archive.rpa", members)
        else:
            for name, data in members.items():
                (game / "game" / name).parent.mkdir(parents=True, exist_ok=True)
                (game / "game" / name).write_bytes(data)
        return game, csv, manifest

    def _spec(self, base: Path, items=None, *, name="spec.json") -> Path:
        directory = base / "spec"
        directory.mkdir(exist_ok=True)
        defaults = {"gui/overlay/menu.png": _base_image(), "gui/overlay/menu_hover.png": _base_image((90, 60, 30))}
        images = []
        for index, (path, rendered) in enumerate(items if items is not None else [(p, _localized(i)) for p, i in defaults.items()]):
            filename = f"rendered{index}.png"
            if isinstance(rendered, bytes):
                (directory / filename).write_bytes(rendered)
            else:
                rendered.save(directory / filename)
            images.append({"path": path, "rendered": filename, "regions": [REGION]})
        (directory / name).write_text(json.dumps({"schema": 1, "language": "vietnamese", "images": images}), encoding="utf-8")
        return directory / name

    def _apply(self, base: Path, game, csv, manifest, spec):
        return apply_renpy_translation_package(str(csv), str(manifest), str(game), str(base / "out"), image_overlay_spec=str(spec))

    def test_loose_assets_become_exact_bound_locale_images_without_touching_the_game(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest = self._game(base)
            before = {p: p.read_bytes() for p in game.rglob("*") if p.is_file()}
            self._apply(base, game, csv, manifest, self._spec(base))
            out = base / "out"
            report = json.loads((out / "image_overlay.json").read_text(encoding="utf-8"))
            self.assertEqual([i["path"] for i in report["images"]], ["gui/overlay/menu.png", "gui/overlay/menu_hover.png"])
            first = report["images"][0]
            self.assertEqual(first["baseline"], {"path": "game/gui/overlay/menu.png", "sha256": hashlib.sha256(before[game / "game/gui/overlay/menu.png"]).hexdigest()})
            self.assertEqual((first["width"], first["height"], first["mode"]), (120, 100, "RGB"))
            self.assertEqual(first["references"][0]["hotspots"], [[10, 20, 60, 30], [10, 60, 60, 30]])
            self.assertTrue(all(REGION[0] <= v for v in first["changed_bbox"][:2]) and first["changed_bbox"][2] <= 78 and first["changed_bbox"][3] <= 98)
            staged = out / "COPY_TO_GAME_ROOT" / first["target"]
            self.assertEqual(hashlib.sha256(staged.read_bytes()).hexdigest(), first["sha256"])
            self.assertEqual({p: p.read_bytes() for p in game.rglob("*") if p.is_file()}, before)
            payload = _validate_renpy_overlay_output(out)
            self.assertTrue((payload / first["target"]).is_file())
            package = write_renpy_patch_manifest(out, game, "0.1.24", json.loads(manifest.read_text(encoding="utf-8")))
            checks = {c["path"]: c["sha256"] for c in package["game_checks"]}
            self.assertEqual(checks["game/gui/overlay/menu.png"], first["baseline"]["sha256"])
            self.assertIn("game/gui/overlay/menu_hover.png", checks)
            files = {f["path"]: f for f in package["files"]}
            self.assertEqual(files[first["target"]]["source_sha256"], first["sha256"])
            self.assertFalse(files[first["target"]]["original_exists"])
            self.assertEqual(package["image_overlay"]["images"][0]["sha256"], first["sha256"])

    def test_archive_member_is_bound_by_container_and_member_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest = self._game(base, archive=True)
            self._apply(base, game, csv, manifest, self._spec(base))
            report = json.loads((base / "out/image_overlay.json").read_text(encoding="utf-8"))
            baseline = report["images"][0]["baseline"]
            self.assertEqual((baseline["path"], baseline["member"]), ("game/archive.rpa", "gui/overlay/menu.png"))
            self.assertEqual(baseline["sha256"], hashlib.sha256((game / "game/archive.rpa").read_bytes()).hexdigest())
            package = write_renpy_patch_manifest(base / "out", game, "0.1.24", json.loads(manifest.read_text(encoding="utf-8")))
            self.assertIn({"path": "game/archive.rpa", "sha256": baseline["sha256"]}, package["game_checks"])
            # the archive changing after generation is refused when the installer identity is written
            (game / "game/archive.rpa").write_bytes((game / "game/archive.rpa").read_bytes() + b"x")
            with self.assertRaises(Exception):
                write_renpy_patch_manifest(base / "out", game, "0.1.24", json.loads(manifest.read_text(encoding="utf-8")))

    def _refused(self, build, *, archive=False, extra=None, needle=""):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest = self._game(base, archive=archive)
            if extra:
                extra(game)
            spec = build(base)
            with self.assertRaises((overlay.ImageOverlayError, RenPyPatchError)) as caught:
                self._apply(base, game, csv, manifest, spec)
            self.assertIn(needle, str(caught.exception))
            self.assertFalse((base / "out/COPY_TO_GAME_ROOT/game/tl/vietnamese/gui").exists())
            self.assertFalse((base / "out/image_overlay.json").exists())

    def test_changes_outside_declared_regions_are_refused(self):
        self._refused(lambda b: self._spec(b, [("gui/overlay/menu.png", _localized(_base_image(), [8, 18, 70, 85]))]), needle="outside the declared regions")

    def test_identical_render_size_and_mode_changes_are_refused(self):
        self._refused(lambda b: self._spec(b, [("gui/overlay/menu.png", _base_image())]), needle="identical")
        self._refused(lambda b: self._spec(b, [("gui/overlay/menu.png", _localized(_base_image()).resize((121, 100)))]), needle="size/mode")
        self._refused(lambda b: self._spec(b, [("gui/overlay/menu.png", _localized(_base_image()).convert("RGBA"))]), needle="size/mode")

    def test_unknown_unreferenced_or_unsafe_asset_paths_are_refused(self):
        add = lambda game: (game / "game/gui/unused.png").write_bytes(_png(_base_image()))
        self._refused(lambda b: self._spec(b, [("gui/unused.png", _localized(_base_image()))]), extra=add, needle="not a known imagemap")
        self._refused(lambda b: self._spec(b, [("gui/missing.png", _localized(_base_image()))]), needle="not a known imagemap")
        for path in ("../gui/overlay/menu.png", "tl/vietnamese/menu.png", "gui/overlay/menu.jpg", "C:/menu.png"):
            self._refused(lambda b, path=path: self._spec(b, [(path, _localized(_base_image()))]), needle="")

    def test_lossy_baseline_and_loose_archive_shadow_are_refused(self):
        def jpeg_screen(game):
            (game / "game/screens.rpy").write_text(SCREEN.replace("menu.png", "menu.jpg"), encoding="utf-8")
        self._refused(lambda b: self._spec(b, [("gui/overlay/menu.jpg", _localized(_base_image()))]), extra=jpeg_screen, needle="lossless")

        def shadow(game):
            write_rpa(game / "game/archive.rpa", {"gui/overlay/menu.png": (game / "game/gui/overlay/menu.png").read_bytes()})
        self._refused(lambda b: self._spec(b, [("gui/overlay/menu.png", _localized(_base_image()))]), extra=shadow, needle="more than once")

    def test_existing_different_locale_image_and_wrong_format_are_refused(self):
        def locale(game):
            target = game / "game/tl/vietnamese/gui/overlay/menu.png"
            target.parent.mkdir(parents=True)
            target.write_bytes(_png(_base_image((5, 5, 5))))
        self._refused(lambda b: self._spec(b, [("gui/overlay/menu.png", _localized(_base_image()))]), extra=locale, needle="locale image already exists")
        stream = __import__("io").BytesIO()
        _localized(_base_image()).save(stream, format="JPEG")
        self._refused(lambda b: self._spec(b, [("gui/overlay/menu.png", stream.getvalue())]), needle="expected PNG")

    def test_hotspot_outside_the_bitmap_is_refused(self):
        def screen(game):
            (game / "game/screens.rpy").write_text(SCREEN.replace("(10, 60, 60, 30)", "(100, 90, 60, 30)"), encoding="utf-8")
        self._refused(lambda b: self._spec(b, [("gui/overlay/menu.png", _localized(_base_image()))]), extra=screen, needle="hotspot lies outside")

    def test_overlay_generation_does_not_need_numpy_in_the_packaged_worker(self):
        import sys
        from unittest import mock
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(sys.modules, {"numpy": None}):
            base = Path(temp)
            game, csv, manifest = self._game(base)
            self._apply(base, game, csv, manifest, self._spec(base))
            report = json.loads((base / "out/image_overlay.json").read_text(encoding="utf-8"))
            self.assertEqual(report["images"][0]["changed_bbox"][:2], [REGION[0], REGION[1]])
            self.assertGreater(report["images"][0]["changed_pixels"], 0)

    def test_spec_schema_is_strict(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, _, _ = self._game(base)
            for body in ({"schema": 2, "images": []}, {"schema": 1, "images": []}, {"schema": 1, "language": "french", "images": [{}]},
                         {"schema": 1, "images": [{"path": "gui/overlay/menu.png", "rendered": "x.png", "regions": [], "extra": 1}]}):
                spec = base / "bad.json"
                spec.write_text(json.dumps(body), encoding="utf-8")
                with self.assertRaises(overlay.ImageOverlayError):
                    overlay.prepare_image_overlays(game, spec)

    def test_validator_rejects_stray_tampered_or_unreported_images(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest = self._game(base)
            self._apply(base, game, csv, manifest, self._spec(base))
            out = base / "out"
            _validate_renpy_overlay_output(out)
            stray = out / "COPY_TO_GAME_ROOT/game/tl/vietnamese/gui/stray.png"
            stray.write_bytes(_png(_base_image()))
            with self.assertRaises(RuntimeError):
                _validate_renpy_overlay_output(out)
            stray.unlink()
            staged = out / "COPY_TO_GAME_ROOT/game/tl/vietnamese/gui/overlay/menu.png"
            good = staged.read_bytes()
            staged.write_bytes(_png(_base_image((200, 1, 1))))
            with self.assertRaises(RuntimeError):
                _validate_renpy_overlay_output(out)
            staged.write_bytes(good)
            report_path = out / "image_overlay.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["images"][0]["target"] = "game/evil.png"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            with self.assertRaises(RuntimeError):
                _validate_renpy_overlay_output(out)
            report_path.unlink()          # images without their report are not accepted either
            with self.assertRaises(RuntimeError):
                _validate_renpy_overlay_output(out)

    def test_baseline_drift_between_generation_and_publication_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            game, csv, manifest = self._game(base)
            payloads, report = overlay.prepare_image_overlays(game, self._spec(base))
            overlay.verify_baselines(game, report)
            (game / "game/gui/overlay/menu.png").write_bytes(_png(_base_image((1, 1, 1))))
            with self.assertRaises(overlay.ImageOverlayError):
                overlay.verify_baselines(game, report)


if __name__ == "__main__":
    unittest.main()
