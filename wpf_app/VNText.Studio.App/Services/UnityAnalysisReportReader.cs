using System.IO;
using System.Text.Json;
using VNText.PatchInstaller;

namespace VNText.Studio.App.Services;

public sealed record UnityAnalysisReportSnapshot(
    string UnityStatus,
    bool InventoryComplete,
    int ResourceCount,
    int TextCandidateCount,
    int PatchableCount,
    int ExtractOnlyCount,
    int ReviewRequiredCount,
    int UnsupportedCount,
    int UnknownCount,
    int ScanErrorCount,
    string ReportPath)
{
    public int ReviewRiskCount => ReviewRequiredCount + UnsupportedCount;

    /// <summary>Engine as classified by the worker during this scan ("RENPY_LOOSE_SOURCE", "UNITY", ...); empty for reports written by older versions.</summary>
    public string EngineDetection { get; init; } = "";
    public string EngineDetectionReason { get; init; } = "";
    public bool HasRenpyAssets { get; init; }
    public string TimingsText { get; init; } = "";

    /// <summary>Plain-language font / image inventory lines for a Ren'Py folder (empty for other engines).</summary>
    public IReadOnlyList<string> AssetLines { get; init; } = Array.Empty<string>();
}

public static class UnityAnalysisReportReader
{
    public static UnityAnalysisReportSnapshot? TryRead(string reportPath, out string? error)
    {
        error = null;
        try
        {
            using var document = JsonDocument.Parse(File.ReadAllText(reportPath));
            var root = document.RootElement;
            var unity = GetObject(root, "unity");
            var summary = GetObject(root, "summary");
            var coverage = GetObject(root, "coverage");
            var scanErrors = root.TryGetProperty("scan_errors", out var errors)
                && errors.ValueKind == JsonValueKind.Array
                ? errors.GetArrayLength()
                : GetInt(summary, "scan_error_count");

            return new UnityAnalysisReportSnapshot(
                GetString(unity, "status", "NOT_DETECTED"),
                GetBool(root, "inventory_complete"),
                GetInt(summary, "resource_count"),
                GetInt(coverage, "text_candidates"),
                GetInt(coverage, "patchable_text"),
                GetInt(coverage, "extract_only_text"),
                GetInt(coverage, "review_required"),
                GetInt(coverage, "unsupported"),
                GetInt(summary, "unknown_resources"),
                scanErrors,
                reportPath)
            {
                AssetLines = root.TryGetProperty("renpy_assets", out var assets) ? AssetInventoryPresentation.FromScan(assets) : Array.Empty<string>(),
                HasRenpyAssets = root.TryGetProperty("renpy_assets", out var renpyAssets) && renpyAssets.ValueKind == JsonValueKind.Object,
                EngineDetection = GetString(GetObject(root, "engine_detection"), "engine", ""),
                EngineDetectionReason = GetString(GetObject(root, "engine_detection"), "reason", ""),
                TimingsText = root.TryGetProperty("timings_seconds", out var timings) && timings.ValueKind == JsonValueKind.Object
                    ? string.Join(", ", timings.EnumerateObject().Select(item => $"{item.Name}={item.Value}")) : "",
            };
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException)
        {
            error = ex.Message;
            return null;
        }
    }

    private static JsonElement GetObject(JsonElement root, string property)
    {
        return root.TryGetProperty(property, out var value) && value.ValueKind == JsonValueKind.Object
            ? value
            : default;
    }

    private static string GetString(JsonElement root, string property, string fallback)
    {
        return root.ValueKind == JsonValueKind.Object
            && root.TryGetProperty(property, out var value)
            && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? fallback
            : fallback;
    }

    private static int GetInt(JsonElement root, string property)
    {
        return root.ValueKind == JsonValueKind.Object
            && root.TryGetProperty(property, out var value)
            && value.TryGetInt32(out var number)
            ? Math.Max(0, number)
            : 0;
    }

    private static bool GetBool(JsonElement root, string property)
    {
        return root.ValueKind == JsonValueKind.Object
            && root.TryGetProperty(property, out var value)
            && value.ValueKind is JsonValueKind.True or JsonValueKind.False
            && value.GetBoolean();
    }
}
