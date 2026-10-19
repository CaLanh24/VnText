"""Source constraints, finite-grammar fixtures and real bounded revision; research only."""
import argparse
import json
import subprocess
import time
from tests.tools import translation_quality_phase8 as natural
from tests.tools import translation_quality_phase20 as frozen
from tests.tools import translation_quality_phase18 as core
from tests.tools import translation_lexical_transport_v2 as transport
from tests.tools import translation_alternative_constraints as constraints
import re
from tests.tools.translation_role_binding import bind_metadata_roles
from tests.tools.translation_quality_guard import protect,sanitize_context
from tests.tools.translation_quality_low_memory_trial import run_one,MODEL,CLI
from tests.tools.translation_quality_prompt_trial import completion_output

ROOT=natural.ROOT
DATA=ROOT/'evaluation/translation_quality_phase22/dataset.v1.json'
FIXTURES=ROOT/'evaluation/translation_quality_phase13/fixtures.v1.json'
DATA_HASH='39612f4d1151fa7d7e319367ded73985ed53153dbbe46e2df143daf724c22710'
FIXTURES_HASH='58254e012e45ffefad34649f24e4e12a6be8b06b75118180edf3ab4bb83ba1da'
EVIDENCE=ROOT/'DEV_RUN/translation-quality-phase22'
PANEL=('Q21-02','Q21-09','Q21-14','Q21-16')
TERMS={**natural.prior.GLOSSARY,'reject':'từ chối','archive':'kho lưu trữ',
       'unverified':'chưa xác minh','unchecked':'chưa kiểm tra','export':'xuất dữ liệu',
       'release':'phát hành','backup':'bản sao lưu','signature':'chữ ký','checksum':'mã kiểm tra',
       'canceling':'việc hủy bỏ','aborting':'việc hủy bỏ','tablet':'máy tính bảng',
       'charger':'bộ sạc','outline':'dàn ý','patching':'vá','eligible':'đủ điều kiện','unresolved':'chưa giải quyết','snapshot':'bản chụp trạng thái','upload':'tải lên',
       'migration':'di chuyển dữ liệu','rollback':'hoàn tác','table':'bảng','stopping':'dừng','rollback data':'dữ liệu hoàn tác','collection':'tập hợp','permitted':'được phép','file transfer':'truyền tệp','verified':'xác minh'}


def translation_prompt(row,previous,feedback):
    prepared=transport.prepare(row)
    working={**row,'source_en':prepared.working_source}
    builder=core if 'I would have' in row['source_en'] and 'if I had' in row['source_en'] and not any('hẳn đã' in target for _,target in prepared.bindings) else frozen
    prompt,p,rule=builder.translation_prompt(working,previous,feedback)
    if len(p.markers)>1:
        anchor='Translate only this English segment into natural Vietnamese, without explanation:'
        prompt=prompt.replace(anchor,'Copy these literal tokens exactly, never translate their names: '+' '.join(p.markers)+'\n\n'+anchor)
    return prompt,(prepared,p),rule


def restore(bundle,raw):
    return transport.restore(bundle[0],bundle[1],raw)


def code_hashes():
    return {**frozen.code_hashes(),'tests/tools/translation_quality_phase18.py':natural.prior.digest(core.__file__), 'tests/tools/translation_lexical_transport_v2.py':natural.prior.digest(transport.__file__),
            'tests/tools/translation_alternative_constraints.py':natural.prior.digest(constraints.__file__),
            'tests/tools/translation_quality_phase22.py':natural.prior.digest(__file__)}


