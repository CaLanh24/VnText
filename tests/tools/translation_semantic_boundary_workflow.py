"""Actual generated extract/translate/patch readback for the boundary fix."""
import hashlib
import json
import os
from pathlib import Path
from tests.lib.dev_environment import dev_env_root, release_python
from tests.lib.work_paths import work_temp_dir
from vntext.package_io import read_csv_rows_file
from vntext.mt_check import structural_problems
from tests.unit.test_worker_translate import _start_worker, _read_ready, _run_task, _stop_worker


def main():
    root=Path.cwd();e=Path.home()/'Downloads/VM-Acceptance'
    out=e/'semantic-boundary-workflow.json';assert not out.exists()
    frozen=json.loads((root/'evaluation/translation_semantic_campaign_v1/boundary-frozen.json').read_text(encoding='utf-8'))
    work=work_temp_dir('semantic-boundary-workflow')
    for name in ['TEMP','TMP','TMPDIR']:os.environ[name]=str(work)
    os.environ.update(VNTEXT_CT2_MODEL=str(dev_env_root()/'cache/models/opus-mt-en-vi-int8'),VNTEXT_CT2_NO_DOWNLOAD='1',VNTEXT_WORKER_PYTHON=str(release_python()))
    source=work/'source';source.mkdir();input_file=source/'fixture.txt'
    lines=[x['source']for x in frozen['rows']]
    input_file.write_text('\n'.join(lines)+'\n',encoding='utf-8');original=hashlib.sha256(input_file.read_bytes()).hexdigest()
    package=work/'package';report=dict(status='RUN_STARTED',events=[],fixture_only=True)
    def save():out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    proc=_start_worker();save()
    def run(name,params):
        result=_run_task(proc,'semantic-boundary-'+name,name,params,timeout=100)
        report['events'].append(dict(task=name,result=result));save();assert result['ok'],result
        return result
    try:
        _read_ready(proc)
        run('extract',dict(src=str(source),out=str(package),mode='deep',level='balanced',separate_review=True))
        fields,before=read_csv_rows_file(package/'translation.csv');assert len(before)==2
        translated=run('translate',dict(out=str(package)))
        after_fields,after=read_csv_rows_file(package/'translation.csv')
        assert fields==after_fields and [(r['key'],r['source_text'])for r in before]==[(r['key'],r['source_text'])for r in after]
        assert all(r['translation']and not structural_problems(r,r['translation'])for r in after)
        assert 'bắc.Nadia' not in after[0]['translation']
        run('patch',dict(src=str(source),out=str(package)))
        patched=package/'Patch_Viet_Hoa/COPY_TO_GAME_ROOT/fixture.txt'
        assert patched.read_text(encoding='utf-8-sig').splitlines()==[r['translation']for r in after]
        assert hashlib.sha256(input_file.read_bytes()).hexdigest()==original
        report.update(status='PASS_PRODUCT_READBACK',rows=after,source_unchanged=True,semantic_limit='Major long-row omissions and Mila name drift are not fixed by whitespace preservation',patch_readback_exact=True)
    except BaseException as err:report.update(status='FAILED',error=repr(err));raise
    finally:
        _stop_worker(proc);report['worker_exit_code']=proc.returncode
        report['worker_lifecycle']='Existing helper explicitly terminates idle worker; task success separate from native exit.'
        save()
    print(report['status'])


if __name__=='__main__':main()
