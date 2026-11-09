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
    // display then needs no guess from the wording.  Same reference-keyed idiom as UiText.ProducedMessages; only ERROR/WARN/SUCCESS are accepted.
    private static readonly ConditionalWeakTable<string, string> Explicit = new();
    public static string Mark(string line, string level)
    {
        if (level is not ("ERROR" or "WARN" or "SUCCESS")) return line;
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
            var level = stored.Groups[1].Value;
            if (level is "ERROR" or "WARN") return level;
            text = text[stored.Length..];
            text = Regex.Replace(text, @"^\[task [^\]]+\]\s*", "");
        }
        text = Regex.Replace(text, @"^\[\d\d:\d\d:\d\d\]\s*", "");
        if (Regex.IsMatch(text, @"^(?:\[(?:error|lỗi)\]|── Lỗi|Lỗi(?:\b|:)|Error(?:\b|:)|Không thể|Không đọc được|Không ghi được)", RegexOptions.IgnoreCase)) return "ERROR";
        if (Regex.IsMatch(text, @"^(?:\[(?:warning|cảnh báo)\]|Cảnh báo|Warning|Lấy text một phần|── Lấy text một phần)", RegexOptions.IgnoreCase)) return "WARN";
        if (Regex.IsMatch(text, @"^(?:\[success\]|CSV OK:|Extract xong|Dịch xong|Tạo patch xong|Đã hoàn tất|Hoàn tất(?:\b|:)|── Hoàn tất|Kiểm tra patch: [1-9]\d* hợp lệ, 0 bị chặn|Patch read-back PASS|Patch tại )", RegexOptions.IgnoreCase)) return "SUCCESS";
        return "INFO";
    }
    public object Convert(object value, Type targetType, object parameter, CultureInfo culture) => Severity(value as string);
    public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => throw new NotSupportedException();
}
