"""Find one active/cold artifact without inflating or dumping registry history."""
from pathlib import Path
import argparse,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'lib'))
from registry_storage import cold_records
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--id',required=True);a=p.parse_args()
 manifest=Path(__file__).resolve().parents[2]/'TEST_RUN/artifacts_manifest.json';doc=json.loads(manifest.read_text(encoding='utf8'))
 matches=[{'storage':'active',**r} for r in doc.get('artifacts',[]) if r.get('id')==a.id]
 matches.extend({'storage':'cold',**r} for r in cold_records(doc,manifest) if r.get('id')==a.id)
 print(json.dumps({'id':a.id,'matches':matches,'cold_is_cleanup_acceptance':False},ensure_ascii=True))
 raise SystemExit(0 if matches else 2)
