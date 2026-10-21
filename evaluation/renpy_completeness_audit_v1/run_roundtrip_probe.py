"""Official native lookup readback of the patch generated in the audit."""
from pathlib import Path
import sys,json,shutil,subprocess,hashlib
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tests.lib.work_paths import work_temp_dir
from vntext.renpy_toolchain import validate_sdk
from vntext.app_tasks import run_extract_task
from vntext.package_io import read_csv_rows_file,write_csv_rows_file
from vntext.patch_pipeline import apply_translation_package
OUT=Path(__file__).parent;work=work_temp_dir('renpy-roundtrip-probe');sdk=validate_sdk(ROOT/'.dev-env/tools/renpy-8.5.3')
gt=json.loads((OUT/'ground_truth.json').read_text(encoding='utf-8'));source=work/'source';(source/'game').mkdir(parents=True)
p=source/'game/script.rpy';p.write_text(gt['basic']['script'],encoding='utf-8');digest=hashlib.sha256(p.read_bytes()).hexdigest();events=[]
pkg=work/'package';run_extract_task(str(source),str(pkg),'safe','balanced',True,renpy_sdk_path=str(sdk.root),renpy_sdk_action='existing',progress=lambda x:None,log=lambda x:None,complete=events.append)
fields,rows=read_csv_rows_file(pkg/'translation.csv')
for row in rows:row['translation']='VI '+row['source_text']
write_csv_rows_file(pkg/'translation.csv',fields,rows)
manifest=json.loads((pkg/'manifest.json').read_text(encoding='utf-8'))
patch=work/'patch';apply_translation_package(str(pkg/'translation.csv'),str(pkg/'manifest.json'),str(source),str(patch))
shutil.copytree(patch/'COPY_TO_GAME_ROOT',source,dirs_exist_ok=True)
expected={e['locator']['native_id']:'VI '+e['source_text']for e in manifest['entries']if e['import_method']=='renpy_dialogue'}
strings={e['source_text']:'VI '+e['source_text']for e in manifest['entries']if e['import_method']=='renpy_string'}
probe='init 1000 python:\n    import json, os\n    renpy.game.preferences.language = "vietnamese"\n    out = {"dialogue": {}, "strings": {}}\n'
for key in expected:probe+=f'    node, translated = renpy.game.script.translator.lookup_translate({key!r})\n    out["dialogue"][{key!r}] = {{"text": node.what, "translated": translated}}\n'
for text in strings:probe+=f'    out["strings"][{text!r}] = renpy.translate_string({text!r}, language="vietnamese")\n'
probe+='    with open(os.path.join(config.basedir, "readback.json"), "w", encoding="utf-8") as receipt:\n        json.dump(out, receipt, ensure_ascii=False)\n'
(source/'game/readback.rpy').write_text(probe,encoding='utf-8')
cmd=[str(sdk.python),str(sdk.renpy_py),str(source),'lint'];r=subprocess.run(cmd,cwd=sdk.root,text=True,encoding='utf-8',capture_output=True,timeout=60)
rb=json.loads((source/'readback.json').read_text(encoding='utf-8'))if(source/'readback.json').exists()else{}
result={'command':cmd,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'readback':rb,'expected_dialogue':expected,'expected_strings':strings,'original_script_unchanged':hashlib.sha256(p.read_bytes()).hexdigest()==digest}
result['mapping_pass']=all(rb.get('dialogue',{}).get(k)=={'text':v,'translated':True}for k,v in expected.items())and rb.get('strings')==strings
(OUT/'native-readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'exit':r.returncode,'mapping_pass':result['mapping_pass'],'dialogues':len(expected),'strings':len(strings)}))
