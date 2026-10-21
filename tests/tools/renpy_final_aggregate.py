"""Read immutable canonical groundtruth; write a separate final aggregate."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tests.lib.work_paths import work_temp_dir
from tests.unit.test_renpy_archive import write_rpa,write_rpa2
from vntext.app_tasks import run_extract_task
from vntext.package_io import read_csv_rows_file,write_csv_rows_file
from vntext.patch_pipeline import apply_translation_package
from vntext.patchability import assess_entry
from vntext.renpy_toolchain import validate_sdk

GT=ROOT/'evaluation/renpy_completeness_audit_v1/ground_truth.json'
LOCK='39e9a61a37d47f660ba8a3ebea244a423a99daae5353373821be2cd89a953491'
def digest(data):return hashlib.sha256(data).hexdigest()
def extract(game,package,sdk):
    events=[];logs=[]
    run_extract_task(str(game),str(package),'safe','balanced',True,renpy_sdk_path=str(sdk.root),renpy_sdk_action='existing',progress=lambda _:None,log=logs.append,complete=events.append)
    manifest=json.loads((package/'manifest.json').read_text(encoding='utf-8'))if(package/'manifest.json').is_file()else {'entries':[]}
    return events[-1],manifest,logs
def identity(manifest):
    return sorted((e['key'],e['source_text'],e['file_path'],e['context'],e.get('object_info'),e['import_method'],json.dumps(e['locator'],sort_keys=True))for e in manifest['entries'])
def tree(game):return {p.relative_to(game).as_posix():digest(p.read_bytes())for p in game.rglob('*')if p.is_file()}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    raw=GT.read_bytes();assert digest(raw)==LOCK
    truth=json.loads(raw);sdk=validate_sdk(ROOT/'.dev-env/tools/renpy-8.5.3')
    report={'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'ground_truth_sha256':LOCK,'baseline':{'recall':[15,19],'precision':[15,16]},
        'precision_qualification':'Locked negative policy; visible path-shaped label disputed, not a confirmed classifier bug',
        'cases':{},'containers':{},'misses':[],'false_positives':[]}
    numerator=denominator=patchable=emitted=0
    with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-final-aggregate'))as temporary:
        work=Path(temporary)
        for name,case in truth.items():
            base=work/name;game=base/'source';(game/'game').mkdir(parents=True)
            (game/'game/script.rpy').write_text(case['script'],encoding='utf-8');original=tree(game)
            event,manifest,logs=extract(game,base/'package',sdk)
            entries=manifest['entries'];record={'script_sha256':digest(case['script'].encode()),'event':event,'logs':logs,'entries':entries,'inventory_delta':[]}
            positive_sources={e['text']for e in case['expectations']if e['occurrences']>0}
            for expected in case['expectations']:
                count=expected['occurrences']
                if count<=0:continue
                dialogue=expected['category']in {'DIALOGUE','NARRATION'}
                wanted=count if dialogue else 1
                matching=[e for e in entries if e['source_text']==expected['text']and e['import_method']==('renpy_dialogue'if dialogue else 'renpy_string')]
                found=len(matching)if dialogue else int(bool(matching))
                admitted=sum(assess_entry(e).status=='SUPPORTED_AND_PATCHABLE'for e in matching)if dialogue else int(any(assess_entry(e).status=='SUPPORTED_AND_PATCHABLE'for e in matching))
                denominator+=wanted;numerator+=min(wanted,found);patchable+=min(wanted,admitted)
                row={'text':expected['text'],'category':expected['category'],'expected':wanted,'found':found,'patchable':admitted,
                     'locations':[{'key':e['key'],'file':e['file_path'],'context':e['context'],'locator':e['locator']}for e in matching]}
                record['inventory_delta'].append(row)
                if found<wanted:report['misses'].append({'case':name,**row})
            for entry in entries:
                if entry['source_text']not in positive_sources:
                    report['false_positives'].append({'case':name,'text':entry['source_text'],'key':entry['key'],
                        'qualification':'POLICY_DISPUTED'if entry['source_text']=='images/bg.png'else 'UNEXPECTED_OR_CONDITIONAL'})
            emitted+=len(entries)
            try:
                assert event.get('ok'),event
                fields,rows=read_csv_rows_file(base/'package/translation.csv')
                for row in rows:row['translation']='VI '+row['source_text']
                write_csv_rows_file(base/'package/translation.csv',fields,rows)
                apply_translation_package(str(base/'package/translation.csv'),str(base/'package/manifest.json'),str(game),str(base/'patch'))
                assert tree(game)==original
                shutil.copytree(base/'patch/COPY_TO_GAME_ROOT',game,dirs_exist_ok=True);before=tree(game)
                repeated,replay,_=extract(game,base/'repeat',sdk)
                assert repeated.get('ok'),repeated
                assert identity(manifest)==identity(replay)
                assert before==tree(game)
                fields,rows=read_csv_rows_file(base/'repeat/translation.csv')
                for row in rows:row['translation']='VI '+row['source_text']
                write_csv_rows_file(base/'repeat/translation.csv',fields,rows)
                apply_translation_package(str(base/'repeat/translation.csv'),str(base/'repeat/manifest.json'),str(game),str(base/'repatch'))
                assert before==tree(game)
                record['roundtrip']='PASS_IDENTITY_SOURCE_PRESERVATION_REPATCH'
            except Exception as error:record['roundtrip']='FAIL';record['roundtrip_error']=repr(error)
            report['cases'][name]=record
            shutil.rmtree(base)
        # Original container probes retained separately; do not pad denominator19.
        for name,writer in [('rpa2',write_rpa2),('rpa3',write_rpa)]:
            base=work/name;game=base/'source';(game/'game').mkdir(parents=True)
            writer(game/'game/scripts.rpa',{'nested/script.rpy':truth['basic']['script'].encode()})
            writer(game/'game/extra.rpa',{'extras/other.rpy':b'label other:\n    "Archive second file"\n    return\n'})
            before=tree(game);event,manifest,_=extract(game,base/'package',sdk)
            report['containers'][name]={'event':event,'entries':manifest['entries'],'source_unchanged':tree(game)==before,
                'runtime_execution':'NOT_PROVEN_RPY_ONLY_ARCHIVE','eligibility':'SOURCE_DISCOVERY_ONLY_PARTIAL'}
            shutil.rmtree(base)
        base=work/'compiled';game=base/'source';(game/'game').mkdir(parents=True)
        script=game/'game/script.rpy';script.write_text(truth['basic']['script'],encoding='utf-8')
        compile_result=subprocess.run([str(sdk.python),str(sdk.renpy_py),str(game),'compile'],cwd=sdk.root,capture_output=True,text=True,encoding='utf-8',timeout=60)
        assert compile_result.returncode==0,compile_result.stdout+compile_result.stderr
        script.unlink();before=tree(game);event,manifest,_=extract(game,base/'package',sdk)
        report['containers']['compiled']={'event':event,'entries':manifest['entries'],'source_unchanged':tree(game)==before,
            'unresolved':manifest.get('stats',{}).get('errors',[]),'eligibility':'TYPED_SUPPORTED_SLOTS_ONLY; UNKNOWN_AST_PARTIAL'}
    assert digest(GT.read_bytes())==LOCK
    assert denominator==19
    report['recall']={'numerator':numerator,'denominator':denominator}
    report['precision']={'numerator':numerator,'denominator':emitted}
    report['patchable_recall']={'numerator':patchable,'denominator':denominator,'eligibility':'Frozen19 expected static/native mapping units; schema/preflight proof admission, not whole-game runtime acceptance'}
    report['aggregate_status']='PASS'if numerator==19 and all(r['roundtrip']!='FAIL'for r in report['cases'].values())else 'GAPS_REMAIN'
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k]for k in ('source_sha','recall','precision','patchable_recall','aggregate_status','misses','false_positives')},ensure_ascii=False))
    return 0 if report['aggregate_status']=='PASS'else 1

if __name__=='__main__':raise SystemExit(main())
