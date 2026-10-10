"""Native SDK tests use only generated source; missing SDK is an explicit skip."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from vntext.renpy_toolchain import validate_sdk, copy_template_workspace, generate_empty_vietnamese_template
from vntext.renpy_extract import extract_native_template_entries, parse_renpy_translation_templates
from tests.lib.work_paths import work_temp_dir

SDK = Path(os.environ.get('VNTEXT_RENPY_NATIVE_SDK',str(Path(__file__).resolve().parents[2]/'.dev-env/tools/renpy-8.5.3')))

class NativeRenPySdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prior_tempdir = tempfile.tempdir
        cls._managed_temp_root = work_temp_dir("renpy-native-sdk")
        tempfile.tempdir = str(cls._managed_temp_root)

    @classmethod
    def tearDownClass(cls):
        tempfile.tempdir = cls._prior_tempdir

    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official pinned RenPy8.5.3 SDK absent; native acceptance not run')
    def test_native_generated_dialogue_menu_strings_and_input_unchanged(self):
        sdk=validate_sdk(SDK)
        with tempfile.TemporaryDirectory(prefix='native-sdk-') as temp:
            root=Path(temp);source=root/'source';(source/'game').mkdir(parents=True)
            script=source/'game/script.rpy'
            script.write_text('define e = Character("Eileen")\nlabel start:\n    e "Hello [name]!"\n    menu:\n        "First choice":\n            pass\n    $ label_text = _("Settings")\n    return\n',encoding='utf-8')
            digest=hashlib.sha256(script.read_bytes()).hexdigest();workspace=root/'workspace'
            inventory=copy_template_workspace(source,workspace)
            run=generate_empty_vietnamese_template(sdk,workspace)
            print(json.dumps({'command':run.args,'stdout':run.stdout,'stderr':run.stderr,'exit_code':run.returncode,'copy_inventory':inventory},ensure_ascii=True))
            self.assertEqual(run.returncode,0)
            units=parse_renpy_translation_templates(workspace/'game/tl/vietnamese',language='vietnamese')
            own=[unit for unit in units if unit.source_file.replace('\\','/').endswith('game/script.rpy') or unit.source_file=='script.rpy']
            texts={unit.source_text for unit in own}
            self.assertTrue({'Hello [name]!','First choice','Settings'}.issubset(texts),texts)
            self.assertTrue(any(unit.native_id for unit in own if unit.unit_kind=='dialogue'))
            self.assertEqual(hashlib.sha256(script.read_bytes()).hexdigest(),digest)
            self.assertEqual(list(source.rglob('*.rpyc')),[])

    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official pinned RenPy8.5.3 SDK absent; native acceptance not run')
    def test_minimal_translation_workspace_matches_native_full_copy(self):
        sdk=validate_sdk(SDK)
        with tempfile.TemporaryDirectory(prefix='native-compare-') as temp:
            root=Path(temp);source=root/'source';(source/'game').mkdir(parents=True)
            script=source/'game/script.rpy'
            script.write_text('define e = Character("Eileen")\nlabel start:\n    e "Hello [name]!"\n    menu:\n        "First choice":\n            pass\n    $ label_text = _("Settings")\n    return\n',encoding='utf-8')
            (source/'game'/'unused.png').write_bytes(b'not decoded by script')
            digest=hashlib.sha256(script.read_bytes()).hexdigest();outputs=[];runs=[]
            for name,translation_only in [('full',False),('minimal',True)]:
                workspace=root/name
                inventory=copy_template_workspace(source,workspace,translation_only=translation_only)
                run=generate_empty_vietnamese_template(sdk,workspace);runs.append(run)
                units=parse_renpy_translation_templates(workspace/'game/tl/vietnamese',language='vietnamese')
                own=[u for u in units if u.source_file.replace('\\','/').endswith('game/script.rpy') or u.source_file=='script.rpy']
                outputs.append([(u.source_text,u.native_id,u.unit_kind) for u in own])
                print(json.dumps({'workspace':name,'command':run.args,'stdout':run.stdout,'stderr':run.stderr,'exit_code':run.returncode,'copy_inventory':inventory},ensure_ascii=True))
            self.assertTrue(all(run.returncode==0 for run in runs))
            self.assertEqual(outputs[0],outputs[1])
            self.assertTrue({'Hello [name]!','First choice','Settings'}.issubset({row[0] for row in outputs[1]}))
            self.assertTrue(any(native_id for _text,native_id,kind in outputs[1] if kind=='dialogue'))
            self.assertEqual(hashlib.sha256(script.read_bytes()).hexdigest(),digest)

    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official pinned RenPy8.5.3 SDK absent; native acceptance not run')
    def test_native_sdk_generates_identity_for_rpa_source_without_modifying_archive(self):
        from tests.unit.test_renpy_archive import write_rpa
        from vntext.renpy_archive import RenPyArchive
        sdk=validate_sdk(SDK)
        with tempfile.TemporaryDirectory(prefix='native-rpa-') as temp:
            root=Path(temp);source=root/'source';(source/'game').mkdir(parents=True)
            archive=source/'game/scripts.rpa';script=b'label start:\n    e "Archive line"\n'
            write_rpa(archive,{'game/script.rpy':script});before=RenPyArchive(archive).container_sha256
            workspace=root/'workspace';inventory=copy_template_workspace(source,workspace,translation_only=True)
            run=generate_empty_vietnamese_template(sdk,workspace)
            main,review,_stats=extract_native_template_entries(source,workspace/'game/tl/vietnamese',archive_sources=inventory['archive_sources'])
            print(json.dumps({'command':run.args,'stdout':run.stdout,'stderr':run.stderr,'exit_code':run.returncode,'inventory':inventory},ensure_ascii=True))
            self.assertEqual(run.returncode,0)
            self.assertEqual(review,[])
            self.assertEqual([entry.source_text for entry in main],['Archive line'])
            self.assertEqual(main[0].native_contract['precondition']['source_sha256'],hashlib.sha256(script).hexdigest())
            self.assertEqual(RenPyArchive(archive).container_sha256,before)

    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official pinned RenPy8.5.3 SDK absent; native acceptance not run')
    def test_compiled_only_sdk_translate_has_no_native_identity_readback(self):
        sdk=validate_sdk(SDK)
        with tempfile.TemporaryDirectory(prefix='compiled-sdk-') as temp:
            root=Path(temp);game=root/'game';game.mkdir()
            script=game/'script.rpy'
            script.write_text('define e = Character("Eileen")\nlabel start:\n    e "Compiled line"\n    return\n',encoding='utf-8')
            compile_command=[str(sdk.python),str(sdk.renpy_py),str(root),'compile']
            compiled=subprocess.run(compile_command,cwd=sdk.root,text=True,capture_output=True,timeout=120)
            rpyc=script.with_suffix('.rpyc')
            self.assertEqual(compiled.returncode,0,compiled.stdout+'\n'+compiled.stderr)
            self.assertTrue(rpyc.is_file())
            script.unlink()
            run=generate_empty_vietnamese_template(sdk,root)
            units=parse_renpy_translation_templates(root/'game/tl/vietnamese',language='vietnamese')
            matching=[unit for unit in units if unit.source_text=='Compiled line']
            game_units=[unit for unit in units if unit.source_file.replace('\\','/').startswith('game/')]
            print(json.dumps({'compile_command':compile_command,'compile_exit_code':compiled.returncode,'compiled_sha256':hashlib.sha256(rpyc.read_bytes()).hexdigest(),'translation_command':run.args,'translation_exit_code':run.returncode,'game_units':len(game_units),'compiled_dialogue_identity_readback':[(unit.source_text,unit.native_id) for unit in game_units if unit.unit_kind=='dialogue']},ensure_ascii=True))
            self.assertEqual(run.returncode,0)
            self.assertEqual(matching,[])
