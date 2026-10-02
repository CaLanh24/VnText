using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using VNText.Studio.App.Models;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App.Services;

/// <summary>
/// DEV-only UI probe for the Translate CSV picker and completion modal.
/// --translate-csv-completion-popup-probe &lt;outDir&gt;
/// </summary>
internal static class TranslateCsvCompletionPopupProbe
{
    private const uint BmClick = 0x00F5;

    public static async Task<int> RunAsync(MainWindow window, string outDir)
    {
        Directory.CreateDirectory(outDir);
        var logPath = Path.Combine(outDir, "probe.log");
        var resultPath = Path.Combine(outDir, "result.json");
        File.WriteAllText(logPath, "", Encoding.UTF8);

        void Log(string message)
        {
            File.AppendAllText(logPath, $"[{DateTime.Now:HH:mm:ss.fff}] {message}{Environment.NewLine}", Encoding.UTF8);
        }

        var dispatcher = window.Dispatcher;
        MainViewModel vm = null!;
        await dispatcher.InvokeAsync(() => vm = (MainViewModel)window.DataContext);

        var screenshots = new List<object>();
        foreach (var (width, height) in new[] { (1440d, 920d), (1040d, 720d) })
        {
            var shot = Path.Combine(outDir, $"translate_{(int)width}x{(int)height}.png");
            var metrics = await dispatcher.InvokeAsync(() =>
            {
                window.WindowState = WindowState.Normal;
                window.Width = width;
                window.Height = height;
                vm.NavigateTab(WorkflowTabs.Translate);
                window.UpdateLayout();

                var picker = window.FindName("ChooseTranslateCsvButton") as Button;
                var pathText = window.FindName("TranslateCsvPathText") as TextBlock;
                CaptureWindow(window, shot);
                return new
                {
                    requested_width = width,
                    requested_height = height,
                    actual_width = window.ActualWidth,
                    actual_height = window.ActualHeight,
                    picker_visible = picker?.IsVisible == true,
                    picker_width = picker?.ActualWidth ?? 0,
                    picker_text = (picker?.Content as TextBlock)?.Text,
                    path_display = pathText?.Text,
                    screenshot = shot,
                };
            });
            screenshots.Add(metrics);
            Log($"screenshot {shot} picker_visible={metrics.picker_visible} picker_width={metrics.picker_width:F1}");
        }

        var popupResults = new List<object>();
        var cases = new[]
        {
            (task: "extract", id: "probe-popup-success", title: "VNText Studio — Hoàn tất", kind: "success", evt: new WorkerEvent
            {
                Type = "complete", Id = "probe-popup-success", Ok = true, Complete = true,
            }),
            (task: "translate", id: "probe-popup-partial", title: "VNText Studio — Chưa hoàn tất", kind: "warning", evt: new WorkerEvent
            {
                Type = "complete", Id = "probe-popup-partial", Ok = true, Complete = false, Pending = 2, ReviewOnly = 1, Translated = 7,
            }),
            (task: "patch", id: "probe-popup-error", title: "VNText Studio — Lỗi", kind: "error", evt: new WorkerEvent
            {
                Type = "complete", Id = "probe-popup-error", Ok = false, Error = "Probe error",
            }),
        };

        foreach (var item in cases)
        {
            var clickTask = Task.Run(() => WaitForAndClickMessageBox(item.title, TimeSpan.FromSeconds(8)));
            await dispatcher.InvokeAsync(() => vm.TestSimulateTaskComplete(item.task, item.evt));
            var clicked = await clickTask;

            var duplicateTask = Task.Run(() => WaitForMessageBox(item.title, TimeSpan.FromMilliseconds(900)));
            await dispatcher.InvokeAsync(() => vm.TestHandleWorkerEvent(item.evt));
            var duplicateShown = await duplicateTask;

            popupResults.Add(new
            {
                task = item.task,
                expected_kind = item.kind,
                shown_and_ok_clicked = clicked,
                duplicate_shown = duplicateShown,
            });
            Log($"popup task={item.task} shown_and_ok_clicked={clicked} duplicate_shown={duplicateShown}");
        }

        var screenshotsOk = screenshots.Count == 2 && screenshots.All(x =>
        {
            var type = x.GetType();
            return (bool)type.GetProperty("picker_visible")!.GetValue(x)! &&
                   (double)type.GetProperty("picker_width")!.GetValue(x)! > 0;
        });
        var popupsOk = popupResults.Count == cases.Length && popupResults.All(x =>
        {
            var type = x.GetType();
            return (bool)type.GetProperty("shown_and_ok_clicked")!.GetValue(x)! &&
                   !(bool)type.GetProperty("duplicate_shown")!.GetValue(x)!;
        });
        var payload = new
        {
            ok = screenshotsOk && popupsOk,
            screenshots,
            popup_results = popupResults,
            note = "Ảnh UI thật ở 1440x920 và 1040x720; popup được mở bằng MainWindow owner và tự bấm OK qua Win32 probe.",
        };
        await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
        Log($"probe done ok={payload.ok}");
        return payload.ok ? 0 : 1;
    }

    private static bool WaitForAndClickMessageBox(string title, TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline)
        {
            var handle = FindWindow(null, title);
            if (handle != IntPtr.Zero)
            {
                var button = FindButton(handle);
                if (button != IntPtr.Zero)
                {
                    PostMessage(button, BmClick, IntPtr.Zero, IntPtr.Zero);
                    return true;
                }
            }
            Thread.Sleep(25);
        }
        return false;
    }

    private static bool WaitForMessageBox(string title, TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline)
        {
            if (FindWindow(null, title) != IntPtr.Zero)
                return true;
            Thread.Sleep(25);
        }
        return false;
    }

    private static IntPtr FindButton(IntPtr parent)
    {
        IntPtr found = IntPtr.Zero;
        EnumChildWindows(parent, (handle, _) =>
        {
            var className = new StringBuilder(64);
            GetClassName(handle, className, className.Capacity);
            if (string.Equals(className.ToString(), "Button", StringComparison.OrdinalIgnoreCase))
            {
                found = handle;
                return false;
            }
            return true;
        }, IntPtr.Zero);
        return found;
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

    private delegate bool EnumWindowsProc(IntPtr handle, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr FindWindow(string? className, string? windowName);

    [DllImport("user32.dll")]
    private static extern bool EnumChildWindows(IntPtr parent, EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassName(IntPtr handle, StringBuilder className, int maxCount);

    [DllImport("user32.dll")]
    private static extern bool PostMessage(IntPtr handle, uint message, IntPtr wParam, IntPtr lParam);
}
