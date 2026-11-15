using System.Globalization;
using System.Windows.Controls;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.Validation;

/// <summary>
/// Whole-number input for the region editor.  A value that is empty, not an integer or outside the range is REJECTED before it reaches the review model
/// (the model keeps its last valid number and nothing is coerced); the error content is an app message the field's error template localizes.
/// </summary>
public sealed class IntegerRangeRule : ValidationRule
{
  public int Minimum { get; set; }
  public int Maximum { get; set; } = int.MaxValue;

  public IntegerRangeRule() : base(ValidationStep.RawProposedValue, false) { }

  public override ValidationResult Validate(object? value, CultureInfo cultureInfo)
  {
    var text = (value as string)?.Trim() ?? "";
    if (!int.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out var number))
      return new ValidationResult(false, "Nhập số nguyên hợp lệ");
    if (number < Minimum || number > Maximum)
      return new ValidationResult(false, UiText.Msg("Nhập số nguyên từ {0} đến {1}", Minimum.ToString(CultureInfo.InvariantCulture), Maximum.ToString(CultureInfo.InvariantCulture)));
    return ValidationResult.ValidResult;
  }
}
