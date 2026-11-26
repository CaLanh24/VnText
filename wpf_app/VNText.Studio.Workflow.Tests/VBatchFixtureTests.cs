using System.IO;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using VNText.Studio.App;
using VNText.Studio.App.Controls;
using VNText.Studio.App.Converters;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    /// <summary>
    /// V4 (typed journal severity), V5 (honest Images page states), V6 (About card idle border token) and V7 (distinct image icon) on the REAL MainWindow, in Light and Dark.
    /// Everything runs on owned temp packages under TEST_RUN; nothing touches the Owner's data.
    /// </summary>
    private static int RunVBatchFixture()
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
                var work = Path.Combine(TestTempRoot(), "vbatch_" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(work);
                try
                {
                    // ---------------- V4: severity comes from the producer / structured result ----------------
                    AssertEqual("INFO", AppJournalStore.Level("Kiểm tra bản dịch: 7 hợp lệ · 0 bị chặn · không phát hiện lỗi"));      // a valid result that merely says "no error"
                    AssertEqual("INFO", AppJournalStore.Level("Câu nguồn: The error in the sentence"));
                    AssertEqual("INFO", AppJournalStore.Level("Dịch xong 7 dòng, không có lỗi."));
                    AssertEqual("INFO", AppJournalStore.Level("Đã xóa bản dịch 4 dòng lỗi."));
                    AssertEqual("ERROR", AppJournalStore.Level("Lỗi: không ghi được bản dịch"));                                   // genuine failures keep their level
                    AssertEqual("ERROR", AppJournalStore.Level("[error] worker exited"));
                    AssertEqual("ERROR", AppJournalStore.Level("Không đọc được trạng thái"));
                    AssertEqual("WARN", AppJournalStore.Level("Cảnh báo: 1 dòng cần chú ý"));
                    AssertEqual("WARN", AppJournalStore.Level("[stderr] something"));
                    AssertEqual("ERROR", AppJournalStore.Level("Unity analyzer: NOT_DETECTED; scan_errors=2"));
                    AssertEqual("INFO", AppJournalStore.Level("Unity analyzer: NOT_DETECTED; scan_errors=0"));
                    // Embedded producer-looking tokens are source data. Both live colour and
                    // persisted severity must agree, including after timestamp/task wrappers.
                    var quotedSources = new[] {
                        "Câu nguồn: [error] is printed on the screen",
                        "Source: [warning] and [stderr] are literal text",
                        "Source: scan_errors=2 is an example, not an analyzer result"
                    };
                    var sourceJournal = new AppJournalStore(Path.Combine(work, "source-journal"));
                    foreach (var source in quotedSources)
                    {
                        AssertEqual("INFO", AppJournalStore.Level(source));
                        AssertEqual("INFO", LogSeverityConverter.Severity("[12:34:56] [task fixture] " + source));
                        sourceJournal.Append(source);
                    }
                    foreach (var savedLine in sourceJournal.Files().SelectMany(f => sourceJournal.Read(f).Split('\n', StringSplitOptions.RemoveEmptyEntries)))
                    {
                        Require(savedLine.Contains(" INFO "), "source tokens must persist as INFO: " + savedLine);
                        AssertEqual("INFO", LogSeverityConverter.Severity(savedLine));
                    }
                    AssertEqual("ERROR", LogSeverityConverter.Severity("[12:34:56] [task fixture] [error] actual failure"));
                    AssertEqual("WARN", LogSeverityConverter.Severity("[12:34:56] [task fixture] [stderr] actual diagnostic"));
                    AssertEqual("ERROR", LogSeverityConverter.Severity("[12:34:56] Unity analyzer: NOT_DETECTED; scan_errors=2"));
                    // the page classifier agrees on the same wording (one anchored rule set)
                    foreach (var line in new[] { "Kiểm tra bản dịch: 7 hợp lệ · 0 bị chặn · không phát hiện lỗi", "Câu nguồn: The error in the sentence", "Lỗi: không ghi được bản dịch", "Cảnh báo: 1 dòng cần chú ý" })
                        AssertEqual(AppJournalStore.Level(line), LogSeverityConverter.Severity(line) == "SUCCESS" ? "INFO" : LogSeverityConverter.Severity(line));
                    // explicit producer levels reach BOTH the page and the saved journal, whatever the words say
                    using (var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false))
                    {
                        var tag = " [vb-" + Guid.NewGuid().ToString("N") + "]";      // the saved journal is shared across runs: find only THIS run's lines
                        vm.TestAppendLog("[csv-timing] validate_worker=3ms bind=1ms — 7 hợp lệ, không phát hiện lỗi" + tag + "c", "DEBUG");
                        vm.TestAppendLog("Kiểm tra bản dịch: 7 hợp lệ · 0 bị chặn · không phát hiện lỗi" + tag + "i", "INFO");
                        vm.TestAppendLog("Kiểm tra bản dịch: 5 hợp lệ · 2 bị chặn" + tag + "w", "WARN");
                        vm.TestAppendLog("Kiểm tra thất bại: bản dịch hỏng" + tag + "e", "ERROR");
                        vm.TestAppendLog("Câu nguồn chứa error và lỗi nhưng chỉ là nội dung" + tag + "u");                                // unmarked: no inference from the middle of a sentence
                        var shown = vm.LogLines.TakeLast(5).Select(LogSeverityConverter.Severity).ToArray();
                        AssertEqual("DEBUG,INFO,WARN,ERROR,INFO", string.Join(",", shown));
                        var persisted = vm.JournalStore.Files().SelectMany(f => vm.JournalStore.Read(f).Split('\n', StringSplitOptions.RemoveEmptyEntries)).Where(l => l.Contains(tag.Trim().TrimEnd(']'))).ToArray();
                        string Saved(string needle) => System.Text.RegularExpressions.Regex.Match(persisted.Last(l => l.Contains(needle)), @"^\S+ \S+ [+-]\d\d:\d\d (ERROR|WARN|INFO|DEBUG) ").Groups[1].Value;
                        AssertEqual("DEBUG", Saved(tag + "c"));
                        AssertEqual("INFO", Saved(tag + "i"));
                        AssertEqual("WARN", Saved(tag + "w"));
                        AssertEqual("ERROR", Saved(tag + "e"));
                        AssertEqual("INFO", Saved(tag + "u"));
                        // a persisted line renders with its stored level on the journal page (historic lines are never rewritten)
                        AssertEqual("ERROR", LogSeverityConverter.Severity(persisted.Last(l => l.Contains(tag + "e"))));
                        AssertEqual("DEBUG", LogSeverityConverter.Severity(persisted.Last(l => l.Contains(tag + "c"))));
                        AssertEqual("INFO", LogSeverityConverter.Severity(persisted.Last(l => l.Contains(tag + "u"))));
                        // a REAL open of a valid CSV logs nothing red
                        var csv = Path.Combine(work, "translation.csv");
                        File.WriteAllText(Path.Combine(work, "manifest.json"), """{"entries":[{"key":"k1","source_text":"Hello"},{"key":"k2","source_text":"Bye"}]}""", Encoding.UTF8);
                        File.WriteAllText(csv, "key,source_text,translation,context,file_path,import_method\r\nk1,Hello,Xin chào,UI:Text,a.rpy,renpy_string\r\nk2,Bye,Tạm biệt,UI:Text,a.rpy,renpy_string\r\n", new UTF8Encoding(true));
                        var picker = new FakePathPicker { TranslationCsv = csv };
                        using var openVm = new MainViewModel(picker, new PythonWorkerHost(), startWorker: false);
                        var before = openVm.LogLines.Count;
                        openVm.OpenCsvEditorFileCommand.Execute(null);
                        for (var wait = 0; wait < 60 && (openVm.CsvEditorRows.Count < 2 || openVm.CsvEditorValidating); wait++) PumpFixture(120);
                        Require(openVm.CsvEditorRows.Count == 2, "the valid CSV opened");
                        var opened = openVm.LogLines.Skip(before).ToArray();
                        Require(opened.Length > 0 && opened.All(l => LogSeverityConverter.Severity(l) is not ("ERROR" or "WARN")), "a valid CSV opens without a red or amber line: " + string.Join(" | ", opened));
                    }

                    // ---------------- V5: Images page states (view model + the real panel) ----------------
                    var game = Path.Combine(work, "game"); Directory.CreateDirectory(game);
                    string Package(string name, string? report)
                    {
                        var dir = Path.Combine(work, name); Directory.CreateDirectory(Path.Combine(dir, "images"));
                        File.WriteAllText(Path.Combine(dir, "manifest.json"), "{\"entries\":[]}", Encoding.UTF8);
                        File.WriteAllText(Path.Combine(dir, "translation.csv"), "key,source_text,translation\r\n", new UTF8Encoding(true));
                        if (report is not null) File.WriteAllText(Path.Combine(dir, "images", "report.json"), report, Encoding.UTF8);
                        return dir;
                    }
                    // Mirrors vntext/image_batch.py: text_detected is set ONLY for a confirmed text-bearing image (OCR_READY/TRANSLATED_DRAFT, or UNTRANSLATED after a
                    // successful OCR); an image whose OCR/decoding FAILED stays status UNTRANSLATED with no text_detected; a confirmed blank image is NO_TEXT.
                    string Report(params string[] statuses) => "{\"text_detection_policy\":\"crop-consensus-1\",\"items\":[" + string.Join(",", statuses.Select((s, i) =>
                        $"{{\"source\":\"img{i}.png\",\"status\":\"{s}\"" + (s is "OCR_READY" or "TRANSLATED_DRAFT" ? ",\"text_detected\":true" : s == "NO_TEXT" ? ",\"text_detected\":false" : "") + ",\"ocr_result\":\"\",\"translated\":\"\"}")) + "]}";
                    var noReportPkg = Package("pkg-noreport", null);
                    var noTextPkg = Package("pkg-notext", Report("NO_TEXT", "NO_TEXT", "NO_TEXT"));
                    var resultsPkg = Package("pkg-results", Report("TRANSLATED_DRAFT", "OCR_READY", "NO_TEXT"));
                    var brokenPkg = Package("pkg-broken", "{ not json");
                    var failedScanPkg = Package("pkg-failed-scan", Report("UNTRANSLATED", "NO_TEXT"));
                    var neverPkg = Path.Combine(work, "pkg-never"); Directory.CreateDirectory(neverPkg);   // an export folder without even an images directory

                    foreach (var theme in new[] { "light", "dark" })
                    {
                        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        vm.Theme = theme; vm.Language = "vi"; vm.UiScale = 1.2;
                        vm.NavigateTabCommand.Execute("images");
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal; window.Width = 1055; window.Height = 720;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1")
                        {
                            window.WindowStartupLocation = WindowStartupLocation.Manual;
                            window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false;
                        }
                        window.Show(); window.UpdateLayout(); PumpFixture(150);
                        FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                        var panel = FindVisualChildren<ImageWorkspacePanel>((DependencyObject)Named("ImagesPage")).Single();
                        TextBlock PanelText(string name) => (TextBlock)(panel.FindName(name) ?? throw new InvalidOperationException(name));
                        FrameworkElement PanelPart(string name) => (FrameworkElement)(panel.FindName(name) ?? throw new InvalidOperationException(name));
                        void Refresh() { vm.RefreshImageWorkspace(); window.UpdateLayout(); PumpFixture(100); }
                        string State() => $"{theme}: page={vm.ImagePage} lead='{PanelText("LeadText").Text}' detail='{PanelText("StateDetailText").Text}'";

                        // 1) no source selected: a short missing-source state with the next action; no scan/OCR/draft claim and no count
                        vm.InputPath = ""; vm.OutputPath = ""; Refresh();
                        AssertEqual(MainViewModel.ImagePageKind.NoSource, vm.ImagePage);
                        Require(PanelPart("ImageNextActionButton").IsVisible && !PanelPart("WorkspaceSummaryCard").IsVisible, "V5 no source: next action visible, no counts card: " + State());
                        Require(!(PanelText("LeadText").Text + PanelText("StateDetailText").Text).Contains("đã được lọc", StringComparison.OrdinalIgnoreCase)
                                && !(PanelText("LeadText").Text + PanelText("StateDetailText").Text).Contains("tự tạo bản dịch nháp", StringComparison.OrdinalIgnoreCase)
                                && !PanelText("LeadText").Text.Any(char.IsDigit), "V5 no source: no claim that images were filtered/OCR'd/drafted and no number: " + State());
                        Require(PanelText("LeadText").Text.Length <= 60 && PanelText("StateDetailText").Text.Length <= 90, "V5: the state stays concise: " + State());
                        // the long help is behind Details, closed by default, and opening it leaves the state untouched
                        Require(!PanelPart("IntroDetails").IsVisible && !PanelText("SafetyText").IsVisible, "V5: the long help is closed by default");
                        vm.ToggleImageDetailsCommand.Execute(null); window.UpdateLayout(); PumpFixture(60);
                        Require(PanelPart("IntroDetails").IsVisible && PanelText("SafetyText").IsVisible && PanelText("IntroText").Text.Length > 200 && vm.ImageDetailsToggleText == "Ẩn chi tiết", "V5: Details opens the full explanation");
                        AssertEqual(MainViewModel.ImagePageKind.NoSource, vm.ImagePage);
                        vm.ToggleImageDetailsCommand.Execute(null); window.UpdateLayout(); PumpFixture(60);
                        Require(!PanelPart("IntroDetails").IsVisible, "V5: Details closes again");
                        // the manual editor stays reachable from this state
                        Require(PanelPart("EditImagesButton").IsVisible && vm.EnterImageEditCommand.CanExecute(null), "V5: the manual editor is reachable without a source");
                        vm.EnterImageEditCommand.Execute(null); window.UpdateLayout(); PumpFixture(60);
                        Require(PanelPart("ChooseButton").IsVisible && PanelPart("OcrButton").IsVisible, "V5: the manual editor opens");
                        vm.LeaveImageEditCommand.Execute(null); window.UpdateLayout(); PumpFixture(60);
                        // the next action goes to the Extract step
                        vm.OpenExtractForImagesCommand.Execute(null);
                        AssertEqual(WorkflowTabs.Extract, vm.SelectedTab); vm.NavigateTabCommand.Execute("images"); window.UpdateLayout(); PumpFixture(60);

                        // 2) a game but no export folder
                        vm.InputPath = game; vm.OutputPath = ""; Refresh();
                        AssertEqual(MainViewModel.ImagePageKind.NoOutput, vm.ImagePage);
                        Require(PanelPart("ImageNextActionButton").IsVisible && !PanelPart("WorkspaceSummaryCard").IsVisible, "V5 no output: " + State());
                        // 3) an export folder with no image report: not scanned yet
                        vm.OutputPath = neverPkg; Refresh();
                        AssertEqual(MainViewModel.ImagePageKind.NoReport, vm.ImagePage);
                        Require(PanelPart("ImageNextActionButton").IsVisible && !PanelPart("WorkspaceSummaryCard").IsVisible && vm.ImageResults.Count == 0, "V5 no report: " + State());
                        vm.OutputPath = noReportPkg; Refresh();
                        AssertEqual(MainViewModel.ImagePageKind.NoReport, vm.ImagePage);
                        // 4) NO_TEXT: a COMPLETED scan with nothing to do; never "OCR chưa xong"
                        vm.OutputPath = noTextPkg; Refresh();
                        AssertEqual(MainViewModel.ImagePageKind.NoText, vm.ImagePage);
                        Require(!PanelPart("ImageNextActionButton").IsVisible && PanelPart("WorkspaceSummaryCard").IsVisible && !vm.ImageHasResults && !vm.ImageHasUntranslated, "V5 no text: completed state without a to-do action: " + State());
                        Require(vm.ImageWorkspaceSummary.Contains("Đã quét 3 ảnh", StringComparison.Ordinal) && !State().Contains("chưa", StringComparison.OrdinalIgnoreCase), "V5 no text: the count is the report's own (3 scanned): " + vm.ImageWorkspaceSummary + " / " + State());
                        // 5) results: counts only from the matching report
                        vm.OutputPath = resultsPkg; Refresh();
                        AssertEqual(MainViewModel.ImagePageKind.Results, vm.ImagePage);
                        Require(PanelText("LeadText").Text == "2 ảnh có chữ trong gói." && vm.ImageWorkspaceSummary.Contains("2 ảnh có chữ", StringComparison.Ordinal) && PanelPart("WorkspaceSummaryCard").IsVisible && !PanelPart("ImageNextActionButton").IsVisible,
                            "V5 results: " + State() + " / " + vm.ImageWorkspaceSummary);
                        // switching back to a package WITHOUT a report must not keep the previous counts
                        vm.OutputPath = noReportPkg; Refresh();
                        Require(vm.ImagePage == MainViewModel.ImagePageKind.NoReport && vm.ImageResults.Count == 0 && !PanelText("LeadText").Text.Any(char.IsDigit), "V5: no stale counts after switching package: " + State());
                        // 6) an unreadable report is its own state, not an empty scan
                        vm.OutputPath = brokenPkg; Refresh();
                        AssertEqual(MainViewModel.ImagePageKind.Unreadable, vm.ImagePage);
                        Require(PanelPart("ImageNextActionButton").IsVisible, "V5 unreadable: next action: " + State());
                        // A parseable report is not proof of a successful negative scan: failed
                        // images must never become the completed NO_TEXT state.
                        vm.OutputPath = failedScanPkg; Refresh();
                        AssertEqual(MainViewModel.ImagePageKind.ScanFailed, vm.ImagePage);
                        Require(PanelPart("ImageNextActionButton").IsVisible && !PanelPart("WorkspaceSummaryCard").IsVisible,
                            "V5 failed scan offers recovery and no successful counts: " + State());
                        Require(!State().Contains("không có ảnh chứa chữ", StringComparison.OrdinalIgnoreCase), "V5 failed scan is not NO_TEXT");
                        Require(PanelPart("EditImagesButton").IsVisible && vm.EnterImageEditCommand.CanExecute(null), "V5 failed scan retains the manual editor");
                        // English text of every state is catalogued
                        vm.Language = "en"; PumpFixture(250); Refresh();
                        AssertEqual("Image scanning could not finish.", PanelText("LeadText").Text);
                        Require(!PanelText("LeadText").Text.Contains("báo cáo", StringComparison.OrdinalIgnoreCase) && !PanelText("StateDetailText").Text.Contains("Báo cáo", StringComparison.Ordinal), "V5: English state text: " + State());
                        vm.OutputPath = resultsPkg; Refresh();
                        AssertEqual("2 images with text in the package.", PanelText("LeadText").Text);
                        vm.OutputPath = noTextPkg; Refresh();
                        Require(PanelText("LeadText").Text == "Scan finished: no image contains text." && PanelText("WorkspaceSummary").Text.StartsWith("Scanned 3 images", StringComparison.Ordinal), "V5 English no text: " + State() + " / " + vm.ImageWorkspaceSummary);
                        vm.Language = "vi"; PumpFixture(250); Refresh();

                        // ---------------- V6: About destination card idle border is the semantic token ----------------
                        Color Token(string key) => ((SolidColorBrush)window.FindResource(key)).Color;
                        var style = (Style)window.FindResource("AboutDestinationStyle");
                        var probe = new Button { Style = style, Content = "x", Width = 200, Height = 140 };
                        var host = (Panel)Named("AboutDestinationsGrid"); host.Children.Add(probe);
                        probe.ApplyTemplate(); probe.UpdateLayout(); window.UpdateLayout();
                        var cardBorder = FindVisualChildren<Border>(probe).First();
                        Require(((SolidColorBrush)probe.BorderBrush).Color == Token("CardBorderBrush"), $"V6 {theme}: the idle destination border is CardBorderBrush, not a hard-coded near-white (#F0F1F5)");
                        var infoStyle = (Style)window.FindResource("AboutInfoSurfaceStyle");
                        var neighbour = new Border { Style = infoStyle, Width = 200, Height = 140 };
                        host.Children.Add(neighbour); window.UpdateLayout();
                        Require(((SolidColorBrush)neighbour.BorderBrush).Color == ((SolidColorBrush)probe.BorderBrush).Color, $"V6 {theme}: the destination card matches the adjacent author card when idle");
                        // hover/focus stay blue and the card never changes size
                        var trigger = style.Triggers.OfType<Trigger>().Single(t => t.Property == UIElement.IsMouseOverProperty);
                        var hoverBrush = trigger.Setters.OfType<Setter>().Single(s => s.Property == Control.BorderBrushProperty).Value as SolidColorBrush;
                        Require(hoverBrush is not null && hoverBrush.Color == (Color)ColorConverter.ConvertFromString("#4063ED"), "V6: the blue hover border is unchanged");
                        Require(!trigger.Setters.OfType<Setter>().Any(s => s.Property == Control.BorderThicknessProperty || s.Property == FrameworkElement.WidthProperty || s.Property == FrameworkElement.HeightProperty || s.Property == FrameworkElement.MarginProperty),
                            "V6: hover changes no size/thickness (no layout shift)");
                        Require(cardBorder.BorderThickness.Left == 1, "V6: the destination card border thickness is constant");
                        host.Children.Remove(probe); host.Children.Remove(neighbour);
                        // the author card stays information, not a link
                        var author = FindVisualChildren<Border>((DependencyObject)Named("AboutDestinationsGrid")).First(b => System.Windows.Automation.AutomationProperties.GetName(b).StartsWith("Tác giả", StringComparison.Ordinal));
                        Require(author.Style == infoStyle && FindVisualChildren<Button>(author).Count() == 0, "V6: the author card stays an information card, not a button/link");

                        // ---------------- V7: a distinct image icon, same geometry language, route/order/label unchanged ----------------
                        var navButtons = FindVisualChildren<Button>(window).Where(b => b.CommandParameter is string s && new[] { "extract", "translate", "images", "editcsv", "patch" }.Contains(s)).ToList();
                        AssertEqual("extract,translate,images,editcsv,patch", string.Join(",", navButtons.Select(b => (string)b.CommandParameter)));      // order and routes unchanged
                        System.Windows.Shapes.Path IconOf(string route) => FindVisualChildren<System.Windows.Shapes.Path>(navButtons.Single(b => (string)b.CommandParameter == route)).First();
                        var imageIcon = IconOf("images"); var translateIcon = IconOf("translate");
                        Require(!ReferenceEquals(imageIcon.Data, translateIcon.Data) && imageIcon.Data.ToString() != translateIcon.Data.ToString(), "V7: Images and Auto translate no longer share one icon");
                        AssertEqual(translateIcon.Width, imageIcon.Width); AssertEqual(translateIcon.Height, imageIcon.Height);
                        AssertEqual(translateIcon.StrokeThickness, imageIcon.StrokeThickness); AssertEqual(translateIcon.Margin, imageIcon.Margin);
                        Require(ReferenceEquals(imageIcon.Style, translateIcon.Style) || imageIcon.Style.BasedOn == translateIcon.Style.BasedOn || imageIcon.Style == translateIcon.Style, "V7: the same nav icon style");
                        var a = imageIcon.Data.Bounds; var t2 = translateIcon.Data.Bounds;
                        Require(Math.Abs((a.Left + a.Width / 2) - 12) <= 1.5 && Math.Abs((a.Top + a.Height / 2) - 12) <= 1.5 && a.Width >= 16 && a.Width <= 20 && a.Height >= 16 && a.Height <= 20,
                            $"V7: the image icon sits on the same 24-unit grid, centred ({a}) like its siblings ({t2})");
                        Require(System.Windows.Automation.AutomationProperties.GetName(navButtons.Single(b => (string)b.CommandParameter == "images")) == "Dịch ảnh", "V7: the label is unchanged");
                        window.Close();
                    }
                    Console.WriteLine("WPF V-batch fixture: PASS (V4 typed severity page+journal, V5 six Images page states + Details + manual editor, V6 About border token Light/Dark, V7 distinct image icon)");
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
