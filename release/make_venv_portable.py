# -*- coding: utf-8 -*-
"""Make a Release worker .venv portable: bundle base CPython + rewrite pyvenv.cfg.

Windows venv Scripts/python.exe is a launcher that requires pyvenv.cfg ``home`` to
point at a real base interpreter. Copying only .venv still depends on the build
machine's system Python. This script:

1. Copies a pruned CPython base into ``worker/python``
2. Rewrites ``.venv/pyvenv.cfg`` so ``home`` is that bundled runtime (absolute,
   resolved for the current Release layout; no AppData/Programs/Python, no DEV path)
3. Drops ``executable`` / ``command`` lines that embed build-machine paths
4. Smoke-imports required worker packages
"""
from __future__ import annotations

import re
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

DROP_LIB_DIRS = {
    "site-packages",
    "ensurepip",
    "test",
    "tests",
    "idlelib",
    "turtledemo",
    "lib2to3",
    "ctypes/macholib",
}

# The bundled interpreter is also used directly by release diagnostics and by
# external smoke harnesses.  Environment variables set by the WPF child
# launcher cannot protect those callers, so disable import bytecode at the
# runtime itself.  This is intentionally tiny and has no effect on translation
# or worker semantics.
PORTABLE_SITECUSTOMIZE = "import sys\nsys.dont_write_bytecode = True\n"
EARLY_BYTECODE_GUARD = "sys.dont_write_bytecode = True\n"


def _read_home(pyvenv_cfg: Path) -> Path:
    home = None
    for line in pyvenv_cfg.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("home"):
            _, _, value = line.partition("=")
            home = Path(value.strip().strip('"'))
            break
    if home is None or not home.is_dir():
        raise RuntimeError(f"Cannot resolve base Python home from {pyvenv_cfg}")
    return home


def _copy_base_python(src_home: Path, dest: Path) -> None:
    license_file = src_home / "LICENSE.txt"
    if not license_file.is_file():
        raise FileNotFoundError(f"Base Python license missing: {license_file}")
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(license_file, dest / "LICENSE.txt")

    for name in ("python.exe", "pythonw.exe", "python3.dll", "python312.dll", "python311.dll", "python310.dll"):
        src = src_home / name
        if src.is_file():
            shutil.copy2(src, dest / name)

    for dll in src_home.glob("*.dll"):
        shutil.copy2(dll, dest / dll.name)

    # Tcl/Tk data dirs required by tkinter (vntext_studio imports tkinter at load).
    for folder in ("tcl", "tk"):
        src = src_home / folder
        if src.is_dir():
            shutil.copytree(
                src,
                dest / folder,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
            )

    dlls_src = src_home / "DLLs"
    if dlls_src.is_dir():
        shutil.copytree(dlls_src, dest / "DLLs", dirs_exist_ok=True)

    lib_src = src_home / "Lib"
    lib_dest = dest / "Lib"
    if not lib_src.is_dir():
        raise RuntimeError(f"Base Python Lib missing: {lib_src}")

    def _ignore(directory: str, names: list[str]) -> set[str]:
        rel = Path(directory).relative_to(lib_src).as_posix() if Path(directory) != lib_src else ""
        drop: set[str] = set()
        for name in names:
            key = name if not rel else f"{rel}/{name}"
            if name in DROP_LIB_DIRS or key in DROP_LIB_DIRS:
                drop.add(name)
            if name == "site-packages":
                drop.add(name)
        return drop

    def _ignore_bytecode(directory: str, names: list[str]) -> set[str]:
        ignored = _ignore(directory, names)
        ignored.update(
            name
            for name in names
            if name == "__pycache__" or Path(name).suffix.lower() in {".pyc", ".pyo"}
        )
        return ignored

    shutil.copytree(lib_src, lib_dest, ignore=_ignore_bytecode, dirs_exist_ok=True)
    (lib_dest / "site-packages").mkdir(parents=True, exist_ok=True)
    (lib_dest / "sitecustomize.py").write_text(PORTABLE_SITECUSTOMIZE, encoding="utf-8")

    # CPython imports encodings before sitecustomize.  Inject the guard after
    # the first ``import sys`` in those bootstrap modules so their own imports
    # cannot recreate caches before the runtime hook is reached.
    for relative in (Path("encodings") / "__init__.py", Path("site.py")):
        path = lib_dest / relative
        text = path.read_text(encoding="utf-8")
        if EARLY_BYTECODE_GUARD in text:
            continue
        marker = "import sys\n"
        if marker not in text:
            raise RuntimeError(f"Cannot install early bytecode guard in {path}")
        text = text.replace(marker, marker + EARLY_BYTECODE_GUARD, 1)
        path.write_text(text, encoding="utf-8")

    # CPython imports ``encodings`` before it can execute sitecustomize.  Keep
    # the guarded bootstrap modules in the standard-library zip path, which
    # importlib loads without writing source bytecode.  The Lib copies remain
    # as a readable fallback for installations that do not use the zip path.
    dll_names = sorted(
        p.stem for p in src_home.glob("python*.dll") if re.fullmatch(r"python\d{3}", p.stem)
    )
    zip_name = f"{dll_names[-1] if dll_names else 'python312'}.zip"
    with zipfile.ZipFile(dest / zip_name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in (Path("encodings"), Path("site.py")):
            source = lib_dest / relative
            if source.is_dir():
                for child in source.rglob("*.py"):
                    archive.write(child, (relative / child.relative_to(source)).as_posix())
            else:
                archive.write(source, relative.as_posix())

    if not (dest / "python.exe").is_file():
        raise RuntimeError(f"Bundled python.exe missing under {dest}")


def _write_pyvenv_cfg(venv_root: Path, bundled_home: Path, version: str) -> None:
    # Absolute path required by Windows venv launcher; must point inside Release.
    home = str(bundled_home.resolve())
    text = (
        f"home = {home}\n"
        "include-system-site-packages = false\n"
        f"version = {version}\n"
    )
    (venv_root / "pyvenv.cfg").write_text(text, encoding="utf-8")


def _parse_version(pyvenv_cfg: Path) -> str:
    for line in pyvenv_cfg.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("version"):
            return line.split("=", 1)[1].strip() or "3.12.10"
    return "3.12.10"


def assert_portable_cfg(venv_root: Path, worker_root: Path) -> None:
    cfg = venv_root / "pyvenv.cfg"
    text = cfg.read_text(encoding="utf-8", errors="replace")
    forbidden = (
        r"AppData\\Local\\Programs\\Python",
        r"Programs\\Python",
        r"VNText_Studio_Core",
        r"portable_zip_update",
    )
    for pat in forbidden:
        if re.search(pat, text, flags=re.IGNORECASE):
            raise RuntimeError(f"pyvenv.cfg still references build/system path ({pat}):\n{text}")
    if "executable =" in text or "command =" in text:
        raise RuntimeError("pyvenv.cfg must not retain executable/command build lines")
    home_line = next((ln for ln in text.splitlines() if ln.startswith("home")), "")
    if "=" not in home_line:
        raise RuntimeError("pyvenv.cfg missing home=")
    home = Path(home_line.split("=", 1)[1].strip()).resolve()
    expected = (worker_root / "python").resolve()
    if home != expected:
        raise RuntimeError(f"pyvenv home must be worker/python ({expected}), got {home}")


def smoke(venv_root: Path, bundled_home: Path) -> None:
    py = venv_root / "Scripts" / "python.exe"
    code = (
        "import sys, pathlib\n"
        f"home = pathlib.Path(r'''{bundled_home}''').resolve()\n"
        "assert pathlib.Path(sys.base_prefix).resolve() == home, (sys.base_prefix, home)\n"
        "bp = sys.base_prefix.replace('\\\\','/')\n"
        "assert 'Programs/Python' not in bp and '/AppData/Local/Programs/Python' not in bp\n"
        "import UnityPy, ctranslate2\n"
        "assert sys.dont_write_bytecode is True\n"
        "print('portable_smoke_ok', sys.base_prefix)\n"
    )
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([str(py), "-c", code], capture_output=True, text=True, timeout=120, env=env)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "portable smoke failed")
    print(proc.stdout.strip())


