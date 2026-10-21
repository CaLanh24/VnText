"""One seen-source comparison of existing split and full-sentence seams."""
import hashlib
import json
import os
from pathlib import Path
import time
from tests.lib.work_paths import work_temp_dir
from tests.tools import translation_quality_phase1 as provenance
from vntext.mt_ct2_model import Ct2Translator
from vntext.mt_ct2_io import _batch_translate_chunk
from vntext.mt_check import structural_problems


def main():
    root=Path.cwd();out=Path.home()/'Downloads/VM-Acceptance/semantic-relation-comparison.json';assert not out.exists()
    path=root/'evaluation/translation_semantic_campaign_v1/relation-frozen.json';frozen=path.read_bytes();data=json.loads(frozen)
    work=work_temp_dir('semantic-relation-comparison')
    for key in ('TEMP','TMP','TMPDIR'):os.environ[key]=str(work)
    provenance._configure_offline_cache();os.environ.update(VNTEXT_CT2_NO_DOWNLOAD='1',VNTEXT_CT2_INTER_THREADS='1',VNTEXT_CT2_INTRA_THREADS='1')
    report=dict(status='RUN_STARTED',frozen_sha256=hashlib.sha256(frozen).hexdigest(),model=provenance._model_identity(),calls=[],rows=[],memory=[])
    started=time.monotonic()
    def save():out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def guard():
        m=provenance._windows_process_memory();report['memory'].append(m)
        assert m['available']and m['peak_working_set_bytes']<1610612736
        assert time.monotonic()-started<110
    save()
    try:
        t=Ct2Translator(provenance.MODEL_DIR);backend=t._translator;guard()
        class Capture:
            def translate_batch(self,tokens,**kwargs):
                guard();assert sum(len(x['input_tokens'])for x in report['calls'])+len(tokens)<=8
                results=backend.translate_batch(tokens,**kwargs)
                report['calls'].append(dict(input_tokens=tokens,output_tokens=[r.hypotheses[0]for r in results],kwargs=kwargs));save();return results
        t._translator=Capture()
        for item in data['rows']:
            row=dict(key=item['id'],source_text=item['source'],file_path='seen-relations.txt',context=item['id'],import_method='plain_text_line')
            split=_batch_translate_chunk(t,[row])[row['key']]
            full=t.translate(item['source'])
            report['rows'].append(dict(id=item['id'],source=item['source'],product_split=split,full_sentence=full,split_structure=structural_problems(row,split),full_structure=structural_problems(row,full),split_names_exact=all(n in split for n in item['required_names']),full_names_exact=all(n in full for n in item['required_names'])))
            guard();save()
        assert path.read_bytes()==frozen and provenance._model_identity()['tree_sha256']==report['model']['tree_sha256']
        report.update(status='COMPLETED_FOR_SOURCE_ALIGNED_REVIEW',elapsed_seconds=time.monotonic()-started)
    except BaseException as err:report.update(status='FAILED',error=repr(err));raise
    finally:save()
    print(report['status'])


if __name__=='__main__':main()
