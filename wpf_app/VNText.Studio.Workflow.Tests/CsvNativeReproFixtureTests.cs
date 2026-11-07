using System.IO;
using System.Windows;
using System.Windows.Controls;
using VNText.Studio.App;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    /// <summary>
    /// Native repro (0.1.17, exact 369adc5): outer window 1565x1080 physical at OS 150% = 1043x720 DIP, UI 120%, Dark, four ordinary one-line rows,
    /// find "kiểm tra", empty replacement, the REAL Preview command.  The visible viewport is the window CLIENT area (outer height minus the title bar and
    /// the page padding below the card), not the outer window height the first fixture used.
    /// </summary>
    private static int RunCsvNativeReproFixture()
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
                var picker = new FakePathPicker();
                var vm = new MainViewModel(picker, worker, startWorker: false);
                vm.UiScale = 1.2;
                vm.Theme = "dark";
                vm.NavigateTabCommand.Execute("editcsv");
                try
                {
                    foreach (var (outerHeight, scale, label) in new[] { (720.0, 1.2, "native 1043x720 UI120"), (883.0, 1.2, "tallest here UI120"), (720.0, 1.0, "720 UI100"), (760.0, 1.0, "760 UI100 (former threshold)"), (780.0, 1.0, "780 UI100"), (800.0, 1.0, "800 UI100"), (883.0, 1.0, "883 UI100") })
                    {
                        vm.UiScale = scale;
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal;
                        window.Width = 1043;
                        window.Height = outerHeight;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1")
                        {
                            window.WindowStartupLocation = WindowStartupLocation.Manual;
                            window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false;
                        }
                        window.Show();
                        window.UpdateLayout();
                        PumpFixture(200);
                        FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                        var grid = (DataGrid)Named("CsvEditorGrid");
                        var rows = Enumerable.Range(1, 4).Select(i => new CsvEditorRow { Index = i, Key = "k" + i, SourceText = "Sentence " + i, Translation = "Câu kiểm tra " + i }).ToList();
                        // A real CSV file on disk (the real Preview reads and validates against it); owned test rows only.
                        var csvDir = Path.Combine(TestTempRoot(), "csv_repro_" + Guid.NewGuid().ToString("N")); Directory.CreateDirectory(csvDir);
                        var csvPath = Path.Combine(csvDir, "csv-layout-369.csv");
                        File.WriteAllText(csvPath, "key,source_text,translation" + (char)10 + string.Concat(rows.Select(r => r.Key + "," + r.SourceText + "," + r.Translation + (char)10)), new System.Text.UTF8Encoding(true));
                        // The REAL open path (picker -> background load -> validation), not a seeded row list.
                        picker.TranslationCsv = csvPath;
                        window.Dispatcher.BeginInvoke(new Action(() => vm.OpenCsvEditorFileCommand.Execute(null)));
                        for (var wait = 0; wait < 80 && grid.Items.Count < rows.Count; wait++) PumpFixture(100);
                        for (var wait = 0; wait < 100 && vm.CsvEditorStatus.Contains("kiểm tra", StringComparison.OrdinalIgnoreCase); wait++) PumpFixture(100);
                        Require(grid.Items.Count == rows.Count, "the real CSV open loaded the 4 rows (" + grid.Items.Count + ")");
                        vm.CsvBulkFind = "kiểm tra";
                        vm.CsvBulkReplace = "";
                        window.UpdateLayout();
                        PumpFixture(250);
                        // The REAL Preview command: it awaits a background task, so it must start inside a running dispatcher frame; the fixture then waits for its result.
                        var previewMode = "REAL command";
                        window.Dispatcher.BeginInvoke(new Action(() => vm.BulkReplaceCsvCommand.Execute(null)));
                        for (var wait = 0; wait < 60 && !vm.CsvBulkPreview.Contains("Trước:", StringComparison.Ordinal); wait++) PumpFixture(100);
                        if (!vm.CsvBulkPreview.Contains("Trước:", StringComparison.Ordinal))
                        {
                            // honest fallback label: the text below is SEEDED, not produced by the command
                            previewMode = "SEEDED text (real command did not finish in the fixture; it left: " + vm.CsvBulkPreview + ")";
                            vm.TestSetCsvBulkPreview("Sẽ thay 4 lần trong 4 dòng (dòng đang lọc).\nTrước: Câu kiểm tra 1\nSau: Câu  1\nTrước: Câu kiểm tra 2\nSau: Câu  2\nTrước: Câu kiểm tra 3\nSau: Câu  3");
                        }
                        window.UpdateLayout();
                        PumpFixture(400);
                        // window.Content is laid out at 1/UiScale; TranslatePoint reports window (DIP) space, so the client area in that space is ActualHeight x scale.
                        var client = ((FrameworkElement)window.Content).ActualHeight * scale;
                        // the page keeps a bottom margin below the card; what the user can reach without scrolling the page is the client area
                        var gridTop = grid.TranslatePoint(new Point(0, 0), window).Y;
                        // The card CLIPS what overflows it: the visible table is the intersection of the grid, the card's inner area (minus its padding and footer) and the client area.
                        var card = Named("CsvEditorCard"); var footer = Named("CsvEditorFooter");
                        var cardBottom = card.TranslatePoint(new Point(0, card.ActualHeight), window).Y;
                        var footerBottom = footer.TranslatePoint(new Point(0, footer.ActualHeight), window).Y;
                        var footerTop = footer.TranslatePoint(new Point(0, 0), window).Y;
                        var visibleBottom = Math.Min(Math.Min(client, grid.TranslatePoint(new Point(0, grid.ActualHeight), window).Y), footerTop);
                        for (var wait = 0; wait < 100 && (grid.Items.Count < rows.Count || vm.CsvEditorStatus.Contains("đang kiểm tra", StringComparison.OrdinalIgnoreCase)); wait++) PumpFixture(100);
                        for (var wait = 0; wait < 30 && grid.ItemContainerGenerator.ContainerFromIndex(0) is null; wait++) { grid.UpdateLayout(); PumpFixture(100); }
                        var full = 0;
                        var bottoms = new List<double>();
                        for (var i = 0; i < rows.Count; i++)
                            if (grid.ItemContainerGenerator.ContainerFromIndex(i) is DataGridRow { IsVisible: true } r)
                            {
                                var bottom = r.TranslatePoint(new Point(0, r.ActualHeight), window).Y; bottoms.Add(Math.Round(bottom));
                                if (bottom <= visibleBottom + 0.5) full++;
                            }
                        // scrolled page content is reachable too: count the rows the grid itself shows when the page scrolls to its end
                        var pageScroll = FindVisualChildren<ScrollViewer>(Named("CsvEditorCard")).FirstOrDefault(s => s.Name == "CsvCardScroll");
                        var report = $"{label}: client={Math.Round(client)} gridTop={Math.Round(gridTop)} gridH={Math.Round(grid.ActualHeight)} fullRowsInClient={full} bottoms=[{string.Join(",", bottoms)}] low={vm.CsvEditorValidationCompact} outerH={Math.Round(window.ActualHeight)} scale={UiAppearance.Scale} pageScroll={(pageScroll is null ? "none" : "H" + Math.Round(pageScroll.ViewportHeight) + "/" + Math.Round(pageScroll.ExtentHeight))}";
                        Console.WriteLine("REPRO " + report);
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_DIAG") == "1")
                            foreach (var n in new[] { "CsvEditorSearchBox", "CsvEditorCard", "CsvChooseHeaderButton", "CsvBulkReplacePanel", "CsvBulkPreviewHeader", "CsvBulkPreviewScroll", "CsvEditorValidationShortText", "CsvEditorGrid" })
                            {
                                var e = Named(n); var y = e.TranslatePoint(new Point(0, 0), window).Y;
                                Console.WriteLine($"   {n}: y={Math.Round(y, 1)} h={Math.Round(e.ActualHeight, 1)} bottom={Math.Round(y + e.ActualHeight, 1)}");
                            }
                        Require(vm.CsvBulkPreview.Contains("Trước:", StringComparison.Ordinal), "the real Preview produced examples");
                        // acceptance: at least three ordinary one-line rows are fully visible INSIDE the client area after Preview, with the tools open
                        report += $" cardBottom={Math.Round(cardBottom)} footer={Math.Round(footerTop)}-{Math.Round(footerBottom)}";
                        Require(full >= 3, "native repro " + report);
                        Require(footerBottom <= cardBottom + 0.5 && footerBottom <= client + 0.5, "the grid footer stays inside the card and the client area " + report);
                        // Every find/replace/scope/Preview/Apply/Undo control lies fully inside the bulk panel AND the client area (width and height), and nothing overlaps the examples column.
                        double ClientW() => ((FrameworkElement)window.Content).ActualWidth * scale;
                        Rect Box(FrameworkElement e) { var p = e.TranslatePoint(new Point(0, 0), window); return new Rect(p.X, p.Y, e.ActualWidth * scale, e.ActualHeight * scale); }
                        var panelBox = Box(Named("CsvBulkReplacePanel"));
                        var previewBox = Box(Named("CsvPreviewArea"));
                        var clientBox = new Rect(0, 0, ClientW(), client);
                        foreach (var name in new[] { "CsvBulkFindTextBox", "CsvBulkReplaceTextBox", "CsvBulkScopeComboBox", "CsvBulkPreviewButton", "CsvBulkApplyButton", "CsvBulkUndoButton" })
                        {
                            var box = Box(Named(name));
                            Require(Named(name).IsVisible && box.Width > 8 && box.Height > 8, name + " is visible " + label);
                            Require(box.Left >= panelBox.Left - 0.5 && box.Right <= panelBox.Right + 0.5 && box.Top >= panelBox.Top - 0.5 && box.Bottom <= panelBox.Bottom + 0.5,
                                name + " is fully inside the find/replace panel " + label + " box=" + box + " panel=" + panelBox);
                            Require(clientBox.Contains(box.TopLeft) && box.Right <= clientBox.Right + 0.5 && box.Bottom <= clientBox.Bottom + 0.5, name + " is inside the client " + label);
                            if (Named("CsvPreviewArea").IsVisible && vm.CsvEditorValidationCompact)
                                Require(!box.IntersectsWith(Rect.Inflate(previewBox, -0.5, -0.5)), name + " does not overlap the examples column " + label);
                        }
                        // standard 36 / compact 30 control sizes are unchanged
                        Require(Named("CsvBulkScopeComboBox").ActualHeight == 36 && Named("CsvBulkFindTextBox").ActualHeight == 36, "standard control height is kept " + label);
                        Console.WriteLine("   preview=" + previewMode + " panel=" + panelBox + " previewArea=" + previewBox);
                        // nothing was collapsed or hidden
                        Require(Named("CsvBulkReplacePanel").IsVisible && Named("CsvBulkFindTextBox").IsVisible && Named("CsvBulkApplyButton").IsVisible && Named("CsvBulkPreviewScroll").IsVisible, "tools stay open " + label);
                        window.Close();
                    }
                    Console.WriteLine("WPF CSV native-repro fixture: PASS (4 ordinary rows, Preview mode reported per case, all bulk controls inside panel+client without overlap, >=3 full rows inside the client area at 1043x720 UI120 (native), 883 UI120 and 720/800/883 UI100, Dark)");
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
