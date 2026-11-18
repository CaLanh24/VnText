using System.IO;
using System.Windows;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

/// <summary>
/// Row checkboxes of the CSV editor: a selection for batch actions that is independent of the grid focus/highlight.
/// Batch actions work on the SAME CSV: "Dịch dòng đã chọn" (existing offline OPUS-MT route, only the checked rows) and
/// "Xóa dòng đã chọn" (conflict-protected removal, recorded in user_exclusions.json so a re-extraction does not bring them back).
/// </summary>
public sealed partial class MainViewModel
{
    private int _csvCheckedCount;
    private bool _suppressCheckedEvents;
    private bool _csvSelectionPreparing;

    public int CsvCheckedCount => _csvCheckedCount;
    public bool CsvHasChecked => _csvCheckedCount > 0;
    public string CsvCheckedText => _csvCheckedCount == 0
        ? UiText.Translate("Chưa chọn dòng nào")
        : _csvCheckedCount == 1 ? UiText.Translate("Đã chọn 1 dòng")
        : UiText.Msg("Đã chọn {0} dòng", _csvCheckedCount.ToString("N0"));

    public RelayCommand CsvSelectAllFilteredCommand { get; private set; } = null!;
    public RelayCommand CsvSelectTranslatableCommand { get; private set; } = null!;
    public RelayCommand CsvClearCheckedCommand { get; private set; } = null!;
    public RelayCommand CsvTranslateCheckedCommand { get; private set; } = null!;
    public RelayCommand CsvDeleteCheckedCommand { get; private set; } = null!;

    private void InitCsvSelection()
    {
        CsvSelectAllFilteredCommand = new RelayCommand(_ => SetCheckedForFiltered(true), _ => CanRunCsvBatchAction(allowDirty: true));
        CsvSelectTranslatableCommand = new RelayCommand(_ => _ = SelectTranslatableAsync(), _ => !Busy && CanRunCsvBatchAction(allowDirty: true));
        CsvClearCheckedCommand = new RelayCommand(_ => SetCheckedForFiltered(false, all: true), _ => CsvHasChecked);
        CsvTranslateCheckedCommand = new RelayCommand(_ => _ = TranslateCheckedCsvRowsAsync(), _ => CsvHasChecked && CanRunCsvBatchAction(allowDirty: true));
        CsvDeleteCheckedCommand = new RelayCommand(_ => _ = DeleteCheckedCsvRowsAsync(), _ => CsvHasChecked && CanRunCsvBatchAction(allowDirty: true));
        CsvEditorRow.SelectionChanged += OnCsvRowCheckedChanged;
        PropertyChanged += (_, e) =>
        {
            if (e.PropertyName is nameof(Busy) or nameof(CsvEditorLoading) or nameof(CsvEditorSaving)
                or nameof(CsvEditorPath) or nameof(CsvEditorHasDocument))
                RecountChecked();
        };
    }

    private void DisposeCsvSelection() => CsvEditorRow.SelectionChanged -= OnCsvRowCheckedChanged;

    private void OnCsvRowCheckedChanged(bool _)
    {
        if (!_suppressCheckedEvents) RecountChecked();
    }

    internal void RecountChecked()
    {
        _csvCheckedCount = _csvEditorRows.Count(row => row.IsSelected);
        Raise(nameof(CsvCheckedCount)); Raise(nameof(CsvHasChecked)); Raise(nameof(CsvCheckedText));
        CsvSelectAllFilteredCommand?.RaiseCanExecuteChanged();
        CsvClearCheckedCommand?.RaiseCanExecuteChanged(); CsvTranslateCheckedCommand?.RaiseCanExecuteChanged(); CsvDeleteCheckedCommand?.RaiseCanExecuteChanged();
    }

