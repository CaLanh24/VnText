from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from tests.lib.work_paths import work_temp_dir

WORK = work_temp_dir("renpy-adapter")

from vntext.renpy_adapter import detect_engine


class RenPyEngineDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior_tempdir = tempfile.tempdir
        tempfile.tempdir = str(WORK)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior_tempdir

    def _folder(self) -> tempfile.TemporaryDirectory:
        return tempfile.TemporaryDirectory()

    def test_loose_source_is_supported(self):
        with self._folder() as temp:
            root = Path(temp)
            (root / "game").mkdir()
            (root / "game" / "script.rpy").write_text("label start:\n", encoding="utf-8")
            result = detect_engine(root)
            self.assertEqual((result.engine, result.status), ("RENPY_LOOSE_SOURCE", "SUPPORTED"))

    def test_translation_overlay_and_exact_helper_do_not_hide_compiled_source(self):
        with self._folder()as temp:
            root=Path(temp);(root/'game/tl/vietnamese').mkdir(parents=True)
            (root/'game/script.rpyc').write_bytes(b'compiled evidence')
            (root/'game/tl/vietnamese/vntext.rpy').write_text('translate vietnamese strings:\n    old "A"\n    new "B"\n',encoding='utf-8')
            helper=root/'game/zzz_vntext_vietnamese.rpy'
            helper.write_text('init 999 python:\n    config.language = "vietnamese"\n',encoding='utf-8')
            self.assertEqual(detect_engine(root).engine,'RENPY_COMPILED_ONLY')
            helper.write_text('label extra_source:\n    "Do not hide this source"\n',encoding='utf-8')
            self.assertEqual(detect_engine(root).engine,'RENPY_LOOSE_SOURCE')

    def test_compiled_only_is_not_patchable(self):
        with self._folder() as temp:
            root = Path(temp)
            (root / "game").mkdir()
            (root / "game" / "script.rpyc").write_bytes(b"x")
            result = detect_engine(root)
            self.assertEqual((result.engine, result.status), ("RENPY_COMPILED_ONLY", "EXTRACT_ONLY"))
            from vntext.extract_pipeline import extract_project
            with self.assertRaisesRegex(ValueError,"Ren'Py"):
                extract_project(str(root))

    def test_supported_rpa_source_is_detected_without_fallback_route(self):
        from tests.unit.test_renpy_archive import write_rpa
        with self._folder() as temp:
            root=Path(temp);(root/"game").mkdir()
            write_rpa(root/"game/scripts.rpa",{"game/script.rpy":b'label start:\n    "Hello"\n'})
            result=detect_engine(root)
            self.assertEqual((result.engine,result.status),("RENPY_ARCHIVE_SOURCE","SUPPORTED"))
            from vntext.extract_pipeline import extract_project
            with self.assertRaisesRegex(ValueError,"RPA"):
                extract_project(str(root))

    def test_compiled_source_in_archive_remains_compiled_only(self):
        from tests.unit.test_renpy_archive import write_rpa
        with self._folder() as temp:
            root=Path(temp);(root/"game").mkdir()
            write_rpa(root/"game/scripts.rpa",{"game/script.rpyc":b"opaque compiled"})
            self.assertEqual(detect_engine(root).engine,"RENPY_COMPILED_ONLY")

    def test_unsupported_archive_is_not_guessed_as_unity(self):
        with self._folder() as temp:
            root=Path(temp);(root/"game").mkdir();(root/"game/old.rpa").write_bytes(b"RPA-1.0 unsupported")
            result=detect_engine(root)
            self.assertEqual(result.engine,"RENPY_ARCHIVE_UNSUPPORTED")
            from vntext.extract_pipeline import extract_project
            with self.assertRaisesRegex(ValueError,"RPA"):
                extract_project(str(root))

    def test_mixed_evidence_requires_review(self):
        with self._folder() as temp:
            root = Path(temp)
            (root / "game").mkdir()
            (root / "game" / "script.rpy").write_text("label start:\n", encoding="utf-8")
            (root / "Example_Data").mkdir()
            result = detect_engine(root)
            self.assertEqual((result.engine, result.status), ("MIXED", "REVIEW_REQUIRED"))
            from vntext.extract_pipeline import extract_project
            with self.assertRaisesRegex(ValueError,"Ren'Py"):
                extract_project(str(root))

    def test_unknown_is_not_guessed(self):
        with self._folder() as temp:
            result = detect_engine(Path(temp))
            self.assertEqual((result.engine, result.status), ("UNKNOWN", "REVIEW_REQUIRED"))
