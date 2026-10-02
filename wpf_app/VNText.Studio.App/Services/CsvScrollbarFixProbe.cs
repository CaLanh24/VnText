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
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App.Services;

/// <summary>
/// Assert CsvEditorGrid scrollbar is real (visible, opaque, scrollable) with 27k CSV.
/// --csv-scrollbar-fix-probe &lt;outDir&gt; [--csv &lt;path&gt;]
/// </summary>
internal static class CsvScrollbarFixProbe
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
            var stamped = $"[{DateTime.Now:HH:mm:ss.fff}] {line}";
            File.AppendAllText(logPath, stamped + Environment.NewLine);
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
            vm.NavigateTab(WorkflowTabs.EditCsv);
        });
        Log($"start csv={csv}");

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
                Log($"csv ready rows={rows} elapsed={loadSw.ElapsedMilliseconds}ms");
                break;
            }
            await Task.Delay(200);
        }

        if (!ready)
        {
            await WriteFail(resultPath, "CSV load timeout", null);
            Log("FAIL CSV load timeout");
            return 1;
        }

        // Ensure overflow at both sizes by waiting layout after resize.
        var sizes = new[] { (1440.0, 920.0, "wide"), (1040.0, 720.0, "narrow") };
        var sizeResults = new List<object>();
        string? failReason = null;
        var allOk = true;

        foreach (var (w, h, label) in sizes)
        {
            Log($"resize {label} {w}x{h}");
            await dispatcher.InvokeAsync(() =>
            {
                window.WindowState = WindowState.Normal;
                window.Width = w;
                window.Height = h;
                vm.NavigateTab(WorkflowTabs.EditCsv);
            });
            await Task.Delay(250);
            await dispatcher.InvokeAsync(() => window.UpdateLayout(), DispatcherPriority.Loaded);
            await Task.Delay(150);

            ScrollViewer? sv = null;
            ScrollBar? vbar = null;
            Thumb? thumb = null;
            double scrollable = 0, viewport = 0, extent = 0, offset0 = 0;
            var computed = Visibility.Collapsed;
            double barW = 0, barH = 0, barOpacity = 0;
            double thumbH = 0, thumbW = 0, thumbOpacity = 0;
            var barVis = Visibility.Collapsed;
            var isVirt = false;
            var containerCount = 0;

            await dispatcher.InvokeAsync(() =>
            {
                var grid = window.FindName("CsvEditorGrid") as DataGrid;
                if (grid is null)
                    return;
                isVirt = VirtualizingPanel.GetIsVirtualizing(grid);
                sv = FindDescendant<ScrollViewer>(grid);
                if (sv is null)
                    return;
                scrollable = sv.ScrollableHeight;
                viewport = sv.ViewportHeight;
                extent = sv.ExtentHeight;
                offset0 = sv.VerticalOffset;
                computed = sv.ComputedVerticalScrollBarVisibility;
                vbar = FindVerticalScrollBar(sv);
                if (vbar is not null)
                {
                    barW = vbar.ActualWidth;
                    barH = vbar.ActualHeight;
                    barOpacity = vbar.Opacity;
                    barVis = vbar.Visibility;
                    thumb = FindDescendant<Thumb>(vbar);
                    if (thumb is not null)
                    {
                        thumbH = thumb.ActualHeight;
                        thumbW = thumb.ActualWidth;
                        thumbOpacity = thumb.Opacity;
                    }
                }
                containerCount = CountVisibleRowContainers(grid);
            });

            Log($"tree {label}: scrollable={scrollable:F1} viewport={viewport:F1} extent={extent:F1} " +
                $"computed={computed} barW={barW:F1} barOpacity={barOpacity:F2} thumbH={thumbH:F1} virt={isVirt} containers={containerCount}");

            var shotName = $"csv_scrollbar_{label}_{(int)w}x{(int)h}.png";
            var shotPath = Path.Combine(outDir, shotName);
            var barShotName = $"csv_scrollbar_bar_{label}.png";
            var barShotPath = Path.Combine(outDir, barShotName);
            Rect barBoundsInWindow = Rect.Empty;
            await dispatcher.InvokeAsync(() =>
            {
                CaptureWindow(window, shotPath);
                if (vbar is not null && vbar.ActualWidth > 0 && vbar.ActualHeight > 0)
                {
                    try
                    {
                        barBoundsInWindow = vbar.TransformToAncestor(window)
                            .TransformBounds(new Rect(0, 0, vbar.ActualWidth, vbar.ActualHeight));
                        CropPng(shotPath, barShotPath, barBoundsInWindow);
                    }
                    catch (Exception ex)
                    {
                        Log($"bar crop failed: {ex.Message}");
                    }
                }
            });

            // Interaction tests
            double afterWheel = offset0, afterPage = offset0, afterThumb = offset0;
            await dispatcher.InvokeAsync(() =>
            {
                if (sv is null) return;
                sv.Focus();
                sv.ScrollToVerticalOffset(0);
            });
            await Task.Delay(50);

            await dispatcher.InvokeAsync(() =>
            {
                if (sv is null) return;
                sv.RaiseEvent(new MouseWheelEventArgs(Mouse.PrimaryDevice, Environment.TickCount, -480)
                {
                    RoutedEvent = UIElement.MouseWheelEvent,
                    Source = sv,
                });
                afterWheel = sv.VerticalOffset;
            });
            await Task.Delay(40);

            await dispatcher.InvokeAsync(() =>
            {
                if (sv is null) return;
                sv.ScrollToVerticalOffset(0);
                sv.PageDown();
                afterPage = sv.VerticalOffset;
            });
            await Task.Delay(40);

            await dispatcher.InvokeAsync(() =>
            {
                if (sv is null || vbar is null) return;
                sv.ScrollToVerticalOffset(0);
                var target = Math.Min(vbar.Maximum, Math.Max(1, vbar.Maximum * 0.25));
                vbar.Value = target;
                sv.ScrollToVerticalOffset(target);
                afterThumb = sv.VerticalOffset;
            });
            await Task.Delay(40);

            Log($"scroll {label}: wheel={afterWheel:F1} page={afterPage:F1} thumb={afterThumb:F1} barBounds={barBoundsInWindow}");

            // Anti-fake checks
            var reasons = new List<string>();
            if (scrollable <= 0)
                reasons.Add("ScrollableHeight<=0");
            if (computed != Visibility.Visible)
                reasons.Add($"ComputedVertical={computed}");
            if (vbar is null)
                reasons.Add("no vertical ScrollBar");
            if (barOpacity < 0.95)
                reasons.Add($"bar Opacity={barOpacity:F2} (hover-only/fake)");
            if (barW < 8)
                reasons.Add($"bar ActualWidth={barW:F1}");
            if (barVis != Visibility.Visible)
                reasons.Add($"bar Visibility={barVis}");
            if (thumb is null || thumbH < 8)
                reasons.Add($"thumb missing/small H={thumbH:F1}");
            if (thumbH > 0 && barH > 0 && thumbH / barH > 0.92 && scrollable > 100)
                reasons.Add($"thumb fills track ({thumbH:F0}/{barH:F0}) — fake strip");
            if (afterWheel <= 0.01 && afterPage <= 0.01)
                reasons.Add("wheel+PageDown did not change offset");
            if (afterThumb <= 0.01)
                reasons.Add("thumb/value scroll did not change offset");
            if (!isVirt)
                reasons.Add("virtualization off");
            var rowCount = 0;
            await dispatcher.InvokeAsync(() => rowCount = vm.CsvEditorRows.Count);
            if (containerCount > 0 && rowCount > 500 && containerCount > Math.Max(80, rowCount * 0.05))
                reasons.Add($"too many row containers={containerCount} for rows={rowCount}");

            var pixelOk = false;
            if (File.Exists(barShotPath) && new FileInfo(barShotPath).Length > 200)
                pixelOk = await SampleScrollbarElementPixelsAsync(barShotPath, Log);
            else
                reasons.Add("missing/empty scrollbar crop");
            if (!pixelOk && File.Exists(barShotPath))
                reasons.Add("scrollbar crop pixels lack track/thumb contrast");

            var sizeOk = reasons.Count == 0;
            if (!sizeOk)
            {
                allOk = false;
                failReason ??= string.Join("; ", reasons);
                Log($"FAIL {label}: {string.Join("; ", reasons)}");
            }
            else
            {
                Log($"PASS {label}");
            }

            sizeResults.Add(new
            {
                label,
                width = w,
                height = h,
                ok = sizeOk,
                scrollable_height = Math.Round(scrollable, 2),
                viewport_height = Math.Round(viewport, 2),
                extent_height = Math.Round(extent, 2),
                computed_vertical = computed.ToString(),
                bar_actual_width = Math.Round(barW, 2),
                bar_actual_height = Math.Round(barH, 2),
                bar_opacity = Math.Round(barOpacity, 3),
                bar_visibility = barVis.ToString(),
                thumb_actual_height = Math.Round(thumbH, 2),
                thumb_actual_width = Math.Round(thumbW, 2),
                offset_wheel = Math.Round(afterWheel, 2),
                offset_pagedown = Math.Round(afterPage, 2),
                offset_thumb = Math.Round(afterThumb, 2),
                virtualizing = isVirt,
                visible_row_containers = containerCount,
                row_count = rowCount,
                screenshot = shotName,
                scrollbar_shot = barShotName,
                pixel_contrast_ok = pixelOk,
                fail_reasons = reasons,
            });
        }

        // Quick tab lag check (virtualization / UI still responsive)
        var lagMs = 0.0;
        await dispatcher.InvokeAsync(() =>
        {
            var sw = Stopwatch.StartNew();
            vm.NavigateTab(WorkflowTabs.Extract);
            vm.NavigateTab(WorkflowTabs.EditCsv);
            sw.Stop();
            lagMs = sw.Elapsed.TotalMilliseconds;
        });
        Log($"tab extract↔editcsv setter_ms={lagMs:F1}");
        if (lagMs > 800)
        {
            allOk = false;
            failReason ??= $"tab switch lag {lagMs:F0}ms";
        }

        // Real mouse-wheel on DataGrid (optional extra evidence)
        double wheelOffset = 0;
        await dispatcher.InvokeAsync(() =>
        {
            var grid = window.FindName("CsvEditorGrid") as DataGrid;
            var sv = grid is null ? null : FindDescendant<ScrollViewer>(grid);
            if (sv is null) return;
            sv.ScrollToVerticalOffset(0);
            sv.RaiseEvent(new MouseWheelEventArgs(Mouse.PrimaryDevice, Environment.TickCount, -480)
            {
                RoutedEvent = UIElement.MouseWheelEvent,
                Source = sv,
            });
            wheelOffset = sv.VerticalOffset;
        });
        Log($"mousewheel_delta_offset={wheelOffset:F1}");

        var payload = new
        {
            ok = allOk,
            fail_reason = failReason,
            csv,
            sizes = sizeResults,
            tab_switch_ms = Math.Round(lagMs, 2),
            mousewheel_offset = Math.Round(wheelOffset, 2),
            note = "PASS requires visible opaque scrollbar, real scroll offsets, virtualization intact.",
        };
        await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(payload, Indented));
        Log($"done ok={allOk}");
        return allOk ? 0 : 1;
    }

    private static async Task WriteFail(string path, string reason, object? extra)
    {
        await File.WriteAllTextAsync(path, JsonSerializer.Serialize(new { ok = false, fail_reason = reason, extra }, Indented));
    }

    private static ScrollBar? FindVerticalScrollBar(ScrollViewer sv)
    {
        ScrollBar? found = null;
        void Walk(DependencyObject d)
        {
            if (found is not null) return;
            if (d is ScrollBar { Orientation: Orientation.Vertical } sb)
            {
                found = sb;
                return;
            }
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
            var found = FindDescendant<T>(VisualTreeHelper.GetChild(root, i));
            if (found is not null) return found;
        }
        return null;
    }

    private static int CountVisibleRowContainers(DataGrid grid)
    {
        var count = 0;
        void Walk(DependencyObject d)
        {
            if (d is DataGridRow { IsVisible: true })
                count++;
            for (var i = 0; i < VisualTreeHelper.GetChildrenCount(d); i++)
                Walk(VisualTreeHelper.GetChild(d, i));
        }
        Walk(grid);
        return count;
    }

    private static void CaptureWindow(Window window, string path)
    {
        window.UpdateLayout();
        var w = (int)Math.Max(1, window.ActualWidth);
        var h = (int)Math.Max(1, window.ActualHeight);
        var rtb = new RenderTargetBitmap(w, h, 96, 96, PixelFormats.Pbgra32);
        rtb.Render(window);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(rtb));
        using var fs = File.Create(path);
        encoder.Save(fs);
    }

    private static void CaptureElement(FrameworkElement el, string path)
    {
        el.UpdateLayout();
        var w = (int)Math.Ceiling(Math.Max(1, el.ActualWidth));
        var h = (int)Math.Ceiling(Math.Max(1, el.ActualHeight));
        var rtb = new RenderTargetBitmap(w, h, 96, 96, PixelFormats.Pbgra32);
        rtb.Render(el);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(rtb));
        using var fs = File.Create(path);
        encoder.Save(fs);
    }

    private static void CropPng(string sourcePath, string destPath, Rect boundsDip)
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
        var scaleX = bi.DpiX > 0 ? bi.DpiX / 96.0 : 1.0;
        var scaleY = bi.DpiY > 0 ? bi.DpiY / 96.0 : 1.0;
        // RenderTargetBitmap used 96dpi; ActualWidth of window matches pixel size in CaptureWindow.
        var x = (int)Math.Floor(Math.Max(0, boundsDip.X));
        var y = (int)Math.Floor(Math.Max(0, boundsDip.Y));
        var w = (int)Math.Ceiling(Math.Max(1, boundsDip.Width));
        var h = (int)Math.Ceiling(Math.Max(1, boundsDip.Height));
        if (x + w > bi.PixelWidth) w = Math.Max(1, bi.PixelWidth - x);
        if (y + h > bi.PixelHeight) h = Math.Max(1, bi.PixelHeight - y);
        var cropped = new CroppedBitmap(bi, new Int32Rect(x, y, w, h));
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(cropped));
        using var outFs = File.Create(destPath);
        encoder.Save(outFs);
    }

    /// <summary>
    /// Sample a rendered ScrollBar bitmap for track vs thumb luminance contrast.
    /// </summary>
    private static Task<bool> SampleScrollbarElementPixelsAsync(string pngPath, Action<string> log)
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
                if (width < 4 || height < 20)
                {
                    log($"bar bitmap too small {width}x{height}");
                    return false;
                }
                var stride = width * 4;
                var pixels = new byte[stride * height];
                converted.CopyPixels(pixels, stride, 0);

                var luminances = new List<double>(height);
                var midX = width / 2;
                for (var y = 2; y < height - 2; y++)
                {
                    var i = y * stride + midX * 4;
                    var b = pixels[i];
                    var g = pixels[i + 1];
                    var r = pixels[i + 2];
                    var a = pixels[i + 3];
                    if (a < 180) continue;
                    luminances.Add(0.2126 * r + 0.7152 * g + 0.0722 * b);
                }
                if (luminances.Count < 10)
                {
                    log($"bar pixel sample too few n={luminances.Count}");
                    return false;
                }
                var min = luminances.Min();
                var max = luminances.Max();
                var range = max - min;
                // Track ~#E8ECF1 (~232), thumb ~#5A6573 (~100) → range should be large.
                var ok = range >= 40;
                log($"bar pixel lum min={min:F0} max={max:F0} range={range:F0} ok={ok}");
                return ok;
            }
            catch (Exception ex)
            {
                log($"bar pixel sample error: {ex.Message}");
                return false;
            }
        });
    }
}
