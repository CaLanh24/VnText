using System.IO;
using System.Windows;
using System.Windows.Threading;
using VNText.Studio.App.Services;

namespace VNText.Studio.App;

public partial class App : Application
{
    private ScrollbarProbe? _scrollbarProbe;

    protected override void OnStartup(StartupEventArgs e)
    {
        if (e.Args.Contains("--apply-wpf-update") || e.Args.Contains("--apply-github-wpf-update") ||
            e.Args.Contains("--apply-full-app-update") || e.Args.Contains("--apply-github-full-app-update") ||
            e.Args.Contains("--recover-full-app-update"))
        {
            Shutdown(WpfUpdateService.RunUpdater(e.Args));
            return;
        }

        if (e.Args.Contains("--update-health-check"))
        {
            Shutdown(WpfUpdateService.RunHealthCheck());
            return;
        }

        try
        {
            if (WorkerPaths.IsReleaseLayout())
            {
                var installRoot = Path.GetDirectoryName(WorkerPaths.MainExePath())!;
                if (FullAppUpdateService.StartInterruptedRecovery(installRoot))
                {
                    Shutdown();
                    return;
                }
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show("VNText Studio could not recover an interrupted update. Keep the install folder intact and contact support:\n" + ex.Message,
                "VNText Studio Update Recovery", MessageBoxButton.OK, MessageBoxImage.Error);
            Shutdown(6);
            return;
        }

        foreach (var flag in new[] { "--release-verify", "--release-verify-qml", "--release-version", "--release-verify-update" })
        {
            if (!e.Args.Contains(flag))
                continue;
            var reportIndex = Array.IndexOf(e.Args, "--report");
            var reportPath = reportIndex >= 0 && reportIndex + 1 < e.Args.Length
                ? e.Args[reportIndex + 1]
                : null;
            Shutdown(ReleaseVerifyRunner.Run(flag, reportPath));
            return;
        }

        if (e.Args.Contains("--smoke-worker"))
        {
            int code;
            try
            {
                code = Task.Run(SmokeWorker.Run).GetAwaiter().GetResult();
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine($"Smoke worker failed: {ex}");
                code = 1;
            }
            Shutdown(code);
            return;
        }

        base.OnStartup(e);
        ShutdownMode = ShutdownMode.OnMainWindowClose;
        var window = new MainWindow();
        MainWindow = window;
        Exit += (_, _) =>
        {
            if (window.DataContext is IDisposable disposable)
                disposable.Dispose();
        };

        var workflowE2eIdx = Array.IndexOf(e.Args, "--wpf-workflow-e2e");
        if (workflowE2eIdx >= 0 && workflowE2eIdx + 1 < e.Args.Length)
        {
            var reportPath = e.Args[workflowE2eIdx + 1];
            var inputPath = ArgumentValue(e.Args, "--input")
                ?? Environment.GetEnvironmentVariable("VNTEXT_WPF_E2E_INPUT")
                ?? "";
            var outputPath = ArgumentValue(e.Args, "--output")
                ?? Environment.GetEnvironmentVariable("VNTEXT_WPF_E2E_OUTPUT")
                ?? "";
            var translationModel = ArgumentValue(e.Args, "--translation-model") ?? "ct2";
            var modelDir = ArgumentValue(e.Args, "--model-dir") ?? "";
            var modelRevision = ArgumentValue(e.Args, "--model-revision") ?? "";
            window.Show();
            _ = Task.Run(async () =>
            {
                var code = await WpfWorkflowE2eProbe.RunAsync(
                        window,
                        inputPath,
                        outputPath,
                        reportPath,
                        translationModel,
                        modelDir,
                        modelRevision)
                    .ConfigureAwait(false);
                await window.Dispatcher.InvokeAsync(() => Shutdown(code));
            });
            return;
        }

        var probeIdx = Array.IndexOf(e.Args, "--scrollbar-probe");
        if (probeIdx >= 0 && probeIdx + 1 < e.Args.Length)
        {
            _scrollbarProbe = new ScrollbarProbe(window, e.Args[probeIdx + 1]);
            Exit += (_, _) => _scrollbarProbe?.Dispose();
        }

        var csvSbIdx = Array.IndexOf(e.Args, "--csv-scrollbar-fix-probe");
        if (csvSbIdx >= 0 && csvSbIdx + 1 < e.Args.Length)
        {
            var outDir = e.Args[csvSbIdx + 1];
            string? csv = null;
            var csvIdx = Array.IndexOf(e.Args, "--csv");
            if (csvIdx >= 0 && csvIdx + 1 < e.Args.Length)
                csv = e.Args[csvIdx + 1];

            window.Show();
            _ = Task.Run(async () =>
            {
                try
                {
                    await Task.Delay(500);
                    var code = await CsvScrollbarFixProbe.RunAsync(window, outDir, csv).ConfigureAwait(false);
                    var shutdown = window.Dispatcher.InvokeAsync(() => Shutdown(code));
                    if (await Task.WhenAny(shutdown.Task, Task.Delay(8000)).ConfigureAwait(false) != shutdown.Task)
                        Environment.Exit(code);
                }
                catch (Exception ex)
                {
                    try
                    {
                        Directory.CreateDirectory(outDir);
                        await File.WriteAllTextAsync(
                            Path.Combine(outDir, "result.json"),
                            System.Text.Json.JsonSerializer.Serialize(new { ok = false, error = ex.ToString() }));
                    }
                    catch { /* ignore */ }
                    Environment.Exit(1);
                }
            });
            return;
        }

        var polishIdx = Array.IndexOf(e.Args, "--ui-scrollbar-polish-probe");
        if (polishIdx >= 0 && polishIdx + 1 < e.Args.Length)
        {
            var outDir = e.Args[polishIdx + 1];
            string? csv = null;
            var csvIdx = Array.IndexOf(e.Args, "--csv");
            if (csvIdx >= 0 && csvIdx + 1 < e.Args.Length)
                csv = e.Args[csvIdx + 1];

            window.Show();
            _ = Task.Run(async () =>
            {
                try
                {
                    await Task.Delay(500);
                    var code = await UiScrollbarPolishProbe.RunAsync(window, outDir, csv).ConfigureAwait(false);
                    var shutdown = window.Dispatcher.InvokeAsync(() => Shutdown(code));
                    if (await Task.WhenAny(shutdown.Task, Task.Delay(8000)).ConfigureAwait(false) != shutdown.Task)
                        Environment.Exit(code);
                }
                catch (Exception ex)
                {
                    try
                    {
                        Directory.CreateDirectory(outDir);
                        await File.WriteAllTextAsync(
                            Path.Combine(outDir, "result.json"),
                            System.Text.Json.JsonSerializer.Serialize(new { ok = false, error = ex.ToString() }));
                    }
                    catch { /* ignore */ }
                    Environment.Exit(1);
                }
            });
            return;
        }

        var finalSbIdx = Array.IndexOf(e.Args, "--ui-scrollbar-final-probe");
        if (finalSbIdx >= 0 && finalSbIdx + 1 < e.Args.Length)
        {
            var outDir = e.Args[finalSbIdx + 1];
            string? csv = null;
            var csvIdx = Array.IndexOf(e.Args, "--csv");
            if (csvIdx >= 0 && csvIdx + 1 < e.Args.Length)
                csv = e.Args[csvIdx + 1];

            window.Show();
            _ = Task.Run(async () =>
            {
                try
                {
                    await Task.Delay(500);
                    var code = await UiScrollbarFinalProbe.RunAsync(window, outDir, csv).ConfigureAwait(false);
                    var shutdown = window.Dispatcher.InvokeAsync(() => Shutdown(code));
                    if (await Task.WhenAny(shutdown.Task, Task.Delay(8000)).ConfigureAwait(false) != shutdown.Task)
                        Environment.Exit(code);
                }
                catch (Exception ex)
                {
                    try
                    {
                        Directory.CreateDirectory(outDir);
                        await File.WriteAllTextAsync(
                            Path.Combine(outDir, "result.json"),
                            System.Text.Json.JsonSerializer.Serialize(new { ok = false, error = ex.ToString() }));
                    }
                    catch { /* ignore */ }
                    Environment.Exit(1);
                }
            });
            return;
        }

        var tabProbeFullIdx = Array.IndexOf(e.Args, "--tab-responsive-probe-full");
        if (tabProbeFullIdx >= 0 && tabProbeFullIdx + 1 < e.Args.Length)
        {
            var outDir = e.Args[tabProbeFullIdx + 1];
            string? csv = null;
            var csvIdx = Array.IndexOf(e.Args, "--csv");
            if (csvIdx >= 0 && csvIdx + 1 < e.Args.Length)
                csv = e.Args[csvIdx + 1];

            window.Show();
            _ = Task.Run(async () =>
            {
                try
                {
                    await Task.Delay(500);
                    var code = await TabResponsiveFullLoadProbe.RunAsync(window, outDir, csv).ConfigureAwait(false);
                    var shutdown = window.Dispatcher.InvokeAsync(() => Shutdown(code));
                    if (await Task.WhenAny(shutdown.Task, Task.Delay(5000)).ConfigureAwait(false) != shutdown.Task)
                        Environment.Exit(code);
                }
                catch (Exception ex)
                {
                    try
                    {
                        Directory.CreateDirectory(outDir);
                        await File.WriteAllTextAsync(
                            Path.Combine(outDir, "result.json"),
                            System.Text.Json.JsonSerializer.Serialize(new { ok = false, error = ex.ToString() }));
                    }
                    catch { /* ignore */ }
                    Environment.Exit(1);
                }
            });
            return;
        }

        var analyzeProbeIdx = Array.IndexOf(e.Args, "--analyze-ui-probe");
        if (analyzeProbeIdx >= 0 && analyzeProbeIdx + 1 < e.Args.Length)
        {
            var outDir = e.Args[analyzeProbeIdx + 1];
            window.Show();
            _ = Task.Run(async () =>
            {
                try
                {
                    await Task.Delay(500);
                    var code = await AnalyzeUiProbe.RunAsync(window, outDir).ConfigureAwait(false);
                    var shutdown = window.Dispatcher.InvokeAsync(() => Shutdown(code));
                    if (await Task.WhenAny(shutdown.Task, Task.Delay(5000)).ConfigureAwait(false) != shutdown.Task)
                        Environment.Exit(code);
                }
                catch (Exception ex)
                {
                    try
                    {
                        Directory.CreateDirectory(outDir);
                        await File.WriteAllTextAsync(
                            Path.Combine(outDir, "result.json"),
                            System.Text.Json.JsonSerializer.Serialize(new { ok = false, error = ex.ToString() }));
                    }
                    catch { /* ignore */ }
                    Environment.Exit(1);
                }
            });
            return;
        }

        var tabProbeIdx = Array.IndexOf(e.Args, "--tab-responsive-probe");
        if (tabProbeIdx >= 0 && tabProbeIdx + 1 < e.Args.Length)
        {
            var outDir = e.Args[tabProbeIdx + 1];
            string? csv = null;
            var csvIdx = Array.IndexOf(e.Args, "--csv");
            if (csvIdx >= 0 && csvIdx + 1 < e.Args.Length)
                csv = e.Args[csvIdx + 1];

            window.Show();
            // Run probe off the UI sync context to avoid Dispatcher await deadlocks.
            _ = Task.Run(async () =>
            {
                try
                {
                    await Task.Delay(400);
                    var code = await TabResponsiveProbe.RunAsync(window, outDir, csv).ConfigureAwait(false);
                    var shutdown = window.Dispatcher.InvokeAsync(() => Shutdown(code));
                    if (await Task.WhenAny(shutdown.Task, Task.Delay(3000)).ConfigureAwait(false) != shutdown.Task)
                        Environment.Exit(code);
                }
                catch (Exception ex)
                {
                    try
                    {
                        Directory.CreateDirectory(outDir);
                        await File.WriteAllTextAsync(
                            Path.Combine(outDir, "result.json"),
                            System.Text.Json.JsonSerializer.Serialize(new { ok = false, error = ex.ToString() }));
                    }
                    catch { /* ignore */ }
                    Environment.Exit(1);
                }
            });
            return;
        }

        var completionPopupIdx = Array.IndexOf(e.Args, "--translate-csv-completion-popup-probe");
        if (completionPopupIdx >= 0 && completionPopupIdx + 1 < e.Args.Length)
        {
            var outDir = e.Args[completionPopupIdx + 1];
            window.Show();
            _ = Task.Run(async () =>
            {
                try
                {
                    await Task.Delay(500);
                    var code = await TranslateCsvCompletionPopupProbe.RunAsync(window, outDir).ConfigureAwait(false);
                    var shutdown = window.Dispatcher.InvokeAsync(() => Shutdown(code));
                    if (await Task.WhenAny(shutdown.Task, Task.Delay(5000)).ConfigureAwait(false) != shutdown.Task)
                        Environment.Exit(code);
                }
                catch (Exception ex)
                {
                    try
                    {
                        Directory.CreateDirectory(outDir);
                        await File.WriteAllTextAsync(
                            Path.Combine(outDir, "result.json"),
                            System.Text.Json.JsonSerializer.Serialize(new { ok = false, error = ex.ToString() }));
                    }
                    catch { /* ignore */ }
                    Environment.Exit(1);
                }
            });
            return;
        }

        var patchOutputPickerIdx = Array.IndexOf(e.Args, "--patch-output-picker-probe");
        if (patchOutputPickerIdx >= 0 && patchOutputPickerIdx + 1 < e.Args.Length)
        {
            var outDir = e.Args[patchOutputPickerIdx + 1];
            window.Show();
            _ = Task.Run(async () =>
            {
                try
                {
                    await Task.Delay(500);
                    var code = await PatchOutputPickerProbe.RunAsync(window, outDir).ConfigureAwait(false);
                    var shutdown = window.Dispatcher.InvokeAsync(() => Shutdown(code));
                    if (await Task.WhenAny(shutdown.Task, Task.Delay(5000)).ConfigureAwait(false) != shutdown.Task)
                        Environment.Exit(code);
                }
                catch (Exception ex)
                {
                    try
                    {
                        Directory.CreateDirectory(outDir);
                        await File.WriteAllTextAsync(
                            Path.Combine(outDir, "result.json"),
                            System.Text.Json.JsonSerializer.Serialize(new { ok = false, error = ex.ToString() }));
                    }
                    catch { /* ignore */ }
                    Environment.Exit(1);
                }
            });
            return;
        }

        var csvEditorLayoutIdx = Array.IndexOf(e.Args, "--csv-editor-layout-probe");
        if (csvEditorLayoutIdx >= 0 && csvEditorLayoutIdx + 1 < e.Args.Length)
        {
            var outDir = e.Args[csvEditorLayoutIdx + 1];
            string? csv = null;
            var csvIdx = Array.IndexOf(e.Args, "--csv");
            if (csvIdx >= 0 && csvIdx + 1 < e.Args.Length)
                csv = e.Args[csvIdx + 1];

            window.Show();
            _ = Task.Run(async () =>
            {
                try
                {
                    await Task.Delay(500);
                    var code = await CsvEditorLayoutProbe.RunAsync(window, outDir, csv).ConfigureAwait(false);
                    var shutdown = window.Dispatcher.InvokeAsync(() => Shutdown(code));
                    if (await Task.WhenAny(shutdown.Task, Task.Delay(5000)).ConfigureAwait(false) != shutdown.Task)
                        Environment.Exit(code);
                }
                catch (Exception ex)
                {
                    try
                    {
                        Directory.CreateDirectory(outDir);
                        await File.WriteAllTextAsync(
                            Path.Combine(outDir, "result.json"),
                            System.Text.Json.JsonSerializer.Serialize(new { ok = false, error = ex.ToString() }));
                    }
                    catch { /* ignore */ }
                    Environment.Exit(1);
                }
            });
            return;
        }

        var bulkGlossaryIdx = Array.IndexOf(e.Args, "--bulk-glossary-ui-probe");
        if (bulkGlossaryIdx >= 0 && bulkGlossaryIdx + 1 < e.Args.Length)
        {
            var outDir = e.Args[bulkGlossaryIdx + 1];
            string? csv = null;
            var csvIdx = Array.IndexOf(e.Args, "--csv");
            if (csvIdx >= 0 && csvIdx + 1 < e.Args.Length)
                csv = e.Args[csvIdx + 1];

            window.Show();
            _ = Task.Run(async () =>
            {
                try
                {
                    await Task.Delay(500);
                    var code = await BulkGlossaryUiProbe.RunAsync(window, outDir, csv).ConfigureAwait(false);
                    var shutdown = window.Dispatcher.InvokeAsync(() => Shutdown(code));
                    if (await Task.WhenAny(shutdown.Task, Task.Delay(5000)).ConfigureAwait(false) != shutdown.Task)
                        Environment.Exit(code);
                }
                catch (Exception ex)
                {
                    try
                    {
                        Directory.CreateDirectory(outDir);
                        await File.WriteAllTextAsync(Path.Combine(outDir, "result.json"), System.Text.Json.JsonSerializer.Serialize(new { ok = false, error = ex.ToString() }));
                    }
                    catch { /* ignore */ }
                    Environment.Exit(1);
                }
            });
            return;
        }

        window.Show();
        MainWindowHandleNormalizer.Schedule(window);
    }

    private static string? ArgumentValue(string[] args, string name)
    {
        var index = Array.IndexOf(args, name);
        return index >= 0 && index + 1 < args.Length ? args[index + 1] : null;
    }
}
