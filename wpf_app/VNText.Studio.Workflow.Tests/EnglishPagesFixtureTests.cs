using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Media;
using System.Windows.Threading;
using VNText.Studio.App;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private static IEnumerable<string> PageStrings(DependencyObject root)
    {
        var uiColumns = new HashSet<string> { "TRẠNG THÁI", "STATUS", "CHẾ ĐỘ NỀN", "BACKGROUND MODE", "XÓA", "DELETE" };
        foreach (var node in Descendants(root))
        {
            if (node is TextBox) continue;
            if (node is TextBlock inCell && FindAncestor<DataGridCell>(inCell) is { } owning && !(owning.Column.Header is string columnHeader && uiColumns.Contains(columnHeader))) continue;
            if (node is TextBlock text && !string.IsNullOrEmpty(text.Text)) yield return text.Text;
            if (node is ContentControl { Content: string content } && content.Length > 0) yield return content;
            if (node is HeaderedContentControl { Header: string header }) yield return header;
            if (node is FrameworkElement element)
            {
                if (element.ToolTip is string tip && tip.Length > 0) yield return tip;
                var name = System.Windows.Automation.AutomationProperties.GetName(element); if (!string.IsNullOrEmpty(name)) yield return name;
                var help = System.Windows.Automation.AutomationProperties.GetHelpText(element); if (!string.IsNullOrEmpty(help)) yield return help;
            }
            if (node is DataGrid grid)
                foreach (var column in grid.Columns) if (column.Header is string columnTitle) yield return columnTitle;
            if (node is ComboBox combo)
                foreach (var item in combo.Items)
                {
                    if (item is string plain) yield return plain;
                    else if (item?.GetType().GetProperty("Label")?.GetValue(item) is string label) yield return label;
                    else if (item?.GetType().GetProperty("Name")?.GetValue(item) is string optionName) yield return optionName;
                }
        }
    }

    /// <summary>Real MainWindow, English, UI 120%, 1043x720 DIP: every application-owned string on Settings (General/Data/About), CSV, Patch, Glossary, Journal,
    /// release notes and the confirmation dialogs is English; user data, paths, technical text and release-note bodies are excluded.</summary>
    private static int RunEnglishPagesFixture(string[] args)
    {
        var exitCode = 1;
        var inventoryOnly = args.Contains("--inventory", StringComparer.Ordinal);
        var thread = new Thread(() =>
        {
            var root = Path.Combine(TestTempRoot(), "vntext_wpf_pages_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            try
            {
                var local = Environment.GetEnvironmentVariable("VNTEXT_LOCALAPPDATA") ?? throw new InvalidOperationException("isolated root required");
                Require(Path.GetFullPath(local).Contains(Path.DirectorySeparatorChar + "TEST_RUN" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "TEST_RUN isolation");
                var app = new VNText.Studio.App.App();
                app.InitializeComponent();
                app.ShutdownMode = ShutdownMode.OnExplicitShutdown;
                var packageA = CreatePatchSourcePackage("Hộ tống");
                var packageB = CreatePatchSourcePackage("Đồng " + string.Join(" ", Enumerable.Repeat("bán", 40)), complete: false);
                var picker = new FakePathPicker();
                using var worker = new PythonWorkerHost();
                var vm = new MainViewModel(picker, worker, startWorker: false) { OutputPath = packageA };
                vm.UiScale = 1.2;
                var window = new MainWindow(vm, new FixtureUpdatePresentation());
                window.WindowState = WindowState.Normal; window.Width = 1043; window.Height = 720; window.Show(); window.UpdateLayout(); PumpFixture(250);
                vm.Language = "en"; window.UpdateLayout(); PumpFixture(300);
                var offenders = new SortedDictionary<string, SortedSet<string>>();
                var states = 0;
                void Scan(string state, DependencyObject scope)
                {
                    window.UpdateLayout(); PumpFixture(120);
                    foreach (var s in PageStrings(scope).Concat(scope is Window w ? new[] { w.Title } : Array.Empty<string>()))
                        if (VietnameseLetters.IsMatch(s))
                        {
                            if (!offenders.TryGetValue(state, out var set)) offenders[state] = set = new SortedSet<string>();
                            set.Add(s.Length > 150 ? s[..150] + "…" : s);
                        }
                    states++;
                }
                FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                DependencyObject CsvScope() => ((FrameworkElement)Named("CsvEditorCard")).Parent;
                DependencyObject PatchScope() => Named("PatchPage");
                // Settings: General / Data / About
                vm.NavigateTabCommand.Execute("settings"); window.UpdateLayout(); PumpFixture(200);
                var settingsTabs = FindVisualChildren<TabControl>(window).First(tc => tc.Items.Count >= 3);
                for (var tab = 0; tab < settingsTabs.Items.Count; tab++) { settingsTabs.SelectedIndex = tab; Scan("settings tab " + tab, Named("SettingsScrollViewer")); }
                // CSV editor: empty, loaded with a warning row, dirty, preview, filter/scope options, errors
                vm.NavigateTabCommand.Execute("editcsv"); Scan("csv empty", CsvScope());
                var rows = new List<CsvEditorRow>
                {
                    new() { Index = 1, Key = "k1", SourceText = "Hello, {name}.", Translation = "Xin chào.", IssueLabel = "placeholder mismatch", IssueDisplay = "Mất/sai placeholder {…}" },
                    new() { Index = 2, Key = "k2", SourceText = "Bye.", Translation = "Tạm biệt.", IssueLabel = "review_only", IssueDisplay = "Trong review_only.csv (cần xem lại thủ công)" },
                    new() { Index = 3, Key = "k3", SourceText = "Thanks.", Translation = "Cảm ơn." },
                };
                vm.TestLoadCsvRows(Path.Combine(packageA, "translation.csv"), rows, UiText.Msg("Cảnh báo: {0} dòng cần xem lại — {1}. Xem cột Trạng thái hoặc lọc “Chỉ dòng lỗi”.", 2, UiText.Msg("{0}× {1}", 1, UiText.Key("Mất/sai placeholder {…}"))));
                vm.TestSetCsvBulkPreview(UiText.Lines(UiText.Msg("Sẽ thay {0} lần trong {1} dòng ({2}).", 4, 3, UiText.Key("dòng đang lọc")), UiText.Msg("Trước: {0}\nSau: {1}", "Open the door.", "Open the gate.")));
                Scan("csv loaded + preview", CsvScope());
                vm.ToggleCsvBulkPreviewDetailCommand.Execute(null); vm.ToggleCsvBulkCommand.Execute(null); Scan("csv tools open + examples", CsvScope());
                rows[2].Translation = "Cảm ơn nhiều."; Scan("csv dirty", CsvScope());
                vm.TestSetCsvSaveError("file đã đổi bên ngoài"); Scan("csv save error", CsvScope());
                vm.TestSetCsvLoadError(Path.Combine(packageA, "translation.csv"), "CSV trống"); Scan("csv load error", CsvScope());
                // Patch: idle / valid / blocked / delivery
                vm.NavigateTabCommand.Execute("patch"); picker.TranslationCsv = Path.Combine(packageA, "translation.csv");
                vm.ValidateTranslationCsvCommand.Execute(null); Scan("patch validated", PatchScope());
                vm.ChooseTranslationCsvCommand.Execute(null); vm.TestSetPatchDelivery("Gói patch có installer — VNTextPatchInstaller.exe", "Created at C:\\Out\\Patch_A"); Scan("patch ready + delivery", PatchScope());
                picker.TranslationCsv = Path.Combine(packageB, "translation.csv"); vm.ChooseTranslationCsvCommand.Execute(null); Scan("patch blocked", PatchScope());
                vm.TestSetTranslationCsvPath(Path.Combine(packageA, "translation.csv")); Scan("patch source changed", PatchScope());
                // glossary overlay content is part of the window tree; Journal; release notes; confirmation dialogs
                if (window.FindName("GlossaryOverlay") is FrameworkElement glossary) Scan("glossary", glossary);
                Directory.CreateDirectory(vm.JournalStore.Root);
                File.WriteAllText(Path.Combine(vm.JournalStore.Root, "app.log." + DateTime.Now.ToString("yyyy-MM-dd")), "2026-10-31 10:00:00 +07:00 INFO alpha\n", System.Text.Encoding.UTF8);
                var journal = new JournalWindow(window, vm); journal.Show(); journal.UpdateLayout(); PumpFixture(200);
                Scan("journal", journal);
                var regexToggle = FindVisualChildren<ToggleButton>(journal).First(b => b.Content is string);
                var query = FindVisualChildren<TextBox>(journal).First(b => !b.IsReadOnly);
                query.Text = "["; regexToggle.IsChecked = true; PumpFixture(150); Scan("journal regex error", journal);
                journal.Close();
                var notes = new UpdateWindow(window, new FixtureUpdatePresentation(), notesOnly: true); notes.Show(); notes.UpdateLayout(); PumpFixture(200);
                Scan("release notes", notes);
                notes.Close();
                foreach (var (message, caption, buttons) in new[]
                {
                    ("CSV có thay đổi chưa lưu. Lưu trước khi mở lại hoặc chọn file khác?", "Thay đổi CSV chưa lưu", MessageBoxButton.YesNoCancel),
                    ("Thay thế 4 lần trong 3 dòng?\n\nTìm: cửa\nThay bằng: cổng\nChỉ sửa cột Bản dịch; cột Nguyên bản/key giữ nguyên.\nỨng dụng sẽ tạo bản lưu khôi phục và kiểm tra file sau khi lưu.", "Xác nhận thay thế hàng loạt", MessageBoxButton.YesNo),
                    ("Khôi phục CSV về trước lần thay thế hàng loạt gần nhất?", "Xác nhận hoàn tác", MessageBoxButton.YesNo),
                    ("Xóa tệp nhật ký app.log.2026-10-31?", "Nhật ký", MessageBoxButton.YesNo),
                })
                {
                    var dialog = AppDialogService.Build(message, caption, buttons, MessageBoxImage.Question, window, _ => { });
                    dialog.Show(); dialog.UpdateLayout(); PumpFixture(120);
                    Scan("dialog: " + (caption.Length > 24 ? caption[..24] : caption), dialog);
                    dialog.Close();
                }
                // Vietnamese stays the original text after switching back
                vm.Language = "vi"; window.UpdateLayout(); PumpFixture(250);
                var statusText = FindVisualChildren<TextBlock>(window).Select(b => b.Text).ToList();
                Require(statusText.Contains("Tìm và thay thế bản dịch") || statusText.Contains("Dịch tự động"), "Vietnamese labels are back after switching language");
                var first = new SortedDictionary<string, string>(StringComparer.Ordinal);
                foreach (var (state, set) in offenders) foreach (var s in set) first.TryAdd(s, state);
                var summary = string.Join("\n", first.Select(kv => "[" + kv.Value + "] " + kv.Key.Replace("\n", "\\n")));
                if (inventoryOnly) { File.WriteAllText(@"C:\v\DEV_RUN\gatec\english_inventory.txt", "INVENTORY (" + states + " states, " + first.Count + " distinct strings)\n" + summary, new System.Text.UTF8Encoding(false)); Console.WriteLine("inventory written: " + first.Count); exitCode = 0; }
                else
                {
                    Require(offenders.Count == 0, "English pages still show Vietnamese app text:\n" + summary);
                    Console.WriteLine("WPF English pages fixture: PASS (" + states + " states: Settings General/Data/About, CSV empty/loaded/dirty/errors, Patch states, Glossary, Journal, release notes, dialogs)");
                    exitCode = 0;
                }
                window.Close(); app.Shutdown();
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); exitCode = 1; }
            finally { try { Directory.Delete(root, true); } catch { } }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        return exitCode;
    }
}
