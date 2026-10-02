"""Collect only QtQml + QtQuick QML imports (not the full PySide6/qml tree)."""
from __future__ import annotations

from pathlib import Path

import PySide6
from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)

_qml_root = Path(PySide6.__file__).resolve().parent / "qml"
_dest_root = Path("PySide6") / "qml"

_MODULES = ("QtQml", "QtQuick")
_SUBMODULES = (
    ("QtQml", "Models"),
    ("QtQml", "WorkerScript"),
)


def _dest_dir(src: Path) -> str:
    rel = src.relative_to(_qml_root)
    if src.is_dir():
        parent = rel
    else:
        parent = rel.parent
    return str(_dest_root / parent)


def _add_tree(src_dir: Path) -> None:
    if not src_dir.is_dir():
        return
    for path in src_dir.rglob("*"):
        if path.is_file():
            datas.append((str(path), _dest_dir(path)))


def _add_plugin(qmldir: Path) -> None:
    if not qmldir.is_file():
        return
    plug_bins, plug_datas = pyside6_library_info._process_qml_plugin(qmldir)
    binaries.extend((str(src), _dest_dir(src)) for src in plug_bins)
    datas.extend((str(src), _dest_dir(src)) for src in plug_datas)


for module in _MODULES:
    _add_tree(_qml_root / module)
    _add_plugin(_qml_root / module / "qmldir")

for parent, child in _SUBMODULES:
    sub = _qml_root / parent / child
    _add_tree(sub)
    _add_plugin(sub / "qmldir")
