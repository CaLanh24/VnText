namespace VNText.Studio.App.Services;

/// <summary>A filter/scope choice: the stored Value never changes; the shown Label follows the display language (RefreshLabel after a switch).</summary>
public sealed class CsvFilterOption : System.ComponentModel.INotifyPropertyChanged
{
    private readonly string _viLabel;
    public CsvFilterOption(string value, string label) { Value = value; _viLabel = label; }
    public string Value { get; }
    public string Label => UiText.Translate(_viLabel);
    public event System.ComponentModel.PropertyChangedEventHandler? PropertyChanged;
    public void RefreshLabel() => PropertyChanged?.Invoke(this, new System.ComponentModel.PropertyChangedEventArgs(nameof(Label)));
}

public static class CsvFilterModes
{
    public const string All = "all";
    public const string Untranslated = "untranslated";
    public const string ReviewOnly = "review_only";
    public const string Errors = "errors";

    public static IReadOnlyList<CsvFilterOption> Options { get; } =
    [
        new(All, "Tất cả"),
        new(Untranslated, "Chưa dịch"),
        new(ReviewOnly, "Cần xem lại"),
        new(Errors, "Chỉ dòng lỗi"),
    ];
}
