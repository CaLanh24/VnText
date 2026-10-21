"""One fixed supported target-prefix diagnostic; no product policy change."""
import hashlib
import json
import os
from pathlib import Path
import time
from tests.lib.work_paths import work_temp_dir
from tests.tools import translation_quality_phase1 as provenance
from vntext.mt_ct2_model import Ct2Translator
from vntext.mt_check import structural_problems, source_proper_name_tokens


def main():
    root=Path.cwd();e=Path.home()/'Downloads/VM-Acceptance';out=e/'semantic-prefix-comparison.json';assert not out.exists()
    source=root/'evaluation/translation_semantic_campaign_v1/relation-frozen.json'
    definition=root/'evaluation/translation_semantic_campaign_v1/prefix-frozen.json'
    frozen=source.read_bytes();spec=definition.read_bytes();data=json.loads(frozen)
    assert json.loads(spec)['relation_source_sha256']==hashlib.sha256(frozen).hexdigest()
    work=work_temp_dir('semantic-prefix-comparison')
    for name in ['TEMP','TMP','TMPDIR']:os.environ[name]=str(work)
    provenance._configure_offline_cache();os.environ.update(VNTEXT_CT2_NO_DOWNLOAD='1',VNTEXT_CT2_INTER_THREADS='1',VNTEXT_CT2_INTRA_THREADS='1')
    report=dict(status='RUN_STARTED',source_sha256=hashlib.sha256(frozen).hexdigest(),definition_sha256=hashlib.sha256(spec).hexdigest(),model=provenance._model_identity(),rows=[],memory=[])
    started=time.monotonic()
    def save():out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def guard():
        m=provenance._windows_process_memory();report['memory'].append(m)
        assert m['available']and m['peak_working_set_bytes']<1610612736
        assert time.monotonic()-started<110
    save()
    try:
        t=Ct2Translator(provenance.MODEL_DIR);tok=t._tokenizer;guard()
        for item in data['rows']:
            assert len(report['rows'])<4
            name=item['required_names'][0];assert item['source'].startswith(name+' ') and name.casefold() in source_proper_name_tokens(item['source'])
            prefix_ids=tok(text_target=name,add_special_tokens=False)['input_ids']
            assert tok.decode(prefix_ids,skip_special_tokens=True)==name
            prefix=tok.convert_ids_to_tokens(prefix_ids)
            encoded=tok.convert_ids_to_tokens(tok.encode(t._model_input(item['source']),add_special_tokens=True))
            guard();begin=time.monotonic()
            result=t._translator.translate_batch([encoded],target_prefix=[prefix],batch_type='tokens',max_batch_size=t._max_batch_size)[0]
            text=tok.decode(tok.convert_tokens_to_ids(result.hypotheses[0]),skip_special_tokens=True)
            report['rows'].append(dict(id=item['id'],source=item['source'],name=name,prefix_tokens=prefix,input_tokens=encoded,output_tokens=result.hypotheses[0],translation=text,structure=structural_problems(dict(source_text=item['source']),text),names_exact=all(n in text for n in item['required_names']),elapsed_seconds=time.monotonic()-begin));guard();save()
        assert source.read_bytes()==frozen and definition.read_bytes()==spec
        assert provenance._model_identity()['tree_sha256']==report['model']['tree_sha256']
        report.update(status='COMPLETED_FOR_SOURCE_ALIGNED_REVIEW',elapsed_seconds=time.monotonic()-started)
    except BaseException as err:report.update(status='FAILED',error=repr(err));raise
    finally:save()
    print(report['status'])


if __name__=='__main__':main()