def constrained_pipeline(row,infer):
    history=[];previous='';feedback=[]
    contract=constraints.source_contract(row)
    for attempt in range(2):
        prompt,p,logic_rule=translation_prompt(row,previous,feedback)
        raw=infer(prompt,row['id']+f'-attempt-{attempt}')
        draft='';structural_error='';edits=[]
        try:draft=restore(p,raw)
        except ValueError as exc:structural_error=str(exc)
        original=draft
        metadata_edits=[]
        if draft:
            draft,edits=natural.bind_generic_roles(row,draft)
            draft,metadata_edits=bind_metadata_roles(row,draft)
        audit=constraints.audit_constraints(row,draft)
        flags=natural.rule_audit(row,draft)
        state='FAIL' if flags or audit['status']=='FAIL' else audit['status']
        history.append(dict(attempt=attempt,raw=raw,original_draft=original,draft=draft,role_edits=edits,
                            metadata_edits=metadata_edits,structural_error=structural_error,constraints=audit,advisory_flags=flags,state=state,logic_rule=logic_rule))
        retry=state=='FAIL' or (state=='UNKNOWN' and contract is not None) or not draft
        if not retry or attempt==1:break
        previous=draft
        feedback=[sanitize_context(constraints.feedback(contract))]+audit['reasons']+flags
        if not draft:feedback.append('Return only a translation and keep every source marker unchanged.')
    chosen,reason=constraints.select_attempt(history)
    return dict(id=row['id'],source=row['source_en'],group=row['group'],split=row['split'],history=history,
                draft=history[chosen]['draft'],constraint_status=history[chosen]['state'],
                selected_attempt=chosen,selection_reason=reason,status='NEEDS_REVIEW',output='')


def fixture_score(records):
    return dict(correct_matches=sum(r['expected']=='CONSTRAINTS_MATCH' and r['status']=='CONSTRAINTS_MATCH' for r in records),
                correct_false_flags=sum(r['expected']=='CONSTRAINTS_MATCH' and r['status']=='FAIL' for r in records),
                bad_detected=sum(r['expected']=='FAIL' and r['status']=='FAIL' for r in records),
                false_accept=sum(r['expected']=='FAIL' and r['status']=='CONSTRAINTS_MATCH' for r in records),
                unknown=sum(r['status']=='UNKNOWN' for r in records),n=len(records))


