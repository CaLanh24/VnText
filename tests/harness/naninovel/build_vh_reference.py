"""Build a conservative EN -> VI Naninovel reference from two Unity builds.

The localized and English builds keep the same serialized string slots.  This
tool compares those slots inside the same MonoBehaviour/path_id and refuses a
whole object when its aligned string structure is not identical.  It never
writes either input game.
"""
from __future__ import annotations

import argparse
import json
import sys
import gc
import time
from pathlib import Path


def _bootstrap(root: Path) -> None:
    value = str(root.resolve())
    if value not in sys.path:
        sys.path.insert(0, value)


_TECHNICAL_EXACT = {
    "naninovel",
    "naninovel.commands",
    "opening",
    "labelscriptline",
    "commandscriptline",
    "generictextscriptline",
    "commentscriptline",
    "printtext",
    "addchoice",
}


def _display_candidate(text: str, choices: set[str], *, source: bool) -> bool:
    from vntext.extract import naninovel_script_display_candidate

    value = str(text or "").strip()
    lowered = value.lower()
    if lowered in _TECHNICAL_EXACT or "elringus.naninovel" in lowered:
        return False
    if lowered.endswith(".commands") or lowered.endswith(".runtime"):
        return False
    if value in choices:
        return True
    return naninovel_script_display_candidate(value, choices)


def _object_map(env):
    return {
        int(obj.path_id): obj
        for obj in env.objects
        if str(getattr(getattr(obj, "type", None), "name", "")) == "MonoBehaviour"
    }


def _script_map(env):
    from vntext.extract import collect_naninovel_script_path_ids, _mono_script_path_id

    scripts = collect_naninovel_script_path_ids(env.objects)
    return {
        int(obj.path_id): obj
        for obj in env.objects
        if str(getattr(getattr(obj, "type", None), "name", "")) == "MonoBehaviour"
        and _mono_script_path_id(obj) in scripts
    }


def _same_structure(en_items, vh_items) -> bool:
    if len(en_items) != len(vh_items):
        return False
    # Names/types and metadata are unchanged between the two builds.  A high
    # equal-string ratio rejects accidental pairing when a slot was inserted.
    equal = 0
    for left, right in zip(en_items, vh_items):
        if left["text"] == right["text"]:
            equal += 1
    return equal >= max(8, int(len(en_items) * 0.20))


def dump_full_slots(game_path: Path, out_path: Path) -> dict:
    """Dump one build at a time so UnityPy environments do not coexist in RAM."""
    import UnityPy
    from vntext.extract import _object_raw_bytes, _scan_unity_length_prefixed_strings

    started = time.time()
    env = UnityPy.load(str(game_path))
    objects = _script_map(env)
    slots: dict[str, list[str]] = {}
    for number, (path_id, obj) in enumerate(sorted(objects.items()), start=1):
        raw = _object_raw_bytes(obj)
        items = _scan_unity_length_prefixed_strings(raw, step=4, seeded=False)
        slots[str(path_id)] = [str(item.get("text") or "") for item in items]
        del items, raw
        if number % 10 == 0:
            print(f"objects {number}/{len(objects)} slots={sum(map(len, slots.values()))}", flush=True)
    result = {
        "version": "2.0.0",
        "input": str(game_path),
        "script_objects": len(objects),
        "slots": slots,
        "elapsed_seconds": round(time.time() - started, 2),
    }
    del objects, env
    gc.collect()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("script_objects", "elapsed_seconds")}, ensure_ascii=False), flush=True)
    return result


def _decode_textasset_script(script, decode_candidate):
    if isinstance(script, str):
        return script, "utf-8"
    if isinstance(script, (bytes, bytearray)):
        raw = bytes(script)
        text = decode_candidate(raw, "utf-8") or decode_candidate(raw, "utf-16le")
        return text, "bytes"
    return "", ""


