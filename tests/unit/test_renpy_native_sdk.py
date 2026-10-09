"""Native SDK tests use only generated source; missing SDK is an explicit skip."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from vntext.renpy_toolchain import validate_sdk, copy_template_workspace, generate_empty_vietnamese_template
from vntext.renpy_extract import parse_renpy_translation_templates

SDK = Path(os.environ.get('VNTEXT_RENPY_NATIVE_SDK',str(Path(__file__).resolve().parents[2]/'.dev-env/tools/renpy-8.5.3')))

class NativeRenPySdkTests(unittest.TestCase):
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
