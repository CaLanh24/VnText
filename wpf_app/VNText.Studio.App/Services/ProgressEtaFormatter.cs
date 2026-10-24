using System.Globalization;

namespace VNText.Studio.App.Services;

public static class ProgressEtaFormatter
{
    private const double MaxDisplaySeconds = 365d * 24 * 60 * 60;

    public static string Format(string? value)
    {
        if (!double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var seconds)
            || !double.IsFinite(seconds) || seconds < 0 || seconds > MaxDisplaySeconds)
            return "";
        var total = (long)Math.Round(seconds, MidpointRounding.AwayFromZero);
        if (total < 60) return $"{total} giây";
        var minutes = (total + 30) / 60;
        if (minutes < 60) return $"{minutes} phút";
        var hours = minutes / 60;
        var remaining = minutes % 60;
        var days = hours / 24;
        if (days > 0)
        {
            var remainingHours = hours % 24;
            var parts = new List<string> { $"{days} ngày" };
            if (remainingHours > 0) parts.Add($"{remainingHours} giờ");
            if (remaining > 0) parts.Add($"{remaining} phút");
            return string.Join(" ", parts);
        }
        return remaining == 0 ? $"{hours} giờ" : $"{hours} giờ {remaining} phút";
    }
}
