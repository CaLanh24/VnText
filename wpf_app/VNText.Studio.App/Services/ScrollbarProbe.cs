using System.IO;
using System.Text.Json;
using System.Threading;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Media;
using System.Windows.Threading;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App.Services;

/// <summary>
/// DEV-only probe: dump ScrollViewer/ScrollBar metrics when request.json appears in outDir.
/// Activated by --scrollbar-probe &lt;outDir&gt;.
/// </summary>
internal sealed class ScrollbarProbe
{
    private readonly MainWindow _window;
    private readonly string _outDir;
    private readonly FileSystemWatcher _watcher;
    private int _busy;

    public ScrollbarProbe(MainWindow window, string outDir)
    {
        _window = window;
        _outDir = outDir;
        Directory.CreateDirectory(outDir);
        _watcher = new FileSystemWatcher(outDir, "request.json")
        {
            NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.FileName | NotifyFilters.CreationTime,
            EnableRaisingEvents = true,
        };
        _watcher.Changed += OnRequest;
        _watcher.Created += OnRequest;
    }

    private void OnRequest(object sender, FileSystemEventArgs e)
    {
        if (Interlocked.Exchange(ref _busy, 1) == 1)
            return;
        _window.Dispatcher.BeginInvoke(DispatcherPriority.ApplicationIdle, async () =>
        {
            try
            {
                await Task.Delay(80);
                await HandleRequestAsync();
            }
            finally
            {
                Interlocked.Exchange(ref _busy, 0);
            }
        });
    }

