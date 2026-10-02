"""Shared constants and imports for split mt_ct2."""

from __future__ import annotations


import csv


import json


import os


import re


import shutil


import threading


import time


from pathlib import Path


from typing import Callable


from vntext import mt_check


from vntext.mt_apply import apply_batch


from vntext.mt_translation_safety import (
    postprocess,
    split_parts,
    split_randpick_variants,
    validate_candidate,
)


from vntext.patch_gate import RETRANSLATE_STILL_BLOCKED_NOTE, reason_label_vi, translation_passes_patch_gate


from vntext.mt_strategies import (
    candidate_quality_issues,
    moan_preserve_indices,
    retry_row_strategies,
    translate_synonym_row,
)


from vntext.mt_classify import (
    classify_row,
    classify_row_authoritative,
    classify_source_row,
)


from vntext.mt_paths import ensure_mt_dir, paths_for_csv


from vntext.package_io import CSV_FIELDS, read_csv_rows_file, write_csv_rows_file


csv.field_size_limit(10 ** 9)


MODEL_REPO = "dekthedev/opus-mt-en-vi-ct2-int8"

MODEL_REVISION = "c22547827b876e8ee939d6a9363965e5c9f769e1"


MODEL_SUBDIR = "opus-mt-en-vi-int8"


ProgressFn = Callable[[dict], None]


LogFn = Callable[[str], None]


CancelFn = Callable[[], bool]


CT2_MAX_SRC_TOKENS = max(64, min(512, int(os.environ.get("VNTEXT_CT2_MAX_SRC_TOKENS", "480") or "480")))


_SENTENCE_SPLIT_RX = re.compile(r"(?<=[.!?…。！？])\s+|(?<=\n)")


_SOFT_SPLIT_RX = re.compile(r"(?<=[,;:，；：])\s+|(?<=\s)")


_SENTINEL_KEEP_RX = re.compile(r"ZZG\d+ZZG")


_TRANSLATOR: Ct2Translator | None = None
_TRANSLATOR_DIR: Path | None = None


_TRANSLATOR_LOCK = threading.Lock()
