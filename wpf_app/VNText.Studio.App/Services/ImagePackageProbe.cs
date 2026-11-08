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
    public sealed record ImageResult(string Name, string ReviewPath, string DraftPath, string Status);
    public static IReadOnlyList<ImageResult> ReadResults(string packageDir)
    {
        var results = new List<ImageResult>();
        try
        {
            var root = Path.Combine(packageDir, "images");
            if (!Directory.Exists(root)) return results;
            var reports = new[] { Path.Combine(root, "report.json") }.Concat(
                Directory.EnumerateDirectories(root, "retry-*").Take(MaxRetryDirectories).Select(p => Path.Combine(p, "report.json")));
            var report = reports.Where(File.Exists).OrderByDescending(File.GetLastWriteTimeUtc).ThenBy(p => p, StringComparer.OrdinalIgnoreCase).FirstOrDefault();
            if (report is null || new FileInfo(report).Length > MaxReportBytes) return results;
            root = Path.GetDirectoryName(report)!;
            string SafePath(string relative)
            {
                if (string.IsNullOrEmpty(relative)) return "";
                var path = Path.GetFullPath(Path.Combine(root, relative));
                if (!path.StartsWith(Path.GetFullPath(root) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) return "";
                for (var part = new FileInfo(path) as FileSystemInfo; part is not null; part = part is FileInfo f ? f.Directory : ((DirectoryInfo)part).Parent)
                    if (part.Exists && (part.Attributes & FileAttributes.ReparsePoint) != 0) return "";
                return File.Exists(path) ? path : "";
            }
            using var doc = JsonDocument.Parse(File.ReadAllText(report));
            if (!doc.RootElement.TryGetProperty("items", out var items) || items.ValueKind != JsonValueKind.Array) return results;
            foreach (var item in items.EnumerateArray().Take(MaxItems))
            {
                if (item.ValueKind != JsonValueKind.Object || !item.TryGetProperty("text_detected", out var detected) || detected.ValueKind != JsonValueKind.True) continue;
                string S(string name) => item.TryGetProperty(name, out var p) && p.ValueKind == JsonValueKind.String ? p.GetString()! : "";
                results.Add(new ImageResult(Path.GetFileName(S("source")), SafePath(S("ocr_result")), SafePath(S("translated")),
                    S("status") == "TRANSLATED_DRAFT" ? "Đã dịch nháp" : "Cần dịch / xem lại"));
            }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException or ArgumentException) { }
        return results;
    }
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
                if (item.ValueKind != JsonValueKind.Object
                    || !item.TryGetProperty("status", out var status)
                    || status.ValueKind != JsonValueKind.String)
                    continue;
                var text = status.GetString();
                if (text == "NO_TEXT") continue;
                if (text is not ("OCR_READY" or "TRANSLATED_DRAFT")
                    && (!item.TryGetProperty("text_detected", out var detected) || detected.ValueKind != JsonValueKind.True)) continue;
                total++;
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
