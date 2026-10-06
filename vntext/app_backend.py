"""Backend compatibility surface shared by worker and legacy desktop UIs.

This module deliberately contains no launcher or widget imports.  Public
callers should use its functions directly; ``vntext_studio`` re-exports them
for existing external integrations.
"""

from __future__ import annotations

import csv
from collections import Counter
import json
import re
import shutil
import time
from pathlib import Path

from vntext.entry import Entry, make_key
from vntext.package_io import (
    CSV_FIELDS,
    RAW_EXTRACT_ONLY_METHODS,
    is_direct_asset_patchable,
    read_csv_rows_file,
    read_translation_rows,
    resolve_translation_package_dir,
    split_asset_patchable_entries,
    write_csv,
    write_csv_rows_file,
    write_package,
)

VERSION = "0.1.2"

from vntext.extract import (
    ASSET_INDEX_FIELDS,
    QUOTED,
    TEXT_EXTS,
    UI_MONO_CLASSES,
    UI_SHORT_TEXT,
    UNITY_EXTS,
    _COMMON_DIALOGUE_WORDS,
    _clean_inline_text,
    _mono_class_name,
    _raw_candidate_csv_worthy,
    _replace_text_in_naninovel_command,
    _semicolon_csv_read,
    _semicolon_csv_write,
    _strip_raw_tail_noise,
    _typetree_field_is_display_text,
    _word_stats_for_raw,
    decode_candidate,
    extract_project,
    extract_unity_typetree,
    format_duration,
    has_binary_garbage,
    is_ui_text_field,
    iter_files,
    iter_naninovel_display_texts,
    looks_like_code_or_asset_token,
    looks_like_demo_or_placeholder,
    raw_text_quality,
    rel_path,
    scan_naninovel_blob,
    short_dialogue_fragment_ok,
    should_naninovel_scan,
)
from vntext.patch import apply_translation_package
from vntext.unity_analyzer import detect_resource_kind


def build_asset_index(input_path: str, output_dir: str, progress_callback=None):
    try:
        import UnityPy
    except Exception as exc:
        return [], [f"UnityPy not available: {exc}"]

    root = Path(input_path)
    base = root if root.is_dir() else root.parent
    unity_paths = [
        p
        for p in iter_files(root)
        if p.suffix.lower() in UNITY_EXTS or detect_resource_kind(p).get("is_unity_extractable")
    ]
    total = max(1, len(unity_paths))
    started = time.time()
    rows = []
    errors = []
    for index, path in enumerate(unity_paths, start=1):
        rel = rel_path(path, base)
        try:
            env = UnityPy.load(str(path))
        except Exception as exc:
            errors.append(f"{path}: {exc}")
            if progress_callback:
                elapsed = time.time() - started
                done = index
                eta = (elapsed / done) * (total - done) if done else 0
                progress_callback({
                    "done": done,
                    "total": total,
                    "file": rel,
                    "found": len(rows),
                    "elapsed": elapsed,
                    "eta": eta,
                    "phase": "asset_index",
                })
            continue
        for obj in env.objects:
            type_name = getattr(obj.type, "name", str(obj.type))
            path_id = getattr(obj, "path_id", "")
            name = ""
            size = ""
            try:
                data = obj.read()
                name = getattr(data, "m_Name", "") or getattr(data, "name", "")
                script = getattr(data, "m_Script", None)
                if script is None:
                    script = getattr(data, "script", None)
                if isinstance(script, (bytes, bytearray, str)):
                    size = len(script)
            except Exception:
                pass
            rows.append({
                "file_path": rel,
                "path_id": path_id,
                "type": type_name,
                "name": name,
                "size": size,
                "container": str(path),
            })
        if progress_callback:
            elapsed = time.time() - started
            done = index
            eta = (elapsed / done) * (total - done) if done else 0
            progress_callback({
                "done": done,
                "total": total,
                "file": rel,
                "found": len(rows),
                "elapsed": elapsed,
                "eta": eta,
                "phase": "asset_index",
            })

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "asset_index.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=ASSET_INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows, errors



