"""Engine scan contract over many generated game layouts (not tied to any real game).

For every layout the scan must: finish quickly, never raise, classify the engine from ONE source, never read a Ren'Py folder as "unknown without a reason",
and never report a font/image inventory that contradicts the engine verdict.
"""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tests.lib.work_paths import work_temp_dir
from tests.unit.test_renpy_archive import write_rpa, write_rpa2
from vntext.renpy_adapter import detect_engine
from vntext.renpy_asset_scan import scan_renpy_assets

SCRIPT = b'label start:\n    "Hello"\n    return\n'
RPYC = b"RENPY RPC2" + b"\0" * 64


def _touch(root: Path, relative: str, data: bytes = b"x") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _rpa(writer, root: Path, relative: str, members: dict) -> None:
    (root / relative).parent.mkdir(parents=True, exist_ok=True)
    writer(root / relative, members)


def _renpy_shell(root: Path) -> None:
    (root / "renpy").mkdir(parents=True, exist_ok=True)
    (root / "lib").mkdir(exist_ok=True)
    _touch(root, "Game.exe")


LAYOUTS = {
    # name: (builder, allowed engines)
    "loose_rpy": (lambda r: (_renpy_shell(r), _touch(r, "game/script.rpy", SCRIPT)), {"RENPY_LOOSE_SOURCE"}),
    "loose_rpy_no_runtime_dirs": (lambda r: _touch(r, "game/script.rpy", SCRIPT), {"RENPY_LOOSE_SOURCE"}),
    "rpa3_scripts": (lambda r: (_renpy_shell(r), _rpa(write_rpa, r, "game/scripts.rpa", {"script.rpy": SCRIPT})), {"RENPY_ARCHIVE_SOURCE"}),
    "rpa2_scripts": (lambda r: (_renpy_shell(r), _rpa(write_rpa2, r, "game/scripts.rpa", {"script.rpy": SCRIPT})), {"RENPY_ARCHIVE_SOURCE"}),
    "compiled_only": (lambda r: (_renpy_shell(r), _touch(r, "game/script.rpyc", RPYC)), {"RENPY_COMPILED_ONLY"}),
    "images_only_rpa": (lambda r: (_renpy_shell(r), _rpa(write_rpa, r, "game/images.rpa", {"bg/a.png": b"png"})), {"UNKNOWN", "RENPY_ARCHIVE_SOURCE"}),
    "fonts_but_no_script": (lambda r: (_renpy_shell(r), _touch(r, "game/fonts/a.ttf", b"\0\1\0\0")), {"UNKNOWN"}),
    "corrupt_rpa": (lambda r: (_renpy_shell(r), _touch(r, "game/broken.rpa", b"RPA-3.0 nonsense\n")), {"RENPY_ARCHIVE_UNSUPPORTED"}),
    "unicode_and_spaces": (lambda r: (_renpy_shell(r), _touch(r, "game/tập lệnh đặc biệt.rpy", SCRIPT)), {"RENPY_LOOSE_SOURCE"}),
    "tl_folder_ignored": (lambda r: (_renpy_shell(r), _touch(r, "game/tl/vietnamese/x.rpy", SCRIPT)), {"UNKNOWN"}),
    "empty_game_dir": (lambda r: (r / "game").mkdir(parents=True), {"UNKNOWN"}),
    "unity_data_dir": (lambda r: (_touch(r, "G.exe"), _touch(r, "G_Data/globalgamemanagers")), {"UNITY"}),
    "unity_plus_renpy": (lambda r: (_touch(r, "G_Data/globalgamemanagers"), _touch(r, "game/script.rpy", SCRIPT)), {"MIXED"}),
    "empty_folder": (lambda r: None, {"UNKNOWN"}),
    "plain_text_assets": (lambda r: _touch(r, "dialogue.txt", b"Hello\n"), {"UNKNOWN"}),
}


class ScanLayoutMatrixTests(unittest.TestCase):
    def test_every_layout_scans_quickly_consistently_and_without_error(self):
        base = work_temp_dir("scan-layout-matrix")
        for name, (build, allowed) in LAYOUTS.items():
            with self.subTest(layout=name), tempfile.TemporaryDirectory(dir=base) as temp:
                root = Path(temp) / "game root"
                root.mkdir()
                build(root)
                started = time.monotonic()
                detection = detect_engine(root)
                assets = scan_renpy_assets(root)
                self.assertLess(time.monotonic() - started, 20, "scan must be bounded")
                self.assertIn(detection.engine, allowed, detection)
                self.assertTrue(detection.reason, "every verdict carries its reason")
                # Font/image inventory exists exactly for a folder with game/, whatever the engine verdict is.
                self.assertEqual((root / "game").is_dir(), assets is not None)
                if assets is not None:
                    self.assertEqual(assets["engine"], "renpy")
                    json.dumps(assets)  # the report must serialise
                # A folder the scanner calls UNKNOWN while it found Ren'Py assets is the one case the app words as "Ren'Py, no readable script".
                if detection.engine == "UNKNOWN" and assets is not None:
                    self.assertIn("fonts", assets)

    def test_scan_does_not_modify_the_game_folder(self):
        base = work_temp_dir("scan-layout-matrix")
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            _renpy_shell(root)
            _rpa(write_rpa, root, "game/scripts.rpa", {"script.rpy": SCRIPT})
            _touch(root, "game/script.rpyc", RPYC)

            def snapshot():
                return {p.relative_to(root).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns) for p in root.rglob("*") if p.is_file()}
            before = snapshot()
            detect_engine(root)
            scan_renpy_assets(root)
            self.assertEqual(before, snapshot())

    def test_archive_is_not_reparsed_for_each_scan_step(self):
        from vntext import renpy_archive
        base = work_temp_dir("scan-layout-matrix")
        with tempfile.TemporaryDirectory(dir=base) as temp:
            root = Path(temp)
            _renpy_shell(root)
            _rpa(write_rpa, root, "game/scripts.rpa", {"script.rpy": SCRIPT})
            renpy_archive.clear_archive_cache()
            with patch.object(renpy_archive.RenPyArchive, "_hash_file", autospec=True, side_effect=renpy_archive.RenPyArchive._hash_file) as hashed:
                detect_engine(root)
                scan_renpy_assets(root)
                detect_engine(root)
            self.assertEqual(hashed.call_count, 1, "one full-file hash per archive per process for read-only scans")


if __name__ == "__main__":
    unittest.main()