def dump_textasset_lines(game_path: Path, out_path: Path) -> dict:
    """Dump TextAsset lines from one build without keeping two UnityPy envs."""
    import UnityPy
    from vntext.extract import (
        decode_candidate,
        iter_textasset_language_table_cells,
        iter_textasset_lines,
    )

    started = time.time()
    env = UnityPy.load(str(game_path))
    assets: dict[str, dict] = {}
    for obj in env.objects:
        if str(getattr(getattr(obj, "type", None), "name", "")) != "TextAsset":
            continue
        try:
            data = obj.read()
            name = str(getattr(data, "m_Name", "") or getattr(data, "name", "") or "")
            text, encoding = _decode_textasset_script(
                getattr(data, "m_Script", None), decode_candidate
            )
            if not text:
                continue
            raw_lines = text.splitlines(keepends=True)
            tables = list(iter_textasset_language_table_cells(text))
            if tables:
                entries = [
                    {
                        "line_index": line_index,
                        "method": "unity_textasset_table_cell",
                        **{key: value for key, value in parsed.items() if key != "newline"},
                    }
                    for line_index, parsed in tables
                ]
            else:
                entries = [
                    {
                        "line_index": line_index,
                        "method": "unity_textasset_line",
                        **{key: value for key, value in parsed.items() if key != "newline"},
                    }
                    for line_index, parsed in iter_textasset_lines(text)
                ]
            assets[str(obj.path_id)] = {
                "path_id": str(obj.path_id),
                "name": name,
                "encoding": encoding,
                "line_count": len(raw_lines),
                "entries": entries,
            }
        except Exception:
            continue
    del env
    gc.collect()
    result = {
        "version": "3.0.0",
        "input": str(game_path),
        "textasset_objects": len(assets),
        "assets": assets,
        "elapsed_seconds": round(time.time() - started, 2),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "textasset_objects": len(assets),
                "entries": sum(len(asset["entries"]) for asset in assets.values()),
                "elapsed_seconds": result["elapsed_seconds"],
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    return result


def build_textasset_reference(en_dump_path: Path, vh_dump_path: Path, out_path: Path) -> dict:
    """Pair TextAsset entries only when path_id/name/line structure is stable."""
    from vntext.extract import has_vietnamese_chars

    en_data = json.loads(en_dump_path.read_text(encoding="utf-8"))
    vh_data = json.loads(vh_dump_path.read_text(encoding="utf-8"))
    rows_by_key: dict[tuple, dict] = {}
    stats = {
        "en_textasset_objects": len(en_data.get("assets", {})),
        "vh_textasset_objects": len(vh_data.get("assets", {})),
        "common_textasset_objects": 0,
        "aligned_objects": 0,
        "skipped_structure": 0,
        "aligned_entries": 0,
        "candidate_pairs": 0,
        "vietnamese_pairs": 0,
        "ambiguous_signatures": 0,
    }

    for path_id, en_asset in sorted(
        en_data.get("assets", {}).items(), key=lambda pair: int(pair[0])
    ):
        vh_asset = vh_data.get("assets", {}).get(path_id)
        if vh_asset is None:
            continue
        stats["common_textasset_objects"] += 1
        if (
            en_asset.get("name") != vh_asset.get("name")
            or en_asset.get("line_count") != vh_asset.get("line_count")
        ):
            stats["skipped_structure"] += 1
            continue
        en_entries = {
            (entry.get("method"), entry.get("line_index"), entry.get("column_index", -1)): entry
            for entry in en_asset.get("entries", [])
        }
        vh_entries = {
            (entry.get("method"), entry.get("line_index"), entry.get("column_index", -1)): entry
            for entry in vh_asset.get("entries", [])
        }
        if set(en_entries) != set(vh_entries):
            stats["skipped_structure"] += 1
            continue
        stats["aligned_objects"] += 1
        stats["aligned_entries"] += len(en_entries)
        for locator, en_entry in sorted(en_entries.items(), key=lambda pair: pair[0]):
            vh_entry = vh_entries[locator]
            source = str(en_entry.get("text") or "").strip()
            translation = str(vh_entry.get("text") or "").strip()
            if not source or not translation or source == translation:
                continue
            stats["candidate_pairs"] += 1
            if not has_vietnamese_chars(translation):
                continue
            stats["vietnamese_pairs"] += 1
            method = str(en_entry.get("method") or "unity_textasset_line")
            name = str(en_asset.get("name") or "")
            line_index = int(en_entry.get("line_index") or 0)
            if method == "unity_textasset_table_cell":
                context = (
                    f"TextAsset:{name}:table:{en_entry.get('row_key', '')}:"
                    f"{en_entry.get('column_name', '')}"
                )
            else:
                context = f"TextAsset:{name}:line:{line_index + 1}"
            row = {
                "source_text_en": source,
                "translation_vh": translation,
                "context": context,
                "file_path": "data.unity3d",
                "object_info": f"TextAsset:{path_id}:{name}",
                "import_method": method,
                "path_id": str(path_id),
                "field": "m_Script",
                "encoding": en_asset.get("encoding", ""),
                "line_index": line_index,
                "line_mode": en_entry.get("mode", ""),
                "prefix": en_entry.get("prefix", ""),
            }
            if method == "unity_textasset_table_cell":
                row.update(
                    {
                        "delimiter": ";",
                        "column_index": en_entry.get("column_index", ""),
                        "column_name": en_entry.get("column_name", ""),
                        "row_key": en_entry.get("row_key", ""),
                        "header_line_index": en_entry.get("header_line_index", ""),
                    }
                )
            key = (context, source, method)
            previous = rows_by_key.get(key)
            if previous is None:
                rows_by_key[key] = row
            elif previous["translation_vh"] != translation:
                rows_by_key.pop(key, None)
                stats["ambiguous_signatures"] += 1

    rows = sorted(
        rows_by_key.values(),
        key=lambda row: (int(row["path_id"]), int(row["line_index"]), row["context"]),
    )
    result = {
        "version": "3.0.0",
        "inputs": {
            "en_dump": str(en_dump_path),
            "vh_dump": str(vh_dump_path),
        },
        "stats": {**stats, "reference_rows": len(rows)},
        "rows": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["stats"], ensure_ascii=False), flush=True)
    return result


