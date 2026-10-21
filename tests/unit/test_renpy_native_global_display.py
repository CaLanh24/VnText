"""Native SDK oracle for existing global-string writer, not discovery claims."""
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


class NativeGlobalDisplayTests(unittest.TestCase):
    @unittest.skipUnless((SDK/'renpy.py').is_file(),'Official SDK8.5.3 absent')
    def test_global_writer_translates_displayed_literals_in_loose_and_compiled_games(self):
        sdk=validate_sdk(SDK)
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-global-display'))as tmp:
            root=Path(tmp);source=root/'source';(source/'game').mkdir(parents=True)
            script=source/'game/script.rpy'
            script.write_text('label start:\n    menu:\n        "Menu option":\n            pass\n    $ label = _("Localized setting")\n    return\nscreen native_ui():\n    text "Plain label"\n    textbutton "Plain button" action NullAction() tooltip "Plain tip"\n',encoding='utf-8')
            result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(source),'compile'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            strings=['Plain label','Plain button','Plain tip','Menu option','Localized setting']
            for kind in ('loose','compiled','archive'):
                compiled=kind!='loose'
                for patched in (False,True):
                    lookup=root/'lookup';(lookup/'game').mkdir(parents=True)
                    suffix='.rpyc'if compiled else '.rpy'
                    if kind=='archive':write_rpa(lookup/'game/archive.rpa',{'script.rpyc':script.with_suffix('.rpyc').read_bytes()})
                    else:shutil.copy2(script.with_suffix(suffix),lookup/('game/script'+suffix))
                    original_files={path:path.read_bytes()for path in (lookup/'game').iterdir()if path.is_file()}
                    if patched:
                        package=root/(kind+'-package');events=[]
                        run_extract_task(str(lookup),str(package),'safe','balanced',True,renpy_sdk_path=str(SDK),renpy_sdk_action='existing',progress=lambda _:None,log=lambda _:None,complete=events.append)
                        self.assertTrue(events[-1].get('ok'),events[-1])
                        fields,rows=read_csv_rows_file(package/'translation.csv')
                        self.assertEqual({r['source_text']for r in rows},set(strings))
                        for row in rows:row['translation']='VI '+row['source_text']
                        write_csv_rows_file(package/'translation.csv',fields,rows)
                        patch=root/(kind+'-patch')
                        apply_translation_package(str(package/'translation.csv'),str(package/'manifest.json'),str(lookup),str(patch))
                        shutil.copytree(patch/'COPY_TO_GAME_ROOT',lookup,dirs_exist_ok=True)
                        repeated=root/(kind+'-repeat');events=[]
                        run_extract_task(str(lookup),str(repeated),'safe','balanced',True,renpy_sdk_path=str(SDK),renpy_sdk_action='existing',progress=lambda _:None,log=lambda _:None,complete=events.append)
                        self.assertTrue(events[-1].get('ok'),events[-1])
                        original_manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8'))
                        repeat_manifest=json.loads((repeated/'manifest.json').read_text(encoding='utf-8'))
                        identity=lambda m:sorted((e['key'],e['source_text'],e['file_path'],e['import_method'],e['locator'])for e in m['entries'])
                        self.assertEqual(identity(original_manifest),identity(repeat_manifest))
                        fields,rows=read_csv_rows_file(repeated/'translation.csv')
                        for row in rows:row['translation']='VI '+row['source_text']
                        write_csv_rows_file(repeated/'translation.csv',fields,rows)
                        repatch=root/(kind+'-repatch')
                        apply_translation_package(str(repeated/'translation.csv'),str(repeated/'manifest.json'),str(lookup),str(repatch))
                        shutil.copytree(repatch/'COPY_TO_GAME_ROOT',lookup,dirs_exist_ok=True)
                    probe='''init 1000 python:
    import json, os
    renpy.game.preferences.language="vietnamese"
    text=renpy.text.text.Text
    button=renpy.ui._textbutton("Plain button",tooltip="Plain tip",style="button",text_style="button_text")
    menu=next(node for node in renpy.game.script.namemap.values() if isinstance(node,renpy.ast.Menu))
    result={"text":text("Plain label").text,"button":button._main.text,
        "tooltip_raw":button._get_tooltip(),"tooltip_display":text(button._get_tooltip()).text,
        "menu_display":text(menu.items[0][0]).text,
        "localization_raw":renpy.store._("Localized setting"),
        "localization_display":text(renpy.store._("Localized setting")).text,
        "substitute_false":text("Plain label",substitute=False).text}
    with open(os.path.join(config.basedir,"readback.json"),"w",encoding="utf-8") as output:
        json.dump(result,output,ensure_ascii=False)
'''
                    (lookup/'game/probe.rpy').write_text(probe,encoding='utf-8')
                    result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(lookup),'lint'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
                    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                    readback=lookup/'readback.json'
                    self.assertTrue(readback.is_file(),result.stdout+result.stderr+'\n'+'\n'.join(path.read_text(encoding='utf-8',errors='replace')[:6000]for path in lookup.glob('*.txt')))
                    rb=json.loads(readback.read_text(encoding='utf-8'));prefix='VI 'if patched else ''
                    for field,text in [('text','Plain label'),('button','Plain button'),('tooltip_display','Plain tip'),('menu_display','Menu option'),('localization_display','Localized setting')]:
                        self.assertEqual(rb[field],[prefix+text],rb)
                    self.assertEqual(rb['tooltip_raw'],'Plain tip');self.assertEqual(rb['localization_raw'],'Localized setting')
                    self.assertEqual(rb['substitute_false'],['Plain label'])
                    self.assertTrue(all(path.read_bytes()==raw for path,raw in original_files.items()))
                    print('NATIVE_DISPLAY',kind,patched,json.dumps(rb,ensure_ascii=False))
                    shutil.rmtree(lookup)
