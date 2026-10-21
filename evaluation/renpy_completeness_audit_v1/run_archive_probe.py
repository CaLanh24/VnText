"""Targeted confirmation of standard archive member roots, using official loader."""
from pathlib import Path
import sys,json,pickle,zlib,subprocess
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tests.lib.work_paths import work_temp_dir
from vntext.renpy_toolchain import validate_sdk,generate_empty_vietnamese_template,copy_template_workspace
from vntext.app_tasks import run_extract_task
from vntext.package_io import read_csv_rows_file
OUT=Path(__file__).parent;work=work_temp_dir('renpy-archive-probe');sdk=validate_sdk(ROOT/'.dev-env/tools/renpy-8.5.3')
def rpa(path,members):
    header=b'RPA-3.0 0000000000000000 00000000\n';data=bytearray(header);index={}
    for name,content in members.items():
        index[name]=[(len(data),len(content),b'')];data.extend(content)
    offset=len(data);data.extend(zlib.compress(pickle.dumps(index,protocol=5)));data[:len(header)]=f'RPA-3.0 {offset:016x} 00000000\n'.encode();path.write_bytes(data)
script=b'label archive_only:\n    "Archive standard-root dialogue"\n    return\n'
result={}
for prefix in ['', 'game/']:
    name='standard'if not prefix else 'prefixed';src=work/name/'source';(src/'game').mkdir(parents=True)
    member=prefix+'nested/script.rpy';rpa(src/'game/scripts.rpa',{member:script})
    ws=work/name/'workspace';inv=copy_template_workspace(src,ws,translation_only=True)
    events=[];logs=[];package=work/name/'package'
    run_extract_task(str(src),str(package),'safe','balanced',True,renpy_sdk_path=str(sdk.root),renpy_sdk_action='existing',progress=lambda x:None,log=logs.append,complete=events.append)
    result[name]={'member':member,'workspace_inventory':inv,'events':events,'rows':read_csv_rows_file(package/'translation.csv')[1]if(package/'translation.csv').exists()else[]}
    # Official Ren'Py loads the archive member verbatim under this standard name.
    (src/'game/probe.rpy').write_text('init python:\n    import json, os\n    with open(os.path.join(config.basedir, "loader-readback.json"), "w") as receipt:\n        json.dump({"loadable": renpy.loadable("'+member+'"), "content": renpy.file("'+member+'").read().decode("utf-8")}, receipt)\n',encoding='utf-8')
    cmd=[str(sdk.python),str(sdk.renpy_py),str(src),'lint'];p=subprocess.run(cmd,cwd=sdk.root,text=True,encoding='utf-8',capture_output=True,timeout=60)
    result[name]['official_loader']={'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'readback':json.loads((src/'loader-readback.json').read_text())if(src/'loader-readback.json').exists()else None}
(OUT/'archive-probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:{'rows':len(v['rows']),'loader':v['official_loader']['readback']}for k,v in result.items()}))