def _candidate_has_gibberish_word_shape(cleaned: str) -> bool:
    """Bat cac raw candidate bi cat lech byte nhung van trong nhu chu alphabet."""
    if not cleaned:
        return True
    if any(ch in cleaned for ch in "`|^~&"):
        return True
    # Ky tu ?/! chen giua word: ca??qbear, ab!cd.
    if re.search(r"[A-Za-z]{1,6}[?!]{2,}[A-Za-z]", cleaned):
        return True
    # Apostrophe bat dau mot manh tu bi cat: 'pness, Afa. Van cho phep quote dung: 'my little pony'?
    if re.match(r"^'[a-z]{1,8}(?:\s|,|\.|!|\?)", cleaned) and cleaned.count("'") < 2:
        return True
    # Mot chu cai tien to binary + word viet thuong: Jp..., Pll go!, Fo girl?
    if re.match(r"^[A-Z][a-z]{0,2}[.!?,Ã¢â‚¬Â¦]*\s+[a-z]", cleaned):
        first = re.findall(r"[A-Za-z']+", cleaned)
        fw = first[0].strip("'Ã¢â‚¬â„¢") if first else ""
        # Chi bat prefix 1-2 ky tu lech offset. Khong giet cau binh thuong: One would..., Why is..., All right...
        if len(fw) <= 2 and fw not in {"I", "A", "Ah", "Oh", "No", "Ok", "OK", "Is", "It", "My", "He", "We", "As", "If", "So", "Of", "To", "In", "On", "At", "Mr", "Ms", "Dr"}:
            return True
    # Camel/fused token giua cau.
    if re.search(r"[a-z]{2,}[A-Z][A-Za-z]", cleaned):
        return True
    # Cac mau v&by,Some / qbear / w2x.
    if re.search(r"[A-Za-z]\W{1,3}[A-Za-z]{1,3}\W{1,3}[A-Za-z]", cleaned) and any(ch in cleaned for ch in "&@#$%|~^`"):
        return True
    return False


def _candidate_sentence_like_enough(cleaned: str) -> bool:
    """Nhan dien dong raw candidate nen tu dong day vao translation.csv.

    Chap nhan ca fragment thoai/narration binh thuong, vi game VN hay cat theo line.
    Khong doi ten cot/key/source_text; chi phan loai dong.
    """
    if not cleaned:
        return False
    if short_dialogue_fragment_ok(cleaned):
        return True
    lowered = cleaned.lower()
    if lowered in UI_SHORT_TEXT:
        return True
    # UI/title ending/label hien thi.
    if re.fullmatch(r"[A-Z0-9][A-Z0-9 '\-()]{3,64}", cleaned):
        if not looks_like_code_or_asset_token(cleaned):
            return True
    if lowered.startswith('title="') and 6 <= len(cleaned) <= 80:
        return True
    if cleaned.startswith("(") and cleaned.endswith(")") and 5 <= len(cleaned) <= 80:
        return True

    words = [w.strip("'Ã¢â‚¬â„¢").lower() for w in re.findall(r"[A-Za-z']+", cleaned)]
    long_words = [w for w in words if len(w) >= 3]
    if not words:
        return False
    common = sum(1 for w in words if w in _COMMON_DIALOGUE_WORDS or w.rstrip('s') in _COMMON_DIALOGUE_WORDS)
    has_mark = any(mark in cleaned for mark in ".!?,:;Ã¢â‚¬Â¦Ã¢â„¢Â¡Ã¢â„¢Â¥")
    has_space = " " in cleaned
    ends_cleanish = cleaned[-1] in ".!?Ã¢â‚¬Â¦Ã¢â„¢Â¡Ã¢â„¢Â¥)Ã¢â‚¬â„¢'\"]}>" or len(cleaned) >= 18

    # Cau/fragment bat dau hoa, co it nhat 2-3 tu va co tin hieu hoi thoai.
    starts_ok = cleaned[0].isupper() or cleaned[0] in "'\"([{<Ã‚Â¿Ã‚Â¡Ã¢â‚¬Â¦Ã¢â‚¬Å“Ã¢â‚¬Ëœ" or cleaned.startswith("...")
    if starts_ok and has_space:
        if common >= 1 and len(words) >= 2 and ends_cleanish:
            return True
        if common >= 1 and len(long_words) >= 2 and (has_mark or len(cleaned) >= 16):
            return True
        if has_mark and len(words) >= 2 and len(cleaned) >= 8:
            # Short dialogue/title fragments with clean punctuation.
            return True
        if len(long_words) >= 4 and (has_mark or len(cleaned) >= 20):
            return True
        if len(words) >= 3 and common >= 1 and len(cleaned) >= 14:
            # One would be fine / Why is he suddenly try
            return True

    # Lowercase dau dong thuong la bi cat dau, nhung neu la narration dai va sach thi van can dich.
    if cleaned[0].islower() and has_space:
        if len(long_words) >= 5 and common >= 1 and len(cleaned) >= 28:
            return True
        if len(long_words) >= 6 and cleaned[-1] in ".!?Ã¢â‚¬Â¦Ã¢â„¢Â¡Ã¢â„¢Â¥)Ã¢â‚¬â„¢'\"]}>":
            return True
    return False


