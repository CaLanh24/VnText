"""Bounded RPYC inspection. Pickle instructions are data and never execute."""
from __future__ import annotations

from dataclasses import dataclass
import ast
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


def ast_nodes(root, prefixes=('renpy.ast.',)):
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
                if constructor.kind=='global' and str(constructor.args).startswith(prefixes) and fields is not None:
                    nodes.append((constructor.args,fields))
            pending.extend([value.args,value.state])
        elif isinstance(value,dict): pending.extend(value.values())
        elif isinstance(value,(tuple,list)): pending.extend(value)
    return nodes


def _compiled_root(data):
    root=inspect_rpyc(data)
    if not isinstance(root,tuple)or len(root)!=2 or not isinstance(root[0],dict)or not isinstance(root[1],list):
        raise ValueError('Unsupported compiled AST root')
    if root[0].get('version')!=5003000 or root[0].get('key')!='unlocked':
        raise ValueError('Unsupported compiled script version or locked script')
    return root


def _inert_expression(value):
    if isinstance(value,str):return value
    if isinstance(value,Symbol)and value.kind in {'NEWOBJ','REDUCE'}:
        constructor,args=value.args
        if constructor.kind=='global'and constructor.args in {'renpy.ast.PyExpr','renpy.astsupport.PyExpr'}and args and isinstance(args[0],str):
            return args[0]
    return None


def _literal_display(expression):
    source=_inert_expression(expression)
    if source is None or len(source)>65536:return None
    try:node=ast.parse(source,mode='eval').body
    except (SyntaxError,ValueError):return None
    if isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id=='_'and len(node.args)==1 and not node.keywords:
        node=node.args[0]
    return node.value if isinstance(node,ast.Constant)and isinstance(node.value,str)else None


def _python_source(fields):
    code=fields.get('code')
    if not isinstance(code,Symbol)or code.kind!='NEWOBJ':return None
    constructor,_=code.args;state=code.state
    if constructor.kind!='global'or constructor.args!='renpy.ast.PyCode':return None
    if not isinstance(state,tuple)or len(state)not in {4,5,6,7}or state[0]!=1:return None
    source=_inert_expression(state[1])
    return source if source is not None and len(source)<=65536 else None


def _pure_localization(fields):
    source=_python_source(fields)
    if source is None:return False
    try:tree=ast.parse(source)
    except (SyntaxError,ValueError):return False
    return bool(tree.body)and all(isinstance(node,ast.Assign)and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)
        and isinstance(node.value,ast.Call)and isinstance(node.value.func,ast.Name)and node.value.func.id=='_'
        and len(node.value.args)==1 and not node.value.keywords and isinstance(node.value.args[0],ast.Constant)
        and isinstance(node.value.args[0].value,str)for node in tree.body)


def _static_screen_covered(screen):
    pending=[screen];seen=set()
    while pending:
        node=pending.pop()
        if id(node)in seen:continue
        seen.add(id(node))
        if not isinstance(node,Symbol)or node.kind!='NEWOBJ':return False
        constructor,_=node.args;fields=node.state
        if constructor.kind!='global'or not isinstance(fields,dict):return False
        if constructor.args not in {'renpy.sl2.slast.SLScreen','renpy.sl2.slast.SLDisplayable'}:return False
        if constructor.args.endswith('SLDisplayable'):
            display=fields.get('displayable');positional=fields.get('positional')
            if not isinstance(display,Symbol)or display.kind!='global'or display.args not in {'renpy.text.text.Text','renpy.ui._textbutton'}:return False
            if not isinstance(positional,list)or len(positional)!=1 or _literal_display(positional[0])is None:return False
        for item in fields.get('keyword',[]):
            if not isinstance(item,tuple)or len(item)!=2:return False
            if item[0]=='tooltip'and _literal_display(item[1])is not None:continue
            expr=_inert_expression(item[1])
            try:value=ast.parse(expr,mode='eval').body if expr is not None else None
            except (SyntaxError,ValueError):return False
            if isinstance(value,ast.Constant):continue
            if item[0]=='action'and isinstance(value,ast.Call)and isinstance(value.func,ast.Name)and value.func.id=='NullAction'and not value.args and not value.keywords:continue
            return False
        children=fields.get('children',[])
        if not isinstance(children,list):return False
        pending.extend(children)
    return True


