"""Public gate for requirements/locks: hash pairing, dependency closure, top-level coverage."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCKS = ROOT / "requirements" / "locks"

try:
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    from packaging.version import Version
except ImportError:  # pragma: no cover - the locked runtime always ships packaging
    Requirement = None


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_dependency_locks", ROOT / "release" / "verify_dependency_locks.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipIf(Requirement is None, "packaging is not installed")
class DependencyLockClosureTests(unittest.TestCase):
    def test_every_lock_profile_verifies(self):
        verifier = _load_verifier()
        profiles = sorted(LOCKS.glob("windows-*.json"))
        self.assertTrue(profiles)
        for path in profiles:
            with self.subTest(profile=path.stem):
                self.assertEqual(verifier.verify(path)["outcome"], "PASS")

    def test_runtime_requirements_are_locked(self):
        top_level = [
            Requirement(line.split("#", 1)[0].strip())
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.split("#", 1)[0].strip() and not line.startswith("-")
        ]
        profiles = sorted(LOCKS.glob("windows-*-runtime.json"))
        self.assertTrue(profiles)
        for path in profiles:
            packages = {canonicalize_name(p["name"]): p["version"] for p in json.loads(path.read_text(encoding="utf-8"))["packages"]}
            for req in top_level:
                with self.subTest(profile=path.stem, requirement=str(req)):
                    version = packages.get(canonicalize_name(req.name))
                    self.assertIsNotNone(version, f"{req.name} missing from {path.name}")
                    self.assertIn(Version(version), req.specifier)


if __name__ == "__main__":
    unittest.main()
