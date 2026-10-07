"""WPF workflow + path picker tests (console harness, no NuGet)."""

from __future__ import annotations

import sys
from pathlib import Path

def _tests_lib_on_path() -> None:
    cur = Path(__file__).resolve().parent
    while cur.name != "tests" and cur.parent != cur:
        cur = cur.parent
    lib = cur / "lib"
    p = str(lib)
    if p not in sys.path:
        sys.path.insert(0, p)
    tools = cur / "tools"
    p = str(tools)
    if p not in sys.path:
        sys.path.insert(0, p)

_tests_lib_on_path()
from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)

import subprocess
import os
import unittest
from pathlib import Path
from uuid import uuid4

from cleanup_work_artifacts import cleanup_after_test
from work_paths import ambient_scope, new_scope_id, register_artifacts

DEV_RUN_ROOT = Path(os.environ.get("VNTEXT_DEV_RUN_ROOT", str(ROOT / "DEV_RUN"))).expanduser()
DOTNET = Path(os.environ.get("VNTEXT_DOTNET", str(ROOT / ".dev-env" / "dotnet-sdk-10" / "dotnet.exe")))
WORKFLOW_PROJECT = ROOT / "wpf_app" / "VNText.Studio.Workflow.Tests"
DOTNET_LAYOUT_VERSION = "8.0.30"
APPHOST_PACK_VERSION = os.environ.get("VNTEXT_APPHOST_PACK_VERSION", "10.0.12")


