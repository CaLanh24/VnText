"""Existing translations are target state, never source-template authority."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from tests.lib.work_paths import work_temp_dir
from tests.lib.dev_environment import renpy_native_sdk
from vntext.app_tasks import run_extract_task
from vntext.package_io import read_csv_rows_file, write_csv_rows_file
from vntext.patch_pipeline import apply_translation_package
from vntext.patch_renpy import RenPyPatchError, apply_renpy_translation_package
from tests.unit import test_renpy_patch as patch_fixtures

ROOT = Path(__file__).resolve().parents[2]
SDK = renpy_native_sdk()


class RenPyRoundTripTests(unittest.TestCase):
    @unittest.skipUnless((SDK/'renpy.py').is_file(), 'Official SDK8.5.3 absent')
    def test_own_overlay_reextract_keeps_authoritative_identity_and_source(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-roundtrip')) as tmp:
            root=Path(tmp);game=root/'source';(game/'game').mkdir(parents=True)
            gt=json.loads((ROOT/'evaluation/renpy_completeness_audit_v1/ground_truth.json').read_text(encoding='utf-8'))
            # This R5 fixture exercises only the admitted native patch subset.
            # R3 tests the full immutable audit input and its mandatory PARTIAL.
            script=game/'game/script.rpy';script.write_text('\n'.join(line for line in gt['basic']['script'].splitlines()
                if line.strip()not in {'text "Plain screen label"','textbutton "Plain button label" action NullAction()'})+'\n',encoding='utf-8')
            original=script.read_bytes()
            def extract(out):
                events=[]
                run_extract_task(str(game),str(out),'safe','balanced',True,
                    renpy_sdk_path=str(SDK),renpy_sdk_action='existing',
                    progress=lambda _:None,log=lambda _:None,complete=events.append)
                self.assertTrue(events[-1].get('ok'),events[-1])
                return json.loads((out/'manifest.json').read_text(encoding='utf-8'))
            first=extract(root/'first')
            fields,rows=read_csv_rows_file(root/'first/translation.csv')
            for row in rows:row['translation']='VI '+row['source_text']
            write_csv_rows_file(root/'first/translation.csv',fields,rows)
            apply_translation_package(str(root/'first/translation.csv'),str(root/'first/manifest.json'),str(game),str(root/'patch'))
            shutil.copytree(root/'patch/COPY_TO_GAME_ROOT',game,dirs_exist_ok=True)
            before={p.relative_to(game).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in game.rglob('*')if p.is_file()}
            second=extract(root/'second')
            def identities(m):
                return sorted((e['key'],e['source_text'],e['file_path'],e['context'],e.get('object_info',''),e['import_method'],json.dumps(e['locator'],sort_keys=True))for e in m['entries'])
            self.assertEqual(identities(first),identities(second))
            self.assertEqual(script.read_bytes(),original)
            self.assertEqual(before,{p.relative_to(game).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in game.rglob('*')if p.is_file()})
            fields,rows=read_csv_rows_file(root/'second/translation.csv')
            for row in rows:row['translation']='VI '+row['source_text']
            write_csv_rows_file(root/'second/translation.csv',fields,rows)
            apply_translation_package(str(root/'second/translation.csv'),str(root/'second/manifest.json'),str(game),str(root/'repatch'))
            verification=json.loads((root/'repatch/patch_verification.json').read_text(encoding='utf-8'))
            self.assertEqual(verification['already_satisfied'],sum(e['import_method']in {'renpy_dialogue','renpy_string'}for e in first['entries']))
            self.assertTrue(all(item['reason']=='already_satisfied'for item in verification['results']))
            self.assertEqual(before,{p.relative_to(game).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in game.rglob('*')if p.is_file()})
            # SDK lookup in separate copies proves native semantics before and
            # after overlay; probes/compiled outputs never change the source.
            from vntext.renpy_toolchain import validate_sdk
            sdk=validate_sdk(SDK)
            expected_dialogue={e['locator']['native_id']:e['source_text']for e in first['entries']if e['import_method']=='renpy_dialogue'}
            expected_strings={e['source_text']:e['source_text']for e in first['entries']if e['import_method']=='renpy_string'}
            for stage in ['original','patched','repatched']:
                patched=stage!='original'
                lookup=root/('lookup-'+stage)
                (lookup/'game').mkdir(parents=True)
                (lookup/'game/script.rpy').write_bytes(original)
                if patched:shutil.copytree(root/('repatch'if stage=='repatched'else 'patch')/'COPY_TO_GAME_ROOT',lookup,dirs_exist_ok=True)
                probe='init 1000 python:\n    import json, os\n    renpy.game.preferences.language = "vietnamese"\n    out = {"dialogue": {}, "strings": {}}\n'
                for native_id in expected_dialogue:
                    probe+=f'    node, translated = renpy.game.script.translator.lookup_translate({native_id!r})\n    out["dialogue"][{native_id!r}] = [node.what, translated]\n'
                for source in expected_strings:
                    probe+=f'    out["strings"][{source!r}] = renpy.translate_string({source!r}, language="vietnamese")\n'
                probe+='    with open(os.path.join(config.basedir,"readback.json"),"w",encoding="utf-8") as receipt:\n        json.dump(out,receipt,ensure_ascii=False)\n'
                (lookup/'game/probe.rpy').write_text(probe,encoding='utf-8')
                result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(lookup),'lint'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                rb=json.loads((lookup/'readback.json').read_text(encoding='utf-8'))
                prefix='VI 'if patched else ''
                self.assertEqual(rb['dialogue'],{key:[prefix+value,patched]for key,value in expected_dialogue.items()})
                self.assertEqual(rb['strings'],{key:prefix+value for key,value in expected_strings.items()})
                shutil.rmtree(lookup)

    def test_existing_inventory_does_not_require_generated_provenance(self):
        from vntext.renpy_extract import existing_translation_inventory, RenPyTemplateParseError
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-target-state')) as tmp:
            game=Path(tmp);target=game/'game/tl/vietnamese/old.rpy';target.parent.mkdir(parents=True)
            target.write_text('translate vietnamese strings:\n    old "Old label"\n    new "Nhãn cũ"\n',encoding='utf-8')
            state=existing_translation_inventory(game)
            self.assertEqual(state['strings']['Old label']['translation'],'Nhãn cũ')
            other=target.with_name('conflict.rpy');other.write_text('translate vietnamese strings:\n    old "Old label"\n    new "Khác"\n',encoding='utf-8')
            with self.assertRaisesRegex(RenPyTemplateParseError,'conflict'):existing_translation_inventory(game)
            other.unlink();target.write_text('translate vietnamese strings:\n    old "Old label"\n',encoding='utf-8')
            with self.assertRaisesRegex(RenPyTemplateParseError,'unverifiable'):existing_translation_inventory(game)

    def test_repatch_preserves_existing_own_overlay_unselected_strings(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-repatch')) as tmp:
            base=Path(tmp);game,csv,manifest=patch_fixtures.RenPyPatchTests()._package(base)
            own=game/'game/tl/vietnamese/vntext.rpy';own.parent.mkdir(parents=True)
            prior='translate vietnamese strings:\n    old "Existing label"\n    new "Nhãn có sẵn"\n'
            own.write_text(prior,encoding='utf-8')
            apply_renpy_translation_package(str(csv),str(manifest),str(game),str(base/'out'))
            output=(base/'out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy').read_text(encoding='utf-8')
            self.assertIn(prior,output)
            self.assertEqual(own.read_text(encoding='utf-8'),prior)

    def test_existing_dialogue_conflict_refuses_before_writing(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-existing-conflict')) as tmp:
            base=Path(tmp);game,csv,manifest=patch_fixtures.RenPyPatchTests()._package(base)
            entry=next(e for e in json.loads(manifest.read_text(encoding='utf-8'))['entries']if e['import_method']=='renpy_dialogue')
            own=game/'game/tl/vietnamese/other.rpy';own.parent.mkdir(parents=True)
            speaker=entry.get('object_info')or''
            own.write_text(f'translate vietnamese {entry["locator"]["native_id"]}:\n    {speaker} "Khác nội dung"\n',encoding='utf-8')
            with self.assertRaisesRegex(RenPyPatchError,'conflict'):
                apply_renpy_translation_package(str(csv),str(manifest),str(game),str(base/'out'))
            self.assertFalse((base/'out/COPY_TO_GAME_ROOT').exists())

    def test_added_target_during_staging_refuses_and_preserves_foreign_file(self):
        from vntext import patch_renpy
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-inventory-cas')) as tmp:
            base=Path(tmp);game,csv,manifest=patch_fixtures.RenPyPatchTests()._package(base)
            foreign=game/'game/tl/vietnamese/foreign.rpy'
            original=patch_renpy._render_overlay
            raw=b'translate vietnamese strings:\n    old "Foreign"\n    new "Ngoai"\n'
            def mutate(*args):
                foreign.parent.mkdir(parents=True,exist_ok=True);foreign.write_bytes(raw)
                return original(*args)
            with patch.object(patch_renpy,'_render_overlay',side_effect=mutate):
                with self.assertRaisesRegex(RenPyPatchError,'inventory changed'):
                    apply_renpy_translation_package(str(csv),str(manifest),str(game),str(base/'out'))
            self.assertEqual(foreign.read_bytes(),raw)
            self.assertFalse((base/'out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy').exists())

    def test_equivalent_dialogue_elsewhere_is_not_duplicated(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-dialogue-satisfied')) as tmp:
            base=Path(tmp);game,csv,manifest=patch_fixtures.RenPyPatchTests()._package(base)
            entries=json.loads(manifest.read_text(encoding='utf-8'))['entries']
            entry=next(e for e in entries if e['import_method']=='renpy_dialogue')
            _,rows=read_csv_rows_file(csv)
            translation=next(row['translation']for row in rows if row['key']==entry['key'])
            other=game/'game/tl/vietnamese/other.rpy';other.parent.mkdir(parents=True)
            other.write_text(f'translate vietnamese {entry["locator"]["native_id"]}:\n    {entry.get("object_info")or ""} {json.dumps(translation,ensure_ascii=False)}\n',encoding='utf-8')
            before=other.read_bytes()
            apply_renpy_translation_package(str(csv),str(manifest),str(game),str(base/'out'))
            overlay=(base/'out/COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy').read_text(encoding='utf-8')
            self.assertNotIn('translate vietnamese '+entry['locator']['native_id']+':',overlay)
            verification=json.loads((base/'out/patch_verification.json').read_text(encoding='utf-8'))
            record=next(item for item in verification['results']if item['key']==entry['key'])
            self.assertEqual(record['reason'],'already_satisfied');self.assertEqual(record['target'],str(other))
            self.assertEqual(other.read_bytes(),before)

    def test_foreign_addition_after_activation_rolls_back_only_owned_output(self):
        from vntext import patch_renpy
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-activation-cas')) as tmp:
            base=Path(tmp);game,csv,manifest=patch_fixtures.RenPyPatchTests()._package(base)
            out=base/'out'
            apply_renpy_translation_package(str(csv),str(manifest),str(game),str(out))
            target=out/'COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy'
            activation=out/'COPY_TO_GAME_ROOT/game/zzz_vntext_vietnamese.rpy'
            prior=(target.read_bytes(),activation.read_bytes())
            foreign=game/'game/tl/vietnamese/foreign.rpy'
            raw=b'translate vietnamese strings:\n    old "Foreign"\n    new "Ngoai"\n'
            replace=patch_renpy.os.replace
            def mutate(src,dst):
                result=replace(src,dst)
                if Path(dst)==activation and '.renpy-overlay-'in str(src):
                    foreign.parent.mkdir(parents=True,exist_ok=True);foreign.write_bytes(raw)
                return result
            with patch.object(patch_renpy.os,'replace',side_effect=mutate):
                with self.assertRaisesRegex(RenPyPatchError,'inventory changed'):
                    apply_renpy_translation_package(str(csv),str(manifest),str(game),str(out))
            self.assertEqual((target.read_bytes(),activation.read_bytes()),prior)
            self.assertEqual(foreign.read_bytes(),raw)
