"""Research natural translation -> calibrated advisory audit -> at most one revision."""
import argparse
import json
import re
import subprocess
import time
from tests.tools import translation_quality_phase5 as prior
from tests.tools import translation_quality_phase6 as sense
from tests.tools.translation_quality_guard import protect,restore,opaque_tokens,sanitize_context,spans
from vntext.mt_check import structural_problems
from tests.tools.translation_quality_prompt_trial import completion_output
from tests.tools.translation_quality_semantic_transport import role_pair,paraphrase_logic,relationship_contradictions
from tests.tools.translation_quality_low_memory_trial import run_one,MODEL,CLI

ROOT=prior.ROOT
DATA=ROOT/'evaluation/translation_quality_phase8/dataset.v1.json'
FIXTURES=DATA.with_name('audit-fixtures.v1.json')
DATA_HASH='867143bb1e4a0c27b8370c8704139be4fcc20cb3597130c1a746b0677c0c9fa8'
FIXTURES_HASH='f97a16c36383aa354f394c1bd84aa1e7b558c60fd68206a8c8991e74145bdd1d'
EVIDENCE=ROOT/'DEV_RUN/translation-quality-phase8'
PANEL=('Q5-29-2','Q6-09-2','Q6-17-2','Q7-03-1','Q7-03-2','Q7-05-2','Q7-09-2','Q7-12-2')


def code_hashes():
    paths=('tests/tools/translation_quality_phase8.py','tests/tools/translation_quality_semantic_transport.py')
    return {**prior.code_hashes(),**{p:prior.digest(ROOT/p) for p in paths},
            'tests/tools/translation_quality_phase6.py':prior.digest(sense.__file__)}


def parse_audit(raw):
    value=raw.strip()
    if value=='PASS':return 'PASS',''
    if value=='FAIL':return 'FAIL','meaning or role mismatch'
    m=re.fullmatch(r'FAIL: ([^\r\n]{1,160})',value)
    return ('FAIL',m[1]) if m else ('UNKNOWN','unparseable audit response')


def rule_audit(row,draft):
    flags=[]
    if not draft:return ['structural rejection']
    if opaque_tokens(row['source_en'])!=opaque_tokens(draft):flags.append('protected syntax differs')
    pair=role_pair(row.get('address_context',''))
    if pair:
        if re.search(r'(?<!\w)(tôi|bạn|ông|bà)(?!\w)',draft,re.I):flags.append('generic/wrong role pronoun')
        if pair[1]=='giáo sư' and re.search(r'(?<!\w)(thầy|cô)(?!\w)',draft,re.I):flags.append('unknown professor gender guessed')
        # Narrow duplicated recipient detector; no source coordination -> no invented counterpart.
        if re.search(r'\byou\s+my\b',row['source_en'],re.I):
            if re.search(re.escape(pair[1])+r'\s+và\s+'+re.escape(pair[0]),draft,re.I):
                flags.append('added speaker as recipient')
        flags+=relationship_contradictions(row.get('address_context',''),draft)
    s=row['source_en'].casefold();d=draft.casefold()
    if s.startswith('unless ') and d.startswith('chỉ '):flags.append('possible unless condition reversal')
    if re.search(r'(?:canceling|aborting).+must not (?:remove|erase|delete)',s) and re.match(r'(đừng|không được) hủy',d):
        flags.append('cancellation/deletion prohibition reversed')
    plain_source=re.sub(r'<[^>]*>','',s).strip()
    plain_draft=re.sub(r'<[^>]*>','',d).strip()
    if plain_source.startswith('do not delete ') and re.match(r'(?:hãy )?(?:xóa|xoá|gỡ bỏ)\b',plain_draft):
        flags.append('affirmative deletion contradicts source prohibition')
    if plain_source.startswith('reject ') and plain_draft.startswith('chấp nhận '):
        flags.append('accept contradicts source rejection')
    return flags


