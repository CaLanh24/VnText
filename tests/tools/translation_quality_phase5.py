"""Protection-first research on seen sentences, then a fresh frozen corpus."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT/'tests/lib')]
from tests.tools.translation_quality_guard import protect, restore, sanitize_context
from tests.tools.translation_quality_prompt_trial import context_for, completion_output, PANEL
from tests.tools.translation_quality_low_memory_trial import run_one, MODEL, CLI
from tests.tools import translation_quality_phase1 as old_eval
from work_paths import WORK_ROOT, ambient_scope, register_artifact
from vntext.mt_check import structural_problems

EVIDENCE = ROOT/'DEV_RUN/translation-quality-phase5'
DATA = ROOT/'evaluation/translation_quality_phase5/dataset.v1.json'
DATA_HASH = '199d5bde7dcf9b7ff9f2e08e0782a7ff88d39563b8cb0ec1a645c6570082759d'
MODEL_HASH = 'dc5f44fcf1fa496ee7ad725982c0c8c553a4de00259b53af84c4b89fb0c06699'
GLOSSARY = {'checksum':'mã kiểm tra', 'manifest':'bản kê khai', 'cache':'bộ nhớ đệm',
            'glossary':'bảng thuật ngữ', 'CSV':'CSV', 'placeholder':'biến giữ chỗ',
            'patch':'bản vá', 'locator':'bộ định vị', 'fingerprint':'dấu vân tay',
            'parser':'trình phân tích', 'sidecar':'tệp phụ', 'worker':'tiến trình xử lý',
            'read-only':'chỉ đọc', 'preview':'xem trước', 'copy':'sao chép', 'cancel':'hủy',
            'export':'xuất dữ liệu', 'journal':'nhật ký', 'shortcut':'phím tắt',
            'badge':'huy hiệu', 'overwrite':'ghi đè', 'overwriting':'ghi đè'}


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def code_hashes():
    return {p: digest(ROOT/p) for p in (
        'tests/tools/translation_quality_phase5.py', 'tests/tools/translation_quality_guard.py',
        'tests/tools/translation_quality_low_memory_trial.py', 'tests/tools/translation_quality_prompt_trial.py')}


def make_prompt(row, rows, variant):
    p = protect(row['source_en'])
    reference, ids = context_for(row, rows)
    sections = []
    if row['group'] in ('terminology', 'ui'):
        sections.append('Domain: software documentation and application interface.')
    terms = [f'{a} translates to {b}' for a,b in GLOSSARY.items()
             if re.search(r'(?<!\w)'+re.escape(a)+r'(?!\w)', row['source_en'], re.I)]
    if terms:
        sections.append('Reference translations:\n'+'\n'.join(terms))
    if reference:
        sections.append('Background (reference only, do not translate):\n'+sanitize_context(reference))
    if variant == 'semantic':
        sections.append('Keep the intended meaning, including negation and conditions. '
                        'Translate idioms by meaning, not word for word. Do not change the requested action.')
        if row.get('address_context'):
            sections.append('Use Vietnamese address matching the speaker relationship.')
    elif variant != 'base':
        raise ValueError(variant)
    if p.markers:
        sections.append('Keep every VNT marker unchanged, once, in its original order. '
                        'Translate ordinary words between markers; only markers are code.')
    sections.append('Translate only the following English segment into Vietnamese, without explanation:\n\n'+p.masked)
    return '\n\n'.join(sections), ids, p


def register_work():
    scope = ambient_scope()
    work = WORK_ROOT/'phase5'
    register_artifact(artifact_id='phase5', path=work, kind='test_temp', created_by=__file__,
                      owner=__file__, purpose='synthetic packages/inference only', lifecycle='DISPOSABLE',
                      scope_id=scope['scope_id'], run_id=scope['run_id'], scope_root=scope['scope_root'])
    work.mkdir(parents=True)
    return work


def baseline(rows, work, report, save):
    from vntext.entry import Entry
    from vntext.package_io import write_package, read_csv_rows_file
    from vntext.mt_ct2_pipeline import run_ct2_translate
    old_eval._configure_offline_cache()
    before_model = old_eval._model_identity()
    for arm in ('unassisted', 'glossary'):
        package = work/arm
        entries = [Entry(key=r['id'], source_text=r['source_en'],
                         file_path=r['scenario_boundary']['file_id'], context=r['id'],
                         import_method='plain_text_line', safety='safe', locator={'line':i}, backend='synthetic').finalize()
                   for i,r in enumerate(rows,1)]
        write_package(str(package), entries, [], {'files_scanned':30}, separate_review=False, enable_trace=True)
        fields, original = read_csv_rows_file(package/'translation.csv')
        if arm == 'glossary':
            (package/'.mt').mkdir(exist_ok=True)
            (package/'.mt/glossary.json').write_text(json.dumps(GLOSSARY,ensure_ascii=False),encoding='utf-8')
        start = time.monotonic()
        result = run_ct2_translate(package/'translation.csv', model_dir=old_eval.MODEL_DIR,
                                   is_cancelled=lambda: time.monotonic()-start>1500)
        after_fields, after = read_csv_rows_file(package/'translation.csv')
        assert fields == after_fields
        assert [(x['key'],x['source_text']) for x in original] == [(x['key'],x['source_text']) for x in after]
        report.setdefault('arms',[]).append({'name':arm,'result':result,'source_order_schema_unchanged':True,
            'seconds':round(time.monotonic()-start,3),'rows':[
                {'id':r['id'],'split':r['split'],'source':r['source_en'],'output':a.get('translation',''),
                 'structural_reasons':structural_problems(a,a['translation']) if a.get('translation') else None}
                for r,a in zip(rows,after)]})
        save()
    report['opus_model'] = before_model
    report['opus_model_unchanged'] = old_eval._model_identity()['tree_sha256']==before_model['tree_sha256']
    assert report['opus_model_unchanged']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stage',choices=('protect','develop','refine','baseline','final'))
    parser.add_argument('--variant',choices=('base','semantic'),default='semantic')
    parser.add_argument('--attempt',type=int,default=1)
    args = parser.parse_args()
    target = EVIDENCE/(args.stage+f'-{args.attempt}.json')
    if target.exists():
        raise FileExistsError(target)
    assert digest(DATA)==DATA_HASH
    new_rows = json.loads(DATA.read_text(encoding='utf-8'))['rows']
    variants = (args.variant,)
    rows = new_rows
    if args.stage in ('protect','develop','refine'):
        seen = json.loads((ROOT/'evaluation/translation_quality_phase1/dataset.v1.json').read_text(encoding='utf-8'))['rows']
        ids = {f'TOK-{i:03}' for i in range(1,15)} if args.stage=='protect' else set(PANEL)|{'TOK-008','TOK-009'}
        if args.stage=='refine':
            ids |= {'UI-002','TOK-011','TOK-013'}
        rows = [r for r in seen if r['id'] in ids]
        variants = ('base',) if args.stage=='protect' else (('semantic',) if args.stage=='refine' else ('base','semantic'))
    else:
        selection = json.loads((EVIDENCE/'selection.json').read_text(encoding='utf-8'))
        assert selection['dataset_sha256']==DATA_HASH and selection['code_hashes']==code_hashes()
        assert selection['new_outputs_reviewed'] is False and selection['variant']==args.variant
    work = register_work()
    report = {'stage':args.stage,'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'code_hashes':code_hashes(),'dataset_sha256':DATA_HASH,'glossary':GLOSSARY,
              'variants':variants,'runs':[],'status':'IN_PROGRESS','human_acceptance':'NOT_CONDUCTED'}
    started = time.monotonic()
    def save():
        report['elapsed_seconds']=round(time.monotonic()-started,3)
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    if args.stage=='baseline':
        baseline(rows,work,report,save)
    else:
        assert digest(MODEL)==MODEL_HASH
        report.update(model_sha256=MODEL_HASH,runtime_sha256=digest(CLI.with_name('llama-completion.exe')))
        for row in rows:
            for variant in variants:
                if time.monotonic()-started>3300:
                    report['status']='TOTAL_TIMEOUT'; save(); return 1
                prompt,context_ids,p = make_prompt(row, seen if args.stage in ('protect','develop','refine') else new_rows,variant)
                run = run_one(prompt,work,row['id']+'-'+variant,no_repack=True,max_tokens=128,completion=True)
                run.update(id=row['id'],split=row['split'],group=row['group'],source=row['source_en'],
                           variant=variant,context_ids=context_ids,masked_source=p.masked,
                           original_tokens=p.tokens,markers=p.markers)
                if run['status']=='RETURNED':
                    run['raw_translation']=completion_output(run['stdout'])
                    try:
                        run['output']=restore(p,run['raw_translation'])
                        run['structural_reasons']=structural_problems({'source_text':row['source_en']},run['output'])
                        run['guard_status']='ACCEPTED'
                    except ValueError as exc:
                        run.update(guard_status='REJECTED',guard_reason=str(exc),output='')
                report['runs'].append(run); save()
                print(row['id'],variant,run['status'],run.get('guard_status'),flush=True)
                if run['status']!='RETURNED':
                    report['status']=run['status']; save(); return 1
        report['model_unchanged']=digest(MODEL)==MODEL_HASH
        assert report['model_unchanged']
    report['status']='COMPLETED'; save()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
