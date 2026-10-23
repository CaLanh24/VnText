using System.Globalization;

namespace VNText.Studio.App.Services;

public static class ProgressEtaFormatter
{
    public static string Format(string? value)
    {
        if (!double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out var seconds)
            || !double.IsFinite(seconds) || seconds < 0)
            return "";
        var total = (long)Math.Round(seconds, MidpointRounding.AwayFromZero);
        if (total < 60) return $"{total} giây";
        var minutes = (total + 30) / 60;
        if (minutes < 60) return $"{minutes} phút";
        var hours = minutes / 60;
        var remaining = minutes % 60;
        return remaining == 0 ? $"{hours} giờ" : $"{hours} giờ {remaining} phút";
    }
}