def build_from_dumps(en_dump_path: Path, vh_dump_path: Path, out_path: Path) -> dict:
    """Pair already dumped full slots without loading UnityPy."""
    from vntext.extract import (
        _naninovel_command_role,
        has_vietnamese_chars,
        iter_naninovel_display_texts,
    )

    en_data = json.loads(en_dump_path.read_text(encoding="utf-8"))
    vh_data = json.loads(vh_dump_path.read_text(encoding="utf-8"))
    en_slots = en_data.get("slots", {})
    vh_slots = vh_data.get("slots", {})
    rows_by_key: dict[tuple, dict] = {}
    stats = {
        "en_script_objects": len(en_slots),
        "vh_script_objects": len(vh_slots),
        "common_script_objects": 0,
        "aligned_objects": 0,
        "skipped_structure": 0,
        "aligned_slots": 0,
        "candidate_pairs": 0,
        "vietnamese_pairs": 0,
        "ambiguous_signatures": 0,
    }
    for path_id, en_items in sorted(en_slots.items(), key=lambda pair: int(pair[0])):
        vh_items = vh_slots.get(path_id)
        if vh_items is None:
            continue
        stats["common_script_objects"] += 1
        if not _same_structure(
            [{"text": text} for text in en_items],
            [{"text": text} for text in vh_items],
        ):
            stats["skipped_structure"] += 1
            continue
        stats["aligned_objects"] += 1
        stats["aligned_slots"] += len(en_items)
        choices: set[str] = set()
        for raw in en_items:
            if _naninovel_command_role(raw) == "choice":
                choices.update(part for part in iter_naninovel_display_texts(raw) if part)
        for slot_index, (en_raw, vh_raw) in enumerate(zip(en_items, vh_items)):
            en_raw = str(en_raw or "").strip()
            vh_raw = str(vh_raw or "").strip()
            if not en_raw or en_raw == vh_raw:
                continue
            en_displays = list(iter_naninovel_display_texts(en_raw))
            vh_displays = list(iter_naninovel_display_texts(vh_raw))
            if len(en_displays) != len(vh_displays):
                continue
            role = _naninovel_command_role(en_raw)
            import_method = (
                "naninovel_choice" if role == "choice"
                else "naninovel_print" if role == "print"
                else "naninovel_script_string"
            )
            for display_index, (source, translation) in enumerate(zip(en_displays, vh_displays)):
                source = source.strip()
                translation = translation.strip()
                if (
                    not source
                    or not translation
                    or not _display_candidate(source, choices, source=True)
                ):
                    continue
                stats["candidate_pairs"] += 1
                if not has_vietnamese_chars(translation):
                    continue
                stats["vietnamese_pairs"] += 1
                actual_role = role if role in {"choice", "print"} else (
                    "choice" if source in choices else "plain"
                )
                context = f"NaninovelScript:{path_id}"
                if actual_role in {"choice", "print"}:
                    context += f":{actual_role}"
                key = (context, source, import_method)
                row = {
                    "source_text_en": source,
                    "translation_vh": translation,
                    "context": context,
                    "file_path": "data.unity3d",
                    "object_info": f"MonoBehaviour:{path_id}:Script",
                    "import_method": import_method,
                    "path_id": str(path_id),
                    "slot_index": slot_index,
                    "display_index": display_index,
                    "display_role": actual_role,
                    "command_text_en": en_raw if en_raw != source and source in en_raw else "",
                }
                previous = rows_by_key.get(key)
                if previous is None:
                    rows_by_key[key] = row
                elif previous["translation_vh"] != translation:
                    rows_by_key.pop(key, None)
                    stats["ambiguous_signatures"] += 1
    rows = sorted(
        rows_by_key.values(),
        key=lambda row: (int(row["path_id"]), int(row["slot_index"]), row["display_index"]),
    )
    result = {
        "version": "2.0.0",
        "inputs": {"en_dump": str(en_dump_path), "vh_dump": str(vh_dump_path)},
        "stats": {**stats, "reference_rows": len(rows)},
        "rows": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["stats"], ensure_ascii=False), flush=True)
    return result


