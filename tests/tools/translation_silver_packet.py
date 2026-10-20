"""Offline Phase19 evidence packaging/verification; never imports inference code."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PACKET = ROOT / 'evaluation/translation_silver_packet_v1'
DATA = ROOT / 'evaluation/translation_quality_phase19/dataset.v1.json'
EXPECTED_DATA = '085c0731f7ca5c1ed3fcc6342c882516c1c95d66d5d82ac47ca49dd78b6013ee'
SNAPSHOTS = ('blind-input.json', 'blind-review.json', 'sealed-label-map.json',
             'coordinator-blind-audit.json', 'blind-rubric.json', 'blind-seal.json',
             'selection.json', 'unmasked-review.json')
AUDIT_NOTES = {
    'Q19-dialogue-08': 'Both lose past counterfactual; original major/major retained.',
    'Q19-idiom-06': 'Original A acceptable remains original; historical override A uncertain records invented listener/future lottery event.',
    'Q19-address-02': 'Historical B acceptable->minor loses dinner specificity; keep ownership/roles finding separate.',
    'Q19-address-08': 'Candidate reverses giver/receiver; OPUS omits relative clause. Neither is positive memory.',
    'Q19-address-10': 'Application kind and professor gender are underspecified; both uncertain retained.',
    'Q19-ui-04': 'Historical acceptable/acceptable retained. Current conservative exclusion: undone->huy bo may mean cancellation rather than undo. No new categorical severity or repaired output claimed.',
    'Q19-ui-08': 'Keep original A minor and historical A->major for untranslated Restore; B discard->skip remains major. Original winner A is not acceptance.',
    'Q19-terminology-04': 'OPUS drive->lock changes object; candidate acceptable remains agent judgment.',
    'Q19-terminology-05': 'Candidate cancellation loses rollback. Original B minor and historical B->major remain separate; original winner B is not acceptance.',
    'Q19-terminology-06': 'Candidate invoice->receipt is major; OPUS acceptable does not justify selecting aggregate Hy winner.',
    'Q19-terminology-08': 'Candidate sensor->switch is major; OPUS minor naturalness retained.',
    'Q19-protected_tokens-02': 'Empty OPUS output is unusable workflow coverage, not a paired semantic mistranslation. No memory positive from this row.',
}
TERM_RULES = {
    'checksum': ('file integrity', 'ordinary check/payment sum is not a checksum', 'candidate'),
    'migration': ('ordered database/data-record migration', 'human/bird migration is not data migration', 'candidate'),
    'copy': ('file-copy imperative preserving literal placeholders', 'copy as publication text is not a file-copy command', 'candidate'),
    'archive': ('archive storage versus compressed archive file unresolved', 'historical target may name a repository rather than an archive file', 'exclude_sense_unresolved'),
    'backup': ('backup artifact in undo/delete operation', 'undo must not silently become cancel', 'exclude_current_row_concern'),
    'cancel': ('cancel a trip/action', 'cancel algebraically or undo a completed change differs', 'exclude_phrase_not_exact_target'),
}
DOMAINS = {
    'manifest': ('artifact inventory', 'political manifesto'),
    'cache': ('software cache', 'hidden physical supply'),
    'glossary': ('translation term list', 'approved target list requires separate rights/review'),
    'CSV': ('literal format name', 'literal token is not a translation quality claim'),
    'placeholder': ('technical format/variable token', 'temporary person/object'),
    'patch': ('software patch artifact', 'cloth/skin patch'),
    'locator': ('data locator', 'physical locating device'),
    'fingerprint': ('artifact/content identity hash', 'biometric fingerprint'),
    'parser': ('software syntax parser', 'human interpreting a statement'),
    'sidecar': ('companion metadata file', 'motorcycle sidecar'),
    'worker': ('software worker process', 'human employee'),
    'read-only': ('software access mode', 'a request to read something'),
    'preview': ('software preview', 'movie trailer'),
    'export': ('software data export', 'international trade'),
    'journal': ('software event journal', 'academic journal'),
    'shortcut': ('keyboard shortcut', 'physical shorter route'),
    'badge': ('UI indicator', 'physical police badge'),
    'overwrite': ('replace file/content', 'write too extensively'),
    'overwriting': ('replacing file/content', 'excessive writing'),
    'reject': ('reject candidate/input', 'reject person socially'),
    'unverified': ('verification status', 'not a semantic approval label'),
    'unchecked': ('not yet checked', 'unchecked checkbox differs from verification'),
    'release': ('software release', 'release physical restraint'),
    'signature': ('digital artifact signature', 'handwritten signature'),
    'canceling': ('cancel operation gerund', 'algebraic cancellation'),
    'aborting': ('abort running operation', 'medical context'),
    'tablet': ('computing device', 'medicine tablet'),
    'charger': ('electrical charger', 'animal/vehicle'),
    'outline': ('document outline', 'geometric contour'),
    'patching': ('software patch operation', 'mending fabric'),
    'eligible': ('explicit eligibility condition', 'not blanket permission'),
    'unresolved': ('unresolved review item', 'not rejected or accepted by default'),
    'snapshot': ('state snapshot', 'photograph'),
    'upload': ('data transfer upward', 'publication is a separate permission'),
    'rollback': ('transaction undo', 'physical rolling backward'),
    'table': ('database/data table', 'furniture'),
    'stopping': ('interrupting a running operation', 'successfully completing it'),
    'rollback data': ('data needed for undo', 'data generated during undo'),
    'collection': ('data collection/set', 'collecting payment'),
    'permitted': ('explicitly allowed set', 'general approval not inferred'),
    'file transfer': ('file transmission', 'legal transfer of ownership'),
    'verified': ('checked correctness', 'mere acknowledgment'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def canonical(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def packet_rows(dataset, outputs, review, mapping, audit):
    blind = {r['id']: r for r in review['records']}
    hy = {r['id']: r for r in outputs['candidate_rows']}
    arms = {a: {r['id']: r for r in records} for a, records in outputs['opus_rows'].items()}
    rows = []
    for source in dataset['rows']:
        rid = source['id']; original = blind[rid]
        overrides = [o for o in audit['overrides'] if o['id'] == rid]
        verdicts = {mapping[rid][label]: original[label]['verdict'] for label in ('A', 'B')}
        for override in overrides:
            verdicts[mapping[rid][override['label']]] = override['to_verdict']
        disposition = {arm: 'retain_silver' if grade == 'acceptable' else
                       'uncertain' if grade == 'uncertain' else 'reject_positive_reuse'
                       for arm, grade in verdicts.items()}
        concern_reason = {'Q19-ui-04':'current undo/cancel concern',
                          'Q19-dialogue-06':'unsupported masculine listener address with empty address context'}.get(rid)
        concern = concern_reason is not None
        memory = set(verdicts.values()) == {'acceptable'} and not concern
        rows.append(dict(id=rid, source=source, use='seen_development_regression_only',
            source_rights=dataset['provenance'], rights_status='KNOWN_generated_for_project_source',
            outputs=dict(candidate=hy[rid], opus_unassisted=arms['unassisted'][rid],
                         opus_glossary=arms['glossary'][rid]),
            original_blind_review=original, label_map=mapping[rid],
            historical_coordinator_adjustments=overrides,
            audited_verdicts=verdicts, disposition=disposition,
            current_audit= AUDIT_NOTES.get(rid),
            current_conservative_exclusion=concern,
            memory_eligible=memory,
            memory_exclusion_reason=None if memory else
                concern_reason if concern else
                'both compared arms must have acceptable historical audited verdicts',
            label='agent-reviewed silver; needs-human-review', human_gold=False,
            approved=False, training_eligible=False))
    return rows


def terms_and_memory(rows, bank):
    audited = []; candidates = []
    for term, target in bank.items():
        hits = [r for r in rows if re.search(r'(?<!\w)'+re.escape(term)+r'(?!\w)', r['source']['source_en'], re.I)]
        if term in TERM_RULES:
            domain, counter, status = TERM_RULES[term]
        else:
            domain, counter = DOMAINS[term]; status = 'exclude_no_phase19_source_occurrence'
        positives = []
        for row in hits:
            for arm, grade in row['audited_verdicts'].items():
                text = row['outputs']['candidate']['draft'] if arm == 'candidate' else row['outputs']['opus_glossary']['output']
                if grade == 'acceptable' and re.search(r'(?<!\w)'+re.escape(target)+r'(?!\w)', text, re.I):
                    positives.append(dict(id=row['id'], arm=arm, source=row['source']['source_en'], target_output=text))
        record = dict(source_term=term, historical_target=target,
            bank_provenance='evidence/outputs.json#/term_bank', domain_scope=domain,
            counter_sense=counter, counter_sense_status='manual_scope_design_NOT_model_tested',
            occurrence_ids=[r['id'] for r in hits], positive_observations=positives,
            disposition=status, label='silver_candidate_only; needs-human-review',
            approved=False, training_eligible=False)
        if status == 'candidate':
            assert positives
            candidates.append(record)
        audited.append(record)
    memory = []
    for index,row in enumerate(rows):
        if not row['memory_eligible']: continue
        # Fixed evidence policy: both reviewed arms acceptable, prefer existing OPUS
        # glossary draft; do not select using aggregate model score or preference.
        text = row['outputs']['opus_glossary']['output']
        if not text: continue
        key = dict(source_en=row['source']['source_en'],
                   domain_context=row['source'].get('domain_context', ''),
                   address_context=row['source'].get('address_context', ''),
                   scenario_boundary=row['source']['scenario_boundary'])
        memory.append(dict(id=row['id'], exact_match_key=key, key_sha256=canonical(key),
            target=text, output_arm='opus_glossary', source_rights=row['source_rights'],
            provenance=dict(file='curation.json',json_pointer=f'/rows/{index}',record_id=row['id']),
            label='agent-reviewed silver; needs-human-review', approved=False,
            human_gold=False, training_eligible=False, product_import_allowed=False))
    return audited, candidates[:12], memory[:20]


def build(source):
    if PACKET.exists(): raise FileExistsError('Packet already exists; never overwrite evidence')
    dataset = read(DATA); assert sha(DATA) == EXPECTED_DATA
    baseline = read(source/'baseline.json'); final = read(source/'final.json')
    inputs = {name: read(source/name) for name in SNAPSHOTS}
    assert baseline['status'] == final['status'] == 'COMPLETED'
    assert baseline['dataset_sha256'] == final['dataset_sha256'] == EXPECTED_DATA
    assert baseline['term_bank'] == final['term_bank'] and len(final['term_bank']) == 48
    assert final['code_hashes'] == inputs['selection.json']['code_hashes']
    outputs = dict(candidate_rows=final['rows'],
        opus_rows={a['name']: a['rows'] for a in baseline['arms']}, term_bank=final['term_bank'])
    rows = packet_rows(dataset, outputs, inputs['blind-review.json'],
                       inputs['sealed-label-map.json'], inputs['coordinator-blind-audit.json'])
    terms, candidates, memory = terms_and_memory(rows, final['term_bank'])
    PACKET.mkdir(); evidence = PACKET/'evidence'; evidence.mkdir()
    for name in SNAPSHOTS:
        (evidence/name).write_bytes((source/name).read_bytes())
    write(evidence/'outputs.json', outputs)
    identities = {}
    for name in ('baseline.json', 'final.json'):
        run = baseline if name == 'baseline.json' else final
        identities[name] = dict(original_file_sha256=sha(source/name),
            historical_locator='DEV_RUN/translation-quality-phase19/'+name,
            source_sha=run['source_sha'], code_hashes=run['code_hashes'],
            dataset_sha256=run['dataset_sha256'], status=run['status'],
            model_identity= {k: run[k] for k in ('model_sha256','runtime_sha256','model_unchanged') if k in run}
                if name == 'final.json' else run['opus_model'],
            projection_sha256=canonical(outputs['candidate_rows'] if name == 'final.json' else outputs['opus_rows']),
            note='Full original file hash is historical provenance, not recomputable from compact projection; embedded rows are exact JSON values, no new run.')
    write(evidence/'run-identities.json', identities)
    write(PACKET/'curation.json', dict(rows=rows))
    write(PACKET/'term-audit.json', dict(records=terms))
    write(PACKET/'candidate-bank.json', dict(records=candidates))
    write(PACKET/'memory-candidate.json', dict(records=memory))
    write(PACKET/'audit12.json', dict(kind='current DEV source/mapping/severity audit; not human gold',
        records=[dict(id=rid, note=note) for rid,note in AUDIT_NOTES.items()]))
    write(PACKET/'manifest.json', dict(schema_version=1,
        source_base=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT,text=True).strip(),
        source_dataset=dict(path='evaluation/translation_quality_phase19/dataset.v1.json',sha256=sha(DATA),
                            rights_pointer='/provenance', provenance=dataset['provenance']),
        builder='tests/tools/translation_silver_packet.py',
        builder_sha256=sha(__file__),
        budget='0 monetary spend; DEV<=5h; Brain read-only audit<=1h',
        use='seen development/regression research ONLY',
        model_generated_targets_rights='Model identities and historical license pointers in README; no human authorship or publication/training authorization inferred from source rights.',
        counts=dict(sources=len(rows),audited_rows=len(AUDIT_NOTES),terms=len(terms),
                    candidate_terms=len(candidates),memory=len(memory)),
        human_gold=False,approved=False,training_eligible=False,
        files={str(p.relative_to(PACKET)).replace('\\','/'):sha(p) for p in sorted(PACKET.rglob('*.json'))}))
    return verify(PACKET)


def verify(packet):
    manifest = read(packet/'manifest.json')
    assert sha(__file__)==manifest['builder_sha256'], 'builder identity mismatch'
    actual={str(p.relative_to(packet)).replace('\\','/') for p in packet.rglob('*') if p.is_file() and p.name!='manifest.json'}
    assert set(manifest['files'])==actual, 'unlisted/missing packet payload'
    for name, digest in manifest['files'].items():
        path = packet/name
        assert path.resolve().is_relative_to(packet.resolve()), 'unsafe packet path'
        assert sha(path) == digest, f'content hash mismatch: {name}'
    assert sha(DATA) == manifest['source_dataset']['sha256'] == EXPECTED_DATA
    dataset=read(DATA); e=packet/'evidence'; output=read(e/'outputs.json')
    assert dataset['provenance']['rights']=='generated-for-project'
    assert manifest['source_dataset']['provenance']==dataset['provenance']
    assert manifest['approved'] is manifest['human_gold'] is manifest['training_eligible'] is False
    review=read(e/'blind-review.json'); mapping=read(e/'sealed-label-map.json')
    audit=read(e/'coordinator-blind-audit.json'); seal=read(e/'blind-seal.json')
    for name,key in [('blind-input.json','blind_input_sha256'),('blind-rubric.json','rubric_sha256'),('sealed-label-map.json','sealed_mapping_sha256')]:
        assert sha(e/name)==seal[key], f'seal mismatch: {name}'
    assert sha(e/'blind-review.json')==audit['blind_review_sha256']
    assert sha(e/'blind-input.json')==audit['blind_input_sha256']
    unmasked=read(e/'unmasked-review.json')
    assert sha(e/'blind-review.json')==unmasked['blind_review_sha256']
    assert sha(e/'coordinator-blind-audit.json')==unmasked['coordinator_blind_audit_sha256']
    assert review['mapping_seen'] is False
    rows=packet_rows(dataset,output,review,mapping,audit)
    assert len(rows)==len({r['id'] for r in rows})==60
    assert Counter(r['source']['group'] for r in rows)==Counter(dict.fromkeys(['dialogue','idiom','address','ui','terminology','protected_tokens'],10))
    observed={r['id']:r for r in read(e/'blind-input.json')['records']}
    for row in rows:
        rid=row['id']; original=observed[rid]
        assert original['source_en']==row['source']['source_en']==row['outputs']['candidate']['source']
        for arm in ('opus_glossary','opus_unassisted'):
            assert row['outputs'][arm]['source']==original['source_en']
        for label,arm in mapping[rid].items():
            actual=row['outputs']['candidate']['draft'] if arm=='candidate' else row['outputs']['opus_glossary']['output']
            assert actual==original[label], (rid,label,'raw/mapping mismatch')
    assert read(packet/'curation.json')['rows']==rows, 'curation derivation mismatch'
    assert read(packet/'audit12.json')['records']==[dict(id=rid,note=note) for rid,note in AUDIT_NOTES.items()]
    terms,bank,memory=terms_and_memory(rows,output['term_bank'])
    assert len(terms)==48 and len(bank)<=12 and len(memory)<=20
    for name,records in [('term-audit.json',terms),('candidate-bank.json',bank),('memory-candidate.json',memory)]:
        assert read(packet/name)['records']==records, f'policy mismatch: {name}'
    for record in memory:
        locator=record['provenance']
        assert locator['file']=='curation.json'
        resolved=read(packet/locator['file'])
        for component in locator['json_pointer'].split('/')[1:]:
            resolved=resolved[int(component)] if isinstance(resolved,list) else resolved[component]
        assert resolved['id']==locator['record_id']==record['id']
        assert record['target']==resolved['outputs']['opus_glossary']['output']
        assert record['exact_match_key']['source_en']==resolved['source']['source_en']
    for run,key in [('final.json','candidate_rows'),('baseline.json','opus_rows')]:
        identity=read(e/'run-identities.json')[run]
        assert identity['dataset_sha256']==EXPECTED_DATA
        assert identity['projection_sha256']==canonical(output[key])
        assert identity['source_sha']==seal['source_base']
        assert identity['code_hashes']==read(e/'selection.json')['code_hashes']
    counts=dict(sources=len(rows),audited_rows=len(AUDIT_NOTES),terms=len(terms),candidate_terms=len(bank),memory=len(memory))
    assert manifest['counts']==counts
    return dict(status='PASS',counts=counts,new_model_runs=0,human_gold=False,
                memory_ids=[r['id'] for r in memory],audit12_ids=list(AUDIT_NOTES),
                dispositions=dict(Counter(v for r in rows for v in r['disposition'].values())))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['build','verify'])
    parser.add_argument('--source',type=Path,default=ROOT/'DEV_RUN/translation-quality-phase19')
    args=parser.parse_args()
    print(json.dumps(build(args.source) if args.action=='build' else verify(PACKET),ensure_ascii=False,indent=2))
