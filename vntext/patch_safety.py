"""Safety patch responsibilities."""

from __future__ import annotations

from vntext.patch_constants import (
    Path,
    json,
    shutil,
    struct,
)


def backup_original_file(src: Path, backup_root: Path, rel: str):
    backup = backup_root / rel
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(src, backup)


def make_raw_slot_op(entry: dict, trans: str, force_keep_length: bool = False) -> dict:
    """Build one safe in-place raw patch op.

    This does NOT expand Unity files. Translation must fit the original byte slot.
    For Naninovel/blob candidates we keep the original stored length to avoid
    shifting serialized object layout; the new text is zero padded in the old slot.
    """
    locator = dict(entry.get("locator", {}) or {})
    if force_keep_length:
        locator["keep_original_length"] = True
    return {"source_text": entry.get("source_text", ""), "translation": trans, "locator": locator, "method": entry.get("import_method", "")}


def report_backend_coverage(report: list[str], counters: dict[str, dict[str, int]]) -> None:
    if not counters:
        return
    report.append("")
    report.append("COVERAGE THEO BACKEND:")
    for backend in sorted(counters):
        c = counters[backend]
        total = c.get("patched", 0) + c.get("skipped", 0)
        report.append(f"BACKEND {backend}: patched={c.get('patched',0)} skipped={c.get('skipped',0)} total={total}")


def inc_backend(counters: dict[str, dict[str, int]], backend: str, name: str, amount: int = 1) -> None:
    backend = backend or "unknown"
    counters.setdefault(backend, {"patched": 0, "skipped": 0})[name] += amount


def iter_patch_locators(entry: dict) -> list[dict]:
    """Return primary locator plus duplicate_locations.

    Older builds deduped identical source_text in the same file/import_method, but
    importer only wrote the first locator. That left many menu/UI labels in English.
    v1.33 writes every stored locator, closer to UABEA dump/import behaviour.
    """
    locators: list[dict] = []
    main = entry.get("locator", {}) or {}
    if isinstance(main, dict) and main:
        locators.append(dict(main))
    for dup in entry.get("duplicate_locations", []) or []:
        if isinstance(dup, dict) and dup:
            locators.append(dict(dup))
    # De-dupe identical locators without changing order.
    seen = set()
    out = []
    for loc in locators:
        key = json.dumps(loc, sort_keys=True, ensure_ascii=False, default=str)
        if key in seen:
            continue
        seen.add(key)
        out.append(loc)
    return out or [{}]


def make_entry_with_locator(entry: dict, locator: dict) -> dict:
    clone = dict(entry)
    clone["locator"] = dict(locator or {})
    clone["duplicate_locations"] = []
    return clone


def apply_raw_fixed_ops(target: Path, ops: list[dict], report: list[str], rel: str, label: str = "raw_fixed_slot") -> tuple[int, int]:
    """Patch raw string slots in an already-written Unity file.

    Safe rule: never expand the file. Translation must fit the original byte slot.
    For normal raw_fixed_slot we keep current behaviour. For blob/candidate ops with
    keep_original_length=True, we do not rewrite the stored length prefix; this avoids
    shifting serialized layouts and usually lets Unity/TMP stop at the zero padding.
    """
    if not ops:
        return 0, 0
    try:
        data = bytearray(target.read_bytes())
    except OSError as exc:
        report.append(f"SKIP {rel}: khong doc duoc file patch de {label}: {exc}")
        return 0, len(ops)
    changed = 0
    skipped = 0
    frozen = bytes(data)
    for op in ops:
        source_text = op.get("source_text", "")
        trans = op.get("translation", "")
        locator = op.get("locator", {}) or {}
        encoding = locator.get("encoding", "utf-8")
        try:
            old_raw = source_text.encode(encoding)
            new_raw = trans.encode(encoding)
        except Exception as exc:
            report.append(f"SKIP {rel}: {label} encoding loi: {exc}")
            skipped += 1
            continue
        slot_len = int(locator.get("length") or len(old_raw))
        offset = int(locator.get("offset") or -1)
        length_offset = locator.get("length_offset")
        if len(new_raw) > slot_len:
            report.append(f"SKIP {rel}: {label} ban dich dai hon slot ({len(new_raw)}>{slot_len}) cho: {source_text[:80]}")
            skipped += 1
            continue
        patch_at = -1
        if 0 <= offset <= len(data) - len(old_raw) and data[offset:offset + len(old_raw)] == old_raw:
            patch_at = offset
        else:
            found = frozen.find(old_raw)
            if found >= 0:
                patch_at = found
        if patch_at < 0:
            report.append(f"SKIP {rel}: {label} khong tim thay source trong file patch: {source_text[:80]}")
            skipped += 1
            continue
        keep_original_length = bool(locator.get("keep_original_length"))
        if length_offset is not None and not keep_original_length:
            try:
                lo = int(length_offset)
                if patch_at != offset and patch_at >= 4:
                    candidate_lo = patch_at - 4
                    if struct.unpack_from("<I", data, candidate_lo)[0] == slot_len:
                        lo = candidate_lo
                if 0 <= lo <= len(data) - 4 and struct.unpack_from("<I", data, lo)[0] == slot_len:
                    # Only safe when new length keeps the same 4-byte alignment; otherwise
                    # serialized readers may start the next field at the wrong offset.
                    if (len(new_raw) + 3) // 4 == (slot_len + 3) // 4:
                        data[lo:lo + 4] = struct.pack("<I", len(new_raw))
            except Exception:
                pass
        pad = b"\x00" * (slot_len - len(new_raw))
        data[patch_at:patch_at + slot_len] = new_raw + pad
        changed += 1
    if changed:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes(data))
        report.append(f"RAW {rel}: {label} patched {changed}/{len(ops)}")
    return changed, skipped


