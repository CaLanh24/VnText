"""Static font evidence. Glyph presence never proves runtime font mapping."""
from __future__ import annotations
import hashlib
import re
import unicodedata
from pathlib import Path
from vntext.font_coverage import cmap_glyphs

MAX_FONT_BYTES = 16 * 1024 * 1024


def required_characters(translations):
    text = "\n".join(str(value) for value in translations)
    text = re.sub(r"\{[^{}]*\}|\[[^\[\]]*\]", "", text)
    return sorted({ord(c) for form in (text, unicodedata.normalize("NFC", text), unicodedata.normalize("NFD", text))
                   for c in form if not c.isspace() and unicodedata.category(c)[0] != "C"})


def inspect_font(path: Path, characters):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FONT_BYTES:
        raise ValueError("Font must be a regular bounded TTF/OTF file")
    data = path.read_bytes()
    result = cmap_glyphs(data, characters)
    return {"sha256": hashlib.sha256(data).hexdigest(), "missing": result["missing"],
            "characters_checked": len(characters), "format": result["format"]}


def font_report(engine, translations, *, font=None, styles=()):
    characters = required_characters(translations)
    report = {"engine": engine, "glyph_status": "UNKNOWN", "mapping_status": "UNKNOWN",
              "runtime_status": "NOT_PROVEN", "compatible": False,
              "reason": "Runtime font mapping has not been verified; no compatibility claim.",
              "characters_checked": len(characters), "styles": list(styles)}
    if engine != "renpy":
        report["reason"] = "Unity/TMP atlas, material and fallback mapping require a verified adapter; no blind font replacement."
    elif font is not None:
        report.update(inspect_font(Path(font), characters))
        report["glyph_status"] = "MISSING" if report["missing"] else "PASS"
        report["mapping_status"] = "STATIC_STYLES_ONLY" if styles else "UNKNOWN"
        report["reason"] = "Static language-specific styles only; dynamic, inline, bold/italic and icon mappings are not claimed."
    return report
