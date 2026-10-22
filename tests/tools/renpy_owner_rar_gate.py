"""Owner local RAR: complete game subtree, native text API, normal Patch."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from tests.lib.work_paths import work_temp_dir
from tests.tools.cleanup_work_artifacts import _project_size_snapshot
from tests.tools.renpy_declared_sample import create_declared_sample
from tests.tools.renpy_owner_rar_preflight import SOURCE,EVIDENCE
from tests.tools.renpy_real_game_gate import identity
from vntext.package_io import write_package
from vntext.patch_pipeline import apply_translation_package
from vntext.patchability import assess_entry
from vntext.renpy_archive import RenPyArchive
from vntext.renpy_extract import extract_native_template_entries
from vntext.renpy_toolchain import validate_sdk,copy_template_workspace,generate_empty_vietnamese_template

ROOT=Path(__file__).resolve().parents[2]
REPORT=EVIDENCE/'renpy-owner-rar-run.json'


def sha(path):
    with path.open('rb')as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(report):REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')


def quota(reserve=0):
    result=_project_size_snapshot()
    if not result['complete']or result['non_exempt_bytes']+reserve>result['limit_bytes']:raise ValueError('measured global quota/reserve unavailable')
    return result


def extract_text(game,output,sdk,work):
    with tempfile.TemporaryDirectory(dir=work)as temporary:
        workspace=Path(temporary)/'script-workspace'
        inventory=copy_template_workspace(game,workspace,translation_only=True)
        generate_empty_vietnamese_template(sdk,workspace)
        main,review,stats=extract_native_template_entries(game,workspace/'game/tl/vietnamese',language='vietnamese',archive_sources=inventory.get('archive_sources'))
        counts=write_package(str(output),main,review,stats,separate_review=True,enforce_symmetry=True,enable_trace=True)
    errors=list(stats.get('errors')or[])
    review_count=sum(counts[k]for k in ('review_only_entries','raw_candidate_entries','raw_unpatchable_entries'))
    accounted=counts['main_entries']+review_count+counts['technical_skipped_entries']+counts['auto_raw_rejected']+int(counts.get('renpy_engine_common_excluded_review_entries',0))-int(stats.get('renpy_non_native_review_entries')or 0)
    if stats.get('native_units')and accounted!=stats['native_units']:errors.append(f'native accounting mismatch: {stats["native_units"]} vs {accounted}')
    status={'status':'PARTIAL'if errors or review_count else 'COMPLETE','complete':not(errors or review_count),
        'scope':'FULL_NATIVE_TEXT_PACKAGE; AUTOMATIC_IMAGE_BATCH_NOT_RUN_QUOTA','errors':errors,'review':review_count,'main':counts['main_entries'],
        'native_units':stats.get('native_units'),'native_accounted':accounted,'workspace_inventory':inventory}
    (output/'extract_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    return json.loads((output/'manifest.json').read_text(encoding='utf-8')),status


def main():
    global REPORT
    parser=argparse.ArgumentParser();parser.add_argument('--stem',default='renpy-owner-rar-run')
    parser.add_argument('--font-profile-vietnamese',action='store_true',help='Authorized disposable VM trial only; default off')
    args=parser.parse_args()
    if not args.stem.replace('-','').isalnum():raise ValueError('invalid evidence stem')
    REPORT=EVIDENCE/(args.stem+'.json')
    if REPORT.exists():raise ValueError('refusing to overwrite prior run receipt')
    preflight=json.loads((EVIDENCE/'renpy-owner-rar-preflight.json').read_text(encoding='utf-8'))
    if preflight['preflight']!='PASS'or sha(SOURCE)!=preflight['source_sha256']:raise ValueError('original archive/preflight drift')
    sdk=validate_sdk(ROOT/'.dev-env/tools/renpy-8.5.3')
    report={'outcome':'RUN_STARTED','source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'preflight':preflight,'route':'PRODUCTION_NATIVE_TEXT_API_ONLY; IMAGE_BATCH_NOT_RUN_QUOTA',
        'selection_rule':'Before Patch: first2 proof-admitted dialogue by sourcefile/line/key; Start/Preferences/Save/Load strings, max6; neutral UI/dialogue only',
        'runtime':{'expected_executable':str(sdk.python),'version':sdk.version,'bundled_original_version':'8.3.7.25031702','qualification':'existingSDK; original bundled runtime not executed'}}
    save(report)
    try:
        with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-owner-rar'))as temporary:
            work=Path(temporary);game=work/'game-copy';game.mkdir()
            report['before_copy_quota']=quota(int(preflight['game_bytes'])+preflight['scripts_bytes']+16*1024*1024);save(report)
            subprocess.run(['tar','-xf',str(SOURCE),'-C',str(game),'--strip-components','2','Cucked by My Wife/FTWorlds-1.0-pc/game'],check=True,timeout=120,capture_output=True)
            expected=json.loads((EVIDENCE/'renpy-owner-rar-inventory.json').read_text(encoding='utf-8-sig'))['inventory']
            wanted={r['path'].split('FTWorlds-1.0-pc/',1)[1]:r['bytes']for r in expected if '/game/'in r['path']and r['mode'][0]=='-'}
            actual={p.relative_to(game).as_posix():p.stat().st_size for p in game.rglob('*')if p.is_file()}
            if actual!=wanted:raise ValueError('complete game subtree inventory mismatch')
            if any(p.is_symlink()or getattr(p.lstat(),'st_file_attributes',0)&0x400 for p in game.rglob('*')):raise ValueError('extracted reparse/link')
            original={p.relative_to(game).as_posix():sha(p)for p in game.rglob('*')if p.is_file()}
            report['original_inventory']=original;report['copy_complete']=True
            archive=RenPyArchive(game/'game/archive.rpa')
            if archive.container_sha256!=preflight['rpa_sha256']:raise ValueError('RPA streamed identity drift')
            report['after_copy_quota']=quota(preflight['scripts_bytes']+16*1024*1024);save(report)
            manifest,status=extract_text(game,work/'full-package',sdk,work)
            report.update(full_status=status,stats=manifest['stats'],entry_count=len(manifest['entries']))
            report['full_review_entries']=[e for e in manifest['entries']if e.get('review_only')]
            dialogue=sorted((e for e in manifest['entries']if e['import_method']=='renpy_dialogue'and assess_entry(e).eligible),key=lambda e:(e['file_path'],e.get('native_contract',{}).get('provenance',{}).get('source_line',0),e['key']))[:2]
            sample=list(dialogue)
            for text in ('Start','Preferences','Save','Load'):
                row=next((e for e in manifest['entries']if e['import_method']=='renpy_string'and e['source_text']==text and assess_entry(e).eligible),None)
                if row:sample.append(row)
            report['frozen_selected_entries']=sample
            report['sample_waiting']=True;report['after_extract_quota']=quota(8*1024*1024);save(report)
            translations_path=EVIDENCE/(args.stem+'-translations.json');deadline=time.monotonic()+180
            while not translations_path.exists()and time.monotonic()<deadline:time.sleep(1)
            pairs=json.loads(translations_path.read_text(encoding='utf-8'))
            if set(p['key']for p in pairs)!={e['key']for e in sample}:raise ValueError('pairs do not match frozen sample')
            report['reviewed_pairs']=pairs;report['sample_waiting']=False
            report['declared_sample_provenance']=create_declared_sample(work/'full-package',work/'sample',pairs)
            apply_translation_package(str(work/'sample/translation.csv'),str(work/'sample/manifest.json'),str(game),str(work/'patch'))
            shutil.copytree(work/'patch/COPY_TO_GAME_ROOT',game,dirs_exist_ok=True)
            report['patch']='PASS_DECLARED_SAMPLE_NORMAL_VALIDATORS';save(report)
            quota(preflight['scripts_bytes']+8*1024*1024)
            repeated,repeat_status=extract_text(game,work/'repeat',sdk,work)
            report['repeat_status']=repeat_status;report['roundtrip_identity']=identity(manifest)==identity(repeated)
            if not report['roundtrip_identity']:raise ValueError('full text roundtrip identity drift')
            create_declared_sample(work/'repeat',work/'repeat-sample',pairs)
            apply_translation_package(str(work/'repeat-sample/translation.csv'),str(work/'repeat-sample/manifest.json'),str(game),str(work/'repatch'))
            shutil.copytree(work/'repatch/COPY_TO_GAME_ROOT',game,dirs_exist_ok=True)
            report['repatch']='PASS_NORMAL_VALIDATORS';report['before_native_quota']=quota(8*1024*1024);save(report)
            overlay=game/'game/tl/vietnamese/vntext.rpy'
            report['actual_text_overlay']={'sha256':sha(overlay),'utf8':overlay.read_text(encoding='utf-8')}
            trial_receipt=None
            if args.font_profile_vietnamese:
                from tests.tools.renpy_vm_font_trial import install_trial
                quota(9*1024*1024)
                trial_receipt=install_trial(game,enabled=True)
                report['font_trial']=trial_receipt
                report['after_font_trial_quota']=quota(8*1024*1024);save(report)
            log=work/'native.log';command=[str(sdk.python),str(sdk.renpy_py),str(game),'--savedir',str(work/'native-saves')]
            with log.open('wb')as stream:
                process=subprocess.Popen(command,cwd=sdk.root,stdout=stream,stderr=subprocess.STDOUT)
                report['owned_native_process']={'pid':process.pid,'command':command,'expected_executable':str(sdk.python)}
                report['native_window_waiting']=True;save(report)
                try:
                    deadline=time.monotonic()+300
                    while process.poll()is None and time.monotonic()<deadline and not(EVIDENCE/(args.stem+'-finish.signal')).exists():time.sleep(1)
                finally:
                    if process.poll()is None:
                        process.terminate()
                        try:process.wait(timeout=10)
                        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
                report['native_exit']=process.returncode
            report['native_log_excerpt']=log.read_text(encoding='utf-8',errors='replace')[-8000:]
            if trial_receipt:
                from tests.tools.renpy_vm_font_trial import own_generated_bytecode,rollback_trial
                own_generated_bytecode(trial_receipt)
                report['font_trial_rollback']=rollback_trial(trial_receipt)
            report['post_native_original_changes']=[name for name,digest in original.items()if not(game/name).is_file()or sha(game/name)!=digest]
            report['original_rpa_unchanged']=sha(game/'game/archive.rpa')==preflight['rpa_sha256']
            report['native_window_waiting']=False;report['outcome']='TECHNICAL_PIPELINE_COMPLETED_NATIVE_EVIDENCE_EXTERNAL';save(report)
    except Exception as error:
        report['outcome']='GATE_ERROR';report['error']=repr(error);save(report)
        raise
    finally:
        report['original_rar_unchanged']=sha(SOURCE)==preflight['source_sha256'];save(report)


if __name__=='__main__':main()
