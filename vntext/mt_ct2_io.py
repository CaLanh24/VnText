"""Io responsibilities split from mt_ct2."""

from __future__ import annotations

import time

from vntext.mt_ct2_constants import (
    csv,
    ensure_mt_dir,
    moan_preserve_indices,
    os,
    paths_for_csv,
    postprocess,
    read_csv_rows_file,
    reason_label_vi,
    shutil,
    split_parts,
    split_randpick_variants,
    translation_passes_patch_gate,
)



def _load_csv(csv_path: Path) -> tuple[list[str], list[dict]]:
    return read_csv_rows_file(csv_path)


def _join_pieces(pieces: list[str]) -> str:
    out: list[str] = []
    for piece in pieces:
        if not piece:
            continue
        if out:
            prev = out[-1]
            if (prev[-1].isalnum() or prev[-1] in "}>]") and (
                piece[0].isalnum() or ord(piece[0]) > 127
            ):
                out.append(" ")
        out.append(piece)
    return "".join(out)


def _batch_translate_chunk(
    translator: Ct2Translator,
    rows: list[dict],
    user_glossary: dict[str, str] | None = None,
    translation_memory: dict | None = None,
    *,
    v2_glossary: dict | None = None,
    glossary_conflicts: set[str] | None = None,
) -> dict[str, str]:
    """Translate a chunk: batch all text fragments (incl. tag/placeholder rows) in few CT2 calls."""
    from vntext.package_glossary import (
        lookup_user_phrase,
        mask_user_glossary_terms,
        restore_user_glossary_terms,
    )
    from vntext.mt_memory import lookup_translation_memory
    from vntext.glossary_v2 import mask_terms, resolve_exact, restore_terms

    user_glossary = user_glossary or {}
    # Generic terms are restored after CT2 runs.  Keeping them in the sentence
    # gives the model the context it needs to translate the surrounding prose.
    protect_lexical = False
    work_rows: list[dict] = []
    exact_overrides: dict[str, str] = {}
    user_restores: dict[str, dict[str, str]] = {}
    v2_restores: dict[str, dict[str, str]] = {}
    conflict_keys = glossary_conflicts if glossary_conflicts is not None else set()
    for row in rows:
        src = str(row.get("source_text") or "")
        v2_exact = resolve_exact(src, row, v2_glossary)
        if v2_exact.get("status") == "conflict":
            conflict_keys.add(str(row["key"]))
            work_rows.append({**row, "source_text": ""})
            continue
        if v2_exact.get("status") == "match":
            exact_overrides[str(row["key"])] = str(v2_exact.get("target") or "")
            work_rows.append({**row, "source_text": ""})
            continue
        exact = lookup_user_phrase(src, user_glossary)
        if exact is not None:
            exact_overrides[str(row["key"])] = exact
            work_rows.append({**row, "source_text": ""})
            continue
        memory_hit = lookup_translation_memory(row, translation_memory)
        if memory_hit is not None:
            exact_overrides[str(row["key"])] = memory_hit
            work_rows.append({**row, "source_text": ""})
            continue
        masked_v2, restore_v2, v2_conflicts = mask_terms(src, row, v2_glossary)
        if v2_conflicts:
            conflict_keys.add(str(row["key"]))
            work_rows.append({**row, "source_text": ""})
            continue
        masked, restore = mask_user_glossary_terms(masked_v2, user_glossary)
        work_rows.append({**row, "source_text": masked})
        user_restores[str(row["key"])] = restore
        v2_restores[str(row["key"])] = restore_v2

    row_structs: list[tuple] = []
    frag_cores: list[str] = []
    frag_refs: list[tuple[int, int, int, int, str, str]] = []

    for ri, row in enumerate(work_rows):
        src = row["source_text"]
        variants = split_randpick_variants(src)
        if variants:
            variant_parts: list[list[tuple[str, str]]] = []
            for vi, variant in enumerate(variants):
                _prepared, parts = split_parts(variant, protect_lexical=protect_lexical)
                variant_parts.append(parts)
                for pi, (kind, val) in enumerate(parts):
                    if kind != "text" or not val.strip():
                        continue
                    lead = val[: len(val) - len(val.lstrip())]
                    trail = val[len(val.rstrip()) :]
                    core = val.strip()
                    fi = len(frag_cores)
                    frag_cores.append(core)
                    frag_refs.append((ri, vi, pi, fi, lead, trail))
            row_structs.append(("randpick", variant_parts))
        else:
            _prepared, parts = split_parts(src, protect_lexical=protect_lexical)
            row_structs.append(("single", parts))
            for pi, (kind, val) in enumerate(parts):
                if kind != "text" or not val.strip():
                    continue
                lead = val[: len(val) - len(val.lstrip())]
                trail = val[len(val.rstrip()) :]
                core = val.strip()
                fi = len(frag_cores)
                frag_cores.append(core)
                frag_refs.append((ri, -1, pi, fi, lead, trail))

    translated_cores: list[str] = []
    if frag_cores:
        unique: list[str] = []
        index_map: list[int] = []
        seen: dict[str, int] = {}
        for core in frag_cores:
            if core not in seen:
                seen[core] = len(unique)
                unique.append(core)
            index_map.append(seen[core])
        unique_out = translator.translate_many(unique)
        preserve = moan_preserve_indices(unique)
        for idx in preserve:
            unique_out[idx] = unique[idx]
        translated_cores = [unique_out[i] for i in index_map]
    text_map: dict[tuple[int, int, int], str] = {}
    for ri, vi, pi, fi, lead, trail in frag_refs:
        text_map[(ri, vi, pi)] = lead + translated_cores[fi] + trail

    out: dict[str, str] = {}
    for ri, row in enumerate(work_rows):
        original = rows[ri]
        src = row["source_text"]
        kind, payload = row_structs[ri]
        if str(original["key"]) in conflict_keys:
            out[original["key"]] = ""
            continue
        if str(original["key"]) in exact_overrides:
            out[original["key"]] = exact_overrides[str(original["key"])]
            continue
        if kind == "randpick":
            variant_outs: list[str] = []
            for vi, parts in enumerate(payload):
                pieces: list[str] = []
                for pi, (part_kind, val) in enumerate(parts):
                    if part_kind == "tech":
                        pieces.append(val)
                    else:
                        pieces.append(text_map.get((ri, vi, pi), val))
                variant_outs.append(_join_pieces(pieces))
            translated = postprocess(src, ",".join(variant_outs))
        else:
            parts = payload
            pieces = []
            for pi, (part_kind, val) in enumerate(parts):
                if part_kind == "tech":
                    pieces.append(val)
                else:
                    pieces.append(text_map.get((ri, -1, pi), val))
            translated = postprocess(src, _join_pieces(pieces))
        translated = restore_user_glossary_terms(
            translated, user_restores.get(str(original["key"]), {})
        )
        out[original["key"]] = restore_terms(
            translated, v2_restores.get(str(original["key"]), {})
        )
    return out


