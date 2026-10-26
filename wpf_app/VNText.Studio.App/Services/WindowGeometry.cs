using System.Windows;

namespace VNText.Studio.App.Services;

/// <summary>
/// Keeps the restored (non-maximized) main window inside the logical work area.  Design size 1440x920 and minimum
/// 1040x720 apply only while they fit; on smaller or high-DPI (fewer logical pixels) work areas the minimum shrinks to
/// the area and the window never extends past the taskbar or the screen edge.  The OS scale and settings are never changed.
/// </summary>
internal static class WindowGeometry
{
    internal const double DesignWidth = 1440, DesignHeight = 920, DesignMinWidth = 1040, DesignMinHeight = 720;

    internal readonly record struct Fit(double Width, double Height, double MinWidth, double MinHeight, double Left, double Top);

    /// <param name="area">Logical (DIP) work area; an invalid area falls back to the design size at the origin.</param>
    /// <param name="left">Requested left or NaN/null to centre.</param>
    internal static Fit Compute(double desiredWidth, double desiredHeight, double? left, double? top, Rect area)
    {
        var usable = area.Width > 0 && area.Height > 0 && double.IsFinite(area.Width) && double.IsFinite(area.Height)
                     && double.IsFinite(area.Left) && double.IsFinite(area.Top);
        if (!usable)
            return new Fit(DesignWidth, DesignHeight, DesignMinWidth, DesignMinHeight, 0, 0);
        var minWidth = Math.Min(DesignMinWidth, area.Width);
        var minHeight = Math.Min(DesignMinHeight, area.Height);
        var width = Math.Clamp(Positive(desiredWidth, DesignWidth), minWidth, area.Width);
        var height = Math.Clamp(Positive(desiredHeight, DesignHeight), minHeight, area.Height);
        var x = left is { } l && double.IsFinite(l) ? l : area.Left + (area.Width - width) / 2;
        var y = top is { } t && double.IsFinite(t) ? t : area.Top + (area.Height - height) / 2;
        x = Math.Clamp(x, area.Left, Math.Max(area.Left, area.Right - width));
        y = Math.Clamp(y, area.Top, Math.Max(area.Top, area.Bottom - height));
        return new Fit(width, height, minWidth, minHeight, x, y);
    }

    private static double Positive(double value, double fallback) => double.IsFinite(value) && value > 0 ? value : fallback;

    internal static void Apply(Window window, Fit fit)
    {
        window.MinWidth = fit.MinWidth;
        window.MinHeight = fit.MinHeight;
        window.Width = fit.Width;
        window.Height = fit.Height;
        window.WindowStartupLocation = WindowStartupLocation.Manual;
        window.Left = fit.Left;
        window.Top = fit.Top;
    }
}
