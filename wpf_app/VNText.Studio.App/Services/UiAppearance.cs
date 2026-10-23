using System.Windows;
using System.Windows.Media;
using Microsoft.Win32;

namespace VNText.Studio.App.Services;

public static class UiAppearance
{
    private static ResourceDictionary? _overrides;
    private static readonly Dictionary<string, Brush> Original = new();
    public static bool IsDark(string theme)
    {
        if (theme != "system") return theme == "dark";
        try { using var key = Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"); return key?.GetValue("AppsUseLightTheme") is int n && n == 0; }
        catch { return false; }
    }
    public static void Apply(string theme, double strength)
    {
        var app = Application.Current;
        if (app is null) return;
        if (_overrides is null)
        {
            var tokens = app.Resources.MergedDictionaries.First();
            foreach (var key in tokens.Keys.OfType<string>())
                if (tokens[key] is Brush brush) Original[key] = brush.CloneCurrentValue();
            _overrides = new ResourceDictionary(); app.Resources.MergedDictionaries.Add(_overrides);
        }
        var dark = IsDark(theme);
        foreach (var (key, brush) in Original) _overrides[key] = brush.CloneCurrentValue();
        string C(string light, string night) => dark ? night : light;
        void Set(string key, string color) => _overrides![key] = new SolidColorBrush((Color)ColorConverter.ConvertFromString(color));
        foreach (var key in new[] { "InkBrush", "TextPrimaryBrush" }) Set(key, C("#111827", "#EDF1F7"));
        foreach (var key in new[] { "MutedBrush", "TextSecondaryBrush", "TextMutedBrush" }) Set(key, C("#4B5B71", "#B7C2D3"));
        Set("SoftTextBrush", C("#94A3B8", "#9AACC4"));
        foreach (var key in new[] { "SurfaceBrush", "WindowBrush" }) Set(key, C("#FFFFFF", "#202B3C"));
        foreach (var key in new[] { "FieldBackgroundBrush", "SubtlePanelBrush", "LogPanelBrush", "PillBackgroundBrush", "ProjectCardBrush", "TableHeaderBrush" }) Set(key, C("#F5F7FB", "#273448"));
        foreach (var key in new[] { "LineBrush", "BorderBrush", "CardBorderBrush", "CtrlBorderBrush" }) Set(key, C("#E5E7EB", "#3B4B63"));
        Set("SettingsPreferenceFieldBrush", C("#EEF2F7", "#273448"));
        Set("SettingsPreferenceBorderBrush", C("#D1D8E2", "#3B4B63"));
        Set("BlueSoftBrush", C("#E9F1FF", "#28436C"));
        Set("BlueBrush", C("#2868E8", "#8CB5FF"));
        _overrides["SettingsTitleBrush"] = new LinearGradientBrush(
            (Color)ColorConverter.ConvertFromString(C("#2563EB", "#8CB5FF")),
            (Color)ColorConverter.ConvertFromString(C("#089DB2", "#65D6E8")), 0);
        Set("NavActiveBackgroundBrush", C("#212563EB", "#2B4772"));
        Set("NavActiveForegroundBrush", C("#2454EE", "#8CB5FF"));
        Set("NavDividerBrush", C("#D0D6E3", "#3B4B63"));
        Set("NavHoverBrush", C("#0E000000", "#354258"));
        Set("SettingsRowHoverBrush", C("#F0F0F0", "#2A394F"));
        Set("GreenSoftBrush", C("#E6FAEF", "#173D32"));
        Set("GreenDarkBrush", C("#087C42", "#7BDEA7"));
        Set("GreenBrush", C("#16A34A", "#7BDEA7"));
        if (dark)
        {
            Set("DisabledBackgroundBrush", "#263247");
            Set("DisabledPrimaryBackgroundBrush", "#2C4265");
            Set("DisabledBorderBrush", "#39485E");
            Set("DisabledForegroundBrush", "#94A1B5");
            Set("ProgressTrackBrush", "#344258");
        }
        var factor = Math.Clamp(strength, 0, 100) / 100;
        Color Tone(string hex)
        {
            var source = (Color)ColorConverter.ConvertFromString(hex);
            var neutral = dark ? Color.FromRgb(18, 25, 38) : Colors.White;
            return Color.FromRgb((byte)(neutral.R + (source.R - neutral.R) * factor), (byte)(neutral.G + (source.G - neutral.G) * factor), (byte)(neutral.B + (source.B - neutral.B) * factor));
        }
        _overrides["SidebarBrush"] = new LinearGradientBrush(dark
            ? new GradientStopCollection { new(Tone("#1B283E"),0), new(Tone("#182437"),.55), new(Tone("#152031"),1) }
            : new GradientStopCollection { new(Tone("#DEE4F2"),0), new(Tone("#DEE4F2"),.2), new(Tone("#E1E6F2"),.28), new(Tone("#E9EEF4"),.9), new(Tone("#EAEFF5"),1) }, new Point(0,0), new Point(0,1));
        if (dark)
        {
            // Preserve the existing dark canvas; no dark reference was supplied.
            _overrides["WorkspaceCanvasBrush"] = new LinearGradientBrush(new GradientStopCollection {
                new(Tone("#19253A"), 0), new(Tone("#162335"), .52), new(Tone("#122D2D"), 1) }, new Point(0,0), new Point(1,1));
        }
        else
        {
            var rectangle = new RectangleGeometry(new Rect(0, 0, 1, 1));
            var drawing = new DrawingGroup();
            drawing.Children.Add(new GeometryDrawing(new SolidColorBrush(Tone("#EFF2F7")), null, rectangle));
            var upperLight = new LinearGradientBrush(new GradientStopCollection {
                new(Tone("#D3DBF2"), 0), new(Tone("#F3F3F4"), .48),
                new(Tone("#DFEEED"), .9), new(Tone("#E2EFEE"), 1) }, new Point(0,0), new Point(1,0));
            var fade = new LinearGradientBrush(new GradientStopCollection {
                new(Colors.White, 0), new(Colors.White, .207), new(Colors.Transparent, .828), new(Colors.Transparent, 1) }, new Point(0,0), new Point(0,1));
            var light = new DrawingGroup { OpacityMask = fade };
            light.Children.Add(new GeometryDrawing(upperLight, null, rectangle)); drawing.Children.Add(light);
            _overrides["WorkspaceCanvasBrush"] = new DrawingBrush(drawing) { Stretch = Stretch.Fill };
        }
    }
}
