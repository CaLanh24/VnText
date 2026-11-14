using System.Globalization;
using System.Runtime.CompilerServices;
using System.Text.RegularExpressions;
using System.Windows.Data;

namespace VNText.Studio.App.Converters;

public sealed class LogSeverityConverter : IValueConverter
{
    // Only metadata / the beginning of an application message is classified.
    // A source sentence containing 'error' or 'ok' must not change its colour.
    // A producer that KNOWS its severity (CSV validation failure, patch preflight with omitted rows) marks the line instance it adds to the log;
    // display then needs no guess from the wording.  Same reference-keyed idiom as UiText.ProducedMessages; ERROR/WARN/SUCCESS/INFO/DEBUG are accepted
    // (a valid result or a timing line is INFO/DEBUG by its producer, never red because its wording contains the word "lỗi").
    private static readonly ConditionalWeakTable<string, string> Explicit = new();
    public static string Mark(string line, string level)
    {
        if (level is not ("ERROR" or "WARN" or "SUCCESS" or "INFO" or "DEBUG")) return line;
        var marked = new string(line.AsSpan());
        Explicit.Add(marked, level);
        return marked;
    }

    public static string Severity(string? line)
    {
        if (line is not null && Explicit.TryGetValue(line, out var explicitLevel)) return explicitLevel;
        var text = line ?? "";
        var stored = Regex.Match(text, @"^\S+ \S+ [+-]\d\d:\d\d (ERROR|WARN|INFO|DEBUG) ");
        if (stored.Success)
        {
            // The persisted level was decided by the producer: it is authoritative.  Only a known success headline may still brighten an INFO line.
            var level = stored.Groups[1].Value;
            if (level is "ERROR" or "WARN" or "DEBUG") return level;
            text = text[stored.Length..];
            text = Regex.Replace(text, @"^\[task [^\]]+\]\s*", "");
            return ClassifyText(text) == "SUCCESS" ? "SUCCESS" : "INFO";
        }
        return ClassifyText(text);
    }

    /// <summary>Anchored wording classification for a line whose producer gave no level.  Never a free substring search: a sentence that merely CONTAINS "error"/"lỗi" keeps INFO.</summary>
    public static string ClassifyText(string text)
    {
        text = Regex.Replace(text, @"^(?:\[(?:task [^\]]+|\d\d:\d\d:\d\d)\]\s*){1,2}", "");
        if (text.StartsWith("Unity analyzer:", StringComparison.Ordinal))
        {
            var scanErrors = Regex.Match(text, @";\s*scan_errors=(?<count>\d+)(?:\s|;|$)", RegexOptions.CultureInvariant);
            if (scanErrors.Success && int.TryParse(scanErrors.Groups["count"].Value, out var count) && count > 0) return "ERROR";
        }
        if (Regex.IsMatch(text, @"^(?:\[(?:error|lỗi)\]|── Lỗi|Lỗi(?:\b|:)|Error(?:\b|:)|Không thể|Không đọc được|Không ghi được)", RegexOptions.IgnoreCase)) return "ERROR";
        if (Regex.IsMatch(text, @"^(?:\[(?:warning|cảnh báo|stderr)\]|Cảnh báo|Warning|Lấy text một phần|── Lấy text một phần)", RegexOptions.IgnoreCase)) return "WARN";
        if (Regex.IsMatch(text, @"^(?:\[success\]|CSV OK:|Extract xong|Dịch xong|Tạo patch xong|Đã hoàn tất|Hoàn tất(?:\b|:)|── Hoàn tất|Kiểm tra patch: [1-9]\d* hợp lệ, 0 bị chặn|Patch read-back PASS|Patch tại )", RegexOptions.IgnoreCase)) return "SUCCESS";
        return "INFO";
    }
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture) => Severity(value as string);
    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotSupportedException();
}
