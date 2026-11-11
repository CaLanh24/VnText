"""Offline finite R12 A/B. Generation does not rate its own outputs or claim full-game quality."""
from pathlib import Path
import argparse,hashlib,json,os,random,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
def generate(model,out):
    from unittest.mock import patch
    from vntext.mt_ct2_model import get_translator
    from vntext.mt_ct2_io import _batch_translate_chunk
    model=Path(model).resolve()
    if not (model/'model.bin').is_file():raise ValueError('acquired model missing; no download')
    os.environ['VNTEXT_CT2_NO_DOWNLOAD']='1'
    corpus_path=ROOT/'tests/golden/mt-quality/corpus.json';corpus=json.loads(corpus_path.read_text(encoding='utf8'))
    translator=get_translator(model);blind=[];mapping={};rng=random.SystemRandom()
    for c in corpus['cases']:
        row={'key':c['id'],'source_text':c['source'],'import_method':'renpy_dialogue'}
        processed=_batch_translate_chunk(translator,[row],c['terms']).get(c['id'],'')
        with patch('vntext.mt_ct2_io.postprocess',side_effect=lambda src,text:text):
            raw=_batch_translate_chunk(translator,[row],c['terms']).get(c['id'],'')
        arms=[('processed',processed),('raw',raw)];rng.shuffle(arms)
        for i,(arm,text) in enumerate(arms):
            key=c['id']+'-'+str(i+1);mapping[key]=arm
            blind.append({'id':key,'source':c['source'],'context':c['context'],'output':text,'protected':c['protected'],'terms':c['terms']})
    out.mkdir(parents=True,exist_ok=False)
    write=lambda name,data:(out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    write('blind.json',blind);write('arm-map.json',mapping)
    write('provenance.json',{'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'git_status':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True),'corpus_sha256':hashlib.sha256(corpus_path.read_bytes()).hexdigest(),'model_bin_sha256':hashlib.sha256((model/'model.bin').read_bytes()).hexdigest(),'model':str(model),'python':sys.version,'criteria':corpus['criteria'],'native_or_whole_game_acceptance':False})
    print(json.dumps({'ok':True,'cases':len(corpus['cases']),'blind':str(out/'blind.json'),'review_required':True}))
def score(out,review):
    blind=json.loads((out/'blind.json').read_text(encoding='utf8'));mapping=json.loads((out/'arm-map.json').read_text(encoding='utf8'));ratings=json.loads(Path(review).read_text(encoding='utf8'))
    if set(ratings)!=set(mapping):raise ValueError('complete saved blind review required before unblinding')
    result=[]
    for row in blind:
        r=ratings[row['id']];text=row['output'];src=row['source']
        pattern='|'.join(re.escape(t) for t in sorted(row['protected'],key=len,reverse=True))
        protected=(re.findall(pattern,text)==re.findall(pattern,src)) if pattern else True
        terms=all(term in text for term in row['terms'].values())
        result.append({'id':row['id'],'arm':mapping[row['id']],'protected':protected,'terms':terms,**r})
    processed=[r for r in result if r['arm']=='processed']
    result={'cases':result,'outcome':'PASS' if all(r['protected'] and r['terms'] and r['basic_vietnamese'] and not r['app_corruption'] for r in processed) else 'FAIL','boundary':'Finite synthetic basic-draft/protected-span acceptance only; semantic limits recorded; single model-assisted blind review, not independent human/gameplay proof.'}
    (out/'scored.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['generate','score']);p.add_argument('--model');p.add_argument('--output',type=Path,required=True);p.add_argument('--review');a=p.parse_args()
    generate(a.model,a.output) if a.action=='generate' else score(a.output,a.review)
