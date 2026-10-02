"""Shared VNText Studio brand icon (feather .ico / logo.png)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PKG = Path(__file__).resolve().parent


def _project_roots() -> list[Path]:
    roots: list[Path] = []
    here = _PKG
    if here.name == "vntext":
        roots.append(here.parent)
        if here.parent.name == "worker":
            roots.append(here.parent.parent)
    return roots


@lru_cache(maxsize=1)
def logo_ico_path() -> Path | None:
    for root in _project_roots():
        for rel in (
            "release/assets/vntext_studio.ico",
            "wpf_app/VNText.Studio.App/Assets/vntext_studio.ico",
        ):
            p = (root / rel).resolve()
            if p.is_file():
                return p
    return None


@lru_cache(maxsize=1)
def logo_source_png_path() -> Path | None:
    for root in _project_roots():
        for rel in (
            "release/assets/VNTextStudio_Feather.png",
            "qml_ui/icons/logo.png",
        ):
            p = (root / rel).resolve()
            if p.is_file():
                return p
    return None


@lru_cache(maxsize=1)
def logo_png_path() -> Path | None:
    return logo_source_png_path()
