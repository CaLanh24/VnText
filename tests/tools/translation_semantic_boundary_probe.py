"""Measure the existing long-input budget path without changing any policy."""
import hashlib
import json
import os
from pathlib import Path
import time
import argparse
import difflib
from tests.lib.work_paths import work_temp_dir
from tests.tools import translation_quality_phase1 as provenance
from vntext.mt_ct2_model import Ct2Translator, _split_text_under_token_limit


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['before','after'],default='before',nargs='?');stage=parser.parse_args().stage
    root=Path.cwd();e=Path.home()/'Downloads/VM-Acceptance'
    output=e/f'semantic-boundary-{stage}.json';assert not output.exists()
    frozen=root/'evaluation/translation_semantic_campaign_v1/boundary-frozen.json'
    frozen_bytes=frozen.read_bytes();data=json.loads(frozen_bytes)
    work=work_temp_dir('semantic-boundary-'+stage)
    for name in ('TEMP','TMP','TMPDIR'):os.environ[name]=str(work)
    provenance._configure_offline_cache()
    os.environ.update(VNTEXT_CT2_NO_DOWNLOAD='1',VNTEXT_CT2_INTER_THREADS='1',VNTEXT_CT2_INTRA_THREADS='1')
    r=dict(status='RUN_STARTED',frozen_sha256=hashlib.sha256(frozen_bytes).hexdigest(),model=provenance._model_identity(),calls=[],rows=[],memory=[])
    r['code_hashes']={n:hashlib.sha256((root/n).read_bytes()).hexdigest()for n in ['vntext/mt_ct2_model.py','tests/tools/translation_semantic_boundary_probe.py']}
    def save():output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    started=time.monotonic()
    def guard():
        m=provenance._windows_process_memory();r['memory'].append(m)
        assert m['available'] and m['peak_working_set_bytes']<1610612736,m
        assert time.monotonic()-started<170
    save()
    try:
        t=Ct2Translator(provenance.MODEL_DIR);backend=t._translator;guard()
        class Capture:
            def translate_batch(self,tokens,**kwargs):
                guard();assert sum(len(x['input_lengths'])for x in r['calls'])+len(tokens)<=12
                result=backend.translate_batch(tokens,**kwargs)
                r['calls'].append(dict(input_lengths=[len(x)for x in tokens],output_lengths=[len(x.hypotheses[0])for x in result],last_tokens=[x.hypotheses[0][-4:]for x in result],kwargs=kwargs));save();return result
        t._translator=Capture()
        for row in data['rows']:
            parts=_split_text_under_token_limit(row['source'],t._input_token_len,max_tokens=t._max_src_tokens)
            assert ''.join(parts)==row['source']
            if row['id']=='long-events':assert len(parts)>1
            translated=t.translate(row['source']);guard()
            r['rows'].append(dict(id=row['id'],source=row['source'],source_tokens=t._input_token_len(row['source']),parts=parts,translation=translated))
            save()
        assert frozen.read_bytes()==frozen_bytes
        assert provenance._model_identity()['tree_sha256']==r['model']['tree_sha256']
        if stage=='after':
            before=json.loads((e/'semantic-boundary-before.json').read_text(encoding='utf-8'))
            assert r['frozen_sha256']==before['frozen_sha256'] and r['model']['tree_sha256']==before['model']['tree_sha256']
            assert r['calls']==before['calls'], 'Model tokens/profile changed; separator attribution invalid'
            changes=[]
            for old,new in zip(before['rows'],r['rows']):
                assert old['source']==new['source'] and old['parts']==new['parts']
                for tag,a,b,c,d in difflib.SequenceMatcher(a=old['translation'],b=new['translation'],autojunk=False).get_opcodes():
                    if tag!='equal':
                        left=old['translation'][a:b];right=new['translation'][c:d]
                        assert not left.strip() and not right.strip(),(left,right)
                        changes.append(dict(id=new['id'],kind=tag,old=left,new=right))
            assert changes and before['rows'][1]['translation']==r['rows'][1]['translation']
            r['verified_whitespace_only_changes']=changes
        r.update(status='COMPLETED_FOR_REVIEW',elapsed_seconds=time.monotonic()-started)
    except BaseException as err:r.update(status='FAILED',error=repr(err));raise
    finally:save()
    print(r['status'])


if __name__=='__main__':main()