def _encoded_variants(text: str) -> list[bytes]:
    variants: list[bytes] = []
    if not text:
        return variants
    for enc in ("utf-8", "utf-8-sig", "utf-16le"):
        try:
            raw = text.encode(enc)
        except Exception:
            continue
        if raw and raw not in variants:
            variants.append(raw)
    return variants


def verify_patched_translations(patched_root: Path, grouped_items: dict[str, list[tuple[dict, str]]], report: list[str]) -> None:
    """Best-effort post-write verification.

    This does not prove the game will choose that asset at runtime, but it proves
    the patched file actually contains the Vietnamese bytes after import. It is
    designed to catch the old failure mode: report said patched, but output file
    did not contain the translation.
    """
    checked = 0
    found = 0
    miss_samples: list[str] = []
    for rel, items in grouped_items.items():
        target = patched_root / rel
        if not target.exists() or not target.is_file():
            continue
        try:
            blob = target.read_bytes()
        except OSError:
            continue
        for entry, trans in items:
            trans = str(trans or "").strip()
            if not trans:
                continue
            method = entry.get("import_method", "")
            if method in {
                "raw_review_only",
                "external_dump_reimport",
                "review_only",
                "raw_fixed_slot",
                "naninovel_blob_string",
                "naninovel_raw_candidate",
                "naninovel_script_string",
            }:
                continue
            if target.suffix.lower() in {".unity3d", ".bundle", ".assets"}:
                continue
            checked += 1
            ok = any(raw in blob for raw in _encoded_variants(trans))
            if ok:
                found += 1
            elif len(miss_samples) < 30:
                miss_samples.append(f"VERIFY_MISS {rel}: {entry.get('source_text','')[:60]} => {trans[:60]}")
    report.append(f"VERIFY translated_bytes_in_patched_files: {found}/{checked}")
    if miss_samples:
        report.append("VERIFY_MISS_SAMPLES:")
        report.extend(miss_samples)


def resolve_game_source_file(game_base: Path, rel: str) -> tuple[Path, str]:
    """Map CSV file_path to a real file under the game root.

    Users sometimes extract from a ``*_Data`` directory, then patch using the
    folder that contains the executable. Accept every Unity data directory so
    this fallback does not depend on one game's name.
    """
    rel_norm = str(rel or "").replace("\\", "/").lstrip("/")
    if not rel_norm:
        return game_base / rel, rel
    direct = game_base / Path(rel_norm)
    if direct.exists():
        return direct, str(Path(rel_norm))
    relative_path = Path(rel_norm)
    try:
        data_dirs = sorted(
            (item for item in game_base.iterdir() if item.is_dir() and item.name.casefold().endswith("_data")),
            key=lambda item: item.name.casefold(),
        )
    except OSError:
        data_dirs = []
    matches = []
    for data_dir in data_dirs:
        nested = data_dir / relative_path
        if nested.is_file():
            matches.append((nested, str(Path(data_dir.name) / relative_path)))
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        # A shortened manifest path is ambiguous when a container has more
        # than one Unity game root.  Never patch an arbitrary *_Data tree.
        return direct, str(Path(rel_norm))
    return direct, str(Path(rel_norm))

__all__ = ['backup_original_file', 'make_raw_slot_op', 'report_backend_coverage', 'inc_backend', 'iter_patch_locators', 'make_entry_with_locator', 'apply_raw_fixed_ops', '_encoded_variants', 'verify_patched_translations', 'resolve_game_source_file']
