"""Source constraints, finite-grammar fixtures and real bounded revision; research only."""
import argparse
import json
import subprocess
import time
from tests.tools import translation_quality_phase8 as natural
from tests.tools import translation_constraints as constraints
from tests.tools.translation_quality_guard import protect,restore,sanitize_context
from tests.tools.translation_quality_low_memory_trial import run_one,MODEL,CLI
from tests.tools.translation_quality_prompt_trial import completion_output

ROOT=natural.ROOT
DATA=ROOT/'evaluation/translation_quality_phase9/dataset.v1.json'
FIXTURES=DATA.with_name('constraint-fixtures.v1.json')
DATA_HASH='f35bd9acfe70af58e7572f97222debea4de0a867a3b7c38b30b101e5aedcb4ae'
FIXTURES_HASH='723605f7d959684dafdd17fecba6694bcc07ee42de5e67250ab664ed7b5fb38b'
EVIDENCE=ROOT/'DEV_RUN/translation-quality-phase9'
PANEL=('Q8-01-1','Q8-03-1','Q8-06-2','Q8-09-1','Q8-11-2','Q8-12-2')


def code_hashes():
    return {**natural.code_hashes(),'tests/tools/translation_constraints.py':natural.prior.digest(constraints.__file__),
            'tests/tools/translation_quality_phase9.py':natural.prior.digest(__file__)}


def constrained_pipeline(row,infer):
    history=[];previous='';feedback=[]
    contract=constraints.source_contract(row)
    for attempt in range(2):
        prompt,p,logic_rule=natural.translation_prompt(row,previous,feedback)
        raw=infer(prompt,row['id']+f'-attempt-{attempt}')
        draft='';structural_error='';edits=[]
        try:draft=restore(p,raw)
        except ValueError as exc:structural_error=str(exc)
        original=draft
        if draft:draft,edits=natural.bind_generic_roles(row,draft)
        audit=constraints.audit_constraints(row,draft)
        flags=natural.rule_audit(row,draft)
        state='FAIL' if flags or audit['status']=='FAIL' else audit['status']
        history.append(dict(attempt=attempt,raw=raw,original_draft=original,draft=draft,role_edits=edits,
                            structural_error=structural_error,constraints=audit,advisory_flags=flags,state=state,logic_rule=logic_rule))
        retry=state=='FAIL' or (state=='UNKNOWN' and contract is not None) or not draft
        if not retry or attempt==1:break
        previous=draft
        feedback=[sanitize_context(constraints.feedback(contract))]+audit['reasons']+flags
        if not draft:feedback.append('Return only a translation and keep every source marker unchanged.')
    return dict(id=row['id'],source=row['source_en'],group=row['group'],split=row['split'],history=history,
                draft=history[-1]['draft'],constraint_status=history[-1]['state'],status='NEEDS_REVIEW',output='')


def fixture_score(records):
    return dict(correct_matches=sum(r['expected']=='CONSTRAINTS_MATCH' and r['status']=='CONSTRAINTS_MATCH' for r in records),
                correct_false_flags=sum(r['expected']=='CONSTRAINTS_MATCH' and r['status']=='FAIL' for r in records),
                bad_detected=sum(r['expected']=='FAIL' and r['status']=='FAIL' for r in records),
                false_accept=sum(r['expected']=='FAIL' and r['status']=='CONSTRAINTS_MATCH' for r in records),
                unknown=sum(r['status']=='UNKNOWN' for r in records),n=len(records))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('seen-fixtures','fresh-fixtures','seen','baseline','final'))
    args=parser.parse_args();EVIDENCE.mkdir(exist_ok=True)
    target=EVIDENCE/(args.stage+'.json')
    if target.exists():raise FileExistsError(target)
    assert natural.prior.digest(DATA)==DATA_HASH and natural.prior.digest(FIXTURES)==FIXTURES_HASH
    selection=json.loads((EVIDENCE/'selection.json').read_text(encoding='utf-8'))
    assert selection['code_hashes']==code_hashes() and selection['dataset_sha256']==DATA_HASH
    assert selection['new_outputs_reviewed'] is False
    report=dict(stage=args.stage,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                code_hashes=code_hashes(),dataset_sha256=DATA_HASH,fixtures_sha256=FIXTURES_HASH,
                calls=[],rows=[],status='IN_PROGRESS',human_acceptance='NOT_CONDUCTED')
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
        if args.stage=='baseline':natural.prior.baseline(rows,work,report,save)
        else:
            if args.stage=='seen':
                old=json.loads(natural.DATA.read_text(encoding='utf-8'))['rows'];rows=[r for r in old if r['id'] in PANEL]
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
