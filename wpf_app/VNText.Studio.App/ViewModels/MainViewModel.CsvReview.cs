using System.IO;
using System.Windows;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

/// <summary>
/// Owner report (0.1.35): the editor had no way to check every untranslated row at once, and a "Cần xem lại" row showed a status with no
/// reason a person understands and no way out.  This part adds one-click selections (untranslated / needs review) and, for the row in focus,
/// its reason in plain Vietnamese with the actions that resolve it: accept the machine proposal, edit the translation, or skip (remove) the row.
/// Every action goes through the existing conflict-checked save/remove paths, and the counts refresh from the review ledger afterwards.
/// </summary>
public sealed partial class MainViewModel
{
    public RelayCommand CsvSelectUntranslatedCommand { get; private set; } = null!;
    public RelayCommand CsvSelectReviewCommand { get; private set; } = null!;
    public RelayCommand CsvAcceptCandidateCommand { get; private set; } = null!;
    public RelayCommand CsvEditFocusedCommand { get; private set; } = null!;
    public RelayCommand CsvSkipFocusedCommand { get; private set; } = null!;

    /// <summary>Raised to ask the window to start editing the translation cell of the focused row.</summary>
    public event Action<CsvEditorRow>? CsvEditFocusedRequested;

    private void InitCsvReview()
    {
        CsvSelectUntranslatedCommand = new RelayCommand(_ => SelectCsvRows(row => row.NeedsTranslation, CsvFilterModes.Untranslated, "chưa dịch"),
            _ => CanRunCsvBatchAction(allowDirty: true));
        CsvSelectReviewCommand = new RelayCommand(_ => SelectCsvRows(IsCsvReviewRow, CsvFilterModes.ReviewOnly, "cần xem lại"),
            _ => CanRunCsvBatchAction(allowDirty: true));
        CsvAcceptCandidateCommand = new RelayCommand(_ => _ = AcceptFocusedCandidateAsync(), _ => FocusedCsvRow is { } row && !string.IsNullOrWhiteSpace(row.ReviewCandidate) && CanRunCsvBatchAction(allowDirty: true));
        CsvEditFocusedCommand = new RelayCommand(_ => { if (FocusedCsvRow is { } row) CsvEditFocusedRequested?.Invoke(row); }, _ => FocusedCsvRow is not null && !CsvEditorGridReadOnly);
        CsvSkipFocusedCommand = new RelayCommand(_ => _ = SkipFocusedRowAsync(), _ => FocusedCsvRow is not null && CanRunCsvBatchAction(allowDirty: true));
        PropertyChanged += (_, e) =>
        {
            if (e.PropertyName is nameof(Busy) or nameof(CsvEditorLoading) or nameof(CsvEditorSaving) or nameof(CsvEditorPath) or nameof(CsvEditorGateStats))
                RaiseCsvFocusedIssue();
        };
    }

    /// <summary>A row the "Cần xem lại" count includes (same rule as the footer count).</summary>
    internal static bool IsCsvReviewRow(CsvEditorRow row) => !row.IsTechnical && (row.HasIssue || row.IsReviewOnly);

    /// <summary>Check every row of the document that matches, show them with the matching filter, and say how many were checked.</summary>
    internal void SelectCsvRows(Func<CsvEditorRow, bool> match, string filterMode, string what)
    {
        _suppressCheckedEvents = true;
        var count = 0;
        try
        {
            foreach (var row in _csvEditorRows)
            {
                row.IsSelected = match(row);
                if (row.IsSelected) count++;
            }
        }
        finally { _suppressCheckedEvents = false; }
        CsvEditorSearch = "";
        CsvFilterMode = filterMode;
        RecountChecked();
        ShowToast(count == 0 ? UiText.Msg("Không có dòng {0}.", UiText.Translate(what)) : UiText.Msg("Đã chọn {0} dòng {1}.", count.ToString("N0"), UiText.Translate(what)), "info", playSound: false);
    }

    internal CsvEditorRow? FocusedCsvRow => _csvEditorSelectedKeys.Count == 1
        ? _csvEditorRows.FirstOrDefault(row => string.Equals(row.Key, _csvEditorSelectedKeys[0], StringComparison.OrdinalIgnoreCase))
        : null;

    public bool CsvFocusedIssueVisible => FocusedCsvRow is { } row && !row.IsTechnical && (row.HasIssue || row.IsEmpty);

    public string CsvFocusedIssueReason => FocusedCsvRow is not { } row ? ""
        : row.HasIssue ? UiText.Msg("Lý do: {0}", UiText.TranslateDynamic(string.IsNullOrWhiteSpace(row.IssueDisplay) ? row.IssueLabel : row.IssueDisplay))
        : row.IsEmpty ? UiText.Translate("Lý do: dòng này chưa có bản dịch nên bản Việt hóa sẽ bỏ qua.")
        : "";

