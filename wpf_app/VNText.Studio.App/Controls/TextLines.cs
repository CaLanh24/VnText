using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace VNText.Studio.App.Controls;

/// <summary>Bounds a wrapping TextBlock to N lines of its own font (WPF has no MaxLines): MaxHeight follows the font, so any UI scale keeps whole lines and the ellipsis lands on the last allowed line.</summary>
public static class TextLines
{
    public static readonly DependencyProperty MaxProperty = DependencyProperty.RegisterAttached("Max", typeof(int), typeof(TextLines), new PropertyMetadata(0, (d, _) => Apply(d)));
    public static int GetMax(DependencyObject d) => (int)d.GetValue(MaxProperty);
    public static void SetMax(DependencyObject d, int value) => d.SetValue(MaxProperty, value);

    private static void Apply(DependencyObject d)
    {
        if (d is not TextBlock tb) return;
        tb.Loaded -= OnLoaded;
        tb.Loaded += OnLoaded;
        Update(tb);
    }

    private static void OnLoaded(object sender, RoutedEventArgs e) => Update((TextBlock)sender);

    private static void Update(TextBlock tb)
    {
        var lines = GetMax(tb);
        if (lines <= 0) { tb.ClearValue(FrameworkElement.MaxHeightProperty); return; }
        var line = double.IsNaN(tb.LineHeight) || tb.LineHeight <= 0 ? tb.FontFamily.LineSpacing * tb.FontSize : tb.LineHeight;
        tb.MaxHeight = System.Math.Ceiling(line * lines);
    }
}
