using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Media.Imaging;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App.Services;

/// <summary>DEV-only visual probe for the Analyze preflight surface.</summary>
internal static class AnalyzeUiProbe
{
    public static async Task<int> RunAsync(MainWindow window, string outDir)
    {
        Directory.CreateDirectory(outDir);
        var results = new List<object>();
        MainViewModel vm = null!;

        await window.Dispatcher.InvokeAsync(() =>
        {
            vm = (MainViewModel)window.DataContext;
            vm.InputPath = @"C:\fixture\Example.exe";
            vm.OutputPath = Path.Combine(outDir, "package");
            vm.NavigateTab(WorkflowTabs.Extract);
        });

        foreach (var (width, height) in new[] { (1440d, 920d), (1040d, 720d) })
        {
            var shot = Path.Combine(outDir, $"analyze_{(int)width}x{(int)height}.png");
            var metrics = await window.Dispatcher.InvokeAsync(() =>
            {
                window.WindowState = WindowState.Normal;
                window.Width = width;
                window.Height = height;
                window.UpdateLayout();
                var panel = window.FindName("AnalyzePanel") as FrameworkElement;
                var button = window.FindName("AnalyzeButton") as FrameworkElement;
                CaptureWindow(window, shot);
                return new
                {
                    width,
                    height,
                    analyze_panel_visible = panel?.IsVisible == true,
                    analyze_panel_width = panel?.ActualWidth ?? 0,
                    analyze_button_visible = button?.IsVisible == true,
                    analyze_button_width = button?.ActualWidth ?? 0,
                    analyze_command_enabled = vm.AnalyzeCommand.CanExecute(null),
                    scrollable_height = window.FindName("PageScrollViewer") is System.Windows.Controls.ScrollViewer sv
                        ? sv.ScrollableHeight
                        : 0,
                    screenshot = shot,
                };
            });
            results.Add(metrics);
        }

        var ok = results.Count == 2 && results.All(item =>
        {
            var type = item.GetType();
            return (bool)type.GetProperty("analyze_panel_visible")!.GetValue(item)!
                && (double)type.GetProperty("analyze_panel_width")!.GetValue(item)! > 0
                && (bool)type.GetProperty("analyze_button_visible")!.GetValue(item)!
                && (double)type.GetProperty("analyze_button_width")!.GetValue(item)! > 0
                && (bool)type.GetProperty("analyze_command_enabled")!.GetValue(item)!;
        });
        await File.WriteAllTextAsync(
            Path.Combine(outDir, "result.json"),
            JsonSerializer.Serialize(new { ok, results, note = "Analyze preflight surface rendered at 1440x920 and 1040x720." }, new JsonSerializerOptions { WriteIndented = true }));
        return ok ? 0 : 1;
    }

    private static void CaptureWindow(Window window, string path)
    {
        var bitmap = new RenderTargetBitmap(
            (int)Math.Max(1, window.ActualWidth),
            (int)Math.Max(1, window.ActualHeight),
            96,
            96,
            System.Windows.Media.PixelFormats.Pbgra32);
        bitmap.Render(window);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(bitmap));
        using var stream = File.Create(path);
        encoder.Save(stream);
    }
}
