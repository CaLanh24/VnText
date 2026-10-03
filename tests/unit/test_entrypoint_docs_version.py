"""Regression checks for the shipped entrypoint, docs, and WPF version fallback."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]


class EntrypointDocsVersionTests(unittest.TestCase):
    def test_docs_describe_current_release_and_workflow(self):
        current_version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
        backend = (ROOT / "vntext" / "app_backend.py").read_text(encoding="utf-8")
        package = (ROOT / "vntext" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn(f'VERSION = "{current_version}"', backend)
        self.assertIn(f'__version__ = "{current_version}"', package)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_vi = (ROOT / "README_VI.txt").read_text(encoding="utf-8")
        development = (ROOT / "docs" / "DEVELOPMENT.md").read_text(encoding="utf-8")
        self.assertIn(current_version, readme)
        self.assertNotIn("1.39-fast-extract", readme)
        self.assertNotIn("1.40.4", readme)
        self.assertIn("**Extract**", readme)
        self.assertIn("Dịch trong ứng dụng", readme)
        self.assertIn("nhập CSV", readme)
        self.assertIn("**Patch**", readme)
        self.assertLess(readme.index("**Extract**"), readme.index("Dịch trong ứng dụng"))
        self.assertLess(readme.index("Dịch trong ứng dụng"), readme.index("**Patch**"))
        self.assertIn("README.md", readme_vi)
        self.assertIn("docs/DEVELOPMENT.md", readme_vi)
        self.assertLess(len(readme_vi), 300)
        self.assertIn("Python 3.11", development)
        self.assertIn("CTranslate2", development)
        self.assertIn("dotnet build", development)
        self.assertIn("tests/unit/test_wpf_workflow.py", development)
        self.assertIn("DEV_RUN", development)
        self.assertIn("--smoke-worker", development)
        self.assertIn("publish.ps1", development)
        self.assertIn("TEST_MATRIX.md", development)
        # Every requirements path in the clone instructions must exist publicly.
        requirement_paths = set(re.findall(r"(?:release/)?requirements[\w-]*\.txt", development))
        self.assertTrue(requirement_paths)
        for relative in requirement_paths:
            self.assertTrue((ROOT / relative).is_file(), f"Missing documented prerequisite: {relative}")
        self.assertNotIn("DEV_RUN", readme + readme_vi)
        self.assertNotIn("-IncludeVinAI", readme + readme_vi + development)
        self.assertNotIn("-VinaiModelDir", readme + readme_vi + development)
        requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
        self.assertIn("ctranslate2==4.8.1", requirements)

    def test_windows_metadata_keeps_versions_and_owner_copyright(self):
        current_version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
        version_parts = tuple(int(part) for part in current_version.split("."))
        self.assertEqual(len(version_parts), 3)
        file_parts = (*version_parts, 0)
        file_version = ".".join(str(part) for part in file_parts)
        version_info = (ROOT / "release" / "version_info.txt").read_text(encoding="utf-8")
        self.assertIn(f"filevers=({', '.join(str(part) for part in file_parts)})", version_info)
        self.assertIn(f"prodvers=({', '.join(str(part) for part in file_parts)})", version_info)
        self.assertIn(f"FileVersion', u'{file_version}'", version_info)
        self.assertIn(f"ProductVersion', u'{current_version}'", version_info)
        self.assertIn("LegalCopyright', u'Copyright 2026 Calanh'", version_info)

    def test_default_entrypoints_and_legacy_opt_in_do_not_require_qml(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        readme_vi = (ROOT / "README_VI.txt").read_text(encoding="utf-8")
        development = (ROOT / "docs" / "DEVELOPMENT.md").read_text(encoding="utf-8")
        self.assertIn('or "tk"', app)
        self.assertIn("qml_ui.bridge", app)  # retained only as explicit legacy opt-in
        self.assertIn("release", readme.lower())
        self.assertIn("dotnet build", development)

    def test_wpf_version_fallback_is_neutral_and_reads_version_file(self):
        source = (ROOT / "wpf_app/VNText.Studio.App/ViewModels/MainViewModel.cs").read_text(encoding="utf-8")
        self.assertIn('"vunknown"', source)
        self.assertNotIn('"v1.40.4"', source)
        self.assertIn('"VERSION.txt"', source)


if __name__ == "__main__":
    unittest.main()
