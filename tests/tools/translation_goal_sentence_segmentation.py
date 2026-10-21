"""Bounded, test-only long-prose segmentation probe. No production hook."""
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def candidate_units(text):
    """Return reconstructible cores/separators, or abstain on ambiguous syntax.

    These lexical guards do NOT certify discourse independence; this helper is
    an experiment, not a semantic validator or a default product policy.
    """
    if len(text) < 800 or re.search(r'''[0-9{}<>\[\]()\\"']''', text):
        return None
    if re.search(r'\b(?:[A-Z]|Dr|Mr|Mrs|Ms|Prof|Capt|St|etc|vs|e\.g|i\.e|Professor|Captain|Doctor)\.', text, re.IGNORECASE):
        return None
    from vntext.mt_check import source_proper_name_tokens
    if source_proper_name_tokens(text):
        return None
    units=[]
    last=0
    for match in re.finditer(r'(?<=\.)[ \t\r\n]+(?=[A-Z])', text):
        units.append((text[last:match.start()], match.group(0)))
        last=match.end()
    units.append((text[last:], ''))
    if len(units)<3:
        return None
    for core, _separator in units:
        if len(core)>300 or not re.match(r'^(?:A|An|The)\s+[a-z]', core):
            return None
        if re.match(r'^(?:A|An|The)\s+(?:same|latter|former|other|next|previous)\b',core):
            return None
    assert ''.join(core+separator for core,separator in units)==text
    return units


def main():
    from tests.lib.work_paths import work_temp_dir
    from tests.tools import translation_quality_phase1 as old
    from vntext.mt_ct2_model import Ct2Translator
    from vntext.mt_check import structural_problems
    raw=ROOT/'DEV_RUN/translation-quality-goal/longtext-before.json'
    before=json.loads(raw.read_text(encoding='utf-8'))
    source=before['sources'][0][1]
    short=before['sources'][1][1]
    units=candidate_units(source)
    assert units and len(units)==17
    controls={
        'short':short,
        'placeholder':source+' Keep {mode}.',
        'tag':source+' Keep <b>text</b>.',
        'escape':source+r' Keep\ntext.',
        'decimal':source+' A version is 2.4.',
        'abbreviation':'Dr. Smith waits. '+source,
        'name':source+' The guard helps Mara.',
        'quote':source+' A guard says "wait."',
        'anaphora':source+' The latter must stay unchanged.',
    }
    for name,text in controls.items():
        assert candidate_units(text) is None,name
    mixed=source.replace('. ','.\n',1)
    mixed_units=candidate_units(mixed)
    assert mixed_units and ''.join(a+b for a,b in mixed_units)==mixed
    work=work_temp_dir('translation-goal-sentence-segmentation')
    for name in ('TEMP','TMP','TMPDIR'):os.environ[name]=str(work)
    old._configure_offline_cache()
    model=old._model_identity()
    assert model['tree_sha256']==before['model']['tree_sha256']
    output=ROOT/'DEV_RUN/translation-quality-goal/sentence-segmentation.json'
    assert not output.exists()
    translator=Ct2Translator(old.MODEL_DIR)
    translated=translator.translate_many([core for core,_sep in units]+[short])
    assert len(translated)==len(units)+1
    assert translated[-1]==before['rows'][1]['translation']
    joined=''.join(target+separator for target,(_core,separator) in zip(translated,units))
    assert not structural_problems({'source_text':source},joined)
    assert old._model_identity()['tree_sha256']==model['tree_sha256']
    report=dict(status='MEASURED_NOT_ADMITTED',model_tree_sha256=model['tree_sha256'],
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                original_report_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
                source=source,before=before['rows'][0]['translation'],after=joined,
                units=[dict(source=core,separator=separator,target=target)
                       for (core,separator),target in zip(units,translated)],
                controls={name:'ABSTAIN_ORIGINAL_ROUTE' for name in controls},
                source_reconstruction=True,newline_separator_reconstruction=True,
                short_control_unchanged=True,structural_reasons=[],human_gold=False,
                semantic_acceptance=False,
                qualification='Lexical guards do not prove discourse independence; no product policy or glossary/memory path changed.')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],units=len(units),output=str(output))))


if __name__=='__main__':
    main()
