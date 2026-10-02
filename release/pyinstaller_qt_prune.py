"""Prune unused Qt/QML payloads from PyInstaller Analysis (VNText Studio)."""
from __future__ import annotations

from pathlib import Path

# Top-level QML import dirs not used by ClientRoot (QtQuick + QtQml only).
QML_DROP_TOP = {
    "Qt",
    "Qt3D",
    "Qt5Compat",
    "QtCharts",
    "QtCore",
    "QtDataVisualization",
    "QtGraphs",
    "QtLocation",
    "QtMultimedia",
    "QtNetwork",
    "QtPositioning",
    "QtQuick3D",
    "QtRemoteObjects",
    "QtScxml",
    "QtSensors",
    "QtTest",
    "QtTextToSpeech",
    "QtWebChannel",
    "QtWebEngine",
    "QtWebSockets",
    "QtWebView",
}

# Qt plugin folders not required for QWidget + QtQuick software shell.
PLUGIN_DROP = {
    "assetimporters",
    "canbus",
    "designer",
    "geometryloaders",
    "geoservices",
    "multimedia",
    "position",
    "qmllint",
    "qmltooling",
    "sceneparsers",
    "scxmldatamodel",
    "sensors",
    "sqldrivers",
    "texttospeech",
    "webview",
    "vectorimageformats",
}

# Qt6 DLL name fragments to drop (WebEngine, 3D, charts, …).
DLL_DROP_FRAGMENTS = (
    "Qt6WebEngine",
    "Qt6WebEngineCore",
    "Qt6WebEngineQuick",
    "Qt6WebEngineWidgets",
    "Qt6WebView",
    "Qt6Quick3D",
    "Qt6Quick3DRuntimeRender",
    "Qt6Quick3DUtils",
    "Qt6Quick3DHelpers",
    "Qt6Quick3DAssetImport",
    "Qt6Quick3DAssetUtils",
    "Qt6Quick3DEffects",
    "Qt6Quick3DParticles",
    "Qt6Quick3DPhysics",
    "Qt6Quick3DXr",
    "Qt6Charts",
    "Qt6Graphs",
    "Qt6DataVisualization",
    "Qt6Location",
    "Qt6Positioning",
    "Qt6PositioningQuick",
    "Qt6Multimedia",
    "Qt6MultimediaQuick",
    "Qt6SpatialAudio",
    "Qt63D",
    "Qt6Scxml",
    "Qt6StateMachine",
    "Qt6Sensors",
    "Qt6SensorsQuick",
    "Qt6TextToSpeech",
    "Qt6Bluetooth",
    "Qt6Pdf",
    "Qt6PdfQuick",
    "Qt6PdfWidgets",
    "Qt6RemoteObjects",
    "Qt6RemoteObjectsQml",
    "Qt6HttpServer",
    "Qt6SerialBus",
    "Qt6SerialPort",
    "Qt6Nfc",
    "Qt6VirtualKeyboard",
    "Qt6UiTools",
    "Qt6Designer",
    "Qt6DesignerComponents",
    "Qt6Help",
    "Qt6AxContainer",
    "Qt6AxServer",
    "Qt6AxBase",
    "Qt6DBus",
    "Qt6Sql",
    "Qt6Test",
    "Qt6SvgWidgets",
)

# QML subpaths inside QtQuick we do not import.
QML_QUICK_DROP = (
    "/QtQuick/Controls/",
    "/QtQuick/Dialogs/",
    "/QtQuick/Templates/",
    "/QtQuick/VirtualKeyboard/",
    "/QtQuick/Scene3D/",
    "/QtQuick/Scene2D/",
    "/QtQuick/Shapes/",
    "/QtQuick/Effects/",
    "/QtQuick/Particles/",
    "/QtQuick/NativeStyle/",
    "/QtQuick/LocalStorage/",
    "/QtQuick/XmlListModel/",
)


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def _qml_drop(path: str) -> bool:
    p = _norm(path)
    marker = "/qml/"
    if marker not in p:
        return False
    rel = p.split(marker, 1)[1]
    top = rel.split("/", 1)[0]
    if top in QML_DROP_TOP:
        return True
    if top == "QtQuick":
        return any(seg in p for seg in QML_QUICK_DROP)
    return False


def _plugin_drop(path: str) -> bool:
    p = _norm(path)
    marker = "/plugins/"
    if marker not in p:
        return False
    rel = p.split(marker, 1)[1]
    folder = rel.split("/", 1)[0]
    return folder in PLUGIN_DROP


def _dll_drop(path: str) -> bool:
    name = Path(_norm(path)).name
    return any(frag in name for frag in DLL_DROP_FRAGMENTS)


def should_drop_bundle_path(path: str) -> bool:
    p = _norm(path)
    if _qml_drop(p) or _plugin_drop(p) or _dll_drop(p):
        return True
    if "WebEngineProcess" in p:
        return True
    return False


def prune_analysis(analysis) -> tuple[int, int]:
    """Remove unused Qt/QML binaries and datas. Returns (bin_dropped, data_dropped)."""
    bin_before = len(analysis.binaries)
    data_before = len(analysis.datas)

    analysis.binaries = [
        item for item in analysis.binaries if not should_drop_bundle_path(item[0])
    ]
    analysis.datas = [
        item for item in analysis.datas if not should_drop_bundle_path(item[0])
    ]

    return bin_before - len(analysis.binaries), data_before - len(analysis.datas)


PRUNED_SUMMARY = {
    "qml_modules_removed": sorted(QML_DROP_TOP),
    "qml_quick_subpaths_removed": list(QML_QUICK_DROP),
    "qt_plugins_removed": sorted(PLUGIN_DROP),
    "qt_dll_families_removed": list(DLL_DROP_FRAGMENTS),
}
