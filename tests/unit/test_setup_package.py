"""Focused hash and path-boundary checks for the single-file Setup payload."""
from __future__ import annotations

import sys
from pathlib import Path
import os
import stat
import base64
import subprocess
import unittest
import zipfile
import hashlib
import json
import re
from uuid import uuid4

def _bootstrap_tests():
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    sys.path.insert(0, str(cur / "lib"))
    from bootstrap import bootstrap
    return bootstrap(__file__)

TESTS, ROOT, _LIB = _bootstrap_tests()
sys.path.insert(0, str(ROOT / "release"))
import package_installer
import publish_owner_wpf_update
from work_paths import new_scope_id, register_artifact, artifact_scope
sys.path.insert(0, str(TESTS / "tools"))
from cleanup_work_artifacts import cleanup_after_test


class SetupPackageTests(unittest.TestCase):
    def test_wpf_brand_assets_require_all_product_files_and_exact_hashes(self):
        import shutil
        names = ("release/assets/vntext_studio.ico",
                 "wpf_app/VNText.Studio.App/Assets/vntext_studio.ico",
                 "wpf_app/VNText.Studio.App/Assets/vntext_studio_logo_128.png",
                 "wpf_app/VNText.Studio.App/Assets/vntext_studio_logo_256.png")
        generated = TESTS / "golden" / "_work" / f"wpf-brand-{uuid4().hex}"
        with artifact_scope(generated, artifact_id=generated.name, kind="test_fixture",
                            owner="test_setup_package.py", purpose="WPF brand integrity test"):
            for name in names:
                target = generated / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            command = f"Assert-WpfBrandAssets '{generated}' '{ROOT}'"
            helpers = ["Get-Sha256", "Assert-WpfBrandAssets"]
            result = self._publisher_call(helpers, command)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            for name in names:
                target = generated / name
                original = target.read_bytes()
                target.write_bytes(b"tampered")
                self.assertNotEqual(0, self._publisher_call(helpers, command).returncode, name)
                target.unlink()
                self.assertNotEqual(0, self._publisher_call(helpers, command).returncode, name)
                target.write_bytes(original)

    def _publisher_call(self, names, command):
        source = str(ROOT / "release" / "publish.ps1").replace("'", "''")
        selected = ",".join("'" + name + "'" for name in names)
        script = f"""
$ErrorActionPreference = 'Stop'
$tokens = $null; $errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{source}', [ref]$tokens, [ref]$errors)
if ($errors.Count) {{ throw ($errors | Out-String) }}
$names = @({selected})
$functions = @($ast.FindAll({{ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -in $names }}, $false))
if ($functions.Count -ne $names.Count) {{ throw 'Publisher helper missing' }}
foreach ($function in $functions) {{ . ([scriptblock]::Create($function.Extent.Text)) }}
{command}
"""
        return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                              capture_output=True, text=True, timeout=30)

    def test_project_notices_copy_hash_and_missing_source(self):
        from work_paths import work_temp_dir
        import shutil

        work = work_temp_dir("setup-notices")
        sources = {
            "LICENSE": "APACHE-2.0.txt", "NOTICE": "NOTICE",
            "THIRD_PARTY_NOTICES.md": "THIRD_PARTY_NOTICES.md",
            **{f"release/licenses/{name}": f"python/{name}" for name in (
                "ctranslate2-MIT.txt", "sentencepiece-darts_clone.txt",
                "sentencepiece-esaxx.txt", "sentencepiece-protobuf-lite.txt")},
            **{f"release/licenses/{name}": f"native/{name}" for name in (
                "cudnn-9.10.2-eula.html", "cudnn-9.10.2-acknowledgements.html",
                "intel-2025.3-cpp-eula.rtf", "intel-2025.3-customer-terms.txt", "intel-2025.3-credist.txt",
                "intel-2025.3-compiler-third-party-programs.txt",
                "intel-2025.3-openmp-third-party-programs.txt", "intel-2025.3-tbb-license.txt",
                "intel-2025.3-tbb-third-party-programs.txt")},
        }
        fixture = work / "source"
        app = work / "app"
        for relative in sources:
            target = fixture / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)
        def copy():
            return self._publisher_call(["Copy-ProjectNotices"], f"Copy-ProjectNotices '{fixture}' '{app}'")
        copied = copy()
        self.assertEqual(0, copied.returncode, copied.stdout + copied.stderr)
        for relative, destination in sources.items():
            self.assertEqual((ROOT / relative).read_bytes(), (app / "licenses" / destination).read_bytes())
        for relative in sources:
            saved = (fixture / relative).read_bytes()
            (fixture / relative).unlink()
            missing = copy()
            self.assertNotEqual(0, missing.returncode)
            self.assertIn("Release license source missing", missing.stderr)
            (fixture / relative).write_bytes(saved)
        publish_source = (ROOT / "release" / "publish.ps1").read_text(encoding="utf-8")
        layout = publish_source[publish_source.index("function Assert-ReleaseLayout("):]
        for name in (
            "intel-2025.3-cpp-eula.rtf", "intel-2025.3-credist.txt",
            "intel-2025.3-customer-terms.txt",
            "intel-2025.3-compiler-third-party-programs.txt",
            "intel-2025.3-openmp-third-party-programs.txt", "intel-2025.3-tbb-license.txt",
            "intel-2025.3-tbb-third-party-programs.txt",
        ):
            self.assertIn(f'"native\\{name}"', layout)
        print(f"NOTICE_COPY: {len(sources)} exact copy/hash matches; {len(sources)} missing-input rejections")

    def test_installer_version_guard_rejects_mismatch(self):
        from work_paths import work_temp_dir

        work = work_temp_dir("setup-version-guard")
        source = work / "fixture.cs"
        source.write_text("class Fixture { static void Main() {} }", encoding="utf-8")
        csc = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        assembly = work / "fixture.exe"
        built = subprocess.run([str(csc), "/nologo", f"/out:{assembly}", str(source)],
                               capture_output=True, text=True, timeout=90)
        self.assertEqual(0, built.returncode, built.stdout + built.stderr)
        rejected = self._publisher_call(["Assert-SetupVersion"], f"Assert-SetupVersion '{assembly}' '2.3.4' '2.3.4.0'")
        self.assertNotEqual(0, rejected.returncode)
        self.assertIn("Installer version mismatch", rejected.stderr)
        invalid = self._publisher_call(["Write-SetupVersionSource"], f"Write-SetupVersionSource '{work / 'invalid.cs'}' '2.3.4' '2.3.5.0'")
        self.assertNotEqual(0, invalid.returncode)
        self.assertFalse((work / "invalid.cs").exists())

    def test_publisher_layout_rejects_fmod_binaries(self):
        from work_paths import work_temp_dir

        root = work_temp_dir("setup-fmod-guard")
        source = (ROOT / "release" / "publish.ps1").read_text(encoding="utf-8")
        start = source.index("function Assert-ReleaseLayout(")
        end = source.index("\nif ($RequireIsolatedArtifacts)", start)
        function = source[start:end]
        for name in ("fmod.dll", "FMODSTUDIO.DLL", "libfmod.so.13", "libfmod.dylib"):
            binary = root / name
            binary.write_bytes(b"vendor fixture")
            quoted_root = str(root).replace("'", "''")
            command = function + f"\nAssert-ReleaseLayout '{quoted_root}' '8.0.30' '8.0.30'"
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                capture_output=True, text=True, timeout=30,
            )
            self.assertNotEqual(0, proc.returncode)
            self.assertIn("RELEASE contains vendor FMOD binaries", proc.stderr)
            binary.unlink()

    def test_hash_inventory_and_traversal_rejection(self):
        work = TESTS / "golden" / "_work" / f"setup-package-{uuid4().hex}"
        scope = os.environ.get("VNTEXT_ARTIFACT_SCOPE_ID") or new_scope_id("setup-package")
        run_id = os.environ.get("VNTEXT_ARTIFACT_RUN_ID") or scope
        register_artifact(artifact_id=f"setup-package:{work.name}", path=work, kind="test_workspace", created_by="test_setup_package.py", owner="test_setup_package.py", purpose="Setup package hash and traversal test", lifecycle="DISPOSABLE", scope_id=scope, run_id=run_id)
        payload = work / "payload"
        archive = work / "payload.zip"
        payload.mkdir(parents=True, exist_ok=True)
        (payload / "app" / "worker").mkdir(parents=True, exist_ok=True)
        (payload / "app" / "worker" / "app.py").write_text("payload", encoding="utf-8")
        license_dir = payload / "app" / "licenses"
        license_dir.mkdir(parents=True)
        copied = self._publisher_call(["Copy-ProjectNotices"], f"Copy-ProjectNotices '{ROOT}' '{payload / 'app'}'")
        self.assertEqual(0, copied.returncode, copied.stdout + copied.stderr)
        (payload / "VNText Studio.exe").write_bytes(b"main app")
        (payload / "Uninstall.exe").write_bytes(b"uninstaller")
        outcome = "FAIL"
        try:
            manifest = package_installer.build(payload, archive)
            self.assertEqual({
                "app/worker/app.py",
                "app/licenses/APACHE-2.0.txt",
                "app/licenses/NOTICE",
                "app/licenses/THIRD_PARTY_NOTICES.md",
                "app/licenses/python/ctranslate2-MIT.txt",
                "app/licenses/python/sentencepiece-darts_clone.txt",
                "app/licenses/python/sentencepiece-esaxx.txt",
                "app/licenses/python/sentencepiece-protobuf-lite.txt",
                "app/licenses/native/cudnn-9.10.2-eula.html",
                "app/licenses/native/cudnn-9.10.2-acknowledgements.html",
                "app/licenses/native/intel-2025.3-cpp-eula.rtf",
                "app/licenses/native/intel-2025.3-customer-terms.txt",
                "app/licenses/native/intel-2025.3-credist.txt",
                "app/licenses/native/intel-2025.3-compiler-third-party-programs.txt",
                "app/licenses/native/intel-2025.3-openmp-third-party-programs.txt",
                "app/licenses/native/intel-2025.3-tbb-license.txt",
                "app/licenses/native/intel-2025.3-tbb-third-party-programs.txt",
                "VNText Studio.exe",
                "Uninstall.exe",
            }, set(manifest["files"]))
            self.assertEqual(manifest, package_installer.verify(archive))
            (payload / "unexpected.txt").write_text("not allowed", encoding="utf-8")
            with self.assertRaises(ValueError):
                package_installer.build(payload, work / "invalid-layout.zip")
            (payload / "unexpected.txt").unlink()
            csc = Path(os.environ["WINDIR"]) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
            if not csc.is_file():
                csc = Path(os.environ["WINDIR"]) / "Microsoft.NET" / "Framework" / "v4.0.30319" / "csc.exe"
            source = ROOT / "release" / "Setup.cs"
            references = [f"/reference:{name}.dll" for name in ("System.Windows.Forms", "System.Web.Extensions", "System.IO.Compression", "System.IO.Compression.FileSystem")]
            setup_exe = work / "Setup.exe"
            uninstaller = work / "Uninstall.exe"
            version = (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
            numeric = version.split("-", 1)[0] + ".0"
            attributes = work / "SetupVersion.cs"
            generated = self._publisher_call(["Write-SetupVersionSource"], f"Write-SetupVersionSource '{attributes}' '{version}' '{numeric}'")
            self.assertEqual(0, generated.returncode, generated.stdout + generated.stderr)
            built = subprocess.run([str(csc), "/nologo", "/target:winexe", f"/out:{setup_exe}", f"/resource:{archive},Payload.zip", *references, str(source), str(attributes)], capture_output=True, text=True, timeout=90)
            self.assertEqual(0, built.returncode, built.stdout + built.stderr)
            built_uninstaller = subprocess.run([str(csc), "/nologo", "/target:winexe", "/define:UNINSTALLER", f"/out:{uninstaller}", *references, str(source), str(attributes)], capture_output=True, text=True, timeout=90)
            self.assertEqual(0, built_uninstaller.returncode, built_uninstaller.stdout + built_uninstaller.stderr)
            self.assertTrue(setup_exe.is_file() and uninstaller.is_file())
            for executable in (setup_exe, uninstaller):
                checked = self._publisher_call(["Assert-SetupVersion"], f"Assert-SetupVersion '{executable}' '{version}' '{numeric}'")
                self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)
            print(f"INSTALLER_VERSION: actual Setup + Uninstall PE Product={version}; File/Assembly={numeric}")
            changed = work / "changed.zip"
            with zipfile.ZipFile(archive) as original, zipfile.ZipFile(changed, "w") as altered:
                for item in original.infolist():
                    altered.writestr(item.filename, b"tampered" if item.filename == "app/worker/app.py" else original.read(item))
            with self.assertRaises(ValueError):
                package_installer.verify(changed)
            traversal = work / "traversal.zip"
            with zipfile.ZipFile(archive) as original, zipfile.ZipFile(traversal, "w") as altered:
                for item in original.infolist():
                    altered.writestr(item.filename, original.read(item))
                altered.writestr("../escape.txt", "unsafe")
            with self.assertRaises(ValueError):
                package_installer.verify(traversal)
            setup_source = source.read_text(encoding="utf-8")
            publish_source = (ROOT / "release" / "publish.ps1").read_text(encoding="utf-8")
            self.assertIn("function Copy-ProjectNotices", publish_source)
            self.assertIn("Copy-ProjectNotices $DevRoot $stagingApp", publish_source)
            self.assertIn('"python\\sentencepiece-protobuf-lite.txt"', publish_source)
            self.assertIn('Source = "release\\licenses\\ctranslate2-MIT.txt"', publish_source)
            self.assertIn('Source = "release\\licenses\\intel-2025.3-cpp-eula.rtf"', publish_source)
            self.assertIn('Source = "release\\licenses\\intel-2025.3-customer-terms.txt"', publish_source)
            self.assertIn('"native\\intel-2025.3-customer-terms.txt"', publish_source)
            self.assertIn("private const string IntelTermsPath", setup_source)
            self.assertIn("private const string IntelEulaPath", setup_source)
            self.assertIn("View original Intel agreement", setup_source)
            self.assertIn("ShowOriginalIntelEula(eula)", setup_source)
            install_source = setup_source[setup_source.index("private static int Install()"):setup_source.index("private static Form CreateProgressWindow")]
            self.assertIn("try { accepted = ConfirmIntelTerms(); }", install_source)
            self.assertLess(install_source.index("ConfirmIntelTerms()"), install_source.index("new FolderBrowserDialog()"))
            self.assertIn("if (!accepted) return 1;", install_source)
            self.assertIn("Setup could not verify the Intel terms in its payload:", install_source)
            self.assertIn("return 2;", install_source)
            consent_source = setup_source[setup_source.index("private static bool ConfirmIntelTerms"):setup_source.index("private static void ShowOriginalIntelEula")]
            self.assertIn('accept.DialogResult = DialogResult.Yes;', consent_source)
            self.assertIn('decline.DialogResult = DialogResult.No;', consent_source)
            self.assertIn('return form.ShowDialog() == DialogResult.Yes;', consent_source)
            self.assertEqual(2, consent_source.count("VerifyPayloadEntry(zip, manifest,"))
            self.assertNotIn("VerifyPayload(zip, manifest", consent_source)
            self.assertNotIn("Directory.CreateDirectory", consent_source)
            self.assertNotIn("File.Write", consent_source)
            self.assertIn("private static ZipArchiveEntry VerifyPayloadEntry(ZipArchive zip, PayloadManifest manifest, string relative)", setup_source)
            self.assertIn('throw new InvalidDataException("Payload hash mismatch: " + relative);', setup_source)
            terms_source = (ROOT / "release" / "licenses" / "intel-2025.3-customer-terms.txt").read_text(encoding="utf-8")
            self.assertIn("7.1 Intel will not be liable", terms_source)
            self.assertIn("will not exceed $100", terms_source)
            self.assertIn("not to VNText Studio source code", terms_source)
            self.assertIn("Apache License 2.0", terms_source)
            self.assertIn('entry.FullName, "VNText Studio.exe"', setup_source)
            self.assertIn('SafeTarget(root, entry.FullName)', setup_source)
            self.assertNotIn('CreateShortcut(root)', setup_source)
            self.assertIn('LegacyShortcutName = "VNText Studio.lnk"', setup_source)
            self.assertIn('data/install-manifest.json', setup_source)
            self.assertIn('RemoveEmptyProgramDirectories(root, obsolete)', setup_source)
            self.assertIn('WriteUpdateSource(root)', setup_source)
            self.assertIn('"github_owner", githubIdentity[0]', setup_source)
            self.assertIn('"github_repository", githubIdentity[1]', setup_source)
            self.assertIn('GetManifestResourceStream(GitHubUpdateSourceResourceName)', setup_source)
            self.assertNotIn('OWNER_PREVIEW', setup_source)
            self.assertNotIn('.preview/wpf-update-current.zip', setup_source)
            self.assertIn("[string]$WpfUpdateVersion", publish_source)
            self.assertIn('[string]$GitHubOwner = ""', publish_source)
            self.assertIn('[string]$GitHubRepository = ""', publish_source)
            self.assertIn('$githubConfigJson = @{ owner = $GitHubOwner; repository = $GitHubRepository } | ConvertTo-Json -Compress', publish_source)
            self.assertIn('$setupCompileArgs += [string]::Concat("/resource:", $githubConfigResource, ",VNText.Studio.GitHubUpdateSource.json")', publish_source)
            self.assertIn('VNText.Studio.GitHubUpdateSource.json', publish_source)
            self.assertIn('GitHub stable updates: unconfigured', publish_source)
            self.assertIn("Build WPF Updates candidate $WpfUpdateVersion", publish_source)
            self.assertIn("release\\publish_owner_wpf_update.py", publish_source)
            self.assertIn("$updatesStaging", publish_source)
            self.assertIn("GetVersionInfo($wpfUpdateExe).ProductVersion", publish_source)
            self.assertIn("$wpfUpdateProductVersion -ne $WpfUpdateVersion", publish_source)
            feed_commit = publish_source.index("[System.IO.File]::Replace($pendingUpdateFeed, $currentUpdateFeed, $previousUpdateFeed)")
            setup_hash_check = publish_source.index("if ((Get-Sha256 $pendingSetup) -ne $setupSha)")
            self.assertLess(setup_hash_check, feed_commit, "Updates feed must not replace its manifest before the new Setup hash is verified.")
            self.assertIn("WPF Updates retention:", publish_source)
            uninstall_source = setup_source[setup_source.index("private static int Uninstall()"):]
            self.assertIn("BuildUninstallCleanupCommand(root", uninstall_source)
            self.assertIn("BackgroundWorker", uninstall_source)
            self.assertIn("System.Windows.Forms.Timer", uninstall_source)
            self.assertIn("UI heartbeat", uninstall_source)
            self.assertIn("Application.Run(progress)", uninstall_source)
            self.assertNotIn("ChooseUninstallMode", setup_source)
            self.assertNotIn("CreateUninstallPlan", setup_source)
            self.assertNotIn(".vntext-uninstall-plan-", setup_source)
            self.assertNotIn('Start-Sleep', uninstall_source)
            self.assertNotIn('SilentlyContinue', uninstall_source)
            self.assertNotIn("Remove-Item", uninstall_source)
            self.assertEqual(1, uninstall_source.count("MessageBoxButtons.YesNo"))
            self.assertIn("data/", uninstall_source)
            self.assertIn("thư mục cài đặt vẫn còn nhưng trống", uninstall_source)
            self.assertIn("Final uninstall cleanup failed", uninstall_source)
            worker_source = setup_source[setup_source.index("private static void RemoveUninstallContents") :]
            self.assertIn("FileShare.None", worker_source)
            self.assertIn("FileAttributes.ReparsePoint", worker_source)
            self.assertIn('phase = "blocked"', worker_source)
            self.assertIn('phase = "failed"', worker_source)

            install_root = work / "uninstall-fixture"
            (install_root / "app").mkdir(parents=True)
            (install_root / "data").mkdir()
            (install_root / "Uninstall.exe").write_bytes(b"uninstaller")
            (install_root / "VNText Studio.exe").write_bytes(b"main app")
            (install_root / "app" / ".vntext-uninstall-plan-b80d5fe4d3cb42178e81b61f848bfee2.json").write_text(
                "stale plan from earlier uninstall", encoding="utf-8"
            )
            (install_root / "data" / "user.txt").write_text("user data", encoding="utf-8")
            (install_root / "unowned-note.txt").write_text("inside the chosen install folder", encoding="utf-8")
            synthetic_dir = install_root / "app" / "synthetic"
            synthetic_dir.mkdir(parents=True)
            (install_root / "app" / "subfolder").mkdir()
            (install_root / "app" / "subfolder" / "fixture.txt").write_text("app fixture", encoding="utf-8")
            for index in range(512):
                (synthetic_dir / f"file-{index:04d}.txt").write_text("fixture", encoding="utf-8")
            owner_root = work / "install-root"
            (owner_root / "app" / "Assets" / "Fonts").mkdir(parents=True)
            (owner_root / "app" / "Assets" / "Fonts" / "LICENSE.txt").write_text("same support file", encoding="utf-8")
            (owner_root / "data").mkdir()
            expected_entries = sum(1 for entry in install_root.rglob("*") if entry != install_root / "Uninstall.exe")
            harness_source = work / "uninstall_harness.cs"
            intel_tampered = work / "intel-terms-tampered.zip"
            intel_missing = work / "intel-terms-missing.zip"
            terms_path = "app/licenses/native/intel-2025.3-customer-terms.txt"
            for destination, omit_terms, tamper_terms in (
                (intel_tampered, False, True), (intel_missing, True, False),
            ):
                with zipfile.ZipFile(archive) as original, zipfile.ZipFile(destination, "w") as altered:
                    for item in original.infolist():
                        if omit_terms and item.filename == terms_path:
                            continue
                        content = original.read(item)
                        if tamper_terms and item.filename == terms_path:
                            content += b"tampered"
                        altered.writestr(item, content)
            harness_source.write_text(r"""
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Reflection;

internal static class UninstallHarness
{
    private static void Require(bool condition, string message)
    {
        if (!condition) throw new InvalidOperationException(message);
    }

    private static void VerifyPayload(Assembly assembly, string archivePath, string root)
    {
        var type = assembly.GetType("Setup", true);
        var read = type.GetMethod("ReadManifest", BindingFlags.NonPublic | BindingFlags.Static);
        var verify = type.GetMethod("VerifyPayload", BindingFlags.NonPublic | BindingFlags.Static);
        using (var file = File.OpenRead(archivePath))
        using (var zip = new System.IO.Compression.ZipArchive(file, System.IO.Compression.ZipArchiveMode.Read))
        {
            var manifest = read.Invoke(null, new object[] { zip });
            verify.Invoke(null, new object[] { zip, manifest, root });
        }
    }

    private static bool VerifyIntelEntries(Assembly assembly, string archivePath)
    {
        var type = assembly.GetType("Setup", true);
        var read = type.GetMethod("ReadManifest", BindingFlags.NonPublic | BindingFlags.Static);
        var manifestType = assembly.GetType("PayloadManifest", true);
        var verify = type.GetMethod("VerifyPayloadEntry", BindingFlags.NonPublic | BindingFlags.Static,
            null, new[] { typeof(System.IO.Compression.ZipArchive), manifestType, typeof(string) }, null);
        try
        {
            using (var file = File.OpenRead(archivePath))
            using (var zip = new System.IO.Compression.ZipArchive(file, System.IO.Compression.ZipArchiveMode.Read))
            {
                var manifest = read.Invoke(null, new object[] { zip });
                verify.Invoke(null, new object[] { zip, manifest, "app/licenses/native/intel-2025.3-customer-terms.txt" });
                verify.Invoke(null, new object[] { zip, manifest, "app/licenses/native/intel-2025.3-cpp-eula.rtf" });
            }
            return true;
        }
        catch (TargetInvocationException) { return false; }
    }

    private static bool InvokeConsent(Assembly assembly, string buttonName)
    {
        var setup = assembly.GetType("Setup", true);
        var confirm = setup.GetMethod("ConfirmIntelTerms", BindingFlags.NonPublic | BindingFlags.Static);
        var clicked = false;
        var timer = new System.Windows.Forms.Timer { Interval = 50 };
        timer.Tick += delegate
        {
            foreach (System.Windows.Forms.Form open in System.Windows.Forms.Application.OpenForms)
            {
                if (open.Text != "Intel oneAPI Redistributable Terms") continue;
                var buttons = open.Controls.Find(buttonName, true);
                if (buttons.Length == 0) continue;
                clicked = true;
                timer.Stop();
                ((System.Windows.Forms.Button)buttons[0]).PerformClick();
                return;
            }
        };
        timer.Start();
        var result = (bool)confirm.Invoke(null, null);
        timer.Stop();
        timer.Dispose();
        Require(clicked, "Intel consent button was not exercised: " + buttonName);
        return result;
    }

    private static int InvokeDeclinedInstall(Assembly assembly)
    {
        var setup = assembly.GetType("Setup", true);
        var install = setup.GetMethod("Install", BindingFlags.NonPublic | BindingFlags.Static);
        var clicked = false;
        var timer = new System.Windows.Forms.Timer { Interval = 50 };
        timer.Tick += delegate
        {
            foreach (System.Windows.Forms.Form open in System.Windows.Forms.Application.OpenForms)
            {
                if (open.Text != "Intel oneAPI Redistributable Terms") continue;
                var buttons = open.Controls.Find("declineIntelTerms", true);
                if (buttons.Length == 0) continue;
                clicked = true;
                timer.Stop();
                ((System.Windows.Forms.Button)buttons[0]).PerformClick();
                return;
            }
        };
        System.EventHandler startTimerWhenMessagePumpIsReady = null;
        startTimerWhenMessagePumpIsReady = delegate
        {
            System.Windows.Forms.Application.Idle -= startTimerWhenMessagePumpIsReady;
            timer.Start();
        };
        System.Windows.Forms.Application.Idle += startTimerWhenMessagePumpIsReady;
        int result;
        try
        {
            result = (int)install.Invoke(null, null);
        }
        finally
        {
            System.Windows.Forms.Application.Idle -= startTimerWhenMessagePumpIsReady;
            timer.Stop();
            timer.Dispose();
        }
        Require(clicked, "Install did not present the Intel terms before opening the destination picker.");
        return result;
    }

    [STAThread]
    private static int Main(string[] args)
    {
        var assembly = Assembly.LoadFrom(args[3]);
        var setupType = assembly.GetType("Setup", true);
        var helper = setupType.GetMethod("BuildUninstallCleanupCommand", BindingFlags.NonPublic | BindingFlags.Static);
        var progressFactory = setupType.GetMethod("CreateUninstallProgressForm", BindingFlags.NonPublic | BindingFlags.Static);
        Require(helper != null && progressFactory != null, "Uninstall progress or final helper entry point was not found.");
        var fixtureRoot = Path.GetFullPath(args[0]);
        var selfPath = Path.Combine(fixtureRoot, "Uninstall.exe");
        Require(VerifyIntelEntries(assembly, args[5]), "Valid Intel terms/EULA entries were rejected.");
        Require(!VerifyIntelEntries(assembly, args[6]), "Tampered Intel terms passed hash verification.");
        Require(!VerifyIntelEntries(assembly, args[7]), "Missing Intel terms passed manifest verification.");
        var beforeDeclinedInstall = Directory.GetFileSystemEntries(fixtureRoot).Length;
        Require(InvokeDeclinedInstall(assembly) == 1, "Declined Setup did not return the non-install exit code.");
        Require(Directory.GetFileSystemEntries(fixtureRoot).Length == beforeDeclinedInstall,
            "Declined Setup wrote into the selected test root.");
        Require(InvokeConsent(assembly, "acceptIntelTerms"), "Explicit Intel acceptance did not continue.");
        Require(!InvokeConsent(assembly, "declineIntelTerms"), "Intel decline did not stop consent.");
        Console.WriteLine("Intel terms accept/decline/tamper/missing/no-write checks PASS");
        var generated = (string)helper.Invoke(null, new object[] { fixtureRoot, 2147483647, selfPath });
        Require(generated.Contains("WaitForExit"), "Final helper does not wait for the uninstaller process.");
        Require(generated.Contains("[IO.File]::Delete($selfPath)") && generated.Contains("[IO.Directory]::GetFileSystemEntries($root).Length -ne 0"), "Final helper does not delete Uninstall.exe and verify the empty install folder.");
        Require(!generated.Contains("[IO.Directory]::Delete($root"), "Final helper deletes the install root.");
        Require(generated.Contains("GetPathRoot") && generated.Contains("ReparsePoint") && generated.Contains("Unexpected item appeared during final cleanup"), "Final helper lost its drive-root, reparse-point or exact-path guard.");
        Require(generated.Contains("Final uninstall cleanup failed") && generated.Contains("exit 1") && generated.Contains("exit 0"), "Final helper does not report failure with a nonzero exit code.");
        Require(!generated.Contains("Remove-Item") && !generated.Contains("Stop-Process"), "Final helper recurses or force-stops a process.");
        Require(!generated.Contains(".vntext-uninstall-plan-"), "Uninstall still creates a temporary plan file.");
        var parentStillRunning = true;
        try { Process.GetProcessById(2147483647).Dispose(); }
        catch (ArgumentException) { parentStillRunning = false; }
        Require(!parentStillRunning, "Final helper test requires a parent PID sentinel that is absent.");
        File.WriteAllText(args[1], generated, System.Text.Encoding.Unicode);

        var evidence = new List<Dictionary<string, object>>();
        var form = (System.Windows.Forms.Form)progressFactory.Invoke(null,
            new object[] { fixtureRoot, selfPath, 2147483647, false, evidence });
        form.Opacity = 0;
        form.ShowInTaskbar = false;
        var watchdogState = "waiting for progress form to complete";
        var watchdog = new System.Threading.Timer(delegate
        {
            Console.WriteLine("WATCHDOG: " + watchdogState);
            Console.Out.Flush();
            Environment.Exit(124);
        }, null, 10000, System.Threading.Timeout.Infinite);
        var details = (System.Windows.Forms.TextBox)form.Controls.Find("uninstallDetails", true)[0];
        var heartbeatControl = (System.Windows.Forms.Label)form.Controls.Find("uninstallHeartbeat", true)[0];
        var detailsText = details.Text;
        var heartbeatText = heartbeatControl.Text;
        form.FormClosing += delegate
        {
            detailsText = details.Text;
            heartbeatText = heartbeatControl.Text;
        };
        System.Windows.Forms.Application.Run(form);
        watchdog.Dispose();
        Require(Convert.ToInt32(form.Tag) == 0, "Fixture uninstall progress flow did not complete: " + detailsText);
        Console.WriteLine("UI_HEARTBEAT:" + heartbeatText);
        foreach (var update in evidence)
            Console.WriteLine("PROGRESS:" + new System.Web.Script.Serialization.JavaScriptSerializer().Serialize(update));
        Require(File.Exists(selfPath), "Progress worker removed its own running executable.");
        Require(!File.Exists(Path.Combine(fixtureRoot, "data", "user.txt")), "Progress worker preserved install data.");
        Require(Directory.Exists(fixtureRoot), "Progress worker removed the root before the handoff helper.");
        Console.WriteLine("uninstall progress form and descendant cleanup PASS");
        var setupAssembly = Assembly.LoadFrom(args[3]);
        var ownerRoot = Path.GetFullPath(args[4]);
        VerifyPayload(setupAssembly, args[5], ownerRoot);
        var setup = setupAssembly.GetType("Setup", true);
        setup.GetMethod("WriteUpdateSource", BindingFlags.NonPublic | BindingFlags.Static).Invoke(null, new object[] { ownerRoot });
        setup.GetMethod("WriteInstallManifest", BindingFlags.NonPublic | BindingFlags.Static).Invoke(null,
            new object[] { Path.Combine(ownerRoot, "data", "install-manifest.json"), new List<string> { ".vntext-update-source.json" } });
        Console.WriteLine("Setup payload and local Updates source PASS");
        return 0;
    }
}
""", encoding="utf-8")
            harness = work / "uninstall_harness.exe"
            helper_script = work / "uninstall_helper.ps1"
            built_harness = subprocess.run([str(csc), "/nologo", "/target:exe", f"/out:{harness}", "/reference:System.Windows.Forms.dll", "/reference:System.Web.Extensions.dll", "/reference:System.IO.Compression.dll", str(harness_source)], capture_output=True, text=True, timeout=90)
            self.assertEqual(0, built_harness.returncode, built_harness.stdout + built_harness.stderr)
            try:
                exercised = subprocess.run([str(harness), str(install_root), str(helper_script), str(uninstaller), str(setup_exe), str(owner_root), str(archive), str(intel_tampered), str(intel_missing)], capture_output=True, text=True, timeout=30)
            except subprocess.TimeoutExpired as error:
                self.fail(f"Uninstall fixture exceeded its watchdog timeout; stdout={error.stdout!r}; stderr={error.stderr!r}")
            self.assertEqual(0, exercised.returncode, exercised.stdout + exercised.stderr)
            self.assertIn("uninstall progress form and descendant cleanup PASS", exercised.stdout)
            self.assertIn("Intel terms accept/decline/tamper/missing/no-write checks PASS", exercised.stdout)
            self.assertIn("Setup payload and local Updates source PASS", exercised.stdout)
            installed_update_source = json.loads((owner_root / ".vntext-update-source.json").read_text(encoding="utf-8"))
            self.assertEqual("", installed_update_source["github_owner"])
            self.assertEqual("", installed_update_source["github_repository"])
            heartbeat = re.search(r"UI_HEARTBEAT:UI heartbeat: (\d+); max delay: (\d+) ms", exercised.stdout)
            self.assertIsNotNone(heartbeat, exercised.stdout)
            self.assertGreaterEqual(int(heartbeat.group(1)), 2, exercised.stdout)
            self.assertLess(int(heartbeat.group(2)), 5000, exercised.stdout)
            print("UI_HEARTBEAT_EVIDENCE:" + heartbeat.group(0))
            progress = [json.loads(line.removeprefix("PROGRESS:")) for line in exercised.stdout.splitlines() if line.startswith("PROGRESS:")]
            phases = {item["phase"] for item in progress}
            self.assertTrue({"scanning", "checking", "deleting", "handoff"}.issubset(phases), progress)
            scanning = [item for item in progress if item["phase"] == "scanning"]
            self.assertTrue(scanning, progress)
            self.assertEqual(expected_entries + 1, scanning[-1]["done"])
            self.assertLess(len(scanning), expected_entries, "Scan progress was not coalesced.")
            for phase in ("scanning", "checking", "deleting"):
                elapsed = [item["elapsedMilliseconds"] for item in progress if item["phase"] == phase]
                self.assertTrue(elapsed and elapsed == sorted(elapsed), f"Missing or regressing {phase} timing: {progress}")
                print(f"PHASE_TIMING:{phase}:{elapsed[-1]} ms")

            # Explicit Owner-approved test input only; publisher defaults remain unconfigured.
            github_owner = "Calanh24"
            github_repository = "VnText"
            github_config = work / "github-config.json"
            github_config.write_text(json.dumps({"owner": github_owner, "repository": github_repository}), encoding="utf-8")
            configured_setup = work / "Setup-configured.exe"
            configured_resource = f"/resource:{github_config},VNText.Studio.GitHubUpdateSource.json"
            configured_build = subprocess.run(
                [str(csc), "/nologo", "/target:winexe", f"/out:{configured_setup}", f"/resource:{archive},Payload.zip", configured_resource, *references, str(source), str(attributes)],
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(0, configured_build.returncode, configured_build.stdout + configured_build.stderr)
            identity_harness_source = work / "github_identity_harness.cs"
            identity_harness_source.write_text(r"""
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Web.Script.Serialization;

internal static class GitHubIdentityHarness
{
    private static int Main(string[] args)
    {
        var assembly = Assembly.LoadFrom(args[0]);
        var setup = assembly.GetType("Setup", true);
        setup.GetMethod("WriteUpdateSource", BindingFlags.NonPublic | BindingFlags.Static).Invoke(null, new object[] { args[1] });
        var values = new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(File.ReadAllText(Path.Combine(args[1], ".vntext-update-source.json")));
        if (!String.Equals(Convert.ToString(values["github_owner"]), args[2], StringComparison.Ordinal) ||
            !String.Equals(Convert.ToString(values["github_repository"]), args[3], StringComparison.Ordinal)) return 1;
        Console.WriteLine("explicit GitHub identity embedded in Setup and installed source PASS");
        return 0;
    }
}
""", encoding="utf-8")
            identity_harness = work / "github_identity_harness.exe"
            built_identity_harness = subprocess.run(
                [str(csc), "/nologo", "/target:exe", f"/out:{identity_harness}", "/reference:System.Web.Extensions.dll", str(identity_harness_source)],
                capture_output=True,
                text=True,
                timeout=90,
            )
            self.assertEqual(0, built_identity_harness.returncode, built_identity_harness.stdout + built_identity_harness.stderr)
            configured_root = work / "configured-install-root"
            configured_root.mkdir()
            configured_identity = subprocess.run(
                [str(identity_harness), str(configured_setup), str(configured_root), github_owner, github_repository],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(0, configured_identity.returncode, configured_identity.stdout + configured_identity.stderr)
            self.assertIn("explicit GitHub identity embedded in Setup and installed source PASS", configured_identity.stdout)
            for phase in ("checking", "deleting"):
                self.assertEqual(expected_entries, next(item["total"] for item in progress if item["phase"] == phase))
                self.assertLess(sum(1 for item in progress if item["phase"] == phase), expected_entries, f"{phase} progress was not coalesced.")
            self.assertTrue(install_root.is_dir(), "Fixture worker removed the install root before handoff.")
            self.assertEqual([install_root / "Uninstall.exe"], list(install_root.iterdir()), "Fixture worker did not remove all descendants, including data.")
            powershell = Path(os.environ["WINDIR"]) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            helper_command = helper_script.read_text(encoding="utf-16")
            encoded_helper = base64.b64encode(helper_command.encode("utf-16le")).decode("ascii")
            finalized = subprocess.run(
                [str(powershell), "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_helper],
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(0, finalized.returncode, finalized.stdout + finalized.stderr)
            self.assertFalse((install_root / "Uninstall.exe").exists(), "Final helper kept Uninstall.exe.")
            for relative in (
                "VNText Studio.exe",
                "app",
                "app/synthetic",
                "app/subfolder/fixture.txt",
                "data",
                "data/user.txt",
                "unowned-note.txt",
            ):
                self.assertFalse((install_root / relative).exists(), f"Final helper kept install content: {relative}")
            root_stat = install_root.stat(follow_symlinks=False)
            self.assertTrue(stat.S_ISDIR(root_stat.st_mode), "Final helper removed or replaced the install root.")
            self.assertEqual(0, getattr(root_stat, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400), "Install root became a reparse point.")
            self.assertEqual([], list(install_root.iterdir()), "Final helper did not leave an empty install root.")
            update_source = json.loads((owner_root / ".vntext-update-source.json").read_text(encoding="utf-8"))
            updates_root = work / "Updates"
            self.assertEqual(str(updates_root), update_source["updates_root"])
            self.assertEqual([".vntext-update-source.json"], json.loads((owner_root / "data" / "install-manifest.json").read_text(encoding="utf-8")))

            installed_exe = owner_root / "VNText Studio.exe"
            installed_exe.write_bytes(b"installed A")
            version = "1.44.9-dev"
            (owner_root / "app" / "VERSION.txt").write_text(version + "\n", encoding="utf-8")
            (owner_root / "app" / "RELEASE.json").write_text(json.dumps({"version": version, "sha256": hashlib.sha256(installed_exe.read_bytes()).hexdigest()}), encoding="utf-8")
            candidate = work / "wpf-output"
            (candidate / "Assets" / "Fonts").mkdir(parents=True)
            (candidate / "VNText.Studio.App.exe").write_bytes(b"installed B")
            (candidate / "Assets" / "Fonts" / "LICENSE.txt").write_text("same support file", encoding="utf-8")
            source_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
            result = publish_owner_wpf_update.publish(candidate, owner_root, updates_root, "1.44.10-dev", source_sha, notes="WPF internal")
            self.assertEqual(version, result["current_version"])
            self.assertEqual(["app/Assets/Fonts/LICENSE.txt"], [item["path"] for item in result["unchanged_support_files"]])
            package_path = Path(result["package_path"])
            self.assertEqual(result["package_sha256"], hashlib.sha256(package_path.read_bytes()).hexdigest())
            feed_path = updates_root / publish_owner_wpf_update.FEED_NAME
            previous_feed = feed_path.read_bytes()
            published_feed = json.loads(previous_feed)
            self.assertEqual(package_path.name, published_feed["package_file"])
            self.assertEqual(result["package_sha256"], published_feed["package_sha256"])
            with zipfile.ZipFile(package_path) as package:
                self.assertEqual({"wpf-update-manifest.json", *publish_owner_wpf_update.ALLOWLIST}, set(package.namelist()))
                update_manifest = json.loads(package.read("wpf-update-manifest.json"))
                self.assertEqual("1.44.10-dev", update_manifest["version"])
                self.assertEqual(source_sha, update_manifest["source_sha"])
                self.assertEqual(hashlib.sha256(b"installed A").hexdigest(), update_manifest["base_files"]["VNText Studio.exe"]["sha256"])
            previous_package_hash = result["package_sha256"]
            (candidate / "Assets" / "Fonts" / "LICENSE.txt").write_text("changed support file", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "outside the updater allowlist"):
                publish_owner_wpf_update.publish(candidate, owner_root, updates_root, "1.44.11-dev", source_sha)
            self.assertEqual(previous_package_hash, hashlib.sha256(package_path.read_bytes()).hexdigest())
            self.assertEqual(previous_feed, feed_path.read_bytes())
            (candidate / "Assets" / "Fonts" / "LICENSE.txt").write_text("same support file", encoding="utf-8")
            with self.assertRaises(ValueError):
                publish_owner_wpf_update.publish(candidate, owner_root, updates_root, version, source_sha)
            self.assertEqual(previous_package_hash, hashlib.sha256(package_path.read_bytes()).hexdigest())
            self.assertEqual(previous_feed, feed_path.read_bytes())
            (candidate / "Assets" / "Fonts" / "LICENSE.txt").write_text("same support file", encoding="utf-8")
            (candidate / "VNText.Studio.App.exe").write_bytes(b"installed C")
            newer = publish_owner_wpf_update.publish(candidate, owner_root, updates_root, "1.44.11-dev", source_sha)
            self.assertNotEqual(package_path.name, Path(newer["package_path"]).name)
            self.assertTrue(package_path.is_file(), "Superseded WPF package was deleted.")
            self.assertEqual(2, newer["retained_package_count"])
            outcome = "PASS"
        finally:
            report = cleanup_after_test([work], reason="test_setup_package.py", outcome=outcome, scope_id=scope, run_id=run_id)
        if outcome == "PASS":
            self.assertTrue(report.get("ok"), report)


if __name__ == "__main__":
    unittest.main()
