"""Shared patch imports and constants."""

from __future__ import annotations


import json


import hashlib


import re


import shutil


import struct


import time


from pathlib import Path


from vntext.extract import (
    TEXT_EXTS,
    UI_MONO_CLASSES,
    UNITY_EXTS,
    _mono_class_name,
    _object_raw_bytes,
    UI_SHORT_TEXT,
    _replace_text_in_naninovel_command,
    _scan_unity_length_prefixed_strings,
    find_aligned_unity_strings,
    find_aligned_unity_strings_containing,
    _semicolon_csv_read,
    _semicolon_csv_write,
    _typetree_field_is_display_text,
    _unity_string_padding,
    is_ui_text_field,
    iter_naninovel_display_texts,
)


from vntext.package_io import read_translation_rows


from vntext.mt_check import load_whitelist


from vntext.patch_gate import load_review_only_keys, patch_skip_reason


_NANO_SCRIPT_SKIP_TOKENS = frozenset(
    {
        "tip",
        "tips",
    }
)