def compiled_display_candidates(data: bytes):
    """Read typed static display slots as review inventory, never execute them."""
    nodes=ast_nodes(_compiled_root(data),prefixes=('renpy.ast.','renpy.sl2.slast.'))
    rows=[]
    def add(text,kind,line):
        if isinstance(text,str)and text.strip():
            rows.append({'text':text,'kind':kind,'line':line,'ordinal':len(rows),'native_global_eligible':True,
                         'runtime_mapping_proven':False})
    for name,fields in nodes:
        line=fields.get('linenumber')
        location=fields.get('location')
        if line is None and isinstance(location,tuple)and len(location)>=2:line=location[1]
        if name=='renpy.ast.Menu':
            items=fields.get('items')
            if not isinstance(items,list):raise ValueError('Malformed compiled menu items')
            for item in items:
                if not isinstance(item,tuple)or len(item)!=3:raise ValueError('Malformed compiled menu item')
                if isinstance(item[0],str):add(item[0],'menu_label'if item[2]is not None else 'menu_caption',line)
        elif name=='renpy.ast.Python':
            source=_python_source(fields)
            if source is None:continue
            try:tree=ast.parse(source)
            except (SyntaxError,ValueError):continue
            for node in ast.walk(tree):
                if isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id=='_'and len(node.args)==1 and not node.keywords:
                    arg=node.args[0]
                    if isinstance(arg,ast.Constant)and isinstance(arg.value,str):add(arg.value,'python_localization',line)
        elif name=='renpy.sl2.slast.SLDisplayable':
            row_start=len(rows)
            displayable=fields.get('displayable')
            kind=displayable.args if isinstance(displayable,Symbol)and displayable.kind=='global'else None
            positional=fields.get('positional')
            if kind in {'renpy.text.text.Text','renpy.ui._textbutton'}and isinstance(positional,list)and positional:
                add(_literal_display(positional[0]),'screen_text'if kind=='renpy.text.text.Text'else 'screen_button',line)
            keyword=fields.get('keyword')
            if isinstance(keyword,list):
                for item in keyword:
                    if isinstance(item,tuple)and len(item)==2 and item[0]=='tooltip':add(_literal_display(item[1]),'screen_tooltip',line)
                for item in keyword:
                    if isinstance(item,tuple)and len(item)==2 and item[0]in {'substitute','text_substitute'}:
                        if _inert_expression(item[1])!='True':
                            for row in rows[row_start:]:row['native_global_eligible']=False
    return rows


def compiled_dialogues(data: bytes):
    root = _compiled_root(data)
    nodes = ast_nodes(root)
    dialogues = []; unresolved = set(); identifiers = set()
    for name, fields in nodes:
        if name != 'renpy.ast.TranslateSay':
            covered=(name=='renpy.ast.Python'and _pure_localization(fields)
                or name=='renpy.ast.Screen'and _static_screen_covered(fields.get('screen'))
                or name=='renpy.ast.Menu'and isinstance(fields.get('items'),list)
                    and all(isinstance(item,tuple)and len(item)==3 and isinstance(item[0],str)
                        and _inert_expression(item[1])=='True'for item in fields['items'])
                    and not any(fields.get(key)for key in ('set','with_','arguments')))
            if not covered and name not in {'renpy.ast.Label','renpy.ast.Return','renpy.ast.Init','renpy.ast.Pass'}:
                unresolved.add(name)
            continue
        if fields.get('language') is not None:
            unresolved.add('existing translated dialogue'); continue
        native_id=fields.get('identifier'); text=fields.get('what'); speaker=fields.get('who')
        if isinstance(speaker,Symbol):
            speaker=_inert_expression(speaker)
            if speaker is None:
                unresolved.add('dialogue speaker expression');continue
        if (not isinstance(native_id,str) or not re.fullmatch(r'[A-Za-z_]\w*',native_id)
                or not isinstance(text,str) or not text
                or speaker is not None and not isinstance(speaker,str)):
            raise ValueError('Unsupported compiled dialogue identity or speaker')
        if native_id in identifiers: raise ValueError('Duplicate compiled dialogue identifier')
        if fields.get('interact') is False or any(fields.get(key) for key in ('temporary_attributes','arguments')):
            unresolved.add('dialogue attributes or arguments'); continue
        attributes=fields.get('attributes')or ()
        transition=_inert_expression(fields.get('with_'))if fields.get('with_')is not None else ''
        if not isinstance(attributes,(tuple,list))or not all(isinstance(value,str)and re.fullmatch(r'[A-Za-z_]\w*',value)for value in attributes):
            unresolved.add('dialogue attributes or arguments');continue
        prefix=' '.join(value for value in [speaker or '',*attributes]if value)
        suffix='with '+transition if transition else ''
        from vntext.renpy_extract import _say_statement
        try:
            if fields.get('with_')is not None and (not isinstance(transition,str)or not re.fullmatch(r'[A-Za-z_]\w*',transition)):
                raise ValueError('unsupported transition expression')
            _say_statement((prefix+' 'if prefix else '')+'"probe"'+(' '+suffix if suffix else ''))
        except ValueError:
            unresolved.add('dialogue speaker or transition expression');continue
        identifiers.add(native_id)
        row={'native_id':native_id,'text':text,'speaker':speaker or '', 'line':fields.get('linenumber')}
        if attributes or suffix or (speaker or '').startswith('"'):row.update(say_prefix=prefix,say_suffix=suffix)
        dialogues.append(row)
    return dialogues, sorted(unresolved)


