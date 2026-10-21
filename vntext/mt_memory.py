"""Deterministic package-scoped translation memory for offline MT.

The memory is a consistency aid, not a model or a replacement for review.  It
only reuses a translation when the normalized source, import method and
context family identify one unambiguous previous translation.  User glossary
lookups still run first.
"""
from __future__ import annotations

import json
import hashlib
import re
import unicodedata
import os
import uuid
from pathlib import Path

MEMORY_VERSION = "1.0.0"
MEMORY_NAME = "translation_memory.json"
STRICT_MEMORY_POLICY = "strict-approval-v1"
MEMORY_SCOPE_NAME = "translation_memory_scope.json"


def _digest_entries(entries) -> str:
    return hashlib.sha256(json.dumps(entries, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _package_binding(package_dir) -> str:
    return hashlib.sha256(str(Path(package_dir).resolve()).casefold().encode("utf-8")).hexdigest()


def _scope_failure(package_dir, reason) -> dict:
    return dict(version=MEMORY_VERSION, scope_policy=STRICT_MEMORY_POLICY,
                scope_error=reason, entries=[], _package_dir=str(Path(package_dir).resolve()))


def _strict_requested(package_dir) -> bool:
    meta=Path(package_dir)/".mt"
    if (meta/MEMORY_SCOPE_NAME).exists() or (meta/MEMORY_SCOPE_NAME).is_symlink():
        return True
    try:
        payload=json.loads((meta/MEMORY_NAME).read_text(encoding="utf-8"))
        return isinstance(payload,dict) and "scope_policy" in payload
    except (OSError,ValueError):
        return False


def _load_strict(package_dir) -> dict:
    """Read both approval artifacts without repairing/downgrading either."""
    meta=Path(package_dir)/".mt"
    try:
        if any(p.is_symlink() for p in (meta,meta/MEMORY_NAME,meta/MEMORY_SCOPE_NAME)):
            raise ValueError("linked strict memory artifacts")
        guard=json.loads((meta/MEMORY_SCOPE_NAME).read_text(encoding="utf-8"))
        memory=json.loads((meta/MEMORY_NAME).read_text(encoding="utf-8"))
        if not isinstance(guard,dict) or not isinstance(memory,dict):
            raise ValueError("invalid strict memory objects")
        if type(guard.get("version")) is not int or guard["version"]!=1 or memory.get("version")!=MEMORY_VERSION:
            raise ValueError("unsupported strict memory version")
        if any(p.get("scope_policy")!=STRICT_MEMORY_POLICY for p in (guard,memory)):
            raise ValueError("unsupported strict memory policy")
        expected=_package_binding(package_dir)
        if any(p.get("package_binding")!=expected for p in (guard,memory)):
            raise ValueError("strict memory package binding mismatch")
        approval=memory.get("approval_sha256")
        if not isinstance(approval,str) or not re.fullmatch(r"[a-fA-F0-9]{64}",approval) or guard.get("approval_sha256")!=approval:
            raise ValueError("strict memory approval mismatch")
        if memory.get("review_kind") not in {"owner-delegated-agent","user-confirmed","mixed-explicit"}:
            raise ValueError("unsupported strict memory review attribution")
        if memory['review_kind']!='owner-delegated-agent':
            decision_path=meta/'translation_memory_decisions.json'
            if decision_path.is_symlink():
                raise ValueError('linked review decision')
            decision_bytes=decision_path.read_bytes()
            decision=json.loads(decision_bytes.decode('utf-8'))
            if (hashlib.sha256(decision_bytes).hexdigest()!=approval
                    or not isinstance(decision,dict) or decision.get('version')!=1
                    or decision.get('reviewer_kind')!='user-confirmed'
                    or decision.get('package_binding')!=expected
                    or decision.get('human_gold') is not False or decision.get('training_eligible') is not False):
                raise ValueError('review decision artifact mismatch')
        entries=memory.get("entries")
        if not isinstance(entries,list) or guard.get("entries_sha256")!=_digest_entries(entries):
            raise ValueError("strict memory entry digest mismatch")
        proposal_file=memory.get("proposal_file_sha256")
        if not isinstance(proposal_file,str) or not re.fullmatch(r"[a-fA-F0-9]{64}",proposal_file) or guard.get("proposal_file_sha256")!=proposal_file:
            raise ValueError("strict memory proposal file mismatch")
        records=guard.get("approval_records")
        if not isinstance(records,dict) or len(records)!=len(entries):
            raise ValueError("strict memory approval record mapping mismatch")
        identities=set()
        approved_ids=set()
        for entry in entries:
            fields=("source_text_exact","file_path_exact","context_exact","import_method","translation")
            if not isinstance(entry,dict) or any(not isinstance(entry.get(k),str) or not entry[k] for k in fields):
                raise ValueError("invalid strict memory entry scope")
            if entry.get("approved") is not True or entry.get("human_gold") is not False or entry.get("training_eligible") is not False:
                raise ValueError("invalid strict memory approval flags")
            if entry.get("source")!=normalize_memory_text(entry["source_text_exact"]):
                raise ValueError("strict memory source mismatch")
            identity=tuple(entry[k] for k in fields[:-1])
            if identity in identities:
                raise ValueError("duplicate strict memory scope")
            identities.add(identity)
            approval_id=entry.get("approval_id")
            record=records.get(approval_id) if isinstance(approval_id,str) else None
            proposal=entry.get("proposal_sha256")
            if (not isinstance(approval_id,str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}",approval_id)
                    or approval_id in approved_ids or not isinstance(record,dict)
                    or not isinstance(proposal,str) or not re.fullmatch(r"[a-fA-F0-9]{64}",proposal)
                    or record.get("proposal_sha256")!=proposal
                    or record.get("scope_sha256")!=_digest_entries({k:entry[k] for k in fields})):
                raise ValueError("strict memory per-entry approval provenance mismatch")
            kind=entry.get('reviewer_kind',memory['review_kind'])
            if (kind not in {'owner-delegated-agent','user-confirmed'}
                    or (memory['review_kind'] in {'owner-delegated-agent','user-confirmed'} and kind!=memory['review_kind'])
                    or (memory['review_kind']!='owner-delegated-agent' and record.get('reviewer_kind')!=kind)):
                raise ValueError('strict memory per-entry reviewer mismatch')
            approved_ids.add(approval_id)
        if set(records)!=approved_ids:
            raise ValueError("strict memory extra approval records")
        return {**memory,"_package_dir":str(Path(package_dir).resolve())}
    except (OSError,ValueError,TypeError,UnicodeError) as error:
        return _scope_failure(package_dir,str(error))


def _approval_replace(path: Path, content: bytes) -> None:
    """Atomic single-file replace; caller owns snapshot CAS and transaction."""
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.pending')
    try:
        with temporary.open('xb') as handle:
            handle.write(content);handle.flush();os.fsync(handle.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists():
            temporary.unlink()


def activate_reviewed_memory(package: Path, rows: list[dict], snapshot: dict, current_snapshot) -> dict:
    """Called only under editor approval ownership after disk revalidation.

    Snapshot callback includes CSV and validation inputs; each owned activation
    updates only its own expected digest. A foreign mutation is never restored.
    """
    package=Path(package);meta=package/'.mt'
    expected=dict(snapshot);written={};originals={};rollback_errors=[]
    if current_snapshot()!=expected:
        raise ValueError('Dữ liệu vừa đổi; hãy xem trước lại')
    prior=load_translation_memory(package)
    strict=_strict_requested(package)
    if strict and prior.get('scope_error'):
        raise ValueError('Không thể mở rộng bộ nhớ đã duyệt không hợp lệ')
    entries=[dict(e)for e in prior.get('entries',[])] if strict else []
    old_guard=json.loads((meta/MEMORY_SCOPE_NAME).read_text(encoding='utf-8')) if strict else {}
    records={k:dict(v) for k,v in old_guard.get('approval_records',{}).items()}
    for entry in entries:
        entry.setdefault('reviewer_kind',prior.get('review_kind','owner-delegated-agent'))
        records[entry['approval_id']]['reviewer_kind']=entry['reviewer_kind']
    event=dict(version=1,reviewer_kind='user-confirmed',package_binding=_package_binding(package),
               selected_rows=rows,prior_snapshot=snapshot,human_gold=False,training_eligible=False)
    event_hash=_digest_entries(event)
    fields=('source_text_exact','file_path_exact','context_exact','import_method','translation')
    for row in rows:
        scope=(row['source_text'],row['file_path'],row['context'],row['import_method'])
        matching=[e for e in entries if tuple(e[k]for k in fields[:-1])==scope]
        if matching:
            if matching[0]['translation']!=row['translation']:
                raise ValueError('Bản dịch được duyệt xung đột; không tự thay thế')
            continue
        identifier='user-'+_digest_entries(dict(event=event_hash,key=row['key']))[:40]
        entry=dict(source=normalize_memory_text(row['source_text']),context_family=context_family(row),
            source_text_exact=row['source_text'],file_path_exact=row['file_path'],context_exact=row['context'],
            import_method=row['import_method'],translation=row['translation'],approval_id=identifier,
            proposal_sha256=_digest_entries(row),reviewer_kind='user-confirmed',approved=True,human_gold=False,training_eligible=False)
        entries.append(entry)
        records[identifier]=dict(proposal_sha256=entry['proposal_sha256'],scope_sha256=_digest_entries({k:entry[k]for k in fields}),reviewer_kind='user-confirmed')
    kind='mixed-explicit' if len({e['reviewer_kind']for e in entries})>1 else entries[0]['reviewer_kind']
    encode=lambda value:(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    decision_bytes=encode(event)
    decision_hash=hashlib.sha256(decision_bytes).hexdigest()
    memory=dict(version=MEMORY_VERSION,scope_policy=STRICT_MEMORY_POLICY,package_binding=_package_binding(package),
                approval_sha256=decision_hash,proposal_file_sha256=event_hash,review_kind=kind,entries=entries)
    guard=dict(version=1,scope_policy=STRICT_MEMORY_POLICY,package_binding=memory['package_binding'],
               approval_sha256=decision_hash,proposal_file_sha256=event_hash,entries_sha256=_digest_entries(entries),approval_records=records)
    outputs=[(MEMORY_SCOPE_NAME,encode(guard)),('translation_memory_decisions.json',decision_bytes),(MEMORY_NAME,encode(memory))]
    history=meta/'approval_history'/uuid.uuid4().hex
    history.mkdir(parents=True,exist_ok=False)
    # Backups are retained exact evidence, never granted approval by conversion.
    for name,_data in outputs:
        path=meta/name;originals[name]=path.read_bytes() if path.exists() else None
        if originals[name] is not None:
            (history/(name+'.backup')).write_bytes(originals[name])
    (history/'decision.json').write_bytes(decision_bytes)
    try:
        for name,data in outputs:
            if current_snapshot()!=expected:
                raise ValueError('Dữ liệu bị thay đổi trong lúc ghi; giữ lại xung đột')
            _approval_replace(meta/name,data)
            written[name]=data;expected['.mt/'+name]=hashlib.sha256(data).hexdigest()
        loaded=_load_strict(package)
        if loaded.get('scope_error') or current_snapshot()!=expected:
            raise ValueError('Không xác minh được dữ liệu sau khi ghi')
        return dict(ok=True,count=len(rows),memory_entries=len(entries),scope_policy=STRICT_MEMORY_POLICY)
    except (OSError,ValueError) as error:
        for name,data in reversed(list(written.items())):
            path=meta/name
            try:
                if path.is_symlink() or not path.is_file() or path.read_bytes()!=data:
                    rollback_errors.append(name+': foreign change retained');continue
                before=originals[name]
                if before is None:path.unlink()
                else:_approval_replace(path,before)
            except OSError as rollback:
                rollback_errors.append(name+': '+str(rollback))
        return dict(ok=False,error=str(error),rolled_back=not rollback_errors,rollback_errors=rollback_errors)


def normalize_memory_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"\s+", " ", value).strip()


def context_family(row: dict) -> str:
    context = str(row.get("context") or "").strip()
    if not context:
        return ""
    return context.split(":", 1)[0].casefold()


def _memory_key(row: dict) -> tuple[str, str, str]:
    return (
        normalize_memory_text(str(row.get("source_text") or "")),
        str(row.get("import_method") or "").strip(),
        context_family(row),
    )


def build_translation_memory(rows: list[dict], package_dir: str | Path | None = None) -> dict:
    """Build unique, structurally valid source→translation entries.

    Ambiguous source strings are intentionally omitted.  This prevents a
    choice label or repeated line from leaking wording from another context.
    """
    if package_dir and _strict_requested(package_dir):
        # Approved scope is an explicit allowlist, never learned from MT/CSV.
        return _load_strict(package_dir)
    from vntext.mt_translation_safety import validate_candidate
    from vntext.patch_gate import load_whitelist

    whitelist = load_whitelist(Path(package_dir)) if package_dir else set()
    grouped: dict[tuple[str, str, str], set[str]] = {}
    examples: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        source = str(row.get("source_text") or "").strip()
        translation = str(row.get("translation") or "").strip()
        if not source or not translation or source == translation:
            continue
        if validate_candidate(row, translation, whitelist):
            continue
        key = _memory_key(row)
        grouped.setdefault(key, set()).add(translation)
        examples[key] = row

    entries = []
    for (source, method, family), values in sorted(grouped.items()):
        if len(values) != 1:
            continue
        entries.append({
            "source": source,
            "import_method": method,
            "context_family": family,
            "translation": next(iter(values)),
        })
    memory = {
        "version": MEMORY_VERSION,
        "entries": entries,
        "source_rows": len(rows),
        "unique_entries": len(entries),
    }
    if package_dir:
        path = Path(package_dir) / ".mt" / MEMORY_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(memory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return memory


def load_translation_memory(package_dir: str | Path | None) -> dict:
    if not package_dir:
        return {"version": MEMORY_VERSION, "entries": []}
    if _strict_requested(package_dir):
        return _load_strict(package_dir)
    path = Path(package_dir) / ".mt" / MEMORY_NAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": MEMORY_VERSION, "entries": []}
    if not isinstance(payload, dict) or payload.get("version") != MEMORY_VERSION:
        return {"version": MEMORY_VERSION, "entries": []}
    entries = payload.get("entries")
    if not isinstance(entries, list):
        return {"version": MEMORY_VERSION, "entries": []}
    return {**payload, "entries": [entry for entry in entries if isinstance(entry, dict)]}


def memory_scope_is_current(memory: dict | None) -> bool:
    """Legacy is unchanged; strict snapshots must still match live artifacts."""
    if not memory or "scope_policy" not in memory:
        return True
    if memory.get("scope_policy")!=STRICT_MEMORY_POLICY or memory.get("scope_error"):
        return False
    package=memory.get("_package_dir")
    if not isinstance(package,str) or not package:
        return False
    fresh=_load_strict(package)
    return not fresh.get("scope_error") and fresh==memory


def lookup_translation_memory(row: dict, memory: dict | None) -> str | None:
    if not memory:
        return None
    if "scope_policy" in memory:
        if not memory_scope_is_current(memory):
            return None
        matches=[e for e in memory["entries"] if all(
            str(row.get(field) or "")==e[expected] for field,expected in
            (("source_text","source_text_exact"),("file_path","file_path_exact"),
             ("context","context_exact"),("import_method","import_method")))]
        return matches[0]["translation"] if len(matches)==1 else None
    source, method, family = _memory_key(row)
    if not source:
        return None
    exact = [
        entry for entry in memory.get("entries", [])
        if str(entry.get("source") or "") == source
        and str(entry.get("import_method") or "") == method
        and str(entry.get("context_family") or "") == family
    ]
    if len(exact) == 1:
        return str(exact[0].get("translation") or "").strip() or None
    # Fallback only when the same method has one unambiguous wording across
    # context families; context is still part of the preference order above.
    same_method = [
        entry for entry in memory.get("entries", [])
        if str(entry.get("source") or "") == source
        and str(entry.get("import_method") or "") == method
    ]
    values = {str(entry.get("translation") or "").strip() for entry in same_method}
    return next(iter(values)) if len(values) == 1 and next(iter(values), "") else None