    private async Task HandleRequestAsync()
    {
        var requestPath = Path.Combine(_outDir, "request.json");
        if (!File.Exists(requestPath))
            return;

        string raw;
        try
        {
            raw = await File.ReadAllTextAsync(requestPath);
        }
        catch
        {
            return;
        }

        using var doc = JsonDocument.Parse(string.IsNullOrWhiteSpace(raw) ? "{}" : raw);
        var root = doc.RootElement;
        var label = root.TryGetProperty("label", out var l) ? l.GetString() ?? "probe" : "probe";
        var tab = root.TryGetProperty("tab", out var t) ? t.GetString() : null;
        var width = root.TryGetProperty("width", out var w) ? w.GetDouble() : 0;
        var height = root.TryGetProperty("height", out var h) ? h.GetDouble() : 0;

        if (width > 0 && height > 0)
        {
            _window.WindowState = WindowState.Normal;
            _window.Width = width;
            _window.Height = height;
        }

        if (!string.IsNullOrWhiteSpace(tab) && _window.DataContext is MainViewModel vm)
            vm.NavigateTabCommand.Execute(tab);

        await Task.Delay(120);
        _window.UpdateLayout();
        await _window.Dispatcher.InvokeAsync(() => { }, DispatcherPriority.Loaded);
        await Task.Delay(80);
        _window.UpdateLayout();

        double? offsetBefore = null;
        double? offsetAfter = null;
        double? scrollable = null;
        if (_window.FindName("PageScrollViewer") is ScrollViewer pageSv)
        {
            scrollable = pageSv.ScrollableHeight;
            offsetBefore = pageSv.VerticalOffset;
            var scrollCmd = root.TryGetProperty("scroll", out var sc) ? sc.GetString() : null;
            if (string.Equals(scrollCmd, "page_down", StringComparison.OrdinalIgnoreCase))
            {
                pageSv.Focus();
                pageSv.PageDown();
                await Task.Delay(100);
                _window.UpdateLayout();
                offsetAfter = pageSv.VerticalOffset;
            }
            else if (string.Equals(scrollCmd, "line_down", StringComparison.OrdinalIgnoreCase))
            {
                pageSv.Focus();
                pageSv.LineDown();
                pageSv.LineDown();
                pageSv.LineDown();
                await Task.Delay(100);
                _window.UpdateLayout();
                offsetAfter = pageSv.VerticalOffset;
            }
        }

        var payload = Collect(label, tab, width, height, offsetBefore, offsetAfter, scrollable);
        var outPath = Path.Combine(_outDir, $"{label}.json");
        await File.WriteAllTextAsync(outPath, JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
        await File.WriteAllTextAsync(Path.Combine(_outDir, $"{label}.done"), outPath);
        try { File.Delete(requestPath); } catch { /* ignore */ }
    }

    private object Collect(string label, string? tab, double width, double height,
        double? offsetBefore, double? offsetAfter, double? scrollableAtAction)
    {
        var scrollViewers = new List<object>();
        var scrollBars = new List<object>();
        Walk(_window, scrollViewers, scrollBars);

        string[] named =
        [
            "PageScrollViewer", "ExtractPage", "ExtractConfigCard", "ExtractLogCard",
            "TranslatePage", "TranslateConfigCard", "TranslateLogCard",
            "PatchPage", "PatchConfigCard", "PatchCheckCard", "SettingsScrollViewer", "CsvEditorGrid",
        ];
        var elements = new List<object>();
        foreach (var name in named)
        {
            if (_window.FindName(name) is not FrameworkElement fe)
                continue;
            elements.Add(new
            {
                name,
                visibility = fe.Visibility.ToString(),
                isVisible = fe.IsVisible,
                actualWidth = fe.ActualWidth,
                actualHeight = fe.ActualHeight,
                margin = fe.Margin.ToString(),
            });
        }

        return new
        {
            label,
            tab,
            requestedSize = new { width, height },
            actualSize = new { width = _window.ActualWidth, height = _window.ActualHeight },
            fontFamily = _window.FontFamily?.Source,
            fontFamilyBaseUri = _window.FontFamily?.BaseUri?.ToString(),
            scrollAction = new
            {
                scrollableHeight = scrollableAtAction,
                verticalOffsetBefore = offsetBefore,
                verticalOffsetAfter = offsetAfter,
                offsetChanged = offsetBefore is double b && offsetAfter is double a && Math.Abs(a - b) > 0.5,
            },
            capturedAt = DateTimeOffset.Now.ToString("o"),
            elements,
            scrollViewers,
            scrollBars,
        };
    }

    private static void Walk(DependencyObject root, List<object> scrollViewers, List<object> scrollBars)
    {
        var count = VisualTreeHelper.GetChildrenCount(root);
        for (var i = 0; i < count; i++)
        {
            var child = VisualTreeHelper.GetChild(root, i);
            if (child is ScrollViewer sv)
            {
                scrollViewers.Add(new
                {
                    name = (sv.Name is { Length: > 0 } n) ? n : "(unnamed)",
                    visibility = sv.Visibility.ToString(),
                    isVisible = sv.IsVisible,
                    verticalBarVisibility = sv.VerticalScrollBarVisibility.ToString(),
                    computedVertical = sv.ComputedVerticalScrollBarVisibility.ToString(),
                    computedHorizontal = sv.ComputedHorizontalScrollBarVisibility.ToString(),
                    viewportHeight = sv.ViewportHeight,
                    extentHeight = sv.ExtentHeight,
                    scrollableHeight = sv.ScrollableHeight,
                    verticalOffset = sv.VerticalOffset,
                    actualWidth = sv.ActualWidth,
                    actualHeight = sv.ActualHeight,
                    overflowPx = Math.Max(0, sv.ExtentHeight - sv.ViewportHeight),
                });
            }
            else if (child is ScrollBar sb)
            {
                scrollBars.Add(new
                {
                    name = (sb.Name is { Length: > 0 } n) ? n : "(unnamed)",
                    orientation = sb.Orientation.ToString(),
                    visibility = sb.Visibility.ToString(),
                    isVisible = sb.IsVisible,
                    opacity = sb.Opacity,
                    maximum = sb.Maximum,
                    minimum = sb.Minimum,
                    value = sb.Value,
                    viewportSize = sb.ViewportSize,
                    actualWidth = sb.ActualWidth,
                    actualHeight = sb.ActualHeight,
                    trackRatio = sb.Maximum <= 0 ? 1.0 : sb.ViewportSize / (sb.Maximum + sb.ViewportSize),
                });
            }

            Walk(child, scrollViewers, scrollBars);
        }
    }

    public void Dispose()
    {
        _watcher.EnableRaisingEvents = false;
        _watcher.Dispose();
    }
}
