"""Static display slots require native evidence; disabled/dynamic stays review."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tests.lib.work_paths import work_temp_dir

from vntext.renpy_extract import static_screen_candidates


class RenPyUiInventoryTests(unittest.TestCase):
    @unittest.skipUnless((Path(__file__).resolve().parents[2]/'.dev-env/tools/renpy-8.5.3/renpy.py').is_file(),'Official SDK8.5.3 absent')
    def test_unproven_dynamic_or_disabled_ui_still_blocks_final_patch(self):
        from vntext.app_tasks import run_extract_task
        from vntext.patch_pipeline import apply_translation_package
        repo=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-ui-negative'))as tmp:
            root=Path(tmp);game=root/'source';(game/'game').mkdir(parents=True)
            source=game/'game/script.rpy'
            source.write_text('label start:\n    "Supported dialogue"\n    return\nscreen ui():\n    text "Disabled label" substitute False\n    text dynamic_value\n',encoding='utf-8')
            events=[]
            run_extract_task(str(game),str(root/'package'),'safe','balanced',True,renpy_sdk_path=str(repo/'.dev-env/tools/renpy-8.5.3'),renpy_sdk_action='existing',progress=lambda _:None,log=lambda _:None,complete=events.append)
            self.assertEqual(events[-1]['extract_status'],'PARTIAL')
            manifest=json.loads((root/'package/manifest.json').read_text(encoding='utf-8'))
            disabled=next(e for e in manifest['entries']if e['source_text']=='Disabled label')
            self.assertTrue(disabled['review_only']);self.assertFalse(disabled.get('patch_proof'))
            self.assertEqual(len(manifest['stats']['renpy_static_ui_unresolved']),1)
            with self.assertRaisesRegex(ValueError,'Extraction is incomplete'):
                apply_translation_package(str(root/'package/translation.csv'),str(root/'package/manifest.json'),str(game),str(root/'patch'))

    @unittest.skipUnless((Path(__file__).resolve().parents[2]/'.dev-env/tools/renpy-8.5.3/renpy.py').is_file(),'Official SDK8.5.3 absent')
    def test_full_audit_static_ui_has_bound_native_global_contracts(self):
        from vntext.app_tasks import run_extract_task
        from vntext.patch_pipeline import apply_translation_package
        repo=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-ui-sdk'))as tmp:
            root=Path(tmp);game=root/'source';(game/'game').mkdir(parents=True)
            gt=json.loads((repo/'evaluation/renpy_completeness_audit_v1/ground_truth.json').read_text(encoding='utf-8'))
            source=game/'game/script.rpy';source.write_text(gt['basic']['script'],encoding='utf-8');before=source.read_bytes();events=[]
            run_extract_task(str(game),str(root/'package'),'safe','balanced',True,renpy_sdk_path=str(repo/'.dev-env/tools/renpy-8.5.3'),renpy_sdk_action='existing',progress=lambda _:None,log=lambda _:None,complete=events.append)
            self.assertEqual(events[-1]['extract_status'],'COMPLETE',events[-1])
            self.assertTrue(events[-1]['native_accounting_complete'])
            manifest=json.loads((root/'package/manifest.json').read_text(encoding='utf-8'))
            self.assertEqual({r['source_text']for r in manifest['stats']['renpy_static_ui_candidates']},{'Plain screen label','Plain button label'})
            promoted=[e for e in manifest['entries']if e['source_text']in {'Plain screen label','Plain button label'}]
            self.assertEqual(len(promoted),2)
            self.assertTrue(all(e['import_method']=='renpy_string'and e.get('native_contract')and not e['review_only']for e in promoted))
            self.assertEqual(source.read_bytes(),before)
    def test_literals_are_preserved_and_wrapped_dynamic_and_comments_not_guessed(self):
        script='''screen inventory():
    text "Plain label"
    textbutton 'Plain button' action NullAction() tooltip "Helpful tip"
    text _("Native label")
    text dynamic_value
    # text "Comment"
    textbutton _("Native button") action NullAction() tooltip 'Other tip'
label start:
    "Dialogue"
'''
        rows=static_screen_candidates(script,'game/ui.rpy',hashlib.sha256(script.encode()).hexdigest())
        self.assertEqual([r.source_text for r in rows],['Plain label','Plain button','Helpful tip','Native label','Native button','Other tip'])
        self.assertTrue(all(r.review_only and not r.patch_proof and not r.native_contract for r in rows))
        self.assertEqual([r.locator['line']for r in rows],[2,3,3,4,7,7])
        self.assertEqual([r.locator['kind']for r in rows],['text','textbutton','tooltip','text','textbutton','tooltip'])

    def test_inventory_review_cannot_be_promoted_to_a_patch_method(self):
        from vntext.patch_pipeline import detect_patch_engine
        row=static_screen_candidates('screen ui():\n    text "Review label"\n','game/ui.rpy','a'*64)[0].to_manifest()
        native={'import_method':'renpy_dialogue'}
        manifest={'stats':{'engine':'RENPY_LOOSE_SOURCE'},'entries':[native,row]}
        self.assertEqual(detect_patch_engine(manifest),'renpy')
        row['review_only']=False
        with self.assertRaisesRegex(ValueError,'mixed'):detect_patch_engine(manifest)

    def test_disabled_or_dynamic_substitution_remains_review_and_dynamic_text_is_unresolved(self):
        unresolved=[]
        rows=static_screen_candidates('screen ui():\n    text "No substitution" substitute False\n    textbutton "Unknown substitution" text_substitute setting\n    text dynamic_value\n    text "Prefix" + name\n','game/ui.rpy','a'*64,unresolved)
        self.assertEqual(len(rows),2)
        self.assertTrue(all(not row.locator['native_global_eligible']for row in rows))
        self.assertEqual(len(unresolved),2)
        self.assertIn('dynamic',unresolved[0]['reason'])