def auto_candidate_action(text: str) -> str:
    """Tra ve promote/keep/reject cho raw_candidates.csv.

    v1.24: manh tay promote cac cau/fragment doc duoc binh thuong de giam duyet tay.
    Chi giu lai nhung dong lung chung; reject cac raw cat lech byte ro rang.
    """
    cleaned = _strip_raw_tail_noise(_clean_inline_text(text))
    if not cleaned:
        return "reject"
    hard_bad = (
        has_binary_garbage(cleaned)
        or looks_like_code_or_asset_token(cleaned)
        or looks_like_demo_or_placeholder(cleaned)
        or _candidate_has_gibberish_word_shape(cleaned)
    )
    if hard_bad:
        return "reject"

    worthy = _raw_candidate_csv_worthy(cleaned)
    visible, letters, digits, symbols, words, long_words = _word_stats_for_raw(cleaned)
    if visible == 0 or letters / visible < 0.55:
        return "reject"
    if symbols / visible > 0.34 and not any(mark in cleaned for mark in "Ã¢â„¢Â¡Ã¢â„¢Â¥Ã¢â‚¬Â¦"):
        return "reject"
    if re.search(r"[A-Za-z]{1,3}\d|\d[A-Za-z]{1,3}", cleaned) and len(cleaned) < 40:
        return "reject"

    # Neu filter compact cu cho la khong worthy nhung cau van doc duoc, khong reject thang.
    # Day la loi v1.23: nhieu cau binh thuong bi bat duyet tay.
    if not worthy and _candidate_sentence_like_enough(cleaned):
        return "promote"
    if not worthy and len(long_words) >= 3 and " " in cleaned:
        return "keep"
    if not worthy:
        return "reject"

    # Cac dong 2 tu nhung khong co tu common/short dialogue thuong la gibberish: Kuany wayf!
    common = sum(1 for w in [x.strip("'Ã¢â‚¬â„¢").lower() for x in re.findall(r"[A-Za-z']+", cleaned)] if w in _COMMON_DIALOGUE_WORDS or w.rstrip('s') in _COMMON_DIALOGUE_WORDS)
    if len(words) <= 2 and not short_dialogue_fragment_ok(cleaned) and common == 0:
        # Kuany wayf! / Jtrs, phys = reject. Chi cho qua title UI ro hoac ten nhan vat + noun.
        looks_ui_caps = bool(re.fullmatch(r"[A-Z0-9][A-Z0-9 '\-()]{3,64}", cleaned))
        if not looks_ui_caps:
            return "reject"

    if _candidate_sentence_like_enough(cleaned):
        return "promote"

    # Incomplete nhung doc duoc: giu de duyÃ¡Â»â€¡t, khÃƒÂ´ng reject.
    if len(long_words) >= 3 and " " in cleaned and not cleaned[0].islower():
        return "keep"
    return "keep"


