"""Select audited Windows profiles; no install/download or silent range fallback."""
import argparse,json,sys
from pathlib import Path
from importlib.metadata import version,PackageNotFoundError

def select(root,minor):
 tag=''.join(map(str,minor))
 if tag not in ('312','314'):raise ValueError('No audited Windows lock for Python '+str(minor)+'; use CPython3.12/3.14 or explicitly validate a new profile.')
 files=[Path(root)/'requirements/locks'/('windows-cp'+tag+'-runtime.txt')]
 if not all(p.is_file() for p in files):raise ValueError('Dependency profile is incomplete')
 return files

def installed(files):
 failures=[]
 for p in files:
  for line in p.read_text(encoding='utf8').splitlines():
   if not line or line.startswith('#'):continue
   name,want=line.split(' --hash=')[0].split('==')
   try:actual=version(name)
   except PackageNotFoundError:actual='MISSING'
   if actual!=want:failures.append(name+': '+actual+' != '+want)
 if failures:raise ValueError('Preinstalled dependencies differ from lock: '+'; '.join(failures))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--check-installed',action='store_true');a=p.parse_args()
 files=select(a.root,sys.version_info[:2])
 if a.check_installed:installed(files)
 print(json.dumps({'files':list(map(str,files)),'checked_installed':a.check_installed}))
