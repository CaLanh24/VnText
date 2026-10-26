"""WPF workflow + path picker tests (console harness, no NuGet)."""

from __future__ import annotations
import re

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
import xml.etree.ElementTree as ET
import unittest
import unittest.mock
from pathlib import Path
from uuid import uuid4

from cleanup_work_artifacts import cleanup_after_test
from work_paths import ambient_scope, new_scope_id, register_artifacts
from tests.lib.dev_environment import dotnet_executable, nuget_cache

DEV_RUN_ROOT = Path(os.environ.get("VNTEXT_DEV_RUN_ROOT", str(ROOT / "DEV_RUN"))).expanduser()
DOTNET = dotnet_executable()
WORKFLOW_PROJECT = ROOT / "wpf_app" / "VNText.Studio.Workflow.Tests"
DOTNET_LAYOUT_VERSION = os.environ.get("VNTEXT_DOTNET_FRAMEWORK_VERSION", "8.0.30")
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
    nuget_packages = nuget_cache()
    nuget_http_cache = runtime / "nuget-http-cache"
    cache = runtime / "cache"
    nuget_packages.mkdir(parents=True, exist_ok=True)
    env["APPDATA"] = str(appdata)
    env["LOCALAPPDATA"] = str(localappdata)
    env["DOTNET_CLI_HOME"] = str(dotnet_home)
    env["DOTNET_ROOT"] = str(DOTNET.parent)
    env["DOTNET_SKIP_FIRST_TIME_EXPERIENCE"] = "1"
    # Explicit process-only guard: first-use must never add the fresh CLI home's tools dir to the persistent User PATH.
    env["DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"] = "0"
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