def auto_process_raw_candidates(package_dir: str | Path, progress_callback=None) -> dict:
    """Tu dong xu ly raw_candidates.csv.

    - promote: append vao translation.csv, giu key/source_text/cot CSV.
    - keep: giu trong raw_candidates.csv de duyet tay.
    - reject: chuyen sang raw_candidates_rejected.csv.
    """
    package = resolve_translation_package_dir(package_dir)
    translation_path = package / "translation.csv"
    raw_path = package / "raw_candidates.csv"
    if not translation_path.exists():
        raise FileNotFoundError(f"Khong thay translation.csv trong {package}")
    if not raw_path.exists():
        raise FileNotFoundError(f"Khong thay raw_candidates.csv trong {package}")

    trans_fields, trans_rows = read_csv_rows_file(translation_path)
    raw_fields, raw_rows = read_csv_rows_file(raw_path)
    fields = list(trans_fields)
    for field in raw_fields:
        if field not in fields:
            fields.append(field)
    existing = {row.get("key", "").strip() for row in trans_rows if row.get("key", "").strip()}
    promoted, kept, rejected = [], [], []
    total = max(1, len(raw_rows) + 2)
    started = time.time()

    def emit(done: int, label: str, found: int = 0):
        if not progress_callback:
            return
        elapsed = time.time() - started
        safe_done = min(max(done, 0), total)
        eta = (elapsed / safe_done) * (total - safe_done) if safe_done else 0
        progress_callback({
            "done": safe_done,
            "total": total,
            "file": label,
            "found": found,
            "elapsed": elapsed,
            "eta": eta,
            "phase": "auto_raw",
        })

    emit(0, f"Dang doc {len(raw_rows)} dong raw_candidates...", found=0)
    for index, row in enumerate(raw_rows, start=1):
        key = row.get("key", "").strip()
        text = row.get("source_text", "")
        action = auto_candidate_action(text)
        if action == "promote" and key and key not in existing:
            new_row = {field: row.get(field, "") for field in fields}
            promoted.append(new_row)
            existing.add(key)
        elif action == "reject":
            rejected.append({field: row.get(field, "") for field in fields})
        else:
            kept.append({field: row.get(field, "") for field in fields})
        if index == len(raw_rows) or index % 250 == 0:
            emit(index, f"Dang phan loai {index}/{len(raw_rows)}", found=len(promoted))

    emit(len(raw_rows) + 1, "Dang ghi CSV...", found=len(promoted))

    if promoted:
        trans_rows.extend(promoted)
        write_csv_rows_file(translation_path, fields, trans_rows)
    write_csv_rows_file(raw_path, fields, kept)
    if rejected:
        old_fields, old_rows = read_csv_rows_file(package / "raw_candidates_rejected.csv")
        reject_fields = list(fields)
        for field in old_fields:
            if field not in reject_fields:
                reject_fields.append(field)
        old_rows.extend(rejected)
        write_csv_rows_file(package / "raw_candidates_rejected.csv", reject_fields, old_rows)

    report = [
        "VNText Studio auto raw candidate report",
        f"package: {package}",
        f"input_raw_candidates: {len(raw_rows)}",
        f"auto_promoted_to_translation: {len(promoted)}",
        f"kept_for_manual_review: {len(kept)}",
        f"rejected_as_junk: {len(rejected)}",
        f"translation_rows: {len(trans_rows)}",
        "note: auto promote chi dua cau/thoai kha chac vao translation.csv; dong lung chung van giu de duyet tay.",
    ]
    (package / "raw_candidate_auto_report.txt").write_text("\n".join(report), "utf-8")
    cleanup_package_zip_files(package)
    emit(total, "Hoan tat auto loc raw", found=len(trans_rows))
    return {
        "input": len(raw_rows),
        "promoted": len(promoted),
        "kept": len(kept),
        "rejected": len(rejected),
        "translation_rows": len(trans_rows),
    }


