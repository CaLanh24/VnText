"""One frozen synthetic before/after product-path check; existing offline OPUS only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time
import os
import sqlite3

ROOT=Path(__file__).resolve().parents[2]
ROWS=[('outside','The red door is open.'),('inside','Please choose the mode.'),
      ('protected','Please keep {mode}.'),('boundary','The model is ready.')]
ENTRIES=[dict(source='mode',target='chế độ',priority=5),dict(source='mode',target='kiểu',priority=5)]
EVIDENCE=ROOT/'DEV_RUN/glossary-conflict-scope'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['before','before-trace','after','after-final','after-cache'])
    stage=parser.parse_args().stage
    target=EVIDENCE/(stage+'.json')
    if target.exists():raise FileExistsError(target)
    from tests.lib.work_paths import work_temp_dir
    from tests.tools import translation_quality_phase1 as old
    from vntext.entry import Entry
    from vntext.package_io import write_package,read_csv_rows_file
    from vntext.mt_ct2_pipeline import run_ct2_translate
    from vntext.mt_check import structural_problems
    work=work_temp_dir('glossary-conflict-scope-'+stage)
    for name in ('TEMP','TMP','TMPDIR'):os.environ[name]=str(work)
    old._configure_offline_cache()
    model=old._model_identity();started=time.monotonic()
    report=dict(stage=stage,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        code_hashes={n:digest(ROOT/n) for n in ['vntext/glossary_v2.py','vntext/mt_ct2_io.py','vntext/mt_ct2_pipeline.py',
                                             'vntext/mt_strategies.py','tests/tools/glossary_conflict_scope_check.py']},
        fixture=dict(rows=ROWS,glossary=ENTRIES,rights='agent-generated synthetic for project',use='seen technical regression, not benchmark/gold'),
        model=model,arms=[],status='RUN_STARTED')
    EVIDENCE.mkdir(exist_ok=True)
    def save():target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def stopped():
        mem=old._windows_process_memory()
        return time.monotonic()-started>110 or not mem['available'] or mem['peak_working_set_bytes']>=1024**3
    save()
    try:
        for name in ['control','conflict']:
            package=work/name
            entries=[Entry(key=k,source_text=s,file_path='synthetic/glossary-conflict.txt',context=k,
                           import_method='plain_text_line',safety='safe',locator={'line':i},backend='synthetic').finalize()
                     for i,(k,s) in enumerate(ROWS,1)]
            write_package(str(package),entries,[],{'files_scanned':1},separate_review=False,enable_trace=True)
            fields,before=read_csv_rows_file(package/'translation.csv')
            if name=='conflict':
                (package/'.mt/v2').mkdir(parents=True,exist_ok=True)
                (package/'.mt/v2/glossary.json').write_text(json.dumps(dict(schema_version=1,entries=ENTRIES),ensure_ascii=False),encoding='utf-8')
            legacy_seed=None
            if stage=='after-cache' and name=='conflict':
                from vntext.translation_cache import TranslationCache
                old_run=json.loads((EVIDENCE/'before-trace.json').read_text(encoding='utf-8'))
                old_arm=old_run['arms'][1]
                old_row=next(r for r in old_arm['rows'] if r['key']=='protected')
                old_key=old_arm['result']['cache_fingerprints']['protected']
                cache=TranslationCache(package)
                try:assert cache.put(old_key,next(r for r in before if r['key']=='protected'),old_row['translation'],validation_status='PASS',provenance={'kind':'historical regression seed, not approved memory'})
                finally:cache.close()
                legacy_seed=dict(key=old_key,translation=old_row['translation'])
            result=run_ct2_translate(package/'translation.csv',model_dir=old.MODEL_DIR,is_cancelled=stopped)
            after_fields,after=read_csv_rows_file(package/'translation.csv')
            assert fields==after_fields
            assert [(r['key'],r['source_text']) for r in before]==[(r['key'],r['source_text']) for r in after]
            records=[dict(key=r['key'],source=r['source_text'],translation=r.get('translation',''),
                structural_reasons=structural_problems(r,r['translation']) if r.get('translation') else None) for r in after]
            assert not any(r['structural_reasons'] for r in records)
            review_path=package/'review_only.csv'
            review_rows=read_csv_rows_file(review_path)[1] if review_path.exists() else []
            inventory_path=package/'.mt/blocker_inventory.json'
            inventory=json.loads(inventory_path.read_text(encoding='utf-8')) if inventory_path.exists() else None
            database=package/'.mt/v2/translation_cache.sqlite3'
            cached=[]
            if database.exists():
                connection=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)
                try:cached=[dict(cache_key=k,translation=t,validation_status=v) for k,t,v in connection.execute('SELECT cache_key,translation,validation_status FROM cache_entries ORDER BY cache_key')]
                finally:connection.close()
            report['arms'].append(dict(name=name,result=result,fields=fields,source_order_schema_unchanged=True,
                rows=records,review_ledger=review_rows,blocker_inventory=inventory,cache_rows=cached,legacy_cache_seed=legacy_seed))
            save()
        report['model_unchanged']=old._model_identity()['tree_sha256']==model['tree_sha256']
        assert report['model_unchanged']
        if stage.startswith('after'):
            before= json.loads((EVIDENCE/'before.json').read_text(encoding='utf-8'))
            assert before['fixture']==json.loads(json.dumps(report['fixture']))
            assert before['model']['tree_sha256']==report['model']['tree_sha256']
            control={r['key']:r for r in report['arms'][0]['rows']}
            conflict={r['key']:r for r in report['arms'][1]['rows']}
            for key in ['outside','protected','boundary']:
                assert conflict[key]['translation']==control[key]['translation'],key
            assert conflict['outside']['translation'] and conflict['boundary']['translation']
            assert conflict['inside']['translation']=='', 'true conflict must stay blocked'
            assert report['arms'][0]['rows']==before['arms'][0]['rows'],'control changed'
            blocked=report['arms'][1]['blocker_inventory']
            assert blocked and {r['key'] for r in blocked['rows']}=={'inside'}
            assert {r['key'] for r in report['arms'][1]['review_ledger']}=={'inside'}
            assert len(report['arms'][1]['cache_rows'])==(4 if stage=='after-cache' else 3)
            assert all(r['validation_status']=='PASS' for r in report['arms'][1]['cache_rows'])
            if stage=='after-cache':
                arm=report['arms'][1]
                assert arm['result']['cache']['hits']==0
                assert arm['result']['cache_fingerprints']['protected']!=arm['legacy_cache_seed']['key']
                assert any(r['cache_key']==arm['legacy_cache_seed']['key'] for r in arm['cache_rows'])
            report['acceptance']='PASS bounded row-local conflict applicability, not general semantic quality'
        report['status']='COMPLETED'
    except BaseException as error:
        report['status']='FAILED';report['error']=repr(error);raise
    finally:
        report['elapsed_seconds']=time.monotonic()-started
        report['memory']=old._windows_process_memory();save()
    print(json.dumps(dict(status=report['status'],stage=stage,arms=[dict(name=a['name'],translated=a['result']['translated'],blocked=a['result']['blocked']) for a in report['arms']])))


if __name__=='__main__':main()
