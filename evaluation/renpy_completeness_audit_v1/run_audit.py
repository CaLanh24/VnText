"""Investigation only. Generated fixtures, no production modifications."""
from pathlib import Path
import sys, os, json, hashlib, subprocess, shutil, pickle, zlib, urllib.request
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests.lib.work_paths import work_temp_dir
from vntext.renpy_toolchain import validate_sdk, copy_template_workspace, generate_empty_vietnamese_template
from vntext.renpy_extract import parse_renpy_translation_templates, extract_native_template_entries
from vntext.app_tasks import run_extract_task
from vntext.package_io import read_csv_rows_file, write_csv_rows_file
from vntext.patch_pipeline import apply_translation_package

OUT = Path(__file__).parent
def save(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
def sha(data): return hashlib.sha256(data).hexdigest()
def req(url): return urllib.request.urlopen(url, timeout=30).read()

# These expectations are frozen to disk BEFORE invoking any extractor/oracle.
CASES = {
 'basic': ('define e = Character("Eileen")\ndefine f = Character("Frank")\ndefault name = "Player"\nlabel start:\n    e "Hello [name]! {b}Bold{/b} {i}italic{/i} {color=#ff0000}red{/color}{w}{p}"\n    "Narrator: bracket [[ literal. 日本語"\n    e "Repeated dialogue"\n    e "Repeated dialogue"\n    f "Repeated dialogue"\n    e "Escaped \\"quote\\" and [name.upper()]"\n    menu:\n        "First choice":\n            menu:\n                "Nested choice":\n                    pass\n    $ local = _("Localized setting")\n    $ internal = "INTERNAL_KEY_001"\n    $ path = "images/bg.png"\n    $ variable_name = "player_health"\n    $ dynamic = "Generated " + name\n    return\nscreen audit_ui():\n    text "Plain screen label"\n    textbutton "Plain button label" action NullAction()\n    textbutton _("Wrapped button label") action NullAction() tooltip _("Helpful tooltip")\n    text _("Shared UI text")\n    text _("Shared UI text")\n    text _("images/bg.png")\n    text _("   ")\n', [
  ('Hello [name]! {b}Bold{/b} {i}italic{/i} {color=#ff0000}red{/color}{w}{p}', 'DIALOGUE', 1),
  ('Narrator: bracket [[ literal. 日本語','NARRATION',1),('Repeated dialogue','DIALOGUE',3),
  ('Escaped "quote" and [name.upper()]','DIALOGUE',1),('First choice','MENU_CHOICE',1),('Nested choice','MENU_CHOICE',1),
  ('Localized setting','LOCALIZATION_STRING',1),('Plain screen label','SCREEN_UI',1),('Plain button label','SCREEN_UI',1),
  ('Wrapped button label','SCREEN_UI',1),('Helpful tooltip','SCREEN_UI',1),('Shared UI text','SCREEN_UI',2),
  ('images/bg.png','PATH_OR_FILENAME',0),('INTERNAL_KEY_001','INTERNAL_KEY',0),('player_health','VARIABLE_OR_IDENTIFIER',0),
  ('Generated ','RUNTIME_GENERATED',-1),('   ','TECHNICAL_STRING',0)]),
 'multiline': ('define e = Character("Eileen")\nlabel start:\n    e """First multiline\n    second multiline"""\n    return\n', [('First multiline second multiline','DIALOGUE',1)]),
 'single_quote': ("define e = Character('Eileen')\nlabel start:\n    e 'Single quoted dialogue'\n    return\n", [('Single quoted dialogue','DIALOGUE',1)]),
 'speaker_literal': ('label start:\n    "Guide" "Literal speaker dialogue"\n    return\n', [('Literal speaker dialogue','DIALOGUE',1)]),
 'say_suffix': ('define e = Character("Eileen")\nlabel start:\n    e "Timed dialogue" with dissolve\n    return\n', [('Timed dialogue','DIALOGUE',1)]),
 'old_new': ('label start:\n    "Original dialogue"\n    return\ntranslate None strings:\n\n    old "Original localized"\n    new "Existing localized"\n', [('Original dialogue','DIALOGUE',1),('Original localized','LOCALIZATION_STRING',-1),('Existing localized','LOCALIZATION_STRING',-1)]),
}
save('ground_truth.json', {k:{'script':s,'expectations':[dict(text=t,category=c,occurrences=n,decision='SHOULD_EXTRACT' if n>0 else 'SHOULD_NOT_EXTRACT' if n==0 else 'CONDITIONAL_RUNTIME_ONLY',patchability='EXPECTED_STATIC_MAPPING' if n>0 else 'NOT_REQUIRED',location='game/script.rpy',context='start or audit_ui; inspect line records')for t,c,n in exp]}for k,(s,exp)in CASES.items()})
locked = sha((OUT/'ground_truth.json').read_bytes())
work = work_temp_dir('renpy-completeness-audit')
sdk = validate_sdk(ROOT/'.dev-env/tools/renpy-8.5.3')
result={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'ground_truth_sha256':locked,'cases':{},'references':{}}
if (OUT/'results.json').exists():
    result=json.loads((OUT/'results.json').read_text(encoding='utf-8'))
    assert result['ground_truth_sha256']==locked

def product(source, package):
    events=[];logs=[]
    run_extract_task(str(source),str(package),'safe','balanced',True,renpy_sdk_path=str(sdk.root),renpy_sdk_action='existing',progress=lambda x:None,log=logs.append,complete=events.append)
    rows=[]; manifest={}
    if (package/'translation.csv').exists():
        _,rows=read_csv_rows_file(package/'translation.csv')
        manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8-sig'))
    return dict(events=events,logs=logs,rows=rows,entries=manifest.get('entries',[]))

for name,(script,exp) in CASES.items():
    if name in result['cases'] and name != 'basic': continue
    base=work/name;src=base/'source';(src/'game').mkdir(parents=True)
    (src/'game/script.rpy').write_text(script,encoding='utf-8')
    rec={'script_sha256':sha(script.encode()),'ground_truth':exp}
    workspace=base/'oracle'
    try:
        copy_template_workspace(src,workspace,translation_only=True)
        run=generate_empty_vietnamese_template(sdk,workspace)
        templates={p.relative_to(workspace).as_posix():p.read_text(encoding='utf-8')for p in (workspace/'game/tl/vietnamese').rglob('*.rpy')}
        rec['official']={'exit':run.returncode,'templates':{k:v for k,v in templates.items()if k.endswith('/script.rpy')},'stdout':run.stdout,'stderr':run.stderr}
        try:
            units=parse_renpy_translation_templates(workspace/'game/tl/vietnamese')
            rec['native_units']=[u.__dict__ for u in units if u.source_file=='game/script.rpy']
        except Exception as e: rec['native_parse_error']=repr(e)
    except Exception as e: rec['oracle_error']=repr(e)
    rec['product']=product(src,base/'package')
    result['cases'][name]=rec
    save('results.json',result)

# The identical frozen basic script, container-only, nested member names, RPA2 and RPA3.
def archive(path, members,version):
    header=(b'RPA-2.0 0000000000000000\n' if version==2 else b'RPA-3.0 0000000000000000 00000000\n')
    data=bytearray(header);index={};key=0x12345678
    for name,content in members.items():
        offset=len(data);data.extend(content)
        index[name]=[(offset,len(content))]if version==2 else[(offset^key,len(content)^key,b'')]
    offset=len(data);data.extend(zlib.compress(pickle.dumps(index,protocol=2 if version==2 else 5)))
    data[:len(header)]=(f'RPA-2.0 {offset:016x}\n'if version==2 else f'RPA-3.0 {offset:016x} {key:08x}\n').encode()
    path.write_bytes(data)
for version in [2,3]:
    src=work/f'rpa{version}'/'source';(src/'game').mkdir(parents=True)
    archive(src/'game/scripts.rpa',{'nested/script.rpy':CASES['basic'][0].encode()},version)
    archive(src/'game/extra.rpa',{'extras/other.rpy':b'label other:\n    "Archive second file"\n    return\n'},version)
    result[f'rpa{version}']=product(src,src.parent/'package')
    from vntext.renpy_archive import RenPyArchive
    result[f'rpa{version}']['inventory']={p.name:list(RenPyArchive(p).members)for p in (src/'game').glob('*.rpa')}
    save('results.json',result)

# Actual SDK compiled bytes; no forged pickle oracle.
compiled=work/'compiled'/'source';(compiled/'game').mkdir(parents=True)
for p in (work/'basic/oracle/game').glob('*.rpyc'): shutil.copyfile(p,compiled/'game'/p.name)
result['compiled']=product(compiled,compiled.parent/'package')
from vntext.renpy_compiled import compiled_dialogues
result['compiled']['static_ast']={p.name:compiled_dialogues(p.read_bytes())for p in(compiled/'game').glob('*.rpyc')}

# Round trip on current admitted basic rows: synthetic targets preserve tokens verbatim.
base=work/'basic';pkg=base/'package';src=base/'source'
try:
    fields,rows=read_csv_rows_file(pkg/'translation.csv')
    for row in rows:row['translation']='VI '+row['source_text']
    write_csv_rows_file(pkg/'translation.csv',fields,rows)
    patch=base/'patch';apply_translation_package(str(pkg/'translation.csv'),str(pkg/'manifest.json'),str(src),str(patch))
    replay=base/'replay';shutil.copytree(src,replay)
    shutil.copytree(patch/'COPY_TO_GAME_ROOT',replay,dirs_exist_ok=True)
    result['roundtrip']={'overlay':{p.relative_to(patch).as_posix():p.read_text(encoding='utf-8')for p in patch.rglob('*.rpy')},'reextract':product(replay,base/'replay-package')}
except Exception as e:result['roundtrip']={'error':repr(e)}
save('results.json',result)
assert locked==sha((OUT/'ground_truth.json').read_bytes())
print(json.dumps({'cases':{k:{'events':v['product']['events'],'parse_error':v.get('native_parse_error'),'rows':len(v['product']['rows'])}for k,v in result['cases'].items()},'compiled_rows':len(result['compiled']['rows']),'roundtrip_error':result['roundtrip'].get('error'),'work':str(work)},ensure_ascii=True))
