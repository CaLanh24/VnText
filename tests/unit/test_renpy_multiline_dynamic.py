"""Frozen generated multiline fixture and independent official SDK oracle."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests.lib.work_paths import work_temp_dir
from vntext.renpy_toolchain import validate_sdk
from vntext.app_tasks import run_extract_task
from vntext.package_io import read_csv_rows_file,write_csv_rows_file
from vntext.patch_pipeline import apply_translation_package
from tests.unit.test_renpy_archive import write_rpa

SDK=Path(__file__).resolve().parents[2]/'.dev-env/tools/renpy-8.5.3'
# Expectations are declared before any SDK/product output is collected.
SCRIPT='''default player = "Player"
label start:
    'Single quote dialogue'
    """Multiline
    dialogue [player] {b}bold{/b}"""
    return
screen multiline_ui():
    text ("Parenthesized "
          "adjacent label")
    text ("Constant " + "composition")
    text """Triple screen
literal"""
    text 'Single screen label'
    text "Template [player] {b}bold{/b}"
    text ("Hello " + player)
    text player.upper()
    text ("Left" if player else "Right")
    text _("Recoverable template [player]")
'''
STATIC={
    'Parenthesized adjacent label':'STATIC_RECOVERABLE',
    'Constant composition':'STATIC_RECOVERABLE',
    'Triple screen\nliteral':'STATIC_RECOVERABLE',
    'Single screen label':'STATIC_RECOVERABLE',
    'Template [player] {b}bold{/b}':'TEMPLATE_WITH_INTERPOLATION',
    'Recoverable template [player]':'TEMPLATE_WITH_INTERPOLATION',
}
DYNAMIC=['"Hello " + player','player.upper()','"Left" if player else "Right"']


class MultilineDynamicTests(unittest.TestCase):
    def test_static_expression_rejects_code_execution_and_resource_excess(self):
        from vntext.renpy_static import static_string
        for expression in ['__import__("os").system("bad")','f"Hello {player}"','"A" * 100000000',
                           '"A" + player','"A" if player else "B"','"A".upper()',"'x'"+' + \'x\''*300]:
            with self.subTest(expression=expression[:80]):self.assertIsNone(static_string(expression))
        self.assertEqual(static_string('_("Hello " + "[player]")'),'Hello [player]')
        self.assertIsNone(static_string('"'+('x'*65537)+'"'))

    def test_malformed_and_disabled_multiline_never_admit_a_fragment(self):
        from vntext.renpy_extract import static_screen_candidates
        for statement in ['text ("Prefix" + name)','text "Prefix" +','text "Prefix" if flag',
                          'text ("unterminated"','text """unterminated']:
            with self.subTest(statement=statement):
                unresolved=[];rows=static_screen_candidates('screen ui():\n    '+statement+'\n','game/ui.rpy','a'*64,unresolved)
                self.assertEqual(rows,[]);self.assertEqual(len(unresolved),1)
        rows=static_screen_candidates('screen ui():\n    text ("Disabled "\n          "multiline") substitute False\n','game/ui.rpy','a'*64,[])
        self.assertEqual(rows[0].source_text,'Disabled multiline')
        self.assertFalse(rows[0].locator['native_global_eligible'])
        rows=static_screen_candidates('screen ui():\n    text _("Marked disabled") substitute False\n','game/ui.rpy','a'*64,[])
        self.assertEqual(rows[0].source_text,'Marked disabled');self.assertFalse(rows[0].locator['native_global_eligible'])

    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official SDK8.5.3 absent')
    def test_product_dynamic_has_exact_ledger_no_fragments_and_blocks_final_patch(self):
        sdk=validate_sdk(SDK)
        fixture='\n'.join(line for line in SCRIPT.splitlines()if line!='default player = "Player"')+'\n'
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-dynamic-ledger'))as tmp:
            root=Path(tmp);origin=root/'origin';(origin/'game').mkdir(parents=True)
            (origin/'game/script.rpy').write_text(fixture,encoding='utf-8')
            result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(origin),'compile'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for kind in ('loose','compiled','rpa'):
                game=root/kind;(game/'game').mkdir(parents=True)
                if kind=='rpa':write_rpa(game/'game/archive.rpa',{'script.rpyc':(origin/'game/script.rpyc').read_bytes()})
                else:shutil.copy2(origin/('game/script.rpy'if kind=='loose'else 'game/script.rpyc'),game/'game')
                before={p:p.read_bytes()for p in (game/'game').iterdir()if p.is_file()};events=[];package=root/(kind+'package')
                run_extract_task(str(game),str(package),'safe','balanced',True,renpy_sdk_path=str(SDK),renpy_sdk_action='existing',progress=lambda _:None,log=lambda _:None,complete=events.append)
                self.assertEqual(events[-1]['extract_status'],'PARTIAL',events[-1])
                manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8'))
                ledger=manifest['stats']['renpy_static_ui_unresolved'if kind=='loose'else 'renpy_compiled_expression_unresolved']
                self.assertEqual(len(ledger),3,ledger)
                self.assertTrue(all(item['raw_expression']in fixture for item in ledger))
                self.assertTrue(all(any(item['raw_expression']in {expr,'('+expr+')'}for item in ledger)for expr in DYNAMIC))
                self.assertTrue(all(item['source_sha256']and item['span']and item['classification']=='RUNTIME_GENERATED'for item in ledger))
                self.assertFalse({'Hello ','Left','Right','Player','PLAYER'}&{e['source_text']for e in manifest['entries']})
                self.assertIn('Recoverable template [player]',{e['source_text']for e in manifest['entries']})
                with self.assertRaisesRegex(ValueError,'Extraction is incomplete'):
                    apply_translation_package(str(package/'translation.csv'),str(package/'manifest.json'),str(game),str(root/(kind+'patch')))
                self.assertTrue(all(p.read_bytes()==raw for p,raw in before.items()))
                shutil.rmtree(game)

    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official SDK8.5.3 absent')
    def test_product_static_multiline_roundtrip_loose_compiled_and_rpa(self):
        sdk=validate_sdk(SDK)
        static_script='\n'.join(line for line in SCRIPT.splitlines()if line!='default player = "Player"'and not any(expr in line for expr in DYNAMIC))+'\n'
        # Additional declared oracle case; original frozen SCRIPT stays intact.
        static_script+='    text _("Wrapped " + "constant")\n'
        display_values=list(STATIC)+['Wrapped constant']
        expected=set(display_values)|{'Single quote dialogue','Multiline dialogue [player] {b}bold{/b}'}
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-multiline-product'))as tmp:
            root=Path(tmp);origin=root/'origin';(origin/'game').mkdir(parents=True)
            (origin/'game/script.rpy').write_text(static_script,encoding='utf-8')
            result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(origin),'compile'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for kind in ('loose','compiled','rpa'):
                game=root/kind;(game/'game').mkdir(parents=True)
                if kind=='rpa':write_rpa(game/'game/archive.rpa',{'script.rpyc':(origin/'game/script.rpyc').read_bytes()})
                else:shutil.copy2(origin/('game/script.rpy'if kind=='loose'else 'game/script.rpyc'),game/'game')
                original={p:p.read_bytes()for p in (game/'game').iterdir()if p.is_file()}
                identities=[]
                for iteration in (0,1):
                    package=root/(kind+str(iteration));events=[]
                    run_extract_task(str(game),str(package),'safe','balanced',True,renpy_sdk_path=str(SDK),renpy_sdk_action='existing',progress=lambda _:None,log=lambda _:None,complete=events.append)
                    self.assertTrue(events[-1].get('ok'),events[-1])
                    manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8'))
                    fields,rows=read_csv_rows_file(package/'translation.csv')
                    self.assertEqual({row['source_text']for row in rows},expected)
                    identities.append(sorted((e['key'],e['source_text'],e['file_path'],e['context'],e['import_method'],json.dumps(e['locator'],sort_keys=True))for e in manifest['entries']))
                    for row in rows:row['translation']='VI '+row['source_text']
                    write_csv_rows_file(package/'translation.csv',fields,rows)
                    if iteration==0:
                        from vntext.patchability import renpy_contract_fingerprint
                        manifest_path=package/'manifest.json';manifest_bytes=manifest_path.read_bytes()
                        changed=next(e for e in manifest['entries']if e['native_contract']['precondition'].get('display_slot'))
                        changed['native_contract']['precondition']['display_slot']['raw_expression']+=' changed'
                        changed['native_contract']['fingerprint']=renpy_contract_fingerprint(changed['native_contract'])
                        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False),encoding='utf-8')
                        try:
                            with self.assertRaisesRegex(ValueError,'precondition drift'):
                                apply_translation_package(str(package/'translation.csv'),str(manifest_path),str(game),str(root/(kind+'drift')))
                        finally:manifest_path.write_bytes(manifest_bytes)
                        manifest=json.loads(manifest_bytes)
                        if kind=='loose':
                            dialogue=next(e for e in manifest['entries']if e['source_text'].startswith('Multiline dialogue'))
                            self.assertEqual(dialogue['native_contract']['context']['enrichment']['status'],'RESOLVED')
                            span=dialogue['native_contract']['provenance']['source_span']
                            self.assertGreater(span['end_line'],span['start_line'])
                    patch=root/(kind+'patch'+str(iteration))
                    apply_translation_package(str(package/'translation.csv'),str(package/'manifest.json'),str(game),str(patch))
                    shutil.copytree(patch/'COPY_TO_GAME_ROOT',game,dirs_exist_ok=True)
                self.assertEqual(identities[0],identities[1])
                # Probe is added only after production extract/repatch has ended.
                probe='init 1000 python:\n    import json, os\n    renpy.game.preferences.language="vietnamese"\n    result={}\n'
                for value in display_values:
                    probe+=f'    result[{value!r}]=renpy.text.text.Text({value!r},scope={{"player":"Player"}}).text\n'
                for entry in manifest['entries']:
                    if entry['import_method']=='renpy_dialogue':
                        native_id=entry['locator']['native_id']
                        probe+=f'    node,translated=renpy.game.script.translator.lookup_translate({native_id!r})\n    result[{native_id!r}]=[node.what,node.who,node.with_,translated]\n'
                probe+='    with open(os.path.join(config.basedir,"readback.json"),"w",encoding="utf-8") as output:\n        json.dump(result,output,ensure_ascii=False)\n'
                (game/'game/probe.rpy').write_text(probe,encoding='utf-8')
                result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(game),'lint'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
                rb=game/'readback.json';self.assertTrue(rb.is_file(),result.stdout+result.stderr)
                readback=json.loads(rb.read_text(encoding='utf-8'))
                for value in display_values:self.assertEqual(readback[value],['VI '+value.replace('[player]','Player')])
                for entry in manifest['entries']:
                    if entry['import_method']=='renpy_dialogue':self.assertEqual(readback[entry['locator']['native_id']],['VI '+entry['source_text'],None,None,True])
                self.assertTrue(all(p.read_bytes()==raw for p,raw in original.items()))
                print('MULTILINE_PRODUCT',kind,json.dumps(readback,ensure_ascii=False))
                shutil.rmtree(game)

    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official SDK8.5.3 absent')
    def test_official_sdk_locks_normalization_and_expression_semantics(self):
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-multiline-oracle'))as tmp:
            root=Path(tmp);(root/'game').mkdir()
            (root/'game/script.rpy').write_text(SCRIPT,encoding='utf-8')
            before=(root/'game/script.rpy').read_bytes();sdk=validate_sdk(SDK)
            probe='''init 1000 python:
    import json, os
    text=renpy.text.text.Text
    expressions=[("Parenthesized " "adjacent label"),("Constant "+"composition"),"""Triple screen
literal""",'Single screen label',"Template [player] {b}bold{/b}",_("Recoverable template [player]")]
    dialogues={key:node.what for key,node in renpy.game.script.translator.default_translates.items() if hasattr(node,"what")}
    if not dialogues:
        dialogues={key:value.block[0].what for key,value in renpy.game.script.translator.default_translates.items()}
    result={"expressions":expressions,"display":[text(value,scope={"player":"Player"}).text for value in expressions],"dialogues":dialogues}
    with open(os.path.join(config.basedir,"readback.json"),"w",encoding="utf-8") as output:
        json.dump(result,output,ensure_ascii=False)
'''
            (root/'game/probe.rpy').write_text(probe,encoding='utf-8')
            result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(root),'lint'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
            rb=root/'readback.json'
            self.assertTrue(rb.is_file(),result.stdout+result.stderr+'\n'+'\n'.join(p.read_text(encoding='utf-8',errors='replace')[:5000]for p in root.glob('*.txt')))
            readback=json.loads(rb.read_text(encoding='utf-8'))
            self.assertEqual(readback['expressions'],list(STATIC))
            self.assertEqual(set(readback['dialogues'].values()),{'Single quote dialogue','Multiline dialogue [player] {b}bold{/b}'})
            self.assertEqual((root/'game/script.rpy').read_bytes(),before)
            print('FROZEN_FIXTURE_SHA256',hashlib.sha256(SCRIPT.encode()).hexdigest())
            print('OFFICIAL_MULTILINE_ORACLE',json.dumps(readback,ensure_ascii=False))

    def test_static_multiline_and_dynamic_inventory_are_separate(self):
        from vntext.renpy_extract import static_screen_candidates
        unresolved=[];digest=hashlib.sha256(SCRIPT.encode()).hexdigest()
        rows=static_screen_candidates(SCRIPT,'game/script.rpy',digest,unresolved)
        self.assertEqual({row.source_text for row in rows},set(STATIC))
        self.assertTrue(all(row.locator['native_global_eligible']for row in rows))
        self.assertEqual(len(unresolved),3)
        self.assertTrue(all(row['classification']=='RUNTIME_GENERATED'for row in unresolved))
        for row in rows:
            self.assertEqual(row.locator['classification'],STATIC[row.source_text])
            self.assertTrue(row.locator['raw_expression'])
            self.assertEqual(row.locator['source_sha256'],digest)