def bind_generic_roles(row,draft):
    """Narrow, logged post-edit; unsupported discourse is never guessed."""
    source=row['source_en'];pair=role_pair(row.get('address_context',''))
    if not pair or re.search(r'["“”\'’]|\b(?:he|she|his|her|they|them|their|we|us|our|friend|friends|buddy|ego)\b',source,re.I):
        return draft,[]
    if re.search(r'["“”]|(?<!\w)(?:chúng tôi|bọn tôi|cô ấy|ông ấy|bà ấy)(?!\w)',draft,re.I):return draft,[]
    mapping={}
    if re.search(r'\b(?:I|me|my|mine)\b',source,re.I):mapping['tôi']=pair[0]
    if re.search(r'\b(?:you|your|yours)\b',source,re.I):mapping['bạn']=pair[1]
    protected=spans(draft)
    edits=[]
    for m in re.finditer(r'(?<!\w)(tôi|bạn)(?!\w)',draft,re.I):
        if any(a<=m.start()<b for a,b,_ in protected):continue
        replacement=mapping.get(m.group().casefold())
        if replacement:
            if m.start()==0 and m.group()[0].isupper():replacement=replacement[0].upper()+replacement[1:]
            edits.append(dict(start=m.start(),end=m.end(),before=m.group(),after=replacement))
    result=draft
    for edit in reversed(edits):result=result[:edit['start']]+edit['after']+result[edit['end']:]
    if opaque_tokens(result)!=opaque_tokens(draft) or structural_problems({'source_text':source},result):
        raise ValueError('role post-edit violated structure')
    return result,edits


def audit_prompt(row,draft,style):
    role=row.get('address_context','unknown relationship; do not guess')
    body=f"Speaker/listener relationship: {role}\nEnglish source: {row['source_en']}\nVietnamese candidate: {draft}"
    if style=='label':
        return ('Check whether the Vietnamese candidate faithfully translates the English source and explicit relationship. '
                'Check negation, condition, who gives what to whom, sibling age, and added people. '
                'Generic pronouns are wrong when explicit family/professor roles are given. '
                'Do not translate. Reply exactly PASS if correct, otherwise FAIL: followed by one short reason.\n\n'+body)
    if style=='question':
        return ('Does this Vietnamese translation change meaning, negate the wrong action, add a recipient, '
                'or use pronouns inconsistent with the specified roles? '
                'Answer FAIL if any error exists; answer PASS only if all meaning and roles are correct. '
                'Output one word only, PASS or FAIL.\n\n'+body)
    raise ValueError(style)


def translation_prompt(row, draft='', feedback=()):
    p=protect(row['source_en'])
    target,rule=paraphrase_logic(p.masked)
    sections=[]
    if row.get('domain_context'):sections.append('Domain: '+sanitize_context(row['domain_context']))
    pair=role_pair(row.get('address_context',''))
    if pair:
        sections.append(f'Speaker self-reference: {pair[0]}. Listener address: {pair[1]}. '
                        'Keep these roles consistent; do not invent extra people.')
    hints=[h for h in sense.meaning_hints(row,'') if not h.startswith('I/me/my')]
    if hints:sections.append('Vocabulary: '+'; '.join(hints))
    if draft:
        # Only a valid masked draft is passed; no raw previous scene text or target identifiers.
        masked_draft=draft
        for original,marker in zip(p.tokens,p.markers):masked_draft=masked_draft.replace(original,marker,1)
        sections.append('Incorrect Vietnamese draft to revise: '+masked_draft)
    if feedback:
        sections.append('Fix these issues: '+'; '.join(feedback)+'. Preserve the source meaning; do not add information.')
    if p.markers:sections.append('Keep every VNT marker exactly once in its original order. Translate ordinary words between markers.')
    sections.append('Translate only this English segment into natural Vietnamese, without explanation:\n\n'+target)
    return '\n\n'.join(sections),p,rule


def decision(flags,verdict,checker_validated):
    if flags or verdict=='FAIL':return 'FAIL'
    return 'PASS' if checker_validated and verdict=='PASS' else 'UNKNOWN'


def natural_pipeline(row,infer,style,checker_validated):
    history=[]
    previous='';feedback=[]
    for attempt in range(2):
        prompt,p,logic_rule=translation_prompt(row,previous,feedback)
        result=infer(prompt,row['id']+f'-draft-{attempt}')
        draft='';error=''
        try:draft=restore(p,result)
        except ValueError as exc:error=str(exc)
        original_draft=draft;edits=[]
        if draft:draft,edits=bind_generic_roles(row,draft)
        flags=rule_audit(row,draft)
        verdict,reason='UNKNOWN','checker not calibrated'
        if draft and style:
            verdict,reason=parse_audit(infer(audit_prompt(row,draft,style),row['id']+f'-audit-{attempt}'))
        state=decision(flags,verdict,checker_validated)
        history.append(dict(attempt=attempt,raw=result,original_draft=original_draft,role_edits=edits,draft=draft,structural_error=error,rule_flags=flags,
                            audit_verdict=verdict,audit_reason=reason,decision=state,logic_rule=logic_rule))
        if state!='FAIL' or attempt==1:break
        previous=draft
        feedback=flags+([reason] if verdict=='FAIL' else [])
        if not previous:feedback=['preserve the source syntax and return only the translation']
    last=history[-1]
    return dict(id=row['id'],source=row['source_en'],split=row['split'],group=row['group'],history=history,
                draft=last['draft'],output=last['draft'] if last['decision']=='PASS' else '',
                status='AUTO_CANDIDATE' if last['decision']=='PASS' else 'NEEDS_REVIEW')


