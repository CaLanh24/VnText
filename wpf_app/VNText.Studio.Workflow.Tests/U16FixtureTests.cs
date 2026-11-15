using System.IO;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Documents;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using VNText.Studio.App;
using VNText.Studio.App.Controls;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;
using Ellipse = System.Windows.Shapes.Ellipse;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private static Color Rgb(Brush brush) => brush is SolidColorBrush solid ? solid.Color : throw new InvalidOperationException("solid brush expected, got " + brush.GetType().Name);
    private static string Hex(Color color) => $"#{color.R:X2}{color.G:X2}{color.B:X2}";
    private static double Luminance(Color c)
    {
        static double Lin(byte v) { var s = v / 255.0; return s <= 0.03928 ? s / 12.92 : Math.Pow((s + 0.055) / 1.055, 2.4); }
        return 0.2126 * Lin(c.R) + 0.7152 * Lin(c.G) + 0.0722 * Lin(c.B);
    }
    private static double Contrast(Color a, Color b)
    {
        var (hi, lo) = Luminance(a) >= Luminance(b) ? (Luminance(a), Luminance(b)) : (Luminance(b), Luminance(a));
        return (hi + 0.05) / (lo + 0.05);
    }
    private static Color Along(LinearGradientBrush gradient, double t)
    {
        var a = gradient.GradientStops[0].Color; var b = gradient.GradientStops[^1].Color;
        return Color.FromRgb((byte)Math.Round(a.R + (b.R - a.R) * t), (byte)Math.Round(a.G + (b.G - a.G) * t), (byte)Math.Round(a.B + (b.B - a.B) * t));
    }
    private static (byte[] Pixels, int Width, int Height) RenderPixels(FrameworkElement element, double width, double height)
    {
        element.Measure(new Size(width, height)); element.Arrange(new Rect(0, 0, width, height)); element.UpdateLayout();
        var bitmap = new RenderTargetBitmap((int)width, (int)height, 96, 96, PixelFormats.Pbgra32);
        bitmap.Render(element);
        var pixels = new byte[(int)width * (int)height * 4]; bitmap.CopyPixels(pixels, (int)width * 4, 0);
        return (pixels, (int)width, (int)height);
    }
    private static Color PixelAt((byte[] Pixels, int Width, int Height) image, int x, int y) { var i = (y * image.Width + x) * 4; return Color.FromRgb(image.Pixels[i + 2], image.Pixels[i + 1], image.Pixels[i]); }

    /// <summary>
    /// Polish batch U1–U9 / C1–C6 on the REAL MainWindow, JournalWindow and UpdateWindow (VI/Light/UI100, EN/Dark/UI120, VI/Dark/UI100, EN/Light/UI120): the
    /// shipped templates and tokens are rendered and measured; native hover/focus/pressed are proven separately on the running app.
    /// </summary>
    private static int RunU16Fixture()
    {
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            try
            {
                var root = Environment.GetEnvironmentVariable("VNTEXT_LOCALAPPDATA") ?? throw new InvalidOperationException("isolated root required");
                Require(Path.GetFullPath(root).Contains(Path.DirectorySeparatorChar + "TEST_RUN" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "the fixture needs the TEST_RUN isolated settings root");
                var app = new VNText.Studio.App.App();
                app.InitializeComponent();
                app.ShutdownMode = ShutdownMode.OnExplicitShutdown;
                var work = Path.Combine(TestTempRoot(), "u16_" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(work);
                var report = new List<string>();
                try
                {
                    // a real review + game image so the region editor (U2/U3) is the shipped one
                    var png = Path.Combine(work, "ui_01.png");
                    var encoder = new PngBitmapEncoder();
                    encoder.Frames.Add(BitmapFrame.Create(BitmapSource.Create(300, 120, 96, 96, PixelFormats.Bgra32, null, Enumerable.Repeat((byte)255, 300 * 120 * 4).ToArray(), 300 * 4)));
                    using (var stream = File.Create(png)) encoder.Save(stream);
                    var sourceHash = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(png))).ToLowerInvariant();
                    var review = Path.Combine(work, "image_text.json");
                    File.WriteAllText(review, JsonSerializer.Serialize(new ImageTextDocument
                    {
                        SourcePath = png, SourceSha256 = sourceHash, Width = 300, Height = 120, Status = "REVIEW_REQUIRED",
                        Regions = new List<ImageTextRegion> { new() { Id = "r1", Box = new[] { 10, 10, 200, 40 }, SourceText = "Hello" } },
                    }, MainViewModel.ImageJson), Encoding.UTF8);

                    var expectedTokens = new Dictionary<string, (string Light, string Dark)>
                    {
                        ["CtrlBorderBrush"] = ("#7B8798", "#71829C"), ["SettingsPreferenceBorderBrush"] = ("#7B8798", "#71829C"),
                        ["LineBrush"] = ("#E5E7EB", "#3B4B63"), ["CardBorderBrush"] = ("#E5E7EB", "#3B4B63"),                     // card/separator stay soft
                        ["BlueBrush"] = ("#2868E8", "#8CB5FF"),                                                                   // focus colour unchanged
                        ["SwitchOffTrackBrush"] = ("#CBD5E1", "#344258"), ["SwitchOffBorderBrush"] = ("#B5C0D0", "#506078"), ["SwitchOffKnobBrush"] = ("#FFFFFF", "#CBD5E1"),
                        ["SwitchOffHoverBrush"] = ("#BBC8D9", "#42536C"), ["SwitchOnTrackBrush"] = ("#2563EB", "#3A74E8"), ["SwitchOnKnobBrush"] = ("#FFFFFF", "#FFFFFF"),
                        ["InputErrorForegroundBrush"] = ("#B42318", "#FDA29B"), ["InputErrorBorderBrush"] = ("#B42318", "#FDA29B"), ["InputErrorSurfaceBrush"] = ("#FEF3F2", "#4A1F24"),
                        ["LogWarningForegroundBrush"] = ("#9A5B00", "#E0A33A"), ["ToastWarningBorderBrush"] = ("#B56D00", "#E0A33A"),
                        ["DisabledPrimaryBackgroundBrush"] = ("#E7EBF1", "#2B3545"), ["DisabledPrimaryForegroundBrush"] = ("#64748B", "#9AA7BA"), ["DisabledPrimaryBorderBrush"] = ("#D6DDE7", "#42506A"),
                        ["SettingsRowHoverBrush"] = ("#F0F5FC", "#2A394F"), ["NavHoverBrush"] = ("#DFE7F2", "#354258"), ["SecondaryHoverBackgroundBrush"] = ("#EFF5FF", "#273448"),
                    };
                    var expectedGradients = new Dictionary<string, (string[] Light, string[] Dark)>
                    {
                        ["PrimaryFillBrush"] = (["#2563EB", "#087C91"], ["#3264C8", "#0E7490"]),
                        ["PrimaryFillHoverBrush"] = (["#1D4ED8", "#0E6F80"], ["#2855B0", "#155E75"]),
                        ["PrimaryFillPressedBrush"] = (["#1E40AF", "#155E75"], ["#1E40AF", "#155E75"]),
                    };

                    foreach (var (language, theme, scale) in new[] { ("vi", "light", 1.0), ("en", "dark", 1.2), ("vi", "dark", 1.0), ("en", "light", 1.2) })
                    {
                        var dark = theme == "dark";
                        var tag = $"{language}/{theme}/UI{scale * 100:0}";
                        var picker = new FakePathPicker();
                        var vm = new MainViewModel(picker, new PythonWorkerHost(), startWorker: false);
                        vm.Language = language; vm.Theme = theme; vm.UiScale = scale;
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal; window.Width = 1055; window.Height = 720;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1")
                        {
                            window.WindowStartupLocation = WindowStartupLocation.Manual;
                            window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false;
                        }
                        window.Show(); window.UpdateLayout(); PumpFixture(250);
                        FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                        Color Token(string key) => Rgb((Brush)window.FindResource(key));
                        void Page(string tab) { vm.NavigateTabCommand.Execute(tab); window.UpdateLayout(); PumpFixture(200); window.UpdateLayout(); }

                        // ---------- source tokens (what the app resolves after Apply) ----------
                        foreach (var (key, pair) in expectedTokens) AssertEqual(dark ? pair.Dark : pair.Light, Hex(Token(key)));
                        foreach (var (key, pair) in expectedGradients)
                        {
                            var gradient = (LinearGradientBrush)window.FindResource(key);
                            AssertEqual(string.Join(">", dark ? pair.Dark : pair.Light), string.Join(">", gradient.GradientStops.Select(s => Hex(s.Color))));
                        }

                        // ---------- C1: white text/icon on the primary gradient at EVERY sampled position, idle/hover/pressed (not only the endpoints) ----------
                        var contrastRows = new List<string>();
                        foreach (var key in new[] { "PrimaryFillBrush", "PrimaryFillHoverBrush", "PrimaryFillPressedBrush" })
                        {
                            var gradient = (LinearGradientBrush)window.FindResource(key);
                            var worst = Enumerable.Range(0, 41).Select(i => Contrast(Colors.White, Along(gradient, i / 40.0))).Min();
                            Require(worst >= 4.5, $"{tag} C1: white on {key} is >= 4.5:1 along the whole gradient (worst {worst:0.00})");
                            contrastRows.Add($"{key}={worst:0.00}");
                        }
                        // the rendered button: background pixels above the label across the width (the label itself is excluded)
                        var primary = new Button { Style = (Style)app.FindResource("PrimaryButton"), Content = "Mở bước Lấy text", Width = 220, Height = 36 };
                        var shot = RenderPixels(primary, 220, 36);
                        var renderedWorst = Enumerable.Range(8, 204).Select(x => Contrast(Colors.White, PixelAt(shot, x, 3))).Min();
                        Require(renderedWorst >= 4.5, $"{tag} C1: the RENDERED primary button keeps white label contrast >= 4.5:1 ({renderedWorst:0.00})");
                        Require(Rgb(primary.Foreground) == Colors.White, $"{tag} C1: label stays #FFFFFF");

                        // ---------- C5: a disabled primary is neutral (not the selected/brand hue), keeps its label readable and shows no hover/active fill ----------
                        var disabled = new Button { Style = (Style)app.FindResource("PrimaryButton"), Content = "Bắt đầu dịch", Width = 160, Height = 36, IsEnabled = false };
                        RenderPixels(disabled, 160, 36);
                        var surface = (Border)disabled.Template.FindName("PrimarySurface", disabled); var edge = (Border)disabled.Template.FindName("DisabledEdge", disabled);
                        AssertEqual(dark ? "#2B3545" : "#E7EBF1", Hex(Rgb(surface.Background)));
                        AssertEqual(dark ? "#42506A" : "#D6DDE7", Hex(Rgb(edge.BorderBrush)));
                        AssertEqual(dark ? "#9AA7BA" : "#64748B", Hex(Rgb(disabled.Foreground)));
                        Require(surface.Effect is null && !disabled.IsMouseOver, $"{tag} C5: disabled primary carries no elevation/hover");
                        Require(Contrast(Rgb(disabled.Foreground), Rgb(surface.Background)) >= 3.9, $"{tag} C5: the disabled label remains readable");
                        Require(Contrast(Rgb(surface.Background), Token("SurfaceBrush")) < 1.6 && Rgb(surface.Background) != Token("BlueSoftBrush") && Rgb(surface.Background) != Token("NavActiveBackgroundBrush"), $"{tag} C5: disabled is neither brand-tinted nor the selected fill");

                        // ---------- C4: idle control borders are recognisable (rendered pixels) while the card line stays soft ----------
                        var field = new TextBox { Style = (Style)app.FindResource("CompactFieldTextBoxStyle"), Width = 120 };
                        var fieldShot = RenderPixels(field, 120, 32);
                        var fieldInterior = PixelAt(fieldShot, 60, 16);
                        var borderPixel = Enumerable.Range(0, 2).Select(y => PixelAt(fieldShot, 60, y)).OrderByDescending(p => Contrast(p, fieldInterior)).First();
                        Require(Hex(borderPixel) == (dark ? "#71829C" : "#7B8798"), $"{tag} C4: the rendered text-input border is the control token ({Hex(borderPixel)})");
                        Require(Contrast(borderPixel, fieldInterior) >= 3.0, $"{tag} C4: idle input border is >= 3:1 on its field ({Contrast(borderPixel, fieldInterior):0.00})");
                        var outline = new Button { Style = (Style)app.FindResource("OutlineButton"), Content = "Sửa ảnh", Width = 120, Height = 36 };
                        var outlineShot = RenderPixels(outline, 120, 36);
                        var outlineBorder = Enumerable.Range(0, 2).Select(y => PixelAt(outlineShot, 60, y)).OrderByDescending(p => Contrast(p, Token("SurfaceBrush"))).First();
                        Require(Hex(outlineBorder) == (dark ? "#71829C" : "#7B8798") && Contrast(outlineBorder, Token("SurfaceBrush")) >= 3.0, $"{tag} C4: the rendered outline-button border ({Hex(outlineBorder)}) is the control token and >= 3:1 on the card");
                        Require(Contrast(Token("CardBorderBrush"), Token("SurfaceBrush")) < 2.0, $"{tag} C4: the card border stays soft");
                        Require(Hex(Token("BlueBrush")) == (dark ? "#8CB5FF" : "#2868E8"), $"{tag} C4: focus colour unchanged");

                        // ---------- C2: WARN foreground is its own token, readable on the log panel; the toast border is untouched ----------
                        var logBox = new SeverityLogBox { Text = "WARN: resource-status missing\nERROR: x\nOK" };
                        var warnRun = logBox.Document.Blocks.OfType<Paragraph>().First().Inlines.OfType<Run>().First();
                        var warnForeground = Rgb((Brush)(warnRun.TryFindResource("LogWarningForegroundBrush") ?? throw new InvalidOperationException("token")));
                        AssertEqual(dark ? "#E0A33A" : "#9A5B00", Hex(warnForeground));
                        Require(Contrast(warnForeground, Token("LogPanelBrush")) >= 4.5, $"{tag} C2: WARN text on the log panel >= 4.5:1 ({Contrast(warnForeground, Token("LogPanelBrush")):0.00})");

                        // ---------- U2 / C3 on a live window: switches, then (below) region radios + approval; a theme change restyles controls that already exist ----------
                        Page("translate");
                        var switches = FindVisualChildren<CheckBox>(window).Where(c => ReferenceEquals(c.Style, app.FindResource("SwitchStyle")) && c.IsVisible).ToList();
                        Require(switches.Count >= 2, $"{tag} C3: the translate rules expose their switches ({switches.Count})");
                        var toggle = switches[0];
                        var wasChecked = toggle.IsChecked == true;
                        toggle.IsChecked = false; toggle.UpdateLayout();
                        Border Track(CheckBox c) => (Border)c.Template.FindName("Track", c);
                        Ellipse Thumb(CheckBox c) => (Ellipse)c.Template.FindName("Thumb", c);
                        AssertEqual(dark ? "#344258" : "#CBD5E1", Hex(Rgb(Track(toggle).Background)));
                        AssertEqual(dark ? "#506078" : "#B5C0D0", Hex(Rgb(Track(toggle).BorderBrush)));
                        AssertEqual(dark ? "#CBD5E1" : "#FFFFFF", Hex(Rgb(Thumb(toggle).Fill)));
                        Require(Contrast(Rgb(Track(toggle).Background), Token("SurfaceBrush")) < 2.0 || dark, $"{tag} C3: OFF is a quiet fill on the card");
                        toggle.IsChecked = true; toggle.UpdateLayout();
                        AssertEqual(dark ? "#3A74E8" : "#2563EB", Hex(Rgb(Track(toggle).Background)));
                        AssertEqual("#FFFFFF", Hex(Rgb(Thumb(toggle).Fill)));
                        Require(Contrast(Rgb(Track(toggle).Background), Colors.White) >= 3.0, $"{tag} C3: knob stays distinct on the ON track");
                        toggle.IsChecked = false; toggle.UpdateLayout();
                        var disabledSwitch = new CheckBox { Style = (Style)app.FindResource("SwitchStyle"), IsEnabled = false, IsChecked = false };
                        RenderPixels(disabledSwitch, 60, 30);
                        AssertEqual(Hex(Token("DisabledBackgroundBrush")), Hex(Rgb(Track(disabledSwitch).Background)));
                        // live theme change on the SAME instance
                        var other = dark ? "light" : "dark";
                        vm.Theme = other; PumpFixture(150); window.UpdateLayout(); toggle.UpdateLayout();
                        AssertEqual(other == "dark" ? "#344258" : "#CBD5E1", Hex(Rgb(Track(toggle).Background)));
                        AssertEqual(other == "dark" ? "#CBD5E1" : "#FFFFFF", Hex(Rgb(Thumb(toggle).Fill)));
                        toggle.IsChecked = true; toggle.UpdateLayout();
                        AssertEqual(other == "dark" ? "#3A74E8" : "#2563EB", Hex(Rgb(Track(toggle).Background)));
                        toggle.IsChecked = wasChecked;

                        // ---------- U5 / U6 (Translate page) ----------
                        string[] axisLabels = ["Nguồn dịch", "Mô hình dịch", "Tiến trình dịch", "Thuật ngữ ưu tiên", "Quy tắc dịch"];
                        double LeftOf(string vietnamese)
                        {
                            var shown = UiText.Translate(vietnamese);
                            var block = FindVisualChildren<TextBlock>(Named("TranslatePage")).FirstOrDefault(t => t.Text == shown && t.IsVisible);
                            return block is null ? double.NaN : block.TranslatePoint(new Point(0, 0), window).X;
                        }
                        var lefts = axisLabels.Select(l => (l, x: LeftOf(l))).Where(p => !double.IsNaN(p.x)).ToList();
                        Require(lefts.Count >= 3 && lefts.Any(p => p.l == "Nguồn dịch") && lefts.Any(p => p.l == "Thuật ngữ ưu tiên"), $"{tag} U6: the sub-headings are present ({string.Join(", ", lefts.Select(p => p.l))})");
                        var spread = lefts.Max(p => p.x) - lefts.Min(p => p.x);
                        Require(spread < 1.0, $"{tag} U6: same-level headings share one left axis (spread {spread:0.##} DIP: {string.Join(", ", lefts.Select(p => $"{p.l}={p.x:0.#}"))})");
                        vm.Theme = theme; PumpFixture(100);

                        foreach (var (tab, pageName) in new[] { ("extract", "ExtractPage"), ("translate", "TranslatePage"), ("patch", "PatchPage") })
                        {
                            window.Width = 1055; window.Height = 720; Page(tab);
                            var scroller = (ScrollViewer)Named("PageScrollViewer"); var page = Named(pageName);
                            Require(Math.Abs(page.ActualWidth - scroller.ViewportWidth) < 1.0 && scroller.ScrollableWidth < 0.5, $"{tag} U5: {pageName} follows a small window ({page.ActualWidth:0}/{scroller.ViewportWidth:0}, no horizontal scroll)");
                            window.Width = 2400; window.Height = 900; Page(tab);
                            Require(page.ActualWidth <= 1120.5 && Math.Abs(page.ActualWidth - Math.Min(scroller.ViewportWidth, 1120)) < 1.0, $"{tag} U5: {pageName} is min(viewport {scroller.ViewportWidth:0.#}, shared 1120 DIP cap) = {page.ActualWidth:0.#}");
                            Require(Math.Abs(page.TranslatePoint(new Point(0, 0), scroller).X) < 1.0, $"{tag} U5: {pageName} keeps the left content axis");
                            Require(scroller.ScrollableWidth < 0.5, $"{tag} U5: no horizontal scroll on a wide window");
                        }
                        Page("settings");
                        var settingsTabs = FindVisualChildren<TabControl>(Named("SettingsScrollViewer")).First();
                        var settingsHost = (FrameworkElement)settingsTabs.Template.FindName("SettingsContentHost", settingsTabs);
                        Require(settingsHost.ActualWidth <= 1120.5 && Math.Abs(settingsHost.ActualWidth - Math.Min(settingsTabs.ActualWidth, 1120)) < 1.0, $"{tag} U5: Settings content is min(width {settingsTabs.ActualWidth:0.#}, 1120) = {settingsHost.ActualWidth:0.#}");
                        Page("editcsv");
                        vm.TestLoadCsvRows(Path.Combine(work, "translation.csv"), Enumerable.Range(1, 7).Select(i => new CsvEditorRow { Index = i, Key = "k" + i, SourceText = "Hello " + i, Translation = "Xin chào " + i }).ToList(), "OK");
                        window.UpdateLayout(); PumpFixture(250);
                        window.Width = 2400; window.Height = 900; window.UpdateLayout(); PumpFixture(200); window.UpdateLayout();
                        Require(window.ActualWidth > 1500 && Named("CsvEditorGrid").ActualWidth >= ((ScrollViewer)Named("PageScrollViewer")).ViewportWidth - 80, $"{tag} U5: the CSV table is not capped (grid {Named("CsvEditorGrid").ActualWidth:0}, window {window.ActualWidth:0})");
                        Page("images");
                        var imagePanel = FindVisualChildren<ImageWorkspacePanel>(window).First();
                        window.Width = 2400; window.UpdateLayout(); PumpFixture(150);
                        Require(imagePanel.ActualWidth >= ((ScrollViewer)Named("PageScrollViewer")).ViewportWidth - 80, $"{tag} U5: the image page keeps the full area ({imagePanel.ActualWidth:0}, window {window.ActualWidth:0})");

                        // ---------- U7: one action row at both sizes ----------
                        foreach (var (width, height) in new[] { (2400.0, 900.0), (1055.0, 720.0) })
                        {
                            window.Width = width; window.Height = height; Page("images");
                            FrameworkElement P(string n) => (FrameworkElement)(imagePanel.FindName(n) ?? throw new InvalidOperationException(n));
                            Require(P("ImageNextActionButton").IsVisible && P("EditImagesButton").IsVisible, $"{tag} U7: both actions are offered in the empty state");
                            var nextTop = P("ImageNextActionButton").TranslatePoint(new Point(0, 0), window).Y; var editTop = P("EditImagesButton").TranslatePoint(new Point(0, 0), window).Y;
                            Require(Math.Abs((nextTop + P("ImageNextActionButton").ActualHeight / 2) - (editTop + P("EditImagesButton").ActualHeight / 2)) < 1.5, $"{tag} U7: 'Mở bước Lấy text' and 'Sửa ảnh' share one row at {width:0}");
                            var nextLeft = P("ImageNextActionButton").TranslatePoint(new Point(0, 0), window).X; var editLeft = P("EditImagesButton").TranslatePoint(new Point(0, 0), window).X;
                            Require(editLeft > nextLeft + P("ImageNextActionButton").ActualWidth - 1, $"{tag} U7: reading/Tab order is primary first, then the manual editor");
                            Require(P("ImageDetailsButton").TranslatePoint(new Point(0, 0), window).Y < nextTop, $"{tag} U7: 'Chi tiết' is the light disclosure next to the help text, above the actions");
                            Require(vm.EnterImageEditCommand.CanExecute(null), $"{tag} U7: the manual editor stays independently available");
                        }
                        window.Width = 1055; window.Height = 720;

                        // ---------- U2 + U3 on the region details (real review loaded) ----------
                        Require(vm.TryLoadImageReview(review), $"{tag} review loads");
                        vm.EnterImageEditCommand.Execute(null); window.UpdateLayout(); PumpFixture(150);
                        var region = vm.ImageRegions[0]; vm.SelectedImageRegion = region; window.UpdateLayout(); PumpFixture(200);
                        TextBox T(string n) => (TextBox)imagePanel.FindName(n);
                        // U2 radios / approval: token fills, no stock white, live theme change
                        var radio = (RadioButton)imagePanel.FindName("FlatModeBox"); var approve = (CheckBox)imagePanel.FindName("ApproveBox");
                        Ellipse Disc(RadioButton r) => (Ellipse)r.Template.FindName("Disc", r);
                        Border Box(CheckBox c) => (Border)c.Template.FindName("Box", c);
                        radio.UpdateLayout(); approve.UpdateLayout();
                        AssertEqual(Hex(Token("FieldBackgroundBrush")), Hex(Rgb(Disc(radio).Fill)));
                        AssertEqual(Hex(Token("CtrlBorderBrush")), Hex(Rgb(Disc(radio).Stroke)));
                        Require(!dark || Hex(Rgb(Disc(radio).Fill)) != "#FFFFFF", $"{tag} U2: the unchecked radio is not the stock white face in Dark");
                        AssertEqual(Hex(Token("FieldBackgroundBrush")), Hex(Rgb(Box(approve).Background)));
                        Require(Contrast(Rgb(Disc(radio).Stroke), Rgb(Disc(radio).Fill)) >= 3.0 && Contrast(Rgb(Box(approve).BorderBrush), Rgb(Box(approve).Background)) >= 3.0, $"{tag} U2: unchecked outline >= 3:1");
                        radio.RaiseEvent(new RoutedEventArgs(System.Windows.Controls.Primitives.ButtonBase.ClickEvent)); PumpFixture(60); window.UpdateLayout();
                        Require(region.FlatBackgroundApproved && radio.IsChecked == true, $"{tag} U2: choosing a mode still sets exactly that mode");
                        Require(!region.TransparentTextApproved && !region.ReplacementBackgroundApproved && !region.CloneBackgroundApproved, $"{tag} U2: still exactly one mode");
                        AssertEqual(Visibility.Visible, ((Ellipse)radio.Template.FindName("Dot", radio)).Visibility);
                        AssertEqual(Hex(Token("BlueBrush")), Hex(Rgb(Disc(radio).Stroke)));
                        approve.IsChecked = true; window.UpdateLayout();
                        AssertEqual(Hex(Token("BlueBrush")), Hex(Rgb(Box(approve).Background)));
                        Require(region.Approved, $"{tag} U2: approval binding unchanged");
                        approve.IsChecked = false;
                        radio.IsEnabled = false; approve.IsEnabled = false; window.UpdateLayout();
                        AssertEqual(Hex(Token("DisabledBackgroundBrush")), Hex(Rgb(Disc(radio).Fill)));
                        AssertEqual(Hex(Token("DisabledBorderBrush")), Hex(Rgb(Box(approve).BorderBrush)));
                        radio.ClearValue(UIElement.IsEnabledProperty); approve.ClearValue(UIElement.IsEnabledProperty);
                        var radioFaceBefore = Hex(Rgb(Disc(radio).Fill)); var boxBefore = Hex(Rgb(Box(approve).Background));
                        // (the live switch of an unchecked control) — use another unchecked radio so the instance exists across the switch
                        var transparentRadio = (RadioButton)imagePanel.FindName("TransparentModeBox"); transparentRadio.UpdateLayout();
                        var faceBefore = Hex(Rgb(Disc(transparentRadio).Fill));
                        vm.Theme = other; PumpFixture(150); window.UpdateLayout(); transparentRadio.UpdateLayout();
                        var faceAfter = Hex(Rgb(Disc(transparentRadio).Fill));
                        AssertEqual(Hex(Token("FieldBackgroundBrush")), faceAfter);
                        Require(faceBefore != faceAfter, $"{tag} U2: an existing radio restyles on a live theme change ({faceBefore} -> {faceAfter})");
                        vm.Theme = theme; PumpFixture(100); window.UpdateLayout();

                        // U3 numeric validation
                        var numericBoxes = new[] { ("RegionXBox", 0, 99999), ("RegionYBox", 0, 99999), ("RegionWidthBox", 1, 99999), ("RegionHeightBox", 1, 99999), ("RegionFontBox", 1, 999), ("DonorXBox", 0, 99999), ("DonorYBox", 0, 99999) };
                        var fontBox = T("RegionFontBox");
                        // ---- U3 execution defence: a rejected draft must not let Save/Render/package/install/approval run on the stale (last valid) model ----
                        region.FlatBackgroundApproved = true; region.Approved = true; vm.OutputPath = work;
                        Require(!vm.ImageDraftInvalid && vm.SaveImageReviewCommand.CanExecute(null) && vm.RenderImageCommand.CanExecute(null) && approve.IsEnabled, $"{tag} U3 guard: a valid approved region keeps the actions available");
                        var reviewDirs = () => Directory.GetDirectories(work, "image-review-*").Length;
                        var dirsBefore = reviewDirs();
                        foreach (var draft in new[] { "abc", "", "1000", "0" })
                        {
                            fontBox.Text = draft; window.UpdateLayout(); PumpFixture(60);
                            Require(Validation.GetHasError(fontBox) && vm.ImageDraftInvalid, $"{tag} U3 guard: '{draft}' marks the draft invalid in the VM");
                            Require(region.FontSize == 24 && region.Approved && region.FlatBackgroundApproved, $"{tag} U3 guard: the model keeps its last valid number and approval (no coercion)");
                            Require(!vm.SaveImageReviewCommand.CanExecute(null) && !vm.RenderImageCommand.CanExecute(null) && !vm.CreateImageDeliveryCommand.CanExecute(null) && !vm.InstallImageDeliveryCommand.CanExecute(null), $"{tag} U3 guard: Save/Render/package/install are disabled");
                            Require(!approve.IsEnabled, $"{tag} U3 guard: the approval box is disabled");
                            vm.SaveImageReviewCommand.Execute(null); vm.RenderImageCommand.Execute(null);        // Execute ignores CanExecute: the command body must refuse too
                            Require(reviewDirs() == dirsBefore && !vm.Busy, $"{tag} U3 guard: no review folder written and no render task started");
                            Require(UiText.TranslateDynamic(vm.ImageStatus).StartsWith(language == "vi" ? "Chưa thể" : "Cannot", StringComparison.Ordinal), $"{tag} U3 guard: the refusal is explained ({vm.ImageStatus})");
                        }
                        fontBox.Text = "24"; window.UpdateLayout(); PumpFixture(60);              // corrected (same number): drafting ends, the actions return
                        Require(!vm.ImageDraftInvalid && vm.SaveImageReviewCommand.CanExecute(null) && vm.RenderImageCommand.CanExecute(null) && approve.IsEnabled, $"{tag} U3 guard: a corrected value clears the block");
                        fontBox.Text = "abc"; window.UpdateLayout(); PumpFixture(60);
                        var second = new ImageTextRegion { Id = "r2", Box = new[] { 10, 60, 100, 30 }, SourceText = "World" }; vm.ImageRegions.Add(second);
                        vm.SelectedImageRegion = second; window.UpdateLayout(); PumpFixture(120); window.UpdateLayout();
                        Require(!vm.ImageDraftInvalid && vm.SaveImageReviewCommand.CanExecute(null), $"{tag} U3 guard: selecting another region clears the draft block");
                        vm.SelectedImageRegion = region; window.UpdateLayout(); PumpFixture(120); window.UpdateLayout();
                        Require(T("RegionFontBox").Text == "24" && !vm.ImageDraftInvalid, $"{tag} U3 guard: the dropped draft is gone, the model value is shown");
                        T("RegionXBox").Text = "x"; window.UpdateLayout(); PumpFixture(60);
                        Require(vm.ImageDraftInvalid, $"{tag} U3 guard: any numeric field counts (X)");
                        Require(vm.TryLoadImageReview(review), $"{tag} U3 guard: reload"); window.UpdateLayout(); PumpFixture(150);
                        Require(!vm.ImageDraftInvalid && vm.SaveImageReviewCommand.CanExecute(null), $"{tag} U3 guard: a review reload clears the draft block");
                        region = vm.ImageRegions[0]; vm.SelectedImageRegion = region; window.UpdateLayout(); PumpFixture(150); fontBox = T("RegionFontBox");
                        fontBox.Text = "abc"; window.UpdateLayout(); PumpFixture(60);
                        Require(vm.ImageDraftInvalid, $"{tag} U3 guard: draft again before unload");
                        vm.ImageRegions.Clear(); vm.SelectedImageRegion = null; window.UpdateLayout(); PumpFixture(150); window.UpdateLayout();
                        Require(!vm.ImageDraftInvalid, $"{tag} U3 guard: unloading the regions clears the draft block (no stale global block)");
                        Require(vm.TryLoadImageReview(review), $"{tag} U3 guard: reload after unload"); window.UpdateLayout(); PumpFixture(150);
                        region = vm.ImageRegions[0]; vm.SelectedImageRegion = region; window.UpdateLayout(); PumpFixture(150); fontBox = T("RegionFontBox"); approve = (CheckBox)imagePanel.FindName("ApproveBox"); radio = (RadioButton)imagePanel.FindName("FlatModeBox");
                        var heightBefore = fontBox.ActualHeight; var parent = (FrameworkElement)fontBox.Parent; var parentHeightBefore = parent.ActualHeight;
                        var oldFont = region.FontSize;
                        foreach (var (text, kind) in new[] { ("", "whole"), ("abc", "whole"), ("12.5", "whole"), ("0", "range"), ("1000", "range"), ("-5", "range") })
                        {
                            fontBox.Text = text; window.UpdateLayout(); PumpFixture(60);
                            Require(Validation.GetHasError(fontBox), $"{tag} U3: '{text}' is an error");
                            AssertEqual(oldFont, region.FontSize);                         // nothing is coerced or written
                            var shown = UiText.TranslateDynamic((string)Validation.GetErrors(fontBox)[0].ErrorContent);
                            AssertEqual(kind == "whole" ? (language == "vi" ? "Nhập số nguyên hợp lệ" : "Enter a valid whole number")
                                                        : (language == "vi" ? "Nhập số nguyên từ 1 đến 999" : "Enter a whole number from 1 to 999"), shown);
                            var surfaceBorder = (Border)fontBox.Template.FindName("FieldSurface", fontBox);
                            AssertEqual(dark ? "#FDA29B" : "#B42318", Hex(Rgb(surfaceBorder.BorderBrush)));
                            AssertEqual(dark ? "#4A1F24" : "#FEF3F2", Hex(Rgb(surfaceBorder.Background)));
                            Require(AdornerLayer.GetAdornerLayer(fontBox)?.GetAdorners(fontBox)?.Length > 0, $"{tag} U3: the error hint adorner is present");
                            Require(Math.Abs(fontBox.ActualHeight - heightBefore) < 0.5 && Math.Abs(parent.ActualHeight - parentHeightBefore) < 0.5, $"{tag} U3: the error does not move the layout");
                        }
                        Require(Contrast(Rgb((Brush)window.FindResource("InputErrorForegroundBrush")), Rgb((Brush)window.FindResource("SurfaceBrush"))) >= 4.5, $"{tag} U3: hint foreground is readable on the card");
                        fontBox.Text = "30"; window.UpdateLayout(); PumpFixture(60);
                        Require(!Validation.GetHasError(fontBox) && region.FontSize == 30, $"{tag} U3: fixing the value clears the error and applies it");
                        AssertEqual(Hex(Token("CtrlBorderBrush")), Hex(Rgb(((Border)fontBox.Template.FindName("FieldSurface", fontBox)).BorderBrush)));
                        foreach (var (name, minimum, maximum) in numericBoxes)
                        {
                            var box = T(name);
                            foreach (var bad in new[] { "", "x", (maximum + 1).ToString(), (minimum - 1).ToString() })
                            {
                                box.Text = bad; PumpFixture(30);
                                Require(Validation.GetHasError(box), $"{tag} U3: {name} rejects '{bad}'");
                            }
                            box.Text = minimum.ToString(); PumpFixture(30);
                            Require(!Validation.GetHasError(box), $"{tag} U3: {name} accepts {minimum}");
                        }
                        Require(region.Width >= 1 && region.Height >= 1 && region.X >= 0 && region.Y >= 0 && region.FontSize >= 1, $"{tag} U3: the model only ever holds valid numbers");
                        report.Add(tag);

                        // ---------- U4: the CSV tools label follows the language, open and closed, including an auto fold ----------
                        window.Width = 1055; window.Height = 720; Page("editcsv"); PumpFixture(300); window.UpdateLayout(); PumpFixture(150);
                        vm.CsvBulkFind = "Hello"; PumpFixture(60); window.UpdateLayout();
                        vm.TestLoadCsvRows(Path.Combine(work, "translation.csv"), Enumerable.Range(1, 7).Select(i => new CsvEditorRow { Index = i, Key = "k" + i, SourceText = "Hello " + i, Translation = "Xin chào " + i }).ToList(), "OK");
                        window.UpdateLayout(); PumpFixture(300); window.UpdateLayout(); PumpFixture(150);
                        if (!vm.CsvToolsTight && scale < 1.1) { vm.UiScale = 1.2; window.UpdateLayout(); PumpFixture(300); window.UpdateLayout(); PumpFixture(150); }   // 1055x720 folds the tools at 120%, as the N-batch fixture relies on
                        Require(vm.CsvToolsTight, $"{tag} U4: precondition: a small window folds the tools (the table budget wins)");
                        string ToggleText() { window.UpdateLayout(); PumpFixture(120); window.UpdateLayout(); return FindVisualChildren<TextBlock>(Named("CsvToolsToggleButton")).First().Text; }
                        string Expect(string vi, string en, string lang) => lang == "vi" ? vi : en;
                        AssertEqual(Expect("Mở rộng", "Expand", language), ToggleText());
                        var otherLanguage = language == "vi" ? "en" : "vi";
                        vm.Language = otherLanguage; PumpFixture(80); window.UpdateLayout();
                        AssertEqual(Expect("Mở rộng", "Expand", otherLanguage), ToggleText());
                        AssertEqual("Hello", vm.CsvBulkFind);                                                  // typed text survives
                        vm.ToggleCsvToolsCommand.Execute(null); PumpFixture(80); window.UpdateLayout();
                        Require(vm.CsvToolsOpen, $"{tag} U4: the tools are open (tight {vm.CsvToolsTight}, vm text {vm.CsvToolsToggleText})");
                        AssertEqual(Expect("Thu gọn", "Collapse", otherLanguage), ToggleText());
                        vm.Language = language; PumpFixture(80); window.UpdateLayout();
                        AssertEqual(Expect("Thu gọn", "Collapse", language), ToggleText());
                        vm.ToggleCsvToolsCommand.Execute(null); PumpFixture(80);
                        AssertEqual(Expect("Mở rộng", "Expand", language), ToggleText());
                        vm.CsvBulkFind = ""; vm.UiScale = scale;

                        // ---------- U1: Glossary pairs are fully readable by tooltip and by keyboard (the detail strip follows the focused row) ----------
                        var longTerm = "A very long in-game term that certainly does not fit in half of the glossary row " + new string('x', 40);
                        var longTranslation = "Một bản dịch rất dài, vượt quá nửa hàng thuật ngữ nên bị cắt bởi dấu ba chấm " + new string('y', 40);
                        vm.GlossaryEntries.Clear();
                        vm.GlossaryEntries.Add(new GlossaryItem(longTerm, longTranslation)); vm.GlossaryEntries.Add(new GlossaryItem("short", "ngắn"));
                        Page("translate");
                        var editGlossary = (Button)Named("GlossaryEditButton");
                        editGlossary.RaiseEvent(new RoutedEventArgs(System.Windows.Controls.Primitives.ButtonBase.ClickEvent)); window.UpdateLayout(); PumpFixture(200); window.UpdateLayout();
                        var list = (ListBox)Named("GlossaryListBox"); var strip = Named("GlossaryDetailStrip");
                        Require(!strip.IsVisible, $"{tag} U1: no detail strip until a row is focused/selected");
                        var firstRow = (ListBoxItem)list.ItemContainerGenerator.ContainerFromIndex(0);
                        var rowGrid = FindVisualChildren<Grid>(firstRow).First(g => g.ToolTip is ToolTip);
                        var rowTooltip = (ToolTip)rowGrid.ToolTip; Require(rowTooltip.ContentTemplate is null && rowTooltip.Content is StackPanel, $"{tag} U1: the tooltip shows its own content (the global ToolTip style would otherwise print the type name)"); rowTooltip.DataContext = rowGrid.DataContext;          // what the tooltip service does when it opens over the row
                        static IEnumerable<TextBlock> LogicalTexts(DependencyObject node) { if (node is TextBlock block) yield return block; foreach (var child in LogicalTreeHelper.GetChildren(node).OfType<DependencyObject>()) foreach (var inner in LogicalTexts(child)) yield return inner; }
                        var tipTexts = LogicalTexts((DependencyObject)rowTooltip.Content).Select(t => t.Text).ToList();
                        Require(tipTexts.Contains(longTerm) && tipTexts.Contains(longTranslation), $"{tag} U1: the tooltip carries both full sides");
                        var clipped = FindVisualChildren<TextBlock>(rowGrid).Where(t => t.Text == longTerm || t.Text == longTranslation).ToList();
                        Require(clipped.Count == 2 && clipped.All(t => t.TextTrimming == TextTrimming.CharacterEllipsis), $"{tag} U1: the row keeps its density (still ellipsis)");
                        list.Focus(); list.SelectedIndex = 0; window.UpdateLayout(); PumpFixture(100); window.UpdateLayout();      // what Up/Down does through the ListBox
                        Require(strip.IsVisible, $"{tag} U1: keyboard selection opens the detail strip");
                        AssertEqual(longTerm, ((TextBlock)Named("GlossaryDetailTerm")).Text); AssertEqual(longTranslation, ((TextBlock)Named("GlossaryDetailTranslation")).Text);
                        Require(strip.ActualHeight > 40, $"{tag} U1: the strip shows the wrapped pair");
                        var stripBottom = strip.TranslatePoint(new Point(0, strip.ActualHeight), window).Y;
                        var card = (FrameworkElement)Named("GlossaryOverlay"); var cardBox = FindVisualChildren<Border>(card).First(b => b.MaxHeight == 610);
                        Require(stripBottom <= cardBox.TranslatePoint(new Point(0, cardBox.ActualHeight), window).Y + 0.5 && stripBottom <= window.ActualHeight, $"{tag} U1: the strip is inside the dialog card and the window (bottom {stripBottom:0.#}, card {cardBox.ActualHeight:0.#})");
                        var entriesBefore = vm.GlossaryEntries.Count;
                        Require(vm.GlossaryEntries[0].Term == longTerm && vm.GlossaryEntries[0].Translation == longTranslation && vm.GlossaryEntries.Count == entriesBefore, $"{tag} U1: reading changes nothing");
                        list.SelectedIndex = 1; window.UpdateLayout(); PumpFixture(60);
                        AssertEqual("short", ((TextBlock)Named("GlossaryDetailTerm")).Text);
                        list.SelectedIndex = -1; window.UpdateLayout(); PumpFixture(60);
                        Require(!strip.IsVisible, $"{tag} U1: the strip hides with no row");
                        firstRow.RaiseEvent(new System.Windows.Input.KeyboardFocusChangedEventArgs(System.Windows.Input.Keyboard.PrimaryDevice, 0, null, firstRow) { RoutedEvent = UIElement.GotKeyboardFocusEvent });
                        window.UpdateLayout(); PumpFixture(60);
                        Require(strip.IsVisible && list.SelectedIndex == 0, $"{tag} U1: keyboard focus on the row selects it and opens the strip");
                        list.SelectedIndex = -1; window.UpdateLayout(); PumpFixture(60);
                        Require(FindVisualChildren<Button>(firstRow).Any(b => b.Command == vm.RemoveGlossaryEntryCommand), $"{tag} U1: the delete command stays on the row");
                        ((Button)Named("GlossaryCloseButton")).RaiseEvent(new RoutedEventArgs(System.Windows.Controls.Primitives.ButtonBase.ClickEvent)); PumpFixture(100);
                        vm.GlossaryEntries.Clear();

                        // ---------- U9: the Journal header matches the window name ----------
                        var journal = new JournalWindow(window, vm);
                        journal.Show(); journal.UpdateLayout(); PumpFixture(150);
                        var headings = FindVisualChildren<TextBlock>(journal).Select(t => t.Text).ToList();
                        var wanted = language == "vi" ? "Nhật ký — Khắc phục lỗi" : "Journal — Troubleshooting";
                        Require(headings.Contains(wanted) && !headings.Contains("khắc phục lỗi") && !headings.Contains("troubleshooting"), $"{tag} U9: journal header is '{wanted}' ({string.Join(" | ", headings.Take(6))})");
                        journal.Close();

                        // ---------- U8: the release-notes modal: 700 DIP column, <= 85% of the owner, scrolling body, footer kept ----------
                        vm.ReleaseNotesHistory.Clear();
                        for (var i = 0; i < 8; i++) vm.ReleaseNotesHistory.Add(new ReleaseNotesCacheEntry { Version = $"0.1.{20 - i}", ReleaseDate = "2026-11-1" + i, Notes = string.Join("\n", Enumerable.Range(1, 8).Select(n => "- " + n + " " + new string('n', 90))), CachedAtUtc = DateTime.UtcNow });
                        foreach (var (ownerWidth, ownerHeight) in new[] { (1055.0, 720.0), (1583.0, 1000.0) })
                        {
                            window.Width = ownerWidth; window.Height = ownerHeight; window.UpdateLayout(); PumpFixture(120);
                            var notes = new UpdateWindow(window, new FixtureUpdatePresentation(), notesOnly: true); notes.Show(); notes.UpdateLayout(); PumpFixture(250); notes.UpdateLayout();
                            Require(Math.Abs(notes.ActualWidth - 700 * scale) < 1.5 || notes.ActualWidth <= window.ActualWidth - 24, $"{tag} U8: width is the 700 DIP reading column x UI scale ({notes.ActualWidth:0.#} for owner {ownerWidth:0})");
                            Require(notes.ActualHeight <= window.ActualHeight * .85 + .5, $"{tag} U8: height {notes.ActualHeight:0.#} <= 85% of the owner ({window.ActualHeight * .85:0.#})");
                            Require(notes.ActualHeight <= SystemParameters.WorkArea.Height, $"{tag} U8: fits the work area");
                            var scrollers = FindVisualChildren<ScrollViewer>(notes).Where(s => s.ScrollableHeight > 1).ToList();
                            Require(scrollers.Count >= 1, $"{tag} U8: the body scrolls on its own");
                            var closeButton = FindVisualChildren<Button>(notes).First(b => b.IsVisible && (b.Content as string) is "Đóng" or "Close");
                            void FooterInside(string when) { var bottom = closeButton.TranslatePoint(new Point(0, closeButton.ActualHeight), notes).Y; Require(bottom <= notes.ActualHeight - 8, $"{tag} U8: footer visible {when} (button bottom {bottom:0.#} of {notes.ActualHeight:0.#})"); }
                            FooterInside("at the top"); scrollers[0].ScrollToEnd(); notes.UpdateLayout(); PumpFixture(60); FooterInside("at the end of the body");
                            Require(closeButton.TranslatePoint(new Point(0, 0), notes).Y > scrollers[0].TranslatePoint(new Point(0, scrollers[0].ActualHeight), notes).Y - 1, $"{tag} U8: footer sits below the scrolling body");
                            var narrow = FindVisualChildren<TextBlock>(notes).Where(t => string.Concat(t.Inlines.OfType<Run>().Select(r => r.Text)).StartsWith("• ", StringComparison.Ordinal)).Select(t => t.ActualWidth).DefaultIfEmpty(0).Max();
                            Require(narrow > 0 && narrow < 700 * scale - 40, $"{tag} U8: the longest reading line is the narrower column ({narrow:0}; {string.Join(" | ", FindVisualChildren<TextBlock>(notes).Select(t => (t.Text.Length > 12 ? t.Text[..12] : t.Text) + ":" + t.ActualWidth.ToString("0")).Take(14))})");
                            notes.RaiseEvent(new System.Windows.Input.KeyEventArgs(System.Windows.Input.Keyboard.PrimaryDevice, PresentationSource.FromVisual(notes)!, 0, System.Windows.Input.Key.Escape) { RoutedEvent = UIElement.PreviewKeyDownEvent });
                            PumpFixture(100);
                            Require(!notes.IsVisible, $"{tag} U8: Escape closes the modal");
                        }
                        vm.ReleaseNotesHistory.Clear();

                        window.Close();
                        vm.Language = "vi"; vm.Theme = "light"; vm.UiScale = 1;          // the isolated settings return to the defaults (later fixtures read them)
                        vm.Dispose();
                        report.Add("c-rows " + string.Join(";", contrastRows) + $" rendered-worst={renderedWorst:0.00}");
                    }
                    Console.WriteLine("WPF U1-U9/C1-C6 fixture: PASS (" + string.Join(", ", report) + ")");
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
