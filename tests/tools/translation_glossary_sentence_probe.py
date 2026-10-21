"""One bounded complete-sentence glossary transport probe on three seen sources."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import argparse

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--numeric',action='store_true');numeric=parser.parse_args().numeric
    from tests.lib.work_paths import work_temp_dir
    from tests.tools import translation_quality_phase1 as old
    from tests.tools.translation_goal_audit import GLOSSARY,EVIDENCE
    from vntext.package_glossary import mask_user_glossary_terms
    from vntext.mt_ct2_model import Ct2Translator
    from vntext.mt_check import structural_problems
    target=EVIDENCE/('sentence-probe-numeric.json' if numeric else 'sentence-probe.json')
    if target.exists():raise FileExistsError(target)
    work=work_temp_dir('glossary-sentence-probe')
    for name in ('TEMP','TMP','TMPDIR'):os.environ[name]=str(work)
    old._configure_offline_cache();dataset,_,_=old.load_dataset()
    rows=[r for r in dataset['rows'] if r['id'] in ['TERM-001','TERM-004','TERM-014']]
    model=old._model_identity();translator=Ct2Translator(old.MODEL_DIR)
    report=dict(source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        model=model,rows=[],status='RUN_STARTED',human_gold=False)
    def save():target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save();started=time.monotonic()
    for row in rows:
        source=row['source_en'];masked,restores=mask_user_glossary_terms(source,GLOSSARY)
        wrapped={token:'{'+str(i)+'}' if numeric else '{'+token+'}' for i,token in enumerate(restores)}
        for token,value in wrapped.items():masked=masked.replace(token,value)
        raw=translator.translate(masked);errors=structural_problems({'source_text':masked},raw)
        if any(raw.count(wrapped[token])!=masked.count(wrapped[token]) for token in restores):errors.append('carrier occurrence changed')
        draft=raw
        if not errors:
            for token,target_text in restores.items():draft=draft.replace(wrapped[token],target_text)
            errors.extend(structural_problems({'source_text':source},draft))
        report['rows'].append(dict(id=row['id'],source=source,model_input=masked,raw=raw,draft=draft,errors=errors))
        save()
    report['seconds']=time.monotonic()-started;report['model_unchanged']=old._model_identity()['tree_sha256']==model['tree_sha256'];assert report['model_unchanged']
    report['status']='COMPLETED';save()
    print(json.dumps(report['rows'],ensure_ascii=False))


if __name__=='__main__':main()