def _run_harness(env: dict[str, str], artifacts_root: Path, args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
    apphost = artifacts_root / "bin" / "VNText.Studio.Workflow.Tests" / "release" / "VNText.Studio.Workflow.Tests.exe"
    if not apphost.is_file():
        raise AssertionError(f"workflow harness apphost missing: {apphost}")
    runtime_env = env.copy()
    runtime_env["DOTNET_ROOT"] = str(Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "dotnet")
    if args is not None:
        run_args = args
    elif env.get("VNTEXT_WPF_GITHUB_HANDOFF_ONLY") == "1":
        run_args = ["--github-handoff-only"]
    elif env.get("VNTEXT_WPF_FULL_APP_UPDATE_ONLY") == "1":
        run_args = ["--full-app-update-only"]
    elif env.get("VNTEXT_WPF_PREFERENCES_ONLY") == "1":
        run_args = ["--preferences-only"]
    elif env.get("VNTEXT_WPF_PROGRESS_ONLY") == "1":
        run_args = ["--progress-only"]
    else:
        run_args = []
    return subprocess.run(
        [str(apphost), *run_args],
        cwd=str(ROOT),
        env=runtime_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
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
            "-p:RestorePackagesPath=" + str(nuget_cache()),
            "-p:NuGetAudit=false",
            "-p:UseSharedCompilation=false",
        ],
        cwd=str(ROOT),
        env=_harness_env(project_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if build.returncode:
        raise AssertionError(build.stdout + build.stderr)
    executable = artifacts_root / "bin" / "UpdateVersionFixture" / "release" / "UpdateVersionFixture.exe"
    if not executable.is_file():
        raise AssertionError(f"versioned updater test fixture missing: {executable}")
    return executable


class WpfWorkflowTests(unittest.TestCase):
    def test_translate_preflight_validates_the_selected_csv(self):
        workflow = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Workflow.cs").read_text(encoding="utf-8")
        run = workflow[workflow.index("private async void RunTranslate()"):workflow.index("private void ExportCloudRepairPackage()")]
        self.assertIn("var csv = ResolveActiveCsvPath();", run)
        self.assertIn("CsvPackageValidator.Validate(csv, requireTranslations: false)", run)
        self.assertIn("if (!validation.Ok)", run)
        self.assertIn("BuildTranslateParameters(csv)", run)
        self.assertNotIn("WorkflowStatus.Evaluate", run)

    def test_completion_notifications_use_the_app_theme_surface(self):
        window = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml.cs").read_text(encoding="utf-8")
        self.assertIn("vm.ShowCompletionToast(notification)", window)
        self.assertNotIn("MessageBox.Show(", window[window.index("private void OnCompletionRequested"):window.index("private void MainWindow_SizeChanged")])

    def test_harness_env_forces_process_only_global_tools_guard_over_any_inherited_value(self):
        for label, inherited in (("missing", None), ("stale_one", "1"), ("malicious_true", "true"), ("empty", "")):
            with self.subTest(inherited=label):
                before = dict(os.environ)
                patched = {k: v for k, v in os.environ.items() if k != "DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"}
                if inherited is not None:
                    patched["DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"] = inherited
                with unittest.mock.patch.dict(os.environ, patched, clear=True):
                    env = _harness_env(ROOT / "TEST_RUN" / "vntext-guard-probe-never-created")
                    caller_value = os.environ.get("DOTNET_ADD_GLOBAL_TOOLS_TO_PATH")
                self.assertEqual("0", env["DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"])
                self.assertEqual(inherited, caller_value)  # the caller's own mapping is not rewritten
                self.assertEqual(before, dict(os.environ))

    def test_real_sdk_first_use_in_two_fresh_cli_homes_never_touches_persistent_path(self):
        import hashlib
        import json

        if os.name != "nt":
            self.skipTest("Windows registry PATH invariant")
        if not DOTNET.is_file():
            self.skipTest(f".NET SDK 10 is not installed at {DOTNET}")
        import winreg

        from release import dev_bootstrap
        from work_paths import work_temp_dir

        def raw_paths() -> dict[str, tuple[str, int]]:
            out = {}
            for name, hive, sub in (
                ("user", winreg.HKEY_CURRENT_USER, "Environment"),
                ("machine", winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            ):
                with winreg.OpenKey(hive, sub) as key:
                    value, kind = winreg.QueryValueEx(key, "Path")
                out[name] = (value, kind)
            return out

        before = raw_paths()
        homes = []
        results = []
        runs = []
        # Home A: the real owned test-harness environment (SKIP_FIRST_TIME removed so first use genuinely runs).
        # Home B: the bootstrap/runner boundary with an explicit stale inherited value.
        for label, inherited in (("harness_stale_one", "1"), ("bootstrap_malicious_true", "true")):
            work_root = work_temp_dir(f"dotnet-path-guard-{label}")
            homes.append(work_root)
            with unittest.mock.patch.dict(os.environ, {"DOTNET_ADD_GLOBAL_TOOLS_TO_PATH": inherited}):
                if label.startswith("harness"):
                    env = _harness_env(work_root)
                    env.pop("DOTNET_SKIP_FIRST_TIME_EXPERIENCE", None)
                    cli_home = Path(env["DOTNET_CLI_HOME"])
                    self.assertEqual("0", env["DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"])
                    receipt = dev_bootstrap.run([str(DOTNET), "new", "list"], env=env)
                else:
                    cli_home = work_root / "dotnet-home"
                    os.environ.pop("DOTNET_SKIP_FIRST_TIME_EXPERIENCE", None)
                    os.environ.update(
                        DOTNET_CLI_HOME=str(cli_home), APPDATA=str(work_root / "appdata"),
                        LOCALAPPDATA=str(work_root / "localappdata"), DOTNET_CLI_TELEMETRY_OPTOUT="1",
                        DOTNET_MULTILEVEL_LOOKUP="0", DOTNET_ADD_GLOBAL_TOOLS_TO_PATH=inherited,
                    )
                    receipt = dev_bootstrap.run([str(DOTNET), "new", "list"])  # inherited-environment boundary
                    self.assertEqual(inherited, os.environ["DOTNET_ADD_GLOBAL_TOOLS_TO_PATH"])  # caller env unchanged
            self.assertEqual(0, receipt["exit_code"], receipt["stderr"][-400:])
            sentinels = sorted(p.name for p in (cli_home / ".dotnet").glob("*dotnetFirstUseSentinel"))
            self.assertTrue(sentinels, f"first-use did not run in {cli_home}")
            self.assertFalse((cli_home / ".dotnet" / "tools").exists(), "global tools directory created")
            runs.append({"home": str(cli_home), "inherited_guard": inherited, "exit_code": receipt["exit_code"], "first_use_sentinels": sentinels})
        self.assertNotEqual(runs[0]["home"], runs[1]["home"])
        after = raw_paths()
        self.assertEqual(before, after)  # exact raw value and registry kind, User and Machine
        for scope in before:
            self.assertEqual(before[scope][0].count(".dotnet"), after[scope][0].count(".dotnet"))
            for home in homes:
                self.assertNotIn(str(home).lower(), after[scope][0].lower())
        receipt_path = os.environ.get("VNTEXT_DOTNET_PATH_RECEIPT")
        if receipt_path:
            Path(receipt_path).write_text(json.dumps({
                "command": "dotnet new list (SDK first use, SKIP_FIRST_TIME_EXPERIENCE removed)",
                "sdk": str(DOTNET), "runs": runs,
                "path_before": {k: {"length": len(v[0]), "kind": v[1], "sha256": hashlib.sha256(v[0].encode("utf-8")).hexdigest()} for k, v in before.items()},
                "path_after": {k: {"length": len(v[0]), "kind": v[1], "sha256": hashlib.sha256(v[0].encode("utf-8")).hexdigest()} for k, v in after.items()},
                "identical": before == after,
            }, indent=2), encoding="utf-8")

    def test_translate_model_tooltip_is_scoped_to_its_description(self):
        xaml = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").read_text(encoding="utf-8")
        styles = (ROOT / "wpf_app" / "VNText.Studio.App" / "Themes" / "ControlStyles.xaml").read_text(encoding="utf-8")
        self.assertNotIn('ToolTip="Dịch bằng mô hình đã có trên máy, không gửi nội dung lên mạng."', xaml)
        self.assertIn('Text="Dịch Anh sang Việt trên máy" ToolTip="Mô hình OPUS-MT · INT8 · CTranslate2."', xaml)
        tooltip_style = styles.split('<Style TargetType="ToolTip">', 1)[1].split('</Style>', 1)[0]
        self.assertIn('Value="400"', tooltip_style)
        self.assertIn('CornerRadius="8"', tooltip_style)
        self.assertIn("DropShadowEffect", tooltip_style)
        self.assertIn('TextWrapping="Wrap"', tooltip_style)

    def test_workflow_options_are_not_duplicated(self):
        xaml = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").read_text(encoding="utf-8")
        glossary_probe = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "BulkGlossaryUiProbe.cs").read_text(encoding="utf-8")
        for option in (
            'Content="Tách dòng cần duyệt"',
            'Content="Ghi đè bản dịch cũ"',
            'Content="Duyệt bản dịch trước khi đóng gói"',
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
        recovery = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "RenpySdkRecovery.cs").read_text(encoding="utf-8")
        workflow_tests = (ROOT / "wpf_app" / "VNText.Studio.Workflow.Tests" / "Program.cs").read_text(encoding="utf-8")
        worker = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Worker.cs").read_text(encoding="utf-8")
        self.assertIn('Visibility="{Binding RenpySdkOptionsVisible, Converter={StaticResource BoolToVis}}"', xaml)
        self.assertIn("RenpyGameDetector.HasSdkRecoveryEvidence", view_model)
        self.assertIn("Lấy text chưa đầy đủ do thiếu công cụ Ren'Py", worker)
        self.assertIn("Tải công cụ rồi lấy text", xaml)
        self.assertIn("Tiếp tục, lời thoại cần xem lại", xaml)
        self.assertIn("không dùng parser thay thế", xaml)
        self.assertIn('"missing" => "Chưa dùng được SDK Ren\'Py 8.5.3.', recovery)
        self.assertIn('"ready" => "Đã sẵn sàng SDK Ren\'Py 8.5.3."', recovery)
        self.assertIn("RenpySdkRecovery.ResolveAction", worker)
        self.assertIn("RenpySdkRecovery_StatusRequiresSuccessfulEvidence", workflow_tests)

    def test_csv_editor_controls_stay_visible_and_validation_stays_automatic(self):
        xaml = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").read_text(encoding="utf-8")
        editor = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.CsvEditor.cs").read_text(encoding="utf-8")
        self.assertNotIn('x:Name="CsvControlsScrollViewer"', xaml)
        self.assertNotIn('MaxHeight="220"', xaml)
        self.assertIn('Text="Tìm và thay thế bản dịch"', xaml)
        self.assertIn('x:Name="CsvEditorCard"', xaml)
        self.assertIn('x:Name="CsvEditorSearchBox"', xaml)
        self.assertIn('<UniformGrid Grid.Column="1" Columns="3"', xaml)
        self.assertIn('x:Name="CsvBulkFindTextBox"', xaml)
        self.assertIn('x:Name="CsvBulkReplaceTextBox"', xaml)
        self.assertIn('Text="Tìm trong bản dịch"', xaml)
        self.assertIn('Content="Xem trước"', xaml)
        self.assertIn('Content="Áp dụng"', xaml)
        self.assertIn('Command="{Binding ApplyBulkReplaceCsvCommand}"', xaml)
        self.assertIn('Header="MÃ DÒNG" Binding="{Binding Key}" IsReadOnly="True" Width="0" MinWidth="0" Visibility="Collapsed"', xaml)
        self.assertIn('ToolTip="{Binding CsvEditorPathToolTip}"', xaml)
        self.assertIn('IsReadOnly="{Binding CsvEditorGridReadOnly}"', xaml)
        self.assertIn('Text="{Binding CsvEditorLockText}"', xaml)
        self.assertIn("if (Busy)", editor)  # direct-entry save guard
        self.assertIn('ToolTipService.IsEnabled', xaml)
        self.assertIn('Text="{Binding CsvEditorSelectionDetails}"', xaml)
        self.assertIn('Text="{Binding ExtractProgressStep}"', xaml)
        self.assertIn('Text="{Binding PatchProgressStep, StringFormat=\'Bước: {0}\'}"', xaml)
        self.assertIn('Visibility="{Binding ExtractProgressHasEta, Converter={StaticResource BoolToVis}}"', xaml)
        self.assertIn('Visibility="{Binding PatchProgressHasEta, Converter={StaticResource BoolToVis}}"', xaml)
        self.assertIn('Style="{StaticResource BlueProgressBarStyle}"', xaml)
        styles = (ROOT / "wpf_app" / "VNText.Studio.App" / "Themes" / "ControlStyles.xaml").read_text(encoding="utf-8")
        self.assertIn('<Setter Property="GridLinesVisibility" Value="All" />', styles)
        for command in ("ClearBlockedCsvCommand", "ValidateCsvEditorCommand", "RetranslateBlockedCsvCommand", "ApproveCsvMemoryCommand"):
            self.assertNotIn(f'Command="{{Binding {command}}}"', xaml)
        self.assertIn("ValidateCsvEditor(showLog: false)", editor)
        self.assertIn('Text="{Binding CsvEditorUserValidationMessage}"', xaml)
        self.assertIn('ToolTip="{Binding CsvEditorValidationMessage}"', xaml)

    def test_csv_editor_save_is_async_and_protects_exit_and_external_edits(self):
        editor = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.CsvEditor.cs").read_text(encoding="utf-8")
        window = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml.cs").read_text(encoding="utf-8")
        api = (ROOT / "vntext" / "csv_editor_api.py").read_text(encoding="utf-8")
        self.assertIn("private async Task<bool> SaveCsvEditorCoreAsync()", editor)
        self.assertIn("await CsvEditorSaveExecutor(() => RunCsvEditorSave", editor)
        self.assertIn("static work => Task.Run(work)", editor)
        self.assertNotIn("Application.Current?.Dispatcher is null", editor)
        self.assertIn("expectedSha256", editor)
        self.assertIn("WaitForCsvEditorSaveAsync()", window)
        self.assertIn("await vm.TrySaveCsvEditorForExitAsync()", window)
        self.assertIn("Chọn Lưu", window)
        self.assertIn("Bỏ thay đổi", window)
        self.assertIn("CsvEditorDirty = false", editor)
        self.assertIn("editGeneration == Volatile.Read(ref _csvEditorEditGeneration)", editor)
        self.assertIn("CsvEditorExternalChange", api)
        self.assertIn("written_sha256", api)
        workflow_tests = (ROOT / "wpf_app" / "VNText.Studio.Workflow.Tests" / "Program.cs").read_text(encoding="utf-8")
        self.assertIn("CsvEditor_SaveAsyncKeepsDispatcherResponsiveAndCoalesces", workflow_tests)
        self.assertIn("CsvEditor_SaveExternalEditFailsClosedAndKeepsDirty", workflow_tests)
        self.assertIn("test_save_compare_and_swap_rechecks_after_backup", (ROOT / "tests" / "unit" / "test_csv_editor_api.py").read_text(encoding="utf-8"))

    def test_path_picker_cancellation_does_not_prompt_about_or_discard_csv_edits(self):
        paths = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Paths.cs").read_text(encoding="utf-8")
        input_method = paths.split("private async void ChooseInput()", 1)[1].split("private async void ChooseOutput()", 1)[0]
        output_method = paths.split("private async void ChooseOutput()", 1)[1].split("private void ChooseTranslationCsv()", 1)[0]
        for method, picker in ((input_method, "PickInputPath"), (output_method, "PickOutputFolder")):
            self.assertLess(method.index(picker), method.index("ConfirmCsvBeforeSourceChange"))
            self.assertIn("!string.IsNullOrWhiteSpace(path)", method)
            self.assertIn("StringComparison.OrdinalIgnoreCase", method)

    def test_wpf_app_dialogs_use_the_shared_rounded_dialog_shell(self):
        app_dir = ROOT / "wpf_app" / "VNText.Studio.App"
        dialog = (app_dir / "Services" / "AppDialogService.cs").read_text(encoding="utf-8")
        shell = (app_dir / "Services" / "AppDialogWindow.cs").read_text(encoding="utf-8")
        styles = (app_dir / "Themes" / "ControlStyles.xaml").read_text(encoding="utf-8")
        memory = (app_dir / "ViewModels" / "MainViewModel.ReviewedMemory.cs").read_text(encoding="utf-8")
        xaml = (app_dir / "MainWindow.xaml").read_text(encoding="utf-8")
        dialog_fixture = (ROOT / "wpf_app" / "VNText.Studio.Workflow.Tests" / "AppDialogFixtureTests.cs").read_text(encoding="utf-8")
        # Shared shell: borderless transparent window, rounded card, custom X, scrolling body, overlay.
        for needle in ("WindowStyle = WindowStyle.None", "AllowsTransparency = true", "CardRadius = 18",
                       '"DialogCloseButton"', "VerticalScrollBarVisibility = ScrollBarVisibility.Auto",
                       "Key.Escape", "BlurEffect", "Keyboard.Focus(_previousFocus)", '"PrimaryButton" : "OutlineButton"'):
            self.assertIn(needle, shell, needle)
        self.assertIn('x:Key="DialogCloseButton"', styles)
        self.assertIn("IsMouseOver", styles.split('x:Key="DialogCloseButton"')[1].split("</Style>")[0])
        self.assertIn("IsPressed", styles.split('x:Key="DialogCloseButton"')[1].split("</Style>")[0])
        # Every AppDialogService prompt goes through the shell with safe dismiss defaults.
        self.assertIn("new AppDialogWindow(", dialog)
        self.assertIn('MessageBoxButton.YesNo => MessageBoxResult.No', dialog)
        self.assertIn('MessageBoxButton.YesNoCancel or MessageBoxButton.OKCancel => MessageBoxResult.Cancel', dialog)
        self.assertIn('owner ??= app?.Windows.OfType<Window>()', dialog)
        self.assertIn("shared rounded shell/custom X/scroll body", dialog_fixture)
        self.assertIn("new AppDialogWindow(", memory)
        self.assertIsNone(re.search(r"new Window\s*[({]", memory))
        # Update and Journal shells share the same X style, card radius token and button styles.
        for name in ("UpdateWindow.cs", "JournalWindow.cs"):
            text = (app_dir / name).read_text(encoding="utf-8")
            self.assertIn('"DialogCloseButton"', text, name)
            self.assertIn("AppDialogWindow.CardRadius", text, name)
            self.assertIn('"PrimaryButton" : "OutlineButton"', text, name)
            self.assertNotIn('"GhostButton"', text, name)
        self.assertIn("new CornerRadius(0, 0, CardRadius, CardRadius)", shell)
        self.assertIn("_wrappedHost", shell)
        glossary = xaml.split('x:Name="GlossaryOverlay"')[1].split("GlossaryListBox")[0]
        self.assertIn('CornerRadius="18"', glossary)
        self.assertIn('DialogCloseButton', glossary)
        for path in app_dir.rglob("*.cs"):
            if "obj" in path.parts or "bin" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if path.name != "AppDialogService.cs":
                self.assertNotIn("MessageBox.Show(", text, str(path))
            # No plain titled Window may be constructed for an app-owned dialog.
            if path.name not in {"App.xaml.cs"} and "Probe" not in path.name:
                self.assertIsNone(re.search(r"new Window\s*[({]", text), str(path))

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
        self.assertIn("vm.Busy || outputStarted()", probe)
        self.assertIn("OutputIsReady(validateOutput)", probe)
        self.assertIn('Path.Combine(outputPath, "Patch_Viet_Hoa")', probe)
        self.assertIn("WPF E2E output must be a fresh, empty generated package directory", probe)
        self.assertIn('model = "ct2"', workflow)
        self.assertIn('model = "ct2"', (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.CsvEditor.cs").read_text(encoding="utf-8"))
        self.assertIn("human_review_required = HumanReviewRequired", workflow)
        self.assertIn("human_review_required = HumanReviewRequired", (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.CsvEditor.cs").read_text(encoding="utf-8"))
        self.assertIn("public bool HumanReviewRequired", view_model)
        self.assertIn("public bool HumanReviewRequired", settings)
        self.assertIn("Duyệt bản dịch trước khi đóng gói", xaml)
        self.assertIn('Content="Duyệt bản dịch trước khi đóng gói"', xaml)
        self.assertNotIn('Text="Thiết bị"', xaml)
        self.assertNotIn('DataTrigger Binding="{Binding StatusText}" Value="Sẵn sàng"', xaml)
        self.assertIn('DataTrigger Binding="{Binding GlossaryStatus}" Value="Danh sách từ được lưu cùng gói dịch."', xaml)

    def test_content_disclosures_bind_to_real_presentation_states(self):
        view_model = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.cs").read_text(encoding="utf-8")
        analyze = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Analyze.cs").read_text(encoding="utf-8")
        xaml = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").read_text(encoding="utf-8")
        self.assertIn('IsExpanded="{Binding AnalyzeResultsExpanded, Mode=TwoWay}"', xaml)
        self.assertIn('Visibility="{Binding AnalyzeHasReport, Converter={StaticResource BoolToVis}}"', xaml)
        self.assertIn('Text="{Binding AnalyzeEngineDetails}"', xaml)
        self.assertIn('GetRenpyEvidenceKind(InputPath', analyze)
        self.assertIn('IsExpanded="{Binding PatchResultsExpanded, Mode=TwoWay}"', xaml)
        self.assertIn('Visibility="{Binding PatchResultsAvailable, Converter={StaticResource BoolToVis}}"', xaml)
        self.assertIn('Visibility="{Binding PatchPreflightEvaluated, Converter={StaticResource BoolToVis}}"', xaml)
        self.assertIn('Visibility="{Binding CloudRepairPackageReady, Converter={StaticResource BoolToVis}}"', xaml)
        xaml_root = ET.parse(ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").getroot()
        x_name = "{http://schemas.microsoft.com/winfx/2006/xaml}Name"
        named = {element.attrib[x_name]: element for element in xaml_root.iter() if x_name in element.attrib}
        parents = {child: parent for parent in xaml_root.iter() for child in parent}
        patch_card = named["PatchCheckCard"]
        self.assertNotIn("Height", patch_card.attrib)
        self.assertEqual("Top", patch_card.attrib.get("VerticalAlignment"))
        row_definitions = next(element for element in patch_card.iter() if element.tag.endswith("Grid.RowDefinitions"))
        self.assertTrue(all(row.attrib.get("Height") == "Auto" for row in row_definitions))
        self.assertIn('Text="{Binding ExtractProgressStep}"', xaml)
        self.assertIn('Value="{Binding ExtractProgressPercent, Mode=OneWay}"', xaml)
        self.assertIn('Value="{Binding TranslateProgressPercent, Mode=OneWay}"', xaml)
        self.assertIn('Value="{Binding PatchProgressPercent, Mode=OneWay}"', xaml)
        self.assertIn('Text="{Binding TranslateWorkflowStatusText}" FontSize="{StaticResource UiCaptionSize}"', xaml)
        self.assertIn('RefreshWorkflow();\n                RefreshTranslateReadiness();', view_model)
        self.assertIn('Content="Dịch ảnh…"', xaml)
        self.assertIn('Command="{Binding CancelAndExitCommand}"', xaml)
        self.assertIn('Text="{Binding ExtractStatusText}"', xaml)
        window_code = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml.cs").read_text(encoding="utf-8")
        self.assertIn("vm.CancelAndExitCommand.Execute(null)", window_code)
        self.assertIn("await vm.TrySaveCsvEditorForExitAsync()", window_code)
        self.assertIn("MessageBoxButton.YesNoCancel", window_code)
        delivery_panel = named["PatchDeliveryInstructionsPanel"]
        extract_options = named["ExtractOptionsPanel"]
        renpy_options = named["RenpySdkOptionsPanel"]
        self.assertEqual(
            "{Binding PatchDeliveryReady, Converter={StaticResource BoolToVis}}",
            delivery_panel.attrib.get("Visibility"),
        )
        self.assertNotIn("PatchDeliveryReady", extract_options.attrib.get("Visibility", ""))
        self.assertIn("Tách dòng cần duyệt", "".join(element.attrib.get("Content", "") for element in extract_options.iter()))
        self.assertEqual(
            "{Binding RenpySdkOptionsVisible, Converter={StaticResource BoolToVis}}",
            renpy_options.attrib.get("Visibility"),
        )
        self.assertIs(parents.get(parents.get(renpy_options)), extract_options)
        self.assertIn('ToolTip="Nếu CSV thuộc gói ZIP, ứng dụng đối chiếu gói trước khi tạo patch."', xaml)
        self.assertIn('ToolTip="Chỉ nhập dòng khớp mã và câu gốc; dòng khác được giữ để sửa."', xaml)
        self.assertIn('ToolTip="Mô hình OPUS-MT · INT8 · CTranslate2."', xaml)
        self.assertNotIn("Chưa kiểm tra translation.csv", view_model)
        self.assertNotIn("Chưa kiểm tra chất lượng patch", view_model)
        self.assertNotIn("Chưa có lỗi quét được ghi nhận.", analyze)
        self.assertNotIn("Báo cáo sẽ được ghi ngoài thư mục game.", analyze)

    def test_extract_completion_revalidates_the_generated_csv_after_workflow_refresh(self):
        worker = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Worker.cs").read_text(encoding="utf-8")
        refresh = worker.index("RefreshWorkflow();")
        extract_refresh = worker.index('if (completedTask == "extract" && fullyComplete)', refresh)
        csv_path = worker.index('TranslationCsvPath = Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "translation.csv");', extract_refresh)
        readiness = worker.index("RefreshTranslateReadiness(syncCsvValidation: true);", csv_path)
        self.assertLess(refresh, extract_refresh)
        self.assertLess(csv_path, readiness)
        workflow = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Workflow.cs").read_text(encoding="utf-8")
        readiness_apply = re.search(r"void Apply\(CsvValidationResult result\b[^)]*\)", workflow).start()
        self.assertIn("if (syncCsvValidation)", workflow[readiness_apply:])
        self.assertIn("CsvValidationOk = result.Ok;", workflow[readiness_apply:])
        self.assertIn("CsvValidationMessage = result.Message;", workflow[readiness_apply:])
        self.assertIn("Raise(nameof(TranslateWorkflowStatusText));", workflow[readiness_apply:])
        paths = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.Paths.cs").read_text(encoding="utf-8")
        strict_patch_validation = paths[paths.index("private bool ValidateTranslationCsv"):paths.index("private bool ValidateTranslationCsv") + 900]
        self.assertIn("CsvPackageValidator.Validate(path, requireTranslations);", strict_patch_validation)

    def test_image_workspace_is_reachable_and_every_command_is_bound(self):
        app = ROOT / "wpf_app" / "VNText.Studio.App"
        panel = (app / "Controls" / "ImageWorkspacePanel.xaml").read_text(encoding="utf-8")
        window = (app / "MainWindow.xaml").read_text(encoding="utf-8")
        window_code = (app / "MainWindow.xaml.cs").read_text(encoding="utf-8")
        image_vm = (app / "ViewModels" / "MainViewModel.ImageText.cs").read_text(encoding="utf-8")
        # Every stage of the OCR -> review -> render -> delivery -> install workflow has a real binding in the XAML.
        for command in (
            "DiscoverImagesCommand", "ChooseOcrImageCommand", "RunImageOcrCommand", "OpenImageReviewCommand",
            "SaveImageReviewCommand", "RenderImageCommand", "CreateImageDeliveryCommand", "InstallImageDeliveryCommand",
            "RecoverImageDeliveryCommand", "AddImageRegionCommand", "RemoveImageRegionCommand", "OpenOutputCommand",
        ):
            with self.subTest(command=command):
                self.assertRegex(panel, r"Command=\"\{Binding (DataContext\.)?" + command + r"\b")
                if command != "OpenOutputCommand":
                    self.assertIn(f"public RelayCommand {command}", image_vm)
        for binding in ("ImageCandidates", "ImagePath", "ImagePreview", "ImageRegions", "ImageStatus", "ImageWorkspaceSummary", "ImageGridEnabled"):
            with self.subTest(binding=binding):
                self.assertIn("{Binding " + binding, panel)
        for approval in ("FlatBackgroundApproved", "ReplacementBackgroundApproved", "TransparentTextApproved", "CloneBackgroundApproved", "Approved"):
            self.assertIn("IsChecked=\"{Binding " + approval + "}\"", panel)
        # The workspace is opened through the shared themed dialog shell from both entry points.
        self.assertGreaterEqual(len(re.findall(r"Command=\"\{Binding OpenImageWorkspaceCommand\}\"", window)), 2)
        self.assertIn("new AppDialogWindow(this", window_code)
        self.assertIn("ImageWorkspacePanel", window_code)
        self.assertIn("ImageWorkspaceRequested", window_code)
        # The modal has its own Cancel (the owner window, with its Cancel button, is disabled while a modal is open),
        # shows the owning task and the progress/cancel-acknowledgement line, and offers a spinner only while Busy.
        self.assertRegex(panel, r'Command="\{Binding CancelCommand\}"')
        self.assertIn("{Binding ImageWorkspaceTaskText}", panel)
        self.assertIn("{Binding ImageWorkspaceProgressText}", panel)
        self.assertRegex(panel, r'x:Name="TaskBanner"[^>]*\n?[^>]*Visibility="\{Binding Busy')
        # Compact main grid; crop/font/colour/background options are in a labelled detail form bound to the selection.
        self.assertIn("SelectedItem=\"{Binding SelectedImageRegion", panel)
        grid_xaml = panel[panel.index('x:Name="RegionGrid"'):panel.index("</DataGrid>")]
        self.assertLessEqual(grid_xaml.count("<DataGridTextColumn") + grid_xaml.count("<DataGridCheckBoxColumn") + grid_xaml.count("<DataGridTemplateColumn "), 5)
        for field in ("X", "Y", "Width", "Height", "FontSize", "Background", "Foreground", "DonorX", "DonorY"):
            self.assertIn("Text=\"{Binding " + field + ",", panel)
        # The candidate source cannot change while a task runs, cancellation is its own state, and a cancelled/failed OCR keeps the source.
        self.assertRegex(panel, r'x:Name="CandidateCombo"[^>]*IsEnabled="\{Binding ImageGridEnabled\}"')
        complete = image_vm[image_vm.index("private void CompleteImageTask"):]
        self.assertIn("Đã hủy {ImageTaskLabel(task)}", complete)
        self.assertIn("kết quả cũ bị bỏ", complete)
        prepare = image_vm[image_vm.index("internal void PrepareImageExtractState"):image_vm.index("private string _imageTaskImagePath")]
        self.assertNotIn('ImagePath = ""', prepare)
        self.assertIn("PrepareImageExtractState();", image_vm[image_vm.index("private void StartImageTask"):image_vm.index("internal void PrepareImageExtractState")])
        # Honest wording: only the install step writes, and only into a separate copy.
        self.assertNotIn("game không bị sửa", panel)
        self.assertIn("BẢN SAO", panel)
        # Restore geometry is fitted to the logical work area, always (also when window memory is off).
        settings = (app / "ViewModels" / "MainViewModel.Settings.cs").read_text(encoding="utf-8")
        restore = settings[settings.index("internal void RestoreWindow"):settings.index("internal void SaveWindow")]
        self.assertIn("WindowGeometry.Compute", restore)
        self.assertIn("SystemParameters.WorkArea", restore)
        self.assertNotIn("if (!_settings.RememberWindow) return;", restore)
        self.assertIn("RefitWindow", window_code)
        # The empty-text-CSV path never feeds the image commands: they depend on Busy/paths/review state only.
        for line in re.findall(r"new RelayCommand\([^\n]*", image_vm):
            self.assertNotIn("CsvValidationOk", line)
            self.assertNotIn("PatchPreflightOk", line)

    def test_non_applicable_unity_scan_summary_is_not_an_error_log(self):
        journal = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "AppJournalStore.cs").read_text(encoding="utf-8")
        self.assertIn(r"scan_errors=(?<count>\d+)", journal)
        self.assertIn("scanErrorCount > 0", journal)
        self.assertIn(r"\berrors?\b", journal)

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
        self.assertIn('ToolTip="Nếu CSV thuộc gói ZIP, ứng dụng đối chiếu gói trước khi tạo patch."', patch_page)
        self.assertIn('Command="{Binding ChooseTranslationCsvCommand}"', patch_page)

        page_root = ET.parse(ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").getroot()
        parents = {child: parent for parent in page_root.iter() for child in parent}
        export = next(e for e in page_root.iter() if e.attrib.get("Command") == "{Binding ExportCloudRepairPackageCommand}")
        reuse = next(e for e in page_root.iter() if e.attrib.get("Command") == "{Binding ImportExistingTranslationCommand}")
        self.assertLess(list(page_root.iter()).index(export), list(page_root.iter()).index(reuse))
        for action in (export, reuse):
            self.assertEqual("1", action.attrib.get("Grid.Column"))
            self.assertEqual("Center", action.attrib.get("VerticalAlignment"))
            row = parents[action]
            labels = next(e for e in row if e.tag.endswith("StackPanel"))
            self.assertEqual("Wrap", list(labels)[0].attrib.get("TextWrapping"))
            self.assertEqual("{StaticResource OutlineButton}", action.attrib.get("Style"))

    def test_wpf_internal_update_controls_are_available_and_rechecked(self):
        xaml = (ROOT / "wpf_app" / "VNText.Studio.App" / "MainWindow.xaml").read_text(encoding="utf-8")
        view_model = (ROOT / "wpf_app" / "VNText.Studio.App" / "ViewModels" / "MainViewModel.cs").read_text(encoding="utf-8")
        updater = (ROOT / "wpf_app" / "VNText.Studio.App" / "Services" / "WpfUpdateService.cs").read_text(encoding="utf-8")
        self.assertIn('Header="Giới thiệu"', xaml)
        self.assertIn('Text="{Binding CurrentVersionDisplay}"', xaml)
        self.assertIn('Click="CheckUpdates_Click"', xaml)
        adapter = (ROOT / "wpf_app" / "VNText.Studio.App" / "UpdatePresentation.cs").read_text(encoding="utf-8")
        self.assertIn("_vm.RecheckUpdateCommand.Execute(null)", adapter)
        self.assertIn("_vm.RestartForUpdate()", adapter)
        self.assertIn('Text="{Binding GitHubUpdateStatus}"', xaml)
        self.assertIn('AutomationProperties.Name="Kiểm tra cập nhật"', xaml)
        self.assertIn('DataTrigger Binding="{Binding GitHubUpdateStatus}" Value="Kiểm tra phiên bản mới khi bạn sẵn sàng."', xaml)
        self.assertIn('"Chưa cấu hình nguồn cập nhật."', view_model)
        self.assertNotIn('Local Updates preview', xaml)
        self.assertNotIn('Apply local preview', xaml)
        self.assertNotIn('Stable public releases (GitHub)', xaml)
        self.assertNotIn('GitHubUpdateStatus', xaml[:xaml.index('<!-- Main content -->')])
        self.assertNotIn('RecheckUpdateCommand', xaml[:xaml.index('<!-- Main content -->')])
        self.assertIn('ImageSource="Assets/brand-owner.png"', xaml)
        self.assertNotIn('Text="Dự án game"', xaml)
        self.assertNotIn('Text="PROJECT"', xaml)
        self.assertNotIn('Text="Unity project"', xaml)
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
                    "-p:RestorePackagesPath=" + str(nuget_cache()),
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
                encoding="utf-8",
                errors="replace",
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
            self.assertEqual(0, proc.returncode, (proc.stdout or "") + (proc.stderr or ""))
            self.assertIn("PASS", proc.stdout)
            dialog_proc = _run_harness(harness_env, artifacts_root, ["--app-dialog-fixture"])
            self.assertEqual(0, dialog_proc.returncode, (dialog_proc.stdout or "") + (dialog_proc.stderr or ""))
            self.assertIn("WPF app dialog interaction fixture: PASS", dialog_proc.stdout)
            workspace_proc = _run_harness(harness_env, artifacts_root, ["--image-workspace-fixture"])
            self.assertEqual(0, workspace_proc.returncode, (workspace_proc.stdout or "") + (workspace_proc.stderr or ""))
            self.assertIn("WPF image workspace fixture: PASS", workspace_proc.stdout)
            fixture_out = os.environ.get("VNTEXT_UPDATER_PRESENTATION_FIXTURE_OUT")
            if fixture_out:
                import shutil
                destination = Path(fixture_out).resolve()
                self.assertEqual(destination, (ROOT / "DEV_RUN" / "bootstrap-build").resolve())
                for filename in ("VNText.Studio.Workflow.Tests.dll", "VNText.Studio.Workflow.Tests.deps.json", "VNText.Studio.Workflow.Tests.runtimeconfig.json"):
                    candidates = [artifacts_root / "bin" / "VNText.Studio.Workflow.Tests" / "release" / filename]
                    self.assertTrue(candidates, filename)
                    destination.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(candidates[0], destination / filename)
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
