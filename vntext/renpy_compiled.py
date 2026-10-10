"""Bounded RPYC inspection. Pickle instructions are data and never execute."""
from __future__ import annotations

from dataclasses import dataclass
import pickletools
import struct
import zlib
import hashlib
import re
from pathlib import Path

MAX_BYTES = 32 * 1024 * 1024
MAX_OPS = 500_000


@dataclass(eq=False)
class Symbol:
    kind: str
    args: object = None
    state: object = None


def static_pickle(data: bytes):
    """Keep constructors/reducers inert; do not import classes or call __setstate__."""
    if len(data) > MAX_BYTES:
        raise ValueError('Compiled slot exceeds 32 MiB')
    stack, marks, memo = [], [], {}
    stopped = False
    def marked():
        mark = marks.pop()
        result = stack[mark:]
        del stack[mark:]
        return result
    try:
        for count, (opcode, arg, pos) in enumerate(pickletools.genops(data)):
            if count >= MAX_OPS: raise ValueError('Compiled opcode budget exceeded')
            name = opcode.name
            if name in {'PROTO','FRAME'}: continue
            if name == 'STOP':
                stopped = pos + 1 == len(data)
                break
            if name == 'MARK': marks.append(len(stack))
            elif name == 'NONE': stack.append(None)
            elif name in {'NEWTRUE','NEWFALSE'}: stack.append(name == 'NEWTRUE')
            elif name in {'BININT','BININT1','BININT2','LONG1','LONG4','BINFLOAT',
                          'SHORT_BINUNICODE','BINUNICODE','BINUNICODE8','SHORT_BINBYTES','BINBYTES','BINBYTES8'}:
                stack.append(arg)
            elif name == 'EMPTY_DICT': stack.append({})
            elif name == 'EMPTY_LIST': stack.append([])
            elif name == 'EMPTY_TUPLE': stack.append(())
            elif name == 'TUPLE': stack.append(tuple(marked()))
            elif name in {'TUPLE1','TUPLE2','TUPLE3'}:
                size = int(name[-1])
                if len(stack)<size: raise ValueError('Compiled tuple stack underflow')
                values = stack[-size:]; del stack[-size:]; stack.append(tuple(values))
            elif name == 'MEMOIZE': memo[len(memo)] = stack[-1]
            elif name in {'BINPUT','LONG_BINPUT'}: memo[arg] = stack[-1]
            elif name in {'BINGET','LONG_BINGET'}: stack.append(memo[arg])
            elif name == 'GLOBAL': stack.append(Symbol('global', arg.replace(' ', '.')))
            elif name == 'STACK_GLOBAL':
                attribute = stack.pop(); module = stack.pop()
                if not isinstance(module,str) or not isinstance(attribute,str): raise ValueError('Malformed global')
                stack.append(Symbol('global',module+'.'+attribute))
            elif name in {'NEWOBJ','REDUCE'}:
                args = stack.pop(); constructor = stack.pop()
                if not isinstance(args,tuple) or not isinstance(constructor,Symbol): raise ValueError('Malformed constructor')
                stack.append(Symbol(name,(constructor,args)))
            elif name == 'BUILD':
                state = stack.pop()
                if not isinstance(stack[-1],Symbol): raise ValueError('Malformed state')
                stack[-1].state = state
            elif name in {'APPEND','APPENDS'}:
                values = [stack.pop()] if name == 'APPEND' else marked()
                if not isinstance(stack[-1],list): raise ValueError('Malformed list')
                stack[-1].extend(values)
            elif name in {'SETITEM','SETITEMS'}:
                if name == 'SETITEM':
                    value = stack.pop(); key = stack.pop(); values = [key,value]
                else: values = marked()
                if not isinstance(stack[-1],dict) or len(values)%2: raise ValueError('Malformed mapping')
                for i in range(0,len(values),2):
                    key = values[i]
                    if not isinstance(key,(str,int,bytes,type(None))): raise ValueError('Unsupported mapping key')
                    if key in stack[-1]: raise ValueError('Duplicate mapping key')
                    stack[-1][key] = values[i+1]
            else: raise ValueError('Unsupported compiled opcode: '+name)
    except (IndexError,KeyError,TypeError,OverflowError) as exc:
        raise ValueError('Malformed compiled pickle') from exc
    if not stopped or marks or len(stack)!=1: raise ValueError('Compiled pickle trailing data or invalid stack')
    return stack[0]


