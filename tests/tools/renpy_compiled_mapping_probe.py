"""Read-only trace of inert parser refusal; never runs serialized constructors."""
from collections import deque
import hashlib
import json
import sys

from tests.tools.renpy_owner_font_audit import original_members,EVIDENCE
from vntext.renpy_compiled import Symbol,static_pickle,compiled_dialogues


def describe(value):
    result={'python_type':type(value).__name__}
    if isinstance(value,Symbol):
        result['symbol_kind']=value.kind
        if value.kind=='global':result['global']=value.args
        elif value.kind in ('NEWOBJ','REDUCE'):
            constructor,args=value.args
            result['constructor']=describe(constructor);result['argument_count']=len(args)
    elif isinstance(value,(dict,list,tuple)):result['length']=len(value)
    return result


def main():
    payload,pre=original_members();data=payload['screens.rpyc'];del payload
    history=deque(maxlen=20);failure={}
    def trace(frame,event,arg):
        if frame.f_code is not static_pickle.__code__:return None
        frame.f_trace_lines=False
        if event=='exception':
            local=frame.f_locals;stack=local.get('stack',[]);values=local.get('values',[])
            failure.update(position=local.get('pos'),opcode=local.get('name'),target=describe(stack[-1])if stack else None,value_count=len(values),
                value_types=[type(v).__name__ for v in values[:12]],stack_depth=len(stack),mark_depth=len(local.get('marks',[])))
        return trace
    previous=sys.gettrace();sys.settrace(trace)
    try:
        rows,unresolved=compiled_dialogues(data);error=None
    except Exception as e:rows=[];unresolved=[];error=str(e)
    finally:sys.settrace(previous)
    result={'source_rpa_sha256':pre['rpa_sha256'],'member':'screens.rpyc','member_sha256':hashlib.sha256(data).hexdigest(),
        'error':error,'failure':failure,'recent_inert_mapping_ops':list(history),'rows':len(rows),'unresolved':unresolved,
        'scope':'READ_ONLY production inert-parser trace; no pickle.loads/import of game classes/reducer execution'}
    (EVIDENCE/'renpy-compiled-mapping-probe.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'error':error,'failure':failure}))


if __name__=='__main__':main()
