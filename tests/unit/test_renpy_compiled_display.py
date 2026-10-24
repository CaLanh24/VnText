"""Official compiled fixtures, inspected through inert typed AST only."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.lib.work_paths import work_temp_dir
from vntext.renpy_toolchain import validate_sdk
from vntext.app_tasks import run_extract_task
from tests.unit.test_renpy_archive import write_rpa
from tests.lib.dev_environment import renpy_native_sdk

SDK=renpy_native_sdk()


class RenPyCompiledDisplayTests(unittest.TestCase):
    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official SDK8.5.3 absent')
    def test_compiled_static_mapping_and_dynamic_review_are_separate(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-compiled-display'))as tmp:
            root=Path(tmp);game=root/'source';(game/'game').mkdir(parents=True)
            source=game/'game/script.rpy'
            source.write_text('label start:\n    "Native dialogue"\n    menu:\n        "Menu option":\n            pass\n    $ label = _("Localized setting")\n    return\nscreen audit_ui():\n    text "Plain screen"\n    textbutton _("Wrapped button") action NullAction() tooltip "Plain tooltip"\n    text dynamic_value\n',encoding='utf-8')
            sdk=validate_sdk(SDK)
            result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(game),'compile'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            source.unlink();compiled=game/'game/script.rpyc';before=compiled.read_bytes()
            from vntext.renpy_compiled import compiled_display_candidates
            rows=compiled_display_candidates(before)
            self.assertTrue({'Menu option','Localized setting','Plain screen','Wrapped button','Plain tooltip'}<={r['text']for r in rows},rows)
            self.assertNotIn('dynamic_value',{r['text']for r in rows})
            events=[]
            run_extract_task(str(game),str(root/'package'),'safe','balanced',True,progress=lambda _:None,log=lambda _:None,complete=events.append)
            self.assertEqual(events[-1]['extract_status'],'PARTIAL',events[-1])
            manifest=json.loads((root/'package/manifest.json').read_text(encoding='utf-8'))
            candidates=[e for e in manifest['entries']if e['import_method']=='renpy_string']
            self.assertTrue({'Menu option','Localized setting','Plain screen','Wrapped button','Plain tooltip'}<={r['source_text']for r in candidates})
            self.assertTrue(all(not e['review_only']and e.get('patch_proof')and e.get('native_contract')for e in candidates))
            self.assertTrue(all(e['native_contract']['precondition']['source_sha256']==hashlib.sha256(before).hexdigest()for e in candidates))
            self.assertEqual(compiled.read_bytes(),before)
            from vntext.patch_pipeline import apply_translation_package
            with self.assertRaisesRegex(ValueError,'Extraction is incomplete'):
                apply_translation_package(str(root/'package/translation.csv'),str(root/'package/manifest.json'),str(game),str(root/'patch'))
            self.assertFalse((root/'patch/COPY_TO_GAME_ROOT').exists())
            compiled.unlink();archive=game/'game/archive.rpa';write_rpa(archive,{'script.rpyc':before})
            archive_before=archive.read_bytes();events=[]
            run_extract_task(str(game),str(root/'archive-package'),'safe','balanced',True,progress=lambda _:None,log=lambda _:None,complete=events.append)
            self.assertEqual(events[-1]['extract_status'],'PARTIAL',events[-1])
            archived=json.loads((root/'archive-package/manifest.json').read_text(encoding='utf-8'))
            native=next(e for e in archived['entries']if e['import_method']=='renpy_dialogue')
            self.assertEqual(native['file_path'],'game/script.rpyc')
            self.assertEqual(native['native_contract']['provenance']['source_container']['member_name'],'script.rpyc')
            self.assertEqual(archive.read_bytes(),archive_before)
