using System.Globalization;
using System.IO;
using System.Windows;
using System.Windows.Data;
using System.Windows.Media;

namespace VNText.Studio.App.Converters;

public sealed class StepStateToForegroundConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var state = value as string ?? "";
    return state is Services.WorkflowStepState.Current or Services.WorkflowStepState.Running
      ? Application.Current.Resources["AccentBrush"]
      : Application.Current.Resources["TextSecondaryBrush"];
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class StepStateToBackgroundConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var state = value as string ?? "";
    return state is Services.WorkflowStepState.Current or Services.WorkflowStepState.Running
      ? Application.Current.Resources["AccentSubtleBrush"]
      : Brushes.Transparent;
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class StepStateToDotBrushConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var state = value as string ?? "";
    return state switch
    {
      Services.WorkflowStepState.Done => Application.Current.Resources["SuccessBrush"],
      Services.WorkflowStepState.Current or Services.WorkflowStepState.Running =>
        Application.Current.Resources["AccentBrush"],
      _ => Application.Current.Resources["TextTerBrush"],
    };
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class StepStateToFontWeightConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var state = value as string ?? "";
    return state is Services.WorkflowStepState.Current or Services.WorkflowStepState.Running
      ? FontWeights.Medium
      : FontWeights.Normal;
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class StepStateToTitleForegroundConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var state = value as string ?? "";
    return state is Services.WorkflowStepState.Current or Services.WorkflowStepState.Running
      ? Application.Current.Resources["TextPrimaryBrush"]
      : Application.Current.Resources["TextSecondaryBrush"];
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class StepStateToDotRingVisibilityConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var state = value as string ?? "";
    return state is Services.WorkflowStepState.Pending
      ? Visibility.Visible
      : Visibility.Collapsed;
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class InverseBoolToVisibilityConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var visible = value is true;
    return visible ? Visibility.Collapsed : Visibility.Visible;
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class BoolToChevronIconConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture) =>
    value is true ? "chevron_up" : "chevron_down";

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class TabNotEqualsToVisibilityConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var selected = value as string ?? "";
    var tab = parameter as string ?? "";
    return string.Equals(selected, tab, StringComparison.OrdinalIgnoreCase)
      ? Visibility.Collapsed
      : Visibility.Visible;
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class TabEqualsToVisibilityConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var selected = value as string ?? "";
    var tab = parameter as string ?? "";
    return string.Equals(selected, tab, StringComparison.OrdinalIgnoreCase)
      ? Visibility.Visible
      : Visibility.Collapsed;
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class TabEqualsToBackgroundConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var selected = value as string ?? "";
    var tab = parameter as string ?? "";
    return string.Equals(selected, tab, StringComparison.OrdinalIgnoreCase)
      ? Application.Current.Resources["GreenSoftBrush"]
      : Brushes.Transparent;
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class BoolToPrimaryButtonStyleConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var green = value is true;
    var key = green ? "GuiPrimaryButtonStyle" : "GuiBluePrimaryButtonStyle";
    return Application.Current.Resources[key] as Style
      ?? Application.Current.Resources["GuiPrimaryButtonStyle"];
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class PathToDisplayNameConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var path = value as string ?? "";
    if (string.IsNullOrWhiteSpace(path))
      return "Chưa chọn game";
    try
    {
      var trimmed = path.Trim().Trim('"');
      if (File.Exists(trimmed))
        return Path.GetFileNameWithoutExtension(trimmed);
      var name = Path.GetFileName(trimmed.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar));
      return string.IsNullOrWhiteSpace(name) ? trimmed : name;
    }
    catch
    {
      return path;
    }
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class IntToPercentConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var n = value is int i ? i : 0;
    return $"{n}%";
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class LogStateTextConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    if (value is true)
      return "Đang chạy";
    return "Sẵn sàng";
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class CountZeroToVisibilityConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var count = value switch
    {
      int i => i,
      _ => 0,
    };
    return count == 0 ? Visibility.Visible : Visibility.Collapsed;
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class StringMatchConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var current = value as string ?? "";
    var expected = parameter as string ?? "";
    return string.Equals(current, expected, StringComparison.OrdinalIgnoreCase);
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture)
  {
    if (value is true)
      return parameter as string ?? "";
    return Binding.DoNothing;
  }
}

public sealed class TabEqualsToNavBackgroundConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var selected = value as string ?? "";
    var tab = parameter as string ?? "";
    return string.Equals(selected, tab, StringComparison.OrdinalIgnoreCase)
      ? Application.Current.Resources["NavActiveBackgroundBrush"]
      : Brushes.Transparent;
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class TabEqualsToNavForegroundConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var selected = value as string ?? "";
    var tab = parameter as string ?? "";
    return string.Equals(selected, tab, StringComparison.OrdinalIgnoreCase)
      ? Application.Current.Resources["BlueBrush"]
      : Application.Current.Resources["MutedBrush"];
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

public sealed class CountNonZeroToVisibilityConverter : IValueConverter
{
  public object Convert(object value, Type targetType, object parameter, CultureInfo culture)
  {
    var count = value switch
    {
      int i => i,
      _ => 0,
    };
    return count > 0 ? Visibility.Visible : Visibility.Collapsed;
  }

  public object ConvertBack(object value, Type targetType, object parameter, CultureInfo culture) =>
    throw new NotSupportedException();
}

/// <summary>Display-time localization of bound status text: Vietnamese passes through exactly, English maps known/dynamic app messages only (never user data).</summary>
public sealed class UiTextConverter : IValueConverter
{
    public object Convert(object value, Type targetType, object parameter, System.Globalization.CultureInfo culture) =>
        value is string text ? VNText.Studio.App.Services.UiText.TranslateDynamic(text) : value;
    public object ConvertBack(object value, Type targetType, object parameter, System.Globalization.CultureInfo culture) => throw new NotSupportedException();
}

/// <summary>The XAML carries the catalog FORMAT KEY (ConverterParameter, e.g. "Bước: {0}") and the bound value is the raw argument: the key is translated
/// first, then formatted with the argument as it is. Set <see cref="SemanticArgument"/> only when the bound value is itself a UI label/duration (a catalog key);
/// file names, paths and user text are bound with the default and are never looked up.</summary>
public sealed class UiTextFormatConverter : IValueConverter
{
    public bool SemanticArgument { get; set; }
    public object Convert(object value, Type targetType, object parameter, System.Globalization.CultureInfo culture) =>
        VNText.Studio.App.Services.UiText.Format(parameter as string ?? "{0}",
            SemanticArgument && value is string text ? VNText.Studio.App.Services.UiText.Key(text) : value);
    public object ConvertBack(object value, Type targetType, object parameter, System.Globalization.CultureInfo culture) => throw new NotSupportedException();
}
