"""Prune RELEASE worker .venv to packages used by the shipped CT2 worker."""
from __future__ import annotations

import os
import shutil
import sys
import re
import tempfile
from pathlib import Path

# Transformers stays because CT2 uses MarianTokenizer; PyTorch is not shipped.
DROP_PACKAGES = {
    "PySide6",
    "PySide6_Addons",
    "PySide6_Essentials",
    "PySide6_Pdf",
    "PySide6_WebEngine",
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
DROP_COPY_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".git", "test", "tests"}


def _copy_ignore(relative: Path, is_dir: bool, *, site_packages_root: bool = False) -> bool:
    parts = relative.parts
    name = relative.name
    if any(part.lower() in DROP_COPY_DIRS for part in parts) or relative.suffix.lower() in {".pyc", ".pyo", ".log"}:
        return True
    package_offset = 0 if site_packages_root else 2 if parts[:2] == ("Lib", "site-packages") else None
    if package_offset is not None and len(parts) > package_offset:
        package = parts[package_offset]
        if package in DROP_PACKAGES:
            return True
        if package.endswith(".dist-info"):
            stem = package.split("-")[0].lower()
            if stem in {item.lower() for item in DROP_PACKAGES}:
                return True
        if parts[package_offset:package_offset + 2] == ("fmod_toolkit", "libfmod"):
            return True
    if len(parts) >= 2 and parts[0] == "Scripts" and any(
        name.lower().startswith(glob.rstrip("*").lower()) for glob in DROP_SCRIPT_GLOBS
    ):
        return True
    return False


def _copy_pruned_tree(source: Path, destination: Path, *, require_worker_python: bool,
                      site_packages_root: bool = False) -> dict:
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_dir():
        raise FileNotFoundError(source)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"filtered venv destination already exists: {destination}")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("filtered venv source and destination must not overlap")
    copied_bytes = 0
    copied_files = 0
    try:
        for item in source.rglob("*"):
            relative = item.relative_to(source)
            if _copy_ignore(relative, item.is_dir(), site_packages_root=site_packages_root):
                continue
            if item.is_symlink():
                raise RuntimeError(f"worker venv source contains a link: {item}")
            target = destination / relative
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            elif item.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
                copied_bytes += item.stat().st_size
                copied_files += 1
            else:
                raise RuntimeError(f"worker venv source contains a special file: {item}")
        if require_worker_python and not (destination / "Scripts" / "python.exe").is_file():
            raise FileNotFoundError(f"filtered worker venv is missing Scripts/python.exe: {destination}")
    except BaseException:
        if destination.exists() and not destination.is_symlink():
            shutil.rmtree(destination)
        raise
    return {"source": str(source), "destination": str(destination), "bytes": copied_bytes, "files": copied_files}


def copy_pruned_source(source: Path, destination: Path) -> dict:
    """Copy only worker-retained venv files so a raw venv is never staged first."""
    if source.is_symlink():
        raise RuntimeError(f"worker venv source contains a link: {source}")
    return _copy_pruned_tree(source, destination, require_worker_python=True)


def merge_pruned_site(source: Path, destination: Path) -> dict:
    """Merge filtered system-site roots, preserving every existing staged root."""
    if source.is_symlink() or destination.is_symlink():
        raise RuntimeError("system site-packages source and destination must not be links")
    source = source.resolve()
    destination = destination.resolve()
    if not source.is_dir() or not destination.is_dir():
        raise FileNotFoundError("system site-packages source and destination must exist")
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("system site-packages source and destination must not overlap")
    staging_root = Path(tempfile.mkdtemp(prefix=".filtered-system-site-", dir=destination.parent))
    staged = staging_root / "site"
    moved: list[Path] = []
    try:
        _copy_pruned_tree(source, staged, require_worker_python=False, site_packages_root=True)
        for item in staged.iterdir():
            target = destination / item.name
            if target.exists() or target.is_symlink():
                continue
            os.replace(item, target)
            moved.append(target)
        return {"source": str(source), "destination": str(destination),
                "roots_added": [item.name for item in moved]}
    except BaseException:
        for item in reversed(moved):
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            else:
                item.unlink(missing_ok=True)
        raise
    finally:
        if staging_root.exists() and not staging_root.is_symlink():
            shutil.rmtree(staging_root)


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
    if argv[0] == "--copy-pruned-source":
        if len(argv) != 3:
            print("usage: prune_worker_venv.py --copy-pruned-source <source-venv> <destination-venv>", file=sys.stderr)
            return 2
        report = copy_pruned_source(Path(argv[1]), Path(argv[2]))
        print(f"filtered venv copy: {report['files']} files, {report['bytes']} bytes")
        return 0
    if argv[0] == "--merge-pruned-site":
        if len(argv) != 3:
            print("usage: prune_worker_venv.py --merge-pruned-site <system-site-packages> <release-site-packages>", file=sys.stderr)
            return 2
        report = merge_pruned_site(Path(argv[1]), Path(argv[2]))
        print(f"filtered system site merge: {len(report['roots_added'])} roots added")
        return 0
    root = Path(argv[0]).resolve()
    report = prune_venv(root)
    print(f"venv {report['before_mb']} MB -> {report['after_mb']} MB; removed {len(report['removed'])} packages")
    smoke_imports(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
