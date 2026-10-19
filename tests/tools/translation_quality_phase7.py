"""Frozen research-only semantic prompt comparison; never imported by product."""
import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from tests.tools import translation_quality_phase5 as prior
from tests.tools import translation_quality_phase6 as phase6
from tests.tools.translation_quality_semantic_transport import mask_roles,restore_roles,paraphrase_logic,relationship_contradictions
from tests.tools.translation_quality_guard import protect, restore, sanitize_context
from tests.tools.translation_quality_prompt_trial import context_for, completion_output
from tests.tools.translation_quality_low_memory_trial import run_one, MODEL, CLI

ROOT = prior.ROOT
DATA = ROOT/'evaluation/translation_quality_phase7/dataset.v1.json'
DATA_HASH = '6c8b2cc9b13a31909a61966c29e52e62d87c20d2a8d929c2105b6bd5db4f0c0b'
EVIDENCE = ROOT/'DEV_RUN/translation-quality-phase7'
PANEL = ('Q6-04-2','Q6-05-2','Q6-06-2','Q6-07-2','Q6-08-2','Q6-09-2','Q6-15-1','Q6-17-2','Q6-18-1','Q5-29-2')


def code_hashes():
    return {**prior.code_hashes(), 'tests/tools/translation_quality_phase7.py':prior.digest(__file__), 'tests/tools/translation_quality_phase6.py':prior.digest(phase6.__file__), 'tests/tools/translation_quality_semantic_transport.py':prior.digest(ROOT/'tests/tools/translation_quality_semantic_transport.py')}


def role_policy(context):
    """Only explicit metadata roles, never infer sex or kinship from names."""
    c = context.casefold()
    if 'younger brother to older sister' in c:
        return 'Người nói xưng em, gọi người nghe là chị.'
    if 'older sister' in c and 'younger brother' in c:
        return 'Người nói xưng chị, gọi người nghe là em; em trai là người nhỏ tuổi hơn.'
    if 'older brother to younger sister' in c:
        return 'Người nói xưng anh, gọi người nghe là em.'
    if 'mother' in c and 'daughter' in c:
        return 'Người nói xưng mẹ, gọi người nghe là con.'
    if 'student' in c and 'professor' in c:
        return 'Người nói xưng em, gọi người nghe là giáo sư; chưa biết giới tính, không tự chọn thầy hoặc cô.'
    return ''


def make_prompt(row, rows, variant):
    if variant == 'control':
        return phase6.make_prompt(row,rows,'hints')
    if variant not in ('isolated','logic','transport'):
        raise ValueError(variant)
    p=protect(row['source_en'])
    # No preceding translatable prose is exposed. Explicit metadata and finite lexical senses only.
    sections=[]
    if row.get('domain_context'):
        sections.append('Domain: '+sanitize_context(row['domain_context']))
    hints=phase6.meaning_hints(row,'')
    if hints: sections.append('Vocabulary: '+'; '.join(hints))
    if variant in ('logic','transport'):
        sections.append('Preserve who does what to whom. Unless means if not; only restricts eligibility. '
                        'Canceling must not delete means cancellation is allowed and deletion is forbidden. '
                        'Never turn a prohibition on deletion into a prohibition on cancellation. '
                        'Do not add a negation or reverse an existing condition.')
    if p.markers:
        sections.append('Keep each VNT marker exactly once in its original order; translate words between markers.')
    target=p.masked
    if variant=='transport':
        target,_=paraphrase_logic(target)
        roles=mask_roles(target,row.get('address_context',''))
        target=roles.text
        if roles.replacements:
            sections.append('Keep each ROLEVNT token exactly once in its original order. '
                            'It stands for a pronoun; do not replace it or add another pronoun.')
    sections.append('Translate this English text into Vietnamese. Return only its translation:\n\n'+target)
    return '\n\n'.join(sections),[],p


def meaning_hints(row, context):
    source=row['source_en'].casefold()
    domain=row.get('domain_context','').casefold()
    background=(source+' '+context).casefold()
    hints=[]
    if 'once in a blue moon' in source:
        hints.append('once in a blue moon = rất hiếm khi (rarely, NOT once per month or only once ever)')
    if 'out of the woods' in source and re.search(r'fever|clinic|nurse|patient|danger|breathing|health|medical',background+' '+domain):
        hints.append('out of the woods = thoát khỏi nguy hiểm; not out of the woods = chưa thoát khỏi nguy hiểm (NOT leaving a room or forest)')
    if 'platform' in source:
        if 'railway' in domain: hints.append('platform = sân ga (train boarding area, NOT map)')
        elif 'software' in domain: hints.append('platform = nền tảng (software system, NOT railway station)')
        elif 'construction' in domain: hints.append('platform = bục (raised physical surface)')
    for term,target in (('little brother','em trai'),('younger brother','em trai'),('older sister','chị gái'),('amber','hổ phách')):
        if re.search(r'(?<!\w)'+term+r'(?!\w)',source): hints.append(term+' = '+target)
    if 'exporter' in source and row['group'] in ('terminology','ui'):
        hints.append('exporter = công cụ xuất dữ liệu; package = gói (software, not foreign trade)')
    role=role_policy(row.get('address_context',''))
    pairs=(('xưng chị','chị','em'),('xưng mẹ','mẹ','con'),('xưng anh','anh','em'))
    for trigger,speaker,listener in pairs:
        if trigger in role:
            hints.append(f'I/me/my = {speaker}; you/your = {listener}. Use these Vietnamese pronouns, not tôi/bạn.')
            break
    else:
        if 'xưng em' in role:
            listener='giáo sư' if 'giáo sư' in role else 'chị'
            hints.append(f'I/me/my = em; you/your = {listener}. Do not guess gender.')
    return hints