    /// <summary>Check every row of the CURRENT filter (or, for "all", uncheck everything including rows hidden by a filter).</summary>
    private void SetCheckedForFiltered(bool value, bool all = false)
    {
        _suppressCheckedEvents = true;
        try
        {
            if (all || _csvEditorView is null)
                foreach (var row in _csvEditorRows) row.IsSelected = value;
            else
                foreach (var item in _csvEditorView)
                    if (item is CsvEditorRow row) row.IsSelected = value;
        }
        finally { _suppressCheckedEvents = false; }
        RecountChecked();
    }

    private List<string> CheckedCsvKeys() => _csvEditorRows.Where(row => row.IsSelected).Select(row => row.Key).ToList();

    private async Task<bool> EnsureCsvSavedBeforeBatchAsync(string question)
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return false;
        if (!CsvEditorDirty) return true;
        var choice = CsvEditorMessageBox(question, "Lưu CSV", MessageBoxButton.YesNoCancel, MessageBoxImage.Warning);
        if (choice != MessageBoxResult.Yes) return false;
        return await SaveCsvEditorAsync();
    }

    internal async Task TranslateCheckedCsvRowsAsync()
    {
        if (_csvSelectionPreparing) return;
        _csvSelectionPreparing = true;
        try { await TranslateCheckedCsvRowsCoreAsync(); }
        finally { _csvSelectionPreparing = false; }
    }

    private async Task TranslateCheckedCsvRowsCoreAsync()
    {
        if (Busy) { ShowToast("Worker đang bận — hãy đợi hoặc hủy tác vụ hiện tại.", "warning"); return; }
        var keys = CheckedCsvKeys();
        if (keys.Count == 0 || string.IsNullOrWhiteSpace(CsvEditorPath)) return;
        if (!await EnsureCsvSavedBeforeBatchAsync("CSV có thay đổi chưa lưu. Lưu trước khi dịch các dòng đã chọn?")) return;
        Dictionary<string, (bool Eligible, string Reason, bool Technical)> eligibility;
        var preflightPath = CsvEditorPath; var preflightHash = _csvEditorSourceSha256;
        try { eligibility = await Task.Run(() => TranslationCsvEditorService.Eligibility(preflightPath, preflightHash!)); }
        catch (Exception ex) { ShowToast(ex.Message, "error"); return; }
        if (Busy || CsvEditorDirty || preflightPath != CsvEditorPath || preflightHash != _csvEditorSourceSha256 || !keys.SequenceEqual(CheckedCsvKeys())) return;
        var skipped = keys.Count(key => eligibility.TryGetValue(key, out var row) && !row.Eligible);
        var overwritten = _csvEditorRows.Count(row => row.IsSelected && !string.IsNullOrWhiteSpace(row.Translation));
        var message = UiText.Lines(
            UiText.Msg("Dịch {0} dòng đã chọn bằng OPUS-MT offline?", keys.Count.ToString("N0")),
            UiText.Msg("{0} dòng kỹ thuật/không phù hợp sẽ được bỏ qua; lý do từng dòng có trong Nhật ký.", skipped.ToString("N0")),
            overwritten > 0 ? UiText.Msg("{0} dòng trong số đó đã có bản dịch và sẽ được dịch lại; các dòng không chọn giữ nguyên.", overwritten.ToString("N0"))
                            : UiText.Translate("Các dòng không chọn (kể cả bản dịch bạn đã sửa tay) giữ nguyên."),
            "Kết quả được lưu vào chính file CSV này, có sao lưu và kiểm tra cấu trúc sau khi dịch.");
        if (CsvEditorMessageBox(message, "Dịch dòng đã chọn", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes) return;
        if (!await EnsureCsvSavedBeforeBatchAsync("CSV có thay đổi chưa lưu. Lưu trước khi dịch các dòng đã chọn?")) return;
        if (string.IsNullOrWhiteSpace(_csvEditorSourceSha256) || !File.Exists(CsvEditorPath))
        {
            ShowToast("Không xác minh được bản CSV đang mở; hãy tải lại CSV rồi chọn lại.", "error");
            return;
        }
        _csvEditorRetranslatePending = true;
        _csvEditorRetranslatePath = CsvEditorPath;
        BeginTask("translate", BuildSelectedTranslateParams(keys), UiText.Msg("Đang dịch {0} dòng đã chọn…", keys.Count.ToString("N0")));
    }

    private async Task SelectTranslatableAsync()
    {
        if (Busy || _csvSelectionPreparing) return;
        if (!await EnsureCsvSavedBeforeBatchAsync("Lưu CSV trước khi phân loại dòng có thể dịch?")) return;
        try
        {
            var path = CsvEditorPath; var hash = _csvEditorSourceSha256;
            var eligibility = await Task.Run(() => TranslationCsvEditorService.Eligibility(path, hash!));
            if (CsvEditorDirty || path != CsvEditorPath || hash != _csvEditorSourceSha256) return;
            foreach (var row in _csvEditorRows) row.IsSelected = false;
            foreach (var row in _csvEditorView.OfType<CsvEditorRow>())
                row.IsSelected = eligibility.TryGetValue(row.Key, out var decision) && decision.Eligible;
            RecountChecked();
        }
        catch (Exception ex) { ShowToast(ex.Message, "error"); }
    }

    /// <summary>Worker payload for "translate the checked rows": carries the CSV revision the user opened so the worker refuses (no mutation) if the file changed.</summary>
    internal object BuildSelectedTranslateParams(IReadOnlyCollection<string> keys) => new
    {
        csv_path = CsvEditorPath,
        keys = keys.ToArray(),
        selection_only = true,
        expected_csv_sha256 = _csvEditorSourceSha256,
        overwrite = true,
        human_review_required = HumanReviewRequired,
        model = "ct2",
        model_dir = TranslationModelDir,
    };

    internal async Task DeleteCheckedCsvRowsAsync()
    {
        if (Busy) { ShowToast("Worker đang bận — hãy đợi hoặc hủy tác vụ hiện tại.", "warning"); return; }
        var keys = CheckedCsvKeys();
        if (keys.Count == 0 || string.IsNullOrWhiteSpace(CsvEditorPath)) return;
        var message = UiText.Lines(
            UiText.Msg("Xóa {0} dòng đã chọn khỏi CSV?", keys.Count.ToString("N0")),
            "Dòng bị xóa sẽ không được dịch hay patch, và không hiện lại khi lấy text lại từ cùng nguồn.",
            "Nguyên bản game không bị thay đổi; quyết định được ghi lại trong user_exclusions.json.");
        if (CsvEditorMessageBox(message, "Xóa dòng đã chọn", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
        if (!await EnsureCsvSavedBeforeBatchAsync("CSV có thay đổi chưa lưu. Lưu trước khi xóa các dòng đã chọn?")) return;
        if (string.IsNullOrWhiteSpace(_csvEditorSourceSha256) || !File.Exists(CsvEditorPath))
        {
            ShowToast("Không xác minh được bản CSV đang mở; hãy tải lại CSV rồi chọn lại.", "error");
            return;
        }
        var result = TranslationCsvEditorService.ExcludeRows(CsvEditorPath, keys, _csvEditorSourceSha256!);
        if (!result.Ok)
        {
            ShowToast(result.Error ?? "Không xóa được dòng.", "error");
            AppendLog("Xóa dòng thất bại: " + result.Error, "WARN");
            return;
        }
        ShowToast(UiText.Msg("Đã xóa {0} dòng; còn {1} dòng.", result.Removed.ToString("N0"), result.Remaining.ToString("N0")), "success");
        AppendLog(UiText.Msg("Đã xóa {0} dòng khỏi CSV (ghi trong user_exclusions.json).", result.Removed.ToString("N0")));
        SetCheckedForFiltered(false, all: true);
        CsvEditorDirty = false;
        LoadCsvEditor(CsvEditorPath, reload: true);
        if (SameCsvPath(TranslationCsvPath, CsvEditorPath))
            InvalidatePatchSourceState(csvRevisionChanged: true, keepCsvValidation: true);
        RefreshWorkflow();
        RefreshTranslateReadiness();
        RaiseSafeSubsetPatch();
    }
}
