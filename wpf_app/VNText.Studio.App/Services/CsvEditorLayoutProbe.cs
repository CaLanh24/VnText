using System.IO;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Controls.Primitives;
using System.Windows.Threading;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App.Services;

/// <summary>
/// DEV-only probe for CSV editor column resizing and long-text rendering.
/// --csv-editor-layout-probe &lt;outDir&gt; [--csv &lt;path&gt;]
/// </summary>
internal static class CsvEditorLayoutProbe
{
    private static readonly TimeSpan LoadTimeout = TimeSpan.FromMinutes(3);

    public static async Task<int> RunAsync(MainWindow window, string outDir, string? csvOverride)
    {
        Directory.CreateDirectory(outDir);
        var logPath = Path.Combine(outDir, "probe.log");
        var resultPath = Path.Combine(outDir, "result.json");
        File.WriteAllText(logPath, "", Encoding.UTF8);

        void Log(string message) => File.AppendAllText(
            logPath,
            $"[{DateTime.Now:HH:mm:ss.fff}] {message}{Environment.NewLine}",
            Encoding.UTF8);

        var csv = string.IsNullOrWhiteSpace(csvOverride)
            ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "VNText_Output", "Unity_Translation_Package", "translation.csv")
            : csvOverride.Trim().Trim('"');
        if (!File.Exists(csv))
        {
            var missing = new { ok = false, error = "CSV not found", csv };
            await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(missing, Indented));
            return 2;
        }

        MainViewModel vm = null!;
        await window.Dispatcher.InvokeAsync(() => vm = (MainViewModel)window.DataContext);
        var package = Path.GetDirectoryName(csv)!;
        await window.Dispatcher.InvokeAsync(() =>
        {
            vm.OutputPath = package;
            vm.NavigateTab(WorkflowTabs.EditCsv);
        });

        var deadline = DateTime.UtcNow + LoadTimeout;
        var ready = false;
        var validationStarted = false;
        while (DateTime.UtcNow < deadline)
        {
            var snapshot = await window.Dispatcher.InvokeAsync(() => new
            {
                rows = vm.CsvEditorRows.Count,
                loading = vm.CsvEditorLoading,
                validating = vm.CsvEditorValidating,
                viewBound = vm.CsvEditorView is not null,
                visible = vm.CsvEditorVisibleCount,
                validationMessage = vm.CsvEditorValidationMessage,
            });
            if (snapshot.validating)
                validationStarted = true;
            if (validationStarted
                && !snapshot.loading
                && !snapshot.validating
                && snapshot.rows > 0
                && snapshot.viewBound
                && snapshot.visible == snapshot.rows)
            {
                ready = true;
                break;
            }
            await Task.Delay(80);
        }

        if (!ready)
        {
            var timeout = await window.Dispatcher.InvokeAsync(() => new
            {
                ok = false,
                error = "Timeout waiting CSV editor",
                rows = vm.CsvEditorRows.Count,
                loading = vm.CsvEditorLoading,
                validating = vm.CsvEditorValidating,
                viewBound = vm.CsvEditorView is not null,
                visible = vm.CsvEditorVisibleCount,
                validationMessage = vm.CsvEditorValidationMessage,
            });
            await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(timeout, Indented));
            return 1;
        }

        var screenshots = new List<object>();
        var metrics = new List<LayoutMetrics>();
        foreach (var (width, height, expandBulkEditor) in new[] { (1440d, 920d, false), (1200d, 800d, false), (1040d, 720d, true) })
        {
            var stem = $"editcsv_{(int)width}x{(int)height}_{(expandBulkEditor ? "expanded" : "default")}";
            var defaultShot = Path.Combine(outDir, stem + "_layout.png");
            var resizedShot = Path.Combine(outDir, stem + "_resized.png");
            await window.Dispatcher.InvokeAsync(() =>
            {
                window.WindowState = WindowState.Normal;
                window.Width = width;
                window.Height = height;
                vm.NavigateTab(WorkflowTabs.EditCsv);
                var expander = FindVisualChildren<Expander>(window)
                    .FirstOrDefault(item => Equals(item.Header, "Tìm và thay thế bản dịch"));
                if (expander is not null)
                    expander.IsExpanded = expandBulkEditor;
                window.UpdateLayout();
            }, DispatcherPriority.Loaded);
            await Task.Delay(80);
            var item = await window.Dispatcher.InvokeAsync<LayoutMetrics>(() =>
            {
                window.UpdateLayout();
                var bulkExpander = FindVisualChildren<Expander>(window)
                    .FirstOrDefault(item => Equals(item.Header, "Tìm và thay thế bản dịch"));
                var grid = window.FindName("CsvEditorGrid") as DataGrid;
                if (grid is null)
                    return new LayoutMetrics(width, height, 0, 0, 0, 0, 0, 0, expandBulkEditor, false, false, false, false, false, false, 0, 0, false, 0, "", "", "", 0, defaultShot, resizedShot);

                var bulkPanel = window.FindName("CsvBulkReplacePanel") as Border;
                bool BulkControlFits(string name)
                {
                    var control = window.FindName(name) as FrameworkElement;
                    if (bulkPanel is null || control is null || !control.IsVisible || control.ActualWidth <= 0 || control.ActualHeight <= 0)
                        return false;
                    var panelRect = bulkPanel.TransformToAncestor(window).TransformBounds(new Rect(new Point(), bulkPanel.RenderSize));
                    var controlRect = control.TransformToAncestor(window).TransformBounds(new Rect(new Point(), control.RenderSize));
                    return panelRect.Contains(controlRect.TopLeft) && panelRect.Contains(controlRect.BottomRight);
                }
                var bulkControlsVisible = new[]
                {
                    "CsvBulkFindTextBox", "CsvBulkReplaceTextBox", "CsvBulkScopeComboBox",
                    "CsvBulkPreviewButton", "CsvBulkUndoButton",
                }.All(BulkControlFits);

                var sourceColumn = grid.Columns.Count > 1 ? grid.Columns[1] : null;
                var search = window.FindName("CsvEditorSearchBox") as TextBox;
                if (search is not null)
                    search.Text = "";
                vm.CsvEditorSearch = "";
                if (sourceColumn is not null)
                    sourceColumn.Width = new DataGridLength(2, DataGridLengthUnitType.Star);
                var scrollViewer = FindVisualChildren<ScrollViewer>(grid).FirstOrDefault();
                scrollViewer?.ScrollToHorizontalOffset(0);
                scrollViewer?.ScrollToVerticalOffset(0);
                grid.UpdateLayout();

                var actualWidth = window.ActualWidth;
                var actualHeight = window.ActualHeight;
                var dpi = VisualTreeHelper.GetDpi(window);
                var viewportWidth = grid.ActualWidth;
                var sourceHeader = sourceColumn is null
                    ? null
                    : FindVisualChildren<DataGridColumnHeader>(grid).FirstOrDefault(h => ReferenceEquals(h.Column, sourceColumn));
                var gripper = sourceHeader is null
                    ? null
                    : FindVisualChildren<Thumb>(sourceHeader).FirstOrDefault(t => t.Name == "PART_RightHeaderGripper");

                var firstRow = FindVisualChildren<DataGridRow>(grid).FirstOrDefault();
                var sourceCell = sourceColumn is null || firstRow is null
                    ? null
                    : FindVisualChildren<DataGridCell>(firstRow).FirstOrDefault(c => ReferenceEquals(c.Column, sourceColumn));
                var sourceText = sourceCell is null
                    ? null
                    : FindVisualChildren<TextBlock>(sourceCell).FirstOrDefault();

                var before = sourceColumn?.ActualWidth ?? 0;
                var resized = before;
                CaptureWindow(window, defaultShot);
                if (sourceColumn is not null)
                {
                    sourceColumn.Width = new DataGridLength(Math.Max(before + 80, 320), DataGridLengthUnitType.Pixel);
                    grid.UpdateLayout();
                    resized = sourceColumn.ActualWidth;
                }
                CaptureWindow(window, resizedShot);

                var searchText = "Escort";
                if (search is not null)
                {
                    search.Text = searchText;
                    grid.UpdateLayout();
                }
                var searchMatches = vm.CsvEditorVisibleCount;
                var searchValue = search?.Text ?? "";
                var viewModelSearchValue = vm.CsvEditorSearch;
                var searchContentHeight = search is null
                    ? 0
                    : FindVisualChildren<FrameworkElement>(search)
                        .FirstOrDefault(element => element.GetType().Name == "TextBoxView")?.ActualHeight ?? 0;
                var searchBound = search is not null
                    && searchValue == searchText
                    && viewModelSearchValue == searchText
                    && searchMatches > 0
                    && searchMatches < vm.CsvEditorRows.Count
                    && searchContentHeight > 0;

                return new LayoutMetrics(
                    width,
                    height,
                    actualWidth,
                    actualHeight,
                    viewportWidth,
                    grid.ActualHeight,
                    dpi.PixelsPerInchX,
                    dpi.PixelsPerInchY,
                    expandBulkEditor,
                    bulkControlsVisible,
                    grid.IsVisible,
                    grid.CanUserResizeColumns,
                    gripper is not null && gripper.Width >= 8 && gripper.Cursor == System.Windows.Input.Cursors.SizeWE,
                    sourceText?.TextWrapping == TextWrapping.Wrap && sourceText.TextTrimming == TextTrimming.None,
                    sourceText?.ToolTip is not null,
                    before,
                    resized,
                    searchBound,
                    searchMatches,
                    searchValue,
                    viewModelSearchValue,
                    search?.Foreground?.ToString() ?? "",
                    searchContentHeight,
                    defaultShot,
                    resizedShot);
            }, DispatcherPriority.Render);
            metrics.Add(item);
            screenshots.Add(item.DefaultScreenshot);
            screenshots.Add(item.ResizedScreenshot);
            Log($"requested={item.RequestedWidth:F0}x{item.RequestedHeight:F0} actual={item.ActualWindowWidth:F1}x{item.ActualWindowHeight:F1} viewport={item.ContentViewportWidth:F1}x{item.GridHeight:F1} dpi={item.DpiX:F0}x{item.DpiY:F0} expanded={item.ExpanderExpanded} bulk_controls_fit={item.BulkControlsVisible} columns={item.InitialSourceWidth:F1}->{item.ResizedSourceWidth:F1} default={item.DefaultScreenshot} resized={item.ResizedScreenshot}");
        }

        var validationMessage = await window.Dispatcher.InvokeAsync(() => vm.CsvEditorValidationMessage);
        var gateStats = await window.Dispatcher.InvokeAsync(() => vm.CsvEditorGateStats);
        var blankDraftRowStatusesClear = await window.Dispatcher.InvokeAsync(() =>
            vm.CsvEditorRows.Count > 0
            && vm.CsvEditorRows.All(row => row.IssueLabel == "no_translation" && string.IsNullOrEmpty(row.IssueDisplay)));
        var blankDraftMessageOk = validationMessage == "Chưa có bản dịch — chuyển sang Dịch local để dịch CSV."
            && string.IsNullOrEmpty(gateStats) && blankDraftRowStatusesClear;
        var ok = blankDraftMessageOk && metrics.Count == 3 && metrics.All(m =>
            m.ActualWindowWidth > 0 && m.ActualWindowHeight > 0 && m.ContentViewportWidth > 0
            && m.GridVisible && m.GridHeight > 100 && m.CanResize && m.HasResizeGripper && m.SourceWrap && m.SourceTooltip && m.SearchBound
            && (m.ActualWindowWidth <= 1040 || m.ResizedSourceWidth > m.InitialSourceWidth))
            && metrics[^1].ExpanderExpanded && metrics[^1].BulkControlsVisible;
        var payload = new
        {
            ok,
            csv,
            row_count = await window.Dispatcher.InvokeAsync(() => vm.CsvEditorRows.Count),
            metrics,
            screenshots,
            validation_message = validationMessage,
            gate_stats = gateStats,
            blank_draft_row_statuses_clear = blankDraftRowStatusesClear,
            blank_draft_message_ok = blankDraftMessageOk,
            note = "Probe render UI WPF thật; sau mỗi lần resize chờ layout/render, ghi kích thước actual và DPI; PNG layout mặc định tách khỏi PNG sau resize cột.",
        };
        await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(payload, Indented));
        Log($"probe done ok={ok}");
        return ok ? 0 : 1;
    }

    private sealed record LayoutMetrics(
        double RequestedWidth,
        double RequestedHeight,
        double ActualWindowWidth,
        double ActualWindowHeight,
        double ContentViewportWidth,
        double GridHeight,
        double DpiX,
        double DpiY,
        bool ExpanderExpanded,
        bool BulkControlsVisible,
        bool GridVisible,
        bool CanResize,
        bool HasResizeGripper,
        bool SourceWrap,
        bool SourceTooltip,
        double InitialSourceWidth,
        double ResizedSourceWidth,
        bool SearchBound,
        int SearchMatches,
        string SearchText,
        string ViewModelSearchText,
        string SearchForeground,
        double SearchContentHeight,
        string DefaultScreenshot,
        string ResizedScreenshot);

    private static IEnumerable<T> FindVisualChildren<T>(DependencyObject root) where T : DependencyObject
    {
        if (root is null)
            yield break;
        for (var i = 0; i < VisualTreeHelper.GetChildrenCount(root); i++)
        {
            var child = VisualTreeHelper.GetChild(root, i);
            if (child is T match)
                yield return match;
            foreach (var nested in FindVisualChildren<T>(child))
                yield return nested;
        }
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

    private static readonly JsonSerializerOptions Indented = new() { WriteIndented = true };
}
