using System.Windows;
using System.Windows.Media;
using Microsoft.Win32;

namespace VNText.Studio.App.Services;

public static class UiAppearance
{
    /// <summary>Current interface scale (1, 1.1, 1.2). Owned windows follow it so a modal does not keep its own size rhythm.</summary>
    public static double Scale { get; set; } = 1;
    public static bool Scaled => Scale > 1.0001;
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
        foreach (var key in new[] { "LineBrush", "BorderBrush", "CardBorderBrush" }) Set(key, C("#E5E7EB", "#3B4B63"));
        // Control boundaries are separated from card/separator lines: idle inputs and outline buttons stay recognisable (>= 3:1 on their field surface).
        Set("CtrlBorderBrush", C("#7B8798", "#71829C"));
        Set("SettingsPreferenceFieldBrush", C("#EEF2F7", "#273448"));
        Set("InputIdleBorderBrush", C("#E2E3E5", "#394352"));
        Set("SelectIdleBorderBrush", C("#D3D7DE", "#445266"));
        Set("BlueSoftBrush", C("#E9F1FF", "#28436C"));
        Set("BlueBrush", C("#2868E8", "#8CB5FF"));
        _overrides["SettingsTitleBrush"] = new LinearGradientBrush(
            (Color)ColorConverter.ConvertFromString(C("#2563EB", "#8CB5FF")),
            (Color)ColorConverter.ConvertFromString(C("#089DB2", "#65D6E8")), 0);
        _overrides["PrimaryFillBrush"] = new LinearGradientBrush(
            (Color)ColorConverter.ConvertFromString(C("#2563EB", "#3264C8")),
            (Color)ColorConverter.ConvertFromString(C("#087C91", "#0E7490")), 0);
        _overrides["PrimaryFillHoverBrush"] = new LinearGradientBrush(
            (Color)ColorConverter.ConvertFromString(C("#1D4ED8", "#2855B0")),
            (Color)ColorConverter.ConvertFromString(C("#0E6F80", "#155E75")), 0);
        _overrides["PrimaryFillPressedBrush"] = new LinearGradientBrush(
            (Color)ColorConverter.ConvertFromString("#1E40AF"),
            (Color)ColorConverter.ConvertFromString("#155E75"), 0);
        Set("NavActiveBackgroundBrush", C("#212563EB", "#2B4772"));
        Set("NavActiveForegroundBrush", C("#2454EE", "#8CB5FF"));
        Set("NavDividerBrush", C("#D0D6E3", "#3B4B63"));
        Set("NavHoverBrush", C("#DFE7F2", "#354258"));
        Set("SettingsRowHoverBrush", C("#F0F5FC", "#2A394F"));
        Set("SecondaryButtonFillBrush", C("#FFFFFF", "#1E293B"));
        Set("SecondaryButtonEdgeBrush", C("#E2E3E5", "#394352"));
        Set("SecondaryButtonTextBrush", C("#475569", "#94A3B8"));
        Set("SecondaryButtonHoverFillBrush", C("#EEF2F7", "#334155"));
        Set("SecondaryButtonHoverEdgeBrush", C("#D3D7DE", "#4B5869"));
        Set("SecondaryButtonHoverTextBrush", C("#0F172A", "#F1F5F9"));
        _overrides["SecondaryElevation"] = new System.Windows.Media.Effects.DropShadowEffect { Color = Colors.Black, BlurRadius = 10, ShadowDepth = 2, Direction = 270, Opacity = dark ? 0 : 0.10 };
        Set("HoverSurfaceBrush", C("#F0F6FC", "#354258"));
        Set("HoverBorderBrush", C("#C5D7EC", "#5A7396"));
        Set("ToastInfoBackgroundBrush", C("#E9F1FF", "#28436C"));
        Set("ToastInfoForegroundBrush", C("#111827", "#EDF1F7"));
        Set("ToastInfoBorderBrush", C("#2868E8", "#8CB5FF"));
        Set("ToastSuccessBackgroundBrush", C("#E6FAEF", "#173D32"));
        Set("ToastSuccessForegroundBrush", C("#087C42", "#7BDEA7"));
        Set("ProgressFillBrush", C("#22C55E", "#4ADE80"));
        Set("ToastSuccessBorderBrush", C("#16A34A", "#7BDEA7"));
        Set("ToastWarningBackgroundBrush", C("#FFF4DF", "#4A3410"));
        Set("ToastWarningForegroundBrush", C("#111827", "#FFF1D6"));
        Set("ToastWarningBorderBrush", C("#B56D00", "#E0A33A"));
        Set("LogWarningForegroundBrush", C("#9A5B00", "#E0A33A"));
        Set("ToastErrorBackgroundBrush", C("#FFF0F0", "#4A1F24"));
        Set("ToastErrorForegroundBrush", C("#111827", "#FFE4E4"));
        Set("ToastErrorBorderBrush", C("#C84040", "#FF8A8A"));
        Set("GreenSoftBrush", C("#E6FAEF", "#173D32"));
        Set("GreenDarkBrush", C("#087C42", "#7BDEA7"));
        Set("GreenBrush", C("#16A34A", "#7BDEA7"));
        Set("AboutCurrentBackgroundBrush", C("#D8EDE1", "#173D32"));
        Set("AboutCurrentBorderBrush", C("#A1E2BA", "#418C63"));
        Set("AboutCurrentTextBrush", C("#22C55E", "#7BDEA7"));
        Set("SwitchOffTrackBrush", C("#CBD5E1", "#344258"));
        Set("SwitchOffBorderBrush", C("#B5C0D0", "#506078"));
        Set("SwitchOffKnobBrush", C("#FFFFFF", "#CBD5E1"));
        Set("SwitchOffHoverBrush", C("#BBC8D9", "#42536C"));
        Set("SwitchOnTrackBrush", C("#2563EB", "#3A74E8"));
        Set("SwitchOnKnobBrush", "#FFFFFF");
        Set("SwitchOffBrush", C("#CBD5E1", "#344258"));
        Set("InputErrorForegroundBrush", C("#B42318", "#FDA29B"));
        Set("InputErrorBorderBrush", C("#B42318", "#FDA29B"));
        Set("InputErrorSurfaceBrush", C("#FEF3F2", "#4A1F24"));
        // Disabled primary is neutral (not the selected/brand hue) so it never reads as a selected item.
        Set("DisabledPrimaryBackgroundBrush", C("#E7EBF1", "#2B3545"));
        Set("DisabledPrimaryBorderBrush", C("#D6DDE7", "#42506A"));
        Set("DisabledPrimaryForegroundBrush", C("#64748B", "#9AA7BA"));
        if (dark)
        {
            Set("DisabledBackgroundBrush", "#263247");
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