def export_unity_internal_dump(input_path: str, output_dir: str, extract_level: str = "balanced", progress_callback=None) -> dict:
    """Tu dong dump/soi Unity ngay trong app, khong can UABEA/UnityEX.

    Output debug khong bat nguoi dung sua tay dump:
    - asset_index.csv: object trong asset/bundle.
    - unity_auto_dump/unity_extracted_strings.csv: string lay duoc tu TypeTree/TextAsset/raw scanners.
    - unity_auto_dump/textassets/*.txt: TextAsset script/raw text doc duoc.
    - unity_auto_dump/auto_dump_report.txt: tong ket debug.
    """
    root = Path(input_path)
    base = root if root.is_dir() else root.parent
    out = Path(output_dir)
    dump_dir = out / "unity_auto_dump"
    if dump_dir.exists():
        shutil.rmtree(dump_dir)
    dump_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    unity_files = [
        p
        for p in iter_files(root)
        if p.suffix.lower() in UNITY_EXTS or detect_resource_kind(p).get("is_unity_extractable")
    ]
    total = max(1, len(unity_files) + 2)

    def emit(done: int, label: str, found: int = 0):
        if not progress_callback:
            return
        elapsed = time.time() - started
        safe_done = min(max(done, 0), total)
        eta = (elapsed / safe_done) * (total - safe_done) if safe_done else 0
        progress_callback({
            "done": safe_done,
            "total": total,
            "file": label,
            "found": found,
            "elapsed": elapsed,
            "eta": eta,
            "phase": "dump",
        })

    emit(0, "Dang lap asset_index.csv...", found=0)
    rows, index_errors = build_asset_index(input_path, output_dir)
    emit(1, f"asset_index: {len(rows)} object", found=len(rows))
    string_rows = []
    textasset_count = 0

    for index, path in enumerate(unity_files, start=2):
        rel = rel_path(path, base)
        emit(index, rel, found=len(string_rows))
        # TextAsset/object strings qua UnityPy extractor.
        try:
            for entry in extract_unity_typetree(path, base) or []:
                string_rows.append({
                    "file_path": entry.file_path,
                    "context": entry.context,
                    "object_info": entry.object_info,
                    "source_text": entry.source_text,
                    "backend": entry.backend,
                    "import_method": entry.import_method,
                    "safety": entry.safety,
                    "locator_json": json.dumps(entry.locator, ensure_ascii=False),
                    "bucket": "translation" if not entry.review_only else "review",
                })
        except Exception as exc:
            index_errors.append(f"extract_unity_typetree {path}: {exc}")

        # TextAsset raw dump ra file rieng neu doc duoc bang UnityPy.
        try:
            import UnityPy
            env = UnityPy.load(str(path))
            for obj in env.objects:
                type_name = getattr(obj.type, "name", str(obj.type))
                if type_name != "TextAsset":
                    continue
                path_id = getattr(obj, "path_id", "")
                try:
                    data = obj.read()
                    name = getattr(data, "m_Name", "") or getattr(data, "name", "") or f"path_{path_id}"
                    script = getattr(data, "m_Script", None)
                    if script is None:
                        script = getattr(data, "script", None)
                    if isinstance(script, str):
                        txt = script
                    elif isinstance(script, (bytes, bytearray)):
                        txt = decode_candidate(bytes(script), "utf-8") or decode_candidate(bytes(script), "utf-16le") or ""
                    else:
                        txt = ""
                    if txt:
                        safe_rel = re.sub(r"[^A-Za-z0-9_.-]+", "_", rel)
                        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name))[:80]
                        file_out = dump_dir / "textassets" / f"{safe_rel}__{path_id}_{safe_name}.txt"
                        file_out.parent.mkdir(parents=True, exist_ok=True)
                        file_out.write_text(txt, "utf-8", errors="ignore")
                        textasset_count += 1
                except Exception:
                    continue
        except Exception as exc:
            index_errors.append(f"TextAsset dump {path}: {exc}")

        # Raw/Naninovel candidates ma app tu soi duoc.
        try:
            if should_naninovel_scan(path, path.suffix.lower(), is_unity_resource=True):
                for entry in scan_naninovel_blob(path, base, extract_level) or []:
                    string_rows.append({
                        "file_path": entry.file_path,
                        "context": entry.context,
                        "object_info": entry.object_info,
                        "source_text": entry.source_text,
                        "backend": entry.backend,
                        "import_method": entry.import_method,
                        "safety": entry.safety,
                        "locator_json": json.dumps(entry.locator, ensure_ascii=False),
                        "bucket": "translation" if not entry.review_only else ("raw_candidate" if entry.import_method == "naninovel_raw_candidate" else "review"),
                    })
        except Exception as exc:
            index_errors.append(f"scan_naninovel_blob {path}: {exc}")

    dump_fields = ["file_path", "context", "object_info", "source_text", "backend", "import_method", "safety", "locator_json", "bucket"]
    dump_csv = dump_dir / "unity_extracted_strings.csv"
    with dump_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=dump_fields)
        writer.writeheader()
        writer.writerows(string_rows)

    backend_counts = Counter(row["backend"] for row in string_rows)
    bucket_counts = Counter(row["bucket"] for row in string_rows)
    report = [
        "VNText Studio internal Unity dump/debug report",
        f"version: {VERSION}",
        f"input: {input_path}",
        f"unity_files: {len(unity_files)}",
        f"asset_index_rows: {len(rows)}",
        f"debug_string_rows: {len(string_rows)}",
        f"textasset_dump_files: {textasset_count}",
        "bucket_counts:",
    ]
    for name, count in sorted(bucket_counts.items(), key=lambda x: (-x[1], x[0])):
        report.append(f"  {name}: {count}")
    report.append("backend_counts:")
    for name, count in sorted(backend_counts.items(), key=lambda x: (-x[1], x[0])):
        report.append(f"  {name}: {count}")
    if index_errors:
        report.append("errors:")
        report.extend(index_errors[:200])
        if len(index_errors) > 200:
            report.append(f"... {len(index_errors)-200} errors hidden")
    (dump_dir / "auto_dump_report.txt").write_text("\n".join(report), "utf-8")
    emit(total, "Hoan tat dump Unity", found=len(string_rows))
    return {
        "asset_index_rows": len(rows),
        "debug_string_rows": len(string_rows),
        "textasset_dump_files": textasset_count,
        "errors": len(index_errors),
        "dump_dir": str(dump_dir),
    }