def baseline(rows,work,report,save):
    from vntext.entry import Entry
    from vntext.package_io import write_package,read_csv_rows_file
    from vntext.mt_ct2_pipeline import run_ct2_translate
    natural.prior.old_eval._configure_offline_cache()
    before=natural.prior.old_eval._model_identity()
    for arm in ('unassisted','glossary'):
        package=work/arm
        entries=[Entry(key=r['id'],source_text=r['source_en'],file_path=r['scenario_boundary']['file_id'],
                       context=r['id'],import_method='plain_text_line',safety='safe',locator={'line':i},backend='synthetic').finalize()
                 for i,r in enumerate(rows,1)]
        write_package(str(package),entries,[],{'files_scanned':len({r['scenario_boundary']['file_id'] for r in rows})},separate_review=False,enable_trace=True)
        fields,original=read_csv_rows_file(package/'translation.csv')
        if arm=='glossary':
            (package/'.mt').mkdir(exist_ok=True)
            (package/'.mt/glossary.json').write_text(json.dumps(TERMS,ensure_ascii=False),encoding='utf-8')
        started=time.monotonic()
        result=run_ct2_translate(package/'translation.csv',model_dir=natural.prior.old_eval.MODEL_DIR,
                                 is_cancelled=lambda:time.monotonic()-started>1500)
        after_fields,after=read_csv_rows_file(package/'translation.csv')
        assert fields==after_fields
        assert [(r['key'],r['source_text']) for r in original]==[(r['key'],r['source_text']) for r in after]
        report.setdefault('arms',[]).append(dict(name=arm,result=result,source_order_schema_unchanged=True,
            seconds=round(time.monotonic()-started,3),rows=[dict(id=r['id'],split=r['split'],source=r['source_en'],output=a.get('translation',''),
            structural_reasons=natural.structural_problems(a,a['translation']) if a.get('translation') else None) for r,a in zip(rows,after)]))
        save()
    report['opus_model']=before
    report['opus_model_unchanged']=natural.prior.old_eval._model_identity()['tree_sha256']==before['tree_sha256']
    assert report['opus_model_unchanged']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('seen-fixtures','fresh-fixtures','seen','seen-refined','baseline','final'))
    args=parser.parse_args();EVIDENCE.mkdir(exist_ok=True)
    target=EVIDENCE/(args.stage+'.json')
    if target.exists():raise FileExistsError(target)
    assert natural.prior.digest(DATA)==DATA_HASH and natural.prior.digest(FIXTURES)==FIXTURES_HASH
    selection_name='selection-'+args.stage+'.json' if args.stage in ('seen','seen-refined') else 'selection.json'
    selection=json.loads((EVIDENCE/selection_name).read_text(encoding='utf-8'))
    assert selection['code_hashes']==code_hashes() and selection['dataset_sha256']==DATA_HASH
    assert selection['new_outputs_reviewed'] is False
    report=dict(stage=args.stage,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                code_hashes=code_hashes(),dataset_sha256=DATA_HASH,fixtures_sha256=FIXTURES_HASH,
                calls=[],rows=[],term_bank=TERMS,status='IN_PROGRESS',human_acceptance='NOT_CONDUCTED')
    started=time.monotonic()
    def save():
        report['elapsed_seconds']=round(time.monotonic()-started,3)
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    if args.stage in ('seen-fixtures','fresh-fixtures'):
        if args.stage=='seen-fixtures':
            old=json.loads(natural.FIXTURES.read_text(encoding='utf-8'))
            fixtures=old['seen']+old['fresh']
            fixtures=[{**r,'expected':'CONSTRAINTS_MATCH' if r['expected']=='PASS' else 'FAIL'} for r in fixtures]
        else:fixtures=json.loads(FIXTURES.read_text(encoding='utf-8'))['records']
        for row in fixtures:report['rows'].append(dict(id=row['id'],expected=row['expected'],**constraints.audit_constraints(row,row['draft'])))
        report['score']=fixture_score(report['rows'])
    else:
        rows=json.loads(DATA.read_text(encoding='utf-8'))['rows']
        work=natural.prior.register_work()
        if args.stage=='baseline':baseline(rows,work,report,save)
        else:
            if args.stage in ('seen','seen-refined'):
                old=json.loads((ROOT/'evaluation/translation_quality_phase19/dataset.v1.json').read_text(encoding='utf-8'))['rows']
                old+=json.loads((ROOT/'evaluation/translation_quality_phase21/dataset.v1.json').read_text(encoding='utf-8'))['rows']
                old+=json.loads((ROOT/'evaluation/translation_quality_phase20/dataset.v1.json').read_text(encoding='utf-8'))['rows']
                old+=json.loads((ROOT/'evaluation/translation_quality_phase11/dataset.v1.json').read_text(encoding='utf-8'))['rows']
                old+=json.loads((ROOT/'evaluation/translation_quality_phase12/dataset.v1.json').read_text(encoding='utf-8'))['rows']
                old+=json.loads((ROOT/'evaluation/translation_quality_phase15/dataset.v1.json').read_text(encoding='utf-8'))['rows']
                old+=json.loads((ROOT/'evaluation/translation_quality_phase16/dataset.v1.json').read_text(encoding='utf-8'))['rows']
                old+=json.loads((ROOT/'evaluation/translation_quality_phase17/dataset.v1.json').read_text(encoding='utf-8'))['rows']
                rows=list({r['id']:r for r in old if r['id'] in PANEL}.values())
            assert natural.prior.digest(MODEL)==natural.prior.MODEL_HASH
            report.update(model_sha256=natural.prior.MODEL_HASH,runtime_sha256=natural.prior.digest(CLI.with_name('llama-completion.exe')))
            def infer(prompt,label):
                call=run_one(prompt,work,label,no_repack=True,max_tokens=128,completion=True)
                report['calls'].append(call);save()
                if call['status']!='RETURNED':raise RuntimeError(call['status'])
                if not call['stdout'].strip().endswith('[end of text]'):raise RuntimeError('truncated output/no EOG')
                return completion_output(call['stdout'])
            for row in rows:
                report['rows'].append(constrained_pipeline(row,infer));save()
                print(row['id'],report['rows'][-1]['constraint_status'],flush=True)
            report['model_unchanged']=natural.prior.digest(MODEL)==natural.prior.MODEL_HASH
            assert report['model_unchanged']
    report['status']='COMPLETED';save();return 0


if __name__=='__main__':raise SystemExit(main())
