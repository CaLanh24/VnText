using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using VNText.Studio.App;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    /// <summary>
    /// V1/V2/V3 at the reviewed presentations on the REAL MainWindow: outer 1055x720 DIP (1583x1080 physical at OS 150%) and a maximized-sized 1484x800, UI 100/120%,
    /// Vietnamese/English, Light/Dark.  Rows: seven SHORT one-line rows (so a count of three cannot be faked by clipping) and a 120-row set of long wrapping rows.
    /// V1: >=3 full single-line rows, footer separate, last row scrollable; selection and typed text survive resize.  V2: both find/replace fields share top and height
    /// whether their labels take one or two lines.  V3: the row selector is the scoped themed checkbox (idle/checked/disabled brushes, not the stock white box).
    /// </summary>
    private static int RunCsvBudgetFixture()
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
                MainViewModel vm = null!;
                var cases = 0;
                var clock = System.Diagnostics.Stopwatch.StartNew();
                void Time(string what) { if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_TRACE") == "1") Console.WriteLine($"BUDGETTIME {clock.Elapsed.TotalSeconds:0.0}s {what}"); }
                var labelsDiffered = false;
                try
                {
                    foreach (var language in new[] { "vi", "en" })
                    foreach (var theme in new[] { "light", "dark" })
                    foreach (var scale in new[] { 1.0, 1.2 })
                    {
                        // a fresh view model per presentation: windows subscribe to it, so a shared one would make every language switch re-translate all earlier windows
                        (vm as IDisposable)?.Dispose();
                        vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        vm.NavigateTabCommand.Execute("editcsv");
                        vm.Language = language; vm.Theme = theme; vm.UiScale = scale;
                        vm.SetCsvToolsTight(false);
                        Time($"creating window {language}/{theme}/{scale}");
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        Time("window constructed");
                        window.WindowState = WindowState.Normal;
                        window.Width = 1055; window.Height = 720;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1")
                        {
                            window.WindowStartupLocation = WindowStartupLocation.Manual;
                            window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false;
                        }
                        window.Show();
                        window.UpdateLayout(); PumpFixture(90);
                        FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                        var grid = (DataGrid)Named("CsvEditorGrid");
                        System.Windows.Media.Color Token(string key) => ((SolidColorBrush)window.FindResource(key)).Color;

                        void Load(IReadOnlyList<CsvEditorRow> rows)
                        {
                            vm.TestLoadCsvRows(Path.Combine(Path.GetTempPath(), "translation.csv"), rows, "Kiểm tra: hợp lệ.");
                            window.UpdateLayout(); PumpFixture(112); window.UpdateLayout(); PumpFixture(67);
                        }
                        double Client() => ((FrameworkElement)window.Content).ActualHeight * scale;
                        // fully visible rows: bottom inside the table viewport (the visible part of the grid, above the footer and inside the client area)
                        (int full, double visibleBottom) FullRows(int count)
                        {
                            var footer = Named("CsvEditorFooter");
                            var vb = Math.Min(Math.Min(Client(), grid.TranslatePoint(new Point(0, grid.ActualHeight), window).Y), footer.TranslatePoint(new Point(0, 0), window).Y);
                            var n = 0;
                            for (var i = 0; i < count; i++)
                                if (grid.ItemContainerGenerator.ContainerFromIndex(i) is DataGridRow { IsVisible: true } r && r.TranslatePoint(new Point(0, r.ActualHeight), window).Y <= vb + 0.5
                                    && r.TranslatePoint(new Point(0, 0), window).Y >= grid.TranslatePoint(new Point(0, 0), window).Y - 0.5) n++;
                            return (n, vb);
                        }

                        foreach (var (width, height, size) in new[] { (1055.0, 720.0, "small"), (1484.0, 800.0, "maximized-size") })
                        {
                        var label = $"{language}/{theme}/UI{scale * 100:0}/{size}";
                        window.Width = width; window.Height = height; window.UpdateLayout(); PumpFixture(110);
                        vm.SetCsvToolsTight(false); vm.CsvBulkFind = ""; vm.CsvBulkReplace = ""; vm.CsvEditorSearch = "";
                        Time("// ---------- seven SHORT one-line rows ");
                        // ---------- seven SHORT one-line rows ----------
                        var shortRows = Enumerable.Range(1, 7).Select(i => new CsvEditorRow { Index = i, Key = "k" + i, SourceText = "Hello " + i, Translation = "Xin chào " + i }).ToList();
                        Load(shortRows);
                        var (full, vb) = FullRows(shortRows.Count);
                        var footerTop = Named("CsvEditorFooter").TranslatePoint(new Point(0, 0), window).Y;
                        var gridBottom = grid.TranslatePoint(new Point(0, grid.ActualHeight), window).Y;
                        var card = Named("CsvEditorCard");
                        var cardBottom = card.TranslatePoint(new Point(0, card.ActualHeight), window).Y;
                        var report = $"{label}: tight={vm.CsvToolsTight} gridH={Math.Round(grid.ActualHeight)} full={full} client={Math.Round(Client())} footerTop={Math.Round(footerTop)} gridBottom={Math.Round(gridBottom)}";
                        Console.WriteLine("BUDGET " + report);
                        Require(full >= 3, "V1: at least three full single-line rows are visible: " + report);
                        Require(footerTop + 0.5 >= Math.Min(gridBottom, Client()) - 0.5 && Named("CsvEditorFooter").TranslatePoint(new Point(0, Named("CsvEditorFooter").ActualHeight), window).Y <= Math.Min(cardBottom, Client()) + 0.5,
                            "V1: the footer is its own row inside the card and the client: " + report);
                        // the last row is reachable by scrolling and is then fully visible
                        grid.ScrollIntoView(shortRows[^1]); grid.UpdateLayout(); PumpFixture(54);
                        var lastRow = (DataGridRow?)grid.ItemContainerGenerator.ContainerFromIndex(shortRows.Count - 1);
                        Require(lastRow is { IsVisible: true } && lastRow.TranslatePoint(new Point(0, lastRow.ActualHeight), window).Y <= FullRows(shortRows.Count).visibleBottom + 0.5, "V1: the final row scrolls into full view: " + report);
                        grid.ScrollIntoView(shortRows[0]); grid.UpdateLayout(); PumpFixture(36);

                        Time("// ---------- V3: the scoped themed chec");
                        // ---------- V3: the scoped themed checkbox ----------
                        var checkbox = FindVisualChildren<CheckBox>(grid).First();
                        Require(ReferenceEquals(checkbox.Style, window.FindResource("CsvRowCheckBoxStyle")), "V3: the row selector uses the scoped CSV checkbox style " + label);
                        checkbox.ApplyTemplate();
                        var box = (Border)checkbox.Template.FindName("Box", checkbox);
                        var mark = (System.Windows.Shapes.Path)checkbox.Template.FindName("Mark", checkbox);
                        Require(((SolidColorBrush)box.Background).Color == Token("FieldBackgroundBrush") && ((SolidColorBrush)box.BorderBrush).Color == Token("MutedBrush") && mark.Visibility != Visibility.Visible,
                            "V3: idle box uses FieldBackground/Muted tokens, not the stock white box " + label);
                        Require(ContrastRatio(Token("MutedBrush"), Token("FieldBackgroundBrush")) >= 3.0, "V3: the idle outline is a readable (>=3:1) component boundary " + label);
                        checkbox.IsChecked = true; window.UpdateLayout(); PumpFixture(30);
                        Require(shortRows[0].IsSelected && ((SolidColorBrush)box.Background).Color == Token("BlueBrush") && mark.Visibility == Visibility.Visible, "V3: checked fills with the accent and shows the check, and IsSelected follows " + label);
                        Require(ContrastRatio(Token("SurfaceBrush"), Token("BlueBrush")) >= 3.0 && ((SolidColorBrush)mark.Stroke).Color == Token("SurfaceBrush"), "V3: the check mark is readable on the accent fill " + label);
                        checkbox.IsEnabled = false; window.UpdateLayout(); PumpFixture(30);
                        Require(((SolidColorBrush)box.BorderBrush).Color == Token("DisabledBorderBrush") && ((SolidColorBrush)box.Background).Color == Token("DisabledBackgroundBrush"), "V3: disabled uses the disabled tokens " + label);
                        checkbox.IsEnabled = true; checkbox.IsChecked = false; window.UpdateLayout(); PumpFixture(30);
                        Require(!shortRows[0].IsSelected, "V3: unchecking clears IsSelected " + label);
                        vm.CsvSelectAllFilteredCommand.Execute(null);
                        Require(vm.CsvCheckedCount == shortRows.Count, "V3: select-all-filtered selects every visible row " + label);

                        // ---------- retained state across a resize / layout change ----------
                        vm.CsvEditorRows[1].IsSelected = true;
                        vm.CsvBulkFind = "xin"; vm.CsvBulkReplace = "chào";
                        var checkedBefore = vm.CsvCheckedCount;
                        window.Width = width - 140; window.Height = height - 40; window.UpdateLayout(); PumpFixture(112);
                        window.Width = width; window.Height = height; window.UpdateLayout(); PumpFixture(112);
                        Require(vm.CsvCheckedCount == checkedBefore && vm.CsvEditorRows.All(r => r.IsSelected) && vm.CsvBulkFind == "xin" && vm.CsvBulkReplace == "chào",
                            "V1: the selection and the typed find/replace text survive resize and fold/unfold " + label);
                        vm.CsvClearCheckedCommand.Execute(null);
                        Require(vm.CsvCheckedCount == 0, "V3: clear selection " + label);
                        Require(FullRows(shortRows.Count).full >= 3, "V1: three full rows still after the resize round trip " + label);

                        Time("// ---------- V2: the two fields share t");
                        // ---------- V2: the two fields share top and height, labels of one or two lines ----------
                        if (vm.CsvToolsTight && !vm.CsvToolsOpen)
                        {
                            var toggle = (Button)Named("CsvToolsToggleButton");
                            Require(toggle.IsEnabled && toggle.IsVisible, "V1: the fold bar's open button is enabled and visible " + label);
                            // the real control path (UI Automation Invoke), not the command object: a disabled button refuses it
                            ((System.Windows.Automation.Provider.IInvokeProvider)new System.Windows.Automation.Peers.ButtonAutomationPeer(toggle).GetPattern(System.Windows.Automation.Peers.PatternInterface.Invoke)).Invoke();
                            window.UpdateLayout(); PumpFixture(135); window.UpdateLayout(); PumpFixture(67);
                        }
                        var findBox = Named("CsvBulkFindTextBox"); var replaceBox = Named("CsvBulkReplaceTextBox");
                        var findLabel = Named("CsvBulkFindLabel"); var replaceLabel = Named("CsvBulkReplaceLabel");
                        var findTop = findBox.TranslatePoint(new Point(0, 0), window).Y; var replaceTop = replaceBox.TranslatePoint(new Point(0, 0), window).Y;
                        Require(Math.Abs(findTop - replaceTop) < 0.5 && Math.Abs(findBox.ActualHeight - replaceBox.ActualHeight) < 0.5,
                            $"V2: the find and replace fields share top and height {label} (find {findTop:0.0}/{findBox.ActualHeight:0.0}, replace {replaceTop:0.0}/{replaceBox.ActualHeight:0.0}; labels {findLabel.ActualHeight:0.0}/{replaceLabel.ActualHeight:0.0})");
                        Require(findLabel.TranslatePoint(new Point(0, findLabel.ActualHeight), window).Y <= findTop + 0.5 && replaceLabel.TranslatePoint(new Point(0, replaceLabel.ActualHeight), window).Y <= replaceTop + 0.5,
                            "V2: a label never overlaps its field " + label);
                        if (Math.Abs(findLabel.ActualHeight - replaceLabel.ActualHeight) > 2) labelsDiffered = true;   // the case that used to misalign by 27 px was actually exercised
                        var shortHeightWithTools = grid.ActualHeight;
                        Require(FullRows(shortRows.Count).full >= 3, "V1: opened tools keep the three-row floor " + label);

                        Time("cases++;");
                        cases++;
                        if (size != "small") continue;
                        Time("// ---------- 120 long wrapping rows ---");
                        // ---------- 120 long wrapping rows ----------
                        var longText = string.Join(" ", Enumerable.Repeat("The quick brown fox keeps jumping over the very lazy dog again and again", 2));
                        var longRows = Enumerable.Range(1, 120).Select(i => new CsvEditorRow { Index = i, Key = "L" + i, SourceText = i + ": " + longText, Translation = i + ": " + longText.Replace("fox", "cáo") }).ToList();
                        vm.CsvBulkFind = ""; vm.CsvBulkReplace = ""; vm.CsvEditorSearch = "";    // typing a find text also filters the table; clear it for the long-row set
                        if (vm.CsvToolsTight && vm.CsvToolsOpen) { vm.ToggleCsvToolsCommand.Execute(null); window.UpdateLayout(); PumpFixture(120); }   // reading long rows: fold the tools again
                        Load(longRows);
                        var (longFull, _) = FullRows(longRows.Count);
                        string Diag()
                        {
                            var parts = new List<string>();
                            for (var i = 0; i < 6; i++)
                                if (grid.ItemContainerGenerator.ContainerFromIndex(i) is DataGridRow r)
                                    parts.Add($"#{i} top={r.TranslatePoint(new Point(0, 0), window).Y:0} h={r.ActualHeight:0} vis={r.IsVisible}");
                            return $"rows={vm.CsvEditorRows.Count} visible={vm.CsvEditorVisibleCount} viewCount={vm.CsvEditorView?.Cast<object>().Count()} search='{vm.CsvEditorSearch}' mode={vm.CsvFilterMode} gridSrcSame={ReferenceEquals(grid.ItemsSource, vm.CsvEditorView)} gridH={grid.ActualHeight:0} gridTop={grid.TranslatePoint(new Point(0, 0), window).Y:0} items={grid.Items.Count} " + string.Join("; ", parts);
                        }
                        Require(longFull >= 1, "V1: a long row is fully visible and readable " + label + " (" + longFull + ") " + Diag());
                        var scroller = FindVisualChildren<ScrollViewer>(grid).First();
                        Require(scroller.ScrollableHeight > 0, "V1: 120 long rows scroll " + label);
                        var firstLong = (DataGridRow)grid.ItemContainerGenerator.ContainerFromIndex(0);
                        foreach (var tb in FindVisualChildren<TextBlock>(firstLong).Where(t => t.Text.StartsWith("1: ", StringComparison.Ordinal)))
                            Require(tb.TextTrimming == TextTrimming.None && tb.ActualHeight + 0.5 >= tb.DesiredSize.Height && firstLong.ActualHeight + 0.5 >= tb.ActualHeight, "V1: long text wraps without being clipped " + label);
                        Time("// an extreme row taller than the viewpo");
                        // an extreme row taller than the viewport is still readable: pixel scrolling reaches its end
                        var towering = new CsvEditorRow { Index = 121, Key = "T", SourceText = string.Join(" ", Enumerable.Repeat(longText, 8)), Translation = string.Join(" ", Enumerable.Repeat(longText, 8)) };
                        longRows.Add(towering);
                        Load(longRows);
                        grid.ScrollIntoView(towering); grid.UpdateLayout(); PumpFixture(67);
                        scroller = FindVisualChildren<ScrollViewer>(grid).First();
                        scroller.ScrollToVerticalOffset(scroller.ScrollableHeight); grid.UpdateLayout(); PumpFixture(67);
                        var tallRow = (DataGridRow?)grid.ItemContainerGenerator.ContainerFromIndex(longRows.Count - 1);
                        Require(tallRow is { IsVisible: true } && tallRow.TranslatePoint(new Point(0, tallRow.ActualHeight), window).Y <= FullRows(longRows.Count).visibleBottom + 1.5,
                            "V1: the end of a row taller than the viewport is reachable by scrolling " + label);
                        grid.ScrollIntoView(longRows[^1]); grid.UpdateLayout(); PumpFixture(67);
                        Require(grid.ItemContainerGenerator.ContainerFromIndex(longRows.Count - 1) is DataGridRow { IsVisible: true }, "V1: the final long row scrolls into view " + label);
                        }
                        Time("closing window");
                        window.Close();
                        Time("window closed");
                    }
                    Require(labelsDiffered, "V2: at least one presentation really wrapped one label to two lines (the old misalignment) while the fields stayed aligned");
                    vm.Language = "vi"; vm.Theme = "light"; vm.UiScale = 1;   // the isolated settings return to the defaults
                    Console.WriteLine($"WPF CSV budget fixture: PASS ({cases} presentations: vi/en x light/dark x UI100/120 x 1055x720 and 1484x800; 7 short rows + 120 long rows; V1 floor, V2 alignment, V3 checkbox)");
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