def extract_compiled_source(root, is_cancelled=None):
    from vntext.image_text import _regular
    from vntext.renpy_archive import RenPyArchive,resolved_game_path
    from vntext.entry import Entry
    from vntext.renpy_adapter import is_native_activation_helper
    from vntext.renpy_extract import existing_translation_inventory
    from vntext.patchability import make_renpy_contract, renpy_contract_fingerprint, validate_renpy_contract, RENPY_DIALOGUE_PATCH_PROOF
    root=_regular(root).resolve(); game=_regular(root/'game')
    target_state=existing_translation_inventory(root)
    entries=[]; reviews=[]; errors=[]; files=0; total_bytes=0; identifiers=set()
    for path in sorted(game.rglob('*')):
        if is_cancelled and is_cancelled(): raise ValueError('cancelled')
        if not path.is_file() or 'tl' in {part.casefold()for part in path.relative_to(game).parts}: continue
        if is_native_activation_helper(path,game):continue
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
                game_path=resolved_game_path(member)
                sources.append((game_path,item['content'],{'kind':'rpa','path':path.relative_to(root).as_posix(),
                    'member_name':member,'resolved_game_path':game_path,
                    'container_sha256':item['container_sha256'],'member_sha256':item['member_sha256']}))
        for relative,data,container in sources:
            files+=1
            total_bytes+=len(data)
            if files>2000 or total_bytes>128*1024*1024: raise ValueError('Compiled project inspection budget exceeded')
            rows,unresolved=compiled_dialogues(data)
            errors.extend(f'{relative}: static compiled coverage unresolved: {kind}' for kind in unresolved)
            digest=hashlib.sha256(data).hexdigest()
            for row in compiled_display_candidates(data):
                candidate=Entry(row['text'],relative,f'RenPyCompiledCandidate:{relative}:{row["kind"]}:{row["ordinal"]}',
                    object_info=row['kind'],import_method='renpy_compiled_candidate',backend='renpy_compiled_static_inventory',
                    safety='review',review_only=True,locator={**row,'source_sha256':digest,
                        'source_container':container}).finalize()
                if row['native_global_eligible']:
                    from vntext.renpy_extract import native_global_display_entry
                    entries.append(native_global_display_entry(candidate,backend='renpy_compiled_static'))
                else:reviews.append(candidate)
            for row in rows:
                native_id=row['native_id']
                if native_id in identifiers: raise ValueError('Duplicate compiled native identity across files')
                identifiers.add(native_id)
                contract=make_renpy_contract(method='renpy_dialogue',backend='renpy_compiled_static',unit_type='dialogue',
                    source_text=row['text'],file_path=relative,source_sha256=digest,template_sha256=digest,
                    native_id=native_id,source_line=row['line'],speaker=row['speaker'])
                contract['precondition']['template_file']='<compiled-slot-2>'
                if 'say_prefix'in row:
                    contract['precondition'].update(say_prefix=row['say_prefix'],say_suffix=row['say_suffix'])
                contract['provenance']['generated_artifact']={'file':'<compiled-slot-2>','sha256':digest}
                if container: contract['provenance']['source_container']=container
                contract['fingerprint']=renpy_contract_fingerprint(contract)
                entry=Entry(row['text'],relative,f'RenPyCompiled:{relative}:{native_id}',object_info=row['speaker'],
                    import_method='renpy_dialogue',safety='safe',backend='renpy_compiled_static',
                    locator={'native_id':native_id,'unit_type':'dialogue'},patch_proof=dict(RENPY_DIALOGUE_PATCH_PROOF),native_contract=contract).finalize()
                reason=validate_renpy_contract(entry)
                if reason: raise ValueError(reason)
                entries.append(entry)
    if existing_translation_inventory(root)['snapshots']!=target_state['snapshots']:
        raise ValueError('Existing compiled-game translation inventory changed during extraction')
    return entries,reviews,{'engine':'RENPY_COMPILED_NATIVE','files_scanned':files,'native_units':len(entries),
        'native_dialogue_units':sum(entry.import_method=='renpy_dialogue'for entry in entries),
        'native_string_units':sum(entry.import_method=='renpy_string'for entry in entries),
        'errors':errors,'compiled_reader':'static-opcodes-slot-2',
        'renpy_non_native_review_entries':len(reviews),
        'renpy_existing_translations':{kind:[{'identity':identity,**{key:str(value)if isinstance(value,Path)else value for key,value in record.items()}}
            for identity,record in target_state[kind].items()]for kind in ('dialogues','strings')},
        'renpy_compiled_display_candidates':[
            {**entry.to_manifest(),'disposition':'NATIVE_GLOBAL_DISPLAY'if not entry.review_only else 'REVIEW'}
            for entry in entries+reviews if entry.review_only or entry.native_contract.get('precondition',{}).get('display_slot')]}
