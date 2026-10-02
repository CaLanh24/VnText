using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App.Services;

/// <summary>
/// Full-load tab probe: wait until CSV load+validate finish, then switch tabs and measure UI lag.
/// --tab-responsive-probe-full &lt;outDir&gt; [--csv &lt;path&gt;]
/// </summary>
internal static class TabResponsiveFullLoadProbe
{
    private const double LagFailMs = 800;
    private static readonly TimeSpan LoadTimeout = TimeSpan.FromMinutes(12);

    public static async Task<int> RunAsync(MainWindow window, string outDir, string? csvOverride)
    {
        Directory.CreateDirectory(outDir);
        var logPath = Path.Combine(outDir, "tab_switch.log");
        var resultPath = Path.Combine(outDir, "result.json");
        var timingPath = Path.Combine(outDir, "csv_timing.json");
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

        // Soft floor: line count is an upper estimate (blank lines / multiline quotes).
        var expectedMinRows = 1000;
        try
        {
            var lines = 0;
            using var sr = new StreamReader(csv!);
            while (sr.ReadLine() is not null)
                lines++;
            expectedMinRows = Math.Max(1000, (int)(lines * 0.90) - 5);
        }
        catch { /* keep default */ }

        var package = Path.GetDirectoryName(csv)!;
        await dispatcher.InvokeAsync(() =>
        {
            vm.OutputPath = package;
            vm.NavigateTab(WorkflowTabs.EditCsv);
        });
        Log($"full-load probe start csv={csv} expected_rows>={expectedMinRows}");

        var maxLagDuringLoad = 0.0;
        var loadSw = Stopwatch.StartNew();
        var ready = false;
        string? failReason = null;
        var lastLogSec = -1;
        var pingTimeouts = 0;

        while (loadSw.Elapsed < LoadTimeout)
        {
            var ping = Stopwatch.StartNew();
            var invoke = dispatcher.InvokeAsync(() => { }, DispatcherPriority.Send).Task;
            // During load, GC/alloc spikes may delay Send briefly — log only, do not FAIL yet.
            // User requirement: wait full load+validate, THEN measure tab switches.
            var done = await Task.WhenAny(invoke, Task.Delay(TimeSpan.FromMilliseconds(5000)));
            if (done != invoke)
            {
                pingTimeouts++;
                Log($"UI ping timeout during load #{pingTimeouts} at {loadSw.Elapsed.TotalSeconds:F1}s (soft — still waiting)");
                // Still try to read state with a short timeout so we can exit when ready.
            }
            else
            {
                await invoke;
                var lag = ping.Elapsed.TotalMilliseconds;
                if (lag > maxLagDuringLoad)
                    maxLagDuringLoad = lag;
            }

            var loading = true;
            var validating = true;
            var rows = 0;
            var csvStatus = "";
            try
            {
                var snap = dispatcher.InvokeAsync(() =>
                {
                    loading = vm.CsvEditorLoading;
                    validating = vm.CsvEditorValidating;
                    rows = vm.CsvEditorRows.Count;
                    csvStatus = vm.CsvEditorStatus;
                }).Task;
                if (await Task.WhenAny(snap, Task.Delay(2000)) == snap)
                    await snap;
            }
            catch { /* ignore */ }

            var sec = (int)loadSw.Elapsed.TotalSeconds;
            if (sec != lastLogSec && sec % 5 == 0)
            {
                lastLogSec = sec;
                Log($"wait load… t={sec}s loading={loading} validating={validating} rows={rows} max_lag={maxLagDuringLoad:F1}ms status={csvStatus}");
            }

            if (!loading && !validating && rows >= expectedMinRows)
            {
                ready = true;
                Log($"load+validate ready rows={rows} elapsed={loadSw.ElapsedMilliseconds}ms max_lag_during_load={maxLagDuringLoad:F1}ms ping_timeouts={pingTimeouts}");
                break;
            }

            // Finished load but too few rows — fail fast with clear reason.
            if (!loading && !validating && rows > 0 && rows < expectedMinRows && loadSw.Elapsed > TimeSpan.FromSeconds(30))
            {
                failReason = $"row_count={rows} expected>={expectedMinRows} after load";
                Log(failReason);
                break;
            }

            if (!loading && !validating && rows == 0 && loadSw.Elapsed > TimeSpan.FromSeconds(60))
            {
                failReason = $"Load finished with 0 rows; status={csvStatus}";
                Log(failReason);
                break;
            }

            await Task.Delay(150);
        }

        IReadOnlyDictionary<string, long> timing = new Dictionary<string, long>();
        try
        {
            var timingOp = dispatcher.InvokeAsync(() => timing = vm.LastCsvTiming).Task;
            if (await Task.WhenAny(timingOp, Task.Delay(5000)) == timingOp)
                await timingOp;
        }
        catch { /* ignore */ }
        await File.WriteAllTextAsync(timingPath, JsonSerializer.Serialize(timing, Indented));

        if (!ready)
        {
            var rows = 0;
            var loading = false;
            var validating = false;
            try
            {
                var snap = dispatcher.InvokeAsync(() =>
                {
                    rows = vm.CsvEditorRows.Count;
                    loading = vm.CsvEditorLoading;
                    validating = vm.CsvEditorValidating;
                }).Task;
                if (await Task.WhenAny(snap, Task.Delay(2000)) == snap)
                    await snap;
            }
            catch { /* ignore */ }
            failReason ??= $"Timeout waiting full load+validate (rows={rows}, loading={loading}, validating={validating})";
            await WriteResultAsync(resultPath, false, failReason, csv!, rows, loading, validating, maxLagDuringLoad, 0, [], timing, null);
            Log($"FAIL {failReason}");
            return 1;
        }

        // Soft gate during load: extreme freeze only (true multi-second hang on successful pings).
        if (maxLagDuringLoad > 8000)
        {
            failReason = $"UI lag during load {maxLagDuringLoad:F0}ms > 8000";
            await WriteResultAsync(resultPath, false, failReason, csv!, 0, false, false, maxLagDuringLoad, 0, [], timing, null);
            Log($"FAIL {failReason}");
            return 1;
        }

        // Real tab navigation after full load.
        var tabs = new[]
        {
            WorkflowTabs.Extract, WorkflowTabs.Translate, WorkflowTabs.Patch,
            WorkflowTabs.EditCsv, WorkflowTabs.Settings,
            WorkflowTabs.Extract, WorkflowTabs.EditCsv, WorkflowTabs.Translate,
            WorkflowTabs.Patch, WorkflowTabs.Settings, WorkflowTabs.EditCsv,
            WorkflowTabs.Translate, WorkflowTabs.Extract, WorkflowTabs.Patch,
            WorkflowTabs.EditCsv, WorkflowTabs.Settings, WorkflowTabs.EditCsv,
        };

        var switches = new List<object>();
        var maxLagSwitch = 0.0;
        var fail = false;

        foreach (var tab in tabs)
        {
            var sw = Stopwatch.StartNew();
            await dispatcher.InvokeAsync(() => vm.NavigateTab(tab));
            var setterMs = sw.Elapsed.TotalMilliseconds;

            var ping = Stopwatch.StartNew();
            var invoke = dispatcher.InvokeAsync(() => { }, DispatcherPriority.Send).Task;
            var finished = await Task.WhenAny(invoke, Task.Delay(TimeSpan.FromMilliseconds(LagFailMs)));
            if (finished != invoke)
            {
                fail = true;
                failReason = $"Not Responding after nav→{tab} (ping timeout)";
                Log(failReason);
                break;
            }
            await invoke;
            var lagMs = ping.Elapsed.TotalMilliseconds;
            if (lagMs > maxLagSwitch)
                maxLagSwitch = lagMs;

            var loading = false;
            var validating = false;
            var rows = 0;
            await dispatcher.InvokeAsync(() =>
            {
                loading = vm.CsvEditorLoading;
                validating = vm.CsvEditorValidating;
                rows = vm.CsvEditorRows.Count;
            });

            Log($"nav->{tab} setter_ms={setterMs:F1} ui_lag_ms={lagMs:F1} rows={rows} loading={loading} validating={validating}");
            switches.Add(new
            {
                tab,
                setter_ms = Math.Round(setterMs, 2),
                ui_lag_ms = Math.Round(lagMs, 2),
                rows,
                csv_loading = loading,
                csv_validating = validating,
            });

            if (setterMs > LagFailMs || lagMs > LagFailMs)
            {
                fail = true;
                failReason = $"Tab {tab} blocked UI (setter={setterMs:F0} lag={lagMs:F0})";
                break;
            }

            await Task.Delay(40);
        }

        var rowCount = 0;
        var stillLoading = false;
        var stillValidating = false;
        var status = "";
        await dispatcher.InvokeAsync(() =>
        {
            rowCount = vm.CsvEditorRows.Count;
            stillLoading = vm.CsvEditorLoading;
            stillValidating = vm.CsvEditorValidating;
            status = vm.CsvEditorStatus;
            timing = vm.LastCsvTiming;
        });

        string? shotPath = null;
        try
        {
            shotPath = Path.Combine(outDir, "window_after_tabs.png");
            await dispatcher.InvokeAsync(() => CaptureWindow(window, shotPath));
            Log($"screenshot {shotPath}");
        }
        catch (Exception ex)
        {
            Log($"screenshot failed: {ex.Message}");
            shotPath = null;
        }

        // PASS: full load+validate done, rows present, tab switches responsive.
        // During-load lag is soft-gated above; do not require every load ping < 800ms.
        var ok = !fail
                 && rowCount > 0
                 && rowCount >= expectedMinRows
                 && !stillLoading
                 && !stillValidating
                 && maxLagSwitch <= LagFailMs;

        if (!ok && failReason is null)
        {
            if (rowCount <= 0 || rowCount < expectedMinRows)
                failReason = $"row_count={rowCount} expected>={expectedMinRows}";
            else if (stillLoading || stillValidating)
                failReason = $"still busy loading={stillLoading} validating={stillValidating}";
            else
                failReason = $"lag switch={maxLagSwitch:F0} (load_lag={maxLagDuringLoad:F0})";
        }

        await WriteResultAsync(
            resultPath, ok, failReason, csv!, rowCount, stillLoading, stillValidating,
            maxLagDuringLoad, maxLagSwitch, switches, timing, shotPath);
        await File.WriteAllTextAsync(timingPath, JsonSerializer.Serialize(timing, Indented));
        Log($"probe done ok={ok} rows={rowCount} status={status} load_lag={maxLagDuringLoad:F1} switch_lag={maxLagSwitch:F1}");
        return ok ? 0 : 1;
    }

    private static readonly JsonSerializerOptions Indented = new() { WriteIndented = true };

    private static async Task WriteResultAsync(
        string path,
        bool ok,
        string? failReason,
        string csv,
        int rowCount,
        bool loading,
        bool validating,
        double maxLagLoad,
        double maxLagSwitch,
        List<object> switches,
        IReadOnlyDictionary<string, long> timing,
        string? screenshot)
    {
        var payload = new
        {
            ok,
            fail_reason = failReason,
            csv,
            row_count = rowCount,
            csv_loading = loading,
            csv_validating = validating,
            max_ui_lag_during_load_ms = Math.Round(maxLagLoad, 2),
            max_ui_lag_after_load_ms = Math.Round(maxLagSwitch, 2),
            threshold_ms = LagFailMs,
            switches,
            csv_timing = timing,
            screenshot,
            note = "PASS requires full load+validate complete, row_count>0, then tab switches under lag threshold.",
        };
        await File.WriteAllTextAsync(path, JsonSerializer.Serialize(payload, Indented));
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
}
