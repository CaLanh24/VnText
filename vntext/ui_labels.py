"""Generic UI-label routing policy.

The public build does not embed a title-specific label translation table.
Short UI strings remain normal translation candidates unless a package-owned
glossary supplies an exact translation through the translation pipeline.
"""

from __future__ import annotations


def is_ui_row(row: dict) -> bool:
    context = str(row.get("context") or "")
    method = str(row.get("import_method") or "")
    return context.startswith("UI:") or method == "unity_ui_text"


def resolve_ui_label_translation(src: str, context: str = "") -> str | None:
    """No bundled label translations are distributed in the generic build."""

    del src, context
    return None


def should_skip_mt_for_ui_label(row: dict) -> bool:
    """Do not silently drop generic UI labels for lack of a bundled table."""

    del row
    return False
