using System.ComponentModel;
using VNText.Studio.App.Services;
using System.Runtime.CompilerServices;

namespace VNText.Studio.App.Models;

public sealed class CsvEditorRow : INotifyPropertyChanged
{
    private string _translation = "";
    private string _issueLabel = "";
    private string _issueDisplay = "";

    private bool _isSelected;
    /// <summary>Checkbox selection for batch actions; independent of the grid focus/highlight.</summary>
    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (_isSelected == value) return;
            _isSelected = value;
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IsSelected)));
            SelectionChanged?.Invoke(value);
        }
    }
    public static event Action<bool>? SelectionChanged;

    public int Index { get; init; }
    public string Key { get; init; } = "";
    public string SourceText { get; init; } = "";
    private bool _isReviewOnly;
    /// <summary>In the review ledger NOW.  Refreshed by every validation (a save that resolves a row removes it from the ledger; the flag read at
    /// load must not keep the old "review" status - Owner report 0.1.35).</summary>
    public bool IsReviewOnly
    {
        get => _isReviewOnly;
        set { if (_isReviewOnly == value) return; _isReviewOnly = value; PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IsReviewOnly))); }
    }
    /// <summary>What the person can do about the current status (empty when there is nothing to do).</summary>
    public string IssueAction { get; set; } = "";
    /// <summary>Machine translation waiting for a human decision ("Chấp nhận đề xuất"), when there is one.</summary>
    public string ReviewCandidate { get; set; } = "";
    public bool? CanTranslate { get; init; }
    public bool IsTechnical { get; init; }
    public string TranslationSkipReason { get; init; } = "";
    public bool NeedsTranslation => IsEmpty && !IsTechnical;
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
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(IssueShort)));
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
    public string IssueShort => IsTechnical && IsEmpty ? UiText.Translate("Không cần dịch")
        : string.IsNullOrWhiteSpace(_issueLabel) || _issueLabel == "no_translation"
        ? UiText.Translate(IsEmpty ? "Chưa dịch" : "Đã dịch")
        : IsEmpty || _issueDisplay == "Mất/sai placeholder {…}" ? UiText.TranslateDynamic(ShortenIssue(_issueDisplay))
        : UiText.Translate("Đã dịch") + " · " + UiText.TranslateDynamic(ShortenIssue(_issueDisplay));

    internal static string ShortenIssue(string display) => display switch
    {
        "Mất/sai placeholder {…}" => "Sai placeholder",
        "Hỏng tag <…>" => "Sai tag",
        "Trong review_only.csv (cần xem lại thủ công)" => "Cần xem lại",
        "Không ghi được vào game: chưa tìm được vị trí ghi an toàn cho dòng này, nên Tạo patch sẽ bỏ qua (bản dịch vẫn được lưu)" => "Không ghi được vào game",
        "Máy dịch không cho ra bản dịch an toàn cho dòng này; cần tự dịch" => "Cần tự dịch",
        "Bản dịch máy đang chờ bạn duyệt" => "Chờ duyệt",
        "Đã dịch — bấm Lưu để đưa dòng này vào patch" => "Bấm Lưu",
        "Game đã có bản dịch tiếng Việt khác cho câu này" => "Game đã có bản dịch",
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
    /// <summary>Tạo patch will leave this row out (same rule as the patch list): untranslated human text, or any status other than "ready".</summary>
    public bool SkippedByPatch => !IsTechnical && (IsEmpty || (HasIssue && IssueLabel != "review_resolved_unsaved"));
    public bool HasIssue => !IsTechnical && !string.IsNullOrWhiteSpace(IssueLabel) && IssueLabel != "no_translation";

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
