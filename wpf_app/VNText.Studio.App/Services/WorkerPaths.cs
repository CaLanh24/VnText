using System.IO;
using System.Reflection;
using System.Collections.Generic;

namespace VNText.Studio.App.Services;

public static class WorkerPaths
{
    public const string WorkerDirName = "worker";
    public const string MainExeName = "VNText Studio.exe";

    public static string AppRoot()
    {
        var worker = TryResolveWorkerRoot(out var app);
        if (!string.IsNullOrEmpty(app))
            return app;

        if (string.Equals(Path.GetFileName(Environment.ProcessPath), MainExeName, StringComparison.OrdinalIgnoreCase))
        {
            var executableRoot = Path.GetDirectoryName(Environment.ProcessPath);
            if (!string.IsNullOrEmpty(executableRoot))
                return executableRoot;
        }

        foreach (var start in ProbeRoots())
        {
            if (File.Exists(Path.Combine(start, "VERSION.txt"))
                && File.Exists(Path.Combine(start, MainExeName)))
                return start;
        }

        foreach (var start in ProbeRoots())
        {
            var dir = start;
            for (var i = 0; i < 8; i++)
            {
                if (File.Exists(Path.Combine(dir, "VERSION.txt")))
                    return dir;
                var parent = Directory.GetParent(dir);
                if (parent is null) break;
                dir = parent.FullName;
            }
        }
        return Directory.GetCurrentDirectory();
    }

    public static bool IsReleaseLayout()
    {
        if (string.Equals(Path.GetFileName(Environment.ProcessPath), MainExeName, StringComparison.OrdinalIgnoreCase))
            return true;
        if (TryResolveWorkerRoot(out _) is not null)
            return true;
        return ProbeRoots().Any(start =>
            File.Exists(Path.Combine(start, "VERSION.txt"))
            && File.Exists(Path.Combine(start, MainExeName)));
    }

    public static string WorkerRoot()
    {
        var worker = TryResolveWorkerRoot(out var app);
        if (!string.IsNullOrEmpty(worker))
            return worker;

        if (!string.IsNullOrEmpty(app) && Directory.Exists(Path.Combine(app, "vntext_worker")))
            return app;

        return AppRoot();
    }

    public static string RepoRoot()
    {
        if (!IsReleaseLayout())
        {
            var overrideCwd = Environment.GetEnvironmentVariable("VNTEXT_WORKER_CWD");
            if (!string.IsNullOrWhiteSpace(overrideCwd) && Directory.Exists(overrideCwd))
                return Path.GetFullPath(overrideCwd);
        }

        return WorkerRoot();
    }

    public static string AppDataRoot()
    {
        if (!IsReleaseLayout())
        {
            var local = Environment.GetEnvironmentVariable("VNTEXT_LOCALAPPDATA");
            if (string.IsNullOrWhiteSpace(local))
                local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            var devData = Path.Combine(local, "VNTextStudio");
            Directory.CreateDirectory(devData);
            return devData;
        }

        var appRoot = AppRoot();
        var installRoot = string.Equals(Path.GetFileName(appRoot), "app", StringComparison.OrdinalIgnoreCase)
            ? Directory.GetParent(appRoot)?.FullName ?? appRoot
            : appRoot;
        var data = Path.Combine(installRoot, "data");
        try
        {
            Directory.CreateDirectory(data);
            var probe = Path.Combine(data, ".write_probe_" + Guid.NewGuid().ToString("N"));
            File.WriteAllText(probe, "ok");
            File.Delete(probe);
            return data;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            throw new IOException($"VNText Studio cannot write to its install data folder: {data}. Choose a writable install folder or grant write access.", ex);
        }
    }

