"""Sequential disposable real-game acquisition/product/native gate support.

UI observation/input is performed separately through supported sky only.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tests.lib.work_paths import work_temp_dir
from tests.tools.cleanup_work_artifacts import _project_size_snapshot
from vntext.app_tasks import run_extract_task
from vntext.package_io import read_csv_rows_file,write_csv_rows_file
from vntext.patch_pipeline import apply_translation_package
from vntext.renpy_toolchain import validate_sdk
from tests.tools.renpy_declared_sample import create_declared_sample

SPEC={
 'absurd':{'title':'Absurd Saga','url':'https://github.com/absurdsaga/absurdsaga/releases/download/pre-alpha-20241129_1/absurd_saga-pre-alpha-20241129_1-pc.zip',
           'download_bytes':56241525,
           'license_url':'https://raw.githubusercontent.com/absurdsaga/absurdsaga/04a9fed8f5c592e01883be3b450db32bd0140995/LICENSE.md',
           'license':'Code/text MIT; images CC0; music Pixabay Content License; RenPy separately licensed; retained license text, local test only',
           'version':'Official pre-alpha-20241129_1 PC release; archive inventory determines compiled/RPA eligibility; no fabricated variant'},
 'pdl':{'title':'Please Dont Lie (PDL)','url':'https://github.com/Above-and-Below/PDL/releases/download/V0.0.7/PDL-0.0.7-pc.zip',
        'sha256':'690dce8f0ada83cac9f61bc93543e49c5ea1807a1c75f2ed07ac19df1ea8aa2c','download_bytes':63963034,
        'license_url':'https://raw.githubusercontent.com/Above-and-Below/PDL/6e627469caaa51bc1127b8c8de16fceb3b57a07b/LICENSE.md',
        'license':'MIT; copyright2025-2026KathHill','version':'Official V0.0.7 prerelease; original packaged game files'},
 'aqua':{'title':'AquaGuardians','url':'https://codeload.github.com/sk66641/AquaGuardians/zip/756ff3be2cdb3abf53f49ad7fd74a6e3a8e70da2',
         'license_url':'https://raw.githubusercontent.com/sk66641/AquaGuardians/756ff3be2cdb3abf53f49ad7fd74a6e3a8e70da2/license.md',
         'license':'MIT; copyright2024sk66641','version':'Official source commit756ff3be2cdb3abf53f49ad7fd74a6e3a8e70da2; original loose+compiled mix'},
}
def sha(data):return hashlib.sha256(data).hexdigest()
def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
def extract(game,output,sdk):
    events=[];logs=[]
    run_extract_task(str(game),str(output),'safe','balanced',True,renpy_sdk_path=str(sdk.root),renpy_sdk_action='existing',progress=lambda _:None,log=logs.append,complete=events.append)
    manifest=json.loads((output/'manifest.json').read_text(encoding='utf-8'))if(output/'manifest.json').exists()else {}
    return events[-1],manifest,logs
def identity(manifest):return sorted((e['key'],e['source_text'],e['file_path'],e['context'],e['import_method'],json.dumps(e['locator'],sort_keys=True))for e in manifest.get('entries',[]))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--candidate',choices=SPEC,required=True);ap.add_argument('--report',type=Path,required=True)
    ap.add_argument('--finish-signal',type=Path,required=True);ap.add_argument('--hold-seconds',type=int,default=180);args=ap.parse_args()
    spec=SPEC[args.candidate];sdk=validate_sdk(ROOT/'.dev-env/tools/renpy-8.5.3')
    report={'candidate':args.candidate,'spec':spec,'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'outcome':'PENDING','native_visual':'NOT_VERIFIED','sample_type':'COORDINATOR_REVIEWED_VIETNAMESE_SAMPLE; NOT_OWNER_HUMAN_GOLD_OR_MT_BENCHMARK',
        'frozen_selection_rule':'Before product outputs: first2 dialogue units by file/source_line/key, then visible Start/Preferences/Save/Load menu strings, max6; full provenance retained. Reachability sample, not a recall denominator; full unsupported ledger unchanged.'}
    save(args.report,report)
    with tempfile.TemporaryDirectory(dir=work_temp_dir('renpy-real-'+args.candidate))as temporary:
        work=Path(temporary);archive=work/'official.zip';game=work/'game-copy';(game/'game').mkdir(parents=True)
        quota=_project_size_snapshot();report['preflight_quota']=quota
        if not quota['complete']or quota['non_exempt_bytes']+240*1024*1024>quota['limit_bytes']:raise ValueError('insufficient measured acquisition/copy reserve240MiB')
        license_bytes=urllib.request.urlopen(spec['license_url'],timeout=30).read(65536)
        if b'Permission is hereby granted'not in license_bytes:raise ValueError('license prerequisite not established')
        report['license_text']=license_bytes.decode('utf-8');report['license_sha256']=sha(license_bytes);save(args.report,report)
        with urllib.request.urlopen(spec['url'],timeout=45)as response,archive.open('wb')as output:
            size=0
            while chunk:=response.read(1024*1024):
                size+=len(chunk)
                if size>128*1024*1024:raise ValueError('acquisition cap exceeded')
                output.write(chunk)
        digest=sha(archive.read_bytes())
        if spec.get('sha256')and digest!=spec['sha256']:raise ValueError('official asset digest mismatch')
        if spec.get('download_bytes')and size!=spec['download_bytes']:raise ValueError('official asset size mismatch')
        report.update(download_sha256=digest,download_bytes=size)
        with zipfile.ZipFile(archive)as z:
            selected=[];total=0
            for info in z.infolist():
                path=PurePosixPath(info.filename)
                if path.is_absolute()or '..'in path.parts or '\\'in info.filename:raise ValueError('unsafe archive path')
                if (info.external_attr>>16)&0o170000==0o120000:raise ValueError('linked archive member')
                if 'game'not in path.parts or info.is_dir():continue
                at=path.parts.index('game');relative=PurePosixPath(*path.parts[at:])
                total+=info.file_size;selected.append((info,relative))
            if not selected or total>128*1024*1024 or len(selected)>10000:raise ValueError('game expanded inventory outside budget')
            if quota['non_exempt_bytes']+size+total+64*1024*1024>quota['limit_bytes']:raise ValueError('expanded acquisition/copy exceeds measured quota')
            seen=set()
            for info,relative in selected:
                if str(relative).casefold()in seen:raise ValueError('duplicate game member')
                seen.add(str(relative).casefold());target=game/Path(*relative.parts);target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info)as source,target.open('xb')as output:shutil.copyfileobj(source,output)
        original={p.relative_to(game).as_posix():sha(p.read_bytes())for p in game.rglob('*')if p.is_file()}
        report['frozen_original_inventory']=original;report['expanded_game_bytes']=total
        report['script_surface']={suffix:sum(path.endswith(suffix)for path in original)for suffix in ('.rpy','.rpyc','.rpa')}
        report['source_archive_unchanged']=sha(archive.read_bytes())==digest
        report['runtime']={'python':str(sdk.python),'renpy':str(sdk.renpy_py),'version':sdk.version,'qualification':'Original game content launched with existing pinned SDK8.5.3; not original bundled-runtime acceptance'}
        save(args.report,report) # Freeze provenance/inventory/selection before product outputs.
        event,manifest,logs=extract(game,work/'package',sdk)
        report.update(extract_event=event,extract_logs=logs,package_manifest_sha256=sha((work/'package/manifest.json').read_bytes())if manifest else None,
            entry_count=len(manifest.get('entries',[])),stats=manifest.get('stats',{}))
        sample=[]
        sample.extend(sorted((e for e in manifest.get('entries',[])if e['import_method']=='renpy_dialogue'),key=lambda e:(e['file_path'],e.get('native_contract',{}).get('provenance',{}).get('source_line',0),e['key']))[:2])
        for text in ('Start','Preferences','Save','Load'):
            entry=next((e for e in manifest.get('entries',[])if e['import_method']=='renpy_string'and e['source_text']==text),None)
            if entry:sample.append(entry)
        report['frozen_selected_entries']=sample
        report['negative_review_sample']=[e for e in manifest.get('entries',[])if e.get('review_only')][:4]
        report['patch']='NOT_ATTEMPTED_NO_PACKAGE'
        sample_path=args.report.with_name(args.report.stem+'-translations.json')
        report['translation_sample_path']=str(sample_path);report['sample_waiting']=bool(sample);save(args.report,report)
        if sample:
            deadline=time.monotonic()+120
            while not sample_path.exists()and time.monotonic()<deadline:time.sleep(1)
        translations=json.loads(sample_path.read_text(encoding='utf-8'))if sample_path.is_file()else []
        approved={item['key']:item for item in translations}
        for entry in sample:
            if entry['key']in approved and approved[entry['key']]['source_text']!=entry['source_text']:raise ValueError('reviewed sample source mismatch')
        if set(approved)-{e['key']for e in sample}:raise ValueError('reviewed sample outside frozen selection')
        report['reviewed_translation_sample']=translations;report['sample_waiting']=False;save(args.report,report)
        if manifest:
            try:
                provenance=create_declared_sample(work/'package',work/'declared-sample',translations)
                report['declared_sample_provenance']=provenance
                apply_translation_package(str(work/'declared-sample/translation.csv'),str(work/'declared-sample/manifest.json'),str(game),str(work/'patch'))
                report['patch']='PASS_BOUNDED_REVIEWED_VIETNAMESE_SAMPLE'
                shutil.copytree(work/'patch/COPY_TO_GAME_ROOT',game,dirs_exist_ok=True)
                repeated,replay,_=extract(game,work/'repeat',sdk)
                report['repeat_event']=repeated;report['roundtrip_identity']=identity(manifest)==identity(replay)
                create_declared_sample(work/'repeat',work/'repeat-sample',translations)
                apply_translation_package(str(work/'repeat-sample/translation.csv'),str(work/'repeat-sample/manifest.json'),str(game),str(work/'repatch'))
                shutil.copytree(work/'repatch/COPY_TO_GAME_ROOT',game,dirs_exist_ok=True)
                report['repatch']='PASS_DECLARED_SAMPLE_FULL_REPEAT_REMAINS_PARTIAL'
            except Exception as error:report['patch']='BLOCKED';report['patch_error']=repr(error)
        report['original_files_unchanged']=all((game/path).is_file()and sha((game/path).read_bytes())==digest for path,digest in original.items())
        log=work/'native.log';env=os.environ.copy();env['RENPY_DISABLE_SOUND']='1'
        command=[str(sdk.python),str(sdk.renpy_py),str(game),'--savedir',str(work/'native-saves')]
        with log.open('wb')as stream:
            process=subprocess.Popen(command,cwd=sdk.root,env=env,stdout=stream,stderr=subprocess.STDOUT)
            report['owned_native_process']={'pid':process.pid,'command':command,'expected_executable':str(sdk.python)}
            report['native_window_waiting']=True;save(args.report,report)
            try:
                deadline=time.monotonic()+min(args.hold_seconds,300)
                while process.poll()is None and time.monotonic()<deadline and not args.finish_signal.exists():time.sleep(1)
            finally:
                if process.poll()is None:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=10)
                report['owned_native_exit']=process.returncode
        report['native_log_excerpt']=log.read_text(encoding='utf-8',errors='replace')[-10000:]
        report['post_native_original_changes']=[path for path,digest in original.items() if not(game/path).is_file() or sha((game/path).read_bytes())!=digest]
        report['post_native_original_rpy_unchanged']=not any(path.endswith('.rpy') for path in report['post_native_original_changes'])
        report['source_archive_unchanged']=sha(archive.read_bytes())==report['download_sha256']
        report['outcome']='REVIEW_REQUIRED_NATIVE_EVIDENCE_EXTERNAL'
        report['native_window_waiting']=False;save(args.report,report)
    return 0

if __name__=='__main__':raise SystemExit(main())
