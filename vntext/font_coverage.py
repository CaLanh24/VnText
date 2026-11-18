"""Bounded SFNT coverage, without loading or executing a font."""
import struct

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
