"""Read-only shared skill verification; optional removal of the verified duplicate only."""
from pathlib import Path
import argparse, hashlib, json, os, stat
ROOT=Path(__file__).resolve().parents[1]
def verify(root, pin):
    observed={}
    for p in root.rglob('*'):
        if p.is_symlink() or p.lstat().st_file_attributes & 0x400:
            raise ValueError('linked skill path refused')
        if p.is_file(): observed[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    if observed != pin['files']: raise ValueError('skill version/content differs from pin; no mutation')
    return observed
def main():
    a=argparse.ArgumentParser();a.add_argument('--remove-duplicate',action='store_true');args=a.parse_args()
    pin=json.loads((ROOT/'release/impeccable-pin.json').read_text(encoding='utf8'))
    canonical=Path(pin['canonical']).expanduser();verify(canonical,pin)
    local=ROOT/'.agents/skills/impeccable'
    if args.remove_duplicate and local.exists():
        verify(local,dict(pin,files=pin["legacy_duplicate_files"]))
        # The approved duplicate only; no recursive shell deletion or junction traversal.
        for rel,sha in pin['legacy_duplicate_files'].items():
            p=local/rel
            if hashlib.sha256(p.read_bytes()).hexdigest()!=sha: raise ValueError('skill changed during removal')
            p.unlink()
        for p in sorted(local.rglob('*'),key=lambda p:len(p.parts),reverse=True):
            if p.is_dir():p.rmdir()
        local.rmdir()
    print(json.dumps({'ok':True,'version':pin['version'],'files':len(pin['files']),'canonical':str(canonical),'duplicate_removed':args.remove_duplicate}))
if __name__=='__main__':main()