def make_portable(venv_root: Path, worker_root: Path | None = None) -> dict:
    venv_root = venv_root.resolve()
    worker_root = (worker_root or venv_root.parent).resolve()
    cfg = venv_root / "pyvenv.cfg"
    if not cfg.is_file():
        raise FileNotFoundError(cfg)
    src_home = _read_home(cfg)
    version = _parse_version(cfg)
    bundled = worker_root / "python"
    print(f"Bundling base Python from {src_home} -> {bundled}")
    _copy_base_python(src_home, bundled)
    _write_pyvenv_cfg(venv_root, bundled, version)
    assert_portable_cfg(venv_root, worker_root)
    smoke(venv_root, bundled)
    size_mb = round(sum(p.stat().st_size for p in bundled.rglob("*") if p.is_file()) / (1024 * 1024), 1)
    return {"bundled_home": str(bundled), "version": version, "size_mb": size_mb}


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print(
            "usage: make_venv_portable.py <path-to-worker/.venv> [worker-root] [--rewrite-only]",
            file=sys.stderr,
        )
        return 2
    rewrite_only = "--rewrite-only" in argv
    args = [a for a in argv if a != "--rewrite-only"]
    venv = Path(args[0])
    worker = Path(args[1]) if len(args) > 1 else venv.parent
    if rewrite_only:
        venv = venv.resolve()
        worker = worker.resolve()
        bundled = worker / "python"
        if not (bundled / "python.exe").is_file():
            raise SystemExit(f"bundled python missing for rewrite-only: {bundled}")
        version = _parse_version(venv / "pyvenv.cfg") if (venv / "pyvenv.cfg").is_file() else "3.12.10"
        _write_pyvenv_cfg(venv, bundled, version)
        assert_portable_cfg(venv, worker)
        smoke(venv, bundled)
        print(f"rewrite-only ok: home={bundled}")
        return 0
    report = make_portable(venv, worker)
    print(f"portable ok: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
