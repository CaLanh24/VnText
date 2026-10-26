using System.IO;
using System.Text.Json;

namespace VNText.Studio.App.Services;

/// <summary>Reads the OCR report that Extract writes under <c>images/</c> (bounded, read-only).</summary>
public static class ImagePackageProbe
{
    public readonly record struct Summary(int Total, int OcrReady, int TranslatedDrafts);

    public static Summary Read(string? packageDir)
    {
        if (string.IsNullOrWhiteSpace(packageDir)) return default;
        try
        {
            var images = Path.Combine(packageDir, "images");
            if (!Directory.Exists(images)) return default;
            // Extract writes images/report.json; a retry writes images/retry-*/report.json. Newest wins.
            var reports = new List<string>();
            var first = Path.Combine(images, "report.json");
            if (File.Exists(first)) reports.Add(first);
            foreach (var retry in Directory.EnumerateDirectories(images, "retry-*"))
            {
                var candidate = Path.Combine(retry, "report.json");
                if (File.Exists(candidate)) reports.Add(candidate);
            }
            var latest = reports.OrderByDescending(File.GetLastWriteTimeUtc).FirstOrDefault();
            if (latest is null || new FileInfo(latest).Length > 4 * 1024 * 1024) return default;
            using var doc = JsonDocument.Parse(File.ReadAllText(latest));
            if (!doc.RootElement.TryGetProperty("items", out var items) || items.ValueKind != JsonValueKind.Array) return default;
            int total = 0, ready = 0, drafts = 0;
            foreach (var item in items.EnumerateArray())
            {
                total++;
                var status = item.TryGetProperty("status", out var s) ? s.GetString() : "";
                if (status == "OCR_READY") ready++;
                else if (status == "TRANSLATED_DRAFT") drafts++;
            }
            return new Summary(total, ready, drafts);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException)
        {
            return default;
        }
    }
}
