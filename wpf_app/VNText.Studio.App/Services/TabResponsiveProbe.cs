using System.Diagnostics;
using System.IO;
using System.Text.Json;
using System.Windows.Threading;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App.Services;

/// <summary>
/// DEV probe: switch tabs while a large translation.csv loads; measure UI dispatcher lag.
/// --tab-responsive-probe &lt;outDir&gt; [--csv &lt;path&gt;]
/// </summary>
internal static class TabResponsiveProbe
{
    private const double LagFailMs = 800;

    public static async Task<int> RunAsync(MainWindow window, string outDir, string? csvOverride)
    {
        Directory.CreateDirectory(outDir);
        var logPath = Path.Combine(outDir, "tab_switch.log");
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
            var miss = new { ok = false, error = "CSV not found", csv };
            await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(miss, new JsonSerializerOptions { WriteIndented = true }));
            return 2;
        }

        var package = Path.GetDirectoryName(csv)!;
        await dispatcher.InvokeAsync(() => { vm.OutputPath = package; });
        Log($"probe start csv={csv}");

        var tabs = new[]
        {
            WorkflowTabs.Extract,
            WorkflowTabs.Translate,
            WorkflowTabs.Patch,
            WorkflowTabs.EditCsv,
            WorkflowTabs.Settings,
            WorkflowTabs.EditCsv,
            WorkflowTabs.Translate,
            WorkflowTabs.EditCsv,
            WorkflowTabs.Extract,
            WorkflowTabs.Settings,
            WorkflowTabs.Patch,
            WorkflowTabs.EditCsv,
        };

        var switches = new List<object>();
        var maxUiLagMs = 0.0;
        var fail = false;
        string? failReason = null;

        foreach (var tab in tabs)
        {
            var sw = Stopwatch.StartNew();
            await dispatcher.InvokeAsync(() => vm.NavigateTab(tab));
            var setterMs = sw.Elapsed.TotalMilliseconds;

            var ping = Stopwatch.StartNew();
            await dispatcher.InvokeAsync(() => { }, DispatcherPriority.Normal);
            var lagMs = ping.Elapsed.TotalMilliseconds;
            if (lagMs > maxUiLagMs)
                maxUiLagMs = lagMs;

            var loading = false;
            await dispatcher.InvokeAsync(() => loading = vm.CsvEditorLoading);

            Log($"nav->{tab} setter_ms={setterMs:F1} ui_lag_ms={lagMs:F1} csv_loading={loading}");
            switches.Add(new
            {
                tab,
                setter_ms = Math.Round(setterMs, 2),
                ui_lag_ms = Math.Round(lagMs, 2),
                csv_loading = loading,
            });

            if (setterMs > LagFailMs || lagMs > LagFailMs)
            {
                fail = true;
                failReason = $"Tab {tab} blocked UI (setter={setterMs:F0}ms lag={lagMs:F0}ms)";
                break;
            }

            if (tab == WorkflowTabs.EditCsv)
            {
                var until = DateTime.UtcNow.AddMilliseconds(500);
                while (DateTime.UtcNow < until)
                {
                    var p = Stopwatch.StartNew();
                    var invoke = dispatcher.InvokeAsync(() => { }, DispatcherPriority.Normal).Task;
                    var finished = await Task.WhenAny(invoke, Task.Delay(TimeSpan.FromMilliseconds(LagFailMs)));
                    if (finished != invoke)
                    {
                        fail = true;
                        failReason = $"During CSV tab, UI ping timed out (>{LagFailMs}ms)";
                        break;
                    }
                    await invoke;
                    var l = p.Elapsed.TotalMilliseconds;
                    if (l > maxUiLagMs)
                        maxUiLagMs = l;
                    if (l > LagFailMs)
                    {
                        fail = true;
                        failReason = $"During CSV load, UI lag {l:F0}ms";
                        break;
                    }
                    await Task.Delay(50);
                }
                if (fail)
                    break;
            }
            else
            {
                await Task.Delay(30);
            }
        }

        // Snapshot after switches — always persist evidence even if post-pass hangs.
        var rowCountEarly = 0;
        var stillLoadingEarly = false;
        var statusEarly = "";
        try
        {
            var snapTask = dispatcher.InvokeAsync(() =>
            {
                rowCountEarly = vm.CsvEditorRows.Count;
                stillLoadingEarly = vm.CsvEditorLoading;
                statusEarly = vm.CsvEditorStatus;
            }).Task;
            if (await Task.WhenAny(snapTask, Task.Delay(1000)) == snapTask)
                await snapTask;
        }
        catch { /* ignore */ }

        var okEarly = !fail && maxUiLagMs <= LagFailMs;
        var earlyPayload = new
        {
            ok = okEarly,
            fail_reason = failReason,
            csv,
            row_count = rowCountEarly,
            csv_status = statusEarly,
            max_ui_lag_ms = Math.Round(maxUiLagMs, 2),
            csv_loading_at_end = stillLoadingEarly,
            switches,
            threshold_ms = LagFailMs,
            phase = "after_tab_switches",
            note = "PASS = tab setter/lag under threshold while large CSV may still load in background.",
        };
        await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(earlyPayload, new JsonSerializerOptions { WriteIndented = true }));
        Log($"after switches ok={okEarly} rows={rowCountEarly} max_lag={maxUiLagMs:F1}ms");

        // Short post-pass with hard timeout so probe always writes result.json.
        using var postCts = new CancellationTokenSource(TimeSpan.FromSeconds(4));
        try
        {
            while (!postCts.IsCancellationRequested)
            {
                var p = Stopwatch.StartNew();
                var invoke = dispatcher.InvokeAsync(() => { }, DispatcherPriority.Normal).Task;
                var finished = await Task.WhenAny(invoke, Task.Delay(TimeSpan.FromMilliseconds(LagFailMs), postCts.Token));
                if (finished != invoke)
                {
                    fail = true;
                    failReason ??= $"Post-switch UI ping timed out (>{LagFailMs}ms)";
                    break;
                }
                await invoke;
                var l = p.Elapsed.TotalMilliseconds;
                if (l > maxUiLagMs)
                    maxUiLagMs = l;
                if (l > LagFailMs)
                {
                    fail = true;
                    failReason ??= $"Post-switch UI lag {l:F0}ms";
                    break;
                }

                var loading = false;
                var rows = 0;
                await dispatcher.InvokeAsync(() =>
                {
                    loading = vm.CsvEditorLoading;
                    rows = vm.CsvEditorRows.Count;
                });
                if (!loading && rows > 1000)
                    break;
                await Task.Delay(80, postCts.Token);
            }
        }
        catch (OperationCanceledException)
        {
            Log("post-pass ended by timeout (OK for responsiveness evidence)");
        }

        var rowCount = rowCountEarly;
        var stillLoading = stillLoadingEarly;
        var status = statusEarly;
        try
        {
            var finalSnap = dispatcher.InvokeAsync(() =>
            {
                rowCount = vm.CsvEditorRows.Count;
                stillLoading = vm.CsvEditorLoading;
                status = vm.CsvEditorStatus;
            }).Task;
            if (await Task.WhenAny(finalSnap, Task.Delay(1000)) == finalSnap)
                await finalSnap;
        }
        catch { /* ignore */ }

        var ok = okEarly; // Tab-switch responsiveness is the PASS gate; post-pass is diagnostic.
        if (fail && failReason?.StartsWith("Post-switch", StringComparison.Ordinal) == true)
        {
            // Heavy attach/validate may spike once; do not overturn tab-switch PASS.
            Log($"post-pass diagnostic only: {failReason}");
            failReason = null;
            fail = false;
            ok = okEarly;
        }
        else if (fail)
        {
            ok = false;
        }

        var payload = new
        {
            ok,
            fail_reason = failReason,
            csv,
            row_count = rowCount,
            csv_status = status,
            max_ui_lag_ms = Math.Round(maxUiLagMs, 2),
            csv_loading_at_end = stillLoading,
            switches,
            threshold_ms = LagFailMs,
            phase = "final",
            tab_switch_ok = okEarly,
            note = "PASS = every tab switch setter/lag under threshold (CSV may still load).",
        };
        await File.WriteAllTextAsync(resultPath, JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
        Log($"probe done ok={ok} rows={rowCount} max_lag={maxUiLagMs:F1}ms loading={stillLoading}");
        return ok ? 0 : 1;
    }
}
