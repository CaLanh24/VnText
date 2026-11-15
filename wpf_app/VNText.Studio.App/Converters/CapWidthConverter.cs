using System.Globalization;
using System.Windows.Data;

namespace VNText.Studio.App.Converters;

/// <summary>Shared form-width cap: the available width up to <see cref="Max"/> DIP (NaN = automatic while nothing is measured yet), so a simple form keeps its left axis on a wide window.</summary>
public sealed class CapWidthConverter : IValueConverter
{
  public double Max { get; set; } = 1120;

  public object Convert(object value, Type targetType, object parameter, CultureInfo culture) =>
    value is double available && available > 0 ? Math.Min(available, Max) : double.NaN;

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => Binding.DoNothing;
}