def inspect_rpyc(data: bytes):
    if len(data)>MAX_BYTES or not data.startswith(b'RENPY RPC2'):
        raise ValueError('Unsupported or oversized compiled script')
    slots = {}; ranges = []; table_end = None
    for index in range(10,min(len(data)-11,1024),12):
        slot,offset,length = struct.unpack_from('<III',data,index)
        if slot == 0:
            table_end=index+12; break
        if slot not in {1,2} or slot in slots or length==0 or offset+length>len(data):
            raise ValueError('Invalid compiled slot')
        slots[slot]=(offset,length); ranges.append((offset,offset+length))
    if table_end is None or 2 not in slots or any(start<table_end for start,end in ranges):
        raise ValueError('Compiled native identity slot unavailable')
    ranges.sort()
    if any(a[1]>b[0] for a,b in zip(ranges,ranges[1:])): raise ValueError('Overlapping compiled slots')
    offset,length=slots[2]; inflater=zlib.decompressobj()
    decoded=inflater.decompress(data[offset:offset+length],MAX_BYTES+1)
    if len(decoded)>MAX_BYTES or inflater.unconsumed_tail or not inflater.eof or inflater.unused_data:
        raise ValueError('Invalid compressed compiled slot')
    return static_pickle(decoded)


def ast_nodes(root):
    """Walk cyclic inert graphs once; return raw AST fields without evaluating code."""
    pending=[root]; seen=set(); nodes=[]
    while pending:
        value=pending.pop()
        if id(value) in seen: continue
        seen.add(id(value))
        if len(seen)>MAX_OPS: raise ValueError('Compiled graph budget exceeded')
        if isinstance(value,Symbol):
            if value.kind=='NEWOBJ':
                constructor,args=value.args
                state=value.state
                fields=state if isinstance(state,dict) else state[1] if isinstance(state,tuple) and len(state)==2 and state[0] is None and isinstance(state[1],dict) else None
                if constructor.kind=='global' and str(constructor.args).startswith('renpy.ast.') and fields is not None:
                    nodes.append((constructor.args,fields))
            pending.extend([value.args,value.state])
        elif isinstance(value,dict): pending.extend(value.values())
        elif isinstance(value,(tuple,list)): pending.extend(value)
    return nodes


def compiled_dialogues(data: bytes):
    root = inspect_rpyc(data)
    if not isinstance(root,tuple) or len(root)!=2 or not isinstance(root[0],dict) or not isinstance(root[1],list):
        raise ValueError('Unsupported compiled AST root')
    if root[0].get('version') != 5003000 or root[0].get('key') != 'unlocked':
        raise ValueError('Unsupported compiled script version or locked script')
    nodes = ast_nodes(root)
    dialogues = []; unresolved = set(); identifiers = set()
    for name, fields in nodes:
        if name != 'renpy.ast.TranslateSay':
            if name not in {'renpy.ast.Label','renpy.ast.Return','renpy.ast.Init'}:
                unresolved.add(name)
            continue
        if fields.get('language') is not None:
            unresolved.add('existing translated dialogue'); continue
        native_id=fields.get('identifier'); text=fields.get('what'); speaker=fields.get('who')
        if (not isinstance(native_id,str) or not re.fullmatch(r'[A-Za-z_]\w*',native_id)
                or not isinstance(text,str) or not text
                or speaker is not None and (not isinstance(speaker,str) or not re.fullmatch(r'[A-Za-z_]\w*',speaker))):
            raise ValueError('Unsupported compiled dialogue identity or speaker')
        if native_id in identifiers: raise ValueError('Duplicate compiled dialogue identifier')
        if fields.get('interact') is False or any(fields.get(key) for key in ('attributes','temporary_attributes','arguments','with_')):
            unresolved.add('dialogue attributes or arguments'); continue
        identifiers.add(native_id)
        dialogues.append({'native_id':native_id,'text':text,'speaker':speaker or '', 'line':fields.get('linenumber')})
    return dialogues, sorted(unresolved)


