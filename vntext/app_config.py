"""Optional legacy Python updater defaults; remote URLs require explicit configuration."""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path


def _candidate_default_files() -> list[Path]:
    paths: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        paths.append(meipass / "vntext" / "app_release_defaults.json")
    module_dir = Path(__file__).resolve().parent
    paths.append(module_dir / "_release_defaults.json")
    paths.append(module_dir.parent / "release" / "app_release_defaults.json")
    return paths


@lru_cache(maxsize=1)
def release_defaults() -> dict:
    for path in _candidate_default_files():
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            continue
    return {"manifest_url": ""}


def default_update_manifest_url() -> str:
    return str(release_defaults().get("manifest_url") or "").strip()
