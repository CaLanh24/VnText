using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using VNText.Studio.App.Controls;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private static double RelativeLuminance(Color c)
    {
        static double Lin(byte v) { var s = v / 255.0; return s <= 0.03928 ? s / 12.92 : Math.Pow((s + 0.055) / 1.055, 2.4); }
        return 0.2126 * Lin(c.R) + 0.7152 * Lin(c.G) + 0.0722 * Lin(c.B);
    }
    private static double ContrastRatio(Color a, Color b)
    {
        var x = RelativeLuminance(a); var y = RelativeLuminance(b);
        return (Math.Max(x, y) + 0.05) / (Math.Min(x, y) + 0.05);
    }
    private static T? FindAncestor<T>(DependencyObject child) where T : DependencyObject
    {
        for (var node = VisualTreeHelper.GetParent(child); node is not null; node = VisualTreeHelper.GetParent(node))
            if (node is T found) return found;
        return null;
    }

    /// <summary>Real OCR workspace dialog in the four reviewed presentations (Light/Dark x UI 100%/120%, 1043 DIP wide owner at 120%):
    /// the delete button sits inside its cell without a horizontal scroll, and the translation editor is the themed input surface.</summary>
    private static int RunRegionGridFixture()
    {
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            try
            {
                var app = new Application { ShutdownMode = ShutdownMode.OnExplicitShutdown };
                foreach (var dictionary in new[] { "DesignTokens", "IconGeometries", "ControlStyles" })
                    app.Resources.MergedDictionaries.Add(new ResourceDictionary { Source = new Uri($"pack://application:,,,/VNText.Studio.App;component/Themes/{dictionary}.xaml") });
                using var worker = new PythonWorkerHost();
                using var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false);
                var first = new ImageTextRegion { Id = "r1", Box = new[] { 10, 10, 200, 40 }, SourceText = "Hello, adventurer.", Translation = "Xin chào, nhà thám hiểm. Đây là một bản dịch khá dài để ô tự xuống dòng." };
                var second = new ImageTextRegion { Id = "r2", Box = new[] { 10, 60, 200, 40 }, SourceText = "Close", Translation = "Đóng" };
                vm.ImageRegions.Add(first);
                vm.ImageRegions.Add(second);
                var report = new List<string>();
                UiText.Install();
                foreach (var (theme, scale, ownerWidth, language) in new[] { ("light", 1.0, 1200.0, "vi"), ("dark", 1.0, 1200.0, "vi"), ("light", 1.2, 1043.0, "vi"), ("dark", 1.2, 1043.0, "vi"), ("light", 1.2, 1043.0, "en"), ("dark", 1.2, 1043.0, "en") })
                {
                    UiText.SetLanguage(language);
                    UiAppearance.Apply(theme, 100);
                    UiAppearance.Scale = scale;
                    var label = $"{theme} UI{scale * 100:0}% owner {ownerWidth} {language}";
                    var owner = new Window { Title = "Region grid owner", Width = ownerWidth, Height = 720 };
                    owner.Show();
                    var panel = new ImageWorkspacePanel { DataContext = vm };
                    var dialog = new AppDialogWindow(owner, UiText.Translate("Text trong ảnh"), panel, 1040);
                    dialog.AddButton(UiText.Translate("Đóng"), () => { });
                    dialog.Show();
                    dialog.UpdateLayout();
                    PumpFixture(150);
                    var grid = (DataGrid)panel.FindName("RegionGrid");
                    void CheckDeleteButtons(string state)
                    {
                        var scroller = FindVisualChildren<ScrollViewer>(grid).First();
                        Require(scroller.ScrollableWidth < 1, $"{label} {state}: no horizontal scroll in the region grid ({scroller.ScrollableWidth})");
                        var buttons = FindVisualChildren<Button>(grid).Where(b => System.Windows.Automation.AutomationProperties.GetName(b) is "Xóa vùng" or "Delete region").ToList();
                        Require(buttons.Count == 2, $"{label} {state}: both delete buttons are realised ({buttons.Count})");
                        foreach (var button in buttons)
                        {
                            var cell = FindAncestor<DataGridCell>(button) ?? throw new InvalidOperationException("delete button has no cell");
                            var left = button.TranslatePoint(new Point(0, 0), cell).X;
                            var right = button.TranslatePoint(new Point(button.ActualWidth, 0), cell).X;
                            Require(left >= 1 && right <= cell.ActualWidth - 1, $"{label} {state}: the delete button fits its cell (button {Math.Round(left, 1)}..{Math.Round(right, 1)} of {Math.Round(cell.ActualWidth, 1)})");
                            Require(button.ActualWidth >= 40 && button.ActualHeight >= 28, $"{label} {state}: the delete button keeps a usable target ({button.ActualWidth}x{button.ActualHeight})");
                        }
                    }
                    CheckDeleteButtons("idle");
                    vm.SelectedImageRegion = first;
                    dialog.UpdateLayout();
                    PumpFixture(80);
                    CheckDeleteButtons("selected");
                    grid.CurrentCell = new DataGridCellInfo(first, grid.Columns[1]);
                    Require(grid.BeginEdit(), $"{label}: the translation cell enters edit mode");
                    dialog.UpdateLayout();
                    PumpFixture(80);
                    var cellContent = grid.Columns[1].GetCellContent(first);
                    var editor = cellContent as TextBox ?? FindVisualChildren<TextBox>(cellContent).FirstOrDefault() ?? throw new InvalidOperationException($"{label}: no translation editor");
                    SolidColorBrush Brush(string key) => (SolidColorBrush)editor.FindResource(key);
                    Require(editor.Background is SolidColorBrush background && background.Color == Brush("FieldBackgroundBrush").Color, $"{label}: editor background is the themed field surface");
                    Require(editor.Foreground is SolidColorBrush foreground && foreground.Color == Brush("InkBrush").Color, $"{label}: editor text is the themed ink");
                    Require(editor.CaretBrush is SolidColorBrush caret && caret.Color == Brush("InkBrush").Color, $"{label}: the caret follows the theme ink");
                    Require(editor.SelectionBrush is SolidColorBrush selection && selection.Color == Brush("BlueBrush").Color && editor.SelectionOpacity > 0 && editor.SelectionOpacity < 1, $"{label}: the selection is the themed accent at partial opacity");
                    Require(editor.BorderBrush is SolidColorBrush border && border.Color == Brush("LineBrush").Color, $"{label}: editor border is the themed line");
                    Require(theme != "dark" || (((SolidColorBrush)editor.Background).Color != Colors.White && ContrastRatio(((SolidColorBrush)editor.Background).Color, Colors.White) > 1.3), $"{label}: no default white editor in Dark");
                    var ratio = ContrastRatio(((SolidColorBrush)editor.Foreground).Color, ((SolidColorBrush)editor.Background).Color);
                    Require(ratio >= 4.5, $"{label}: editor text contrast {Math.Round(ratio, 1)}:1");
                    var focusedRatio = ContrastRatio(((SolidColorBrush)editor.Foreground).Color, Brush("SurfaceBrush").Color);
                    Require(focusedRatio >= 4.5, $"{label}: editor text stays readable on the focused surface ({Math.Round(focusedRatio, 1)}:1)");
                    Require(editor.AcceptsReturn && editor.TextWrapping == TextWrapping.Wrap, $"{label}: the editor stays multi-line and wrapping");
                    Require(editor.MinHeight >= 48 && double.IsNaN(editor.Height), $"{label}: the editor grows with its text");
                    editor.Text = "Xin chào ✓ — Tiếng Việt có dấu";
                    AssertEqual("Xin chào ✓ — Tiếng Việt có dấu", first.Translation);            // the binding still writes the translation
                    CheckDeleteButtons("editing");
                    grid.CommitEdit(DataGridEditingUnit.Cell, true);
                    grid.CommitEdit(DataGridEditingUnit.Row, true);
                    first.Translation = "Xin chào, nhà thám hiểm. Đây là một bản dịch khá dài để ô tự xuống dòng.";
                    // the dialog footer stays reachable inside the window at every presentation (the English labels are the longer ones)
                    var closeButton = dialog.ButtonPanel.Children.OfType<Button>().Single();
                    Require(closeButton.IsVisible && closeButton.TranslatePoint(new Point(0, closeButton.ActualHeight), dialog).Y <= dialog.ActualHeight, $"{label}: the footer button is inside the dialog");
                    Require(language == "vi" || closeButton.Content as string == "Close", $"{label}: English footer label");
                    dialog.Close();
                    owner.Close();
                    report.Add(label);
                }
                UiText.SetLanguage("vi");
                UiAppearance.Scale = 1;
                UiAppearance.Apply("light", 100);
                var leaks = RunEnglishWorkflowScan(app);
                Console.WriteLine("WPF region grid fixture: PASS (" + string.Join("; ", report) + "; English workflow scan: " + leaks + ")");
                exitCode = 0;
                app.Shutdown();
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); exitCode = 1; }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        return exitCode;
    }

    private static readonly System.Text.RegularExpressions.Regex VietnameseLetters = new("[ăâđêôơưàáạảãầấậẩẫằắặẳẵèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]", System.Text.RegularExpressions.RegexOptions.IgnoreCase);

    private static IEnumerable<string> UiStrings(DependencyObject root)
    {
        foreach (var node in Descendants(root))
        {
            if (node is TextBox) continue;                                              // user-editable text
            if (node is TextBlock block && FindAncestor<DataGridCell>(block) is { } cell && cell.Column.DisplayIndex is 0 or 1) continue;   // OCR text / translation columns are user data
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
                foreach (var column in grid.Columns) if (column.Header is string columnHeader) yield return columnHeader;
        }
    }
    private static IEnumerable<DependencyObject> Descendants(DependencyObject root)
    {
        yield return root;
        for (var i = 0; i < VisualTreeHelper.GetChildrenCount(root); i++)
            foreach (var child in Descendants(VisualTreeHelper.GetChild(root, i))) yield return child;
    }

    /// <summary>English UI from the empty workspace through review load, region selection, editing, background modes, approval, a refused render,
    /// an invalid review and a running task: no Vietnamese app text may remain (OCR text, translations and paths are user data and excluded).</summary>
    private static string RunEnglishWorkflowScan(Application app)
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_english_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var png = Path.Combine(root, "ui_01.png");
            var encoder = new System.Windows.Media.Imaging.PngBitmapEncoder();
            encoder.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(System.Windows.Media.Imaging.BitmapSource.Create(300, 120, 96, 96, PixelFormats.Bgra32, null, Enumerable.Repeat((byte)255, 300 * 120 * 4).ToArray(), 300 * 4)));
            using (var stream = File.Create(png)) encoder.Save(stream);
            var hash = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(File.ReadAllBytes(png))).ToLowerInvariant();
            string Review(string name, string sha)
            {
                var path = Path.Combine(root, name);
                File.WriteAllText(path, System.Text.Json.JsonSerializer.Serialize(new ImageTextDocument
                {
                    SourcePath = png, SourceSha256 = sha, Width = 300, Height = 120, Status = "REVIEW_REQUIRED",
                    Regions = new List<ImageTextRegion> { new() { Id = "r1", Box = new[] { 10, 10, 200, 40 }, SourceText = "Hello", Translation = "Xin chào" } },
                }, MainViewModel.ImageJson), System.Text.Encoding.UTF8);
                return path;
            }
            UiText.SetLanguage("en");
            UiAppearance.Apply("dark", 100);
            UiAppearance.Scale = 1.2;
            using var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false) { OutputPath = root };
            var owner = new Window { Title = "English scan owner", Width = 1043, Height = 720 };
            owner.Show();
            var panel = new ImageWorkspacePanel { DataContext = vm };
            var dialog = new AppDialogWindow(owner, UiText.Translate("Text trong ảnh"), panel, 1040);
            dialog.AddButton(UiText.Translate("Đóng"), () => { });
            dialog.Show();
            dialog.UpdateLayout();
            PumpFixture(150);
            var states = 0;
            void Scan(string state)
            {
                dialog.UpdateLayout();
                PumpFixture(80);
                var offenders = UiStrings(dialog).Concat(new[] { dialog.Title }).Where(s => VietnameseLetters.IsMatch(s)).Distinct().ToList();
                Require(offenders.Count == 0, $"English UI at '{state}' still shows Vietnamese: " + string.Join(" | ", offenders.Select(s => s.Length > 90 ? s[..90] + "…" : s)));
                states++;
            }
            var grid = (DataGrid)panel.FindName("RegionGrid");
            Scan("empty");
            vm.ImagePath = png; Scan("image chosen, not read");
            Require(vm.TryLoadImageReview(Review("good.json", hash), fromSavedReview: true), "the review loads");
            AssertEqual("Review opened. For safety, choose the background mode again and approve the regions before rendering.", UiText.TranslateDynamic(vm.ImageStatus));
            AssertEqual("Review opened. For safety, choose the background mode again and approve the regions before rendering.", ((TextBlock)panel.FindName("StatusLine")).Text);
            Scan("saved review loaded");
            var region = vm.ImageRegions[0];
            vm.SelectedImageRegion = region; Scan("region selected");
            grid.CurrentCell = new DataGridCellInfo(region, grid.Columns[1]); grid.BeginEdit(); Scan("translation editing");
            grid.CommitEdit(DataGridEditingUnit.Cell, true); grid.CommitEdit(DataGridEditingUnit.Row, true);
            ((CheckBox)panel.FindName("FlatModeBox")).IsChecked = true; Scan("flat background chosen");
            ((CheckBox)panel.FindName("ApproveBox")).IsChecked = true; Scan("approved");
            ((CheckBox)panel.FindName("CloneModeBox")).IsChecked = true; Scan("two modes (invalid)");
            ((CheckBox)panel.FindName("CloneModeBox")).IsChecked = false;
            region.Translation = "Trò chơi mới"; vm.RenderImageCommand.Execute(null); Scan("render refused until approved again");
            Require(((TextBlock)panel.FindName("StatusLine")).Text.StartsWith("Approve the text/crop", StringComparison.Ordinal), "the refused render explains itself in English");
            Require(!vm.TryLoadImageReview(Review("bad.json", new string('0', 64)), fromSavedReview: true), "the invalid review is refused");
            Scan("invalid review error");
            vm.TestSetActiveTask("scan-task", "image_extract"); Scan("a running task");
            Require(((TextBlock)panel.FindName("TaskText")).Text.StartsWith("Running:", StringComparison.Ordinal), "the running-task banner is English");
            vm.TestMarkTaskTerminal("scan-task");
            // Vietnamese is exact again after a live switch, and English returns on the way back.
            UiText.SetLanguage("vi"); UiText.Apply(dialog); vm.RaiseImageLanguageText(); dialog.UpdateLayout(); PumpFixture(80);
            AssertEqual("Chọn ảnh, chạy OCR, sửa và duyệt từng vùng rồi dựng ảnh.", ((TextBlock)panel.FindName("LeadText")).Text);
            Require(((TextBlock)panel.FindName("StatusLine")).Text.StartsWith("Không mở được review:", StringComparison.Ordinal), "Vietnamese status is exact after switching back");
            Require(grid.Columns[0].Header as string == "TEXT OCR" && grid.Columns[1].Header as string == "BẢN DỊCH", "Vietnamese grid headers are exact");
            UiText.SetLanguage("en"); UiText.Apply(dialog); vm.RaiseImageLanguageText(); dialog.UpdateLayout(); PumpFixture(80);
            Require(grid.Columns[0].Header as string == "OCR TEXT" && ((TextBlock)panel.FindName("LeadText")).Text.StartsWith("Choose an image", StringComparison.Ordinal), "English returns after the round trip");
            Scan("after the language round trip");
            dialog.Close();
            owner.Close();
            return states + " states, no Vietnamese app text";
        }
        finally
        {
            UiText.SetLanguage("vi");
            UiAppearance.Scale = 1;
            UiAppearance.Apply("light", 100);
            Directory.Delete(root, true);
        }
    }
}
