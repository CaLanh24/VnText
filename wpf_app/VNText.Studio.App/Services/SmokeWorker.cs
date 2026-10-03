using System.IO;
using System.Text.Json;
using VNText.Studio.App.Models;

namespace VNText.Studio.App.Services;

public static class SmokeWorker
{
    public static int Run(string? reportPath = null)
    {
        var steps = new List<object>();
        string? failedStep = null;
        string? workRoot = null;
        var code = 1;
        int Step(string name, Func<Action<WorkerEvent>, int> run)
        {
            failedStep = name;
            var events = new List<object>();
            void Observe(WorkerEvent evt)
            {
                if (evt.Type is "complete" or "error")
                    events.Add(new { type = evt.Type, id = evt.Id, ok = evt.Ok,
                        error = evt.Error, summary = evt.Summary,
                        diagnostic_stage = evt.DiagnosticStage,
                        diagnostic_root_cause = evt.DiagnosticRootCause });
            }
            int result;
            string? exception = null;
            try { result = run(Observe); }
            catch (Exception ex) { result = 1; exception = ex.ToString(); }
            steps.Add(new { step = name, exit_code = result, events, exception });
            if (result == 0) failedStep = null;
            return result;
        }
        try
        {
            code = Step("cancel", RunSampleCancelSmoke);
            if (code == 0)
            {
                failedStep = "prepare_work_root";
                workRoot = PrepareWorkRoot(WorkerPaths.WorkArtifactsRoot());
                code = Step("extract", observe => RunExtractSmoke(workRoot, observe));
                if (code == 0) code = Step("translate", observe => RunTranslateSmoke(workRoot, observe));
                if (code == 0) code = Step("patch", observe => RunPatchSmoke(workRoot, observe));
                if (code == 0) code = Step("crash", RunWorkerCrashSmoke);
            }
        }
        catch (Exception ex)
        {
            code = 1;
            steps.Add(new { step = failedStep, exit_code = code, exception = ex.ToString() });
        }
        finally
        {
            string? cleanupError = null;
            if (workRoot is not null)
            {
                try { Directory.Delete(workRoot, recursive: true); }
                catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
                { cleanupError = ex.ToString(); }
            }
            string Report() => JsonSerializer.Serialize(new { schema = 1, ok = code == 0,
                exit_code = code, failed_step = failedStep, steps, cleanup_error = cleanupError });
            try { if (reportPath is not null) File.WriteAllText(reportPath, Report()); }
            catch (Exception ex)
            {
                failedStep = "write_report";
                code = 1;
                steps.Add(new { step = failedStep, exit_code = code, exception = ex.ToString() });
                Console.Error.WriteLine(ex);
            }
            Console.WriteLine(Report());
        }
        return code;
    }

    public static string PrepareWorkRoot(string artifactsRoot)
    {
        Directory.CreateDirectory(artifactsRoot);
        // Never reuse a previous smoke tree: patch output layout is part of
        // the smoke assertion and can change between builds.
        for (var attempt = 0; attempt < 3; attempt++)
        {
            var candidate = Path.Combine(artifactsRoot, "smoke_m3_" + Guid.NewGuid().ToString("N"));
            if (CanWriteTo(candidate))
                return candidate;
        }

        throw new IOException($"No writable smoke work directory under {artifactsRoot}");
    }

    public static string? FindPatchedSamplePath(string outputDirectory)
    {
        var patchContainer = Path.Combine(outputDirectory, "Patch_Viet_Hoa");
        if (Directory.Exists(patchContainer))
        {
            var patchDirectory = Directory.EnumerateDirectories(
                    patchContainer,
                    "VNTextPatch_v*",
                    SearchOption.TopDirectoryOnly)
                .OrderByDescending(path => path, StringComparer.OrdinalIgnoreCase)
                .FirstOrDefault()
                ?? patchContainer;
            var versionedSample = Path.Combine(patchDirectory, "COPY_TO_GAME_ROOT", "sample.txt");
            if (File.Exists(versionedSample))
                return versionedSample;
        }

        // Older patch fixtures place COPY_TO_GAME_ROOT directly under the
        // output directory. Keep smoke compatible with that contractual layout.
        var legacySample = Path.Combine(outputDirectory, "COPY_TO_GAME_ROOT", "sample.txt");
        return File.Exists(legacySample) ? legacySample : null;
    }

