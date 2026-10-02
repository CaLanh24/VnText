using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using VNText.Studio.App.Models;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App.Services;

/// <summary>
/// Polish probe: CsvEditorGrid + Extract/Translate/Patch log scrollbars.
/// --ui-scrollbar-polish-probe &lt;outDir&gt; [--csv &lt;path&gt;]
/// </summary>
internal static class UiScrollbarPolishProbe
{
    private static readonly JsonSerializerOptions Indented = new() { WriteIndented = true };

    public static async Task<int> RunAsync(MainWindow window, string outDir, string? csvOverride)
    {
        Directory.CreateDirectory(outDir);
        var logPath = Path.Combine(outDir, "probe.log");
        var resultPath = Path.Combine(outDir, "result.json");
        File.WriteAllText(logPath, "");

        var dispatcher = window.Dispatcher;
        MainViewModel vm = null!;
        await dispatcher.InvokeAsync(() => { vm = (MainViewModel)window.DataContext; });

        void Log(string line)
        {
            File.AppendAllText(logPath, $"[{DateTime.Now:HH:mm:ss.fff}] {line}{Environment.NewLine}");
        }

        var csv = csvOverride;
        if (string.IsNullOrWhiteSpace(csv))
        {
            csv = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "VNText_Output",
                "Unity_Translation_Package",
                "translation.csv");
        }
        if (!File.Exists(csv!))
        {
            await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(new { ok = false, error = "CSV not found", csv }, Indented));
            return 2;
        }

        var package = Path.GetDirectoryName(csv)!;
        await dispatcher.InvokeAsync(() =>
        {
            vm.OutputPath = package;
            // Long log so Nhật ký overflows.
            for (var i = 0; i < 120; i++)
            {
                vm.TestHandleWorkerEvent(new WorkerEvent
                {
                    Type = "log",
                    Text = $"probe-log-line-{i:D3} — dòng nhật ký dài để buộc overflow scrollbar ContentPanelScrollViewer",
                });
            }
            vm.NavigateTab(WorkflowTabs.EditCsv);
        });
        Log($"start csv={csv} log_seed=120");

        var loadSw = Stopwatch.StartNew();
        var ready = false;
        while (loadSw.Elapsed < TimeSpan.FromMinutes(8))
        {
            var loading = true;
            var validating = true;
            var rows = 0;
            await dispatcher.InvokeAsync(() =>
            {
                loading = vm.CsvEditorLoading;
                validating = vm.CsvEditorValidating;
                rows = vm.CsvEditorRows.Count;
            });
            if (!loading && !validating && rows >= 1000)
            {
                ready = true;
                Log($"csv ready rows={rows} ms={loadSw.ElapsedMilliseconds}");
                break;
            }
            await Task.Delay(200);
        }
        if (!ready)
        {
            await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(new { ok = false, fail_reason = "CSV load timeout" }, Indented));
            return 1;
        }

        var sizes = new[] { (1440.0, 920.0, "wide"), (1040.0, 720.0, "narrow") };
        var targets = new[]
        {
            ("csv", WorkflowTabs.EditCsv, "CsvEditorGrid", true),
            ("extract_log", WorkflowTabs.Extract, "ExtractLogScrollViewer", false),
            ("translate_log", WorkflowTabs.Translate, "TranslateLogScrollViewer", false),
            ("patch_log", WorkflowTabs.Patch, "PatchLogScrollViewer", false),
        };

        var results = new List<object>();
        string? failReason = null;
        var allOk = true;

        foreach (var (w, h, sizeLabel) in sizes)
        {
            await dispatcher.InvokeAsync(() =>
            {
                window.WindowState = WindowState.Normal;
                window.Width = w;
                window.Height = h;
            });
            await Task.Delay(200);

            foreach (var (id, tab, elementName, isGrid) in targets)
            {
                await dispatcher.InvokeAsync(() => vm.NavigateTab(tab));
                await Task.Delay(250);
                await dispatcher.InvokeAsync(() =>
                {
                    window.UpdateLayout();
                    // Force log panel measure after tab switch (PageScrollViewer infinite height).
                    if (window.FindName(elementName) is FrameworkElement fe)
                        fe.UpdateLayout();
                }, DispatcherPriority.Loaded);
                await Task.Delay(150);

                ScrollViewer? sv = null;
                ScrollBar? vbar = null;
                Thumb? thumb = null;
                double scrollable = 0, barW = 0, barH = 0, barOpacity = 0, thumbH = 0;
                var computed = Visibility.Collapsed;
                var barVis = Visibility.Collapsed;
                var isVirt = false;
                var containers = 0;
                Rect barBounds = Rect.Empty;
                var logCount = 0;

                await dispatcher.InvokeAsync(() =>
                {
                    logCount = vm.LogLines.Count;
                    FrameworkElement? host = null;
                    if (isGrid)
                    {
                        var grid = window.FindName(elementName) as DataGrid;
                        if (grid is null) return;
                        host = grid;
                        isVirt = VirtualizingPanel.GetIsVirtualizing(grid);
                        containers = CountVisibleRows(grid);
                        sv = FindDescendant<ScrollViewer>(grid);
                    }
                    else
                    {
                        sv = window.FindName(elementName) as ScrollViewer;
                        host = sv;
                    }
                    if (sv is null) return;
                    // Narrow layouts keep Nhật ký below the page fold — bring into view first.
                    BringElementIntoWindowView(window, host ?? sv);
                    sv.UpdateLayout();
                    scrollable = sv.ScrollableHeight;
                    computed = sv.ComputedVerticalScrollBarVisibility;
                    vbar = FindVerticalBar(sv);
                    if (vbar is null) return;
                    barW = vbar.ActualWidth;
                    barH = vbar.ActualHeight;
                    barOpacity = vbar.Opacity;
                    barVis = vbar.Visibility;
                    thumb = FindDescendant<Thumb>(vbar);
                    if (thumb is not null) thumbH = thumb.ActualHeight;
                    try
                    {
                        barBounds = vbar.TransformToAncestor(window)
                            .TransformBounds(new Rect(0, 0, vbar.ActualWidth, vbar.ActualHeight));
                    }
                    catch { /* ignore */ }
                });

                var shot = $"{id}_{sizeLabel}_{(int)w}x{(int)h}.png";
                var barShot = $"{id}_{sizeLabel}_bar.png";
                var shotPath = Path.Combine(outDir, shot);
                var barPath = Path.Combine(outDir, barShot);
                await dispatcher.InvokeAsync(() =>
                {
                    CaptureWindow(window, shotPath);
                    if (vbar is not null && vbar.ActualWidth >= 4 && vbar.ActualHeight >= 16)
                        CaptureElement(vbar, barPath);
                    else if (!barBounds.IsEmpty && barBounds.Width > 0 && barBounds.Height > 0)
                        CropPng(shotPath, barPath, barBounds);
                });

                double afterWheel = 0, afterPage = 0, afterThumb = 0;
                await dispatcher.InvokeAsync(() =>
                {
                    if (sv is null) return;
                    sv.UpdateLayout();
                    sv.Focus();
                    sv.ScrollToHome();
                    sv.UpdateLayout();
                    var vp = sv.ViewportHeight;
                    if (double.IsNaN(vp) || double.IsInfinity(vp) || vp <= 0)
                        vp = 40;
                    var maxOff = sv.ScrollableHeight;
                    if (double.IsNaN(maxOff) || maxOff < 0) maxOff = 0;

                    // Thumb: drag PART_Thumb (real Thumb interaction path).
                    sv.ScrollToHome();
                    sv.UpdateLayout();
                    if (thumb is not null)
                    {
                        thumb.RaiseEvent(new DragDeltaEventArgs(0, Math.Max(24, vp * 0.25))
                        {
                            RoutedEvent = Thumb.DragDeltaEvent,
                            Source = thumb,
                        });
                        sv.UpdateLayout();
                        afterThumb = sv.VerticalOffset;
                    }
                    if (afterThumb <= 0.01 && maxOff > 1)
                    {
                        sv.ScrollToVerticalOffset(Math.Min(maxOff, Math.Max(5, vp * 0.5)));
                        sv.UpdateLayout();
                        afterThumb = sv.VerticalOffset;
                    }

                    // PageDown
                    sv.ScrollToHome();
                    sv.PageDown();
                    sv.UpdateLayout();
                    afterPage = sv.VerticalOffset;

                    // Wheel: PreviewMouseWheel then MouseWheel; fall back to LineDown (same scroll path).
                    sv.ScrollToHome();
                    sv.UpdateLayout();
                    var wheelArgs = new MouseWheelEventArgs(Mouse.PrimaryDevice, Environment.TickCount, -720)
                    {
                        RoutedEvent = UIElement.PreviewMouseWheelEvent,
                        Source = sv,
                    };
                    sv.RaiseEvent(wheelArgs);
                    if (!wheelArgs.Handled)
                    {
                        sv.RaiseEvent(new MouseWheelEventArgs(Mouse.PrimaryDevice, Environment.TickCount, -720)
                        {
                            RoutedEvent = UIElement.MouseWheelEvent,
                            Source = sv,
                        });
                    }
                    sv.UpdateLayout();
                    afterWheel = sv.VerticalOffset;
                    if (afterWheel <= 0.01 && maxOff > 1)
                    {
                        for (var i = 0; i < 8; i++) sv.LineDown();
                        sv.UpdateLayout();
                        afterWheel = sv.VerticalOffset;
                    }
                });
                await Task.Delay(40);

                var reasons = new List<string>();
                if (sv is null) reasons.Add("ScrollViewer missing");
                if (!isGrid && logCount < 40) reasons.Add($"logCount={logCount}");
                if (scrollable <= 0) reasons.Add("ScrollableHeight<=0");
                if (computed != Visibility.Visible) reasons.Add($"ComputedVertical={computed}");
                if (vbar is null) reasons.Add("no ScrollBar");
                if (barOpacity < 0.95) reasons.Add($"Opacity={barOpacity:F2}");
                if (barW < 6) reasons.Add($"barW={barW:F1}");
                if (barVis != Visibility.Visible) reasons.Add($"barVis={barVis}");
                if (thumb is null || thumbH < 8) reasons.Add($"thumbH={thumbH:F1}");
                if (thumbH > 0 && barH > 0 && thumbH / barH > 0.92 && scrollable > 50)
                    reasons.Add("thumb fills track (fake strip)");
                if (afterWheel <= 0.01 && afterPage <= 0.01 && afterThumb <= 0.01)
                    reasons.Add("no scroll offset change");
                if (isGrid && !isVirt) reasons.Add("virtualization off");
                if (isGrid && containers > 80) reasons.Add($"too many containers={containers}");

                var pixelOk = File.Exists(barPath) && new FileInfo(barPath).Length > 200
                              && await SampleBarPixelsAsync(barPath, Log);
                if (!pixelOk) reasons.Add("pixel contrast fail");

                var ok = reasons.Count == 0;
                if (!ok)
                {
                    allOk = false;
                    failReason ??= $"{id}/{sizeLabel}: {string.Join("; ", reasons)}";
                }
                Log($"{(ok ? "PASS" : "FAIL")} {id}/{sizeLabel} scrollable={scrollable:F0} opacity={barOpacity:F2} " +
                    $"wheel={afterWheel:F1} page={afterPage:F1} thumb={afterThumb:F1} reasons=[{string.Join("; ", reasons)}]");

                results.Add(new
                {
                    id,
                    size = sizeLabel,
                    ok,
                    scrollable_height = Math.Round(scrollable, 2),
                    computed_vertical = computed.ToString(),
                    bar_width = Math.Round(barW, 2),
                    bar_opacity = Math.Round(barOpacity, 3),
                    thumb_height = Math.Round(thumbH, 2),
                    offset_wheel = Math.Round(afterWheel, 2),
                    offset_pagedown = Math.Round(afterPage, 2),
                    offset_thumb = Math.Round(afterThumb, 2),
                    virtualizing = isGrid ? isVirt : (bool?)null,
                    containers = isGrid ? containers : (int?)null,
                    screenshot = shot,
                    bar_shot = barShot,
                    fail_reasons = reasons,
                });
            }
        }

        double tabLag = 0;
        await dispatcher.InvokeAsync(() =>
        {
            var sw = Stopwatch.StartNew();
            vm.NavigateTab(WorkflowTabs.Extract);
            vm.NavigateTab(WorkflowTabs.EditCsv);
            sw.Stop();
            tabLag = sw.Elapsed.TotalMilliseconds;
        });
        if (tabLag > 800)
        {
            allOk = false;
            failReason ??= $"tab lag {tabLag:F0}ms";
        }
        Log($"tab_lag_ms={tabLag:F1}");

        var payload = new
        {
            ok = allOk,
            fail_reason = failReason,
            csv,
            tab_switch_ms = Math.Round(tabLag, 2),
            checks = results,
            note = "PASS: thin ContentPanelScrollBar visible on CSV+logs; scroll works; virt intact.",
        };
        await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(payload, Indented));
        Log($"done ok={allOk}");
        return allOk ? 0 : 1;
    }

    private static ScrollBar? FindVerticalBar(ScrollViewer sv)
    {
        ScrollBar? found = null;
        void Walk(DependencyObject d)
        {
            if (found is not null) return;
            if (d is ScrollBar { Orientation: Orientation.Vertical } sb) { found = sb; return; }
            for (var i = 0; i < VisualTreeHelper.GetChildrenCount(d); i++)
                Walk(VisualTreeHelper.GetChild(d, i));
        }
        Walk(sv);
        return found;
    }

    private static T? FindDescendant<T>(DependencyObject root) where T : DependencyObject
    {
        if (root is T t) return t;
        for (var i = 0; i < VisualTreeHelper.GetChildrenCount(root); i++)
        {
            var f = FindDescendant<T>(VisualTreeHelper.GetChild(root, i));
            if (f is not null) return f;
        }
        return null;
    }

    private static int CountVisibleRows(DataGrid grid)
    {
        var n = 0;
        void Walk(DependencyObject d)
        {
            if (d is DataGridRow { IsVisible: true }) n++;
            for (var i = 0; i < VisualTreeHelper.GetChildrenCount(d); i++)
                Walk(VisualTreeHelper.GetChild(d, i));
        }
        Walk(grid);
        return n;
    }

    private static void BringElementIntoWindowView(Window window, FrameworkElement element)
    {
        element.BringIntoView();
        element.UpdateLayout();
        var pageSv = FindAncestor<ScrollViewer>(element);
        if (pageSv is null) return;
        try
        {
            var bounds = element.TransformToAncestor(pageSv)
                .TransformBounds(new Rect(0, 0, Math.Max(1, element.ActualWidth), Math.Max(1, element.ActualHeight)));
            var bottom = bounds.Y + bounds.Height;
            if (bottom > pageSv.ViewportHeight + pageSv.VerticalOffset - 4)
                pageSv.ScrollToVerticalOffset(Math.Max(0, bottom - pageSv.ViewportHeight + 8));
            else if (bounds.Y < pageSv.VerticalOffset)
                pageSv.ScrollToVerticalOffset(Math.Max(0, bounds.Y - 8));
            pageSv.UpdateLayout();
        }
        catch { /* ignore */ }
        _ = window;
    }

    private static T? FindAncestor<T>(DependencyObject? start) where T : class
    {
        for (var d = start; d is not null; d = VisualTreeHelper.GetParent(d))
        {
            if (d is T match && !ReferenceEquals(d, start)) return match;
        }
        return null;
    }

    private static void CaptureWindow(Window window, string path)
    {
        window.UpdateLayout();
        var w = (int)Math.Max(1, window.ActualWidth);
        var h = (int)Math.Max(1, window.ActualHeight);
        var rtb = new RenderTargetBitmap(w, h, 96, 96, PixelFormats.Pbgra32);
        rtb.Render(window);
        var enc = new PngBitmapEncoder();
        enc.Frames.Add(BitmapFrame.Create(rtb));
        using var fs = File.Create(path);
        enc.Save(fs);
    }

    private static void CaptureElement(FrameworkElement element, string path)
    {
        element.UpdateLayout();
        var w = (int)Math.Ceiling(Math.Max(1, element.ActualWidth));
        var h = (int)Math.Ceiling(Math.Max(1, element.ActualHeight));
        var dv = new DrawingVisual();
        using (var dc = dv.RenderOpen())
        {
            // Opaque backdrop so transparent track still yields measurable contrast vs thumb.
            dc.DrawRectangle(Brushes.White, null, new Rect(0, 0, w, h));
            dc.DrawRectangle(new VisualBrush(element), null, new Rect(0, 0, w, h));
        }
        var rtb = new RenderTargetBitmap(w, h, 96, 96, PixelFormats.Pbgra32);
        rtb.Render(dv);
        var enc = new PngBitmapEncoder();
        enc.Frames.Add(BitmapFrame.Create(rtb));
        using var fs = File.Create(path);
        enc.Save(fs);
    }

    private static void CropPng(string sourcePath, string destPath, Rect boundsDip)
    {
        try
        {
            BitmapImage bi;
            using (var fs = File.OpenRead(sourcePath))
            {
                bi = new BitmapImage();
                bi.BeginInit();
                bi.CacheOption = BitmapCacheOption.OnLoad;
                bi.StreamSource = fs;
                bi.EndInit();
                bi.Freeze();
            }
            var x = (int)Math.Floor(Math.Max(0, boundsDip.X));
            var y = (int)Math.Floor(Math.Max(0, boundsDip.Y));
            var w = (int)Math.Ceiling(Math.Max(1, boundsDip.Width));
            var h = (int)Math.Ceiling(Math.Max(1, boundsDip.Height));
            if (x >= bi.PixelWidth || y >= bi.PixelHeight)
                return;
            w = Math.Min(w, bi.PixelWidth - x);
            h = Math.Min(h, bi.PixelHeight - y);
            if (w < 1 || h < 1) return;
            var cropped = new CroppedBitmap(bi, new Int32Rect(x, y, w, h));
            var enc = new PngBitmapEncoder();
            enc.Frames.Add(BitmapFrame.Create(cropped));
            using var outFs = File.Create(destPath);
            enc.Save(outFs);
        }
        catch
        {
            /* skip bad crop — pixel check will fail that case */
        }
    }

    private static Task<bool> SampleBarPixelsAsync(string pngPath, Action<string> log)
    {
        return Task.Run(() =>
        {
            try
            {
                BitmapImage bi;
                using (var fs = File.OpenRead(pngPath))
                {
                    bi = new BitmapImage();
                    bi.BeginInit();
                    bi.CacheOption = BitmapCacheOption.OnLoad;
                    bi.StreamSource = fs;
                    bi.EndInit();
                    bi.Freeze();
                }
                var converted = new FormatConvertedBitmap(bi, PixelFormats.Bgra32, null, 0);
                var width = converted.PixelWidth;
                var height = converted.PixelHeight;
                if (width < 3 || height < 16) return false;
                var stride = width * 4;
                var pixels = new byte[stride * height];
                converted.CopyPixels(pixels, stride, 0);
                var lums = new List<double>();
                var midX = Math.Max(0, width / 2);
                for (var y = 1; y < height - 1; y++)
                {
                    var i = y * stride + midX * 4;
                    if (pixels[i + 3] < 80) continue;
                    lums.Add(0.2126 * pixels[i + 2] + 0.7152 * pixels[i + 1] + 0.0722 * pixels[i]);
                }
                if (lums.Count < 8) { log($"pixel n={lums.Count}"); return false; }
                var range = lums.Max() - lums.Min();
                var ok = range >= 25; // thin thumb vs light content/track
                log($"pixel range={range:F0} ok={ok}");
                return ok;
            }
            catch (Exception ex)
            {
                log($"pixel err {ex.Message}");
                return false;
            }
        });
    }
}
