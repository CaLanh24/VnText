using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;

namespace VNText.Studio.App.Services;

public sealed record PatchPreflightResult(
    bool Ok,
    string Summary,
    int Eligible,
    int Blocked,
    int ManifestEntries,
    int TranslatedRows,
    IReadOnlyDictionary<string, int> ReasonCounts,
    string CsvPath,
    string? ManifestPath,
    string? Error = null)
{
    public string DetailMessage
    {
        get
        {
            if (!string.IsNullOrWhiteSpace(Error))
                return Error;
            if (ReasonCounts.Count == 0)
                return Summary;
            var parts = ReasonCounts
                .OrderByDescending(kv => kv.Value)
                .Select(kv => $"{FormatReason(kv.Key)}: {kv.Value}");
            return Summary + Environment.NewLine + string.Join(Environment.NewLine, parts);
        }
    }

    private static string FormatReason(string code) => code switch
    {
        "review_only" => "Trong review_only.csv",
        "no_translation" => "Chưa có bản dịch",
        "garbage_repetition" => "Rác lặp từ/ký tự",
        "html_garbage" => "HTML/entity rác",
        "synonym_manual" => "Synonym — dịch thủ công",
        "tag mismatch" => "Hỏng tag",
        "placeholder mismatch" => "Sai placeholder",
        "validation" => "Validation MT",
        _ => code,
    };

    public static PatchPreflightResult Fail(string csvPath, string message) =>
        new(false, message, 0, 0, 0, 0, new Dictionary<string, int>(), csvPath, null, message);
}

public static class PatchPreflightService
{
    public static PatchPreflightResult Run(string? csvPath, string? manifestPath)
    {
        var csv = (csvPath ?? "").Trim().Trim('"');
        var manifest = (manifestPath ?? "").Trim().Trim('"');
        if (string.IsNullOrEmpty(csv))
            return PatchPreflightResult.Fail("", "Chưa chọn translation.csv");
        if (!File.Exists(csv))
            return PatchPreflightResult.Fail(csv, "translation.csv không tồn tại");
        if (string.IsNullOrEmpty(manifest))
            manifest = Path.Combine(Path.GetDirectoryName(csv) ?? "", "manifest.json");
        if (!File.Exists(manifest))
            return PatchPreflightResult.Fail(csv, "Thiếu manifest.json cùng thư mục");

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = WorkerPaths.PythonExecutable(),
                Arguments = $"-m vntext.patch_gate --json \"{csv}\" \"{manifest}\"",
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

            using var proc = Process.Start(psi);
            if (proc is null)
                return PatchPreflightResult.Fail(csv, "Không khởi chạy được Python worker");

            var stdout = proc.StandardOutput.ReadToEnd();
            var stderr = proc.StandardError.ReadToEnd();
            proc.WaitForExit(TimeSpan.FromMinutes(2));

            if (proc.ExitCode != 0 && string.IsNullOrWhiteSpace(stdout))
                return PatchPreflightResult.Fail(csv, string.IsNullOrWhiteSpace(stderr) ? "Kiểm tra patch thất bại" : stderr.Trim());

            var jsonText = stdout.Trim();
            var start = jsonText.IndexOf('{');
            if (start > 0)
                jsonText = jsonText[start..];

            using var doc = JsonDocument.Parse(jsonText);
            var root = doc.RootElement;
            var reasons = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
            if (root.TryGetProperty("reason_counts", out var rc) && rc.ValueKind == JsonValueKind.Object)
            {
                foreach (var prop in rc.EnumerateObject())
                {
                    if (prop.Value.TryGetInt32(out var n))
                        reasons[prop.Name] = n;
                }
            }

            return new PatchPreflightResult(
                root.TryGetProperty("ok", out var okEl) && okEl.GetBoolean(),
                root.TryGetProperty("summary", out var sumEl) ? sumEl.GetString() ?? "" : "",
                root.TryGetProperty("eligible", out var elEl) ? elEl.GetInt32() : 0,
                root.TryGetProperty("blocked", out var blEl) ? blEl.GetInt32() : 0,
                root.TryGetProperty("manifest_entries", out var meEl) ? meEl.GetInt32() : 0,
                root.TryGetProperty("translated_rows", out var trEl) ? trEl.GetInt32() : 0,
                reasons,
                csv,
                manifest);
        }
        catch (Exception ex)
        {
            return PatchPreflightResult.Fail(csv, $"Lỗi kiểm tra patch: {ex.Message}");
        }
    }
}
