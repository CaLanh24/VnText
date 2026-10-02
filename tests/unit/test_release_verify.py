"""Regression coverage for RELEASE verification work-directory recovery."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch


def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    if str(lib) not in sys.path:
        sys.path.insert(0, str(lib))


_tests_lib_on_path()
from bootstrap import bootstrap

TESTS, ROOT, LIB = bootstrap(__file__)

from vntext.release_verify import resolve_artifacts_root, resolve_work_root, verify_workflow


class ReleaseVerifyTests(unittest.TestCase):
    def test_portable_python_preserves_license_and_rejects_missing_notice(self):
        from release.make_venv_portable import _copy_base_python
        sys.path.insert(0, str(TESTS / "tools"))
        from work_paths import WORK_ROOT, artifact_scope, new_scope_id

        scope = new_scope_id("portable-python-license")
        with artifact_scope(
            WORK_ROOT / scope,
            artifact_id=scope,
            kind="test_workspace",
            owner="test_release_verify.py",
            purpose="CPython notice preservation and missing-license rejection",
        ) as work:
            base = work / "base"
            dest = work / "bundled"
            (base / "Lib" / "encodings").mkdir(parents=True)
            (base / "python.exe").write_bytes(b"synthetic interpreter")
            for path in (base / "Lib" / "site.py", base / "Lib" / "encodings" / "__init__.py"):
                path.write_text("import sys\n", encoding="utf-8")
            dest.mkdir()
            sentinel = dest / "existing.txt"
            sentinel.write_bytes(b"keep existing runtime")
            with self.assertRaisesRegex(FileNotFoundError, "Base Python license missing"):
                _copy_base_python(base, dest)
            self.assertEqual(b"keep existing runtime", sentinel.read_bytes())

            license_bytes = b"Synthetic CPython license\r\nCopyright fixture\r\n"
            (base / "LICENSE.txt").write_bytes(license_bytes)
            _copy_base_python(base, dest)
            self.assertEqual(license_bytes, (dest / "LICENSE.txt").read_bytes())
            self.assertTrue((dest / "python.exe").is_file())
            self.assertTrue((dest / "python312.zip").is_file())

    def test_publisher_records_the_ct2_revision_from_staged_source(self):
        publish = (ROOT / "release" / "publish.ps1").read_text(encoding="utf-8")

        self.assertIn("from vntext.mt_ct2_constants import MODEL_REVISION", publish)
        self.assertIn("revision = $modelRevision", publish)

    def test_release_workflow_uses_the_ct2_product_route(self):
        from vntext.package_io import read_csv_rows_file, write_csv_rows_file

        def translate_with_ct2(csv_path, **kwargs):
            fields, rows = read_csv_rows_file(Path(csv_path))
            for row in rows:
                row["translation"] = "Xin chào"
            write_csv_rows_file(Path(csv_path), fields, rows)
            return {"ok": True, "qa": {"status": "PASS"}}

        with tempfile.TemporaryDirectory() as temp:
            with (
                patch("vntext.mt_ct2.run_ct2_translate", side_effect=translate_with_ct2) as ct2,
            ):
                result = verify_workflow(Path(temp))

        self.assertEqual("ct2", result["backend"])
        self.assertGreater(result["translate_filled"], 0)
        ct2.assert_called_once()

    def test_argos_is_not_a_release_dependency_or_packaging_route(self):
        default_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
        publish = (ROOT / "release" / "publish.ps1").read_text(encoding="utf-8")
        spec = (ROOT / "release" / "vntext_studio.spec").read_text(encoding="utf-8").lower()

        self.assertNotIn("argostranslate", default_requirements)
        self.assertFalse((ROOT / "requirements-legacy-argos.txt").exists())
        self.assertNotIn("requirements-legacy-argos.txt", publish)
        self.assertNotIn("import argostranslate", publish.lower())
        self.assertNotIn("argostranslate", spec)
        self.assertNotIn("minisbd", spec)

    def test_release_launchers_disable_python_bytecode_and_publish_records_sha(self):
        worker_host = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "PythonWorkerHost.cs").read_text(encoding="utf-8")
        verify_runner = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "ReleaseVerifyRunner.cs").read_text(encoding="utf-8")
        publish = (ROOT / "release" / "publish.ps1").read_text(encoding="utf-8")
        release_e2e = (ROOT / "release" / "run_release_e2e.ps1").read_text(encoding="utf-8")
        portable = (ROOT / "release" / "make_venv_portable.py").read_text(encoding="utf-8")
        self.assertIn('Environment["PYTHONDONTWRITEBYTECODE"] = "1"', worker_host)
        self.assertIn('Environment["PYTHONDONTWRITEBYTECODE"] = "1"', verify_runner)
        self.assertIn('$env:PYTHONDONTWRITEBYTECODE = "1"', publish)
        self.assertIn('name == "__pycache__"', portable)
        self.assertIn('ignore_patterns("__pycache__", "*.pyc", "*.pyo")', portable)
        self.assertIn('"PYTHONDONTWRITEBYTECODE"', portable)
        self.assertIn('sitecustomize.py', portable)
        self.assertIn('sys.dont_write_bytecode = True', portable)
        self.assertIn('encodings") / "__init__.py', portable)
        self.assertIn('Path("site.py")', portable)
        self.assertIn('zipfile.ZipFile', portable)
        self.assertIn('ReadToEndAsync()', verify_runner)
        self.assertIn('Task.WaitAll(stdoutTask, stderrTask)', verify_runner)
        self.assertIn('AssemblyInformationalVersionAttribute', verify_runner)
        self.assertIn('FileVersionInfo.GetVersionInfo', verify_runner)
        self.assertIn('mode == "--release-version"', verify_runner)
        self.assertIn('"--release-verify-update"', verify_runner)
        self.assertIn('"--release-verify-update"', (ROOT / "wpf_app" / "VNText.Studio.App" / "App.xaml.cs").read_text(encoding="utf-8"))
        self.assertIn('VNTEXT_UPDATE_URL', verify_runner)
        self.assertIn('VNTEXT_UPDATE_TARGET_EXE', verify_runner)
        self.assertIn('UPDATE_TARGET_ENV', (ROOT / "vntext" / "app_update.py").read_text(encoding="utf-8"))
        self.assertIn('-p:Version=$version', publish)
        self.assertIn('-p:InformationalVersion=$version', publish)
        self.assertIn('-p:IncludeSourceRevisionInInformationalVersion=false', publish)
        self.assertIn('-p:AssemblyVersion=$versionNumeric', publish)
        self.assertIn('-p:FileVersion=$versionNumeric', publish)
        self.assertIn('$nugetConfig = Join-Path $dotnetRuntimeRoot "NuGet.Config"', publish)
        self.assertIn('$env:NUGET_PACKAGES = $nugetPackages', publish)
        self.assertIn('[System.Security.Cryptography.SHA256]::Create()', publish)
        self.assertNotIn('Get-FileHash -LiteralPath', publish)
        self.assertIn(
            'dotnet restore $wpfProj -r win-x64 --configfile $nugetConfig --ignore-failed-sources',
            publish,
        )
        self.assertIn(
            'dotnet restore $installerProj -r win-x64 --configfile $nugetConfig --ignore-failed-sources',
            publish,
        )
        self.assertIn(
            "dotnet publish $wpfProj `\n"
            "        -c Release -r win-x64 --self-contained false --no-restore `",
            publish,
        )
        self.assertNotIn(
            "dotnet publish $wpfProj `\n"
            "        -c Release -r win-x64 --self-contained true `",
            publish,
        )
        self.assertIn('$CandidateRoot', release_e2e)
        self.assertIn('-ReleaseRoot $CandidateRoot', release_e2e)
        self.assertIn('-WpfUpdateVersion $nextVersion', release_e2e)
        self.assertIn('-WpfUpdateVersion $nextWpfUpdateVersion', release_e2e)
        self.assertIn('Assert-UpdatedExeIdentity', release_e2e)
        self.assertNotIn('-SkipTests -ReleaseRoot $ReleaseRoot', release_e2e)
        self.assertNotIn('var stdout = proc.StandardOutput.ReadToEnd();', verify_runner)
        verifier_source = (ROOT / "vntext" / "release_verify.py").read_text(encoding="utf-8")
        self.assertIn('"status": "TRACE_NOT_ENABLED"', verifier_source)
        self.assertIn('per-entry TraceStore stage/root-cause coverage', verifier_source)
        self.assertIn("source_sha = $SourceSha", publish)
        self.assertIn('MODEL_MANIFEST.json', publish)
        self.assertIn('site.getsitepackages()[-1]', publish)
        self.assertIn('Merge system site-packages', publish)
        self.assertIn('license = "Apache-2.0"', publish)
        self.assertIn('distribution = "bundled"', publish)
        self.assertNotIn("-IncludeVinAI", publish)
        self.assertNotIn("-VinaiModelDir", publish)
        self.assertNotIn("torch>=", (ROOT / "requirements.txt").read_text(encoding="utf-8"))
        self.assertIn("lifecycle='DISPOSABLE'", publish)
        registration_call = next(line for line in publish.splitlines() if "& $Python -B -c $registerScript" in line)
        self.assertIn("$workRoot $staging $payloadZip $setupExe $wpfUpdatePublish $updatesStaging", registration_call)
        self.assertNotIn("$ReleaseRoot", registration_call)
        for pattern in (
            '"test_traceability.py"',
            '"test_patch_readback.py"',
            '"test_mt_classify.py"',
            '"test_translation_cache.py"',
            '"test_glossary_context_v2.py"',
            '"test_setup_package.py"',
        ):
            self.assertIn(pattern, publish)
        self.assertLess(publish.index("Clean-ReleaseArtifacts $staging"), publish.index("Final Release audit"))

    def test_artifacts_root_falls_back_when_appdata_path_is_not_a_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            primary = root / "blocked"
            fallback = root / "fallback"
            primary.write_text("blocked", encoding="utf-8")

            artifacts_root = resolve_artifacts_root(primary, fallback)

            self.assertEqual(fallback, artifacts_root)
            self.assertTrue(artifacts_root.is_dir())

    def test_work_root_falls_back_when_primary_is_not_a_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            artifacts_root = Path(temp)
            (artifacts_root / "release_verify").write_text("blocked", encoding="utf-8")

            work_root = resolve_work_root(artifacts_root)

            self.assertNotEqual(artifacts_root / "release_verify", work_root)
            self.assertTrue(work_root.is_dir())
            probe = work_root / "result.json"
            probe.write_text("{}", encoding="utf-8")
            self.assertTrue(probe.is_file())


if __name__ == "__main__":
    unittest.main()
