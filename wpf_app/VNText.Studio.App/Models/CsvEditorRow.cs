using System.ComponentModel;
using VNText.Studio.App.Services;
using System.Runtime.CompilerServices;

namespace VNText.Studio.App.Models;

public sealed class CsvEditorRow : INotifyPropertyChanged
{
    private string _translation = "";
    private string _issueLabel = "";
    private string _issueDisplay = "";

    public int Index { get; init; }
    public string Key { get; init; } = "";
    public string SourceText { get; init; } = "";
    public bool IsReviewOnly { get; init; }
    public Dictionary<string, string> RawFields { get; init; } = new(StringComparer.OrdinalIgnoreCase);

    public string Translation
    {
        get => _translation;
        set
        {
            if (_translation == value) return;
            _translation = value ?? "";
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(Translation)));
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IsEmpty)));
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(HasIssue)));
        }
    }

    public string IssueLabel
    {
        get => _issueLabel;
        set
        {
            if (_issueLabel == value) return;
            _issueLabel = value ?? "";
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IssueLabel)));
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(HasIssue)));
        }
    }

    public string IssueDisplay
    {
        get => _issueDisplay;
        set
        {
            if (_issueDisplay == value) return;
            _issueDisplay = value ?? "";
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IssueDisplay)));
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IssueShort)));
        }
    }

    /// <summary>Short status label for the narrow column; the full diagnostic stays in <see cref="IssueDisplay"/> (tooltip, accessible help text).
    /// Only the known long labels are shortened; any other text is passed through unchanged (the column trims it with an ellipsis).</summary>
    public string IssueShort => UiText.TranslateDynamic(ShortenIssue(_issueDisplay));

    internal static string ShortenIssue(string display) => display switch
    {
        "Mất/sai placeholder {…}" => "Sai placeholder",
        "Hỏng tag <…>" => "Sai tag",
        "Trong review_only.csv (cần xem lại thủ công)" => "Cần xem lại",
        "Rác lặp từ/ký tự" => "Rác lặp",
        "HTML/entity rác" => "HTML rác",
        "Dòng synonym — dịch thủ công" => "Synonym thủ công",
        // The internal reason code is for diagnostics (tooltip/report/disk); the column says what it means to the person.
        "technical_control" => "Mã/định dạng game",
        _ => display,
    };

    public void SetIssueSilent(string label, string display)
    {
        _issueLabel = label ?? "";
        _issueDisplay = display ?? "";
    }

    internal void RaiseLanguageText() => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IssueShort)));

    public void NotifyIssueProperties()
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IssueLabel)));
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IssueDisplay)));
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IssueShort)));
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(HasIssue)));
    }

    public bool IsEmpty => string.IsNullOrWhiteSpace(Translation);
    public bool HasIssue => !string.IsNullOrWhiteSpace(IssueLabel) && IssueLabel != "no_translation";

    public event PropertyChangedEventHandler? PropertyChanged;

    public Dictionary<string, string> ToSaveRow(IReadOnlyList<string> fields)
    {
        var row = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (var field in fields)
            row[field] = RawFields.TryGetValue(field, out var v) ? v : "";
        row["translation"] = Translation;
        return row;
    }
}