def promote_raw_candidates(package_dir: str | Path, keys: set[str], move: bool = True) -> dict:
    """Chuyen raw_candidates da tick sang translation.csv.

    - Giu nguyen key/source_text/ten cot.
    - Khong them dong trung key vao translation.csv.
    - Neu move=True thi xoa dong da chuyen khoi raw_candidates.csv de de theo doi.
    """
    package = resolve_translation_package_dir(package_dir)
    translation_path = package / "translation.csv"
    raw_path = package / "raw_candidates.csv"
    if not translation_path.exists():
        raise FileNotFoundError(f"Khong thay translation.csv trong {package}")
    if not raw_path.exists():
        raise FileNotFoundError(f"Khong thay raw_candidates.csv trong {package}")
    if not keys:
        return {"promoted": 0, "skipped_duplicate": 0, "remaining_raw": 0, "translation_rows": 0}

    trans_fields, trans_rows = read_csv_rows_file(translation_path)
    raw_fields, raw_rows = read_csv_rows_file(raw_path)
    fields = list(trans_fields)
    for field in raw_fields:
        if field not in fields:
            fields.append(field)
    existing = {row.get("key", "").strip() for row in trans_rows if row.get("key", "").strip()}
    promoted_rows = []
    remaining_rows = []
    skipped_duplicate = 0
    keyset = {str(k).strip() for k in keys if str(k).strip()}
    for row in raw_rows:
        key = row.get("key", "").strip()
        if key in keyset:
            if key in existing:
                skipped_duplicate += 1
                if not move:
                    remaining_rows.append(row)
                continue
            new_row = {field: row.get(field, "") for field in fields}
            new_row["translation"] = row.get("translation", "")
            promoted_rows.append(new_row)
            existing.add(key)
            if not move:
                remaining_rows.append(row)
        else:
            remaining_rows.append(row)

    if promoted_rows:
        trans_rows.extend(promoted_rows)
        write_csv_rows_file(translation_path, fields, trans_rows)
    if move:
        write_csv_rows_file(raw_path, fields, remaining_rows)

    report = [
        "VNText Studio raw candidate promote report",
        f"package: {package}",
        f"promoted: {len(promoted_rows)}",
        f"skipped_duplicate: {skipped_duplicate}",
        f"remaining_raw_candidates: {len(remaining_rows)}",
        f"translation_rows: {len(trans_rows)}",
        "note: dong duoc chuyen giu nguyen key/source_text/cot CSV; import_method/safety van giu nhu cu.",
    ]
    (package / "raw_candidate_promote_report.txt").write_text("\n".join(report), "utf-8")
    cleanup_package_zip_files(package)
    return {
        "promoted": len(promoted_rows),
        "skipped_duplicate": skipped_duplicate,
        "remaining_raw": len(remaining_rows),
        "translation_rows": len(trans_rows),
    }


