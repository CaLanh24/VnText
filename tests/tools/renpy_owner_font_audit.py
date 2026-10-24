"""Read-only streamed original RPA/font cmap audit; no game payload on disk."""
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import zlib

from tests.tools.renpy_owner_rar_preflight import SOURCE,EVIDENCE
from tests.lib.dev_environment import renpy_native_sdk
from vntext.renpy_archive import _HEADER,_safe_index,MAX_INDEX_BYTES
from vntext.renpy_compiled import compiled_dialogues

MEMBER='Cucked by My Wife/FTWorlds-1.0-pc/game/archive.rpa'


def stream():return subprocess.Popen(['tar','-xOf',str(SOURCE),MEMBER],stdout=subprocess.PIPE,stderr=subprocess.PIPE)


def read_exact(pipe,count):
    data=pipe.read(count)
    if len(data)!=count:raise ValueError('truncated original RPA stream')
    return data


def discard(pipe,count,digest=None):
    while count:
        chunk=read_exact(pipe,min(count,1024*1024));count-=len(chunk)
        if digest is not None:digest.update(chunk)


def original_members():
    pre=json.loads((EVIDENCE/'renpy-owner-rar-preflight.json').read_text(encoding='utf-8'))
    with SOURCE.open('rb')as f:
        if hashlib.file_digest(f,'sha256').hexdigest()!=pre['source_sha256']:raise ValueError('Owner RAR identity drift')
    p=stream()
    try:
        header=p.stdout.readline(128);match=_HEADER.fullmatch(header)
        if not match:raise ValueError('expected preflight RPA3')
        offset=int(match.group(1),16);key=int(match.group(2),16);digest=hashlib.sha256(header)
        discard(p.stdout,offset-len(header),digest)
        packed=p.stdout.read(MAX_INDEX_BYTES+1);digest.update(packed)
        if len(packed)>MAX_INDEX_BYTES:raise ValueError('index cap')
        if p.communicate(timeout=15)[0]or p.returncode:raise ValueError('tar index stream error')
        if digest.hexdigest()!=pre['rpa_sha256']:raise ValueError('original RPA hash drift')
        inflater=zlib.decompressobj();raw=inflater.decompress(packed,MAX_INDEX_BYTES+1)
        if len(raw)>MAX_INDEX_BYTES or not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:raise ValueError('index compression bounds')
        index=_safe_index(raw)
    finally:
        if p.poll()is None:p.kill();p.communicate()
    chunks=[];payload={};total=0
    for name,records in index.items():
        if not(name.endswith('.rpy')or name.endswith(('.ttf','.otf'))or name=='screens.rpyc'):continue
        payload[name]=[None]*len(records)
        for ordinal,record in enumerate(records):
            start,length=record[:2];prefix=record[2]if len(record)==3 else b''
            if isinstance(prefix,str):prefix=prefix.encode('latin-1')
            start^=key;length^=key;total+=length+len(prefix)
            if start<len(header)or length<0 or start+length>offset or total>48*1024*1024:raise ValueError('selected metadata read cap')
            chunks.append((start,length,prefix,name,ordinal))
    chunks.sort();p=stream();position=0
    try:
        for start,length,prefix,name,ordinal in chunks:
            if start<position:raise ValueError('overlapping selected chunks')
            discard(p.stdout,start-position);payload[name][ordinal]=prefix+read_exact(p.stdout,length);position=start+length
        while p.stdout.read(1024*1024):pass
        if p.communicate(timeout=15)[0]or p.returncode:raise ValueError('tar selected stream error')
    finally:
        if p.poll()is None:p.kill();p.communicate()
    return {name:b''.join(parts)for name,parts in payload.items()},pre


