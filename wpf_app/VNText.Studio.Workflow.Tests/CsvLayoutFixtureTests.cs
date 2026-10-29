using System.IO;
﻿using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using VNText.Studio.App;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    /// <summary>Real MainWindow at the reviewed small presentation: 1565x1080 physical at OS 150% = 1043x720 DIP, with UI scale 120% (the content sees 720/1.2 DIP).</summary>
    private static int RunCsvLayoutFixture()
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
                var worker = new PythonWorkerHost();
                var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false);
                vm.UiScale = 1.2;   // the reviewed UI scale: the content is laid out at 1/1.2 of the window
                vm.NavigateTabCommand.Execute("editcsv");
                var window = new MainWindow(vm, new FixtureUpdatePresentation());
                try
                {
                    window.WindowState = WindowState.Normal;
                    window.Width = 1043;
                    window.Height = 720;
                    window.Show();
                    window.UpdateLayout();
                    PumpFixture(250);
                    FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                    var grid = (DataGrid)Named("CsvEditorGrid");

                    Require(Named("CsvEmptyState").IsVisible && Named("CsvEmptyChooseButton").IsVisible, "empty CSV shows its instruction and the Chọn CSV action");
                    Require(!Named("CsvBulkReplacePanel").IsVisible && !Named("CsvBulkSummary").IsVisible && !grid.IsVisible && !Named("CsvChooseHeaderButton").IsVisible,
                        "no CSV: bulk tools, table and the duplicate header action stay hidden");
                    var emptyHeight = Named("CsvEmptyState").ActualHeight;

                    vm.TestSetCsvEditorPath(Path.Combine(Path.GetTempPath(), "translation.csv"));
                    window.UpdateLayout();
                    PumpFixture(150);
                    Require(!vm.CsvBulkExpanded && Named("CsvBulkSummary").IsVisible && !Named("CsvBulkReplacePanel").IsVisible, "low height starts with the tools collapsed to ONE visible summary row");
                    Require(Named("CsvBulkOpenButton").IsVisible && Named("CsvBulkOpenButton").ActualHeight >= 29.5, "the collapsed summary has an explicit open button");
                    Require(grid.IsVisible && !Named("CsvEmptyState").IsVisible, "a loaded CSV shows the table, not the empty state");
                    Require(grid.ActualHeight >= 150, "the table keeps a finite viewport of at least three rows plus the header (got " + grid.ActualHeight + ")");
                    Require(Math.Abs(grid.ActualHeight - emptyHeight) <= Math.Max(60, emptyHeight * 0.5), "the table viewport does not jump against the empty state");

                    vm.CsvBulkFind = "cửa";
                    vm.CsvBulkReplace = "cổng";
                    vm.ToggleCsvBulkCommand.Execute(null);
                    window.UpdateLayout();
                    PumpFixture(100);
                    Require(vm.CsvBulkExpanded && Named("CsvBulkReplacePanel").IsVisible && !Named("CsvBulkSummary").IsVisible, "the open action expands the tools");
                    Require(Named("CsvBulkScopeComboBox").Height == 36, "bulk scope select is the 36 DIP standard size");
                    vm.ToggleCsvBulkCommand.Execute(null);
                    window.UpdateLayout();
                    PumpFixture(100);
                    Require(!vm.CsvBulkExpanded && vm.CsvBulkFind == "cửa" && vm.CsvBulkReplace == "cổng", "collapsing keeps the typed find/replace text");
                    vm.CsvFilterMode = "untranslated";
                    vm.CsvEditorSearch = "x";
                    PumpFixture(50);
                    Require(!vm.CsvBulkExpanded && vm.CsvBulkFind == "cửa", "filtering and searching neither expand nor reset the tools");
                    // ---- native stylefixed3 findings: a retained preview and a warning row at the same small size ----
                    CsvEditorRow Row(int index, string source, string translation, string label, string display) =>
                        new() { Index = index, Key = "k" + index, SourceText = source, Translation = translation, IssueLabel = label, IssueDisplay = display };
                    const string placeholderDisplay = "Mất/sai placeholder {…}";
                    var rows = new List<CsvEditorRow>
                    {
                        Row(1, "Hello, {name}.", "Xin chào, {name}.", "", ""),
                        Row(2, "Open the door.", "Hãy mở cửa.", "", ""),
                        Row(3, "The door is old.", "Cánh cửa đã cũ.", "", ""),
                        Row(4, "Bye, {name}.", "Tạm biệt.", "placeholder mismatch", placeholderDisplay),
                        Row(5, "Thanks.", "Cảm ơn.", "", ""),
                        Row(6, "Sorry.", "Xin lỗi.", "", ""),
                    };
                    var warning = "Cảnh báo: 1 dòng cần xem lại — 1× Mất/sai placeholder {...}. Xem cột Trạng thái hoặc lọc “Chỉ dòng lỗi”.";
                    var examples = "Sẽ thay 4 lần trong 3 dòng (dòng đang lọc).\nTrước: Hãy mở cửa.\nSau: Hãy mở cổng.\nTrước: Cánh cửa đã cũ và cửa rất nặng.\nSau: Cánh cổng đã cũ và cổng rất nặng.\nTrước: Hãy đóng cửa khi bạn rời đi.\nSau: Hãy đóng cổng khi bạn rời đi.";
                    vm.CsvFilterMode = "all";
                    vm.CsvEditorSearch = "";
                    vm.TestLoadCsvRows(Path.Combine(Path.GetTempPath(), "translation.csv"), rows, warning);
                    vm.TestSetCsvBulkPreview(examples);
                    window.UpdateLayout();
                    PumpFixture(200);
                    Require(!vm.CsvBulkExpanded, "the tools are still collapsed");
                    // Finding 1: the collapsed state keeps ONE preview line; the examples need the explicit button.
                    var summaryText = Named("CsvBulkPreviewSummaryText");
                    Require(summaryText.IsVisible && ((TextBlock)summaryText).Text == "Sẽ thay 4 lần trong 3 dòng (dòng đang lọc).", "the preview summary (count of replacements/rows) stays visible");
                    Require(!Named("CsvBulkPreviewScroll").IsVisible, "the Trước/Sau examples are closed by default after a preview");
                    Require(Named("CsvBulkPreviewDetailButton").IsVisible && vm.CsvBulkPreview == examples, "the explicit examples button exists and the preview text is untouched");
                    int VisibleRows()
                    {
                        var gridBottom = grid.TranslatePoint(new Point(0, grid.ActualHeight), window).Y;
                        var limit = Math.Min(gridBottom, window.ActualHeight) + 0.5;
                        var count = 0;
                        for (var i = 0; i < rows.Count; i++)
                            if (grid.ItemContainerGenerator.ContainerFromIndex(i) is DataGridRow { IsVisible: true } dataRow
                                && dataRow.TranslatePoint(new Point(0, dataRow.ActualHeight), window).Y <= limit) count++;
                        return count;
                    }
                    Require(grid.TranslatePoint(new Point(0, grid.ActualHeight), window).Y <= window.ActualHeight, "the table ends inside the window");
                    var rowsShown = VisibleRows();
                    Require(rowsShown >= 3, "at least three ordinary rows stay visible after preview + collapse (got " + rowsShown + ", items " + grid.Items.Count + ", gridH " + grid.ActualHeight + ", c0 " + (grid.ItemContainerGenerator.ContainerFromIndex(0) is null ? "null" : "ok") + ", winH " + window.ActualHeight + ")");
                    var warningRow = (DataGridRow)grid.ItemContainerGenerator.ContainerFromIndex(3);
                    Require(warningRow.ActualHeight <= 40, "the placeholder warning row stays a single-line row (got " + warningRow.ActualHeight + ")");
                    // Finding 2: a short semantic label, the full diagnostic untouched.
                    AssertEqual("Sai placeholder", rows[3].IssueShort);
                    AssertEqual(placeholderDisplay, rows[3].IssueDisplay);
                    AssertEqual("placeholder mismatch", rows[3].IssueLabel);
                    AssertEqual("Sai số \\n", CsvEditorRow.ShortenIssue("Sai số \\n"));            // unknown/other diagnostics pass through unchanged
                    AssertEqual("Sai tag", CsvEditorRow.ShortenIssue("Hỏng tag <…>"));
                    Require(vm.CsvEditorValidationMessage == warning, "the full validation message is untouched");
                    // the examples open only on request, stay bounded, close with the collapse and never reopen on their own
                    vm.ToggleCsvBulkPreviewDetailCommand.Execute(null);
                    window.UpdateLayout();
                    PumpFixture(100);
                    Require(Named("CsvBulkPreviewScroll").IsVisible && Named("CsvBulkPreviewScroll").ActualHeight <= 120.5, "the examples open on the explicit action inside a bounded scroller");
                    var rowsWithExamples = VisibleRows();
                    Require(rowsWithExamples <= rowsShown, "opened examples never add table rows (" + rowsWithExamples + " vs " + rowsShown + ")");
                    vm.ToggleCsvBulkCommand.Execute(null);   // open the tools
                    vm.ToggleCsvBulkCommand.Execute(null);   // collapse again: the examples close, the preview data stays
                    window.UpdateLayout();
                    PumpFixture(100);
                    Require(!Named("CsvBulkPreviewScroll").IsVisible && vm.CsvBulkPreview == examples && vm.CsvBulkFind == "cửa", "collapsing closes the examples but keeps the preview and the typed text");
                    vm.ToggleCsvBulkPreviewDetailCommand.Execute(null);
                    vm.TestSetCsvBulkPreview(examples + "\nTrước: x\nSau: y");
                    Require(!vm.CsvBulkPreviewDetailOpen, "a new preview never opens its examples by surprise");
                    Console.WriteLine("WPF CSV low-height layout fixture: PASS (empty state, collapsed bulk tools, table viewport, 36 DIP selects, preview summary + examples toggle, short status label; rows visible after preview+collapse: " + rowsShown + ")");
                    exitCode = 0;
                }
                finally { window.Close(); UiText.SetLanguage("vi"); UiAppearance.Apply("light", 100); app.Shutdown(); }
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); exitCode = 1; }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        return exitCode;
    }

    private static void PumpFixture(int milliseconds)
    {
        var frame = new DispatcherFrame();
        var timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(milliseconds) };
        timer.Tick += (_, _) => { timer.Stop(); frame.Continue = false; };
        timer.Start();
        Dispatcher.PushFrame(frame);
    }
    private sealed class FixtureUpdatePresentation : IUpdatePresentation
    {
        public string CurrentVersion => "0.1.14"; public string Version => ""; public string ReleaseDate => ""; public string Notes => ""; public string Status => "";
        public bool Available => false; public bool Downloading => false; public bool Ready => false; public long Received => 0; public long Total => 0; public bool CanStart => false; public bool IsTestFixture => true;
        public event System.ComponentModel.PropertyChangedEventHandler? PropertyChanged { add { } remove { } }
        public event Action? OfferRequested { add { } remove { } }
        public Task CheckAsync() => Task.CompletedTask; public Task DownloadAsync() => Task.CompletedTask; public void Cancel() { }
        public void Defer(bool skip) { } public void Restart() { } public void Dispose() { }
    }
}
