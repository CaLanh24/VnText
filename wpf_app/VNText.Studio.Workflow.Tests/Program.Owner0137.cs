using System.IO;
using System.Text.RegularExpressions;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

/// <summary>
/// 0.1.37 external UX review ("the app speaks like a programmer"): one named check per group.  Group 1 = internal errors shown in plain
/// Vietnamese with a fix button; group 2 = one vocabulary everywhere and no developer terms on a screen; group 3 = numbered steps,
/// next-step button, advanced options folded, bulk actions in one menu.  Synthetic state only.
/// </summary>
internal static partial class Program
{
    private static string MainWindowXaml() => File.ReadAllText(Path.Combine(RepoRoot(), "wpf_app", "VNText.Studio.App", "MainWindow.xaml"), System.Text.Encoding.UTF8);

    /// <summary>Every static string a person can read in MainWindow.xaml (not names, bindings or resource keys).</summary>
    private static List<string> VisibleXamlStrings()
    {
        var xaml = MainWindowXaml();
        var result = new List<string>();
        foreach (Match m in Regex.Matches(xaml, "(?<![:\\w])(?:Content|Text|Header|ToolTip|Title|Description|Label)=\"([^\"{][^\"]*)\""))
            result.Add(m.Groups[1].Value);
        foreach (Match m in Regex.Matches(xaml, "AutomationProperties\\.(?:Name|HelpText)=\"([^\"{][^\"]*)\""))
            result.Add(m.Groups[1].Value);
        return result;
    }