def cmap_glyphs(data,characters):
    """Bounded OpenType Unicode cmap4/12/13 glyph IDs, never renders fonts."""
    def u16(at):return struct.unpack_from('>H',data,at)[0]
    def u32(at):return struct.unpack_from('>L',data,at)[0]
    if data[:4]not in (b'\0\1\0\0',b'OTTO',b'true'):raise ValueError('unsupported sfnt signature')
    count=u16(4)
    if count>256 or 12+16*count>len(data):raise ValueError('font table bounds')
    tables={}
    for i in range(count):
        tag,_,offset,size=struct.unpack_from('>4sLLL',data,12+i*16)
        if offset+size>len(data):raise ValueError('sfnt table outside file')
        tables[tag]=(offset,size)
    base,size=tables[b'cmap']
    if tables[b'maxp'][1]<6:raise ValueError('maxp table bounds')
    maximum=u16(tables[b'maxp'][0]+4)
    if size<4 or 4+8*u16(base+2)>size:raise ValueError('cmap table bounds')
    priority={(3,10):0,(0,6):1,(0,4):2,(3,1):3,(0,3):4,(0,2):5,(0,1):6,(0,0):7}
    candidates=[]
    for i in range(u16(base+2)):
        platform,encoding,offset=struct.unpack_from('>HHL',data,base+4+8*i)
        if (platform,encoding)not in priority:continue
        sub=base+offset
        if sub+2>base+size:raise ValueError('cmap subtable bounds')
        fmt=u16(sub)
        if fmt in (4,12,13):candidates.append((priority[platform,encoding],sub,fmt))
    if not candidates:raise ValueError('Unicode cmap unsupported; coverage UNKNOWN')
    _,sub,fmt=min(candidates)
    length=u16(sub+2)if fmt==4 else u32(sub+4)
    if length<16 or sub+length>base+size:raise ValueError('cmap subtable length')
    result={}
    for cp in characters:
        gid=0
        if fmt==4:
            if u16(sub+6)%2:raise ValueError('cmap4 segment count')
            segments=u16(sub+6)//2
            if 16+8*segments>length:raise ValueError('cmap4 segment bounds')
            for i in range(segments):
                end=u16(sub+14+2*i);start=u16(sub+16+2*segments+2*i)
                if not start<=cp<=end:continue
                delta=u16(sub+16+4*segments+2*i);address=sub+16+6*segments+2*i;relative=u16(address)
                if relative:
                    target=address+relative+2*(cp-start)
                    if target+2>sub+length:raise ValueError('cmap4 glyph bounds')
                    gid=u16(target);gid=(gid+delta)&65535 if gid else 0
                else:gid=(cp+delta)&65535
                break
        else:
            groups=u32(sub+12)
            if groups>200000 or 16+12*groups>length:raise ValueError('cmap12/13 group bounds')
            for i in range(groups):
                start,end,first=struct.unpack_from('>LLL',data,sub+16+12*i)
                if start<=cp<=end:gid=first+(cp-start)if fmt==12 else first;break
        if gid>=maximum:raise ValueError('cmap glyph outside maxp')
        result[cp]=gid
    return {'format':fmt,'glyph_ids':{f'U+{cp:04X}':gid for cp,gid in result.items()},
            'missing':[f'U+{cp:04X} {chr(cp)}'for cp,gid in result.items()if gid==0]}


def main():
    payload,pre=original_members()
    pairs=json.loads((EVIDENCE/'renpy-owner-rar-run4-translations.json').read_text(encoding='utf-8-sig'))
    required=sorted({ord(c)for pair in pairs for c in pair['translation']if c not in '\r\n\t'})
    declarations=[]
    pattern=re.compile(r'font|config\.(?:replace_text|say_menu_text_filter|dialogue_filter)|text_filter|font_replacement_map|FontGroup|\.replace\(')
    for name,data in payload.items():
        if not name.endswith('.rpy')or 'tl'in Path(name).parts:continue
        for number,line in enumerate(data.decode('utf-8-sig').splitlines(),1):
            if pattern.search(line):declarations.append({'member':name,'line':number,'text':line[:1200]})
    fonts={}
    candidate=renpy_native_sdk()/'renpy/common/DejaVuSans.ttf'
    all_fonts={name:data for name,data in payload.items()if name.endswith(('.ttf','.otf'))}
    all_fonts['existing SDK DejaVuSans.ttf']=candidate.read_bytes()
    for name,data in all_fonts.items():
        record={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
        try:record.update(cmap_glyphs(data,required))
        except Exception as error:record['coverage']='UNKNOWN';record['error']=str(error)
        fonts[name]=record
    compiled_error=None
    try:rows,unresolved=compiled_dialogues(payload['screens.rpyc'])
    except Exception as error:rows=[];unresolved=[];compiled_error=str(error)
    exact={pair['source_text']for pair in pairs[:2]}
    original_compiled={'member':'screens.rpyc','member_sha256':hashlib.sha256(payload['screens.rpyc']).hexdigest(),
        'reader':'production compiled_dialogues inert slot2','rows':len(rows),'unresolved':unresolved,'reader_error':compiled_error,
        'neutral_exact_matches':[row for row in rows if row['text']in exact],
        'qualification':'Original paired .rpyc inspected without removing sources; not purecompiled-only distribution or native execution proof'}
    with SOURCE.open('rb')as f:unchanged=hashlib.file_digest(f,'sha256').hexdigest()==pre['source_sha256']
    result={'source_rar_unchanged':unchanged,'rpa_sha256':pre['rpa_sha256'],'required_codepoints':[f'U+{cp:04X}'for cp in required],
        'source_declarations_and_filter_candidates':declarations,'font_cmap':fonts,'original_compiled_probe':original_compiled,
        'scope':'READ_ONLY; no new software, no font rendering/replacement/game edits; cmap IDs are coverage, not shape correctness'}
    (EVIDENCE/'renpy-owner-font-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'rar_unchanged':unchanged,'fonts':{name:{'missing':r.get('missing'),'coverage':r.get('coverage'),'error':r.get('error')}for name,r in fonts.items()},'original_compiled_neutral_matches':len(original_compiled['neutral_exact_matches'])},ensure_ascii=True))


if __name__=='__main__':main()
