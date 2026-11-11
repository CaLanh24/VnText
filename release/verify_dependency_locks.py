"""Verify lock/hash pairing and target-runtime dependency closure without installs."""
import hashlib,json,re
from pathlib import Path
from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version
ROOT=Path(__file__).resolve().parents[1]
def verify(path):
 doc=json.loads(path.read_text(encoding='utf8'));lock=path.with_suffix('.txt')
 if hashlib.sha256(lock.read_bytes()).hexdigest()!=doc['lock_sha256']:raise ValueError('lock hash mismatch')
 packages={canonicalize_name(x['name']):x for x in doc['packages']}
 env=default_environment();env.update(sys_platform='win32',platform_system='Windows',platform_machine='AMD64',python_version=doc['python'],python_full_version=doc['python']+'.0',extra='')
 errors=[]
 for item in packages.values():
  line=item['name']+'=='+item['version']+' --hash=sha256:'+item['sha256']
  if line not in lock.read_text(encoding='utf8'):errors.append('lock entry differs: '+item['name'])
  if not re.fullmatch('[0-9a-f]{64}',item['sha256']):errors.append('invalid artifact hash')
  if not item['url'].startswith('https://files.pythonhosted.org/'):errors.append('untrusted artifact URL')
  for text in item['requires_dist']:
   req=Requirement(text)
   if req.marker and not req.marker.evaluate(env):continue
   target=packages.get(canonicalize_name(req.name))
   if not target or Version(target['version']) not in req.specifier:errors.append(item['name']+' dependency: '+text)
 if errors:raise ValueError('; '.join(errors))
 return {'profile':path.stem,'outcome':'PASS','packages':len(packages),'target_dependency_closure':True,'install_native':'NOT_PROVEN by this metadata check'}
if __name__=='__main__':
 print(json.dumps([verify(p) for p in sorted((ROOT/'requirements/locks').glob('windows-*.json'))]))
