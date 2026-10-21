"""Actual bounded approved-memory reuse; only fresh registered synthetic data."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch
from tests.tools import translation_owner_approval as approval

ROOT=approval.ROOT


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()


def materialize_fixture_memory(package,rows,decision):
    """Explicit test fixture converter, never called by runtime/autodiscovery."""
    from vntext.mt_memory import normalize_memory_text,_package_binding,load_translation_memory
    approval.validate(decision)
    proposals={r['id']:r for r in approval.original.load(approval.original.DEST/'proposals.json')['translations']}
    actual={r['key']:r for r in rows}
    entries=[];records={}
    for accepted in decision['translations']:
        key=accepted['id'];row=actual[key];draft=proposals[key]
        assert row['source_text']==accepted['source']
        assert row['file_path']==accepted['approval_scope']['file_id']
        assert row['context']==accepted['approval_scope']['scenario_id']+':'+key
        assert row['import_method']=='plain_text_line'
        entry=dict(source=normalize_memory_text(row['source_text']),context_family=row['context'].split(':')[0],
            source_text_exact=row['source_text'],file_path_exact=row['file_path'],context_exact=row['context'],
            import_method=row['import_method'],translation=accepted['translation'],approval_id=key,
            proposal_sha256=digest(draft),approved=True,human_gold=False,training_eligible=False)
        entries.append(entry)
        records[key]=dict(proposal_sha256=entry['proposal_sha256'],scope_sha256=digest({k:entry[k] for k in
                         ('source_text_exact','file_path_exact','context_exact','import_method','translation')}))
    memory=dict(version='1.0.0',scope_policy='strict-approval-v1',package_binding=_package_binding(package),
        approval_sha256=approval.sha(approval.DEST/'decision.json'),proposal_file_sha256=decision['proposal_file_sha256'],
        review_kind='owner-delegated-agent',entries=entries)
    guard=dict(version=1,scope_policy=memory['scope_policy'],package_binding=memory['package_binding'],
        approval_sha256=memory['approval_sha256'],proposal_file_sha256=memory['proposal_file_sha256'],
        entries_sha256=digest(entries),approval_records=records)
    meta=package/'.mt';meta.mkdir(exist_ok=True)
    for name,value in [('translation_memory.json',memory),('translation_memory_scope.json',guard)]:
        path=meta/name
        assert not path.exists(),path
        path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    loaded=load_translation_memory(package)
    assert not loaded.get('scope_error') and len(loaded['entries'])==17


def main():
    from tests.lib.work_paths import work_temp_dir
    from tests.tools import translation_quality_phase1 as old
    from vntext.entry import Entry
    from vntext.package_io import write_package,read_csv_rows_file
    from vntext.mt_ct2_model import Ct2Translator
    from vntext.mt_ct2_pipeline import run_ct2_translate,run_ct2_translate_keys
    from vntext.mt_memory import load_translation_memory,lookup_translation_memory
    from vntext.mt_check import structural_problems
    approval.verify()
    work=work_temp_dir('translation-strict-memory-probe')
    for name in ('TEMP','TMP','TMPDIR'):os.environ[name]=str(work)
    old._configure_offline_cache()
    report_path=ROOT/'DEV_RUN/translation-quality-goal/strict-memory-probe.json'
    assert not report_path.exists()
    decision=approval.original.load(approval.DEST/'decision.json')
    package=work/'synthetic-owner-review-v1'
    rows=[dict(key=r['id'],source_text=r['source'],file_path=r['approval_scope']['file_id'],
               context=r['approval_scope']['scenario_id']+':'+r['id'],import_method='plain_text_line')
          for r in decision['translations']]
    origin=rows[0]
    controls=[('wrong-context','context','UNAPPROVED:other'),('wrong-file','file_path','unapproved.txt'),
              ('raw-case','source_text',origin['source_text'][0].lower()+origin['source_text'][1:]),
              ('raw-whitespace','source_text',origin['source_text'].replace(' ','  ',1)),
              ('wrong-method','import_method','unity_textasset_line')]
    rows += [{**origin,'key':name,field:value} for name,field,value in controls]
    entries=[Entry(**row,safety='safe',locator={'line':i},backend='synthetic').finalize()for i,row in enumerate(rows,1)]
    write_package(str(package),entries,[],{'files_scanned':1},separate_review=False,enable_trace=True)
    fields,before=read_csv_rows_file(package/'translation.csv')
    materialize_fixture_memory(package,before,decision)
    files=[package/'.mt'/n for n in ('translation_memory.json','translation_memory_scope.json')]
    sealed={p.name:approval.sha(p) for p in files}
    memory=load_translation_memory(package)
    negatives=[r for r in before if r['key'] in {c[0] for c in controls}]
    assert all(lookup_translation_memory(row,memory) is None for row in negatives)
    model=old._model_identity();real=Ct2Translator(old.MODEL_DIR)
    calls=[]
    class CountRealCalls:
        config=real.config
        def translate(self,text):
            calls.append([text]);return real.translate(text)
        def translate_many(self,texts):
            calls.append(list(texts));return real.translate_many(texts)
    report=dict(status='RUN_STARTED',source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        approval_sha256=approval.sha(approval.DEST/'decision.json'),model=model,
        code_hashes={n:approval.sha(ROOT/n) for n in ('vntext/mt_memory.py','vntext/mt_ct2_pipeline.py',
                        'vntext/translation_cache.py','vntext/mt_ct2_io.py','vntext/mt_strategies.py','vntext/mt_check.py',
                        'tests/tools/translation_strict_memory_probe.py')},
        scope='explicit fresh registered synthetic fixture only, no user/native/global store',human_gold=False,steps=[])
    def save():report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save()
    try:
        with patch('vntext.mt_ct2_model.get_translator',return_value=CountRealCalls()):
            positive=run_ct2_translate_keys(package/'translation.csv',[r['id'] for r in decision['translations']],backup=False,model_dir=old.MODEL_DIR)
            _,after=read_csv_rows_file(package/'translation.csv');by_key={r['key']:r for r in after}
            assert not calls,'Approved exact hits unexpectedly reached model'
            assert all(by_key[r['id']]['translation']==r['translation'] for r in decision['translations'])
            assert all(not by_key[c[0]]['translation'] for c in controls)
            assert not any(structural_problems(r,r['translation'])for r in after if r['translation'])
            report['steps'].append(dict(kind='approved-reuse',result=positive,matching=17,exact_target_matches=17,actual_model_calls=0,
                                        rows=[by_key[r['id']] for r in decision['translations']]))
            save()
            start=len(calls)
            negative=run_ct2_translate_keys(package/'translation.csv',[c[0]for c in controls],backup=False,model_dir=old.MODEL_DIR)
            assert len(calls)>start,'Unapproved rows did not exercise real translator'
            report['steps'].append(dict(kind='wrong-scope',result=negative,lookup_misses=5,model_calls=len(calls)-start,
                                        qualification='Misses prove no approved reuse; unassisted output may coincide, it is not forbidden wording.'))
            save()
            assert {p.name:approval.sha(p)for p in files}==sealed
            # Exercise normal full-run rebuild/empty-target path after selective callers.
            full=run_ct2_translate(package/'translation.csv',model_dir=old.MODEL_DIR)
            assert {p.name:approval.sha(p)for p in files}==sealed
            after_fields,after=read_csv_rows_file(package/'translation.csv')
            assert after_fields==fields
            assert [(r['key'],r['source_text'])for r in before]==[(r['key'],r['source_text'])for r in after]
            report['steps'].append(dict(kind='full-rebuild',result=full,strict_artifacts_byte_unchanged=True,
                                        approval_entries=len(load_translation_memory(package)['entries'])))
            save()
            other=work/'wrong-package-copy'
            assert package.resolve().is_relative_to(work.resolve()) and other.resolve().is_relative_to(work.resolve())
            shutil.copytree(package,other)
            copied=load_translation_memory(other)
            assert copied.get('scope_error') and lookup_translation_memory(before[0],copied) is None
            start=len(calls)
            result=run_ct2_translate_keys(other/'translation.csv',[before[0]['key']],backup=False,model_dir=old.MODEL_DIR)
            assert len(calls)>start
            assert (other/'.mt/translation_memory.json').read_bytes()==files[0].read_bytes()
            report['steps'].append(dict(kind='wrong-package',scope_error=copied['scope_error'],result=result,model_calls=len(calls)-start))
            save()
        assert old._model_identity()['tree_sha256']==model['tree_sha256']
        report.update(status='PASS_SCOPED_REUSE_ONLY',model_unchanged=True,primary_policy_bytes_unchanged=True,
                      terms='Six approved terms checked by approved whole-sentence targets; no substring glossary installed in other scenes.',
                      actual_model_calls_total=len(calls),model_inputs=calls)
    except BaseException as error:
        report.update(status='FAIL',error=repr(error));raise
    finally:save()
    print(json.dumps(dict(status=report['status'],steps=[s['kind']for s in report['steps']],model_calls=len(calls))))


if __name__=='__main__':main()
