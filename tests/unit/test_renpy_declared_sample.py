import json
from pathlib import Path
import tempfile
import unittest

from tests.lib.work_paths import work_temp_dir
from tests.unit import test_renpy_patch as patch_fixtures
from tests.tools.renpy_declared_sample import create_declared_sample
from vntext.patch_pipeline import apply_translation_package
from vntext.patchability import RENPY_DIALOGUE_PATCH_PROOF, RENPY_STRING_PATCH_PROOF


class DeclaredSampleTests(unittest.TestCase):
    def test_unproven_row_is_refused_without_creating_sample(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-sample')) as tmp:
            root=Path(tmp)
            _,_,manifest=patch_fixtures.RenPyPatchTests()._package(root)
            (root/'extract_status.json').write_text('{"status":"PARTIAL","complete":false}',encoding='utf-8')
            entry=json.loads(manifest.read_text(encoding='utf-8'))['entries'][0]
            pairs=[{'key':entry['key'],'source_text':entry['source_text'],'translation':'Xin chào [name]'}]
            with self.assertRaisesRegex(ValueError,'supported patch proof'):
                create_declared_sample(root,root/'sample',pairs)
            self.assertFalse((root/'sample').exists())

    def test_sample_preserves_full_partial_and_exact_provenance_through_normal_patch(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-sample'))as tmp:
            root=Path(tmp);game,csv,manifest=patch_fixtures.RenPyPatchTests()._package(root)
            full=manifest.parent;(full/'extract_status.json').write_text('{"status":"PARTIAL","complete":false}',encoding='utf-8')
            document=json.loads(manifest.read_text(encoding='utf-8'));document['stats']={'engine':'RENPY_LOOSE_SOURCE'}
            for entry in document['entries']:
                entry['context']='fixture native translation unit'
                entry['patch_proof']=dict(RENPY_DIALOGUE_PATCH_PROOF if entry['import_method']=='renpy_dialogue' else RENPY_STRING_PATCH_PROOF)
            manifest.write_text(json.dumps(document),encoding='utf-8')
            before={p.name:p.read_bytes()for p in full.iterdir()if p.is_file()}
            entry=document['entries'][0];pairs=[{'key':entry['key'],'source_text':entry['source_text'],'translation':'VI '+entry['source_text']}]
            provenance=create_declared_sample(full,root/'sample',pairs)
            actual=json.loads((root/'sample/manifest.json').read_text(encoding='utf-8'))['entries'][0]
            for key in ('key','source_text','locator','native_contract'):self.assertEqual(actual[key],entry[key])
            apply_translation_package(str(root/'sample/translation.csv'),str(root/'sample/manifest.json'),str(game),str(root/'patch'))
            self.assertTrue((root/'patch/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy').is_file())
            self.assertEqual(provenance['full_status']['status'],'PARTIAL')
            self.assertTrue(all((full/name).read_bytes()==raw for name,raw in before.items()))
            pairs[0]['source_text']='changed'
            with self.assertRaisesRegex(ValueError,'drift'):create_declared_sample(full,root/'bad',pairs)