def semantic_flags(row, output):
    """Narrow diagnostics only; absence is never a quality verdict."""
    flags=[]
    s=row['source_en'].casefold();o=output.casefold()
    if 'platform' in s and not row.get('domain_context'):
        flags.append('PLATFORM_DOMAIN_UNSPECIFIED')
    if 'platform' in s and 'bản đồ' in o: flags.append('PLATFORM_AS_MAP')
    if ('little brother' in s or 'younger brother' in s) and 'anh trai' in o:
        flags.append('YOUNGER_BROTHER_AGE_REVERSAL')
    if s.startswith('keep ') and 'outside' in s and re.search(r'^(đừng|không)',o):
        flags.append('POSSIBLE_ADDED_PROHIBITION')
    if 'once in a blue moon' in s and re.search(r'tháng|trăng|một lần duy nhất',o):
        flags.append('POSSIBLE_IDIOM_LITERALIZATION')
    if role_policy(row.get('address_context','')) and re.search(r'(?<!\w)(tôi|bạn|ông)(?!\w)',o):
        flags.append('ROLE_PRONOUN_MISMATCH')
    return flags


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=('develop','refine','baseline','final'))
    parser.add_argument('--variant',default='transport',choices=('isolated','control','logic','transport'))
    parser.add_argument('--attempt',type=int,default=1)
    args=parser.parse_args()
    EVIDENCE.mkdir(exist_ok=True)
    target=EVIDENCE/(args.stage+f'-{args.attempt}.json')
    if target.exists(): raise FileExistsError(target)
    assert prior.digest(DATA)==DATA_HASH
    rows=json.loads(DATA.read_text(encoding='utf-8'))['rows']
    variants=(args.variant,)
    if args.stage in ('develop','refine'):
        rows=[]
        for phase in (5,6):
            rows+=json.loads((ROOT/f'evaluation/translation_quality_phase{phase}/dataset.v1.json').read_text(encoding='utf-8'))['rows']
        selected=[r for r in rows if r['id'] in PANEL]
        variants=('control','isolated','logic') if args.stage=='develop' else ('transport',)
    else:
        frozen=json.loads((EVIDENCE/'selection.json').read_text(encoding='utf-8'))
        assert frozen['code_hashes']==code_hashes() and frozen['dataset_sha256']==DATA_HASH
        assert frozen['variant']==args.variant and frozen['new_outputs_reviewed'] is False
        selected=rows
    # Reuse the registered disposable scope owner; no product files or model copies.
    work=prior.register_work()
    report=dict(stage=args.stage,source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                code_hashes=code_hashes(),dataset_sha256=DATA_HASH,runs=[],status='IN_PROGRESS',human_acceptance='NOT_CONDUCTED')
    started=time.monotonic()
    def save():
        report['elapsed_seconds']=round(time.monotonic()-started,3)
        target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    save()
    if args.stage=='baseline':
        prior.baseline(selected,work,report,save)
    else:
        assert prior.digest(MODEL)==prior.MODEL_HASH
        report.update(model_sha256=prior.MODEL_HASH,runtime_sha256=prior.digest(CLI.with_name('llama-completion.exe')))
        for row in selected:
            for variant in variants:
                prompt,ids,p=make_prompt(row,rows,variant)
                run=run_one(prompt,work,row['id']+'-'+variant,no_repack=True,max_tokens=128,completion=True)
                run.update(id=row['id'],source=row['source_en'],split=row['split'],group=row['group'],variant=variant,context_ids=ids)
                if run['status']=='RETURNED':
                    run['raw_translation']=completion_output(run['stdout'])
                    try:
                        raw=run['raw_translation']
                        if variant=='transport':
                            derived,rule=paraphrase_logic(p.masked)
                            roles=mask_roles(derived,row.get('address_context',''))
                            run.update(derived_source=derived,logic_rule=rule,role_replacements=roles.replacements)
                            raw=restore_roles(roles,raw)
                        run['output']=restore(p,raw)
                        if variant=='transport' and relationship_contradictions(row.get('address_context',''),run['output']):
                            raise ValueError('explicit sibling age contradiction')
                        run['guard_status']='ACCEPTED'
                        run['semantic_flags']=semantic_flags(row,run['output'])
                    except ValueError as exc:
                        run.update(output='',guard_status='REJECTED',guard_reason=str(exc))
                report['runs'].append(run);save()
                print(row['id'],variant,run['status'],run.get('guard_status'),flush=True)
                if run['status']!='RETURNED':
                    report['status']=run['status'];save();return 1
        report['model_unchanged']=prior.digest(MODEL)==prior.MODEL_HASH
        assert report['model_unchanged']
    report['status']='COMPLETED';save()
    return 0


if __name__=='__main__':
    raise SystemExit(main())
