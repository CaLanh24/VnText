using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;

namespace VNText.Studio.App.Services;

/// <summary>
/// Builds the anonymous bug report in its own short-lived Python process, so the button works while the worker is busy (image scan after an extract,
/// a translation being cancelled, a task that just failed).  The report only reads the game's structure and the package's status files.
/// </summary>
public static class BugReportProcess
{
    public sealed record Result(bool Ok, string Text, string Path = "", JsonElement? Json = null);

    /// <summary>True when this build carries the report channel (release builds made with the Owner's secrets file); the button is hidden otherwise.</summary>
    public static bool SendAvailable()
    {
        try { return File.Exists(System.IO.Path.Combine(WorkerPaths.RepoRoot(), "vntext", "report_endpoint.bin")); }
        catch (Exception exc) when (exc is IOException or InvalidOperationException or UnauthorizedAccessException) { return false; }
    }

    /// <summary>Sends one bundle the person has previewed and agreed to send; in its own process, never blocking the UI.</summary>
    public static Task<Result> SendAsync(string zipPath) =>
        RunAsync(new { action = "send", zip = zipPath }, TimeSpan.FromMinutes(2), "vntext.report_upload_cli", "message");

    public static async Task<Result> RunAsync(object parameters, TimeSpan? timeout = null, string module = "vntext.bug_report_cli", string failureKey = "error")
    {
        var parameterFile = Path.Combine(Path.GetTempPath(), "vntext-bugreport-" + Guid.NewGuid().ToString("N") + ".json");
        try
        {
            await File.WriteAllTextAsync(parameterFile, JsonSerializer.Serialize(parameters), new UTF8Encoding(false)).ConfigureAwait(false);
            var psi = new ProcessStartInfo
            {
                FileName = WorkerPaths.PythonExecutable(),
                Arguments = "-m " + module + " \"" + parameterFile + "\"",
                WorkingDirectory = WorkerPaths.RepoRoot(),
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8,
            };
            WorkerPaths.ConfigureReleaseEnvironment(psi.Environment);
            psi.Environment["PYTHONUTF8"] = "1";
            psi.Environment["PYTHONIOENCODING"] = "utf-8";
            psi.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
            using var process = Process.Start(psi) ?? throw new InvalidOperationException("Không chạy được tiến trình tạo gói báo lỗi.");
            var output = process.StandardOutput.ReadToEndAsync();
            _ = process.StandardError.ReadToEndAsync();
            using var cancel = new CancellationTokenSource(timeout ?? TimeSpan.FromMinutes(3));
            try { await process.WaitForExitAsync(cancel.Token).ConfigureAwait(false); }
            catch (OperationCanceledException)
            {
                try { process.Kill(true); } catch (InvalidOperationException) { }
                return new Result(false, "Tạo gói báo lỗi quá lâu nên đã dừng.");
            }
            var line = (await output.ConfigureAwait(false)).Split('\n', StringSplitOptions.RemoveEmptyEntries).LastOrDefault() ?? "";
            using var document = JsonDocument.Parse(line);
            var root = document.RootElement;
            var ok = root.TryGetProperty("ok", out var okValue) && okValue.ValueKind == JsonValueKind.True;
            var text = root.TryGetProperty(ok ? (root.TryGetProperty("summary", out _) ? "summary" : "message") : failureKey, out var textValue) ? textValue.GetString() ?? "" : "";
            var path = root.TryGetProperty("path", out var pathValue) ? pathValue.GetString() ?? "" : "";
            return new Result(ok, text, path, root.Clone());
        }
        catch (Exception exc) when (exc is IOException or JsonException or InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            return new Result(false, "Chưa tạo được gói báo lỗi: " + exc.Message);
        }
        finally
        {
            try { File.Delete(parameterFile); } catch (IOException) { }
        }
    }
}
