using System.Globalization;
using System.Windows;
using System.Windows.Data;

namespace VNText.Studio.App.Converters;

/// <summary>Visible only while the bound value is not null (e.g. a detail strip that follows the selected list item).</summary>
public sealed class NullToCollapsedConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture) => value is null ? Visibility.Collapsed : Visibility.Visible;

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) => Binding.DoNothing;
}
