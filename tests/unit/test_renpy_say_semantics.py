"""Static Say grammar must retain native speaker and transition semantics."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests.lib.work_paths import work_temp_dir
from tests.lib.dev_environment import renpy_native_sdk
from vntext.app_tasks import run_extract_task
from vntext.package_io import read_csv_rows_file, write_csv_rows_file
from vntext.patch_pipeline import apply_translation_package
from vntext.renpy_toolchain import validate_sdk

ROOT=Path(__file__).resolve().parents[2]
SDK=renpy_native_sdk()


class RenPySaySemanticsTests(unittest.TestCase):
    def test_bounded_grammar_rejects_expressions_and_statement_injection(self):
        from vntext.renpy_extract import _say_statement
        self.assertEqual(_say_statement('e happy "Text" with dissolve'),('Text','e','happy','with dissolve'))
        self.assertEqual(_say_statement('"Guide" "Text"'),('Text','"Guide"','',''))
        for raw in ['e "Text" with Dissolve(0.5)','e "Text"; jump evil','e\n"Text"','name() "Text"']:
            with self.subTest(raw=raw),self.assertRaises(ValueError):_say_statement(raw)

    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official SDK8.5.3 absent')
    def test_literal_speaker_and_transition_keep_native_semantics(self):
        self._assert_say_semantics('define e = Character("Eileen")\nlabel start:\n    "Guide" "Literal speaker dialogue"\n    e "Timed dialogue" with dissolve\n    return\n')

    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official SDK8.5.3 absent')
    def test_compiled_literal_speaker_and_transition_keep_native_semantics(self):
        self._assert_say_semantics('label start:\n    "Guide" "Literal speaker dialogue"\n    "Timed dialogue" with dissolve\n    return\n',compiled=True)

    def _assert_say_semantics(self,script,compiled=False):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-say')) as tmp:
            root=Path(tmp);game=root/'source';(game/'game').mkdir(parents=True)
            source=game/'game/script.rpy';source.write_text(script,encoding='utf-8');before=source.read_bytes()
            if compiled:
                sdk=validate_sdk(SDK)
                result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(game),'compile'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                source.unlink();source=source.with_suffix('.rpyc');before=source.read_bytes()
            events=[]
            run_extract_task(str(game),str(root/'package'),'safe','balanced',True,renpy_sdk_path=str(SDK),renpy_sdk_action='existing',progress=lambda _:None,log=lambda _:None,complete=events.append)
            self.assertTrue(events[-1].get('ok'),events[-1])
            manifest=json.loads((root/'package/manifest.json').read_text(encoding='utf-8'))
            entries=[e for e in manifest['entries']if e['import_method']=='renpy_dialogue']
            self.assertEqual({e['source_text']for e in entries},{'Literal speaker dialogue','Timed dialogue'})
            fields,rows=read_csv_rows_file(root/'package/translation.csv')
            for row in rows:row['translation']='VI '+row['source_text']
            write_csv_rows_file(root/'package/translation.csv',fields,rows)
            apply_translation_package(str(root/'package/translation.csv'),str(root/'package/manifest.json'),str(game),str(root/'patch'))
            sdk=validate_sdk(SDK);readbacks=[]
            for patched in (False,True):
                lookup=root/'lookup';(lookup/'game').mkdir(parents=True)
                (lookup/'game'/source.name).write_bytes(before)
                if patched:shutil.copytree(root/'patch/COPY_TO_GAME_ROOT',lookup,dirs_exist_ok=True)
                probe='init 1000 python:\n    import json, os\n    renpy.game.preferences.language="vietnamese"\n    result={}\n'
                for entry in entries:
                    native_id=entry['locator']['native_id']
                    probe+=f'    node, translated=renpy.game.script.translator.lookup_translate({native_id!r})\n    result[{native_id!r}]=[node.what,node.who,node.with_,translated]\n'
                probe+='    with open(os.path.join(config.basedir,"readback.json"),"w",encoding="utf-8") as output:\n        json.dump(result,output,ensure_ascii=False)\n'
                (lookup/'game/probe.rpy').write_text(probe,encoding='utf-8')
                result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(lookup),'lint'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                readbacks.append(json.loads((lookup/'readback.json').read_text(encoding='utf-8')))
                shutil.rmtree(lookup)
            for native_id,original in readbacks[0].items():
                self.assertEqual(readbacks[1][native_id],['VI '+original[0],original[1],original[2],True])
            self.assertEqual(source.read_bytes(),before)
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(),hashlib.sha256(before).digest())

    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official SDK8.5.3 absent')
    def test_unsupported_transition_retains_supported_rows_with_partial_status(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-say-partial')) as tmp:
            root=Path(tmp);game=root/'source';(game/'game').mkdir(parents=True)
            source=game/'game/script.rpy'
            source.write_text('define e = Character("Eileen")\nlabel start:\n    e "Supported dialogue"\n    e "Unsupported transition" with Dissolve(0.5)\n    return\n',encoding='utf-8')
            before=source.read_bytes();events=[]
            run_extract_task(str(game),str(root/'package'),'safe','balanced',True,renpy_sdk_path=str(SDK),renpy_sdk_action='existing',progress=lambda _:None,log=lambda _:None,complete=events.append)
            self.assertEqual(events[-1]['extract_status'],'PARTIAL',events[-1])
            manifest=json.loads((root/'package/manifest.json').read_text(encoding='utf-8'))
            self.assertIn('Supported dialogue',{e['source_text']for e in manifest['entries']})
            self.assertNotIn('Unsupported transition',{e['source_text']for e in manifest['entries']})
            status=json.loads((root/'package/extract_status.json').read_text(encoding='utf-8'))
            self.assertGreater(status['errors'],0)
            unresolved=manifest['stats']['renpy_native_unresolved']
            self.assertEqual(len(unresolved),1)
            self.assertEqual(unresolved[0]['source_sha256'],hashlib.sha256(before).hexdigest())
            self.assertTrue(unresolved[0]['native_id'])
            self.assertIn('Dissolve(0.5)',unresolved[0]['raw_block'])
            self.assertEqual(source.read_bytes(),before)
