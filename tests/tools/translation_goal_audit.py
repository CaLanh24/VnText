"""Frozen existing-corpus product-route audit; no prompt/model campaign."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
EVIDENCE=ROOT/'DEV_RUN/translation-quality-goal'
# Same six test-owned terms declared in Phase2, never a product default bank.
GLOSSARY={'checksum':'mã kiểm tra','manifest':'bản kê khai','cache':'bộ nhớ đệm',
          'glossary':'bảng thuật ngữ','CSV':'CSV','placeholder':'biến giữ chỗ'}


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['baseline','final','final-headwords']);stage=parser.parse_args().stage
    target=EVIDENCE/(stage+'.json')
    if target.exists():raise FileExistsError(target)
    from tests.lib.work_paths import work_temp_dir
    from tests.tools import translation_quality_phase1 as evaluator
    from vntext.entry import Entry
    from vntext.package_io import write_package,read_csv_rows_file
    from vntext.mt_ct2_pipeline import run_ct2_translate
    from vntext.mt_check import structural_problems
    dataset,raw,_=evaluator.load_dataset()
    assert hashlib.sha256(raw).hexdigest()=='7f75108ff031022f94b5a68965eebc6f0a99ff37d3fd1804ebec4c6d2fe9242d'
    work=work_temp_dir('translation-quality-goal-'+stage)
    for name in ('TEMP','TMP','TMPDIR'):os.environ[name]=str(work)
    evaluator._configure_offline_cache();model=evaluator._model_identity();started=time.monotonic()
    report=dict(stage=stage,status='RUN_STARTED',source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        code_hashes={n:digest(ROOT/n) for n in ['vntext/package_glossary.py','vntext/glossary_v2.py','vntext/mt_ct2_pipeline.py',
                                             'vntext/mt_ct2_io.py','vntext/mt_strategies.py','vntext/mt_memory.py','tests/tools/translation_goal_audit.py']},
        dataset_sha256=hashlib.sha256(raw).hexdigest(),use='all100 sources already seen; not heldout/generalization',
        supplied_fixture_glossary=GLOSSARY,approved_memory_imported=False,human_gold=False,model=model,arms=[])
    EVIDENCE.mkdir(exist_ok=True)
    def save():target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def stopped():
        memory=evaluator._windows_process_memory()
        return time.monotonic()-started>170 or not memory['available'] or memory['peak_working_set_bytes']>=1024**3
    save()
    try:
        for arm in ('unassisted','supplied_glossary'):
            package=work/arm
            entries=[Entry(key=r['id'],source_text=r['source_en'],file_path=r['scenario_boundary']['file_id'],
                           context=r['scenario_boundary']['group_id']+':'+r['id'],import_method='plain_text_line',
                           safety='safe',locator={'line':i},backend='synthetic').finalize() for i,r in enumerate(dataset['rows'],1)]
            write_package(str(package),entries,[],{'files_scanned':54},separate_review=False,enable_trace=True)
            fields,before=read_csv_rows_file(package/'translation.csv')
            if arm=='supplied_glossary':
                (package/'.mt').mkdir(exist_ok=True)
                (package/'.mt/glossary.json').write_text(json.dumps(GLOSSARY,ensure_ascii=False),encoding='utf-8')
            result=run_ct2_translate(package/'translation.csv',model_dir=evaluator.MODEL_DIR,is_cancelled=stopped)
            after_fields,after=read_csv_rows_file(package/'translation.csv')
            assert fields==after_fields and [(r['key'],r['source_text']) for r in before]==[(r['key'],r['source_text']) for r in after]
            records=[dict(id=r['key'],source=r['source_text'],translation=r.get('translation',''),
                structural_reasons=structural_problems(r,r['translation']) if r.get('translation') else None) for r in after]
            assert not any(r['structural_reasons'] for r in records)
            review=package/'review_only.csv';inventory=package/'.mt/blocker_inventory.json'
            report['arms'].append(dict(name=arm,result=result,rows=records,fields=fields,source_order_schema_unchanged=True,
                review_ledger=read_csv_rows_file(review)[1] if review.exists() else [],
                blocker_inventory=json.loads(inventory.read_text(encoding='utf-8')) if inventory.exists() else None))
            save()
        report['model_unchanged']=evaluator._model_identity()['tree_sha256']==model['tree_sha256'];assert report['model_unchanged']
        if stage.startswith('final'):
            baseline=json.loads((EVIDENCE/'baseline.json').read_text(encoding='utf-8'))
            assert report['dataset_sha256']==baseline['dataset_sha256'] and report['supplied_fixture_glossary']==baseline['supplied_fixture_glossary']
            assert report['model']['tree_sha256']==baseline['model']['tree_sha256']
            report['changed_rows']={a['name']:[dict(id=new['id'],before=old['translation'],after=new['translation']) for old,new in zip(b['rows'],a['rows']) if old['translation']!=new['translation']] for b,a in zip(baseline['arms'],report['arms'])}
        report['status']='COMPLETED'
    except BaseException as error:
        report['status']='FAILED';report['error']=repr(error);raise
    finally:
        report['elapsed_seconds']=time.monotonic()-started;report['memory']=evaluator._windows_process_memory();save()
    print(json.dumps(dict(status=report['status'],stage=stage,arms=[dict(name=a['name'],translated=a['result']['translated'],blocked=a['result']['blocked']) for a in report['arms']])))


if __name__=='__main__':main()
