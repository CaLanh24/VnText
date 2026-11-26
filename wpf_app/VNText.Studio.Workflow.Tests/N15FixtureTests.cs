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
    /// <summary>N1, N2, N5, N6, N7, N8, N9 and N10 on the REAL MainWindow / JournalWindow, VI and EN, Light and Dark (OCR grid N3/N4 live in the region-grid fixture).</summary>
    private static int RunN15Fixture()
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
                var work = Path.Combine(TestTempRoot(), "n15_" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(work);
                var game = Path.Combine(work, "game"); Directory.CreateDirectory(game);
                var picture = Path.Combine(work, "scenery.png"); File.WriteAllBytes(picture, Convert.FromBase64String("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="));
                var report = new List<string>();
                try
                {
                    foreach (var (language, theme) in new[] { ("vi", "light"), ("en", "dark") })
                    {
                        var picker = new FakePathPicker();
                        var vm = new MainViewModel(picker, new PythonWorkerHost(), startWorker: false);
                        vm.Language = language; vm.Theme = theme; vm.UiScale = 1.2;
                        vm.NavigateTabCommand.Execute("editcsv");
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal; window.Width = 1055; window.Height = 720;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1")
                        {
                            window.WindowStartupLocation = WindowStartupLocation.Manual;
                            window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false;
                        }
                        window.Show(); window.UpdateLayout(); PumpFixture(250);
                        FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                        var tag = $"{language}/{theme}";

                        // ---------- N1: the compact header is CSV-only; it never leaks to other pages, after fold/resize either ----------
                        vm.TestLoadCsvRows(Path.Combine(work, "translation.csv"), Enumerable.Range(1, 7).Select(i => new CsvEditorRow { Index = i, Key = "k" + i, SourceText = i == 2 ? "Chọn thư mục game" : "Hello " + i, Translation = i == 2 ? "Chưa chọn game" : "Xin chào " + i }).ToList(), "OK");
                        window.UpdateLayout(); PumpFixture(300); window.UpdateLayout(); PumpFixture(150);
                        Require(vm.CsvToolsTight || vm.PageHeaderMargin.Top == 38, $"{tag} N1: precondition (a small window compacts the CSV header)");
                        AssertEqual(38.0, vm.PageHeaderMargin.Top);
                        foreach (var tab in new[] { "extract", "translate", "images", "patch" })
                        {
                            vm.NavigateTabCommand.Execute(tab); window.UpdateLayout(); PumpFixture(80);
                            AssertEqual(38.0, vm.PageHeaderMargin.Top); AssertEqual(32.0, vm.PageHeaderMargin.Bottom); AssertEqual(58.0, vm.PageHeaderMinHeight);
                        }
                        vm.NavigateTabCommand.Execute("editcsv"); window.UpdateLayout(); PumpFixture(80);
                        AssertEqual(38.0, vm.PageHeaderMargin.Top);                                                   // the CSV page keeps its compact header (row floor)
                        window.Width = 1300; window.Height = 900; window.UpdateLayout(); PumpFixture(200);
                        window.Width = 1055; window.Height = 720; window.UpdateLayout(); PumpFixture(200);
                        vm.NavigateTabCommand.Execute("translate"); window.UpdateLayout(); PumpFixture(80);
                        AssertEqual(38.0, vm.PageHeaderMargin.Top);                                                   // after a fold + resize round trip, still incumbent elsewhere
                        var titleTop = Named("PageScrollViewer").TranslatePoint(new Point(0, 0), window).Y;
                        Require(titleTop > 60, $"{tag} N1: the workflow page body starts below the incumbent header ({titleTop})");

                        // ---------- N2: the page scroller shows a thumb only when needed (Auto), as an overlay (no width jump) ----------
                        var scroller = (ScrollViewer)Named("PageScrollViewer");
                        AssertEqual(ScrollBarVisibility.Auto, scroller.VerticalScrollBarVisibility);
                        vm.NavigateTabCommand.Execute("extract"); window.UpdateLayout(); PumpFixture(150);
                        var widthBefore = scroller.ViewportWidth;
                        Require(scroller.ComputedVerticalScrollBarVisibility == Visibility.Visible || scroller.ExtentHeight <= scroller.ViewportHeight + 0.5, $"{tag} N2: overflowing content gets a scrollbar");
                        // Design QA: the viewer reaches the workspace edge and its padding keeps the card gutter; the scrollbar itself is an overlay (it reserves nothing more).
                        Require(Math.Abs(scroller.ViewportWidth - (scroller.ActualWidth - scroller.Padding.Left - scroller.Padding.Right)) < 0.5, $"{tag} N2: the overlay thumb reserves no gutter beyond the card padding (viewport {scroller.ViewportWidth} vs {scroller.ActualWidth})");
                        var rail = (System.Windows.Controls.Primitives.ScrollBar)scroller.Template.FindName("PART_VerticalScrollBar", scroller);
                        var railRight = rail.TranslatePoint(new Point(rail.ActualWidth, 0), window).X; var content = (FrameworkElement)window.Content; var clientRight = content.TranslatePoint(new Point(content.ActualWidth, 0), window).X;
                        Require(clientRight - railRight >= 0 && clientRight - railRight <= 3, $"{tag} N2: the outer rail sits at the workspace edge (right {railRight:0.#} of {clientRight:0.#})");
                        scroller.ScrollToVerticalOffset(40); window.UpdateLayout(); PumpFixture(60);
                        Require(Math.Abs(scroller.ViewportWidth - widthBefore) < 0.5, $"{tag} N2: scrolling does not change the content width");
                        scroller.ScrollToTop();

                        // ---------- N5: dynamic chrome follows the selected language ----------
                        vm.NavigateTabCommand.Execute("editcsv"); window.UpdateLayout(); PumpFixture(100);
                        vm.CsvEditorRows[0].IsSelected = true; window.UpdateLayout(); PumpFixture(100);
                        var checkedText = FindVisualChildren<TextBlock>(Named("CsvSelectionBar")).First(t => t.Text.Contains("1", StringComparison.Ordinal) && (t.Text.Contains("chọn", StringComparison.OrdinalIgnoreCase) || t.Text.Contains("select", StringComparison.OrdinalIgnoreCase))).Text;
                        Require(language == "vi" ? checkedText.StartsWith("Đã chọn", StringComparison.Ordinal) : checkedText.Contains("selected", StringComparison.Ordinal) && !checkedText.Contains("chọn", StringComparison.Ordinal), $"{tag} N5: the selected-row count is localized ('{checkedText}')");
                        AssertEqual(language == "vi" ? "Đã chọn 1 dòng" : "1 row selected", UiText.TranslateDynamic(vm.CsvCheckedText));
                        vm.Language = language == "vi" ? "en" : "vi"; PumpFixture(60);
                        AssertEqual(language == "vi" ? "1 row selected" : "Đã chọn 1 dòng", UiText.TranslateDynamic(vm.CsvCheckedText));
                        vm.Language = language;
                        vm.CsvEditorRows[1].IsSelected = true; PumpFixture(60);
                        AssertEqual(language == "vi" ? "Đã chọn 2 dòng" : "2 rows selected", UiText.TranslateDynamic(vm.CsvCheckedText));
                        vm.CsvEditorRows[1].IsSelected = false;
                        vm.CsvEditorRows[0].IsSelected = false;
                        AssertEqual(language == "vi" ? "Chưa chọn dòng nào" : "No rows selected", UiText.TranslateDynamic(vm.CsvCheckedText));
                        Require(language == "vi" || UiText.Translate("Chọn thư mục game") != "Chọn thư mục game", $"{tag} N5: the folder picker title is catalogued");
                        Require(language == "vi" || (UiText.Translate("Chọn tệp dữ liệu của game") != "Chọn tệp dữ liệu của game" && UiText.Translate("Chọn nơi lưu bản dịch") != "Chọn nơi lưu bản dịch"), $"{tag} N5: the other picker titles are catalogued");
                        // user data is never translated: a CSV row whose text equals a catalog key stays exactly as the user has it
                        window.UpdateLayout(); PumpFixture(100);
                        var grid = (DataGrid)Named("CsvEditorGrid");
                        Require(FindVisualChildren<TextBlock>(grid).Any(t => t.Text == "Chọn thư mục game") && FindVisualChildren<TextBlock>(grid).Any(t => t.Text == "Chưa chọn game"), $"{tag} N5: CSV content is never localized");

                        // ---------- N7: the patch needs an existing source; the page says what to do; the guard stays ----------
                        var ready = CreatePatchSourcePackage("Hộ tống");
                        picker.TranslationCsv = Path.Combine(ready, "translation.csv");
                        vm.NavigateTabCommand.Execute("patch"); vm.ChooseTranslationCsvCommand.Execute(null);
                        window.UpdateLayout(); PumpFixture(300);
                        Require(vm.ReadyForPatch, $"{tag} N7: the package itself is ready");
                        vm.InputPath = "";
                        window.UpdateLayout(); PumpFixture(120);
                        Require(!vm.RunPatchCommand.CanExecute(null), $"{tag} N7: no source -> Build patch is disabled");
                        var hint = (TextBlock)Named("PatchSourceHintText");
                        Require(hint.IsVisible && hint.Text.Length > 10 && (language == "vi" ? hint.Text.Contains("Chọn thư mục game", StringComparison.Ordinal) : hint.Text.Contains("Choose a game", StringComparison.Ordinal)), $"{tag} N7: an actionable missing-source hint ('{hint.Text}')");
                        vm.InputPath = Path.Combine(work, "does-not-exist");
                        window.UpdateLayout(); PumpFixture(80);
                        Require(!vm.RunPatchCommand.CanExecute(null) && hint.IsVisible && (language == "vi" ? hint.Text.Contains("Không tìm thấy", StringComparison.Ordinal) : hint.Text.Contains("not found", StringComparison.Ordinal)), $"{tag} N7: a nonexistent source is not ready either ('{hint.Text}')");
                        vm.InputPath = game;
                        window.UpdateLayout(); PumpFixture(80);
                        Require(vm.RunPatchCommand.CanExecute(null) && !hint.IsVisible, $"{tag} N7: an existing source with a ready package enables the action and hides the hint");
                        var buildButton = (Button)Named("PatchBuildButton");
                        Require(buildButton.IsEnabled, $"{tag} N7: the visible button is enabled for a valid source");

                        // ---------- N8: explicit folder / asset-file choice; Cancel is terminal ----------
                        vm.InputPath = "";
                        picker.InputPath = null; picker.AssetFile = null;
                        var picksBefore = picker.InputPicks;
                        vm.ChooseInputCommand.Execute(null);
                        PumpFixture(80);
                        AssertEqual(picksBefore + 1, picker.InputPicks); AssertEqual(0, picker.AssetPicks);          // Cancel: ONE folder picker, no second picker
                        Require(vm.InputPath == "" && !vm.Busy, $"{tag} N8: Cancel changes nothing and starts nothing");
                        var chooseButton = (Button)Named("ChooseInputButton");
                        var menu = MainWindow.BuildInputChoiceMenu(vm, chooseButton);
                        AssertEqual(2, menu.Items.Count);
                        menu.IsOpen = true; PumpFixture(100); menu.UpdateLayout();
                        AssertEqual(window.FindResource("SurfaceBrush"), menu.Background);
                        AssertEqual(window.FindResource("InkBrush"), menu.Foreground);
                        AssertEqual(window.FindResource("AppFont"), menu.FontFamily);
                        AssertEqual((double)window.FindResource("UiBodySize"), menu.FontSize);
                        AssertEqual(vm.UiScale, ((System.Windows.Media.ScaleTransform)menu.LayoutTransform).ScaleX);
                        foreach (MenuItem route in menu.Items)
                        {
                            route.ApplyTemplate();
                            Require(route.ActualHeight >= 36 && route.Padding.Left >= 12, "Q1: route keeps app-sized target and padding");
                            Require(route.Template.FindName("RouteSurface", route) is Border, "Q1: source route uses its scoped template");
                            route.IsEnabled = false; PumpFixture(20);
                            AssertEqual(window.FindResource("DisabledForegroundBrush"), route.Foreground);
                            route.IsEnabled = true;
                        }
                        menu.IsOpen = false;
                        AssertEqual(language == "vi" ? "Chọn thư mục game…" : "Choose game folder…", (string)((MenuItem)menu.Items[0]).Header);
                        AssertEqual(language == "vi" ? "Chọn tệp dữ liệu của game…" : "Choose asset / bundle file…", (string)((MenuItem)menu.Items[1]).Header);
                        picker.AssetFile = picture;
                        ((MenuItem)menu.Items[1]).Command.Execute(null);
                        PumpFixture(120);
                        AssertEqual(1, picker.AssetPicks); AssertEqual(picture, vm.InputPath);                            // the asset route still works
                        vm.InputPath = "";
                        var requested = 0; vm.InputChoiceRequested += _ => requested++;
                        ((System.Windows.Automation.Provider.IInvokeProvider)new System.Windows.Automation.Peers.ButtonAutomationPeer(chooseButton).GetPattern(System.Windows.Automation.Peers.PatternInterface.Invoke)).Invoke();
                        PumpFixture(120);
                        AssertEqual(1, requested);                                                                       // the button only offers the choice; it opens no picker itself
                        AssertEqual(1, picker.AssetPicks);

                        // ---------- N9: localized, distinct accessible names on the source/output buttons ----------
                        vm.NavigateTabCommand.Execute("extract"); window.UpdateLayout(); PumpFixture(100);
                        string Name(string id) => System.Windows.Automation.AutomationProperties.GetName(Named(id));
                        var names = new[] { Name("OpenInputButton"), Name("ChooseInputButton"), Name("OpenOutputButton"), Name("ChooseOutputButton") };
                        Require(names.All(n => n.Length > 3) && names.Distinct().Count() == 4, $"{tag} N9: four distinct names ({string.Join(" | ", names)})");
                        Require(language == "vi" ? names.All(n => !n.StartsWith("Open") && !n.StartsWith("Choose")) : names.All(n => n.StartsWith("Open") || n.StartsWith("Choose")), $"{tag} N9: names follow the language ({string.Join(" | ", names)})");

                        // ---------- N6: the chosen image is named before OCR; no stale result is reused ----------
                        vm.NavigateTabCommand.Execute("images"); window.UpdateLayout(); PumpFixture(100);
                        vm.EnterImageEditCommand.Execute(null); window.UpdateLayout(); PumpFixture(100);
                        var panel = FindVisualChildren<ImageWorkspacePanel>((DependencyObject)Named("ImagesPage")).Single();
                        var row = (FrameworkElement)panel.FindName("SelectedImageRow");
                        Require(!row.IsVisible, $"{tag} N6: nothing selected -> no identity row");
                        vm.ImagePath = picture; window.UpdateLayout(); PumpFixture(100);
                        var nameText = (TextBlock)panel.FindName("SelectedImageName");
                        Require(row.IsVisible && nameText.Text == "scenery.png" && (nameText.ToolTip as string) == picture, $"{tag} N6: file name shown with the full path in the tooltip ('{nameText.Text}')");
                        Require(vm.ImageRegions.Count == 0 && !vm.ImageHasPreview && !vm.ImageHasResults, $"{tag} N6: choosing an image reuses no OCR/preview/result state");
                        vm.ImagePath = ""; window.UpdateLayout(); PumpFixture(60);
                        Require(!row.IsVisible, $"{tag} N6: clearing the selection hides the row");

                        // ---------- N10: distinct Clear search vs Delete log, confirmation kept ----------
                        var journal = new JournalWindow(window, vm);
                        journal.Show(); journal.UpdateLayout(); PumpFixture(150);
                        var journalButtons = FindVisualChildren<Button>(journal).Select(b => b.Content as string ?? "").ToList();
                        var clearLabel = language == "vi" ? "Xóa tìm kiếm" : "Clear search"; var deleteLabel = language == "vi" ? "Xóa nhật ký" : "Delete log";
                        Require(journalButtons.Contains(clearLabel) && journalButtons.Contains(deleteLabel) && !journalButtons.Contains("Xóa") && !journalButtons.Contains("Delete"), $"{tag} N10: distinct labels ({string.Join(" | ", journalButtons)})");
                        var clearButton = FindVisualChildren<Button>(journal).First(b => (b.Content as string) == clearLabel);
                        Require(clearButton.ToolTip is string tip && tip.Length > 10, $"{tag} N10: the clear action says it does not delete the log");
                        journal.Close();
                        report.Add(tag);
                        window.Close();
                        vm.Language = "vi"; vm.Theme = "light"; vm.UiScale = 1;          // the isolated settings return to the defaults (later fixtures read them)
                        vm.Dispose();
                    }
                    Require(File.ReadAllText(Path.Combine(@"C:\v", "wpf_app", "VNText.Studio.App", "JournalWindow.cs")).Contains("Xóa tệp nhật ký {0}?", StringComparison.Ordinal), "N10: the file-deletion confirmation is retained");
                    Console.WriteLine("WPF N1-N10 fixture: PASS (" + string.Join(", ", report) + ")");
                    exitCode = 0;
                }
                finally { try { Directory.Delete(work, true); } catch (IOException) { } app.Shutdown(); }
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); }
        });
        thread.SetApartmentState(ApartmentState.STA); thread.Start(); thread.Join();
        return exitCode;
    }
}
