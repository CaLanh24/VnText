using System.Text.RegularExpressions;

namespace VNText.Studio.App.Services;

/// <summary>
/// 0.1.37 (external UX review: "the app speaks like a programmer"): the plain-Vietnamese presentation of internal states.  Pure functions over the
/// raw strings the worker and the resource check produce; the raw text is never discarded, it stays in the log / "Xem chẩn đoán".
/// </summary>
public static class PlainLanguage
{
    public const string EngineMissingText = "Chưa cài bộ dịch Anh → Việt trên máy. Bấm “Cài bộ dịch” để cài (cần mạng một lần, khoảng 75 MB); game không bị thay đổi.";
    public const string EngineChecking = "Đang kiểm tra bộ dịch…";
    public const string EngineReady = "Bộ dịch đã sẵn sàng.";

    /// <summary>True when the raw model status says the translator (model or its runtime) is not usable on this machine.</summary>
    public static bool IsEngineMissing(string? raw)
    {
        var text = raw ?? "";
        return text.Contains("runtime CTranslate2", StringComparison.OrdinalIgnoreCase)
            || text.Contains("Model CTranslate2 chưa có", StringComparison.OrdinalIgnoreCase)
            || text.Contains("Chưa có mô hình dịch", StringComparison.OrdinalIgnoreCase)
            || (text.Contains("ctranslate2", StringComparison.OrdinalIgnoreCase)
                && (text.Contains("ModuleNotFoundError", StringComparison.Ordinal) || text.Contains("ImportError", StringComparison.Ordinal)
                    || text.Contains("DLL load failed", StringComparison.OrdinalIgnoreCase) || text.Contains("No module named", StringComparison.OrdinalIgnoreCase)));
    }

    /// <summary>The one-line status for the translator (Settings row and Translate page); unknown text is kept whole so a real failure is never hidden.</summary>
    public static string EngineStatus(string raw, string folder)
    {
        if (string.IsNullOrWhiteSpace(raw)) return EngineChecking;
        if (IsEngineMissing(raw)) return EngineMissingText;
        if (raw == "Model OPUS-MT INT8 sẵn sàng: " + folder || raw == "Mô hình dịch đã sẵn sàng.") return EngineReady;
        return raw;
    }

    /// <summary>Resource ids from resource-status.json → what the person knows them as.</summary>
    public static string ResourceName(string? id) => (id ?? "").Trim().ToLowerInvariant() switch
    {
        "model" => "bộ dịch",
        "renpy" => "công cụ cho game Ren’Py",
        "ocr" => "nhận diện chữ trong ảnh",
        "worker" or "python" => "bộ xử lý nền",
        var other => other,
    };

    /// <summary>"Thiếu 2 thành phần: bộ dịch, công cụ cho game Ren’Py" — each component once, no internal ids.</summary>
    public static string MissingSummary(IEnumerable<string?> missingIds)
    {
        var names = missingIds.Select(ResourceName).Where(n => n.Length > 0).Distinct(StringComparer.Ordinal).ToList();
        if (names.Count == 0) return "Đã đủ thành phần.";
        var mb = missingIds.Select(id => (id ?? "").Trim().ToLowerInvariant()).Distinct().Select(DownloadMegabytes).Sum();
        var size = mb > 0 ? $" Dung lượng tải khoảng {mb} MB." : "";
        return $"Thiếu {names.Count} thành phần: {string.Join(", ", names)}.{size}";
    }

    /// <summary>Measured public download sizes: the translator model folder is about 74 MB, the Ren’Py SDK archive is 155.5 MiB.  Windows OCR is a Windows language pack, not downloaded here.</summary>
    public static int DownloadMegabytes(string? id) => (id ?? "").Trim().ToLowerInvariant() switch { "model" => 75, "renpy" => 156, _ => 0 };

    public static string WorkerStatus(bool present) => present ? "Sẵn sàng" : "Thiếu bộ xử lý nền";

    /// <summary>"3 câu chưa dịch, 2 câu cần xem lại, 1 câu bị chặn": only the counts that are not zero; every part has its own English entry.</summary>
    public static string CountsPhrase(int pending, int review, int blocked, int translated = 0, bool sentenceStart = false)
    {
        var parts = new List<string>();
        if (translated > 0) parts.Add(sentenceStart ? UiText.Msg("Đã dịch {0} câu", translated) : UiText.Msg("đã dịch {0} câu", translated));
        if (pending > 0) parts.Add(UiText.Msg("{0} câu chưa dịch", pending));
        if (review > 0) parts.Add(UiText.Msg("{0} câu cần xem lại", review));
        if (blocked > 0) parts.Add(UiText.Msg("{0} câu bị chặn", blocked));
        return parts.Count == 0 ? UiText.Msg("không còn câu nào cần xử lý") : UiText.Join(", ", parts);
    }

    private static readonly Regex SavedStepLine = new(@"^(?<lead>\s*(?:\[[^\]]*\]\s*)?)── (?<step>[a-z][a-z0-9_]*) ──\s*$", RegexOptions.Compiled);
    private static readonly Regex SavedStepLabel = new(@"Bước: (?<step>[a-z][a-z0-9_]*)\b", RegexOptions.Compiled);

    /// <summary>A log line saved by an older run may still show an internal step name ("── stale ──"); it is mapped when it is SHOWN, the saved file is not touched.</summary>
    public static string DisplayLogLine(string line)
    {
        if (string.IsNullOrEmpty(line)) return line;
        var m = SavedStepLine.Match(line);
        if (m.Success) return m.Groups["lead"].Value + "── " + StepLabel(m.Groups["step"].Value) + " ──";
        return SavedStepLabel.Replace(line, x => "Bước: " + StepLabel(x.Groups["step"].Value));
    }

    private static readonly Regex InternalToken = new("^[a-z][a-z0-9_]*$", RegexOptions.Compiled);

    /// <summary>A worker step or run status that is still an internal token ("stale", "unity_hash"…) becomes ordinary words.</summary>
    public static string StepLabel(string? step)
    {
        var value = (step ?? "").Trim();
        if (value.Length == 0) return "Đang xử lý";
        return value switch
        {
            "stale" => "Kết quả cũ đã được bỏ",
            "extract_inventory_boundary" or "discovery_inventory" => "Đang đọc danh sách tệp của game",
            "unity_enumerate" => "Đang quét danh sách dữ liệu của game",
            "unity_classify" => "Đang phân loại dữ liệu của game",
            "unity_hash" => "Đang kiểm tra dữ liệu của game",
            "engine_detection" => "Đang nhận diện loại game",
            "asset_scan" => "Đang kiểm tra font và ảnh của game",
            "report_write" => "Đang ghi báo cáo",
            _ when InternalToken.IsMatch(value) => "Đang xử lý",
            _ => value,
        };
    }

    /// <summary>Text a user may read must not carry these developer terms (the regression scan in tests uses the same list).</summary>
    public static readonly string[] ForbiddenUserTokens =
    {
        "ModuleNotFoundError", "ImportError", "CTranslate2", "OPUS-MT", "INT8", "Traceback", "runtime", "Python worker",
        "review_only", "mt_blocked", "human_review", "retranslate_blocked", "bucket", "locator", "manifest",
        "ExtractRunInfo", "VNText.Studio.App", "── stale", "Bước: stale",
    };
}
