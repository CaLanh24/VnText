"""Launch one isolated unittest pattern with the Release runner environment."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def _site_package_roots(python_path: Path, working_directory: Path) -> list[Path]:
    # The interpreter passed to this runner owns the dependency set for this
    # gate. Put its packages first so a stale project .venv cannot shadow the
    # selected release runtime with incompatible native extensions.
    candidates: list[Path] = []
    venv_root = python_path.parent.parent if python_path.parent.name.lower() in {"scripts", "bin"} else None
    if venv_root is not None:
        candidates.extend(
            [
                venv_root / "Lib" / "site-packages",
                venv_root / "lib" / "site-packages",
                *sorted((venv_root / "lib").glob("python*/site-packages")),
            ]
        )
    candidates.append(working_directory / ".dev-env" / ".venv" / "Lib" / "site-packages")
    result: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.is_dir():
            resolved = candidate.resolve()
            key = os.path.normcase(str(resolved))
            if key not in seen:
                result.append(resolved)
                seen.add(key)
    return result


def _environment(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    python_path = Path(args.python_path).expanduser().resolve()
    work = Path(args.working_directory).expanduser().resolve()
    temp_root = Path(args.temp_root).expanduser().resolve()
    python_path_entries = [str(work), *[str(path) for path in _site_package_roots(python_path, work)]]
    existing_pythonpath = [item for item in env.get("PYTHONPATH", "").split(os.pathsep) if item]
    env["PYTHONPATH"] = os.pathsep.join(python_path_entries + existing_pythonpath)
    # Windows tempfile prefers TEMP/TMP over TMPDIR. Keep all three aligned
    # so tests and subprocesses resolve temporary paths inside the registered
    # TEST_RUN root rather than falling back to the user's profile temp path.
    env["TEMP"] = str(temp_root)
    env["TMP"] = str(temp_root)
    env["TMPDIR"] = str(temp_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["VNTEXT_ARTIFACT_SCOPE_ID"] = args.scope_id
    env["VNTEXT_ARTIFACT_RUN_ID"] = args.run_id
    env["VNTEXT_ARTIFACT_SCOPE_ROOT"] = str(Path(args.scope_root).expanduser().resolve())
    env["VNTEXT_WORKER_PYTHON"] = str(python_path)
    env.pop("VNTEXT_RELEASE_TASK_ID", None)
    if args.release_task_id:
        env["VNTEXT_RELEASE_TASK_ID"] = args.release_task_id
    return env


def _probe_code() -> str:
    return """import importlib.util, json, os, sys, tempfile
expected_temp = os.path.normcase(os.path.abspath(os.environ['TMPDIR']))
actual_temp = os.path.normcase(os.path.abspath(tempfile.gettempdir()))
modules = {name: bool(importlib.util.find_spec(name)) for name in ('transformers', 'ctranslate2', 'sentencepiece')}
report = {
    'python': sys.executable,
    'scope_id': os.environ.get('VNTEXT_ARTIFACT_SCOPE_ID'),
    'run_id': os.environ.get('VNTEXT_ARTIFACT_RUN_ID'),
    'scope_root': os.environ.get('VNTEXT_ARTIFACT_SCOPE_ROOT'),
    'tmpdir': os.environ.get('TMPDIR'),
    'tempfile_tempdir': tempfile.gettempdir(),
    'modules': modules,
}
print('REGRESSION_ENV_PROBE ' + json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
if actual_temp != expected_temp or not report['scope_id'] or not report['run_id']:
    raise SystemExit('Release regression child environment did not reach Python')
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-path", required=True)
    parser.add_argument("--working-directory", required=True)
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--scope-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scope-root", required=True)
    parser.add_argument("--temp-root", required=True)
    parser.add_argument("--release-task-id", default="")
    args = parser.parse_args()

    python_path = Path(args.python_path).expanduser().resolve()
    working_directory = Path(args.working_directory).expanduser().resolve()
    temp_root = Path(args.temp_root).expanduser().resolve()
    scope_root = Path(args.scope_root).expanduser().resolve()
    if not python_path.is_file():
        print(f"Regression Python is missing: {python_path}", file=sys.stderr, flush=True)
        return 2
    if not temp_root.is_dir() or temp_root.parent != scope_root:
        print(f"Regression temp root must be an existing direct child of TEST_RUN: {temp_root}", file=sys.stderr, flush=True)
        return 2

    env = _environment(args)
    probe = subprocess.run(
        [str(python_path), "-S", "-B", "-c", _probe_code()],
        cwd=str(working_directory),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.stdout:
        print(probe.stdout, end="", flush=True)
    if probe.stderr:
        print(probe.stderr, end="", file=sys.stderr, flush=True)
    if probe.returncode != 0:
        return probe.returncode

    command = [
        str(python_path),
        "-S",
        "-B",
        "-c",
        # Explicit local namespace prevents a dependency's regular `tests`
        # package from shadowing this repository's namespace-only test tree.
        "import sys,types,runpy; from pathlib import Path; "
        "p=types.ModuleType('tests'); p.__path__=[str(Path.cwd()/'tests')]; "
        "sys.modules['tests']=p; sys.argv=['unittest',*sys.argv[1:]]; "
        "runpy.run_module('unittest',run_name='__main__')",
        "discover",
        "-s",
        "tests/unit",
        "-p",
        args.pattern,
        "-v",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(working_directory),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        print(f"Could not start isolated unittest pattern: {exc}", file=sys.stderr, flush=True)
        return 2
    try:
        if result.stdout:
            sys.stdout.buffer.write(result.stdout)
            sys.stdout.buffer.flush()
        if result.stderr:
            sys.stderr.buffer.write(result.stderr)
            sys.stderr.buffer.flush()
    except (BrokenPipeError, OSError) as exc:
        print(f"Could not forward isolated unittest output: {exc}", file=sys.stderr, flush=True)
        return 2
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
