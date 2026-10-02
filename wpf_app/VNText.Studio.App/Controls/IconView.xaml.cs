using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace VNText.Studio.App.Controls;

public partial class IconView : UserControl
{
    public static readonly DependencyProperty IconProperty =
        DependencyProperty.Register(nameof(Icon), typeof(string), typeof(IconView),
            new PropertyMetadata("", OnVisualChanged));

    public static readonly DependencyProperty StrokeBrushProperty =
        DependencyProperty.Register(nameof(StrokeBrush), typeof(Brush), typeof(IconView),
            new PropertyMetadata(Brushes.Black, OnVisualChanged));

    public static readonly DependencyProperty FillBrushProperty =
        DependencyProperty.Register(nameof(FillBrush), typeof(Brush), typeof(IconView),
            new PropertyMetadata(Brushes.Transparent, OnVisualChanged));

    public static readonly DependencyProperty StrokeThicknessProperty =
        DependencyProperty.Register(nameof(StrokeThickness), typeof(double), typeof(IconView),
            new PropertyMetadata(1.6, OnVisualChanged));

    public IconView()
    {
        InitializeComponent();
        Loaded += (_, _) => ApplyIcon();
    }

    public string Icon
    {
        get => (string)GetValue(IconProperty);
        set => SetValue(IconProperty, value);
    }

    public Brush StrokeBrush
    {
        get => (Brush)GetValue(StrokeBrushProperty);
        set => SetValue(StrokeBrushProperty, value);
    }

    public Brush FillBrush
    {
        get => (Brush)GetValue(FillBrushProperty);
        set => SetValue(FillBrushProperty, value);
    }

    public double StrokeThickness
    {
        get => (double)GetValue(StrokeThicknessProperty);
        set => SetValue(StrokeThicknessProperty, value);
    }

    private static void OnVisualChanged(DependencyObject d, DependencyPropertyChangedEventArgs e)
    {
        if (d is IconView view)
            view.ApplyIcon();
    }

    private void ApplyIcon()
    {
        if (Glyph is null || string.IsNullOrEmpty(Icon))
            return;

        var spec = IconPaths.Get(Icon);
        Glyph.Data = spec.Geometry;
        if (spec.Filled)
        {
            Glyph.Fill = FillBrush;
            Glyph.Stroke = null;
            Glyph.StrokeThickness = 0;
        }
        else
        {
            Glyph.Fill = Brushes.Transparent;
            Glyph.Stroke = StrokeBrush;
            Glyph.StrokeThickness = StrokeThickness;
        }
    }
}