    public string CsvFocusedIssueAction => FocusedCsvRow is not { } row ? ""
        : UiText.Msg("Cách xử lý: {0}", UiText.TranslateDynamic(!string.IsNullOrWhiteSpace(row.IssueAction) ? row.IssueAction
            : row.IsEmpty ? "Dịch dòng này (tích chọn rồi 'Dịch đã chọn', hoặc gõ bản dịch) rồi bấm Lưu."
            : "Sửa bản dịch cho đúng rồi bấm Lưu; hoặc 'Bỏ qua dòng này' nếu không cần dịch."));

    public string CsvFocusedCandidate => FocusedCsvRow is { } row && !string.IsNullOrWhiteSpace(row.ReviewCandidate)
        ? UiText.Msg("Đề xuất của máy: {0}", row.ReviewCandidate) : "";
    public bool CsvFocusedHasCandidate => FocusedCsvRow is { } row && !string.IsNullOrWhiteSpace(row.ReviewCandidate);

    internal void RaiseCsvFocusedIssue()
    {
        Raise(nameof(CsvFocusedIssueVisible)); Raise(nameof(CsvFocusedIssueReason)); Raise(nameof(CsvFocusedIssueAction));
        Raise(nameof(CsvFocusedCandidate)); Raise(nameof(CsvFocusedHasCandidate));
        CsvAcceptCandidateCommand?.RaiseCanExecuteChanged(); CsvEditFocusedCommand?.RaiseCanExecuteChanged(); CsvSkipFocusedCommand?.RaiseCanExecuteChanged();
        CsvSelectUntranslatedCommand?.RaiseCanExecuteChanged(); CsvSelectReviewCommand?.RaiseCanExecuteChanged();
    }

    /// <summary>"Chấp nhận đề xuất": the machine proposal becomes the translation and is saved at once; the save's own check removes the row
    /// from the review ledger only when the text passes every patch check (a proposal that does not stays in review, with its real reason).</summary>
    internal async Task AcceptFocusedCandidateAsync()
    {
        if (FocusedCsvRow is not { } row || string.IsNullOrWhiteSpace(row.ReviewCandidate)) return;
        row.Translation = row.ReviewCandidate;
        MarkCsvEditorDirty();
        if (await SaveCsvEditorAsync())
            AppendLog(UiText.Msg("Đã chấp nhận đề xuất của máy cho dòng {0} và lưu CSV.", row.Key));
        RaiseCsvFocusedIssue();
    }

    /// <summary>"Bỏ qua dòng này": the same conflict-checked removal as "Xóa đã chọn", for the focused row only.</summary>
    internal async Task SkipFocusedRowAsync()
    {
        if (FocusedCsvRow is not { } row) return;
        if (CsvEditorMessageBox(UiText.Lines(
                "Bỏ qua dòng này? Dòng sẽ được xóa khỏi bản dịch: không dịch, không đưa vào bản Việt hóa, và không hiện lại khi lấy text lại.",
                "Game gốc không bị thay đổi; quyết định được ghi trong user_exclusions.json."),
                "Bỏ qua dòng này", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;
        if (!await EnsureCsvSavedBeforeBatchAsync("Bản dịch có thay đổi chưa lưu. Lưu trước khi bỏ qua dòng này?")) return;
        if (string.IsNullOrWhiteSpace(_csvEditorSourceSha256) || !File.Exists(CsvEditorPath))
        {
            ShowToast("Không xác minh được bản bản dịch đang mở; hãy tải lại bản dịch rồi chọn lại.", "error");
            return;
        }
        var result = TranslationCsvEditorService.ExcludeRows(CsvEditorPath, new[] { row.Key }, _csvEditorSourceSha256!);
        if (!result.Ok)
        {
            ShowToast(result.Error ?? "Không bỏ qua được dòng.", "error");
            AppendLog("Bỏ qua dòng thất bại: " + result.Error, "WARN");
            return;
        }
        AppendLog(UiText.Msg("Đã bỏ qua (xóa) dòng {0} khỏi bản dịch (ghi trong user_exclusions.json).", row.Key));
        ShowToast(UiText.Msg("Đã bỏ qua dòng; còn {0} dòng.", result.Remaining.ToString("N0")), "success");
        CsvEditorDirty = false;
        LoadCsvEditor(CsvEditorPath, reload: true);
        if (SameCsvPath(TranslationCsvPath, CsvEditorPath))
            InvalidatePatchSourceState(csvRevisionChanged: true, keepCsvValidation: true);
        RefreshWorkflow();
        RefreshTranslateReadiness();
        RaiseSafeSubsetPatch();
    }
}
