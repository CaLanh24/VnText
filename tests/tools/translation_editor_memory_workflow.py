"""Real worker/CLI workflow for explicit review on generated files only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import argparse
from tests.tools.translation_goal_workflow import SOURCES,DONOR
from tests.lib.dev_environment import dev_env_root, release_python

ROOT=Path(__file__).resolve().parents[2]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',choices=['editor-memory-workflow','editor-memory-workflow-copyfix'],default='editor-memory-workflow')
    label=parser.parse_args().label
    from tests.lib.work_paths import work_temp_dir
    from vntext.package_io import read_csv_rows_file,write_csv_rows_file
    from vntext.mt_memory import load_translation_memory,lookup_translation_memory
    from tests.unit.test_worker_translate import _start_worker,_read_ready,_run_task,_stop_worker
    work=work_temp_dir('editor-memory-workflow')
    for name in ('TEMP','TMP','TMPDIR'):os.environ[name]=str(work)
    os.environ.update(VNTEXT_CT2_MODEL=str(dev_env_root()/'cache/models/opus-mt-en-vi-int8'),
        VNTEXT_WORKER_PYTHON=str(release_python()),
        VNTEXT_CT2_NO_DOWNLOAD='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    source=work/'source';source.mkdir();input_file=source/'fixture.txt'
    input_file.write_text('\n'.join(SOURCES)+'\n',encoding='utf-8');original=sha(input_file)
    package=work/'package';report_path=ROOT/'DEV_RUN/translation-quality-goal'/(label+'.json')
    assert not report_path.exists()
    report=dict(status='RUN_STARTED',source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        fixture='Generated controlled workflow only; explicit test confirmation, not approval of user data/human gold',
        code_hashes={n:sha(ROOT/n)for n in ('vntext/mt_memory.py','vntext/csv_editor_api.py','vntext/mt_ct2_pipeline.py',
                                         'tests/tools/translation_editor_memory_workflow.py')},events=[])
    def save():report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def cli(action,keys,token=None):
        keys_path=work/'keys.json';keys_path.write_text(json.dumps(keys),encoding='utf-8')
        args=[str(release_python()),'-B','-m','vntext.csv_editor_api',action,
              str(package/'translation.csv'),'--keys',str(keys_path)]
        if token:args+=['--preview-token',token]
        child=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=30)
        result=json.loads(child.stdout);assert child.returncode==0,result
        return result
    proc=_start_worker();save()
    def run(label,task,params):
        result=_run_task(proc,label,task,params,timeout=60)
        report['events'].append(dict(label=label,result=result));save();return result
    try:
        _read_ready(proc)
        assert run('extract','extract',dict(src=str(source),out=str(package),mode='deep',level='balanced',separate_review=True))['ok']
        fields,rows=read_csv_rows_file(package/'translation.csv');assert len(rows)==4
        donor=work/'donor.csv';targets=dict(zip(SOURCES,DONOR))
        write_csv_rows_file(donor,fields,[{**r,'translation':targets[r['source_text']]}for r in rows]);donor_hash=sha(donor)
        imported=run('import','patch',dict(cloud_action='external_import',target_csv=str(package/'translation.csv'),source_csv=str(donor)))
        assert imported['applied']==4
        keys=[r['key']for r in rows]
        before={str(p.relative_to(package)):sha(p)for p in package.rglob('*')if p.is_file()}
        preview=cli('preview-reviewed-memory',keys)
        assert preview['ok'] and preview['count']==4
        assert before=={str(p.relative_to(package)):sha(p)for p in package.rglob('*')if p.is_file()}
        confirmed=cli('confirm-reviewed-memory',keys,preview['preview_token'])
        assert confirmed['ok'] and confirmed['memory_entries']==4
        loaded=load_translation_memory(package);assert not loaded.get('scope_error'),loaded
        assert all(e['reviewer_kind']=='user-confirmed'for e in loaded['entries'])
        strict_files=[package/'.mt'/n for n in ('translation_memory.json','translation_memory_scope.json','translation_memory_decisions.json')]
        strict_hashes={p.name:sha(p)for p in strict_files}
        # Clearing only draft cells uses existing save CLI, never alters source/schema.
        fields,approved_rows=read_csv_rows_file(package/'translation.csv')
        payload=work/'cleared.json';payload.write_text(json.dumps(dict(fields=fields,rows=[{**r,'translation':''}for r in approved_rows])),encoding='utf-8')
        clear=subprocess.run([str(release_python()),'-B','-m','vntext.csv_editor_api','save',
                              str(package/'translation.csv'),'--payload',str(payload)],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=30)
        assert clear.returncode==0,clear.stdout
        translated=run('reuse','translate',dict(out=str(package)))
        assert translated['ok'] and translated['complete'],translated
        after_fields,after=read_csv_rows_file(package/'translation.csv')
        assert after_fields==fields and [(r['key'],r['source_text'])for r in after]==[(r['key'],r['source_text'])for r in rows]
        assert all(r['translation']==targets[r['source_text']]for r in after)
        assert {p.name:sha(p)for p in strict_files}==strict_hashes
        assert run('patch','patch',dict(src=str(source),out=str(package)))['ok']
        output=package/'Patch_Viet_Hoa/COPY_TO_GAME_ROOT/fixture.txt'
        assert output.read_text(encoding='utf-8-sig').splitlines()==DONOR
        other=work/'copy';assert other.resolve().is_relative_to(work.resolve())
        # Binding check needs only immutable approval files, not live SQLite WAL.
        (other/'.mt').mkdir(parents=True)
        for artifact in strict_files:
            shutil.copyfile(artifact,other/'.mt'/artifact.name)
        copied=load_translation_memory(other);assert copied.get('scope_error')
        assert lookup_translation_memory(after[0],copied) is None
        assert sha(input_file)==original and sha(donor)==donor_hash
        report.update(status='PASS_CONTROLLED_WORKFLOW',preview_count=4,confirm_result=confirmed,
            approved_targets_reused_exactly=4,patch_readback_exact=True,preview_wrote_nothing=True,
            strict_artifact_hashes=strict_hashes,strict_artifacts_unchanged_after_reuse=True,
            copied_package_refused=True,original_source_unchanged=True,donor_unchanged=True,
            rows=after,native_ui_acceptance=False)
    except BaseException as error:
        report.update(status='FAIL',error=repr(error));raise
    finally:
        _stop_worker(proc);report['worker_exit_code']=proc.returncode
        report['worker_shutdown']='Existing test helper explicitly terminates idle child; not natural exit0.'
        save()
    print(json.dumps(dict(status=report['status'],rows=4,patch_readback=True)))


if __name__=='__main__':main()