    public static void ConfigureReleaseEnvironment(IDictionary<string, string?> environment)
    {
        if (!IsReleaseLayout()) return;
        var data = AppDataRoot();
        var temp = Path.Combine(data, "temp");
        var cache = Path.Combine(data, "cache");
        Directory.CreateDirectory(temp);
        Directory.CreateDirectory(cache);
        environment["VNTEXT_DATA_ROOT"] = data;
        environment["VNTEXT_RENPY_TOOL_ROOT"] = Path.Combine(data, "tools");
        environment["TEMP"] = environment["TMP"] = environment["TMPDIR"] = temp;
        environment["LOCALAPPDATA"] = environment["APPDATA"] = data;
        environment["HF_HOME"] = Path.Combine(cache, "huggingface");
        environment["HF_HUB_CACHE"] = Path.Combine(cache, "huggingface", "hub");
        environment["TRANSFORMERS_CACHE"] = Path.Combine(cache, "huggingface", "transformers");
        environment["TORCH_HOME"] = Path.Combine(cache, "torch");
        environment["VNTEXT_DIRECT_GPU_ROOT"] = Path.Combine(cache, "gpu");
        // Execute bundled CPython directly: the Windows venv launcher requires
        // rewriting pyvenv.cfg after relocation, which would invalidate the
        // exact full-app baseline. Keep every shipped file immutable.
        var worker = WorkerRoot();
        environment["PYTHONHOME"] = Path.Combine(worker, "python");
        environment["PYTHONPATH"] = Path.Combine(worker, ".venv", "Lib", "site-packages");
        environment["PYTHONNOUSERSITE"] = "1";
        environment["PYTHONDONTWRITEBYTECODE"] = "1";
    }

    public static string MainExePath()
    {
        foreach (var start in ProbeRoots())
        {
            var release = Path.Combine(start, MainExeName);
            if (File.Exists(release))
                return release;
        }

        var app = AppRoot();
        var installRoot = string.Equals(Path.GetFileName(app), "app", StringComparison.OrdinalIgnoreCase)
            ? Directory.GetParent(app)?.FullName ?? app
            : app;
        var installedExe = Path.Combine(installRoot, MainExeName);
        if (File.Exists(installedExe))
            return installedExe;

        var devPublish = Path.Combine(app, "release", "wpf_publish", "VNText.Studio.App.exe");
        if (File.Exists(devPublish))
            return devPublish;
        var devBin = Path.Combine(app, "wpf_app", "VNText.Studio.App", "bin", "Release", "net8.0-windows", "win-x64", "VNText.Studio.App.exe");
        if (File.Exists(devBin))
            return devBin;
        return Path.Combine(app, MainExeName);
    }

    public static string PythonExecutable()
    {
        if (!IsReleaseLayout())
        {
            var overridePython = Environment.GetEnvironmentVariable("VNTEXT_WORKER_PYTHON");
            if (!string.IsNullOrWhiteSpace(overridePython))
            {
                var resolved = Path.GetFullPath(overridePython);
                if (!File.Exists(resolved))
                    throw new InvalidOperationException($"Configured test Python worker missing: {resolved}");
                return resolved;
            }
        }

        var worker = WorkerRoot();
        var portable = Path.Combine(worker, ".venv", "Scripts", "python.exe");
        if (File.Exists(portable))
        {
            if (IsReleaseLayout())
            {
                EnsurePortablePyvenvCfg(worker);
                return Path.Combine(worker, "python", "python.exe");
            }
            return portable;
        }

        if (IsReleaseLayout())
        {
            throw new InvalidOperationException(
                $"Release Python worker missing: {portable}. Reinstall VNText Studio or restore worker/.venv.");
        }

        var devVenv = Path.Combine(AppRoot(), ".venv", "Scripts", "python.exe");
        if (File.Exists(devVenv))
            return devVenv;

        return "python";
    }

