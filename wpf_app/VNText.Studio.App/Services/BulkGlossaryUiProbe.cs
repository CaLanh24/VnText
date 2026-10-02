using System.IO;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media.Imaging;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App.Services;

/// <summary>UI probe for bulk CSV replace and per-package glossary controls.</summary>
internal static class BulkGlossaryUiProbe
{
    public static async Task<int> RunAsync(MainWindow window, string outDir, string? csvOverride)
    {
        Directory.CreateDirectory(outDir);
        var logPath = Path.Combine(outDir, "probe.log");
        var resultPath = Path.Combine(outDir, "result.json");
        File.WriteAllText(logPath, "", Encoding.UTF8);
        var csv = string.IsNullOrWhiteSpace(csvOverride)
            ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "VNText_Output", "Unity_Translation_Package", "translation.csv")
            : csvOverride.Trim().Trim('"');
        MainViewModel vm = null!;
        await window.Dispatcher.InvokeAsync(() =>
        {
            vm = (MainViewModel)window.DataContext;
            vm.OutputPath = Path.GetDirectoryName(csv) ?? "";
        });

        var screenshots = new List<object>();
        foreach (var (width, height) in new[] { (1440d, 920d), (1040d, 720d) })
        {
            var shot = Path.Combine(outDir, $"bulk_glossary_{(int)width}x{(int)height}.png");
            var metrics = await window.Dispatcher.InvokeAsync(() =>
            {
                window.WindowState = WindowState.Normal;
                window.Width = width;
                window.Height = height;
                vm.NavigateTab(WorkflowTabs.EditCsv);
                window.UpdateLayout();
                var find = window.FindName("CsvBulkFindTextBox") as TextBox;
                var replace = window.FindName("CsvBulkReplaceTextBox") as TextBox;
                var scope = window.FindName("CsvBulkScopeComboBox") as ComboBox;
                var preview = window.FindName("CsvBulkPreviewButton") as Button;
                var undo = window.FindName("CsvBulkUndoButton") as Button;
                if (find is not null) find.Text = "pheromones";
                if (replace is not null) replace.Text = "mị lực";
                window.UpdateLayout();
                var bulkVisible = find?.IsVisible == true && replace?.IsVisible == true && scope?.IsVisible == true && preview?.IsVisible == true && undo?.IsVisible == true;
                var bulkShot = Path.Combine(outDir, $"bulk_editor_{(int)width}x{(int)height}.png");
                CaptureWindow(window, bulkShot);
                vm.NavigateTab(WorkflowTabs.Translate);
                var openGlossary = window.FindName("GlossaryEditButton") as Button;
                openGlossary?.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
                window.UpdateLayout();
                var term = window.FindName("GlossaryTermTextBox") as TextBox;
                var translation = window.FindName("GlossaryTranslationTextBox") as TextBox;
                var add = window.FindName("GlossaryAddButton") as Button;
                var list = window.FindName("GlossaryListBox") as ListBox;
                var overlay = window.FindName("GlossaryOverlay") as Grid;
                if (term is not null) term.Text = "pheromones";
                if (translation is not null) translation.Text = "mị lực";
                window.UpdateLayout();
                CaptureWindow(window, shot);
                var glossaryVisible = overlay?.Visibility == Visibility.Visible &&
                                      term?.IsVisible == true && translation?.IsVisible == true &&
                                      add?.IsVisible == true && list?.IsVisible == true;
                (window.FindName("GlossaryCloseButton") as Button)?.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
                return new
                {
                    width,
                    height,
                    bulk_controls = find is not null && replace is not null && scope is not null && preview is not null && undo is not null,
                    bulk_visible = bulkVisible,
                    bulk_width = find?.ActualWidth ?? 0,
                    bulk_bound = vm.CsvBulkFind == "pheromones" && vm.CsvBulkReplace == "mị lực",
                    glossary_controls = openGlossary is not null && term is not null && translation is not null && add is not null && list is not null && overlay is not null,
                    glossary_visible = glossaryVisible,
                    glossary_width = term?.ActualWidth ?? 0,
                    bulk_screenshot = bulkShot,
                    screenshot = shot,
                };
            });
            screenshots.Add(metrics);
            File.AppendAllText(logPath, $"{width}x{height} bulk={metrics.bulk_visible} glossary={metrics.glossary_visible}{Environment.NewLine}", Encoding.UTF8);
        }

        var ok = screenshots.Count == 2 && screenshots.All(x =>
        {
            var type = x.GetType();
            return (bool)type.GetProperty("bulk_controls")!.GetValue(x)! &&
                   (bool)type.GetProperty("bulk_visible")!.GetValue(x)! &&
                   (bool)type.GetProperty("bulk_bound")!.GetValue(x)! &&
                   (double)type.GetProperty("bulk_width")!.GetValue(x)! > 0 &&
                   (bool)type.GetProperty("glossary_controls")!.GetValue(x)! &&
                   (bool)type.GetProperty("glossary_visible")!.GetValue(x)! &&
                   (double)type.GetProperty("glossary_width")!.GetValue(x)! > 0;
        });
        await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(new { ok, csv, screenshots, note = "Kiểm tra control và binding thật ở 1440x920/1040x720." }, new JsonSerializerOptions { WriteIndented = true }));
        return ok ? 0 : 1;
    }

    private static void CaptureWindow(Window window, string path)
    {
        var bitmap = new RenderTargetBitmap((int)Math.Max(1, window.ActualWidth), (int)Math.Max(1, window.ActualHeight), 96, 96, System.Windows.Media.PixelFormats.Pbgra32);
        bitmap.Render(window);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(bitmap));
        using var stream = File.Create(path);
        encoder.Save(stream);
    }
}
