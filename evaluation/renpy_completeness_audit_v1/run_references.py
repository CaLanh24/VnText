"""External tools run only against generated audit fixtures, never user games."""
from pathlib import Path
import sys,json,hashlib,urllib.request,subprocess,importlib.util
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tests.lib.work_paths import work_temp_dir
from vntext.renpy_toolchain import validate_sdk,generate_empty_vietnamese_template
OUT=Path(__file__).parent;work=work_temp_dir('renpy-reference-audit')
gt=json.loads((OUT/'ground_truth.json').read_text(encoding='utf-8'))
result={'tools':{},'comparative':{}}
def download(repo,commit,path,target):
    data=urllib.request.urlopen(f'https://raw.githubusercontent.com/{repo}/{commit}/{path}',timeout=30).read()
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    return {'url':f'https://github.com/{repo}/blob/{commit}/{path}','sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
repo='yschdxm/renpy-translator';commit='4cbb00cee29c73a66437cc0828ba0a88bcb40873'
parser=work/'independent/renpy_parser.py'
result['tools']['independent']={'source':download(repo,commit,'src/renpy_parser.py',parser),'license':download(repo,commit,'LICENSE',parser.parent/'LICENSE')}
spec=importlib.util.spec_from_file_location('audit_reference_parser',parser);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
for name,c in gt.items():
    p=work/'fixtures'/name/'game/script.rpy';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(c['script'],encoding='utf-8')
    r=m.RenpyParser().parse_file(str(p),extract_ui=True)
    result['comparative'][name]={'dialogue':[x.__dict__ for x in r.get('dialogues',[])],'ui':[x.__dict__ for x in r.get('ui_texts',[])],'keys':list(r)}

repo='CensoredUsername/unrpyc';commit='3ae8334ed71a05535927dcc559663d3aca51215b';tool=work/'unrpyc'
tree=json.load(urllib.request.urlopen(f'https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1',timeout=30))
files=[x['path']for x in tree['tree']if x['type']=='blob' and (x['path']in ['unrpyc.py','deobfuscate.py','LICENSE']or x['path'].startswith('decompiler/')and x['path'].endswith('.py'))]
result['tools']['unrpyc']={'files':[download(repo,commit,p,tool/p)for p in files]}
sdk=validate_sdk(ROOT/'.dev-env/tools/renpy-8.5.3')
source=work/'fixtures/basic';generate_empty_vietnamese_template(sdk,source)
p=source/'game/script.rpy';p.rename(p.with_suffix('.original'))
command=[sys.executable,'-B',str(tool/'unrpyc.py'),str(p.with_suffix('.rpyc'))]
r=subprocess.run(command,text=True,encoding='utf-8',capture_output=True,timeout=60)
result['unrpyc']={'command':command,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'recovered':p.read_text(encoding='utf-8')if p.exists()else None}

repo='Shizmob/rpatool';commit='74f26d5dfdd645483e02552aa766ca447ad6b191';path=work/'rpatool.py'
result['tools']['rpatool']={'source':download(repo,commit,'rpatool',path),'license':download(repo,commit,'LICENSE',work/'rpatool-LICENSE')}
# Use the independent tool to CREATE archives, then compare VNText read bytes.
spec=importlib.util.spec_from_file_location('audit_rpatool',path);rp=importlib.util.module_from_spec(spec);spec.loader.exec_module(rp)
from vntext.renpy_archive import RenPyArchive
result['rpa']={}
for version in [2,3,3.2]:
    archive=rp.RenPyArchive(version=version);content=gt['basic']['script'].encode()
    archive.files={'nested/script.rpy':content,'other/path.rpy':b'label other:\n    "Second archive member"\n'}
    target=work/f'ref-{version}.rpa'
    try:
        archive.save(str(target))
        rr=RenPyArchive(target)
        result['rpa'][str(version)]={'members':list(rr.members),'exact_bytes':rr.read_member('nested/script.rpy')['content']==content}
    except Exception as e:result['rpa'][str(version)]={'error':repr(e)}
(OUT/'references.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'unrpyc_exit':result['unrpyc']['exit'],'recovered':bool(result['unrpyc']['recovered']),'rpa':result['rpa'],'independent_keys':result['comparative']['basic']['keys']}))