    private static void Owner0137_Group1_MissingTranslatorSaysItInPlainWordsWithInstallButton()
    {
        using var worker = new PythonWorkerHost();
        using var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false);
        var previous = UiText.Language;
        try
        {
            UiText.SetLanguage("vi");
            vm.TestSetTranslationModelReady(false, "Không nạp được runtime CTranslate2 (ModuleNotFoundError: No module named 'ctranslate2').");
            AssertTrue(vm.TranslationEngineMissing);
            foreach (var shown in new[] { vm.TranslateReadinessText, vm.ModelStatusDisplay })
            {
                Require(shown.StartsWith("Chưa cài bộ dịch", StringComparison.Ordinal), "plain sentence: " + shown);
                foreach (var banned in PlainLanguage.ForbiddenUserTokens)
                    Require(!shown.Contains(banned, StringComparison.OrdinalIgnoreCase), $"'{banned}' leaked into: {shown}");
            }
            Require(vm.ModelStatus.Contains("ModuleNotFoundError", StringComparison.Ordinal), "the technical cause stays available for diagnostics");
            Require(vm.InstallEngineCommand.CanExecute(null), "Cài bộ dịch can start the existing install path");
            vm.RecordPersistentError("translate", "Không nạp được runtime CTranslate2 (ModuleNotFoundError: No module named 'ctranslate2'); Dịch tự động đang bị khóa.");
            vm.SelectedTab = WorkflowTabs.Translate;
            AssertEqual(PlainLanguage.EngineMissingText, vm.PersistentErrorText);                 // the error banner speaks plainly too
            Require(!vm.PersistentErrorText.Contains("ModuleNotFoundError", StringComparison.Ordinal), "no Python error name in the banner");
            vm.TestSetTranslationModelReady(true);
            AssertTrue(!vm.TranslationEngineMissing);
        }
        finally { UiText.SetLanguage(previous); }
        var xaml = MainWindowXaml();
        Require(Regex.IsMatch(xaml, "x:Name=\"InstallEngineButton\" Content=\"Cài bộ dịch\"[^>]*Command=\"\\{Binding InstallEngineCommand\\}\"", RegexOptions.Singleline), "Translate page has the Cài bộ dịch button");
        Require(xaml.Contains("x:Name=\"EngineDiagnosticsButton\" Content=\"Xem chẩn đoán\"", StringComparison.Ordinal), "and a Xem chẩn đoán button");
        Require(Regex.IsMatch(xaml, "InstallEngineButton[^>]*Visibility=\"\\{Binding TranslationEngineMissing", RegexOptions.Singleline), "the button shows only when the translator is missing");
    }

    private static void Owner0137_Group1_ResourcesAreSummarisedOnceWithAFixButton()
    {
        AssertEqual("Thiếu 2 thành phần: bộ dịch, công cụ cho game Ren’Py. Dung lượng tải khoảng 231 MB.", PlainLanguage.MissingSummary(new[] { "model", "renpy" }));
        AssertEqual("Thiếu 1 thành phần: bộ dịch. Dung lượng tải khoảng 75 MB.", PlainLanguage.MissingSummary(new[] { "model", "model" }));   // never listed or counted twice   // never listed twice
        AssertEqual("Sẵn sàng", PlainLanguage.WorkerStatus(true));
        AssertEqual("Thiếu bộ xử lý nền", PlainLanguage.WorkerStatus(false));
        var xaml = MainWindowXaml();
        Require(xaml.Contains("Content=\"Sửa tự động\"", StringComparison.Ordinal), "Settings has Sửa tự động");
        Require(!xaml.Contains("Sửa/tải tài nguyên còn thiếu", StringComparison.Ordinal), "the old developer label is gone");
        Require(xaml.Contains("Content=\"Chọn công cụ…\"", StringComparison.Ordinal), "Chọn công cụ…");
        Require(!xaml.Contains("Python worker\" Style", StringComparison.Ordinal), "no Python worker label in Settings");
    }

    private static void Owner0137_Group1_ExtractLogNeverShowsInternalStatesOrTypeNames()
    {
        foreach (var internalToken in new[] { "stale", "unity_hash", "discovery_inventory", "some_new_step" })
        {
            var shown = PlainLanguage.StepLabel(internalToken);
            Require(!shown.Contains("stale", StringComparison.OrdinalIgnoreCase) && !shown.Contains('_'), $"{internalToken} -> {shown}");
        }
        AssertEqual("Đang xử lý", PlainLanguage.StepLabel(""));
        AssertEqual("Đang đọc danh sách tệp của game", PlainLanguage.StepLabel("discovery_inventory"));
        AssertEqual("Kiểm tra tài nguyên", PlainLanguage.StepLabel("Kiểm tra tài nguyên"));                    // already ordinary words: untouched
        var run = new ExtractRunInfo(Path.Combine(TestTempRoot(), "run-20261127-101010000-abc.log"), new DateTime(2026, 11, 27, 10, 10, 10), "Hoàn tất");
        Require(!run.ToString().Contains("ExtractRunInfo", StringComparison.Ordinal) && !run.ToString().Contains("VNText.Studio", StringComparison.Ordinal), "the run reads as its title: " + run);
        AssertEqual(run.Title, run.ToString());
    }

    private static void Owner0137_Group2_NoDeveloperTermsOnAnyScreenAndOneNameForEachThing()
    {
        var strings = VisibleXamlStrings();
        Require(strings.Count > 200, "the scan reads the real screen strings: " + strings.Count);
        var banned = new[]
        {
            "Tạo patch", "Sửa CSV", "Thư mục xuất", "OPUS-MT", "CTranslate2", "INT8", "Python worker", "review_only", "locator", "bucket", "preflight", "runtime",
            "ModuleNotFoundError", "Chọn SDK", "kiểm tra trước khi build", "glyph", "mapping font", "game hoặc asset", "Game / asset", "nguồn game", "bundle", "manifest",
        };
        var hits = new List<string>();
        foreach (var s in strings)
            foreach (var b in banned)
                if (s.Contains(b, StringComparison.OrdinalIgnoreCase)) hits.Add($"[{b}] {s}");
        Require(hits.Count == 0, "developer terms still on screen:\n" + string.Join("\n", hits.Distinct()));
        var xaml = MainWindowXaml();
        Require(xaml.Contains("<TextBlock Text=\"Sửa bản dịch\" />", StringComparison.Ordinal), "nav: Sửa bản dịch");
        Require(xaml.Contains("<TextBlock Text=\"Tạo bản Việt hóa\" />", StringComparison.Ordinal), "nav: Tạo bản Việt hóa");
        Require(xaml.Contains("Text=\"Thư mục game\"", StringComparison.Ordinal) && xaml.Contains("Text=\"Nơi lưu bản dịch\"", StringComparison.Ordinal), "one name for the game folder and the output");
        Require(xaml.Contains("Dịch Anh → Việt trên máy", StringComparison.Ordinal), "translator described in plain words");
    }

    private static void Owner0137_Group2_RebuiltNamesAreUsedByEveryVisibleMessage()
    {
        var root = Path.Combine(RepoRoot(), "wpf_app", "VNText.Studio.App");
        var offenders = new List<string>();
        foreach (var file in Directory.EnumerateFiles(root, "*.cs", SearchOption.AllDirectories).Where(f => !f.Contains($"{Path.DirectorySeparatorChar}obj{Path.DirectorySeparatorChar}") && !f.Contains($"{Path.DirectorySeparatorChar}bin{Path.DirectorySeparatorChar}")))
        {
            if (file.EndsWith("PlainLanguage.cs", StringComparison.Ordinal)) continue;                // holds the forbidden list itself
            var text = File.ReadAllText(file);
            foreach (var old in new[] { "Tạo patch", "Sửa CSV", "Thư mục xuất", "Chọn SDK đã cài" })
                if (text.Contains(old, StringComparison.Ordinal)) offenders.Add(Path.GetFileName(file) + ": " + old);
        }
        Require(offenders.Count == 0, "old names remain in code: " + string.Join(", ", offenders));
    }

    private static void Owner0137_Group3_StepsAreNumberedAndNextStepFollowsProgress()
    {
        using var worker = new PythonWorkerHost();
        using var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false);
        vm.TestSetSteps(WorkflowTabs.Extract, WorkflowStepState.Current, WorkflowStepState.Pending, WorkflowStepState.Pending, false);
        AssertEqual("", vm.StepMark1); AssertEqual("", vm.StepMark2); AssertEqual("", vm.StepMark3); AssertEqual("", vm.StepMark4);   // no numbers on the sidebar, only a check when done
        AssertTrue(!vm.HasNextStep);
        vm.TestSetSteps(WorkflowTabs.Extract, WorkflowStepState.Done, WorkflowStepState.Pending, WorkflowStepState.Pending, false);
        AssertEqual("✓", vm.StepMark1);
        AssertTrue(vm.HasNextStep);
        AssertEqual("Tiếp: Dịch →", vm.NextStepLabel);
        vm.NextStepCommand.Execute(null);
        AssertEqual(WorkflowTabs.Translate, vm.SelectedTab);
        vm.TestSetSteps(WorkflowTabs.Translate, WorkflowStepState.Done, WorkflowStepState.Done, WorkflowStepState.Pending, true);
        AssertEqual("Tiếp: Sửa bản dịch →", vm.NextStepLabel);
        vm.NextStepCommand.Execute(null);
        AssertEqual(WorkflowTabs.EditCsv, vm.SelectedTab);
        AssertEqual("Tiếp: Tạo bản Việt hóa →", vm.NextStepLabel);
        vm.NextStepCommand.Execute(null);
        AssertEqual(WorkflowTabs.Patch, vm.SelectedTab);
        AssertTrue(!vm.HasNextStep);                                                                       // the last step has nothing after it
        vm.TestSetSteps(WorkflowTabs.Patch, WorkflowStepState.Done, WorkflowStepState.Done, WorkflowStepState.Done, true);
        AssertEqual("✓", vm.StepMark4);
        var xaml = MainWindowXaml();
        foreach (var n in new[] { "StepMark1", "StepMark2", "StepMark3", "StepMark4" })
            Require(xaml.Contains("{Binding " + n + "}", StringComparison.Ordinal), n + " is shown in the sidebar");
        Require(xaml.Contains("x:Name=\"NextStepButton\"", StringComparison.Ordinal), "the page header has the next-step button");
    }

    private static void Owner0137_Group3_AdvancedPatchOptionsAreFoldedAndBulkActionsLiveInOneMenu()
    {
        var xaml = MainWindowXaml();
        var expander = Regex.Match(xaml, "<Expander x:Name=\"PatchAdvancedExpander\"[^>]*>", RegexOptions.Singleline);
        Require(expander.Success && expander.Value.Contains("IsExpanded=\"False\"", StringComparison.Ordinal), "Tùy chọn nâng cao starts closed");
        var from = xaml.IndexOf("x:Name=\"PatchAdvancedExpander\"", StringComparison.Ordinal);
        var to = xaml.IndexOf("</Expander>", from, StringComparison.Ordinal);
        var inside = xaml[from..to];
        Require(inside.Contains("x:Name=\"PatchFontGroup\"", StringComparison.Ordinal) && inside.Contains("x:Name=\"PatchImageGroup\"", StringComparison.Ordinal), "font, font size and images sit inside it");
        Require(xaml.IndexOf("x:Name=\"PatchBuildButton\"", StringComparison.Ordinal) > to, "the main button stays outside the fold");
        var menu = xaml[xaml.IndexOf("x:Name=\"CsvActionsButton\"", StringComparison.Ordinal)..];
        menu = menu[..menu.IndexOf("</ContextMenu>", StringComparison.Ordinal)];
        foreach (var item in new[] { "Chọn đang lọc", "Chọn chưa dịch", "Chọn cần xem lại", "Chọn dòng có thể dịch", "Bỏ chọn", "Xóa đã chọn" })
            Require(menu.Contains($"Header=\"{item}\"", StringComparison.Ordinal), item + " is in the Thao tác menu");
        Require(Regex.IsMatch(xaml, "<Button[^>]*Content=\"Dịch đã chọn\"", RegexOptions.Singleline), "Dịch đã chọn stays outside the menu");
        Require(!Regex.IsMatch(xaml, "<Button[^>]*Content=\"Chọn chưa dịch\"", RegexOptions.Singleline), "no loose bulk button is left beside the menu");
    }
}
