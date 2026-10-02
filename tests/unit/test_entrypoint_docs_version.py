"""Regression checks for the shipped entrypoint, docs, and WPF version fallback."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class EntrypointDocsVersionTests(unittest.TestCase):
    def test_docs_describe_current_release_and_workflow(self):
        current_version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
        backend = (ROOT / "vntext" / "app_backend.py").read_text(encoding="utf-8")
        package = (ROOT / "vntext" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn(f'VERSION = "{current_version}"', backend)
        self.assertIn(f'__version__ = "{current_version}"', package)
        for name in ("README.md", "README_VI.txt"):
            text = (ROOT / name).read_text(encoding="utf-8")
            self.assertIn(current_version, text)
            self.assertNotIn("1.39-fast-extract", text)
            self.assertNotIn("1.40.4", text)
            self.assertIn("extract", text.lower())
            translation_term = "dich" if name == "README_VI.txt" else "translate"
            self.assertIn(translation_term, text.lower())
            self.assertIn("patch", text.lower())
            self.assertIn("CT2", text)
            self.assertNotIn("-IncludeVinAI", text)
            self.assertNotIn("-VinaiModelDir", text)

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
        self.assertIn('or "tk"', app)
        self.assertIn("qml_ui.bridge", app)  # retained only as explicit legacy opt-in
        for text in (readme, readme_vi):
            self.assertIn("DEV_RUN", text)
            self.assertIn("VNText.Studio.App.exe", text)
            self.assertIn("release", text.lower())
            self.assertIn("publish.ps1", text)

    def test_wpf_version_fallback_is_neutral_and_reads_version_file(self):
        source = (ROOT / "wpf_app/VNText.Studio.App/ViewModels/MainViewModel.cs").read_text(encoding="utf-8")
        self.assertIn('"vunknown"', source)
        self.assertNotIn('"v1.40.4"', source)
        self.assertIn('"VERSION.txt"', source)


if __name__ == "__main__":
    unittest.main()
