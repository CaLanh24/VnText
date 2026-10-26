using System.IO;
using System.Text.Json;

namespace VNText.Studio.App.Services;

/// <summary>
/// Reads the OCR report that Extract writes under <c>images/</c>.  Read-only and bounded: at most
/// <see cref="MaxRetryDirectories"/> retry directories are examined, a report larger than
/// <see cref="MaxReportBytes"/> is ignored, and every JSON shape is validated by value kind so a
/// user-edited report can never throw into the UI.  Only expected I/O and parse failures are caught.
/// </summary>
public static class ImagePackageProbe
{
    public readonly record struct Summary(int Total, int OcrReady, int TranslatedDrafts);

    public const int MaxRetryDirectories = 64;
    public const long MaxReportBytes = 4L * 1024 * 1024;
    public const int MaxItems = 100_000;

    public static Summary Read(string? packageDir)
    {
        if (string.IsNullOrWhiteSpace(packageDir)) return default;
        try
        {
            var images = Path.Combine(packageDir, "images");
            if (!Directory.Exists(images)) return default;
            // Deterministic preference: the newest report by write time, ties broken by path.
            // Extract writes images/report.json; a retry writes images/retry-*/report.json.
            var reports = new List<string>();
            var first = Path.Combine(images, "report.json");
            if (File.Exists(first)) reports.Add(first);
            foreach (var retry in Directory.EnumerateDirectories(images, "retry-*").Take(MaxRetryDirectories))
            {
                var candidate = Path.Combine(retry, "report.json");
                if (File.Exists(candidate)) reports.Add(candidate);
            }
            var latest = reports
                .OrderByDescending(File.GetLastWriteTimeUtc)
                .ThenBy(path => path, StringComparer.OrdinalIgnoreCase)
                .FirstOrDefault();
            if (latest is null || new FileInfo(latest).Length > MaxReportBytes) return default;
            using var doc = JsonDocument.Parse(File.ReadAllText(latest));
            if (doc.RootElement.ValueKind != JsonValueKind.Object
                || !doc.RootElement.TryGetProperty("items", out var items)
                || items.ValueKind != JsonValueKind.Array)
                return default;
            int total = 0, ready = 0, drafts = 0;
            foreach (var item in items.EnumerateArray())
            {
                if (total >= MaxItems) break;
                total++;
                if (item.ValueKind != JsonValueKind.Object
                    || !item.TryGetProperty("status", out var status)
                    || status.ValueKind != JsonValueKind.String)
                    continue;
                var text = status.GetString();
                if (text == "OCR_READY") ready++;
                else if (text == "TRANSLATED_DRAFT") drafts++;
            }
            return new Summary(total, ready, drafts);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException)
        {
            return default;
        }
    }
}
