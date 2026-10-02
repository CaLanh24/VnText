using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Data;
using System.Windows.Threading;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    private const int CsvEditorUiBatchSize = 350; // kept for potential future chunking

    internal Func<string, string, MessageBoxButton, MessageBoxImage, MessageBoxResult> CsvEditorMessageBox { get; set; } =
        static (message, caption, buttons, image) => MessageBox.Show(message, caption, buttons, image);

    private readonly ResettableObservableCollection<CsvEditorRow> _csvEditorRows = [];
    private readonly List<string> _csvEditorFields = [];
    private readonly HashSet<string> _csvEditorReviewKeys = new(StringComparer.OrdinalIgnoreCase);
    private ICollectionView? _csvEditorView;
    private string _csvEditorPath = "";
    private string _csvEditorStatus = "Chưa mở translation.csv";
    private string _csvEditorSearch = "";
    private string _csvFilterMode = CsvFilterModes.All;
    private bool _csvEditorDirty;
    private string _csvEditorValidationMessage = "";
    private int _csvEditorVisibleCount;
    private int _csvEditorPatchEligible;
    private int _csvEditorPatchBlocked;
    private int _csvEditorBatchActionable;
    private readonly List<string> _csvEditorSelectedKeys = [];
    private bool _csvEditorRetranslatePending;
    private int _csvLoadGeneration;
    private CancellationTokenSource? _csvLoadCts;
    private bool _csvEditorLoading;
    private bool _csvEditorValidating;
    private string _csvBulkFind = "";
    private string _csvBulkReplace = "";
    private string _csvBulkScope = "filtered";
    private string _csvBulkPreview = "Nhập chuỗi rồi bấm Xem trước & thay thế.";
    private string? _csvBulkLastBackup;

    public ObservableCollection<CsvEditorRow> CsvEditorRows => _csvEditorRows;

    public ICollectionView? CsvEditorView => _csvEditorView;

    public string CsvEditorPath
    {
        get => _csvEditorPath;
        private set
        {
            if (Set(ref _csvEditorPath, value))
                Raise(nameof(CsvEditorPathDisplay));
        }
    }

    public string CsvEditorPathDisplay =>
        string.IsNullOrWhiteSpace(CsvEditorPath) ? "Chưa chọn file…" : CsvEditorPath;

    public string CsvEditorStatus
    {
        get => _csvEditorStatus;
        private set => Set(ref _csvEditorStatus, value);
    }

    public string CsvEditorSearch
    {
        get => _csvEditorSearch;
        set
        {
            if (Set(ref _csvEditorSearch, value))
                ApplyCsvEditorFilter();
        }
    }

    public string CsvFilterMode
    {
        get => _csvFilterMode;
        set
        {
            var normalized = string.IsNullOrWhiteSpace(value) ? CsvFilterModes.All : value;
            if (Set(ref _csvFilterMode, normalized))
                ApplyCsvEditorFilter();
        }
    }

    public bool CsvEditorDirty
    {
        get => _csvEditorDirty;
        private set => Set(ref _csvEditorDirty, value);
    }

    public string CsvEditorValidationMessage
    {
        get => _csvEditorValidationMessage;
        private set => Set(ref _csvEditorValidationMessage, value);
    }

    public string CsvBulkFind
    {
        get => _csvBulkFind;
        set
        {
            if (Set(ref _csvBulkFind, value))
            {
                CsvBulkPreview = "Đã thay đổi chuỗi tìm — bấm Xem trước & thay thế.";
                BulkReplaceCsvCommand?.RaiseCanExecuteChanged();
            }
        }
    }

    public string CsvBulkReplace
    {
        get => _csvBulkReplace;
        set => Set(ref _csvBulkReplace, value);
    }

    public string CsvBulkScope
    {
        get => _csvBulkScope;
        set
        {
            if (Set(ref _csvBulkScope, string.Equals(value, "all", StringComparison.OrdinalIgnoreCase) ? "all" : "filtered"))
                CsvBulkPreview = "Đã đổi phạm vi — bấm Xem trước & thay thế.";
        }
    }

    public IReadOnlyList<CsvFilterOption> CsvBulkScopeOptions { get; } =
    [
        new("filtered", "Dòng đang lọc"),
        new("all", "Toàn bộ CSV"),
    ];

    public string CsvBulkPreview
    {
        get => _csvBulkPreview;
        private set => Set(ref _csvBulkPreview, value);
    }

    public int CsvEditorVisibleCount
    {
        get => _csvEditorVisibleCount;
        private set => Set(ref _csvEditorVisibleCount, value);
    }

    public int CsvEditorPatchEligible
    {
        get => _csvEditorPatchEligible;
        private set => Set(ref _csvEditorPatchEligible, value);
    }

    public int CsvEditorPatchBlocked
    {
        get => _csvEditorPatchBlocked;
        private set => Set(ref _csvEditorPatchBlocked, value);
    }

    public int CsvEditorBatchActionable
    {
        get => _csvEditorBatchActionable;
        private set => Set(ref _csvEditorBatchActionable, value);
    }

    public string CsvEditorGateStats =>
        _csvEditorRows.Count == 0
            ? ""
            : $"Hợp lệ {CsvEditorPatchEligible:N0} · Bị chặn {CsvEditorPatchBlocked:N0} · Xử lý hàng loạt {CsvEditorBatchActionable:N0}";

    public bool CsvEditorLoading
    {
        get => _csvEditorLoading;
        private set
        {
            if (Set(ref _csvEditorLoading, value))
            {
                ReloadCsvEditorCommand.RaiseCanExecuteChanged();
                ValidateCsvEditorCommand.RaiseCanExecuteChanged();
                ClearBlockedCsvCommand.RaiseCanExecuteChanged();
                RetranslateBlockedCsvCommand.RaiseCanExecuteChanged();
                Raise(nameof(CsvEditorBusy));
            }
        }
    }

    public bool CsvEditorValidating
    {
        get => _csvEditorValidating;
        private set
        {
            if (Set(ref _csvEditorValidating, value))
            {
                ValidateCsvEditorCommand.RaiseCanExecuteChanged();
                Raise(nameof(CsvEditorBusy));
            }
        }
    }

    public bool CsvEditorBusy => CsvEditorLoading || CsvEditorValidating;

    /// <summary>Last load/validate phase timings in milliseconds (for probes).</summary>
    public IReadOnlyDictionary<string, long> LastCsvTiming { get; private set; }
        = new Dictionary<string, long>();

    public IReadOnlyList<CsvFilterOption> CsvFilterOptions => CsvFilterModes.Options;

    public RelayCommand OpenCsvEditorFileCommand { get; private set; } = null!;
    public RelayCommand ReloadCsvEditorCommand { get; private set; } = null!;
    public RelayCommand SaveCsvEditorCommand { get; private set; } = null!;
    public RelayCommand ValidateCsvEditorCommand { get; private set; } = null!;
    public RelayCommand OpenCsvEditorFromPatchCommand { get; private set; } = null!;
    public RelayCommand ClearBlockedCsvCommand { get; private set; } = null!;
    public RelayCommand RetranslateBlockedCsvCommand { get; private set; } = null!;
    public RelayCommand BulkReplaceCsvCommand { get; private set; } = null!;
    public RelayCommand UndoBulkReplaceCsvCommand { get; private set; } = null!;

    private void InitCsvEditorCommands()
    {
        OpenCsvEditorFileCommand = new RelayCommand(_ => ChooseCsvEditorFile());
        ReloadCsvEditorCommand = new RelayCommand(
            _ => LoadCsvEditor(reload: true),
            _ => !string.IsNullOrWhiteSpace(CsvEditorPath) && !CsvEditorLoading);
        SaveCsvEditorCommand = new RelayCommand(_ => SaveCsvEditor(), _ => CsvEditorDirty && !string.IsNullOrWhiteSpace(CsvEditorPath) && !CsvEditorLoading);
        ValidateCsvEditorCommand = new RelayCommand(
            _ => ValidateCsvEditor(showLog: true),
            _ => !CsvEditorLoading && !_csvEditorValidating && _csvEditorRows.Count > 0);
        OpenCsvEditorFromPatchCommand = new RelayCommand(_ => OpenCsvEditorFromPatch());
        ClearBlockedCsvCommand = new RelayCommand(_ => ClearBlockedCsvTranslations(), _ => CanRunCsvBatchAction());
        RetranslateBlockedCsvCommand = new RelayCommand(_ => RetranslateBlockedCsvRows(), _ => CanRunCsvBatchAction() && !Busy);
        BulkReplaceCsvCommand = new RelayCommand(_ => BulkReplaceTranslation(), _ => CanRunCsvBatchAction() && !Busy && !string.IsNullOrWhiteSpace(CsvBulkFind));
        UndoBulkReplaceCsvCommand = new RelayCommand(_ => UndoBulkReplace(), _ => !Busy && !string.IsNullOrWhiteSpace(_csvBulkLastBackup) && File.Exists(_csvBulkLastBackup));
    }

    internal void UpdateCsvEditorSelection(System.Collections.IList selectedItems)
    {
        _csvEditorSelectedKeys.Clear();
        foreach (var item in selectedItems)
        {
            if (item is CsvEditorRow row && !string.IsNullOrWhiteSpace(row.Key))
                _csvEditorSelectedKeys.Add(row.Key);
        }
        ClearBlockedCsvCommand.RaiseCanExecuteChanged();
        RetranslateBlockedCsvCommand.RaiseCanExecuteChanged();
    }

    private bool CanRunCsvBatchAction() =>
        !string.IsNullOrWhiteSpace(CsvEditorPath) && _csvEditorRows.Count > 0 && !Busy && !CsvEditorLoading;

    private List<string> ResolveCsvBatchTargetKeys()
    {
        if (_csvEditorSelectedKeys.Count > 0)
            return _csvEditorSelectedKeys.ToList();
        return _csvEditorRows.Where(r => r.HasIssue).Select(r => r.Key).ToList();
    }

    private void OnCsvEditorTabSelected()
    {
        if (!string.IsNullOrWhiteSpace(CsvEditorPath) && _csvEditorRows.Count > 0 && !CsvEditorLoading)
            return;
        var path = ResolveActiveCsvPath();
        if (File.Exists(path))
            LoadCsvEditor(path, reload: true);
    }

    private void CancelCsvEditorLoad(string reason)
    {
        Interlocked.Increment(ref _csvLoadGeneration);
        try { _csvLoadCts?.Cancel(); } catch { /* ignore */ }
        // Do not mutate the row collection here — an in-flight PopulateCsvEditorUiAsync
        // may be in a silent update; it exits on generation mismatch and ends silently.
        if (CsvEditorLoading)
        {
            CsvEditorLoading = false;
            CsvEditorStatus = $"Đã hủy tải CSV ({reason})";
            AppendLog($"[csv] Hủy tải: {reason}");
        }
    }

    private void ChooseCsvEditorFile()
    {
        var path = _pathPicker.PickTranslationCsvFile();
        if (!string.IsNullOrWhiteSpace(path))
            LoadCsvEditor(path, reload: true);
    }

    private void OpenCsvEditorFromPatch()
    {
        var path = ResolveActiveCsvPath();
        if (!File.Exists(path))
        {
            AppendLog("Chưa có translation.csv để sửa — hãy extract hoặc chọn file.");
            return;
        }
        TranslationCsvPath = path;
        LoadCsvEditor(path, reload: true);
        SelectedTab = WorkflowTabs.EditCsv;
    }

    private void LoadCsvEditor(bool reload) => LoadCsvEditor(CsvEditorPath, reload);

    private void LoadCsvEditor(string? path, bool reload)
    {
        path = (path ?? "").Trim();
        if (string.IsNullOrEmpty(path))
        {
            CsvEditorStatus = "Chưa chọn translation.csv";
            return;
        }
        if (!reload && path == CsvEditorPath && _csvEditorRows.Count > 0 && !CsvEditorLoading)
            return;

        var gen = Interlocked.Increment(ref _csvLoadGeneration);
        _csvLoadCts?.Cancel();
        _csvLoadCts?.Dispose();
        _csvLoadCts = new CancellationTokenSource();
        var ct = _csvLoadCts.Token;
        var pathCopy = path;

        CsvEditorLoading = true;
        CsvEditorStatus = "Đang tải CSV…";
        CsvEditorValidationMessage = "";
        CsvEditorPatchEligible = 0;
        CsvEditorPatchBlocked = 0;
        CsvEditorBatchActionable = 0;
        Raise(nameof(CsvEditorGateStats));
        _csvEditorRows.ClearSilentThenNotify();
        CsvEditorVisibleCount = 0;
        AppendLog($"[csv] Bắt đầu tải nền: {Path.GetFileName(pathCopy)} (gen={gen})");

        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher is null)
        {
            // Unit-test host: keep synchronous load.
            ApplyCsvDocumentSync(TranslationCsvEditorService.Load(pathCopy));
            return;
        }

        _ = Task.Run(() =>
        {
            var sw = Stopwatch.StartNew();
            CsvEditorDocument doc;
            try
            {
                doc = TranslationCsvEditorService.Load(pathCopy);
            }
            catch (Exception ex)
            {
                doc = new CsvEditorDocument(false, pathCopy, [], [], new HashSet<string>(), ex.Message);
            }

            if (ct.IsCancellationRequested || gen != Volatile.Read(ref _csvLoadGeneration))
                return;

            if (!doc.Ok)
            {
                var err = doc.Error ?? "Không mở được CSV";
                dispatcher.BeginInvoke(() =>
                {
                    if (gen != Volatile.Read(ref _csvLoadGeneration))
                        return;
                    CsvEditorLoading = false;
                    CsvEditorStatus = err;
                    AppendLog($"CSV editor: {err}");
                });
                return;
            }

            var review = new HashSet<string>(doc.ReviewKeys, StringComparer.OrdinalIgnoreCase);
            var built = new List<CsvEditorRow>(doc.Rows.Count);
            var index = 0;
            foreach (var row in doc.Rows)
            {
                if (ct.IsCancellationRequested || gen != Volatile.Read(ref _csvLoadGeneration))
                    return;
                var key = row.TryGetValue("key", out var k) ? k : "";
                // Reuse the load dictionary — avoid a second 27k-row alloc storm / GC pause.
                Dictionary<string, string> fields;
                if (row is Dictionary<string, string> owned)
                    fields = owned;
                else
                    fields = new Dictionary<string, string>(row, StringComparer.OrdinalIgnoreCase);
                built.Add(new CsvEditorRow
                {
                    Index = index++,
                    Key = key,
                    SourceText = row.TryGetValue("source_text", out var s) ? s : "",
                    Translation = row.TryGetValue("translation", out var t) ? t : "",
                    IsReviewOnly = review.Contains(key),
                    RawFields = fields,
                });
            }

            var parseMs = sw.ElapsedMilliseconds;
            dispatcher.BeginInvoke(DispatcherPriority.Background, async () =>
            {
                if (gen != Volatile.Read(ref _csvLoadGeneration) || ct.IsCancellationRequested)
                    return;
                await PopulateCsvEditorUiAsync(doc, built, review, gen, ct, parseMs).ConfigureAwait(true);
            });
        }, ct);
    }

    private void ApplyCsvDocumentSync(CsvEditorDocument doc)
    {
        if (!doc.Ok)
        {
            CsvEditorLoading = false;
            CsvEditorStatus = doc.Error ?? "Không mở được CSV";
            return;
        }

        _csvEditorFields.Clear();
        _csvEditorFields.AddRange(doc.Fields);
        _csvEditorReviewKeys.Clear();
        foreach (var k in doc.ReviewKeys)
            _csvEditorReviewKeys.Add(k);

        _csvEditorRows.Clear();
        var index = 0;
        foreach (var row in doc.Rows)
        {
            var key = row.TryGetValue("key", out var k) ? k : "";
            _csvEditorRows.Add(new CsvEditorRow
            {
                Index = index++,
                Key = key,
                SourceText = row.TryGetValue("source_text", out var s) ? s : "",
                Translation = row.TryGetValue("translation", out var t) ? t : "",
                IsReviewOnly = _csvEditorReviewKeys.Contains(key),
                RawFields = new Dictionary<string, string>(row, StringComparer.OrdinalIgnoreCase),
            });
        }

        CsvEditorPath = doc.CsvPath;
        TranslationCsvPath = doc.CsvPath;
        CsvEditorDirty = false;
        _csvEditorView = CollectionViewSource.GetDefaultView(_csvEditorRows);
        _csvEditorView.Filter = CsvEditorFilter;
        Raise(nameof(CsvEditorView));
        ApplyCsvEditorFilter();
        CsvEditorLoading = false;
        CsvEditorStatus = $"Đã mở {_csvEditorRows.Count} dòng — {Path.GetFileName(doc.CsvPath)}";
        ValidateCsvEditor(showLog: false);
        SaveCsvEditorCommand.RaiseCanExecuteChanged();
    }

    private async Task PopulateCsvEditorUiAsync(
        CsvEditorDocument doc,
        List<CsvEditorRow> built,
        HashSet<string> review,
        int gen,
        CancellationToken ct,
        long parseMs)
    {
        var timing = new Dictionary<string, long>(StringComparer.Ordinal)
        {
            ["parse_ms"] = parseMs,
        };

        var populateSw = Stopwatch.StartNew();
        _csvEditorFields.Clear();
        _csvEditorFields.AddRange(doc.Fields);
        _csvEditorReviewKeys.Clear();
        foreach (var k in review)
            _csvEditorReviewKeys.Add(k);

        CsvEditorPath = doc.CsvPath;
        TranslationCsvPath = doc.CsvPath;
        CsvEditorDirty = false;

        // Unbind DataGrid and clear any default-view filter so EndSilentUpdate Reset
        // does not re-filter 27k rows on the UI thread.
        _csvEditorView = null;
        Raise(nameof(CsvEditorView));
        var defaultView = CollectionViewSource.GetDefaultView(_csvEditorRows);
        if (defaultView is not null)
            defaultView.Filter = null;

        _csvEditorRows.BeginSilentUpdate();
        try
        {
            _csvEditorRows.Clear();
            const int chunk = 400;
            var frameSw = Stopwatch.StartNew();
            for (var i = 0; i < built.Count; i++)
            {
                if (gen != Volatile.Read(ref _csvLoadGeneration) || ct.IsCancellationRequested)
                    return;
                _csvEditorRows.AddSilent(built[i]);
                if ((i + 1) % chunk == 0 || frameSw.ElapsedMilliseconds >= 12)
                {
                    CsvEditorStatus = $"Đang tải CSV… {i + 1:N0}/{built.Count:N0}";
                    CsvEditorVisibleCount = i + 1;
                    frameSw.Restart();
                    // Background so Send-priority UI pings (watchdog) always cut through.
                    await Dispatcher.Yield(DispatcherPriority.Background);
                }
            }
        }
        finally
        {
            var endSw = Stopwatch.StartNew();
            _csvEditorRows.EndSilentUpdate();
            timing["end_silent_update_ms"] = endSw.ElapsedMilliseconds;
        }
        timing["populate_ms"] = populateSw.ElapsedMilliseconds;
        await Dispatcher.Yield(DispatcherPriority.Background);

        if (gen != Volatile.Read(ref _csvLoadGeneration) || ct.IsCancellationRequested)
            return;

        CsvEditorLoading = false;
        CsvEditorStatus = $"Đã mở {_csvEditorRows.Count:N0} dòng — {Path.GetFileName(doc.CsvPath)} (đang kiểm tra…)";
        SaveCsvEditorCommand.RaiseCanExecuteChanged();

        LastCsvTiming = timing;
        Raise(nameof(LastCsvTiming));
        AppendLog(
            $"[csv-timing] parse={timing["parse_ms"]}ms populate={timing["populate_ms"]}ms " +
            $"end_silent={timing["end_silent_update_ms"]}ms rows={_csvEditorRows.Count} (bind deferred until validate)");

        // Defer DataGrid bind until after validate apply — avoids layout storm on 27k rows.
        await Dispatcher.Yield(DispatcherPriority.ApplicationIdle);
        if (gen != Volatile.Read(ref _csvLoadGeneration) || ct.IsCancellationRequested)
            return;
        ValidateCsvEditor(showLog: false);
    }

    private bool CsvEditorFilter(object item)
    {
        if (item is not CsvEditorRow row)
            return false;

        var mode = _csvFilterMode;
        if (mode == CsvFilterModes.Untranslated && !row.IsEmpty)
            return false;
        if (mode == CsvFilterModes.ReviewOnly && !row.IsReviewOnly)
            return false;
        if (mode == CsvFilterModes.Errors && !row.HasIssue)
            return false;

        var q = (_csvEditorSearch ?? "").Trim();
        if (q.Length == 0)
            return true;
        return row.Key.Contains(q, StringComparison.OrdinalIgnoreCase)
               || row.SourceText.Contains(q, StringComparison.OrdinalIgnoreCase)
               || row.Translation.Contains(q, StringComparison.OrdinalIgnoreCase);
    }

    private void ApplyCsvEditorFilter()
    {
        if (_csvEditorView is null)
        {
            CsvEditorVisibleCount = _csvEditorRows.Count;
            return;
        }

        var mode = _csvFilterMode;
        var q = (_csvEditorSearch ?? "").Trim();
        if (mode == CsvFilterModes.All && q.Length == 0)
        {
            _csvEditorView.Refresh();
            CsvEditorVisibleCount = _csvEditorRows.Count;
            return;
        }

        _csvEditorView.Refresh();
        var count = 0;
        foreach (var _ in _csvEditorView)
            count++;
        CsvEditorVisibleCount = count;
    }

    private void MarkCsvEditorDirty()
    {
        CsvEditorDirty = true;
        SaveCsvEditorCommand.RaiseCanExecuteChanged();
    }

    private IReadOnlyList<string>? ResolveCsvBulkKeys()
    {
        if (string.Equals(CsvBulkScope, "all", StringComparison.OrdinalIgnoreCase))
            return null;
        if (_csvEditorView is null)
            return _csvEditorRows.Select(r => r.Key).Where(k => !string.IsNullOrWhiteSpace(k)).ToList();
        return _csvEditorView.Cast<object>()
            .OfType<CsvEditorRow>()
            .Select(r => r.Key)
            .Where(k => !string.IsNullOrWhiteSpace(k))
            .ToList();
    }

    private void BulkReplaceTranslation()
    {
        if (string.IsNullOrWhiteSpace(CsvEditorPath))
        {
            ShowToast("Chưa chọn file CSV.", "warning");
            return;
        }
        if (string.IsNullOrEmpty(CsvBulkFind))
        {
            ShowToast("Nhập chuỗi cần tìm.", "warning");
            return;
        }

        var rows = BuildCsvSaveRows();
        var keys = ResolveCsvBulkKeys();
        var preview = TranslationCsvEditorService.PreviewReplace(
            CsvEditorPath, _csvEditorFields, rows, CsvBulkFind, CsvBulkReplace, keys);
        if (!preview.Ok)
        {
            CsvBulkPreview = preview.Error ?? "Không xem trước được thao tác thay thế.";
            ShowToast(CsvBulkPreview, "error");
            return;
        }
        CsvBulkPreview = preview.Count == 0
            ? "Không tìm thấy chuỗi trong cột Bản dịch."
            : $"Sẽ thay {preview.ReplacementCount:N0} lần trong {preview.Count:N0} dòng ({(keys is null ? "toàn bộ CSV" : "dòng đang lọc")}).";
        if (preview.Count == 0)
        {
            ShowToast(CsvBulkPreview, "info");
            return;
        }

        var confirm =
            $"Thay thế {preview.ReplacementCount:N0} lần trong {preview.Count:N0} dòng?\n\n" +
            $"Tìm: {CsvBulkFind}\nThay bằng: {CsvBulkReplace}\n" +
            "Chỉ sửa cột Bản dịch; cột Nguyên bản/key giữ nguyên.\n" +
            "Một file backup sẽ được tạo và CSV sẽ được validate sau khi ghi.";
        if (MessageBox.Show(confirm, "Xác nhận thay thế hàng loạt", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
            return;

        var result = TranslationCsvEditorService.ReplaceTranslation(
            CsvEditorPath, _csvEditorFields, rows, CsvBulkFind, CsvBulkReplace, keys);
        if (!result.Ok)
        {
            CsvBulkPreview = result.Error ?? "Thay thế hàng loạt thất bại.";
            ShowToast(CsvBulkPreview, "error");
            AppendLog(CsvBulkPreview);
            return;
        }

        _csvBulkLastBackup = result.BackupPath;
        UndoBulkReplaceCsvCommand.RaiseCanExecuteChanged();
        var keySet = new HashSet<string>(preview.Keys, StringComparer.OrdinalIgnoreCase);
        foreach (var row in _csvEditorRows)
        {
            if (!keySet.Contains(row.Key))
                continue;
            row.Translation = Regex.Replace(row.Translation, Regex.Escape(CsvBulkFind), _ => CsvBulkReplace, RegexOptions.IgnoreCase);
        }
        CsvEditorDirty = false;
        ApplyValidationFromBatch(result.IssuesByKey, result.IssuesDisplayByKey, result.Summary,
            result.PatchEligible, result.PatchBlocked, result.BatchActionable);
        CsvBulkPreview = $"Đã thay {result.ReplacementCount:N0} lần trong {result.Count:N0} dòng. Có thể Undo; backup đã tạo.";
        AppendLog($"Bulk replace translation: {CsvBulkPreview} Backup={result.BackupPath}");
        ShowToast(CsvBulkPreview, result.PatchBlocked > 0 ? "warning" : "success");
        SaveCsvEditorCommand.RaiseCanExecuteChanged();
        ValidateTranslationCsv(silent: true);
    }

    private void UndoBulkReplace()
    {
        if (string.IsNullOrWhiteSpace(CsvEditorPath) || string.IsNullOrWhiteSpace(_csvBulkLastBackup))
            return;
        if (MessageBox.Show("Khôi phục CSV về trước lần thay thế hàng loạt gần nhất?", "Xác nhận Undo", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
            return;
        var result = TranslationCsvEditorService.Undo(CsvEditorPath, _csvBulkLastBackup);
        if (!result.Ok)
        {
            ShowToast(result.Error ?? "Undo thất bại.", "error");
            return;
        }
        _csvBulkLastBackup = null;
        UndoBulkReplaceCsvCommand.RaiseCanExecuteChanged();
        CsvBulkPreview = $"Đã Undo — khôi phục {result.RowCount:N0} dòng từ backup.";
        AppendLog(CsvBulkPreview);
        ShowToast(CsvBulkPreview, "success");
        LoadCsvEditor(CsvEditorPath, reload: true);
    }

    internal void OnCsvEditorTranslationChanged()
    {
        MarkCsvEditorDirty();
    }

    private void ValidateCsvEditor(bool showLog)
    {
        if (CsvEditorLoading)
        {
            CsvEditorValidationMessage = "Đang tải CSV — chờ xong rồi kiểm tra.";
            return;
        }
        if (string.IsNullOrWhiteSpace(CsvEditorPath) || _csvEditorRows.Count == 0)
        {
            CsvEditorValidationMessage = "Chưa có dữ liệu để kiểm tra.";
            return;
        }

        var gen = Volatile.Read(ref _csvLoadGeneration);
        var path = CsvEditorPath;
        // Snapshot row refs on UI for optional dirty payload + background silent issue apply.
        var rowSnap = _csvEditorRows.ToList();
        List<Dictionary<string, string>>? dirtyPayload = null;
        if (CsvEditorDirty)
            dirtyPayload = BuildCsvSaveRowsFrom(rowSnap, _csvEditorFields.ToList());

        CsvEditorValidating = true;
        CsvEditorValidationMessage = "Đang kiểm tra CSV…";
        AppendLog($"[csv] Validate nền bắt đầu ({rowSnap.Count:N0} dòng, dirty={CsvEditorDirty})");

        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher is null)
        {
            ApplyValidateResult(TranslationCsvEditorService.Validate(path, dirtyPayload), showLog, gen);
            CsvEditorValidating = false;
            return;
        }

        _ = Task.Run(() =>
        {
            var sw = Stopwatch.StartNew();
            CsvEditorValidateResult result;
            try
            {
                result = TranslationCsvEditorService.Validate(path, dirtyPayload);
            }
            catch (Exception ex)
            {
                result = new CsvEditorValidateResult(
                    false, ex.Message, 0, new Dictionary<string, int>(), new Dictionary<string, string>(),
                    new Dictionary<string, string>(), 0, 0, 0, false, ex.Message);
            }

            var workerMs = sw.ElapsedMilliseconds;
            var applySw = Stopwatch.StartNew();
            if (result.Ok)
            {
                foreach (var row in rowSnap)
                    ApplyIssueToRowSilent(row, result);
            }
            var applyMs = applySw.ElapsedMilliseconds;

            dispatcher.BeginInvoke(() =>
            {
                if (gen != Volatile.Read(ref _csvLoadGeneration))
                {
                    CsvEditorValidating = false;
                    return;
                }
                FinishValidateOnUi(result, showLog, gen, workerMs, applyMs);
                CsvEditorValidating = false;
            });
        });
    }

    private void FinishValidateOnUi(
        CsvEditorValidateResult result,
        bool showLog,
        int gen,
        long validateMs,
        long applyMs)
    {
        if (gen != Volatile.Read(ref _csvLoadGeneration))
            return;
        if (!result.Ok)
        {
            CsvEditorValidationMessage = result.Error ?? "Kiểm tra thất bại";
            if (showLog)
                AppendLog(CsvEditorValidationMessage);
            return;
        }

        CsvEditorPatchEligible = result.PatchEligible;
        CsvEditorPatchBlocked = result.PatchBlocked;
        CsvEditorBatchActionable = result.BatchActionable;
        Raise(nameof(CsvEditorGateStats));
        CsvEditorValidationMessage = result.Summary;

        var bindSw = Stopwatch.StartNew();
        if (_csvEditorView is null)
        {
            _csvEditorView = CollectionViewSource.GetDefaultView(_csvEditorRows);
            _csvEditorView.Filter = CsvEditorFilter;
            Raise(nameof(CsvEditorView));
        }
        var bindMs = bindSw.ElapsedMilliseconds;

        var filterSw = Stopwatch.StartNew();
        ApplyCsvEditorFilter();
        var filterMs = filterSw.ElapsedMilliseconds;

        CsvEditorStatus = $"Đã mở {_csvEditorRows.Count:N0} dòng — {Path.GetFileName(CsvEditorPath)}";

        var timing = new Dictionary<string, long>(LastCsvTiming, StringComparer.Ordinal)
        {
            ["validate_worker_ms"] = validateMs,
            ["validate_apply_ms"] = applyMs,
            ["bind_datagrid_ms"] = bindMs,
            ["collectionview_refresh_ms"] = filterMs,
            ["validate_filter_ms"] = filterMs,
            ["filter_visible_count"] = CsvEditorVisibleCount,
        };
        LastCsvTiming = timing;
        Raise(nameof(LastCsvTiming));

        AppendLog(
            $"[csv-timing] validate_worker={validateMs}ms apply_bg={applyMs}ms " +
            $"bind={bindMs}ms refresh={filterMs}ms — {result.Summary}");
        if (showLog)
            AppendLog($"Kiểm tra CSV: {result.Summary}");
    }

    private static List<Dictionary<string, string>> BuildCsvSaveRowsFrom(
        IReadOnlyList<CsvEditorRow> rows,
        IReadOnlyList<string> fields) =>
        rows.OrderBy(r => r.Index).Select(r => r.ToSaveRow(fields)).ToList();

    private void ApplyValidateResult(CsvEditorValidateResult result, bool showLog, int gen)
    {
        FinishValidateOnUi(result, showLog, gen, validateMs: 0, applyMs: 0);
    }

    private static void ApplyIssueToRowSilent(CsvEditorRow row, CsvEditorValidateResult result)
    {
        string label;
        if (result.IssuesByKey.TryGetValue(row.Key, out var reason))
            label = reason;
        else if (row.IsReviewOnly)
            label = "review_only";
        else if (row.IsEmpty)
            label = "no_translation";
        else
            label = "";

        string display;
        if (result.IssuesDisplayByKey.TryGetValue(row.Key, out var d))
            display = d;
        else if (!string.IsNullOrWhiteSpace(label) && label != "no_translation")
            display = label;
        else
            display = "";

        row.SetIssueSilent(label, display);
    }

    private static void ApplyIssueToRow(CsvEditorRow row, CsvEditorValidateResult result)
    {
        ApplyIssueToRowSilent(row, result);
        row.NotifyIssueProperties();
    }

    private bool SaveCsvEditor()
    {
        if (CsvEditorLoading)
        {
            ShowToast("Đang tải CSV — chưa thể lưu.", "warning");
            return false;
        }
        if (string.IsNullOrWhiteSpace(CsvEditorPath))
        {
            ShowToast("Chưa chọn file CSV để lưu.", "warning");
            return false;
        }
        var rows = BuildCsvSaveRows();
        var duplicates = CsvEditorDiagnostics.FindDuplicateKeys(_csvEditorRows);
        if (duplicates.Count > 0)
        {
            var duplicateMessage = CsvEditorDiagnostics.FormatDuplicateMessage(duplicates);
            CsvEditorValidationMessage = duplicateMessage;
            CsvEditorStatus = $"Chưa lưu — {duplicates.Count} key trùng";
            AppendLog(duplicateMessage);
            ShowToast(duplicateMessage, "error");
            return false;
        }

        var validation = TranslationCsvEditorService.Validate(CsvEditorPath, rows);
        if (!validation.Ok)
        {
            CsvEditorValidationMessage = validation.Error ?? "Không thể lưu — kiểm tra thất bại";
            AppendLog(CsvEditorValidationMessage);
            ShowToast(CsvEditorValidationMessage, "error");
            return false;
        }
        CsvEditorValidationMessage = validation.Summary;
        if (validation.HasWarnings)
            AppendLog($"Cảnh báo trước khi lưu: {validation.Summary}");

        var save = TranslationCsvEditorService.Save(CsvEditorPath, _csvEditorFields, rows);
        if (!save.Ok)
        {
            CsvEditorStatus = save.Error ?? "Lưu thất bại";
            AppendLog(CsvEditorStatus);
            ShowToast(CsvEditorStatus, "error");
            return false;
        }

        CsvEditorDirty = false;
        TranslationCsvPath = CsvEditorPath;
        var savedMsg = $"Đã lưu {save.RowCount:N0} dòng — {Path.GetFileName(CsvEditorPath)}";
        CsvEditorStatus = $"{savedMsg} (UTF-8 BOM, giữ nguyên cột)";
        StatusText = "Đã lưu CSV";
        AppendLog($"Đã lưu translation.csv: {CsvEditorPath}");
        ShowToast(savedMsg, validation.HasWarnings ? "warning" : "success");
        LogExpanded = true;
        ValidateTranslationCsv(silent: true);
        SaveCsvEditorCommand.RaiseCanExecuteChanged();
        return true;
    }

    private List<Dictionary<string, string>> BuildCsvSaveRows() =>
        BuildCsvSaveRowsFrom(_csvEditorRows, _csvEditorFields);

    private void ClearBlockedCsvTranslations()
    {
        if (string.IsNullOrWhiteSpace(CsvEditorPath))
        {
            ShowToast("Chưa chọn file CSV.", "warning");
            return;
        }
        var targetKeys = ResolveCsvBatchTargetKeys();
        var rows = BuildCsvSaveRows();
        var preview = TranslationCsvEditorService.PreviewClearBlocked(CsvEditorPath, _csvEditorFields, rows, targetKeys);
        if (!preview.Ok)
        {
            ShowToast(preview.Error ?? "Không xem trước được", "error");
            return;
        }
        if (preview.Count <= 0)
        {
            ShowToast("Không có dòng lỗi cấu trúc nào có bản dịch để xóa.", "info");
            return;
        }

        var msg =
            $"Xóa cột translation của {preview.Count:N0} dòng bị Patch Gate chặn?\n\n" +
            "Chỉ xóa bản dịch — giữ nguyên key và source.\n" +
            "File backup sẽ được tạo trước khi ghi.";
        if (MessageBox.Show(msg, "Xác nhận xóa bản dịch lỗi", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
            return;

        var result = TranslationCsvEditorService.ClearBlocked(CsvEditorPath, _csvEditorFields, rows, targetKeys);
        if (!result.Ok)
        {
            ShowToast(result.Error ?? "Xóa bản dịch thất bại", "error");
            AppendLog(result.Error ?? "Xóa bản dịch lỗi thất bại");
            return;
        }

        foreach (var key in preview.Keys)
        {
            var row = _csvEditorRows.FirstOrDefault(r => string.Equals(r.Key, key, StringComparison.OrdinalIgnoreCase));
            if (row is not null)
                row.Translation = "";
        }

        ApplyValidationFromBatch(result.IssuesByKey, result.IssuesDisplayByKey, result.Summary, result.PatchEligible, result.PatchBlocked, result.BatchActionable);
        CsvEditorDirty = false;
        SaveCsvEditorCommand.RaiseCanExecuteChanged();
        var backupNote = string.IsNullOrWhiteSpace(result.BackupPath) ? "" : $" Backup: {result.BackupPath}";
        AppendLog($"Đã xóa bản dịch {result.Count:N0} dòng lỗi.{backupNote}");
        ShowToast($"Đã xóa bản dịch {result.Count:N0} dòng — {result.Summary}", "success");
        ValidateTranslationCsv(silent: true);
    }

    private void RetranslateBlockedCsvRows()
    {
        if (Busy)
        {
            ShowToast("Worker đang bận — hãy đợi hoặc hủy tác vụ hiện tại.", "warning");
            return;
        }
        if (string.IsNullOrWhiteSpace(CsvEditorPath))
        {
            ShowToast("Chưa chọn file CSV.", "warning");
            return;
        }

        var targetKeys = ResolveCsvBatchTargetKeys();
        var rows = BuildCsvSaveRows();
        var preview = TranslationCsvEditorService.PreviewRetranslate(CsvEditorPath, rows, targetKeys);
        if (!preview.Ok)
        {
            ShowToast(preview.Error ?? "Không xem trước được", "error");
            return;
        }
        if (preview.Count <= 0)
        {
            ShowToast("Không có dòng lỗi cấu trúc nào để dịch lại.", "info");
            return;
        }

        const string engineLabel = "CT2";
        var msg =
            $"Dịch lại {preview.Count:N0} dòng bằng {engineLabel}?\n\n" +
            "Chỉ các dòng đã chọn hoặc đang bị gate chặn (cấu trúc).\n" +
            "Backup CSV sẽ được tạo trước khi ghi. Validation chạy sau khi dịch.";
        if (CsvEditorMessageBox(msg, "Xác nhận dịch lại dòng lỗi", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
            return;

        if (CsvEditorDirty)
        {
            var saveFirst = CsvEditorMessageBox(
                "CSV có thay đổi chưa lưu. Lưu trước khi dịch lại?",
                "Lưu CSV",
                MessageBoxButton.YesNoCancel,
                MessageBoxImage.Warning);
            if (saveFirst == MessageBoxResult.Cancel)
                return;
            if (saveFirst == MessageBoxResult.Yes && !SaveCsvEditor())
                return;
        }

        _csvEditorRetranslatePending = true;
        BeginTask("translate", new
        {
            csv_path = CsvEditorPath,
            keys = preview.Keys.ToArray(),
            overwrite = true,
            human_review_required = HumanReviewRequired,
            model = "ct2",
            model_dir = TranslationModelDir,
        }, $"Đang dịch lại {preview.Count:N0} dòng lỗi…");
    }

    internal void OnCsvEditorRetranslateComplete(bool ok)
    {
        if (!_csvEditorRetranslatePending)
            return;
        _csvEditorRetranslatePending = false;
        if (!ok || string.IsNullOrWhiteSpace(CsvEditorPath))
            return;
        LoadCsvEditor(CsvEditorPath, reload: true);
        AppendLog("Đã dịch lại và kiểm tra CSV.");
    }

    private void ApplyValidationFromBatch(
        IReadOnlyDictionary<string, string> issuesByKey,
        IReadOnlyDictionary<string, string> issuesDisplay,
        string summary,
        int eligible,
        int blocked,
        int actionable)
    {
        foreach (var row in _csvEditorRows)
        {
            if (issuesByKey.TryGetValue(row.Key, out var reason))
                row.IssueLabel = reason;
            else if (row.IsReviewOnly)
                row.IssueLabel = "review_only";
            else if (row.IsEmpty)
                row.IssueLabel = "no_translation";
            else
            {
                row.IssueLabel = "";
            }

            if (issuesDisplay.TryGetValue(row.Key, out var display))
                row.IssueDisplay = display;
            else if (!string.IsNullOrWhiteSpace(row.IssueLabel) && row.IssueLabel != "no_translation")
                row.IssueDisplay = row.IssueLabel;
            else
                row.IssueDisplay = "";
        }
        CsvEditorPatchEligible = eligible;
        CsvEditorPatchBlocked = blocked;
        CsvEditorBatchActionable = actionable;
        Raise(nameof(CsvEditorGateStats));
        CsvEditorValidationMessage = summary;
        ApplyCsvEditorFilter();
    }
}
