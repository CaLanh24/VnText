"""Read-only Owner RAR and inert streamed RPA index preflight."""
import hashlib
import json
from pathlib import Path
import subprocess
import zlib

from vntext.renpy_archive import RenPyArchive, _HEADER, _HEADER2, _safe_index, MAX_INDEX_BYTES, MAX_MEMBERS, MAX_MEMBER_BYTES
from tests.tools.cleanup_work_artifacts import _project_size_snapshot

EVIDENCE=Path('C:/Users/VNTextDev/Downloads/VM-Acceptance')
SOURCE=Path('C:/Users/VNTextDev/Desktop/game/Cucked_by_My_Wife.rar')


def main():
    outer=json.loads((EVIDENCE/'renpy-owner-rar-inventory.json').read_text(encoding='utf-8-sig'))
    folded=set();files=set()
    for record in outer['inventory']:
        name=record['path'].rstrip('/')
        if record['mode'][0] not in '-d' or not RenPyArchive._safe_name(name):raise ValueError('unsafe outer member path/type')
        if name.casefold() in folded:raise ValueError('outer case collision')
        folded.add(name.casefold())
        if record['mode'][0]=='-':files.add(name.casefold())
    for name in folded:
        if any(str(p).replace('\\','/').casefold() in files for p in Path(name).parents if str(p)!='.'):raise ValueError('outer file-directory collision')
    member='Cucked by My Wife/FTWorlds-1.0-pc/game/archive.rpa'
    expected=next(r['bytes']for r in outer['inventory']if r['path']==member)
    process=subprocess.Popen(['tar','-xOf',str(SOURCE),member],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    digest=hashlib.sha256();total=0
    try:
        header=process.stdout.readline(128);digest.update(header);total=len(header)
        match=_HEADER.fullmatch(header);match2=_HEADER2.fullmatch(header)if not match else None
        if not(match or match2):raise ValueError('unsupported streamed RPA header')
        offset=int((match or match2).group(1),16);key=int(match.group(2),16)if match else 0
        if not len(header)<=offset<expected:raise ValueError('invalid RPA index offset')
        while total<offset:
            chunk=process.stdout.read(min(1024*1024,offset-total))
            if not chunk:raise ValueError('truncated streamed RPA')
            digest.update(chunk);total+=len(chunk)
        packed=process.stdout.read(MAX_INDEX_BYTES+1);digest.update(packed);total+=len(packed)
        if len(packed)>MAX_INDEX_BYTES or total!=expected:raise ValueError('stream size/index cap mismatch')
        errors=process.communicate(timeout=15)[1]
        if process.returncode:raise ValueError('tar stream failure: '+errors.decode(errors='replace')[:400])
    finally:
        if process.poll()is None:process.kill();process.communicate()
    inflater=zlib.decompressobj();raw=inflater.decompress(packed,MAX_INDEX_BYTES+1)
    if len(raw)>MAX_INDEX_BYTES or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:raise ValueError('unsafe compressed index')
    index=_safe_index(raw)
    if len(index)>MAX_MEMBERS:raise ValueError('member count cap')
    members=[];seen=set();ranges=[]
    for name,chunks in index.items():
        if not isinstance(name,str)or not RenPyArchive._safe_name(name)or name.casefold()in seen:raise ValueError('unsafe/colliding RPA path')
        seen.add(name.casefold());size=0
        if not isinstance(chunks,list)or not chunks:raise ValueError('invalid member chunks')
        for chunk in chunks:
            if not isinstance(chunk,tuple)or len(chunk)not in (2,3):raise ValueError('invalid RPA chunk')
            start,length=chunk[:2];prefix=chunk[2]if len(chunk)==3 else b''
            if type(start)is not int or type(length)is not int or not isinstance(prefix,(str,bytes)):raise ValueError('invalid RPA primitive')
            if match:start^=key;length^=key
            if start<len(header)or length<0 or start+length>offset or length+len(prefix)>MAX_MEMBER_BYTES:raise ValueError('RPA chunk outside bounds')
            size+=length+len(prefix);ranges.append((start,start+length))
        members.append({'path':name,'bytes':size})
    ranges.sort()
    if any(a[1]>b[0]for a,b in zip(ranges,ranges[1:])):raise ValueError('overlapping RPA chunks')
    quota=_project_size_snapshot()
    scripts=sum(m['bytes']for m in members if m['path'].endswith(('.rpy','.rpym','.rpyc','.rpymc')))
    projection=quota['non_exempt_bytes']+int(outer['game_bytes'])+scripts+16*1024*1024
    result={'source':str(SOURCE),'source_sha256':hashlib.file_digest(SOURCE.open('rb'),'sha256').hexdigest(),
      'rpa_sha256':digest.hexdigest(),'rpa_version':'3.0'if match else '2.0','rpa_members':members,
      'script_surface':{s:sum(m['path'].endswith(s)for m in members)for s in ('.rpy','.rpyc','.rpym','.rpymc')},
      'scripts_bytes':scripts,'outer_members':outer['members'],'outer_bytes':outer['bytes'],'game_bytes':outer['game_bytes'],
      'quota':quota,'projected_game_scripts_reserve16MiB':projection,'headroom_after_projection':quota['limit_bytes']-projection,
      'preflight':'PASS'if quota['complete']and projection<=quota['limit_bytes']else 'PROVEN_BLOCKED_QUOTA',
      'runtime_bundled':'8.3.7.25031702','planned_runtime':'existing SDK8.5.3; original bundled runtime not copied/executed'}
    (EVIDENCE/'renpy-owner-rar-preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k]for k in ('preflight','script_surface','scripts_bytes','projected_game_scripts_reserve16MiB','headroom_after_projection')}))


if __name__=='__main__':main()
