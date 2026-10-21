"""Real CT2 product-path output-budget capture, no fabricated model outputs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['before','after']);stage=parser.parse_args().stage
    from tests.lib.work_paths import work_temp_dir
    from tests.tools import translation_quality_phase1 as old
    from vntext.mt_ct2_model import Ct2Translator
    from vntext.mt_ct2_pipeline import run_ct2_translate
    from vntext.package_io import write_package,read_csv_rows_file
    from vntext.entry import Entry
    from vntext.mt_check import structural_problems
    target=ROOT/'DEV_RUN/translation-quality-goal'/('longtext-'+stage+'.json')
    if target.exists():raise FileExistsError(target)
    work=work_temp_dir('translation-goal-longtext-'+stage)
    for name in ('TEMP','TMP','TMPDIR'):os.environ[name]=str(work)
    old._configure_offline_cache();dataset,_,_=old.load_dataset()
    source=' '.join(r['source_en'] for r in dataset['rows'] if r['id'].startswith('TERM-'))
    rows=[('long',source),('short','The red door is open.')]
    report=dict(stage=stage,status='RUN_STARTED',source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        code_hashes={str(p):hashlib.sha256((ROOT/p).read_bytes()).hexdigest()for p in ['vntext/mt_ct2_model.py','vntext/mt_model_adapter.py','vntext/mt_check.py','vntext/mt_ct2_pipeline.py','tests/tools/translation_goal_longtext.py']},
        sources=rows,rights='all source sentences are existing project synthetic, reused technical length fixture, not a new quality benchmark',
        model=old._model_identity(),calls=[])
    def save():target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    translator=Ct2Translator(old.MODEL_DIR);backend=translator._translator
    class Capture:
        def translate_batch(self,tokens,**kwargs):
            results=backend.translate_batch(tokens,**kwargs)
            report['calls'].append(dict(input_lengths=[len(t) for t in tokens],
                output_lengths=[len(r.hypotheses[0])for r in results],
                last_tokens=[r.hypotheses[0][-3:]for r in results],kwargs=kwargs,
                effective_max_decoding_length=kwargs.get('max_decoding_length',256)))
            save();return results
    translator._translator=Capture();save()
    package=work/'package'
    entries=[Entry(key=k,source_text=s,file_path='synthetic/longtext.txt',context=k,import_method='plain_text_line',safety='safe',locator={'line':i},backend='synthetic').finalize()for i,(k,s)in enumerate(rows,1)]
    write_package(str(package),entries,[],{'files_scanned':1},separate_review=False,enable_trace=True)
    fields,before=read_csv_rows_file(package/'translation.csv')
    try:
        # Only instrumentation replaces factory lookup; Capture delegates every
        # actual backend call to the original loaded CT2 weights/runtime.
        with patch('vntext.mt_ct2_model.get_translator',return_value=translator):
            result=run_ct2_translate(package/'translation.csv',model_dir=old.MODEL_DIR)
        after_fields,after=read_csv_rows_file(package/'translation.csv')
        assert fields==after_fields and [(r['key'],r['source_text']) for r in before]==[(r['key'],r['source_text'])for r in after]
        assert not any(structural_problems(r,r['translation'])for r in after if r['translation'])
        report.update(result=result,rows=after,fields=fields,source_order_schema_unchanged=True,
            model_unchanged=old._model_identity()['tree_sha256']==report['model']['tree_sha256'])
        assert report['model_unchanged']
        if stage=='after':
            original=json.loads((target.parent/'longtext-before.json').read_text(encoding='utf-8'))
            assert json.loads(json.dumps(rows))==original['sources']
            assert report['model']['tree_sha256']==original['model']['tree_sha256']
            assert after[1]['translation']==original['rows'][1]['translation']
        report['status']='COMPLETED'
    except BaseException as error:
        report['status']='FAILED';report['error']=repr(error);raise
    finally:save()
    print(json.dumps(dict(status=report['status'],calls=report['calls'],translations=[dict(key=r['key'],translation=r['translation'])for r in after]),ensure_ascii=False))


if __name__=='__main__':main()
