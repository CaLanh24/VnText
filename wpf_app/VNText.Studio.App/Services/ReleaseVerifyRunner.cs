using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.Json;

namespace VNText.Studio.App.Services;

public static class ReleaseVerifyRunner
{
    private static int WriteReleaseVersion(string? reportPath)
    {
        var version = (File.Exists(WorkerPaths.MainExePath())
                ? FileVersionInfo.GetVersionInfo(WorkerPaths.MainExePath()).ProductVersion
                : null)?
            .Trim();
        var assembly = Assembly.GetEntryAssembly() ?? Assembly.GetExecutingAssembly();
        if (string.IsNullOrWhiteSpace(version))
        {
            version = assembly
                .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?
                .InformationalVersion?
                .Trim();
        }
        if (string.IsNullOrWhiteSpace(version))
            version = assembly.GetName().Version?.ToString(3);
        if (!string.IsNullOrWhiteSpace(version))
            version = version.Split('+', 2)[0].Trim();
        if (string.IsNullOrWhiteSpace(version))
        {
            Console.Error.WriteLine("Release assembly has no version metadata.");
            return 1;
        }

        var target = string.IsNullOrWhiteSpace(reportPath)
            ? Path.Combine(WorkerPaths.WorkArtifactsRoot(), "release_version.json")
            : Path.GetFullPath(reportPath);
        var parent = Path.GetDirectoryName(target);
        if (!string.IsNullOrWhiteSpace(parent))
            Directory.CreateDirectory(parent);
        File.WriteAllText(
            target,
            JsonSerializer.Serialize(new { version, ok = true }),
            Encoding.UTF8);
        return 0;
    }

    public static IReadOnlyList<string> BuildPythonArguments(string import, string func, string? reportPath)
    {
        var arguments = new List<string>
        {
            "-c",
            $"from {import} import {func}; raise SystemExit({func}())",
        };
        if (!string.IsNullOrWhiteSpace(reportPath))
        {
            arguments.Add("--report");
            arguments.Add(reportPath);
        }
        return arguments;
    }

    public static int Run(string mode, string? reportPath = null)
    {
        var (import, func) = mode switch
        {
            "--release-verify" => ("vntext.release_verify", "run_release_verify"),
            "--release-verify-qml" => ("vntext.release_verify", "run_release_verify_qml"),
            "--release-version" => ("vntext.release_verify", "run_release_version"),
            "--release-verify-update" => ("vntext.release_verify", "run_release_verify_update"),
            _ => throw new ArgumentException($"Unknown verify mode: {mode}", nameof(mode)),
        };

        var root = WorkerPaths.RepoRoot();
        string python;
        try
        {
            python = WorkerPaths.PythonExecutable();
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine(ex.Message);
            return 1;
        }

        if (WorkerPaths.IsReleaseLayout() && python.Contains("Programs\\Python", StringComparison.OrdinalIgnoreCase))
        {
            Console.Error.WriteLine($"Release must not use system Python: {python}");
            return 1;
        }

        if (WorkerPaths.IsReleaseLayout())
        {
            var worker = WorkerPaths.WorkerRoot();
            var bundled = Path.Combine(worker, "python", "python.exe");
            var cfg = Path.Combine(worker, ".venv", "pyvenv.cfg");
            if (!File.Exists(bundled))
            {
                Console.Error.WriteLine($"Release missing bundled portable Python: {bundled}");
                return 1;
            }
            if (!File.Exists(cfg))
            {
                Console.Error.WriteLine($"Release missing pyvenv.cfg: {cfg}");
                return 1;
            }
            var cfgText = File.ReadAllText(cfg);
            if (cfgText.Contains("Programs\\Python", StringComparison.OrdinalIgnoreCase)
                || cfgText.Contains("portable_zip_update", StringComparison.OrdinalIgnoreCase)
                || cfgText.Contains("VNText_Studio_Core", StringComparison.OrdinalIgnoreCase))
            {
                Console.Error.WriteLine("Release pyvenv.cfg still references system/build Python paths.");
                return 1;
            }
            if (!cfgText.Contains(Path.Combine(worker, "python"), StringComparison.OrdinalIgnoreCase))
            {
                Console.Error.WriteLine("Release pyvenv.cfg home must point at worker/python.");
                return 1;
            }

            if (mode == "--release-version")
                return WriteReleaseVersion(reportPath);
        }

        var psi = new ProcessStartInfo
        {
            FileName = python,
            WorkingDirectory = root,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        WorkerPaths.ConfigureReleaseEnvironment(psi.Environment);
        foreach (var argument in BuildPythonArguments(import, func, reportPath))
            psi.ArgumentList.Add(argument);
        psi.Environment["PYTHONUTF8"] = "1";
        psi.Environment["PYTHONIOENCODING"] = "utf-8";
        psi.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        if (mode == "--release-verify-update" && WorkerPaths.IsReleaseLayout())
        {
            var siblingManifest = Path.Combine(WorkerPaths.AppRoot(), "RELEASE.json");
            if (File.Exists(siblingManifest))
                psi.Environment["VNTEXT_UPDATE_URL"] = siblingManifest;
            psi.Environment["VNTEXT_UPDATE_TARGET_EXE"] = WorkerPaths.MainExePath();
        }

        using var proc = Process.Start(psi);
        if (proc is null)
            return 1;

        // Drain both redirected pipes concurrently.  Reading stdout to EOF
        // before stderr can deadlock when a release verification emits enough
        // diagnostics to fill stderr's pipe buffer; the Python child then
        // cannot finish, so no report or exit code reaches QA.
        var stdoutTask = proc.StandardOutput.ReadToEndAsync();
        var stderrTask = proc.StandardError.ReadToEndAsync();
        proc.WaitForExit();
        Task.WaitAll(stdoutTask, stderrTask);
        var stdout = stdoutTask.Result;
        var stderr = stderrTask.Result;
        if (!string.IsNullOrWhiteSpace(stdout))
            Console.Out.Write(stdout);
        if (!string.IsNullOrWhiteSpace(stderr))
            Console.Error.Write(stderr);
        return proc.ExitCode;
    }
}