def _harness_env(work_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("VNTEXT_WORKER_CWD", str(ROOT))
    # The publish regression runner may itself be the portable Release venv.
    # Pass that exact interpreter through the dev/test seam so the WPF harness
    # never falls back to a stale system Python path.
    env["VNTEXT_WORKER_PYTHON"] = sys.executable
    runtime = work_root / "runtime"
    appdata = runtime / "appdata"
    localappdata = runtime / "localappdata"
    dotnet_home = runtime / "dotnet"
    temp = runtime / "temp"
    nuget_packages = ROOT / ".dev-env" / "cache" / "nuget"
    nuget_http_cache = runtime / "nuget-http-cache"
    cache = runtime / "cache"
    nuget_packages.mkdir(parents=True, exist_ok=True)
    env["APPDATA"] = str(appdata)
    env["LOCALAPPDATA"] = str(localappdata)
    env["DOTNET_CLI_HOME"] = str(dotnet_home)
    env["DOTNET_ROOT"] = str(DOTNET.parent)
    env["DOTNET_SKIP_FIRST_TIME_EXPERIENCE"] = "1"
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    env["DOTNET_MULTILEVEL_LOOKUP"] = "0"
    env["NUGET_PACKAGES"] = str(nuget_packages)
    env["NUGET_HTTP_CACHE_PATH"] = str(nuget_http_cache)
    env["TEMP"] = env["TMP"] = env["TMPDIR"] = str(temp)
    env["HF_HOME"] = str(cache / "huggingface")
    env["HF_HUB_CACHE"] = str(cache / "huggingface" / "hub")
    env["TRANSFORMERS_CACHE"] = str(cache / "huggingface" / "transformers")
    env["TORCH_HOME"] = str(cache / "torch")
    env["VNTEXT_DIRECT_GPU_ROOT"] = str(cache / "gpu")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["VNTEXT_LOCALAPPDATA"] = str(localappdata)
    env["VNTEXT_WPF_TEST_WORK_ROOT"] = str(work_root)
    for name in ("VNTEXT_WPF_BASELINE_EXE", "VNTEXT_WPF_CANDIDATE_EXE"):
        if os.environ.get(name):
            env[name] = os.environ[name]
        else:
            env.pop(name, None)
    return env


def _run_harness(env: dict[str, str], artifacts_root: Path) -> subprocess.CompletedProcess[str]:
    apphost = artifacts_root / "bin" / "VNText.Studio.Workflow.Tests" / "release" / "VNText.Studio.Workflow.Tests.exe"
    if not apphost.is_file():
        raise AssertionError(f"workflow harness apphost missing: {apphost}")
    runtime_env = env.copy()
    runtime_env["DOTNET_ROOT"] = str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "dotnet")
    return subprocess.run(
        [str(apphost)],
        cwd=str(ROOT),
        env=runtime_env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _build_versioned_exe_fixture(
    project_root: Path,
    artifacts_root: Path,
    version: str,
    nuget_config: Path,
    layout_targets: Path,
) -> Path:
    project = project_root / "UpdateVersionFixture.csproj"
    project.write_text(
        "<Project Sdk=\"Microsoft.NET.Sdk\"><PropertyGroup>"
        "<OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework>"
        f"<Version>{version}</Version><InformationalVersion>{version}</InformationalVersion>"
        f"<AssemblyVersion>{version}.0</AssemblyVersion><FileVersion>{version}.0</FileVersion>"
        "<IncludeSourceRevisionInInformationalVersion>false</IncludeSourceRevisionInInformationalVersion>"
        "</PropertyGroup></Project>\n",
        encoding="utf-8",
    )
    (project_root / "Program.cs").write_text(
        "internal static class Program { private static int Main() => 0; }\n",
        encoding="utf-8",
    )
    build = subprocess.run(
        [
            str(DOTNET),
            "build",
            str(project),
            "-c",
            "Release",
            "--artifacts-path",
            str(artifacts_root),
            "-p:RestoreConfigFile=" + str(nuget_config),
            "-p:DirectoryBuildTargetsPath=" + str(layout_targets),
            "-p:RestorePackagesPath=" + str(ROOT / ".dev-env" / "cache" / "nuget"),
            "-p:NuGetAudit=false",
        ],
        cwd=str(ROOT),
        env=_harness_env(project_root),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if build.returncode:
        raise AssertionError(build.stdout + build.stderr)
    executable = artifacts_root / "bin" / "UpdateVersionFixture" / "release" / "UpdateVersionFixture.exe"
    if not executable.is_file():
        raise AssertionError(f"versioned updater test fixture missing: {executable}")
    return executable


class WpfWorkflowTests(unittest.TestCase):
    def test_workflow_options_are_not_duplicated(self):
        xaml = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").read_text(encoding="utf-8")
        glossary_probe = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "BulkGlossaryUiProbe.cs").read_text(encoding="utf-8")
        for option in (
            'Content="Tách dòng cần duyệt"',
            'Content="Ghi đè bản dịch cũ"',
            'Content="Bắt buộc duyệt thủ công kết quả MT"',
        ):
            with self.subTest(option=option):
                self.assertEqual(xaml.count(option), 1)
        self.assertIn('x:Name="GlossaryOverlay"', xaml)
        self.assertIn('Click="GlossaryEditButton_Click"', xaml)
        self.assertIn('PreviewKeyDown="GlossaryOverlay_PreviewKeyDown"', xaml)
        self.assertIn('FindName("GlossaryEditButton")', glossary_probe)
        self.assertIn("overlay?.Visibility == Visibility.Visible", glossary_probe)

    def test_renpy_tool_options_are_conditional_and_explain_partial_extraction(self):
        xaml = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").read_text(encoding="utf-8")
        view_model = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.cs").read_text(encoding="utf-8")
        worker = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Worker.cs").read_text(encoding="utf-8")
        self.assertIn('Visibility="{Binding RenpySdkOptionsVisible, Converter={StaticResource BoolToVis}}"', xaml)
        self.assertIn("RenpyGameDetector.IsLooseSourceGame", view_model)
        self.assertIn("Lấy text chưa đầy đủ do thiếu công cụ Ren'Py", worker)
        self.assertIn("Tải công cụ rồi lấy text", xaml)
        self.assertIn("Tiếp tục, lời thoại cần xem lại", xaml)

    def test_workflow_probe_only_accepts_ct2_and_uses_the_selected_local_model(self):
        app = (ROOT / "wpf_app" / "VNText.Studio.App" / "App.xaml.cs").read_text(encoding="utf-8")
        probe = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "WpfWorkflowE2eProbe.cs").read_text(encoding="utf-8")
        workflow = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Workflow.cs").read_text(encoding="utf-8")
        view_model = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.cs").read_text(encoding="utf-8")
        settings = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "AppSettingsStore.cs").read_text(encoding="utf-8")
        xaml = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").read_text(encoding="utf-8")
        self.assertIn('"--translation-model"', app)
        self.assertIn('"--model-dir"', app)
        self.assertIn('"--model-revision"', app)
        self.assertIn("MODEL_SELECTION_WIRING_FAILURE", probe)
        self.assertNotIn("vinai", probe.lower())
        self.assertIn('"model_metadata"', probe)
        self.assertIn('"actual_model_id"', probe)
        self.assertIn('"actual_model_engine"', probe)
        self.assertIn('"actual_model_dir"', probe)
        self.assertIn('if (model != "ct2")', probe)
        self.assertIn('model = "ct2"', workflow)
        self.assertIn('model = "ct2"', (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.CsvEditor.cs").read_text(encoding="utf-8"))
        self.assertIn("human_review_required = HumanReviewRequired", workflow)
        self.assertIn("human_review_required = HumanReviewRequired", (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.CsvEditor.cs").read_text(encoding="utf-8"))
        self.assertIn("public bool HumanReviewRequired", view_model)
        self.assertIn("public bool HumanReviewRequired", settings)
        self.assertIn("Bắt buộc duyệt thủ công kết quả MT", xaml)
        self.assertIn("Gợi ý của model chỉ vào review_only.csv; chưa thể Patch cho đến khi duyệt.", xaml)

    def test_cloud_repair_controls_route_and_preserve_active_csv_on_failure(self):
        view_model = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.cs").read_text(encoding="utf-8")
        workflow = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Workflow.cs").read_text(encoding="utf-8")
        worker = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Worker.cs").read_text(encoding="utf-8")
        paths = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Paths.cs").read_text(encoding="utf-8")
        xaml = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").read_text(encoding="utf-8")
        task_runners = (ROOT / "vntext_worker" / "task_runners.py").read_text(encoding="utf-8")

        self.assertIn("ExportCloudRepairPackageCommand", view_model)
        self.assertNotIn("ImportCloudRepairResultCommand", view_model)
        self.assertIn("ImportExistingTranslationCommand", view_model)
        self.assertIn('cloud_action = "export"', workflow)
        self.assertIn('cloud_action = "import"', workflow)
        self.assertIn('cloud_action = "external_import"', workflow)
        self.assertIn('workerTask: "patch"', workflow)
        self.assertIn("_pendingCloudRepairImportOutputPath", worker)
        self.assertIn("TryActivateCloudRepairImport", worker)
        self.assertIn("_pendingExternalTranslationImportTargetPath", worker)
        self.assertIn("TryActivateExternalTranslationImport", worker)
        self.assertIn("translation.cloud_repair.csv", workflow)
        self.assertIn("BeginCloudRepairImport(path)", paths)
        self.assertIn("SelectedTab == WorkflowTabs.Patch", paths)
        self.assertIn("PickCloudRepairPackagePath", paths)
        self.assertNotIn("candidateDir", paths)
        self.assertIn("Dịch bằng công cụ bên ngoài", xaml)
        self.assertIn("Dùng lại bản dịch cũ", xaml)
        self.assertIn('Command="{Binding ExportCloudRepairPackageCommand}"', xaml)
        self.assertNotIn('Command="{Binding ImportCloudRepairResultCommand}"', xaml)
        self.assertIn('Command="{Binding ImportExistingTranslationCommand}"', xaml)
        self.assertIn('cloud_action in {"export", "import", "external_import"}', task_runners)
        self.assertIn("run_cloud_repair_import_task", task_runners)
        self.assertIn("run_external_translation_import_task", task_runners)

        translate_page = xaml[xaml.index('x:Name="TranslatePage"'):xaml.index('<!-- Patch page -->')]
        patch_page = xaml[xaml.index('<!-- Patch page -->'):]
        self.assertIn('Content="Xuất ZIP"', translate_page)
        self.assertNotIn("Nhập kết quả", translate_page)
        self.assertIn('Text="Nếu vừa xuất ZIP để dịch bên ngoài, CSV trả về sẽ được kiểm tra với gói đó trước khi tạo patch."', patch_page)
        self.assertIn('Command="{Binding ChooseTranslationCsvCommand}"', patch_page)

        cloud_title = xaml.index('Text="Dịch bằng công cụ bên ngoài"')
        rows_start = xaml.rfind("<Grid.RowDefinitions>", 0, cloud_title)
        rows_end = xaml.index("</Grid.RowDefinitions>", rows_start)
        self.assertEqual(4, xaml[rows_start:rows_end].count("<RowDefinition"))
        legacy_section = xaml.index('Text="Dùng lại bản dịch cũ"', rows_end)
        self.assertIn('<Border Grid.Row="3"', xaml[rows_end:legacy_section])

    def test_wpf_internal_update_controls_are_available_and_rechecked(self):
        xaml = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").read_text(encoding="utf-8")
        view_model = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.cs").read_text(encoding="utf-8")
        updater = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "WpfUpdateService.cs").read_text(encoding="utf-8")
        self.assertIn('Text="Phiên bản hiện tại"', xaml)
        self.assertIn('Text="Phiên bản mới"', xaml)
        self.assertIn('Command="{Binding RecheckUpdateCommand}"', xaml)
        self.assertIn('Text="{Binding GitHubUpdateStatus}"', xaml)
        self.assertIn('Content="{Binding GitHubUpdateButtonText}"', xaml)
        self.assertIn('IsEnabled="{Binding GitHubUpdateButtonEnabled}"', xaml)
        self.assertNotIn('Local Updates preview', xaml)
        self.assertNotIn('Apply local preview', xaml)
        self.assertNotIn('Stable public releases (GitHub)', xaml)
        self.assertIn('<StackPanel Grid.Row="3"', xaml)
        self.assertNotIn('Background="{StaticResource SubtlePanelBrush}"', xaml[xaml.index('<StackPanel Grid.Row="3"'):xaml.index('<!-- Main content -->')])
        self.assertNotIn('BorderBrush="{StaticResource LineBrush}" BorderThickness="1" CornerRadius="12"', xaml[xaml.index('<StackPanel Grid.Row="3"'):xaml.index('<!-- Main content -->')])
        self.assertIn('Style="{StaticResource SidebarUpdateButton}"', xaml)
        self.assertIn('Source="Assets/vntext_studio_logo_128.png"', xaml)
        self.assertNotIn('BrandMarkGeometry', xaml)
        self.assertNotIn('BrandDarkBrush}" StrokeThickness', xaml[xaml.index('<StackPanel Grid.Row="0"'):xaml.index('<StackPanel Grid.Row="1"')])
        self.assertNotIn('Background="{StaticResource BrandDarkBrush}"', xaml[xaml.index('<StackPanel Grid.Row="0"'):xaml.index('<StackPanel Grid.Row="1"')])
        self.assertNotIn("áp dụng bản cập nhật thử nghiệm", view_model)
        self.assertIn("public bool GitHubUpdateChecking", view_model)
        self.assertIn("public string GitHubUpdateButtonText", view_model)
        self.assertIn("HandleUpdateAction", view_model)
        self.assertIn("WpfUpdateService.CheckGitHubUpdateAsync", view_model)
        self.assertIn("WpfUpdateService.TryGetAvailableUpdateVersion", view_model)
        self.assertIn("ReadAndValidatePackage(root, source)", updater)
        self.assertIn("IsStrictlyNewerVersion(baselineVersion, manifest.Version)", updater)
        self.assertIn('FeedManifestName = "wpf-update-current.json"', updater)
        self.assertIn('JsonPropertyName("updates_root")', updater)

    def test_release_worker_managed_paths_are_install_root_relative(self):
        paths = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "WorkerPaths.cs").read_text(encoding="utf-8")
        settings = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "AppSettingsStore.cs").read_text(encoding="utf-8")
        worker = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "PythonWorkerHost.cs").read_text(encoding="utf-8")
        vm = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.cs").read_text(encoding="utf-8")
        self.assertIn('Path.Combine(installRoot, "data")', paths)
        self.assertIn('Path.Combine(start, "app")', paths)
        self.assertIn('Path.Combine(installRoot, MainExeName)', paths)
        self.assertIn('Directory.GetParent(appRoot)?.FullName ?? appRoot', paths)
        self.assertIn('Path.Combine(AppDataRoot(), "work")', paths)
        self.assertIn('Environment.GetEnvironmentVariable("VNTEXT_WORK_ARTIFACTS_ROOT")', paths)
        self.assertIn("WorkerPaths.AppDataRoot()", settings)
        self.assertIn("WorkerPaths.ConfigureReleaseEnvironment(psi.Environment)", worker)
        self.assertIn('environment["TEMP"] = environment["TMP"] = environment["TMPDIR"] = temp', paths)
        self.assertIn('environment["LOCALAPPDATA"] = environment["APPDATA"] = data', paths)
        self.assertIn("WorkerPaths.ConfigureReleaseEnvironment(psi.Environment)", (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "ReleaseVerifyRunner.cs").read_text(encoding="utf-8"))
        self.assertIn('Path.Combine(WorkerPaths.AppDataRoot(), "output")', vm)
        self.assertIn("ReleaseManagedPaths_StayUnderInstallRoot", (ROOT / "wpf_app" / "VNText.Studio.Workflow.Tests" / "Program.cs").read_text(encoding="utf-8"))

    def test_wpf_workflow_harness_passes(self):
        if not DOTNET.is_file():
            self.skipTest(f".NET SDK 10 is not installed at {DOTNET}")
        owned_root = ROOT / "TEST_RUN" / f"wpf_workflow_{uuid4().hex}"
        ambient = ambient_scope()
        scope_id = ambient["scope_id"]
        run_id = ambient["run_id"]
        scope_root = Path(ambient["scope_root"]).resolve()
        if scope_id == "legacy":
            scope_id = run_id = new_scope_id("wpf-workflow")
        harness_env = _harness_env(owned_root)
        artifacts_root = owned_root / "dotnet-artifacts"
        nuget_config = owned_root / "NuGet.Config"
        layout_targets = owned_root / "dotnet-layout.targets"
        runtime = owned_root / "runtime"
        owned_roots = (
            (owned_root, "test_workspace", "temporary WPF workflow harness outputs"),
            (artifacts_root, "build_output", "offline WPF workflow harness build outputs"),
            (runtime, "runtime_scope", "registered WPF harness runtime parent"),
            (runtime / "appdata", "profile_cache", "WPF harness APPDATA"),
            (runtime / "localappdata", "profile_cache", "WPF harness LOCALAPPDATA"),
            (runtime / "dotnet", "tool_cache", "WPF harness .NET CLI home"),
            (runtime / "temp", "temporary", "WPF harness TEMP and TMP"),
            (runtime / "nuget-http-cache", "dependency_cache", "offline NuGet HTTP cache"),
            (runtime / "cache", "model_cache", "WPF harness model and GPU cache roots"),
            (nuget_config, "build_configuration", "offline NuGet source configuration"),
            (layout_targets, "build_configuration", "local installed .NET pack version pins"),
        )
        registrations = register_artifacts([
            {
                "artifact_id": f"wpf-workflow:{owned_root.name}:{index}",
                "path": path,
                "kind": kind,
                "created_by": "test_wpf_workflow.py",
                "owner": "test_wpf_workflow.py",
                "purpose": purpose,
                "lifecycle": "DISPOSABLE",
                "scope_id": scope_id,
                "run_id": run_id,
                "scope_root": scope_root,
            }
            for index, (path, kind, purpose) in enumerate(owned_roots)
        ])
        self.assertTrue(
            all(
                record["scope_id"] == scope_id
                and record["run_id"] == run_id
                and Path(record["scope_root"]) == scope_root
                for record in registrations
            ),
            "WPF artifact registrations must use the active cleanup scope",
        )
        owned_root.mkdir(parents=True, exist_ok=True)
        for path, kind, _ in owned_roots[1:]:
            if kind != "build_configuration":
                path.mkdir(parents=True, exist_ok=True)
        outcome = "FAIL"
        cleanup_report = None
        try:
            nuget_config.write_text(
                '<?xml version="1.0" encoding="utf-8"?><configuration><packageSources><clear /><add key="nuget.org" value="https://api.nuget.org/v3/index.json" protocolVersion="3" /></packageSources></configuration>\n',
                encoding="utf-8",
            )
            layout_targets.write_text(
                "<Project><ItemGroup>"
                f'<KnownFrameworkReference Update="Microsoft.NETCore.App" TargetingPackVersion="{DOTNET_LAYOUT_VERSION}" LatestRuntimeFrameworkVersion="{DOTNET_LAYOUT_VERSION}" />'
                f'<KnownFrameworkReference Update="Microsoft.AspNetCore.App" TargetingPackVersion="{DOTNET_LAYOUT_VERSION}" LatestRuntimeFrameworkVersion="{DOTNET_LAYOUT_VERSION}" />'
                f'<KnownFrameworkReference Update="Microsoft.WindowsDesktop.App" TargetingPackVersion="{DOTNET_LAYOUT_VERSION}" LatestRuntimeFrameworkVersion="{DOTNET_LAYOUT_VERSION}" />'
                f'<KnownFrameworkReference Update="Microsoft.WindowsDesktop.App.WPF" TargetingPackVersion="{DOTNET_LAYOUT_VERSION}" LatestRuntimeFrameworkVersion="{DOTNET_LAYOUT_VERSION}" />'
                f'<KnownFrameworkReference Update="Microsoft.WindowsDesktop.App.WindowsForms" TargetingPackVersion="{DOTNET_LAYOUT_VERSION}" LatestRuntimeFrameworkVersion="{DOTNET_LAYOUT_VERSION}" />'
                f'<KnownAppHostPack Update="Microsoft.NETCore.App" AppHostPackVersion="{APPHOST_PACK_VERSION}" />'
                "</ItemGroup></Project>\n",
                encoding="utf-8",
            )
            harness_env["NUGET_CONFIG_FILE"] = str(nuget_config)
            build = subprocess.run(
                [
                    str(DOTNET),
                    "build",
                    str(WORKFLOW_PROJECT),
                    "-c",
                    "Release",
                    "--artifacts-path",
                    str(artifacts_root),
                    "-p:RestoreConfigFile=" + str(nuget_config),
                    "-p:DirectoryBuildTargetsPath=" + str(layout_targets),
                    "-p:RestorePackagesPath=" + str(ROOT / ".dev-env" / "cache" / "nuget"),
                    "-p:NuGetAudit=false",
                    "-p:RestoreIgnoreFailedSources=true",
                    f"-p:TargetingPackVersion={DOTNET_LAYOUT_VERSION}",
                    f"-p:LatestRuntimeFrameworkVersion={DOTNET_LAYOUT_VERSION}",
                    f"-p:AppHostPackVersion={DOTNET_LAYOUT_VERSION}",
                ],
                cwd=str(ROOT),
                env=harness_env,
                capture_output=True,
                text=True,
                timeout=180,
            )
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            if not all(os.environ.get(name) for name in ("VNTEXT_WPF_BASELINE_EXE", "VNTEXT_WPF_CANDIDATE_EXE")):
                baseline_root = owned_root / "update-version-fixtures" / "baseline"
                candidate_root = owned_root / "update-version-fixtures" / "candidate"
                baseline_root.mkdir(parents=True)
                candidate_root.mkdir(parents=True)
                harness_env["VNTEXT_WPF_BASELINE_EXE"] = str(
                    _build_versioned_exe_fixture(
                        baseline_root,
                        artifacts_root / "update-baseline",
                        "1.0.0",
                        nuget_config,
                        layout_targets,
                    )
                )
                harness_env["VNTEXT_WPF_CANDIDATE_EXE"] = str(
                    _build_versioned_exe_fixture(
                        candidate_root,
                        artifacts_root / "update-candidate",
                        "1.0.1",
                        nuget_config,
                        layout_targets,
                    )
                )
            proc = _run_harness(harness_env, artifacts_root)
            self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
            self.assertIn("PASS", proc.stdout)
            outcome = "PASS"
        finally:
            subprocess.run(
                [str(DOTNET), "build-server", "shutdown"],
                cwd=str(ROOT),
                env=harness_env,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            cleanup_report = cleanup_after_test(
                [owned_root],
                reason="test_wpf_workflow.py",
                outcome=outcome,
                scope_id=scope_id,
                run_id=run_id,
            )
        if outcome == "PASS":
            self.assertTrue(cleanup_report and cleanup_report.get("ok"), cleanup_report)


if __name__ == "__main__":
  unittest.main()
