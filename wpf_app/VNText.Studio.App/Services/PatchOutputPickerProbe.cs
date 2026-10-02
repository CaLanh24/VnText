using System.IO;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media.Imaging;
using System.Windows.Media;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App.Services;

/// <summary>
/// DEV-only UI probe for the output-folder picker on the Patch page.
/// --patch-output-picker-probe &lt;outDir&gt;
/// </summary>
internal static class PatchOutputPickerProbe
{
    public static async Task<int> RunAsync(MainWindow window, string outDir)
    {
        Directory.CreateDirectory(outDir);
        var logPath = Path.Combine(outDir, "probe.log");
        var resultPath = Path.Combine(outDir, "result.json");
        File.WriteAllText(logPath, "", Encoding.UTF8);

        void Log(string message) => File.AppendAllText(
            logPath,
            $"[{DateTime.Now:HH:mm:ss.fff}] {message}{Environment.NewLine}",
            Encoding.UTF8);

        MainViewModel vm = null!;
        await window.Dispatcher.InvokeAsync(() => vm = (MainViewModel)window.DataContext);

        var screenshots = new List<object>();
        foreach (var (width, height) in new[] { (1440d, 920d), (1040d, 720d) })
        {
            var shot = Path.Combine(outDir, $"patch_{(int)width}x{(int)height}.png");
            var metrics = await window.Dispatcher.InvokeAsync(() =>
            {
                window.WindowState = WindowState.Normal;
                window.Width = width;
                window.Height = height;
                vm.NavigateTab(WorkflowTabs.Patch);
                window.UpdateLayout();

                var picker = window.FindName("ChoosePatchOutputButton") as Button;
                var pathText = window.FindName("PatchOutputPathText") as TextBlock;
                var gamePicker = window.FindName("ChoosePatchGameButton") as Button;
                var gamePathText = window.FindName("PatchGamePathText") as TextBlock;
                var progress = window.FindName("PatchProgressBar") as ProgressBar;
                var green = window.FindResource("GreenBrush") as SolidColorBrush;
                var progressBrush = progress?.Foreground as SolidColorBrush;
                CaptureWindow(window, shot);
                return new
                {
                    requested_width = width,
                    requested_height = height,
                    actual_width = window.ActualWidth,
                    actual_height = window.ActualHeight,
                    picker_visible = picker?.IsVisible == true,
                    picker_width = picker?.ActualWidth ?? 0,
                    picker_text = (picker?.Content as StackPanel)?.Children.OfType<TextBlock>().FirstOrDefault()?.Text,
                    command_bound = picker?.Command is not null,
                    command_can_execute = picker?.Command?.CanExecute(null) == true,
                    output_display = pathText?.Text,
                    game_picker_visible = gamePicker?.IsVisible == true,
                    game_picker_width = gamePicker?.ActualWidth ?? 0,
                    game_command_bound = gamePicker?.Command is not null,
                    game_command_can_execute = gamePicker?.Command?.CanExecute(null) == true,
                    game_display = gamePathText?.Text,
                    progress_foreground = progressBrush?.Color.ToString(),
                    progress_is_green = progressBrush is not null && green is not null && progressBrush.Color == green.Color,
                    screenshot = shot,
                };
            });
            screenshots.Add(metrics);
            Log($"screenshot {shot} picker_visible={metrics.picker_visible} picker_width={metrics.picker_width:F1} command_bound={metrics.command_bound}");
        }

        var ok = screenshots.Count == 2 && screenshots.All(item =>
        {
            var type = item.GetType();
            return (bool)type.GetProperty("picker_visible")!.GetValue(item)!
                && (double)type.GetProperty("picker_width")!.GetValue(item)! > 0
                && (bool)type.GetProperty("command_bound")!.GetValue(item)!
                && (bool)type.GetProperty("command_can_execute")!.GetValue(item)!
                && (bool)type.GetProperty("game_picker_visible")!.GetValue(item)!
                && (double)type.GetProperty("game_picker_width")!.GetValue(item)! > 0
                && (bool)type.GetProperty("game_command_bound")!.GetValue(item)!
                && (bool)type.GetProperty("game_command_can_execute")!.GetValue(item)!
                && (bool)type.GetProperty("progress_is_green")!.GetValue(item)!;
        });

        var payload = new
        {
            ok,
            screenshots,
            note = "Ảnh UI thật của tab Tạo patch ở 1440x920 và 1040x720; kiểm tra nút chọn game, chọn thư mục xuất và progress bar xanh lá.",
        };
        await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
        Log($"probe done ok={ok}");
        return ok ? 0 : 1;
    }

    private static void CaptureWindow(Window window, string path)
    {
        var width = (int)Math.Max(1, window.ActualWidth);
        var height = (int)Math.Max(1, window.ActualHeight);
        var bitmap = new RenderTargetBitmap(width, height, 96, 96, PixelFormats.Pbgra32);
        bitmap.Render(window);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(bitmap));
        using var stream = File.Create(path);
        encoder.Save(stream);
    }
}
