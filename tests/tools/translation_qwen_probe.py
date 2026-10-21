"""Fixed test-only Qwen experiment with process/memory/timeout ownership."""
import argparse
import ctypes as c
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from tests.lib.work_paths import work_temp_dir


class Mem(c.Structure):
    _fields_=[('length',w.DWORD),('load',w.DWORD)]+[(n,c.c_ulonglong)for n in ['total_physical','available_physical','total_page','available_page','total_virtual','available_virtual','extended']]


class ProcMem(c.Structure):
    _fields_=[('cb',w.DWORD),('faults',w.DWORD)]+[(n,c.c_size_t)for n in ['peak','working','qpp','qpn','qnp','qnn','page','peakpage','private']]


def memory(proc=None):
    m=Mem();m.length=c.sizeof(m);assert c.windll.kernel32.GlobalMemoryStatusEx(c.byref(m))
    result=dict(physical=m.available_physical,commit=m.available_page)
    if proc is not None and proc.poll() is None:
        p=ProcMem();p.cb=c.sizeof(p)
        fn=c.windll.psapi.GetProcessMemoryInfo;fn.argtypes=[w.HANDLE,c.POINTER(ProcMem),w.DWORD]
        assert fn(w.HANDLE(int(proc._handle)),c.byref(p),p.cb)
        result['peak']=p.peak
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['transport','development','fresh']);parser.add_argument('--resource-fit',action='store_true');options=parser.parse_args();stage=options.stage
    suffix='-resource-fit' if options.resource_fit else ''
    root=Path.cwd();e=Path.home()/'Downloads/VM-Acceptance';out=e/f'qwen-{stage}{suffix}.json';assert not out.exists()
    frozen=root/'evaluation/translation_semantic_campaign_v1/qwen-experiment-frozen.json';spec=json.loads(frozen.read_text(encoding='utf-8'))
    model=root/'.dev-env/cache/models/Qwen2.5-0.5B-Instruct-Q4_K_M'/spec['model_file']
    # Ownership/hash already verified at acquisition; verify again incrementally.
    digest=hashlib.sha256()
    with model.open('rb')as f:
        for chunk in iter(lambda:f.read(65536),b''):digest.update(chunk)
    assert digest.hexdigest()==spec['model_sha256']
    exe=root/'.dev-env/tools/llama-b11724/llama-completion.exe'
    assert hashlib.sha256(exe.read_bytes()).hexdigest()==spec['runtime_binary_sha256']
    if stage=='development':
        previous=json.loads((e/f'qwen-transport{suffix}.json').read_text(encoding='utf-8'));assert previous['status']=='PASS_TRANSPORT'
        rows=json.loads((root/'evaluation/translation_semantic_campaign_v1/relation-frozen.json').read_text(encoding='utf-8'))['rows']
    elif stage=='fresh':
        review=json.loads((root/'evaluation/translation_semantic_campaign_v1/qwen-development-review.json').read_text(encoding='utf-8'));assert review['admitted']
        rows=json.loads((root/'evaluation/translation_semantic_campaign_v1/frozen.json').read_text(encoding='utf-8'))['fresh']
    else:rows=[dict(id='transport',source='The door is open.')]
    work=work_temp_dir('qwen-'+stage)
    for key in ['TEMP','TMP','TMPDIR']:os.environ[key]=str(work)
    report=dict(status='RUN_STARTED',stage=stage,model_sha256=digest.hexdigest(),spec_sha256=hashlib.sha256(frozen.read_bytes()).hexdigest(),rows=[],fixture_only=True,resource_fit=options.resource_fit,resource_delta='physical microbatch8 only; logicalbatch64/context512/semantic decode unchanged' if options.resource_fit else None)
    def save():out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    save()
    for row in rows:
        # Include a conservative whole-model increment before preserving live reserves.
        minimum_physical=850*1024**2 if options.resource_fit else 1342177280
        minimum_commit=1792*1024**2 if options.resource_fit else 2147483648
        initial=memory();assert initial['physical']>=minimum_physical and initial['commit']>=minimum_commit,initial
        prompt=spec['prompt_template'].replace('{source}',row['source'])
        promptpath=work/(row['id']+'.txt');promptpath.write_text(prompt,encoding='utf-8')
        stdout=e/f'qwen-{stage}{suffix}-{row["id"]}.stdout.txt';stderr=e/f'qwen-{stage}{suffix}-{row["id"]}.stderr.txt'
        args=[str(exe),'-m',str(model),*spec['args'],'--file',str(promptpath)]
        if options.resource_fit:args+=['--ubatch-size','8']
        record=dict(id=row['id'],source=row['source'],prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),initial_memory=initial,args=args,stdout=str(stdout),stderr=str(stderr),samples=[])
        report['rows'].append(record);save();started=time.monotonic()
        with stdout.open('xb')as so,stderr.open('xb')as se:
            proc=subprocess.Popen(args,cwd=root,stdin=subprocess.DEVNULL,stdout=so,stderr=se,env=os.environ.copy(),creationflags=subprocess.CREATE_NO_WINDOW)
            record['pid']=proc.pid
            try:
                while proc.poll()is None:
                    sample=memory(proc);record['samples'].append(sample)
                    if sample['physical']<268435456 or sample['commit']<1073741824 or sample.get('peak',0)>1610612736:
                        record['guard_failure']=sample;raise RuntimeError('INFERENCE_MEMORY_GUARD')
                    if time.monotonic()-started>120:raise TimeoutError('call budget120s')
                    time.sleep(0.25)
            except BaseException as err:
                record['error']=repr(err);report['status']='FAILED';proc.terminate();proc.wait(timeout=15);save();raise
            finally:
                record.update(exit_code=proc.poll(),elapsed_seconds=time.monotonic()-started);save()
        assert proc.returncode==0,record
        record['raw_stdout']=stdout.read_text(encoding='utf-8',errors='replace');record['stderr_tail']=stderr.read_text(encoding='utf-8',errors='replace')[-4500:];save()
    report['status']='PASS_TRANSPORT'if stage=='transport'else'COMPLETED_FOR_SEMANTIC_REVIEW';save();print(report['status'])


if __name__=='__main__':main()