def cleanup_package_zip_files(output_dir: Path) -> int:
    """Khong tao ZIP goi dich nua.

    Tu v1.25, Unity_Translation_Package la thu muc lam viec chinh.
    App chi doc/ghi truc tiep cac file trong thu muc nay:
    translation.csv, manifest.json, raw_candidates.csv, review_only.csv,
    asset_index.csv, unity_auto_dump/...

    Ham nay chi don cac ZIP goi cu neu con ton tai de tranh nguoi dung sua nham.
    """
    output_dir = Path(output_dir)
    candidates = {
        output_dir / f"{output_dir.name}.zip",
        output_dir.parent / f"{output_dir.name}.zip",
        output_dir / "Unity_Translation_Package.zip",
        output_dir.parent / "Unity_Translation_Package.zip",
    }
    removed = 0
    for zip_path in candidates:
        try:
            if zip_path.exists() and zip_path.is_file() and zip_path.suffix.lower() == ".zip":
                zip_path.unlink()
                removed += 1
        except OSError:
            pass
    return removed


def import_external_dump(dump_path: str, output_dir: str):
    root = Path(dump_path)
    files = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
    entries = []
    for file in files:
        try:
            text = file.read_text("utf-8-sig", errors="ignore")
        except OSError:
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            found = [m.group(1).strip() for m in QUOTED.finditer(line)]
            if not found:
                stripped = line.strip()
                found = [stripped] if raw_text_quality(stripped, for_main=True) else []
            for value in found:
                if raw_text_quality(value, for_main=True):
                    entries.append(Entry(
                        source_text=value,
                        file_path=str(file),
                        context=f"external_dump_line:{line_no}",
                        import_method="external_dump_reimport",
                        safety="conditional",
                        locator={"dump_file": str(file), "line": line_no},
                        backend="external_dump",
                    ).finalize())
    stats = {"mode": "external_dump", "files_scanned": len(files), "main_entries": len(entries), "review_entries": 0, "errors": []}
    write_package(output_dir, entries, [], stats, separate_review=True)
    return entries, stats