def _flush_csv_atomic(csv_path: Path, fields: list[str], rows: list[dict], *, backup: bool = True) -> None:
    paths = paths_for_csv(csv_path)
    ensure_mt_dir(paths)
    if backup and csv_path.is_file():
        shutil.copy2(csv_path, paths.rolling_backup)
    tmp = str(csv_path) + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
        fh.flush()
        os.fsync(fh.fileno())
    # Windows Defender/indexers can briefly hold the destination after the
    # fsync.  Retry only the concrete WinError 5 replace race; other I/O
    # failures remain fatal and the caller still receives a real error.
    for attempt in range(5):
        try:
            os.replace(tmp, csv_path)
            break
        except PermissionError as exc:
            if getattr(exc, "winerror", None) != 5 or attempt == 4:
                raise
            time.sleep(0.2 * (attempt + 1))


def _apply_mapping_memory(
    by_key: dict[str, dict],
    mapping: dict[str, str],
    *,
    allow_overwrite: bool,
    whitelist: set[str],
) -> tuple[int, int, list[tuple[dict, str, list[str]]]]:
    """Update in-memory rows; return (applied, blocked, review_triples)."""
    if not mapping:
        return 0, 0, []
    applied = 0
    blocked = 0
    review: list[tuple[dict, str, list[str]]] = []
    for key, new in mapping.items():
        row = by_key.get(key)
        if row is None:
            blocked += 1
            continue
        if row.get("translation", "").strip() and row["translation"] != new and not allow_overwrite:
            blocked += 1
            continue
        if row.get("translation") == new:
            continue
        gate_ok, gate_reason = translation_passes_patch_gate(row, new, whitelist)
        if not gate_ok:
            label = reason_label_vi(gate_reason) if gate_reason else "Patch Gate"
            review.append((row, new, [f"Patch Gate: {label}"]))
            blocked += 1
            continue
        row["translation"] = new
        applied += 1
    return applied, blocked, review


class _ReviewSink:
    """Batch review_only.csv writes and throttle noisy REVIEW log lines."""

    def __init__(self, emit: Callable[[str], None], *, max_log: int = 3) -> None:
        self._emit = emit
        self._max_log = max(0, max_log)
        self._buffer: list[dict] = []
        self._logged = 0
        self._total = 0

    def add(self, row: dict, attempted: str, reasons: list[str]) -> None:
        self._total += 1
        if self._logged < self._max_log:
            self._emit(f"REVIEW {row['key']}: {'; '.join(reasons[:5])}")
            self._logged += 1
        review_row = dict(row)
        review_row["translation"] = ""
        reason_text = "; ".join(reasons[:5])
        if any("HUMAN_REVIEW_REQUIRED" in reason for reason in reasons):
            review_row["patch_note"] = (
                f"HUMAN_REVIEW_REQUIRED: candidate={attempted[:120]}; "
                "not auto-promoted"
            )
        else:
            review_row["patch_note"] = f"MT blocked: {reason_text}; attempt={attempted[:120]}"
        self._buffer.append(review_row)

    def flush(self, package_dir: Path) -> int:
        from vntext.mt_ct2_status import _append_review_rows
        if not self._buffer:
            return 0
        count = _append_review_rows(package_dir, self._buffer)
        hidden = self._total - self._logged
        if hidden > 0:
            self._emit(f"REVIEW: thêm {hidden} dòng (tổng {self._total} trong lô) → review_only.csv")
        self._buffer.clear()
        self._logged = 0
        self._total = 0
        return count

__all__ = ['_load_csv', '_join_pieces', '_batch_translate_chunk', '_flush_csv_atomic', '_apply_mapping_memory', '_ReviewSink']
