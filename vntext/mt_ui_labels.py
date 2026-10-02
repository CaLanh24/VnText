"""Backward-compatible import surface for the generic UI-label policy.

The old module name is retained only as a compatibility facade.  It contains
no bundled labels or game-specific overrides.
"""

from vntext.ui_labels import is_ui_row, resolve_ui_label_translation, should_skip_mt_for_ui_label

__all__ = ["is_ui_row", "resolve_ui_label_translation", "should_skip_mt_for_ui_label"]
