using System.ComponentModel;
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
        }
    }

    public void SetIssueSilent(string label, string display)
    {
        _issueLabel = label ?? "";
        _issueDisplay = display ?? "";
    }

    public void NotifyIssueProperties()
    {
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IssueLabel)));
        PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IssueDisplay)));
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
