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
                foreach (var (theme, scale, ownerWidth) in new[] { ("light", 1.0, 1200.0), ("dark", 1.0, 1200.0), ("light", 1.2, 1043.0), ("dark", 1.2, 1043.0) })
                {
                    UiAppearance.Apply(theme, 100);
                    UiAppearance.Scale = scale;
                    var label = $"{theme} UI{scale * 100:0}% owner {ownerWidth}";
                    var owner = new Window { Title = "Region grid owner", Width = ownerWidth, Height = 720 };
                    owner.Show();
                    var panel = new ImageWorkspacePanel { DataContext = vm };
                    var dialog = new AppDialogWindow(owner, "Text trong ảnh", panel, 1040);
                    dialog.AddButton("Đóng", () => { });
                    dialog.Show();
                    dialog.UpdateLayout();
                    PumpFixture(150);
                    var grid = (DataGrid)panel.FindName("RegionGrid");
                    void CheckDeleteButtons(string state)
                    {
                        var scroller = FindVisualChildren<ScrollViewer>(grid).First();
                        Require(scroller.ScrollableWidth < 1, $"{label} {state}: no horizontal scroll in the region grid ({scroller.ScrollableWidth})");
                        var buttons = FindVisualChildren<Button>(grid).Where(b => System.Windows.Automation.AutomationProperties.GetName(b) == "Xóa vùng").ToList();
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
                    dialog.Close();
                    owner.Close();
                    report.Add(label);
                }
                UiAppearance.Scale = 1;
                UiAppearance.Apply("light", 100);
                Console.WriteLine("WPF region grid fixture: PASS (" + string.Join("; ", report) + ")");
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
}
