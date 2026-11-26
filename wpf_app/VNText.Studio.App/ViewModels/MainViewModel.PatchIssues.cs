using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

/// <summary>
/// Owner report (0.1.35): Tạo bản Việt hóa said "22 câu chưa đủ điều kiện" with no way to see them (Sửa bản dịch said 5), and a failed build showed no reason
/// on the screen.  The skipped rows now come from the same patch gate list Sửa bản dịch filters on ("Patch sẽ bỏ qua"); a failure is explained in
/// place with "Gửi báo lỗi" / "Tạo gói báo lỗi" next to it.
/// </summary>
public sealed partial class MainViewModel
{
    private PatchPreflightResult? _lastPatchPreflight;
    private string _patchErrorText = "";

    public RelayCommand ShowPatchSkippedCommand { get; private set; } = null!;
    public RelayCommand OpenCsvPatchSkippedCommand { get; private set; } = null!;

    private void InitPatchIssues()
    {
        ShowPatchSkippedCommand = new RelayCommand(_ => ShowPatchSkipped(), _ => _lastPatchPreflight is { } last && last.SkippedItems.Count > 0);
        OpenCsvPatchSkippedCommand = new RelayCommand(_ => OpenCsvPatchSkipped());
    }

    /// <summary>A failed Tạo bản Việt hóa, explained (cause + fix) on the Patch screen; empty when the last build did not fail.</summary>
    public string PatchErrorText
    {
        get => _patchErrorText;
        private set { if (Set(ref _patchErrorText, value)) Raise(nameof(HasPatchError)); }
    }
    public bool HasPatchError => !string.IsNullOrWhiteSpace(_patchErrorText);

    /// <summary>Review evidence kept outside the CSV (never a CSV row, never patched), reported apart from <see cref="PatchBlockedCount"/>.</summary>
    internal int PatchOutsideCsvReviewCount => _lastPatchPreflight?.OutsideCsvReview ?? 0;

    internal void RecordPatchPreflight(PatchPreflightResult result)
    {
        _lastPatchPreflight = result;
        ShowPatchSkippedCommand?.RaiseCanExecuteChanged();
    }

    internal void RecordPatchFailure(string? raw) => PatchErrorText = PatchIssueText.Explain(raw ?? "");
    internal void ClearPatchFailure() => PatchErrorText = "";

    internal string PatchSkippedListText()
    {
        var last = _lastPatchPreflight;
        return last is null ? "" : PatchIssueText.FormatList(last.SkippedItems, last.ItemsTruncated, last.UserExcluded, last.OutsideCsvReview);
    }

    internal void ShowPatchSkipped()
    {
        var text = PatchSkippedListText();
        if (string.IsNullOrWhiteSpace(text)) return;
        if (PatchIssueText.ShowList(text)) OpenCsvPatchSkipped();
    }

    /// <summary>Open the CSV in Sửa bản dịch filtered to exactly the rows the patch leaves out.</summary>
    internal void OpenCsvPatchSkipped()
    {
        SelectedTab = WorkflowTabs.EditCsv;
        CsvEditorSearch = "";
        CsvFilterMode = CsvFilterModes.PatchSkipped;
    }

    /// <summary>The confirmation before a build that skips rows: counts the CSV rows only (the same rows Sửa bản dịch shows) and offers the list.</summary>
    internal string PatchConfirmMessage()
    {
        var last = _lastPatchPreflight;
        var lines = new List<string>
        {
            UiText.Msg("Tạo bản Việt hóa với {0} câu hợp lệ? {1} câu chưa đủ điều kiện sẽ được bỏ qua; game giữ nguyên các câu đó.", PatchEligibleCount, PatchBlockedCount),
        };
        if (last is not null)
            foreach (var group in last.SkippedItems.GroupBy(item => item.Reason).OrderByDescending(g => g.Count()).Take(6))
                lines.Add(UiText.Msg("• {0}: {1}", UiText.TranslateDynamic(group.First().Label), group.Count()));
        if (last is { UserExcluded: > 0 } || last is { OutsideCsvReview: > 0 })
            lines.Add(UiText.Msg("(Không tính {0} dòng bạn đã xóa và {1} dòng chỉ để xem lại ngoài CSV.)", last!.UserExcluded, last.OutsideCsvReview));
        lines.Add(UiText.Translate("Bấm 'Xem danh sách' để xem từng câu, lý do và cách xử lý."));
        return UiText.Lines(lines.ToArray());
    }
}
