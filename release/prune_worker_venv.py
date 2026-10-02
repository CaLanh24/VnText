"""Prune RELEASE worker .venv to packages used by the shipped CT2 worker."""
from __future__ import annotations

import shutil
import sys
import re
from pathlib import Path

# Transformers stays because CT2 uses MarianTokenizer; PyTorch is not shipped.
DROP_PACKAGES = {
    "PySide6",
    "PySide6_Addons",
    "PySide6_Essentials",
    "pyinstaller_hooks_contrib",
    "setuptools",
    "shiboken6",
    "torchaudio",
    "torchvision",
    "torch",
    "torchgen",
    "functorch",
    "stanza",
    "spacy",
    "thinc",
    "blis",
    "cymem",
    "murmurhash",
    "preshed",
    "srsly",
    "catalogue",
    "weasel",
    "spacy_legacy",
    "spacy_loggers",
    "confection",
    "langcodes",
    "language_data",
    "marisa_trie",
    "onnxruntime",
    "onnx",
    "argostranslate",
    "argospm",
    "minisbd",
    "pytest",
    "pyinstaller",
    "_pyinstaller_hooks_contrib",
    "pip",
    "pygments",
    "black",
    "mypy",
    "ruff",
}

DROP_SCRIPT_GLOBS = ("pip*", "pytest*", "pyinstaller*", "torch*", "activate*")


def assert_no_fmod_binaries(root: Path) -> None:
    """Reject vendor FMOD binaries, including unexpected staged locations."""
    for path in root.rglob("*"):
        if path.is_file() and re.fullmatch(
            r"(?:lib)?fmod.*\.(?:dll|dylib|so)(?:\.\d+)*", path.name, re.IGNORECASE
        ):
            raise RuntimeError(f"Staged worker contains vendor FMOD binary: {path}")


def _mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / (1024 * 1024), 1)


def prune_venv(venv_root: Path) -> dict:
    site = venv_root / "Lib" / "site-packages"
    scripts = venv_root / "Scripts"
    if not site.is_dir():
        raise FileNotFoundError(f"site-packages missing: {site}")

    before = _mb(venv_root)
    removed: list[str] = []

    for name in sorted(DROP_PACKAGES):
        target = site / name
        if target.exists():
            shutil.rmtree(target)
            removed.append(name)

    # Drop .dist-info / .libs for removed packages
    for meta in site.glob("*"):
        if not meta.is_dir():
            continue
        stem = meta.name.split("-")[0].lower()
        if stem in {p.lower() for p in DROP_PACKAGES} and meta.name.endswith(".dist-info"):
            shutil.rmtree(meta)

    # Unity text extraction does not use audio export. Keep the MIT helper and
    # its metadata, but do not redistribute its separately licensed vendor SDK.
    fmod_vendor = site / "fmod_toolkit" / "libfmod"
    if fmod_vendor.exists():
        shutil.rmtree(fmod_vendor)
        removed.append("fmod_toolkit/libfmod")

    if scripts.is_dir():
        for item in scripts.iterdir():
            if any(item.name.lower().startswith(glob.rstrip("*")) for glob in DROP_SCRIPT_GLOBS):
                if item.is_file():
                    item.unlink(missing_ok=True)

    assert_no_fmod_binaries(venv_root)
    after = _mb(venv_root)
    return {"before_mb": before, "after_mb": after, "removed": removed}


def smoke_imports(venv_root: Path) -> None:
    py = venv_root / "Scripts" / "python.exe"
    if not py.is_file():
        raise FileNotFoundError(py)
    code = (
        "import UnityPy, ctranslate2\n"
        "from transformers import MarianTokenizer\n"
        "print('prune_smoke_ok')"
    )
    import subprocess

    proc = subprocess.run([str(py), "-c", code], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "import smoke failed")


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("usage: prune_worker_venv.py <path-to-.venv>", file=sys.stderr)
        return 2
    root = Path(argv[0]).resolve()
    report = prune_venv(root)
    print(f"venv {report['before_mb']} MB -> {report['after_mb']} MB; removed {len(report['removed'])} packages")
    smoke_imports(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
