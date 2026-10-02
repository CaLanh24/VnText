"""Install VNText Studio feather brand icon to WPF, Release and QML targets."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:
    raise SystemExit("pip install pillow") from exc

ROOT = Path(__file__).resolve().parent
SOURCE_PNG = ROOT / "assets" / "VNTextStudio_Feather.png"
SOURCE_ICO_LEGACY = ROOT / "assets" / "vntext_studio_source.ico"
OUT_RELEASE = ROOT / "assets" / "vntext_studio.ico"
OUT_WPF = ROOT.parent / "wpf_app" / "VNText.Studio.App" / "Assets" / "vntext_studio.ico"
OUT_WPF_LOGO_128 = ROOT.parent / "wpf_app" / "VNText.Studio.App" / "Assets" / "vntext_studio_logo_128.png"
OUT_WPF_LOGO_256 = ROOT.parent / "wpf_app" / "VNText.Studio.App" / "Assets" / "vntext_studio_logo_256.png"
OUT_QML_PNG = ROOT.parent / "qml_ui" / "icons" / "logo.png"
ICO_SIZES = (256, 128, 64, 48, 32, 16)
# Padding keeps the feather off the square edges at small taskbar sizes.
ICON_PADDING = 0.04
UI_LOGO_PADDING = 0.02


def _source() -> Path:
    if SOURCE_PNG.is_file():
        return SOURCE_PNG
    if SOURCE_ICO_LEGACY.is_file():
        return SOURCE_ICO_LEGACY
    if OUT_RELEASE.is_file():
        return OUT_RELEASE
    raise SystemExit(
        f"Missing brand icon source. Expected PNG at {SOURCE_PNG} "
        f"or legacy ICO at {SOURCE_ICO_LEGACY}."
    )


def _load_rgba(path: Path) -> Image.Image:
    with Image.open(path) as im:
        return im.convert("RGBA")


def _fit_square(im: Image.Image, size: int, *, padding: float = ICON_PADDING) -> Image.Image:
    """Center the artwork on a transparent square without stretching."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pad_px = max(1, int(round(size * padding)))
    inner = max(1, size - pad_px * 2)
    scale = min(inner / im.width, inner / im.height)
    target_w = max(1, int(round(im.width * scale)))
    target_h = max(1, int(round(im.height * scale)))
    resized = im.resize((target_w, target_h), Image.Resampling.LANCZOS)
    offset = ((size - target_w) // 2, (size - target_h) // 2)
    canvas.paste(resized, offset, resized)
    return canvas


def _master_image() -> Image.Image:
    base = _load_rgba(_source())
    master_size = max(512, base.width, base.height)
    return _fit_square(base, master_size)


def _write_ico(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    master = _master_image()
    icons = [_fit_square(master, size, padding=ICON_PADDING) for size in ICO_SIZES]
    icons[0].save(
        path,
        format="ICO",
        sizes=[(icon.width, icon.height) for icon in icons],
        append_images=icons[1:],
        bitmap_format="bmp",
    )


def _write_png(outputs: dict[str, Path] | None = None) -> None:
    master = _master_image()
    outputs = outputs or {
        "wpf_app/VNText.Studio.App/Assets/vntext_studio_logo_128.png": OUT_WPF_LOGO_128,
        "wpf_app/VNText.Studio.App/Assets/vntext_studio_logo_256.png": OUT_WPF_LOGO_256,
        "qml_ui/icons/logo.png": OUT_QML_PNG,
    }
    for key, size in (("wpf_app/VNText.Studio.App/Assets/vntext_studio_logo_128.png", 128),
                      ("wpf_app/VNText.Studio.App/Assets/vntext_studio_logo_256.png", 256),
                      ("qml_ui/icons/logo.png", 128)):
        outputs[key].parent.mkdir(parents=True, exist_ok=True)
        _fit_square(master, size, padding=UI_LOGO_PADDING).save(outputs[key], format="PNG")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    output_root = args.output_root.expanduser().resolve()
    allowed_roots = [Path(value).expanduser().resolve() for value in (
        os.environ.get("VNTEXT_DEV_RUN_ROOT", ""),
        os.environ.get("VNTEXT_ARTIFACT_SCOPE_ROOT", ""),
    ) if value]
    if not allowed_roots or not any(output_root == root or root in output_root.parents for root in allowed_roots):
        raise SystemExit("--output-root must be under the task DEV_RUN root or registered artifact scope")
    destinations = {
        "release/assets/vntext_studio.ico": OUT_RELEASE,
        "wpf_app/VNText.Studio.App/Assets/vntext_studio.ico": OUT_WPF,
        "wpf_app/VNText.Studio.App/Assets/vntext_studio_logo_128.png": OUT_WPF_LOGO_128,
        "wpf_app/VNText.Studio.App/Assets/vntext_studio_logo_256.png": OUT_WPF_LOGO_256,
        "qml_ui/icons/logo.png": OUT_QML_PNG,
    }
    outputs = {
        key: output_root / Path(key)
        for key, path in destinations.items()
    }
    _write_ico(outputs["release/assets/vntext_studio.ico"])
    _write_ico(outputs["wpf_app/VNText.Studio.App/Assets/vntext_studio.ico"])
    _write_png(outputs)
    print("Source:", _source())
    for path in outputs.values():
        print("Wrote", path)
