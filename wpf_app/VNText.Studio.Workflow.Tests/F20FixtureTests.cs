using System.IO;
using System.Windows;
using System.Windows.Controls;
using VNText.Studio.App;
using VNText.Studio.App.Controls;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    /// <summary>full20 F4/F5: bulk-replace counts pluralise independently (VI unchanged, EN time/times + row/rows) and the Translate/Patch log collapses to a hint only while empty and idle.</summary>
    private static int RunF20Fixture()
    {
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            try
            {
                var root = Environment.GetEnvironmentVariable("VNTEXT_LOCALAPPDATA") ?? throw new InvalidOperationException("isolated root required");
                Require(Path.GetFullPath(root).Contains(Path.DirectorySeparatorChar + "TEST_RUN" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "the fixture needs the TEST_RUN isolation");
                var app = new VNText.Studio.App.App();
                app.InitializeComponent();
                app.ShutdownMode = ShutdownMode.OnExplicitShutdown;
                try
                {
                    var cases = new (long m, long r, string en, string vi)[]
                    {
                        (1, 1, "Will replace once in 1 row (filtered rows).", "Sẽ thay 1 lần trong 1 dòng (filtered rows)."),
                        (2, 1, "Will replace 2 times in 1 row (filtered rows).", "Sẽ thay 2 lần trong 1 dòng (filtered rows)."),
                        (1, 2, "Will replace once in 2 rows (filtered rows).", "Sẽ thay 1 lần trong 2 dòng (filtered rows)."),
                        (2, 2, "Will replace 2 times in 2 rows (filtered rows).", "Sẽ thay 2 lần trong 2 dòng (filtered rows)."),
                    };
                    foreach (var language in new[] { "en", "vi" })
                    {
                        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        vm.Language = language; UiText.SetLanguage(language);
                        foreach (var c in cases)
                        {
                            var text = UiText.TranslateDynamic(MainViewModel.BulkReplaceMsg("Sẽ thay {M} lần trong {R} dòng ({T0}).", c.m, c.r, "filtered rows"));
                            Require(text == (language == "en" ? c.en : c.vi), $"F4 {language} {c.m}/{c.r}: '{text}'");
                            var confirm = UiText.TranslateDynamic(MainViewModel.BulkReplaceMsg("Thay thế {M} lần trong {R} dòng?", c.m, c.r));
                            var done = UiText.TranslateDynamic(MainViewModel.BulkReplaceMsg("Đã thay {M} lần trong {R} dòng. Có thể hoàn tác; đã tạo bản lưu khôi phục.", c.m, c.r));
                            if (language == "en")
                            {
                                Require(confirm == $"Replace {(c.m == 1 ? "once" : c.m + " times")} in {(c.r == 1 ? "1 row" : c.r + " rows")}?", "F4 en confirm " + confirm);
                                Require(done.StartsWith($"Replaced {(c.m == 1 ? "once" : c.m + " times")} in {(c.r == 1 ? "1 row" : c.r + " rows")}."), "F4 en success " + done);
                            }
                            else Require(confirm == $"Thay thế {c.m} lần trong {c.r} dòng?", "F4 vi confirm " + confirm);
                        }
                        vm.Language = "vi"; UiText.SetLanguage("vi"); vm.Dispose();
                    }

                    foreach (var (language, theme, scale) in new[] { ("vi", "light", 1.0), ("en", "dark", 1.2) })
                    {
                        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        vm.Language = language; vm.Theme = theme; vm.UiScale = scale;
                        vm.NavigateTabCommand.Execute("translate");
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal; window.Width = 1043; window.Height = 720;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1") { window.WindowStartupLocation = WindowStartupLocation.Manual; window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false; }
                        window.Show(); window.UpdateLayout(); PumpFixture(250);
                        FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                        var tag = $"{language}/{theme}/UI{scale * 100:0}";
                        Require(Named("TranslateLogEmptyHint").IsVisible && !Named("TranslateLogBody").IsVisible, tag + ": F5 empty + idle collapses the log body to a hint");
                        vm.TestSetBusy(true); window.UpdateLayout(); PumpFixture(120);
                        Require(!Named("TranslateLogEmptyHint").IsVisible && Named("TranslateLogBody").IsVisible && Math.Abs(Named("TranslateLogBody").ActualHeight - 220) < 0.5, tag + ": F5 busy keeps the 220 DIP log");
                        vm.TestSetBusy(false); vm.TranslateLogLines.Add("[00:00:00] hello"); window.UpdateLayout(); PumpFixture(120);
                        Require(!Named("TranslateLogEmptyHint").IsVisible && Named("TranslateLogBody").IsVisible && Math.Abs(Named("TranslateLogBody").ActualHeight - 220) < 0.5, tag + ": F5 with entries keeps the 220 DIP log");
                        vm.TranslateLogLines.Clear(); window.UpdateLayout(); PumpFixture(120);
                        Require(Named("TranslateLogEmptyHint").IsVisible && !Named("TranslateLogBody").IsVisible, tag + ": F5 cleared + idle returns to the hint");
                        window.Close(); vm.Language = "vi"; vm.Theme = "light"; vm.UiScale = 1; vm.Dispose();
                    }
                    {
                        // F5 (Root correction): a stale no-match overlay must never cover a read failure or the no-file state (owned fixture log only).
                        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal; window.Width = 1043; window.Height = 720;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1") { window.WindowStartupLocation = WindowStartupLocation.Manual; window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false; }
                        window.Show(); window.UpdateLayout(); PumpFixture(200);
                        Directory.CreateDirectory(vm.JournalStore.Root);
                        var logPath = Path.Combine(vm.JournalStore.Root, "app.log." + DateTime.Now.ToString("yyyy-MM-dd"));
                        Require(Path.GetFullPath(logPath).Contains(Path.DirectorySeparatorChar + "TEST_RUN" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "the Journal fixture log lives in the TEST_RUN isolation");
                        File.WriteAllText(logPath, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff zzz") + " INFO alpha line one" + Environment.NewLine);
                        var journal = new JournalWindow(window, vm);
                        journal.Show(); journal.UpdateLayout(); PumpFixture(250);
                        var queryBox = FindVisualChildren<TextBox>(journal).First(b => b.ToolTip as string == "Tìm trong nhật ký");
                        bool NoMatchShown() => FindVisualChildren<TextBlock>(journal).Any(t => t.IsVisible && t.Text.StartsWith("Không có bản ghi khớp", StringComparison.Ordinal));
                        bool EmptyShown() => FindVisualChildren<TextBlock>(journal).Any(t => t.IsVisible && t.Text.StartsWith("Chưa có bản ghi nào", StringComparison.Ordinal));
                        queryBox.Text = "zzz-none"; PumpFixture(150);
                        Require(NoMatchShown(), "F5: the filter with no match says so");
                        using (var locked = new FileStream(logPath, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
                        {
                            queryBox.Text = "zzz-none-2"; PumpFixture(150);
                            Require(!NoMatchShown() && !EmptyShown(), "F5: a read failure is not covered by a stale no-match overlay");
                            var logBox = FindVisualChildren<VNText.Studio.App.Controls.SeverityLogBox>(journal).First(b => b.IsReadOnly);
                            Require(logBox.Text.Contains("Không đọc được nhật ký", StringComparison.Ordinal), "F5: the read failure message is visible");
                        }
                        queryBox.Text = "alpha"; PumpFixture(150);
                        Require(!NoMatchShown() && !EmptyShown(), "F5: after the lock is released the log reads again");
                        queryBox.Text = "zzz-none"; PumpFixture(150);
                        Require(NoMatchShown(), "F5: no-match again");
                        File.Delete(logPath);
                        FindVisualChildren<Button>(journal).First(b => b.Content as string == "Làm mới").Command?.Execute(null);
                        var refresh = FindVisualChildren<Button>(journal).First(b => b.Content as string == "Làm mới");
                        refresh.RaiseEvent(new RoutedEventArgs(Button.ClickEvent)); PumpFixture(250);
                        Require(!NoMatchShown(), "F5: the no-file state is not covered by a stale no-match overlay");
                        journal.Close(); window.Close(); vm.Dispose();
                    }
                    {
                        // F2 (Root correction): the in-grid translation editor of a very long text is bounded and scrolls its own text (keyboard reaches the end), the data is untouched.
                        var host = new Window { Width = 400, Height = 300, ShowActivated = false, ShowInTaskbar = false, WindowStartupLocation = WindowStartupLocation.Manual, Left = -4000, Top = 0 };
                        var panel = new ImageWorkspacePanel();
                        var longText = string.Join(" ", Enumerable.Repeat("Bảng thông báo ghi rõ từng quy định của ngôi làng rất chi tiết, hãy đọc kỹ từng dòng trước khi rời đi.", 8));
                        var editor = new TextBox { Style = (Style)panel.FindResource("RegionTranslationEditor"), Text = longText, Width = 170 };
                        host.Content = editor; host.Show(); host.UpdateLayout(); PumpFixture(150);
                        var scroller = (ScrollViewer)editor.Template.FindName("PART_ContentHost", editor);
                        Require(editor.ActualHeight <= 112.5, "F2: the long-translation editor is bounded (" + editor.ActualHeight + ")");
                        Require(scroller.VerticalScrollBarVisibility == ScrollBarVisibility.Auto && scroller.ScrollableHeight > 0, "F2: the bounded editor scrolls its own text (" + scroller.ScrollableHeight + ")");
                        editor.Focus(); editor.CaretIndex = editor.Text.Length; editor.ScrollToEnd(); host.UpdateLayout(); PumpFixture(100);
                        Require(scroller.VerticalOffset >= scroller.ScrollableHeight - 1 && editor.Text == longText, "F2: the end of the full text is reachable and the data is unchanged");
                        host.Close();
                    }
                    {
                        // F21: the Glossary row buttons/tooltips and detail labels re-localize live (existing rows included) on every VI<->EN switch; one mapping serves status and step.
                        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        vm.GlossaryEntries.Clear(); vm.GlossaryEntries.Add(new GlossaryItem("Start", "Bắt đầu")); vm.GlossaryEntries.Add(new GlossaryItem("Quit", "Thoát"));
                        vm.NavigateTabCommand.Execute("translate");
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal; window.Width = 1043; window.Height = 900;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1") { window.WindowStartupLocation = WindowStartupLocation.Manual; window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false; }
                        window.Show(); window.UpdateLayout(); PumpFixture(250);
                        ((Button)window.FindName("GlossaryEditButton")!).RaiseEvent(new RoutedEventArgs(System.Windows.Controls.Primitives.ButtonBase.ClickEvent)); window.UpdateLayout(); PumpFixture(250); window.UpdateLayout();
                        var list = (ListBox)window.FindName("GlossaryListBox")!;
                        list.SelectedIndex = 0; window.UpdateLayout(); PumpFixture(150);
                        string RowDelete() => (string)FindVisualChildren<Button>((ListBoxItem)list.ItemContainerGenerator.ContainerFromIndex(1)).First(b => b.Command == vm.RemoveGlossaryEntryCommand).Content;
                        object RowTip() => FindVisualChildren<Button>((ListBoxItem)list.ItemContainerGenerator.ContainerFromIndex(1)).First(b => b.Command == vm.RemoveGlossaryEntryCommand).ToolTip;
                        var strip = (FrameworkElement)window.FindName("GlossaryDetailStrip")!;
                        List<string> Labels() => FindVisualChildren<TextBlock>(strip).Select(t => t.Text).ToList();
                        Require(RowDelete() == "Xóa" && (string)RowTip() == "Xóa thuật ngữ này" && Labels().Contains("Từ trong game") && Labels().Contains("Dịch thành"), "F21: VI labels unchanged");
                        foreach (var lang in new[] { "en", "vi", "en" })
                        {
                            vm.Language = lang; PumpFixture(150); window.UpdateLayout(); PumpFixture(100);
                            var en = lang == "en";
                            Require(RowDelete() == (en ? "Delete" : "Xóa") && (string)RowTip() == (en ? "Remove this term" : "Xóa thuật ngữ này"), "F21: existing row button/tooltip follow " + lang + " (" + RowDelete() + ")");
                            Require(Labels().Contains(en ? "In-game term" : "Từ trong game") && Labels().Contains(en ? "Translation" : "Dịch thành") && !Labels().Contains(en ? "Từ trong game" : "In-game term"), "F21: detail labels follow " + lang);
                        }
                        vm.GlossaryEntries.Add(new GlossaryItem("New", "Mới")); window.UpdateLayout(); PumpFixture(150);
                        Require(FindVisualChildren<Button>((ListBoxItem)list.ItemContainerGenerator.ContainerFromIndex(2)).First(b => b.Command == vm.RemoveGlossaryEntryCommand).Content as string == "Delete", "F21: a row added in English is English");
                        Require(vm.GlossaryEntries[0].Term == "Start" && vm.GlossaryEntries[0].Translation == "Bắt đầu", "F21: glossary data untouched");
                        // status and step share one mapping; unmapped (real warning/error) text passes through
                        UiText.SetLanguage("en");
                        var status = new VNText.Studio.App.Converters.UiTextConverter().Convert("Đang dịch offline…", typeof(string), "", System.Globalization.CultureInfo.InvariantCulture);
                        var step = new VNText.Studio.App.Converters.UiTextFormatConverter { SemanticArgument = true }.Convert("Đang dịch offline…", typeof(string), "Bước: {0}", System.Globalization.CultureInfo.InvariantCulture);
                        var warn = new VNText.Studio.App.Converters.UiTextConverter().Convert("Cảnh báo giả: không có bản dịch", typeof(string), "", System.Globalization.CultureInfo.InvariantCulture);
                        Require((string)status == "Translating offline…" && (string)step == "Step: Translating offline…" && (string)warn == "Cảnh báo giả: không có bản dịch", "F21: EN status/step '" + status + "' / '" + step + "'; unmapped text kept");
                        vm.TestShowTranslateRunningState(7, 7);
                        Require(UiText.TranslateDynamic(vm.CsvValidationMessage) == "Translating — 7/7 rows already have a safe earlier translation; new results appear when the task finishes.", "F21: the running-state line is English: " + UiText.TranslateDynamic(vm.CsvValidationMessage));
                        UiText.SetLanguage("vi");
                        Require((string)new VNText.Studio.App.Converters.UiTextConverter().Convert("Đang dịch offline…", typeof(string), "", System.Globalization.CultureInfo.InvariantCulture) == "Đang dịch offline…", "F21: VI status unchanged");
                        vm.Language = "vi"; vm.GlossaryEntries.Clear(); window.Close(); vm.Dispose();
                    }
                    {
                        // f23 A2: a loaded, settled document with zero filtered rows says so and offers the reset; no document / loading / empty document do not show it.
                        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        vm.UiScale = 1.2; vm.NavigateTabCommand.Execute("editcsv");
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal; window.Width = 1043; window.Height = 720;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1") { window.WindowStartupLocation = WindowStartupLocation.Manual; window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false; }
                        window.Show(); window.UpdateLayout(); PumpFixture(250);
                        FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                        Require(!Named("CsvNoMatchHint").IsVisible, "A2: no document -> no no-match hint");
                        Console.Error.WriteLine("A2 step 0"); var rows = Enumerable.Range(1, 7).Select(i => new CsvEditorRow { Index = i, Key = "k" + i, SourceText = "Hello " + i, Translation = "Xin chào " + i }).ToList();
                        vm.TestLoadCsvRows(Path.Combine(Path.GetTempPath(), "translation.csv"), rows, "OK"); window.UpdateLayout(); PumpFixture(250);
                        Require(!Named("CsvNoMatchHint").IsVisible && vm.CsvEditorVisibleCount == 7, "A2: 7/7 rows shown -> no hint");
                        Console.Error.WriteLine("A2 step 1"); vm.CsvEditorRows[2].IsSelected = true;
                        vm.CsvEditorRows[1].Translation = "Đã sửa"; vm.OnCsvEditorTranslationChanged(vm.CsvEditorRows[1]);
                        Console.Error.WriteLine("A2 step 2"); var dirtyBefore = vm.CsvEditorDirty; var selectedBefore = vm.CsvEditorRows.Count(r => r.IsSelected);
                        Require(dirtyBefore, "A2 precondition: an unsaved edit exists");
                        Console.Error.WriteLine("A2 step 3"); foreach (var lang in new[] { "vi", "en" })
                        {
                            vm.Language = lang; PumpFixture(120);
                            var en = lang == "en";
                            // query with no match
                            Console.Error.WriteLine("A2 step 4"); vm.CsvFilterMode = CsvFilterModes.All; vm.CsvEditorSearch = "zzz-none"; window.UpdateLayout(); PumpFixture(150);
                            Require(Named("CsvNoMatchHint").IsVisible && vm.CsvEditorVisibleCount == 0, "A2 " + lang + ": query with no match shows the hint");
                            Require(((Button)Named("CsvClearFiltersButton")).IsEnabled, "A2: reset button becomes enabled when no-match appears");
                            Require(((TextBlock)Named("CsvNoMatchText")).Text == (en ? "No matching rows found." : "Không tìm thấy dòng phù hợp."), "A2 " + lang + ": hint text '" + ((TextBlock)Named("CsvNoMatchText")).Text + "'");
                            Require(((Button)Named("CsvClearFiltersButton")).Content as string == (en ? "Clear search and filters" : "Xóa tìm kiếm và bộ lọc"), "A2 " + lang + ": action label");
                            // status filter with no match (all 7 rows are valid, so "errors only" is empty)
                            Console.Error.WriteLine("A2 step 5"); vm.CsvEditorSearch = ""; vm.CsvFilterMode = CsvFilterModes.Errors; window.UpdateLayout(); PumpFixture(150);
                            Require(Named("CsvNoMatchHint").IsVisible && ((TextBlock)Named("CsvNoMatchText")).Text == (en ? "No rows in the current filter." : "Không có dòng nào trong bộ lọc hiện tại."), "A2 " + lang + ": status filter with no match");
                            // combined
                            vm.CsvEditorSearch = "zzz-none"; window.UpdateLayout(); PumpFixture(100);
                            Require(Named("CsvNoMatchHint").IsVisible, "A2 " + lang + ": combined filters");
                            Require(vm.CsvEditorRows.Count == 7 && vm.CsvEditorDirty == dirtyBefore && vm.CsvEditorRows.Count(r => r.IsSelected) == selectedBefore && vm.CsvEditorRows[1].Translation == "Đã sửa", "A2 " + lang + ": document, dirty edit and selection untouched while filtered");
                            Console.Error.WriteLine("A2 step 6"); vm.ClearCsvFiltersCommand.Execute(null); window.UpdateLayout(); PumpFixture(200);
                            Require(!Named("CsvNoMatchHint").IsVisible && vm.CsvEditorVisibleCount == 7 && vm.CsvEditorSearch == "" && vm.CsvFilterMode == CsvFilterModes.All, "A2 " + lang + ": reset restores 7/7");
                            Require(vm.CsvEditorDirty == dirtyBefore && vm.CsvEditorRows.Count(r => r.IsSelected) == selectedBefore && vm.CsvEditorRows[1].Translation == "Đã sửa" && vm.CsvEditorRows.Count == 7, "A2 " + lang + ": reset keeps dirty edits, selection and the document");
                        }
                        vm.Language = "vi"; vm.TestClearCsvDirty(); window.Close(); vm.Dispose();
                    }
                    {
                        // Design QA: the resource failure is summarised once inside the Settings > Data card; the page banner never pushes the Settings header/tabs; Patch font group states.
                        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        vm.NavigateTabCommand.Execute("settings"); vm.UiScale = 1.2;
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal; window.Width = 1043; window.Height = 720;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1") { window.WindowStartupLocation = WindowStartupLocation.Manual; window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false; }
                        window.Show(); window.UpdateLayout(); PumpFixture(250);
                        FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                        double HeaderTop() { var h = FindVisualChildren<SettingsHeaderPanel>(window).First(p => p.IsVisible); return h.TranslatePoint(new Point(0, 0), window).Y; }
                        var tabs = FindVisualChildren<TabControl>(window).First(x => x.IsVisible);
                        var tops = new List<double>();
                        foreach (var i in new[] { 0, 1, 2 }) { tabs.SelectedIndex = i; window.UpdateLayout(); PumpFixture(120); tops.Add(HeaderTop()); }
                        Require(tops.All(t => Math.Abs(t - tops[0]) < 0.5), "DQ3: header stays put across the three tabs " + string.Join("/", tops));
                        vm.RecordPersistentError("resources", "SDK boom missing"); tabs.SelectedIndex = 1; window.UpdateLayout(); PumpFixture(200);
                        Require(Math.Abs(HeaderTop() - tops[0]) < 0.5, "DQ3: a resource error does not move the header (" + HeaderTop() + " vs " + tops[0] + ")");
                        Require(!Named("ExtractErrorBanner").IsVisible && Named("ResourceErrorActions").IsVisible, "DQ3: no banner above the header; the card carries the diagnostics actions");
                        var statusText = ((TextBlock)Named("ResourceStatusText")).Text;
                        Require(statusText.Split(new[] { "boom" }, StringSplitOptions.None).Length - 1 <= 1, "DQ3: the cause is not repeated in the card status: " + statusText);
                        foreach (var lang in new[] { "en", "vi" })
                        {
                            vm.Language = lang; PumpFixture(100); window.UpdateLayout();
                            var buttons = FindVisualChildren<Button>(Named("ResourceErrorActions")).Select(b => b.Content as string).ToList();
                            Require(buttons.Contains(lang == "en" ? "View diagnostics" : "Xem chẩn đoán") && buttons.Contains(lang == "en" ? "Copy error" : "Chép lỗi"), "DQ3 " + lang + ": actions " + string.Join("|", buttons));
                        }
                        vm.TestSetResourceStatus("Còn thiếu hoặc hỏng tài nguyên." + Environment.NewLine + "renpy: Chưa sẵn sàng · Chưa tải Ren'Py SDK 8.5.3");
                        Require(vm.ResourceStatusAlreadyStates("renpy: Chưa tải Ren'Py SDK 8.5.3") && vm.ResourceStatusAlreadyStates("Chưa tải Ren'Py SDK 8.5.3") && !vm.ResourceStatusAlreadyStates("Lỗi mạng khác"), "DQ3: an error already stated by the per-resource line is not appended again, a different one is");
                        // Patch font group
                        vm.NavigateTabCommand.Execute("patch"); vm.Language = "vi"; window.UpdateLayout(); PumpFixture(200);
                        Require(vm.PatchFontModeText == "Font Việt đi kèm (mặc định)" && vm.PatchFontStateText.StartsWith("Chưa kiểm — chọn game/asset", StringComparison.Ordinal) && !vm.PatchFontNoticeVisible, "DQ4: default font, no source, no notice");
                        Require(Named("PatchFontGroup").IsVisible && Named("PatchFontModeText").IsVisible && Named("PatchFontStateText").IsVisible, "DQ4: the Vietnamese font group is drawn");
                        vm.ResetPatchFontCommand.Execute(null); window.UpdateLayout(); PumpFixture(100);
                        Require(vm.PatchFontNotice == "Đã chọn: Font Việt đi kèm." && Named("PatchFontNoticeText").IsVisible, "DQ4: choosing the bundled font is confirmed in place");
                        var srcDir = Path.Combine(Path.GetTempPath(), "dq4-src-" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(srcDir);
                        try
                        {
                            vm.InputPath = srcDir; PumpFixture(80);
                            Require(vm.PatchFontStateText.StartsWith("Chưa kiểm — chọn CSV hợp lệ", StringComparison.Ordinal), "DQ4: with a source but no valid CSV the state names the missing step: " + vm.PatchFontStateText);
                        }
                        finally { vm.InputPath = ""; Directory.Delete(srcDir, true); }
                        vm.Language = "en"; PumpFixture(100); window.UpdateLayout();
                        Require(((TextBlock)Named("PatchFontModeText")).Text == "Bundled Vietnamese font (default)" && ((TextBlock)Named("PatchFontNoticeText")).Text == "Selected: bundled Vietnamese font.", "DQ4 en: labels follow the language");
                        vm.Language = "vi"; window.Close(); vm.Dispose();
                    }
                    Console.WriteLine("WPF F20 fixture: PASS (F4 counts VI/EN 1/1 2/1 1/2 2/2; F5 hint/body empty, busy, entries, cleared)");
                    exitCode = 0;
                }
                finally { app.Shutdown(); }
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); }
        });
        thread.SetApartmentState(ApartmentState.STA); thread.Start(); thread.Join();
        return exitCode;
    }
}
