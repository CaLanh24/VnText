"""Resolve explicitly shared development tools for isolated test checkouts."""

from __future__ import annotations

import os
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def dev_env_root() -> Path:
    configured = os.environ.get("VNTEXT_DEV_ENV_ROOT", "").strip()
    return Path(configured).expanduser().resolve() if configured else REPOSITORY_ROOT / ".dev-env"


def worker_python() -> Path:
    configured = os.environ.get("VNTEXT_WORKER_PYTHON", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return dev_env_root() / ".venv" / "Scripts" / "python.exe"


def release_python() -> Path:
    configured = os.environ.get("VNTEXT_RELEASE_PYTHON", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return dev_env_root() / "release-venv" / "Scripts" / "python.exe"


def renpy_native_sdk() -> Path:
    configured = os.environ.get("VNTEXT_RENPY_NATIVE_SDK", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return dev_env_root() / "tools" / "renpy-8.5.3"


def dotnet_executable() -> Path:
    configured = os.environ.get("VNTEXT_DOTNET", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return dev_env_root() / "dotnet-sdk-10" / "dotnet.exe"


def nuget_cache() -> Path:
    return dev_env_root() / "cache" / "nuget"
