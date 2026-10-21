"""Declared acceptance subset via existing package writer; full extraction immutable."""
from dataclasses import fields
import hashlib
import json
from pathlib import Path

from vntext.entry import Entry
from vntext.package_io import write_package,read_csv_rows_file,write_csv_rows_file
from vntext.patchability import assess_entry


def create_declared_sample(full: Path, output: Path, reviewed_pairs: list):
    if output.exists():raise ValueError('sample output already exists')
    original={name:(full/name).read_bytes()for name in ('manifest.json','translation.csv','extract_status.json')if(full/name).is_file()}
    manifest=json.loads(original['manifest.json']);by_key={entry['key']:entry for entry in manifest['entries']}
    if not reviewed_pairs or len(reviewed_pairs)>6:raise ValueError('declared sample must contain1..6 reviewed rows')
    keys=[pair['key']for pair in reviewed_pairs]
    if len(set(keys))!=len(keys):raise ValueError('duplicate sample key')
    selected=[]
    for pair in reviewed_pairs:
        entry=by_key.get(pair['key'])
        if entry is None or pair['source_text']!=entry['source_text']:raise ValueError('sample exact key/source drift')
        if assess_entry(entry).status!='SUPPORTED_AND_PATCHABLE'or entry.get('review_only'):raise ValueError('sample row lacks supported patch proof')
        if not isinstance(pair.get('translation'),str)or not pair['translation']:raise ValueError('sample translation not reviewed')
        selected.append(entry)
    provenance={'scope':'DECLARED_ACCEPTANCE_SAMPLE_NOT_FULL_GAME','full_package_path':str(full),
        'full_files':{name:hashlib.sha256(raw).hexdigest()for name,raw in original.items()},
        'full_status':json.loads(original.get('extract_status.json',b'{}')),'selected_keys':keys,
        'selected_entries':selected,'reviewed_pairs':reviewed_pairs}
    names={field.name for field in fields(Entry)}
    entries=[Entry(**{key:value for key,value in entry.items()if key in names})for entry in selected]
    stats={'engine':manifest['stats']['engine'],'acceptance_scope':'DECLARED_SAMPLE',
        'full_package_provenance':provenance,'native_units':len(entries),'errors':[]}
    write_package(str(output),entries,[],stats,separate_review=True,enforce_symmetry=True)
    _,rows=read_csv_rows_file(output/'translation.csv');pairs={pair['key']:pair for pair in reviewed_pairs}
    for row in rows:row['translation']=pairs[row['key']]['translation']
    columns,_=read_csv_rows_file(output/'translation.csv');write_csv_rows_file(output/'translation.csv',columns,rows)
    (output/'extract_status.json').write_text(json.dumps({'status':'COMPLETE','complete':True,'scope':'DECLARED_SAMPLE',
        'reason':'All declared sample rows proof-admitted; full extraction status unchanged and retained in provenance',
        'main':len(rows),'review':0,'full_status':provenance['full_status']}),encoding='utf-8')
    (output/'sample_provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
    assert all((full/name).read_bytes()==raw for name,raw in original.items())
    return provenance
