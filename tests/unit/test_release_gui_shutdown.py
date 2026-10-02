"""Black-box Release GUI shutdown regression."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASE_EXE = Path(
    os.environ.get("VNTEXT_RELEASE_EXE", str(ROOT / "DEV_RUN" / "VNText.Studio.App.exe"))
).resolve()
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "tests" / "lib"))
from work_paths import WORK_ROOT, ambient_scope, new_scope_id, register_artifact  # noqa: E402


def _runtime_root(executable: Path) -> Path:
    bundled = executable.parent / "dotnet"
    root = bundled if (bundled / "dotnet.exe").is_file() else Path(
        os.environ.get("ProgramFiles", r"C:\Program Files")
    ) / "dotnet"
    desktop = root / "shared" / "Microsoft.WindowsDesktop.App"
    if not (root / "dotnet.exe").is_file() or not any(
        path.is_dir() and path.name.startswith("8.") for path in desktop.iterdir()
    ):
        raise AssertionError(f".NET 8 Windows Desktop runtime not found under {root}")
    return root.resolve()


def _register_root(path: Path, purpose: str) -> None:
    ambient = ambient_scope()
    register_artifact(
        artifact_id=f"gui-shutdown:{path.name}",
        path=path,
        kind="test_temp",
        created_by="test_release_gui_shutdown.py",
        owner="test_release_gui_shutdown.py",
        purpose=purpose,
        lifecycle="DISPOSABLE",
        scope_id=ambient["scope_id"],
        run_id=ambient["run_id"],
        scope_root=ambient["scope_root"],
    )


def _close_main_window(pid: int, wait_seconds: int = 15) -> subprocess.CompletedProcess[str]:
    script = (
        "$ErrorActionPreference='Stop'; "
        f"$deadline=[DateTime]::UtcNow.AddSeconds({wait_seconds}); $closed=$false; $handle=0; $title=''; "
        f"do {{ $p=Get-Process -Id {pid} -ErrorAction SilentlyContinue; "
        "if (!$p) { break }; $p.Refresh(); "
        "$handle=$p.MainWindowHandle.ToInt64(); $title=$p.MainWindowTitle; "
        "if ($title -eq 'VNText Studio') { $closed=$p.CloseMainWindow(); if ($closed) { break } }; "
        "Start-Sleep -Milliseconds 100 "
        "} while ([DateTime]::UtcNow -lt $deadline); "
        "[Console]::WriteLine((@{closed=$closed; hwnd=$handle; title=$title} | ConvertTo-Json -Compress))"
    )
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise RuntimeError("PowerShell is required to close the WPF test window")
    return subprocess.run(
        [powershell, "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=wait_seconds + 5,
    )


class ReleaseGuiShutdownTests(unittest.TestCase):
    def test_close_main_window_exits_and_reaps_gui_process(self):
        if os.name != "nt":
            self.skipTest("Windows WPF only")
        if not RELEASE_EXE.is_file():
            self.skipTest(f"GUI executable missing: {RELEASE_EXE}")
        worker_python = ROOT / ".venv" / "Scripts" / "python.exe"
        if not worker_python.is_file():
            self.fail(f"isolated worker Python is missing: {worker_python}")

        run_token = new_scope_id("gui-shutdown")
        temp_root = WORK_ROOT / f"{run_token}-temp"
        localappdata = WORK_ROOT / f"{run_token}-localappdata"
        _register_root(temp_root, "isolated GUI process temporary directory")
        _register_root(localappdata, "isolated GUI and worker LocalAppData")
        temp_root.mkdir()
        localappdata.mkdir()

        app_data = localappdata / "VNTextStudio"
        runtime = _runtime_root(RELEASE_EXE)
        env = os.environ.copy()
        env.update(
            {
                "DOTNET_ROOT": str(runtime),
                "DOTNET_ROOT_X64": str(runtime),
                "VNTEXT_RELEASE_EXE": str(RELEASE_EXE),
                "VNTEXT_WORKER_CWD": str(ROOT),
                "VNTEXT_WORKER_PYTHON": str(worker_python),
                "VNTEXT_LOCALAPPDATA": str(localappdata),
                "VNTEXT_DATA_ROOT": str(app_data),
                "PYTHONDONTWRITEBYTECODE": "1",
                "APPDATA": str(localappdata),
                "LOCALAPPDATA": str(localappdata),
                "TEMP": str(temp_root),
                "TMP": str(temp_root),
                "TMPDIR": str(temp_root),
                "HF_HOME": str(app_data / "cache" / "huggingface"),
                "HF_HUB_CACHE": str(app_data / "cache" / "huggingface" / "hub"),
                "TRANSFORMERS_CACHE": str(app_data / "cache" / "huggingface" / "transformers"),
                "TORCH_HOME": str(app_data / "cache" / "torch"),
                "VNTEXT_DIRECT_GPU_ROOT": str(app_data / "cache" / "gpu"),
            }
        )

        sha256 = hashlib.sha256(RELEASE_EXE.read_bytes()).hexdigest().upper()
        proc: subprocess.Popen[bytes] | None = None
        try:
            proc = subprocess.Popen([str(RELEASE_EXE)], cwd=temp_root, env=env)
            print(
                "GUI_SHUTDOWN_CONFIG "
                + json.dumps(
                    {
                        "pid": proc.pid,
                        "exe": str(RELEASE_EXE),
                        "sha256": sha256,
                        "cwd": str(temp_root),
                        "dotnet_root": str(runtime),
                        "worker_cwd": str(ROOT),
                        "worker_python": str(worker_python),
                        "localappdata": str(localappdata),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )

            # Wait for the app's one-second WPF auxiliary-window normalization timer
            # before Process.CloseMainWindow selects a window handle.
            time.sleep(1.5)
            result = _close_main_window(proc.pid)
            target = json.loads(result.stdout)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertTrue(
                target["closed"],
                f"WPF main window did not appear: {target}; Popen return code={proc.poll()}, "
                f"exe={RELEASE_EXE}, sha256={sha256}, runtime={runtime}",
            )
            self.assertEqual("VNText Studio", target["title"])
            self.assertEqual(0, proc.wait(timeout=35), "GUI did not exit cleanly after CloseMainWindow")

            # A published Release must remain free of build-only files.
            if (RELEASE_EXE.parent / "RELEASE.json").is_file():
                forbidden = [
                    path
                    for pattern in ("*.pyc", "*.pyo", "*.log", "*.pdb")
                    for path in RELEASE_EXE.parent.rglob(pattern)
                ]
                self.assertEqual([], forbidden, f"Release gained forbidden files: {forbidden}")
        finally:
            if proc is not None and proc.poll() is None:
                _close_main_window(proc.pid, wait_seconds=10)
                proc.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