    private static bool CanWriteTo(string directory)
    {
        try
        {
            Directory.CreateDirectory(directory);
            var probe = Path.Combine(directory, ".write_probe_" + Guid.NewGuid().ToString("N"));
            File.WriteAllText(probe, "ok");
            File.Delete(probe);
            return true;
        }
        catch (IOException)
        {
            return false;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
    }

    private static int RunSampleCancelSmoke(Action<WorkerEvent> observe)
    {
        using var host = new PythonWorkerHost();
        var ready = new ManualResetEventSlim(false);
        var complete = new ManualResetEventSlim(false);
        var sawProgress = false;

        host.EventReceived += (_, evt) =>
        {
            observe(evt);
            switch (evt.Type)
            {
                case "ready":
                    ready.Set();
                    break;
                case "progress":
                    if (evt.Total > 0) sawProgress = true;
                    break;
                case "complete":
                    complete.Set();
                    break;
            }
        };

        host.StartAsync().GetAwaiter().GetResult();
        if (!ready.Wait(TimeSpan.FromSeconds(15)))
            return 2;

        var taskId = "smoke-sample";
        host.RunTask(taskId, "sample", new { steps = 8, delay_ms = 40 });
        Thread.Sleep(120);
        host.Cancel(taskId);

        if (!complete.Wait(TimeSpan.FromSeconds(10)))
            return 3;
        if (!sawProgress)
            return 4;
        if (host.IsBusy)
            return 5;
        return 0;
    }

    private static int RunExtractSmoke(string workRoot, Action<WorkerEvent> observe)
    {
        using var host = new PythonWorkerHost();
        var ready = new ManualResetEventSlim(false);
        var complete = new ManualResetEventSlim(false);
        var sawProgress = false;
        var ok = false;

        host.EventReceived += (_, evt) =>
        {
            observe(evt);
            switch (evt.Type)
            {
                case "ready":
                    ready.Set();
                    break;
                case "progress":
                    if (evt.Total > 0) sawProgress = true;
                    break;
                case "complete":
                    ok = evt.Ok;
                    complete.Set();
                    break;
            }
        };

        host.StartAsync().GetAwaiter().GetResult();
        if (!ready.Wait(TimeSpan.FromSeconds(15)))
            return 12;

        var src = Path.Combine(workRoot, "game");
        Directory.CreateDirectory(src);
        File.WriteAllText(Path.Combine(src, "sample.txt"), "NPC: Hello there\n");
        var outDir = Path.Combine(workRoot, "package");

        host.RunTask("smoke-extract", "extract", new
        {
            src,
            @out = outDir,
            mode = "deep",
            level = "balanced",
            separate_review = true,
        });

        if (!complete.Wait(TimeSpan.FromSeconds(60)))
            return 13;
        if (!sawProgress)
            return 14;
        if (!ok)
            return 15;
        if (host.IsBusy)
            return 16;
        return 0;
    }

    private static int RunTranslateSmoke(string workRoot, Action<WorkerEvent> observe)
    {
        using var host = new PythonWorkerHost();
        var ready = new ManualResetEventSlim(false);
        var complete = new ManualResetEventSlim(false);
        var ok = false;

        host.EventReceived += (_, evt) =>
        {
            observe(evt);
            switch (evt.Type)
            {
                case "ready":
                    ready.Set();
                    break;
                case "complete":
                    ok = evt.Ok;
                    complete.Set();
                    break;
            }
        };

        host.StartAsync().GetAwaiter().GetResult();
        if (!ready.Wait(TimeSpan.FromSeconds(15)))
            return 22;

        var outDir = Path.Combine(workRoot, "package");
        host.RunTask("smoke-translate", "translate", new { @out = outDir, overwrite = false });

        if (!complete.Wait(TimeSpan.FromSeconds(90)))
            return 23;
        if (!ok)
            return 24;

        var csvPath = Path.Combine(outDir, "translation.csv");
        if (!File.Exists(csvPath))
            return 25;
        if (!File.ReadAllText(csvPath).Contains("translation", StringComparison.Ordinal))
            return 26;
        if (host.IsBusy)
            return 27;
        return 0;
    }

    private static int RunPatchSmoke(string workRoot, Action<WorkerEvent> observe)
    {
        using var host = new PythonWorkerHost();
        var ready = new ManualResetEventSlim(false);
        var complete = new ManualResetEventSlim(false);
        var ok = false;
        Directory.CreateDirectory(workRoot);

        host.EventReceived += (_, evt) =>
        {
            observe(evt);
            switch (evt.Type)
            {
                case "ready":
                    ready.Set();
                    break;
                case "complete":
                    ok = evt.Ok;
                    complete.Set();
                    break;
            }
        };

        host.StartAsync().GetAwaiter().GetResult();
        if (!ready.Wait(TimeSpan.FromSeconds(15)))
            return 32;

        var src = Path.Combine(workRoot, "game");
        var outDir = Path.Combine(workRoot, "package");
        // Exercise the same explicit CSV/manifest path used by the real Patch tab.
        // Without these fields the worker resolves outDir as an already-created
        // Patch_Viet_Hoa directory and the versioned output becomes nested.
        var csvPath = Path.Combine(outDir, "translation.csv");
        var manifestPath = Path.Combine(outDir, "manifest.json");
        host.RunTask("smoke-patch", "patch", new
        {
            src,
            @out = outDir,
            csv_path = csvPath,
            manifest_path = manifestPath,
        });

        // The first patch run also copies the self-contained installer into the
        // package; on a cold disk this can exceed one minute.
        if (!complete.Wait(TimeSpan.FromMinutes(3)))
            return 33;
        if (!ok)
            return 34;

        var patched = FindPatchedSamplePath(outDir);
        if (patched is null)
            return 35;
        var patchContainer = Path.Combine(outDir, "Patch_Viet_Hoa");
        if (Directory.Exists(patchContainer))
        {
            var patchDir = Directory.EnumerateDirectories(patchContainer, "VNTextPatch_v*", SearchOption.TopDirectoryOnly)
                .OrderByDescending(path => path, StringComparer.OrdinalIgnoreCase)
                .FirstOrDefault();
            if (patchDir is not null &&
                (!File.Exists(Path.Combine(patchDir, "patch_manifest.json")) ||
                 !File.Exists(Path.Combine(patchDir, "VNTextPatchInstaller.exe"))))
                return 37;
        }
        if (host.IsBusy)
            return 36;
        return 0;
    }

    private static int RunWorkerCrashSmoke(Action<WorkerEvent> observe)
    {
        using var host = new PythonWorkerHost();
        var ready = new ManualResetEventSlim(false);
        var complete = new ManualResetEventSlim(false);
        var ok = true;

        host.EventReceived += (_, evt) =>
        {
            observe(evt);
            switch (evt.Type)
            {
                case "ready":
                    ready.Set();
                    break;
                case "complete":
                    ok = evt.Ok;
                    complete.Set();
                    break;
            }
        };

        host.StartAsync().GetAwaiter().GetResult();
        if (!ready.Wait(TimeSpan.FromSeconds(15)))
            return 42;

        host.RunTask("smoke-crash", "sample", new { steps = 80, delay_ms = 100 });
        Thread.Sleep(250);
        host.KillWorkerForSmoke();

        if (!complete.Wait(TimeSpan.FromSeconds(10)))
            return 43;
        if (ok)
            return 44;
        if (host.IsBusy)
            return 45;
        return 0;
    }
}
