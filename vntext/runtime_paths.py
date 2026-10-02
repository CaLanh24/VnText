"""Runtime paths for development and portable installs."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

APP_NAME = "VNTextStudio"
APP_DISPLAY = "VNText Studio"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def repo_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    here = Path(__file__).resolve().parent
    if here.name == "vntext" and here.parent.name == "worker":
        return here.parent
    return here.parent


def app_data_root() -> Path:
    configured = os.environ.get("VNTEXT_DATA_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    if is_frozen():
        return repo_root() / "data"
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_NAME


def ct2_model_dir() -> Path:
    return app_data_root() / "models" / "opus-mt-en-vi-int8"


def cache_dir() -> Path:
    return app_data_root() / "cache"


def updates_dir() -> Path:
    return app_data_root() / "updates"


def logs_dir() -> Path:
    return app_data_root() / "logs"


def default_output_dir() -> Path:
    if os.environ.get("VNTEXT_DATA_ROOT") or is_frozen():
        return app_data_root() / "output"
    docs = Path.home() / "Documents" / "VNText_Output" / "Unity_Translation_Package"
    return docs


def executable_path() -> Path | None:
    if not is_frozen():
        return None
    return Path(sys.executable).resolve()


def ensure_app_data_dirs() -> None:
    for path in (app_data_root(), cache_dir(), updates_dir(), logs_dir()):
        path.mkdir(parents=True, exist_ok=True)


def configure_runtime() -> None:
    ensure_app_data_dirs()
    temp = app_data_root() / "temp"
    temp.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = os.environ["TMPDIR"] = str(temp)
    tempfile.tempdir = str(temp)
    cache = cache_dir()
    os.environ.setdefault("HF_HOME", str(cache / "huggingface"))
    os.environ.setdefault("HF_HUB_CACHE", str(cache / "huggingface" / "hub"))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(cache / "huggingface" / "transformers"))
    os.environ.setdefault("TORCH_HOME", str(cache / "torch"))
    os.environ.setdefault("VNTEXT_DIRECT_GPU_ROOT", str(cache / "gpu"))