def extract_compiled_source(root, is_cancelled=None):
    from vntext.image_text import _regular
    from vntext.renpy_archive import RenPyArchive
    from vntext.entry import Entry
    from vntext.patchability import make_renpy_contract, renpy_contract_fingerprint, validate_renpy_contract, RENPY_DIALOGUE_PATCH_PROOF
    root=_regular(root).resolve(); game=_regular(root/'game')
    entries=[]; errors=[]; files=0; total_bytes=0; identifiers=set()
    for path in sorted(game.rglob('*')):
        if is_cancelled and is_cancelled(): raise ValueError('cancelled')
        if not path.is_file() or 'tl' in path.relative_to(game).parts: continue
        sources=[]
        if path.suffix.lower() in {'.rpyc','.rpymc'}:
            path=_regular(path)
            if path.stat().st_size>MAX_BYTES: raise ValueError('Compiled file exceeds 32 MiB')
            sources.append((path.relative_to(root).as_posix(),path.read_bytes(),None))
        elif path.suffix.lower()=='.rpa':
            archive=RenPyArchive(path)
            for member in archive.members:
                if Path(member).suffix.lower() not in {'.rpyc','.rpymc'}: continue
                if 'tl' in {part.casefold() for part in Path(member).parts}: continue
                item=archive.read_member(member)
                if len(sources)>=2000 or sum(len(source[1]) for source in sources)+len(item['content'])>128*1024*1024:
                    raise ValueError('Compiled archive inspection budget exceeded')
                sources.append((member,item['content'],{'kind':'rpa','path':path.relative_to(root).as_posix(),
                    'member_name':member,'container_sha256':item['container_sha256'],'member_sha256':item['member_sha256']}))
        for relative,data,container in sources:
            files+=1
            total_bytes+=len(data)
            if files>2000 or total_bytes>128*1024*1024: raise ValueError('Compiled project inspection budget exceeded')
            rows,unresolved=compiled_dialogues(data)
            errors.extend(f'{relative}: static compiled coverage unresolved: {kind}' for kind in unresolved)
            digest=hashlib.sha256(data).hexdigest()
            for row in rows:
                native_id=row['native_id']
                if native_id in identifiers: raise ValueError('Duplicate compiled native identity across files')
                identifiers.add(native_id)
                contract=make_renpy_contract(method='renpy_dialogue',backend='renpy_compiled_static',unit_type='dialogue',
                    source_text=row['text'],file_path=relative,source_sha256=digest,template_sha256=digest,
                    native_id=native_id,source_line=row['line'],speaker=row['speaker'])
                contract['precondition']['template_file']='<compiled-slot-2>'
                contract['provenance']['generated_artifact']={'file':'<compiled-slot-2>','sha256':digest}
                if container: contract['provenance']['source_container']=container
                contract['fingerprint']=renpy_contract_fingerprint(contract)
                entry=Entry(row['text'],relative,f'RenPyCompiled:{relative}:{native_id}',object_info=row['speaker'],
                    import_method='renpy_dialogue',safety='safe',backend='renpy_compiled_static',
                    locator={'native_id':native_id,'unit_type':'dialogue'},patch_proof=dict(RENPY_DIALOGUE_PATCH_PROOF),native_contract=contract).finalize()
                reason=validate_renpy_contract(entry)
                if reason: raise ValueError(reason)
                entries.append(entry)
    return entries,[],{'engine':'RENPY_COMPILED_NATIVE','files_scanned':files,'native_units':len(entries),
        'native_dialogue_units':len(entries),'errors':errors,'compiled_reader':'static-opcodes-slot-2'}
