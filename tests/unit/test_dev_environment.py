from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.lib.dev_environment import (
    REPOSITORY_ROOT,
    dev_env_root,
    dotnet_executable,
    nuget_cache,
    release_python,
    renpy_native_sdk,
    worker_python,
)


class DevEnvironmentPathTests(unittest.TestCase):
    def test_default_paths_remain_checkout_local(self):
        with patch.dict(os.environ, {}, clear=True):
            root = REPOSITORY_ROOT / ".dev-env"
            self.assertEqual(root, dev_env_root())
            self.assertEqual(root / ".venv" / "Scripts" / "python.exe", worker_python())
            self.assertEqual(root / "release-venv" / "Scripts" / "python.exe", release_python())
            self.assertEqual(root / "tools" / "renpy-8.5.3", renpy_native_sdk())
            self.assertEqual(root / "dotnet-sdk-10" / "dotnet.exe", dotnet_executable())
            self.assertEqual(root / "cache" / "nuget", nuget_cache())

    def test_explicit_shared_root_and_executable_overrides_are_respected(self):
        with patch.dict(
            os.environ,
            {
                "VNTEXT_DEV_ENV_ROOT": r"C:\shared\dev",
                "VNTEXT_WORKER_PYTHON": r"C:\shared\python.exe",
                "VNTEXT_RELEASE_PYTHON": r"C:\shared\release-python.exe",
                "VNTEXT_RENPY_NATIVE_SDK": r"C:\shared\renpy-8.5.3",
                "VNTEXT_DOTNET": r"C:\shared\dotnet.exe",
            },
            clear=True,
        ):
            root = Path(r"C:\shared\dev")
            self.assertEqual(root, dev_env_root())
            self.assertEqual(Path(r"C:\shared\python.exe"), worker_python())
            self.assertEqual(Path(r"C:\shared\release-python.exe"), release_python())
            self.assertEqual(Path(r"C:\shared\renpy-8.5.3"), renpy_native_sdk())
            self.assertEqual(Path(r"C:\shared\dotnet.exe"), dotnet_executable())
            self.assertEqual(root / "cache" / "nuget", nuget_cache())