def build(en_path: Path, vh_path: Path, out_path: Path) -> dict:
    import UnityPy
    from vntext.extract import (
        _object_raw_bytes,
        _scan_unity_length_prefixed_strings,
        _naninovel_command_role,
        iter_naninovel_display_texts,
        has_vietnamese_chars,
    )

    started = time.time()
    en_env = UnityPy.load(str(en_path))
    vh_env = UnityPy.load(str(vh_path))
    en_objects = _script_map(en_env)
    vh_objects = _script_map(vh_env)
    rows_by_key: dict[tuple, dict] = {}
    stats = {
        "en_script_objects": len(en_objects),
        "vh_script_objects": len(vh_objects),
        "common_script_objects": 0,
        "aligned_objects": 0,
        "skipped_structure": 0,
        "aligned_slots": 0,
        "candidate_pairs": 0,
        "vietnamese_pairs": 0,
        "ambiguous_signatures": 0,
    }

    for number, (path_id, en_obj) in enumerate(sorted(en_objects.items()), start=1):
        vh_obj = vh_objects.get(path_id)
        if vh_obj is None:
            continue
        stats["common_script_objects"] += 1
        en_items = _scan_unity_length_prefixed_strings(_object_raw_bytes(en_obj), step=4, seeded=False)
        vh_items = _scan_unity_length_prefixed_strings(_object_raw_bytes(vh_obj), step=4, seeded=False)
        if not _same_structure(en_items, vh_items):
            stats["skipped_structure"] += 1
            continue
        stats["aligned_objects"] += 1
        stats["aligned_slots"] += len(en_items)
        choices: set[str] = set()
        for item in en_items:
            raw = str(item.get("text") or "").strip()
            if _naninovel_command_role(raw) == "choice":
                choices.update(part for part in iter_naninovel_display_texts(raw) if part)

        for slot_index, (en_item, vh_item) in enumerate(zip(en_items, vh_items)):
            en_raw = str(en_item.get("text") or "").strip()
            vh_raw = str(vh_item.get("text") or "").strip()
            if not en_raw or en_raw == vh_raw:
                continue
            en_displays = list(iter_naninovel_display_texts(en_raw))
            vh_displays = list(iter_naninovel_display_texts(vh_raw))
            if len(en_displays) != len(vh_displays):
                continue
            role = _naninovel_command_role(en_raw)
            import_method = (
                "naninovel_choice" if role == "choice"
                else "naninovel_print" if role == "print"
                else "naninovel_script_string"
            )
            for display_index, (source, translation) in enumerate(zip(en_displays, vh_displays)):
                source = source.strip()
                translation = translation.strip()
                if not source or not translation:
                    continue
                if not _display_candidate(source, choices, source=True):
                    continue
                stats["candidate_pairs"] += 1
                if not has_vietnamese_chars(translation):
                    continue
                stats["vietnamese_pairs"] += 1
                actual_role = role if role in {"choice", "print"} else (
                    "choice" if source in choices else "plain"
                )
                context = f"NaninovelScript:{path_id}"
                if actual_role in {"choice", "print"}:
                    context += f":{actual_role}"
                key = (context, source, import_method)
                row = {
                    "source_text_en": source,
                    "translation_vh": translation,
                    "context": context,
                    "file_path": "data.unity3d",
                    "object_info": f"MonoBehaviour:{path_id}:Script",
                    "import_method": import_method,
                    "path_id": str(path_id),
                    "slot_index": slot_index,
                    "display_index": display_index,
                    "display_role": actual_role,
                    "command_text_en": en_raw if en_raw != source and source in en_raw else "",
                }
                previous = rows_by_key.get(key)
                if previous is None:
                    rows_by_key[key] = row
                elif previous["translation_vh"] != translation:
                    rows_by_key.pop(key, None)
                    stats["ambiguous_signatures"] += 1
        if number % 10 == 0:
            print(f"objects {number}/{len(en_objects)} aligned={stats['aligned_objects']} rows={len(rows_by_key)}", flush=True)

    rows = sorted(rows_by_key.values(), key=lambda row: (int(row["path_id"]), int(row["slot_index"]), row["display_index"]))
    result = {
        "version": "2.0.0",
        "inputs": {"en": str(en_path), "vh": str(vh_path)},
        "stats": {**stats, "reference_rows": len(rows), "elapsed_seconds": round(time.time() - started, 2)},
        "rows": rows,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["stats"], ensure_ascii=False), flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--en", type=Path)
    parser.add_argument("--vh", type=Path)
    parser.add_argument("--dump", choices=("en", "vh"))
    parser.add_argument("--textasset-dump", choices=("en", "vh"))
    parser.add_argument("--en-dump", type=Path)
    parser.add_argument("--vh-dump", type=Path)
    parser.add_argument("--en-textasset-dump", type=Path)
    parser.add_argument("--vh-textasset-dump", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    _bootstrap(args.root)
    if args.textasset_dump:
        source = args.en if args.textasset_dump == "en" else args.vh
        if source is None:
            parser.error(f"--{args.textasset_dump} is required with --textasset-dump {args.textasset_dump}")
        dump_textasset_lines(source, args.out)
    elif args.en_textasset_dump and args.vh_textasset_dump:
        build_textasset_reference(args.en_textasset_dump, args.vh_textasset_dump, args.out)
    elif args.dump:
        source = args.en if args.dump == "en" else args.vh
        if source is None:
            parser.error(f"--{args.dump} is required with --dump {args.dump}")
        dump_full_slots(source, args.out)
    elif args.en_dump and args.vh_dump:
        build_from_dumps(args.en_dump, args.vh_dump, args.out)
    elif args.en and args.vh:
        build(args.en, args.vh, args.out)
    else:
        parser.error("provide --dump with --en/--vh, or --en-dump and --vh-dump")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
