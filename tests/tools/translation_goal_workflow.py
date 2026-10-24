"""Offline synthetic worker extract/translate/local CSV import/patch read-back."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import argparse
from tests.lib.dev_environment import dev_env_root, release_python

ROOT=Path(__file__).resolve().parents[2]
SOURCES=[r'Please keep <b>{mode}</b>\n.','Open the red door.',
         'Do not close the window.','Please wait here.']
DONOR=[r'Giữ <b>{mode}</b>\n.','Mở cánh cửa màu đỏ.',
       'Đừng đóng cửa sổ.','Vui lòng chờ ở đây.']


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--label',default='workflow');label=parser.parse_args().label
    if label not in {'workflow','workflow-headwords'}:raise ValueError(label)
    from tests.lib.work_paths import work_temp_dir
    from vntext.package_io import read_csv_rows_file,write_csv_rows_file
    from vntext.mt_check import structural_problems
    work=work_temp_dir('translation-goal-workflow')
    for name in ('TEMP','TMP','TMPDIR'):os.environ[name]=str(work)
    os.environ.update(VNTEXT_CT2_MODEL=str(dev_env_root()/'cache/models/opus-mt-en-vi-int8'),
        VNTEXT_WORKER_PYTHON=str(release_python()),
        VNTEXT_CT2_NO_DOWNLOAD='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    from tests.unit.test_worker_translate import _start_worker,_read_ready,_run_task,_stop_worker
    target=ROOT/'DEV_RUN/translation-quality-goal'/(label+'.json')
    if target.exists():raise FileExistsError(target)
    source=work/'synthetic-source';source.mkdir();input_file=source/'fixture.txt'
    input_file.write_text('\n'.join(SOURCES)+'\n',encoding='utf-8');input_sha=sha(input_file)
    report=dict(status='RUN_STARTED',source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        script_sha256=sha(__file__),sources=SOURCES,donor_targets=DONOR,
        provenance='agent-authored controlled synthetic workflow fixtures, not benchmark answers/product memory/human gold',
        input_sha256=input_sha,events=[],branches={},cloud_io=False)
    def save():target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    proc=_start_worker();save()
    def run(label,task,params):
        result=_run_task(proc,label,task,params,timeout=90)
        report['events'].append(dict(label=label,task=task,result=result));save();return result
    def extract(name):
        package=work/name
        assert run('extract-'+name,'extract',dict(src=str(source),out=str(package),mode='deep',level='balanced',separate_review=True))['ok']
        fields,rows=read_csv_rows_file(package/'translation.csv')
        assert len(rows)==4
        assert {r['source_text'] for r in rows}==set(SOURCES)
        return package,fields,rows
    def patch_and_read(package,fields,rows,name):
        assert run('patch-'+name,'patch',dict(src=str(source),out=str(package)))['ok']
        output=package/'Patch_Viet_Hoa/COPY_TO_GAME_ROOT/fixture.txt'
        actual=output.read_text(encoding='utf-8-sig').splitlines()
        expected={r['source_text']:r['translation'] for r in rows}
        assert actual==[expected[s] for s in SOURCES],(actual,expected)
        assert sha(input_file)==input_sha
        report['branches'][name]=dict(fields=fields,rows=rows,patched_lines=actual,readback_exact=True,input_unchanged=True)
        save()
    try:
        _read_ready(proc)
        package,fields,rows=extract('local')
        (package/'.mt').mkdir(exist_ok=True)
        (package/'.mt/glossary.json').write_text(json.dumps({'mode':'chế độ'},ensure_ascii=False),encoding='utf-8')
        result=run('local-translate','translate',dict(out=str(package)))
        assert result['ok'] and result['complete'],result
        after_fields,translated=read_csv_rows_file(package/'translation.csv')
        assert fields==after_fields and [(r['key'],r['source_text']) for r in rows]==[(r['key'],r['source_text'])for r in translated]
        assert all(r['translation'] and not structural_problems(r,r['translation']) for r in translated)
        patch_and_read(package,fields,translated,'local')
        package,fields,rows=extract('import')
        donor=work/'controlled-donor.csv';targets=dict(zip(SOURCES,DONOR))
        write_csv_rows_file(donor,fields,[{**r,'translation':targets[r['source_text']]} for r in rows])
        donor_sha=sha(donor)
        result=run('local-csv-import','patch',dict(cloud_action='external_import',target_csv=str(package/'translation.csv'),source_csv=str(donor)))
        assert result['ok'] and result['applied']==4,result
        after_fields,imported=read_csv_rows_file(package/'translation.csv')
        assert after_fields==fields and [(r['key'],r['source_text']) for r in imported]==[(r['key'],r['source_text'])for r in rows]
        assert sha(donor)==donor_sha
        patch_and_read(package,fields,imported,'import')
        package,fields,rows=extract('invalid')
        bad=work/'invalid-donor.csv'
        write_csv_rows_file(bad,fields,[{**r,'translation':'Giữ nguyên.' if '{mode}' in r['source_text'] else ''} for r in rows])
        before_sha=sha(package/'translation.csv')
        result=run('invalid-local-csv-import','patch',dict(cloud_action='external_import',target_csv=str(package/'translation.csv'),source_csv=str(bad)))
        assert result.get('applied',0)==0,result
        assert sha(package/'translation.csv')==before_sha
        result=run('invalid-patch','patch',dict(src=str(source),out=str(package)))
        assert not result['ok'] and not(package/'Patch_Viet_Hoa/COPY_TO_GAME_ROOT/fixture.txt').exists()
        report['branches']['invalid']=dict(target_csv_unchanged=True,missing_placeholder_not_imported=True,patch_rejected=True)
        report['status']='PASS'
    except BaseException as error:
        report['status']='FAIL';report['error']=repr(error);raise
    finally:
        _stop_worker(proc);report['worker_exit_code']=proc.returncode
        report['input_unchanged']=sha(input_file)==input_sha;save()
    print(json.dumps(dict(status=report['status'],branches=list(report['branches']),input_unchanged=report['input_unchanged'])))


if __name__=='__main__':main()
