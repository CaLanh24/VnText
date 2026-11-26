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
    string? Error = null,
    IReadOnlyList<PatchSkippedItem>? Items = null,
    bool ItemsTruncated = false,
    int UserExcluded = 0,
    int OutsideCsvReview = 0)
{
    public IReadOnlyList<PatchSkippedItem> SkippedItems => Items ?? Array.Empty<PatchSkippedItem>();

    public string DetailMessage
    {
        get
        {
            if (!string.IsNullOrWhiteSpace(Error))
                return Error;
            var summary = Ok ? UiText.Msg("{0} câu sẵn sàng; {1} câu sẽ được bỏ qua.", Eligible, Blocked) : Summary;
            if (UserExcluded > 0 || OutsideCsvReview > 0)
                summary = UiText.Lines(summary, UiText.Msg("Không tính: {0} dòng bạn đã xóa, {1} dòng chỉ để xem lại ngoài bản dịch (không dịch, không đưa vào bản Việt hóa).", UserExcluded, OutsideCsvReview));
            if (ReasonCounts.Count == 0)
                return summary;
            var parts = ReasonCounts
                .OrderByDescending(kv => kv.Value)
                .Select(kv => UiText.Msg("{0}: {1}", UiText.Key(FormatReason(kv.Key)), kv.Value));
            return UiText.Lines(new[] { summary }.Concat(parts).ToArray());
        }
    }

    private static string FormatReason(string code) => code switch
    {
        "review_only" => "Không ghi được vào game (bỏ qua)",
        "mt_blocked" or "retranslate_blocked" => "Máy dịch không dịch được — cần tự dịch",
        "human_review" => "Bản dịch máy chờ bạn duyệt",
        "existing_translation_conflict" => "Game đã có bản dịch khác",
        "technical_control" => "Mã / định dạng của game (giữ nguyên)",
        "no_translation" => "Chưa có bản dịch",
        "garbage_repetition" => "Lặp từ/ký tự bất thường",
        "html_garbage" => "Có mã HTML thừa",
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
    public static PatchPreflightResult Run(string? csvPath, string? manifestPath, bool partialOverride = false)
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
            return PatchPreflightResult.Fail(csv, "Thiếu tệp đi kèm manifest.json cùng thư mục");

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = WorkerPaths.PythonExecutable(),
                Arguments = $"-m vntext.patch_gate --json {(partialOverride ? "--partial-override " : "")}\"{csv}\" \"{manifest}\"",
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
                return PatchPreflightResult.Fail(csv, "Không khởi chạy được bộ xử lý nền");

            var stdout = proc.StandardOutput.ReadToEnd();
            var stderr = proc.StandardError.ReadToEnd();
            proc.WaitForExit(TimeSpan.FromMinutes(2));

            if (proc.ExitCode != 0 && string.IsNullOrWhiteSpace(stdout))
                return PatchPreflightResult.Fail(csv, string.IsNullOrWhiteSpace(stderr) ? "Kiểm tra bản Việt hóa thất bại" : stderr.Trim());

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
                manifest,
                Items: ReadItems(root),
                ItemsTruncated: root.TryGetProperty("items_truncated", out var itEl) && itEl.ValueKind == JsonValueKind.True,
                UserExcluded: root.TryGetProperty("user_excluded", out var ueEl) && ueEl.TryGetInt32(out var ue) ? ue : 0,
                OutsideCsvReview: root.TryGetProperty("outside_csv_review", out var ocEl) && ocEl.TryGetInt32(out var oc) ? oc : 0);
        }
        catch (Exception ex)
        {
            return PatchPreflightResult.Fail(csv, UiText.Msg("Lỗi kiểm tra bản Việt hóa: {0}", ex.Message));
        }
    }

    private static List<PatchSkippedItem> ReadItems(JsonElement root)
    {
        var items = new List<PatchSkippedItem>();
        if (!root.TryGetProperty("items", out var el) || el.ValueKind != JsonValueKind.Array) return items;
        static string Str(JsonElement item, string name) => item.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() ?? "" : "";
        foreach (var item in el.EnumerateArray())
            items.Add(new PatchSkippedItem(Str(item, "key"), Str(item, "source_text"), Str(item, "translation"), Str(item, "reason"), Str(item, "label"), Str(item, "action")));
        return items;
    }
}
