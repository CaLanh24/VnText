from __future__ import annotations

import os
from pathlib import Path
import tempfile
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
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "shared" / "dev"
            worker = root.parent / "python.exe"
            release = root.parent / "release-python.exe"
            sdk = root.parent / "renpy-8.5.3"
            dotnet = root.parent / "dotnet.exe"
            with patch.dict(
                os.environ,
                {
                    "VNTEXT_DEV_ENV_ROOT": str(root),
                    "VNTEXT_WORKER_PYTHON": str(worker),
                    "VNTEXT_RELEASE_PYTHON": str(release),
                    "VNTEXT_RENPY_NATIVE_SDK": str(sdk),
                    "VNTEXT_DOTNET": str(dotnet),
                },
                clear=True,
            ):
                self.assertEqual(root.resolve(), dev_env_root())
                self.assertEqual(worker.resolve(), worker_python())
                self.assertEqual(release.resolve(), release_python())
                self.assertEqual(sdk.resolve(), renpy_native_sdk())
                self.assertEqual(dotnet.resolve(), dotnet_executable())
                self.assertEqual((root / "cache" / "nuget").resolve(), nuget_cache())