def calibration_score(records):
    return dict(false_accept=sum(r['expected']=='FAIL' and r['verdict']=='PASS' for r in records),
                good_accepted=sum(r['expected']=='PASS' and r['verdict']=='PASS' for r in records),
                unknown=sum(r['verdict']=='UNKNOWN' for r in records),n=len(records))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=('calibrate','develop','refine','baseline','final','fresh-audit'))
    args=parser.parse_args()
    EVIDENCE.mkdir(exist_ok=True)
    target=EVIDENCE/(args.stage+'.json')
    if target.exists():raise FileExistsError(target)
    assert prior.digest(DATA)==DATA_HASH and prior.digest(FIXTURES)==FIXTURES_HASH
    rows=json.loads(DATA.read_text(encoding='utf-8'))['rows']
    fixtures=json.loads(FIXTURES.read_text(encoding='utf-8'))
    selection=None
    if args.stage!='calibrate':
        selection=json.loads((EVIDENCE/'checker-selection.json').read_text(encoding='utf-8'))
    if args.stage in ('baseline','final','fresh-audit'):
        frozen=json.loads((EVIDENCE/'selection.json').read_text(encoding='utf-8'))
        assert frozen['code_hashes']==code_hashes() and frozen['dataset_sha256']==DATA_HASH
        assert frozen['new_outputs_reviewed'] is False
    work=prior.register_work()
    report=dict(stage=args.stage,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                code_hashes=code_hashes(),dataset_sha256=DATA_HASH,fixtures_sha256=FIXTURES_HASH,
                calls=[],rows=[],status='IN_PROGRESS',human_acceptance='NOT_CONDUCTED')
    start=time.monotonic()
    def save():
        report['elapsed_seconds']=round(time.monotonic()-start,3)
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    if args.stage=='baseline':prior.baseline(rows,work,report,save)
    else:
        assert prior.digest(MODEL)==prior.MODEL_HASH
        report.update(model_sha256=prior.MODEL_HASH,runtime_sha256=prior.digest(CLI.with_name('llama-completion.exe')))
        def infer(prompt,label):
            call=run_one(prompt,work,label,no_repack=True,max_tokens=128,completion=True)
            report['calls'].append(call);save()
            if call['status']!='RETURNED':raise RuntimeError(call['status'])
            if not call['stdout'].strip().endswith('[end of text]'):raise RuntimeError('missing EOG/truncated output')
            return completion_output(call['stdout'])
        if args.stage in ('calibrate','fresh-audit'):
            selected=fixtures['seen' if args.stage=='calibrate' else 'fresh']
            styles=('label','question') if args.stage=='calibrate' else (selection['diagnostic_style'],)
            for style in styles:
                records=[]
                for row in selected:
                    raw=infer(audit_prompt(row,row['draft'],style),row['id']+'-'+style)
                    verdict,reason=parse_audit(raw)
                    records.append(dict(id=row['id'],expected=row['expected'],raw=raw,verdict=verdict,reason=reason))
                report['rows'].append(dict(style=style,records=records,score=calibration_score(records)));save()
        else:
            if args.stage in ('develop','refine'):
                old=[]
                for phase in (5,6,7):old+=json.loads((ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
                rows=[r for r in old if r['id'] in PANEL]
            for row in rows:
                report['rows'].append(natural_pipeline(row,infer,selection['style'],selection['validated']));save()
                print(row['id'],report['rows'][-1]['status'],flush=True)
        report['model_unchanged']=prior.digest(MODEL)==prior.MODEL_HASH
        assert report['model_unchanged']
    report['status']='COMPLETED';save()
    return 0


if __name__=='__main__':raise SystemExit(main())
