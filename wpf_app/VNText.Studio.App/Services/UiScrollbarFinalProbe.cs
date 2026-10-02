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
/// Final visual+geometry probe for CSV/log scrollbars.
/// --ui-scrollbar-final-probe &lt;outDir&gt; [--csv &lt;path&gt;]
/// Fails on stub/triangle thumbs and shrunken log frames — not only offset/opacity.
/// </summary>
internal static class UiScrollbarFinalProbe
{
    private const double MinThumbHeight = 56;
    private const double MinThumbAspect = 2.5; // height/width — stub fails this
    private const double MinBarHeight = 80;
    private const double MinLogPanelHeight = 160;
    private const double MinLogFillRatio = 0.30; // narrow patch: checklist + footer leave less room

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
        var rowCount = 0;
        while (loadSw.Elapsed < TimeSpan.FromMinutes(8))
        {
            var loading = true;
            var validating = true;
            await dispatcher.InvokeAsync(() =>
            {
                loading = vm.CsvEditorLoading;
                validating = vm.CsvEditorValidating;
                rowCount = vm.CsvEditorRows.Count;
            });
            if (!loading && !validating && rowCount >= 1000)
            {
                ready = true;
                Log($"csv ready rows={rowCount} ms={loadSw.ElapsedMilliseconds}");
                break;
            }
            await Task.Delay(200);
        }
        if (!ready)
        {
            await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(new { ok = false, fail_reason = "CSV load timeout" }, Indented));
            return 1;
        }
        if (rowCount < 20000)
            Log($"WARN expected ~27075 rows, got {rowCount}");

        var sizes = new[] { (1440.0, 920.0, "wide"), (1040.0, 720.0, "narrow") };
        var targets = new[]
        {
            ("csv", WorkflowTabs.EditCsv, "CsvEditorGrid", true, (string?)null, (string?)null),
            ("extract_log", WorkflowTabs.Extract, "ExtractLogScrollViewer", false, "ExtractLogCard", "ExtractConfigCard"),
            ("translate_log", WorkflowTabs.Translate, "TranslateLogScrollViewer", false, "TranslateLogCard", "TranslateConfigCard"),
            ("patch_log", WorkflowTabs.Patch, "PatchLogScrollViewer", false, "PatchCheckCard", "PatchConfigCard"),
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
            await Task.Delay(250);

            foreach (var (id, tab, elementName, isGrid, cardName, peerName) in targets)
            {
                await dispatcher.InvokeAsync(() => vm.NavigateTab(tab));
                await Task.Delay(300);
                await dispatcher.InvokeAsync(() =>
                {
                    window.UpdateLayout();
                    if (window.FindName(elementName) is FrameworkElement fe)
                        fe.UpdateLayout();
                }, DispatcherPriority.Loaded);
                await Task.Delay(200);

                ScrollViewer? sv = null;
                ScrollBar? vbar = null;
                Thumb? thumb = null;
                FrameworkElement? logPanel = null;
                double scrollable = 0, barW = 0, barH = 0, barOpacity = 0;
                double thumbW = 0, thumbH = 0, viewportSize = 0;
                double logH = 0, cardH = 0, peerH = 0;
                var computed = Visibility.Collapsed;
                var barVis = Visibility.Collapsed;
                var isVirt = false;
                var containers = 0;
                var logCount = 0;

                Rect barBounds = Rect.Empty;
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
                        // LogPanelBorderStyle wraps Grid → ScrollViewer
                        if (sv?.Parent is FrameworkElement { Parent: Border panel })
                            logPanel = panel;
                        else if (sv?.Parent is Border direct)
                            logPanel = direct;
                        if (cardName is not null && window.FindName(cardName) is FrameworkElement card)
                            cardH = card.ActualHeight;
                        if (peerName is not null && window.FindName(peerName) is FrameworkElement peer)
                            peerH = peer.ActualHeight;
                        if (logPanel is not null)
                            logH = logPanel.ActualHeight;
                    }
                    if (sv is null) return;
                    BringElementIntoWindowView(window, host ?? sv);
                    sv.UpdateLayout();
                    scrollable = sv.ScrollableHeight;
                    computed = sv.ComputedVerticalScrollBarVisibility;
                    vbar = FindVerticalBar(sv);
                    if (vbar is null) return;
                    BringElementIntoWindowView(window, vbar);
                    vbar.UpdateLayout();
                    barW = vbar.ActualWidth;
                    barH = vbar.ActualHeight;
                    barOpacity = vbar.Opacity;
                    barVis = vbar.Visibility;
                    viewportSize = vbar.ViewportSize;
                    thumb = FindDescendant<Thumb>(vbar);
                    if (thumb is not null)
                    {
                        thumbW = thumb.ActualWidth;
                        thumbH = thumb.ActualHeight;
                    }
                    try
                    {
                        barBounds = vbar.TransformToAncestor(window)
                            .TransformBounds(new Rect(0, 0, Math.Max(1, vbar.ActualWidth), Math.Max(1, vbar.ActualHeight)));
                        if (barBounds.Y < 0 || barBounds.Bottom > window.ActualHeight - 4)
                        {
                            BringElementIntoWindowView(window, vbar);
                            vbar.UpdateLayout();
                            barBounds = vbar.TransformToAncestor(window)
                                .TransformBounds(new Rect(0, 0, Math.Max(1, vbar.ActualWidth), Math.Max(1, vbar.ActualHeight)));
                        }
                    }
                    catch { /* ignore */ }
                });

                var shot = $"{id}_{sizeLabel}_{(int)w}x{(int)h}.png";
                var barShot = $"{id}_{sizeLabel}_bar.png";
                var thumbShot = $"{id}_{sizeLabel}_thumb.png";
                var shotPath = Path.Combine(outDir, shot);
                var barPath = Path.Combine(outDir, barShot);
                var thumbPath = Path.Combine(outDir, thumbShot);
                await dispatcher.InvokeAsync(() =>
                {
                    CaptureWindow(window, shotPath);
                    // Prefer crop from window bitmap — ScrollBar RenderTarget often blank.
                    if (!barBounds.IsEmpty && barBounds.Width >= 4 && barBounds.Height >= 16)
                        CropPng(shotPath, barPath, ExpandRect(barBounds, 1, 2));
                    else if (vbar is not null && vbar.ActualWidth >= 4 && vbar.ActualHeight >= 16)
                        CaptureElement(vbar, barPath);
                    if (thumb is not null)
                    {
                        try
                        {
                            var tb = thumb.TransformToAncestor(window)
                                .TransformBounds(new Rect(0, 0, Math.Max(1, thumb.ActualWidth), Math.Max(1, thumb.ActualHeight)));
                            if (tb.Width >= 2 && tb.Height >= 8)
                                CropPng(shotPath, thumbPath, ExpandRect(tb, 2, 2));
                        }
                        catch { /* ignore */ }
                    }
                });

                double afterWheel = 0, afterPage = 0, afterThumb = 0;
                await dispatcher.InvokeAsync(() =>
                {
                    if (sv is null) return;
                    sv.UpdateLayout();
                    sv.Focus();
                    var vp = sv.ViewportHeight;
                    if (double.IsNaN(vp) || double.IsInfinity(vp) || vp <= 0) vp = 40;
                    var maxOff = sv.ScrollableHeight;
                    if (double.IsNaN(maxOff) || maxOff < 0) maxOff = 0;

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

                    sv.ScrollToHome();
                    sv.PageDown();
                    sv.UpdateLayout();
                    afterPage = sv.VerticalOffset;

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
                if (barW < 8 || barW > 16) reasons.Add($"barW={barW:F1} (want ~10)");
                if (barH < MinBarHeight) reasons.Add($"barH={barH:F0}<{MinBarHeight} (clipped/stub track)");
                if (barVis != Visibility.Visible) reasons.Add($"barVis={barVis}");
                if (double.IsNaN(viewportSize) || viewportSize <= 0)
                    reasons.Add($"ViewportSize={viewportSize}");

                // Visual geometry: reject triangle/stub thumbs (short + squat).
                if (thumb is null) reasons.Add("no Thumb");
                else
                {
                    if (thumbH < MinThumbHeight)
                        reasons.Add($"thumbH={thumbH:F1}<{MinThumbHeight} (stub/triangle)");
                    if (thumbW < 4 || thumbW > 14)
                        reasons.Add($"thumbW={thumbW:F1}");
                    var aspect = thumbW > 0.1 ? thumbH / thumbW : 0;
                    if (aspect < MinThumbAspect)
                        reasons.Add($"thumbAspect={aspect:F2}<{MinThumbAspect} (stub shape)");
                    if (barH > 0 && thumbH / barH > 0.95 && scrollable > 50)
                        reasons.Add("thumb fills entire track");
                    if (barH > 0 && thumbH + 4 >= barH && scrollable > 20)
                        reasons.Add("thumb clipped to bar height");
                }

                if (!isGrid)
                {
                    if (logH < MinLogPanelHeight)
                        reasons.Add($"logH={logH:F0}<{MinLogPanelHeight} (shrunken)");
                    if (peerH > 100 && cardH > 0 && Math.Abs(cardH - peerH) > 40)
                        reasons.Add($"cardH={cardH:F0} vs peerH={peerH:F0} (not stretched)");
                    if (cardH > 120 && logH / cardH < MinLogFillRatio)
                        reasons.Add($"logFill={logH / cardH:F2}<{MinLogFillRatio} (white gap)");
                }

                if (afterWheel <= 0.01 && afterPage <= 0.01 && afterThumb <= 0.01)
                    reasons.Add("no scroll offset change");
                if (isGrid && !isVirt) reasons.Add("virtualization off");
                if (isGrid && containers > 80) reasons.Add($"too many containers={containers}");

                var pixel = await AnalyzeBarImageAsync(barPath, barH, thumbH, Log);
                if (!pixel.Ok && File.Exists(thumbPath))
                {
                    var thumbPixel = await AnalyzeBarImageAsync(thumbPath, thumbH, thumbH, Log);
                    if (thumbPixel.Ok)
                        pixel = thumbPixel with { Reason = "ok-via-thumb-crop" };
                }
                if (!pixel.Ok) reasons.Add($"pixel:{pixel.Reason}");

                var ok = reasons.Count == 0;
                if (!ok)
                {
                    allOk = false;
                    failReason ??= $"{id}/{sizeLabel}: {string.Join("; ", reasons)}";
                }
                Log($"{(ok ? "PASS" : "FAIL")} {id}/{sizeLabel} bar={barW:F0}x{barH:F0} thumb={thumbW:F0}x{thumbH:F0} " +
                    $"logH={logH:F0} cardH={cardH:F0} vpSize={viewportSize:F1} " +
                    $"wheel={afterWheel:F1} page={afterPage:F1} thumbOff={afterThumb:F1} reasons=[{string.Join("; ", reasons)}]");

                results.Add(new
                {
                    id,
                    size = sizeLabel,
                    ok,
                    scrollable_height = Math.Round(scrollable, 2),
                    viewport_size = Math.Round(viewportSize, 2),
                    bar_width = Math.Round(barW, 2),
                    bar_height = Math.Round(barH, 2),
                    bar_opacity = Math.Round(barOpacity, 3),
                    thumb_width = Math.Round(thumbW, 2),
                    thumb_height = Math.Round(thumbH, 2),
                    thumb_aspect = thumbW > 0 ? Math.Round(thumbH / thumbW, 2) : 0,
                    log_panel_height = Math.Round(logH, 2),
                    card_height = Math.Round(cardH, 2),
                    peer_height = Math.Round(peerH, 2),
                    offset_wheel = Math.Round(afterWheel, 2),
                    offset_pagedown = Math.Round(afterPage, 2),
                    offset_thumb = Math.Round(afterThumb, 2),
                    pixel,
                    virtualizing = isGrid ? isVirt : (bool?)null,
                    containers = isGrid ? containers : (int?)null,
                    screenshot = shot,
                    bar_shot = barShot,
                    thumb_shot = File.Exists(thumbPath) ? thumbShot : null,
                    fail_reasons = reasons,
                });
            }
        }

        var payload = new
        {
            ok = allOk,
            fail_reason = failReason,
            csv,
            row_count = rowCount,
            checks = results,
            note = allOk
                ? "PASS: continuous rounded thumb; log frames stretched; scroll works."
                : "FAIL: visual geometry or render checks failed.",
        };
        await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(payload, Indented));
        Log($"done ok={allOk} fail={failReason}");
        return allOk ? 0 : 1;
    }

    private sealed record PixelAnalysis(bool Ok, string Reason, double Range, int DarkRuns, int DarkSpan);

    private static Task<PixelAnalysis> AnalyzeBarImageAsync(string pngPath, double layoutBarH, double layoutThumbH, Action<string> log)
    {
        return Task.Run(() =>
        {
            try
            {
                if (!File.Exists(pngPath) || new FileInfo(pngPath).Length < 200)
                    return new PixelAnalysis(false, "bar image missing/small", 0, 0, 0);

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
                if (width < 3 || height < 24)
                    return new PixelAnalysis(false, $"bar png too small {width}x{height}", 0, 0, 0);

                var stride = width * 4;
                var pixels = new byte[stride * height];
                converted.CopyPixels(pixels, stride, 0);
                var midX = Math.Max(0, width / 2);
                var lums = new double[height];
                for (var y = 0; y < height; y++)
                {
                    var i = y * stride + midX * 4;
                    if (pixels[i + 3] < 40)
                        lums[y] = 255;
                    else
                        lums[y] = 0.2126 * pixels[i + 2] + 0.7152 * pixels[i + 1] + 0.0722 * pixels[i];
                }

                var range = lums.Max() - lums.Min();
                var median = lums.OrderBy(x => x).ElementAt(height / 2);
                var darkThreshold = median - 18;
                var maxRun = 0;
                var run = 0;
                var firstDark = -1;
                var lastDark = -1;
                for (var y = 0; y < height; y++)
                {
                    if (lums[y] <= darkThreshold)
                    {
                        if (run == 0) firstDark = firstDark < 0 ? y : firstDark;
                        run++;
                        lastDark = y;
                        if (run > maxRun) maxRun = run;
                    }
                    else run = 0;
                }

                var span = lastDark >= firstDark && firstDark >= 0 ? lastDark - firstDark + 1 : 0;
                log($"pixel range={range:F0} maxRun={maxRun} span={span} h={height} layoutThumb={layoutThumbH:F0}");

                if (range < 20)
                    return new PixelAnalysis(false, $"contrast range={range:F0}", range, maxRun, span);

                // Full crop: require near-min thumb. Truncated crop (narrow window): require
                // visible dark run + trust layout thumb height when Track already sized it.
                var cropTruncated = layoutBarH > 80 && height < layoutBarH * 0.55;
                var requiredRun = cropTruncated
                    ? Math.Min(MinThumbHeight * 0.5, height * 0.28)
                    : MinThumbHeight * 0.85;
                if (maxRun < requiredRun)
                {
                    if (cropTruncated && layoutThumbH >= MinThumbHeight && maxRun >= 20 && range >= 25)
                        return new PixelAnalysis(true, "ok-clipped-crop+layout", range, maxRun, span);
                    return new PixelAnalysis(false, $"darkRun={maxRun} stub/triangle", range, maxRun, span);
                }

                return new PixelAnalysis(true, "ok", range, maxRun, span);
            }
            catch (Exception ex)
            {
                log($"pixel err {ex.Message}");
                return new PixelAnalysis(false, ex.Message, 0, 0, 0);
            }
        });
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

    private static Rect ExpandRect(Rect r, double dx, double dy)
        => new(r.X - dx, r.Y - dy, r.Width + dx * 2, r.Height + dy * 2);

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
            dc.DrawRectangle(Brushes.White, null, new Rect(0, 0, w, h));
        var bg = new RenderTargetBitmap(w, h, 96, 96, PixelFormats.Pbgra32);
        bg.Render(dv);
        var fg = new RenderTargetBitmap(w, h, 96, 96, PixelFormats.Pbgra32);
        fg.Render(element);
        var group = new DrawingVisual();
        using (var dc = group.RenderOpen())
        {
            dc.DrawImage(bg, new Rect(0, 0, w, h));
            dc.DrawImage(fg, new Rect(0, 0, w, h));
        }
        var rtb = new RenderTargetBitmap(w, h, 96, 96, PixelFormats.Pbgra32);
        rtb.Render(group);
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
            /* pixel check will fail */
        }
    }
}
