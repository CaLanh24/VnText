"""Scan-time and patch-time presentation of the Ren'Py font/image inventory: one outcome per asset, with the reason, for the app to show directly.

Evidence only.  Nothing here edits a game, recognises text in bitmaps or promises coverage beyond the stated scope."""
from __future__ import annotations

from pathlib import Path

MAX_ROWS = 96

# What the user needs to know per font, derived from the inventory status.
#   OK          nothing to do (the font already covers Vietnamese / is the engine default)
#   WILL_REPLACE the font route replaces it for the Vietnamese language when a patch is built (scan time)
#   REPLACED    the built patch routes it (patch time)
#   PRESERVED   deliberately left alone (icon/symbol fonts)
#   UNRESOLVED  cannot be handled safely; the reason says why
_FONT_OUTCOME = {
    "COVERS_TRANSLATION": "OK",
    "ENGINE_DEFAULT": "OK",
    "NEEDS_VIETNAMESE_FONT": "WILL_REPLACE",
    "ICON_PRESERVED": "PRESERVED",
    "AMBIGUOUS_NAME": "UNRESOLVED",
    "UNPARSABLE": "UNRESOLVED",
    "UNSUPPORTED_FORMAT": "UNRESOLVED",
    "UNRESOLVED_BINDING": "UNRESOLVED",
}


def _key(name: str) -> str:
    return name.replace(chr(92), "/").casefold().split("::")[-1]


def font_outcomes(font_assets: list[dict], replacement_keys: list[str] | None = None, *, built: bool = False) -> list[dict]:
    """Per-font rows ``{source, outcome, status, why, uses}``.  With ``built`` the replacement keys of the produced patch decide REPLACED versus
    UNRESOLVED (a font that needs Vietnamese but is not routed is never reported as replaced)."""

    keys = {key for key in (replacement_keys or [])}
    rows = []
    for asset in font_assets[:MAX_ROWS]:
        status = str(asset.get("status") or "")
        outcome = _FONT_OUTCOME.get(status, "UNRESOLVED")
        why = str(asset.get("why") or "")
        if built and status == "NEEDS_VIETNAMESE_FONT":
            source = _key(str(asset.get("source") or ""))
            if source in keys or source.rsplit("/", 1)[-1] in keys:
                outcome = "REPLACED"
            else:
                outcome, why = "UNRESOLVED", "no safe replacement key was generated for this font (ambiguous or unsupported name)"
        rows.append({"source": asset.get("source"), "format": asset.get("format"), "outcome": outcome, "status": status, "why": why,
                     "uses": int(asset.get("static_use_count") or 0)})
    return rows


def outcome_counts(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1
    return dict(sorted(counts.items()))


def scan_renpy_assets(src) -> dict | None:
    """Read-only font and image discovery of a Ren'Py game folder for the Scan step; ``None`` when ``src`` is not a Ren'Py game folder."""

    root = Path(src)
    if not (root / "game").is_dir():
        return None
    from vntext.renpy_font_support import _VIETNAMESE_PROBE

    result: dict = {"schema": 1, "engine": "renpy"}
    try:
        from vntext.renpy_font_inventory import inspect_font_mapping
        inventory = inspect_font_mapping(root, [_VIETNAMESE_PROBE], {}, {})
        rows = font_outcomes(inventory["font_assets"])
        result["fonts"] = {"assets": rows, "total": len(inventory["font_assets"]), "outcomes": outcome_counts(rows), "summary": inventory["font_asset_summary"],
                           "unresolved_notes": inventory["unresolved_count"], "coverage_scope": inventory["coverage_scope"],
                           "checked_against": "Vietnamese letters (probe string); the exact translation is re-checked when the patch is built"}
    except Exception as exc:  # noqa: BLE001 - discovery must never fail the scan
        result["fonts"] = {"error": type(exc).__name__ + ": " + str(exc)[:160]}
    try:
        from vntext.renpy_image_overlay import inventory_image_candidates
        images = inventory_image_candidates(root)
        result["images"] = {"candidates": [{"asset": row["asset"], "states": row["states"], "status": row["status"], "why": row["why"]} for row in images["candidates"][:MAX_ROWS]],
                            "summary": images["summary"], "coverage_scope": images["coverage_scope"]}
    except Exception as exc:  # noqa: BLE001
        result["images"] = {"error": type(exc).__name__ + ": " + str(exc)[:160]}
    return result