    /// <summary>
    /// Validate the shipped runtime without rewriting its hashed inventory.
    /// Release callers execute bundled CPython with ConfigureReleaseEnvironment.
    /// </summary>
    public static void EnsurePortablePyvenvCfg(string workerRoot)
    {
        var bundled = Path.Combine(workerRoot, "python");
        var bundledExe = Path.Combine(bundled, "python.exe");
        var cfgPath = Path.Combine(workerRoot, ".venv", "pyvenv.cfg");
        if (!File.Exists(bundledExe))
            throw new InvalidOperationException(
                $"Release portable Python missing: {bundledExe}. Re-publish or restore worker/python.");
        if (!File.Exists(cfgPath))
            throw new InvalidOperationException($"Release pyvenv.cfg missing: {cfgPath}");

        if (!Directory.Exists(Path.Combine(workerRoot, ".venv", "Lib", "site-packages")))
            throw new InvalidOperationException("Release worker site-packages missing.");
        var check = File.ReadAllText(cfgPath);
        if (check.Contains("Programs\\Python", StringComparison.OrdinalIgnoreCase)
            || check.Contains("Programs/Python", StringComparison.OrdinalIgnoreCase)
            || check.Contains("portable_zip_update", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Release pyvenv.cfg still references system/build Python.");
        }
    }

    public static string WorkerModuleArgs() => "-m vntext_worker.worker_main";

    public static string WorkArtifactsRoot()
    {
        if (!IsReleaseLayout())
        {
            var configuredWorkRoot = Environment.GetEnvironmentVariable("VNTEXT_WORK_ARTIFACTS_ROOT");
            if (!string.IsNullOrWhiteSpace(configuredWorkRoot))
                return Path.GetFullPath(configuredWorkRoot);
        }
        var app = AppRoot();
        if (Directory.Exists(Path.Combine(app, "tests", "golden")))
            return Path.Combine(app, "tests", "golden", "_work");
        if (IsReleaseLayout())
            return Path.Combine(AppDataRoot(), "work");
        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        return ResolveWritableWorkArtifactsRoot(
            Path.Combine(local, "VNTextStudio", "_work"),
            Path.Combine(Path.GetTempPath(), "VNTextStudio", "_work"));
    }

    public static string ResolveWritableWorkArtifactsRoot(string primary, string fallback)
    {
        foreach (var candidate in new[] { primary, fallback })
        {
            try
            {
                Directory.CreateDirectory(candidate);
                var probe = Path.Combine(candidate, ".write_probe_" + Guid.NewGuid().ToString("N"));
                File.WriteAllText(probe, "ok");
                File.Delete(probe);
                return candidate;
            }
            catch (IOException)
            {
                // Try the next root without modifying permissions on either location.
            }
            catch (UnauthorizedAccessException)
            {
                // Try the next root without modifying permissions on either location.
            }
        }
        throw new IOException($"No writable worker artifact directory: {primary} or {fallback}");
    }

    /// <summary>RELEASE: {probe}/worker with vntext_worker + portable python.</summary>
    private static string? TryResolveWorkerRoot(out string? appRoot)
    {
        appRoot = null;
        foreach (var start in ProbeRoots())
        {
            foreach (var candidateApp in new[] { start, Path.Combine(start, "app") })
            {
                var worker = Path.Combine(candidateApp, WorkerDirName);
                if (!Directory.Exists(Path.Combine(worker, "vntext_worker")))
                    continue;
                if (!File.Exists(Path.Combine(worker, ".venv", "Scripts", "python.exe")))
                    continue;
                appRoot = candidateApp;
                return worker;
            }
        }
        return null;
    }

    private static IEnumerable<string> ProbeRoots()
    {
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var path in EnumerateProbeRoots())
        {
            if (string.IsNullOrWhiteSpace(path)) continue;
            var trimmed = path.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            if (trimmed.Length == 0 || !seen.Add(trimmed)) continue;
            yield return trimmed;
        }
    }

    private static IEnumerable<string> EnumerateProbeRoots()
    {
        if (!string.IsNullOrEmpty(Environment.ProcessPath))
        {
            var exeDir = Path.GetDirectoryName(Environment.ProcessPath);
            if (!string.IsNullOrEmpty(exeDir))
                yield return exeDir;
        }

        yield return AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);

        var asmDir = TryGetAssemblyDirectory();
        if (!string.IsNullOrEmpty(asmDir))
            yield return asmDir;

        yield return Directory.GetCurrentDirectory();
    }

    private static string? TryGetAssemblyDirectory()
    {
        try
        {
            var asm = Assembly.GetExecutingAssembly().Location;
            if (string.IsNullOrEmpty(asm))
                return null;
            return Path.GetDirectoryName(asm);
        }
        catch
        {
            return null;
        }
    }
}
