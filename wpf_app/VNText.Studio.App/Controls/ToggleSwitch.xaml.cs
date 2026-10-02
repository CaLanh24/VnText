using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;

namespace VNText.Studio.App.Controls;

public partial class ToggleSwitch : UserControl
{
    public static readonly DependencyProperty IsOnProperty =
        DependencyProperty.Register(nameof(IsOn), typeof(bool), typeof(ToggleSwitch),
            new FrameworkPropertyMetadata(false, FrameworkPropertyMetadataOptions.BindsTwoWayByDefault, OnIsOnChanged));

    public bool IsOn
    {
        get => (bool)GetValue(IsOnProperty);
        set => SetValue(IsOnProperty, value);
    }

    public ToggleSwitch()
    {
        InitializeComponent();
        UpdateVisual();
    }

    private static void OnIsOnChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is ToggleSwitch sw)
            sw.UpdateVisual();
    }

    private void OnClick(object sender, MouseButtonEventArgs e)
    {
        IsOn = !IsOn;
    }

    private void UpdateVisual()
    {
        if (Track is null || Knob is null)
            return;
        Track.Background = IsOn
            ? (Brush)FindResource("AccentBrush")
            : (Brush)FindResource("SwitchOffBrush");
        Track.BorderThickness = IsOn ? new Thickness(0) : new Thickness(1);
        Knob.HorizontalAlignment = IsOn ? HorizontalAlignment.Right : HorizontalAlignment.Left;
        Knob.Margin = IsOn ? new Thickness(0, 0, 4, 0) : new Thickness(4, 0, 0, 0);
    }
}
