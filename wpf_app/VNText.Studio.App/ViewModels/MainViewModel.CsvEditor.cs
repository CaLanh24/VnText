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
    internal sealed record CsvEditorSaveAttempt(CsvEditorValidateResult Validation, CsvEditorSaveResult? Save);

    private const int CsvEditorUiBatchSize = 350; // kept for potential future chunking

    internal Func<string, string, MessageBoxButton, MessageBoxImage, MessageBoxResult> CsvEditorMessageBox { get; set; } =
        static (message, caption, buttons, image) => AppDialogService.Show(message, caption, buttons, image);

    private readonly ResettableObservableCollection<CsvEditorRow> _csvEditorRows = [];
    private readonly List<string> _csvEditorFields = [];
    private readonly HashSet<string> _csvEditorReviewKeys = new(StringComparer.OrdinalIgnoreCase);
    private ICollectionView? _csvEditorView;
    private string _csvEditorPath = "";
    private string _csvEditorStatus = "Chưa mở translation.csv";
    private string _csvEditorSearch = "";
    private string _csvFilterMode = CsvFilterModes.All;
    private bool _csvEditorDirty;
    private readonly HashSet<string> _csvEditorEditedKeys = new(StringComparer.OrdinalIgnoreCase);
    private string _csvEditorValidationMessage = "";
    private int _csvEditorVisibleCount;
    private int _csvEditorPatchEligible;
    private int _csvEditorPatchBlocked;
    private int _csvEditorBatchActionable;
    private bool _csvEditorAllTranslationsEmpty;
    private readonly List<string> _csvEditorSelectedKeys = [];
    private bool _csvEditorRetranslatePending;
    private int _csvLoadGeneration;
    private CancellationTokenSource? _csvLoadCts;
    private bool _csvEditorLoading;
    private bool _csvEditorValidating;
    private bool _csvEditorSaving;
    private string? _csvEditorSourceSha256;
    private Task<bool>? _csvEditorSaveTask;
    private long _csvEditorEditGeneration;
    internal Func<Func<CsvEditorSaveAttempt>, Task<CsvEditorSaveAttempt>> CsvEditorSaveExecutor { get; set; } =
        static work => Task.Run(work);
    private string _csvBulkFind = "";
    private string _csvBulkReplace = "";
    private string _csvBulkScope = "filtered";
    private string _csvBulkPreview = "Nhập chuỗi rồi bấm Xem trước.";
    private string? _csvBulkLastBackup;
    private CsvEditorReplacePreviewResult? _csvBulkPendingPreview;
    private string _csvBulkPendingSignature = "";

    public ObservableCollection<CsvEditorRow> CsvEditorRows => _csvEditorRows;

    public ICollectionView? CsvEditorView => _csvEditorView;

    public string CsvEditorPath
    {
        get => _csvEditorPath;
        private set
        {
            if (Set(ref _csvEditorPath, value))
            {
                Raise(nameof(CsvEditorPathDisplay));
                Raise(nameof(CsvEditorPathToolTip));
                Raise(nameof(CsvEditorHasDocument));
                ApplyCsvBulkDefault();
            }
        }
    }

    public string CsvEditorPathDisplay =>
        string.IsNullOrWhiteSpace(CsvEditorPath) ? "Chưa chọn file…" : Path.GetFileName(CsvEditorPath);
    public string CsvEditorPathToolTip => CsvEditorPath;

    /// <summary>A CSV is open (the path stays through a failed reload); without one the editor shows only its empty state.</summary>
    /// <summary>At low heights the "pick a row" hint line is dropped while nothing is selected, so the table keeps its rows; a selection shows its details again.</summary>
    public bool CsvEditorSelectionDetailsVisible => !(_csvLowHeight && _csvEditorSelectedKeys.Count == 0);

    public bool CsvEditorHasDocument => !string.IsNullOrWhiteSpace(_csvEditorPath);

    private bool _csvBulkExpanded, _csvBulkUserChoice, _csvLowHeight;
    /// <summary>The bulk find/replace tools are open. Collapsed it is still one visible row with an explicit open button; the typed find/replace/preview state is never reset by toggling.</summary>
    public bool CsvBulkExpanded
    {
        get => _csvBulkExpanded;
        private set
        {
            if (!Set(ref _csvBulkExpanded, value)) return;
            if (!value && _csvBulkPreviewDetailOpen) { _csvBulkPreviewDetailOpen = false; RaiseCsvBulkPreviewParts(); }
            Raise(nameof(CsvBulkPanelVisible));
            Raise(nameof(CsvBulkSummaryVisible));
            Raise(nameof(CsvEditorValidationCompact));
        }
    }
    public bool CsvBulkPanelVisible => CsvEditorHasDocument && _csvBulkExpanded;
    public bool CsvBulkSummaryVisible => CsvEditorHasDocument && !_csvBulkExpanded;
    public RelayCommand ToggleCsvBulkCommand { get; private set; } = null!;

    /// <summary>Low window heights leave the table fewer than ~3 rows; until the user chooses, the tools start collapsed there (and when no CSV is open).</summary>
    internal void SetCsvLowHeight(bool low)
    {
        if (_csvLowHeight == low) return;
        _csvLowHeight = low;
        Raise(nameof(CsvEditorSelectionDetailsVisible));
        RaiseCsvCompactLayout();
        ApplyCsvBulkDefault();
    }

    // Low-height presentation: tighter vertical gaps only (controls keep their 36/30 DIP sizes) and a one-line validation summary.
    public Thickness CsvBannerMargin => new(0, _csvLowHeight ? 2 : 6, 0, 0);
    public Thickness CsvBulkAreaMargin => new(0, _csvLowHeight ? 2 : 5, 0, 0);
    public Thickness CsvBulkSummaryMargin => new(0, _csvLowHeight ? 0 : 3, 0, 0);
    public Thickness CsvPreviewAreaMargin => new(0, _csvLowHeight ? 2 : 6, 0, 0);
    public Thickness CsvGridMargin => new(0, _csvLowHeight ? 4 : 8, 0, 0);

    /// <summary>With the tools collapsed (or at a low height) the validation message is ONE line; the whole message stays in the tooltip and the accessible help text.</summary>
    public bool CsvEditorValidationCompact => CsvBulkSummaryVisible || _csvLowHeight;

    public string CsvEditorUserValidationShort
    {
        get
        {
            var message = UiText.TranslateDynamic(CsvEditorUserValidationMessage ?? "");
            var cut = message.IndexOf(" — ", StringComparison.Ordinal);
            if (cut > 0) message = message[..cut];
            else
            {
                var dot = message.IndexOf(". ", StringComparison.Ordinal);
                if (dot > 0) message = message[..(dot + 1)];
            }
            return message.Length <= 80 ? message : message[..79] + "…";
        }
    }

    private void RaiseCsvCompactLayout()
    {
        Raise(nameof(CsvBannerMargin));
        Raise(nameof(CsvBulkAreaMargin));
        Raise(nameof(CsvBulkSummaryMargin));
        Raise(nameof(CsvPreviewAreaMargin));
        Raise(nameof(CsvGridMargin));
        Raise(nameof(CsvEditorValidationCompact));
    }

    private void ApplyCsvBulkDefault()
    {
        if (!_csvBulkUserChoice) CsvBulkExpanded = CsvEditorHasDocument && !_csvLowHeight;
        Raise(nameof(CsvBulkPanelVisible));
        Raise(nameof(CsvBulkSummaryVisible));
        Raise(nameof(CsvEditorValidationCompact));
    }

    internal void TestSetCsvEditorPath(string path) => CsvEditorPath = path;
    internal void TestClearCsvDirty() => CsvEditorDirty = false;

    /// <summary>Layout fixture hook: shows these rows in the real grid without running the worker.</summary>
    internal void TestLoadCsvRows(string path, IEnumerable<CsvEditorRow> rows, string validationMessage)
    {
        _csvEditorRows.Clear();
        foreach (var row in rows) _csvEditorRows.Add(row);
        CsvEditorPath = path;
        _csvEditorView = CollectionViewSource.GetDefaultView(_csvEditorRows);
        _csvEditorView.Filter = CsvEditorFilter;
        Raise(nameof(CsvEditorView));
        ApplyCsvEditorFilter();
        CsvEditorValidationMessage = validationMessage;
        CsvEditorWarningSummary = validationMessage;
    }
    internal void TestSetCsvBulkPreview(string text) => CsvBulkPreview = text;
    internal void TestSetCsvSaveError(string reason) => SetCsvEditorSaveError(CsvEditorPath, reason, CsvSaveKeepsDraftRecovery);
    internal void TestSetCsvLoadError(string path, string reason) => FailCsvEditorLoad(path, reason);
    public string CsvEditorSelectionDetails => _csvEditorSelectedKeys.Count switch
    {
        0 => "Chọn một dòng để xem mã kỹ thuật.",
        1 => UiText.Msg("Mã dòng: {0}", _csvEditorSelectedKeys[0]),
        _ => UiText.Msg("Đã chọn {0} dòng · Mã đầu tiên: {1}", _csvEditorSelectedKeys.Count.ToString("N0"), _csvEditorSelectedKeys[0])
    };

    public string CsvEditorStatus
    {
        get => _csvEditorStatus;
        private set => Set(ref _csvEditorStatus, value);
    }

    private string _csvEditorLoadError = "";
    private string _csvEditorSaveError = "";
    private string _csvEditorWarningSummary = "";

    /// <summary>Shown inline in the editor when a chosen CSV is rejected (the file name and the reason); the previously open document stays.</summary>
    public string CsvEditorLoadError
    {
        get => _csvEditorLoadError;
        private set { if (Set(ref _csvEditorLoadError, value)) Raise(nameof(HasCsvEditorLoadError)); }
    }

    public bool HasCsvEditorLoadError => !string.IsNullOrEmpty(_csvEditorLoadError);

    /// <summary>
    /// Durable reason a save was refused (external hash conflict, duplicate keys, failed validation/write). It stays visible until a save
    /// succeeds or a document is loaded; editing, filtering, tab changes, validation and a cancelled reload never clear it.
    /// </summary>
    public string CsvEditorSaveError
    {
        get => _csvEditorSaveError;
        private set
        {
            if (!Set(ref _csvEditorSaveError, value)) return;
            Raise(nameof(HasCsvEditorSaveError));
            Raise(nameof(CsvEditorUserValidationMessage));
        }
    }

    public bool HasCsvEditorSaveError => !string.IsNullOrEmpty(_csvEditorSaveError);

    private const string CsvSaveKeepsDraftRecovery = " Bản nháp của bạn vẫn được giữ và file ngoài không bị ghi đè; bấm “Tải lại” để chọn Lưu, Bỏ hoặc Hủy.";
    private const string CsvSaveFixRecovery = " Bản nháp của bạn vẫn được giữ; sửa lỗi rồi lưu lại.";

    /// <summary>Records the refusal only for the document that is open (a stale or concurrent save of another path must not paint this one).</summary>
    private void SetCsvEditorSaveError(string path, string reason, string recovery)
    {
        if (!string.Equals(path, CsvEditorPath, StringComparison.OrdinalIgnoreCase)) return;
        var text = string.IsNullOrWhiteSpace(reason) ? "không rõ lý do" : reason.Trim().TrimEnd('.');
        CsvEditorSaveError = UiText.Msg("Không lưu được: {0}.{1}", UiText.Key(text), UiText.Key(recovery));
    }

    /// <summary>Count, reason and where to look for the rows that saved or validated with warnings.</summary>
    public string CsvEditorWarningSummary
    {
        get => _csvEditorWarningSummary;
        private set { if (Set(ref _csvEditorWarningSummary, value)) Raise(nameof(CsvEditorUserValidationMessage)); }
    }

    public string CsvEditorSearch
    {
        get => _csvEditorSearch;
        set
        {
            if (Set(ref _csvEditorSearch, value))
            {
                ApplyCsvEditorFilter();
                if (_csvBulkPendingPreview is not null) InvalidateCsvBulkPreview("Đã đổi nội dung lọc — hãy xem trước lại.");
            }
        }
    }

    public string CsvFilterMode
    {
        get => _csvFilterMode;
        set
        {
            var normalized = string.IsNullOrWhiteSpace(value) ? CsvFilterModes.All : value;
            if (Set(ref _csvFilterMode, normalized))
            {
                ApplyCsvEditorFilter();
                if (_csvBulkPendingPreview is not null) InvalidateCsvBulkPreview("Đã đổi bộ lọc — hãy xem trước lại.");
            }
        }
    }

    public bool CsvEditorDirty
    {
        get => _csvEditorDirty;
        private set
        {
            if (!Set(ref _csvEditorDirty, value)) return;
            if (!value) { _csvEditorEditedKeys.Clear(); ResumeDeferredOffer(); }
            Raise(nameof(CsvEditorDirtySummary));
        }
    }
    public string CsvEditorDirtySummary => _csvEditorEditedKeys.Count > 0
        ? UiText.Msg("Chưa lưu · {0} câu đã sửa", _csvEditorEditedKeys.Count.ToString("N0")) : "Có thay đổi chưa lưu";

    public string CsvEditorValidationMessage
    {
        get => _csvEditorValidationMessage;
        private set { if (Set(ref _csvEditorValidationMessage, value)) Raise(nameof(CsvEditorUserValidationMessage)); }
    }

    public string CsvEditorUserValidationMessage => CsvEditorSaving ? CsvEditorValidationMessage
        : !string.IsNullOrEmpty(CsvEditorSaveError) ? CsvEditorSaveError
        : _csvEditorRows.Count == 0 || CsvEditorLoading || CsvEditorValidating
        ? CsvEditorValidationMessage
        : !string.IsNullOrEmpty(CsvEditorWarningSummary) ? CsvEditorWarningSummary
        : _csvEditorAllTranslationsEmpty ? "Chưa có bản dịch — chuyển sang Dịch tự động để bắt đầu."
        : CsvEditorPatchBlocked > 0 ? "Một số câu cần xem lại trước khi tạo gói. Chọn câu để xem lý do và chỉnh bản dịch."
        : "Bản dịch được kiểm tra tự động. Bạn có thể chỉnh ngữ cảnh, xưng hô và cách diễn đạt.";

    public string CsvBulkFind
    {
        get => _csvBulkFind;
        set
        {
            if (Set(ref _csvBulkFind, value))
            {
                InvalidateCsvBulkPreview("Đã thay đổi chuỗi tìm — hãy xem trước lại.");
                BulkReplaceCsvCommand?.RaiseCanExecuteChanged();
            }
        }
    }

    public string CsvBulkReplace
    {
        get => _csvBulkReplace;
        set { if (Set(ref _csvBulkReplace, value)) InvalidateCsvBulkPreview("Đã thay đổi chuỗi thay thế — hãy xem trước lại."); }
    }

    public string CsvBulkScope
    {
        get => _csvBulkScope;
        set
        {
            if (Set(ref _csvBulkScope, string.Equals(value, "all", StringComparison.OrdinalIgnoreCase) ? "all" : "filtered"))
                InvalidateCsvBulkPreview("Đã đổi phạm vi — hãy xem trước lại.");
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
        private set
        {
            if (!Set(ref _csvBulkPreview, value)) return;
            _csvBulkPreviewDetailOpen = false;       // a new preview never opens its examples by surprise
            RaiseCsvBulkPreviewParts();
        }
    }

    private bool _csvBulkPreviewDetailOpen;
    /// <summary>First line of the preview: how many replacements in how many rows. Always the only preview text a collapsed tools row keeps.</summary>
    public string CsvBulkPreviewSummary
    {
        get => UiText.SplitFirstLine(_csvBulkPreview ?? "").First;
    }
    /// <summary>The Trước/Sau examples (everything after the first line); shown only through the explicit toggle, in a height-bounded scroller.</summary>
    public string CsvBulkPreviewDetail
    {
        get => UiText.SplitFirstLine(_csvBulkPreview ?? "").Remainder;
    }
    public bool CsvBulkHasPreviewDetail => CsvBulkPreviewDetail.Length > 0;
    public bool CsvBulkPreviewDetailOpen => _csvBulkPreviewDetailOpen && CsvBulkHasPreviewDetail;
    public string CsvBulkPreviewDetailButtonText => CsvBulkPreviewDetailOpen ? "Ẩn ví dụ" : "Xem ví dụ";
    public RelayCommand ToggleCsvBulkPreviewDetailCommand { get; private set; } = null!;

    private void RaiseCsvBulkPreviewParts()
    {
        Raise(nameof(CsvBulkPreviewSummary));
        Raise(nameof(CsvBulkPreviewDetail));
        Raise(nameof(CsvBulkHasPreviewDetail));
        Raise(nameof(CsvBulkPreviewDetailOpen));
        Raise(nameof(CsvBulkPreviewDetailButtonText));
    }

    public bool CsvBulkCanApply => _csvBulkPendingPreview is { Ok: true, Count: > 0 } &&
        string.Equals(_csvBulkPendingSignature, CsvBulkSignature(), StringComparison.Ordinal);

    public int CsvEditorVisibleCount
    {
        get => _csvEditorVisibleCount;
        private set { if (Set(ref _csvEditorVisibleCount, value)) Raise(nameof(CsvEditorGateStats)); }
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

    public string CsvEditorGateStats
    {
        get
        {
            if (_csvEditorRows.Count == 0) return "Chưa có câu";
            var translated = 0; var review = 0;
            foreach (var row in _csvEditorRows) { if (!row.IsEmpty) translated++; if (row.HasIssue || row.IsReviewOnly) review++; }
            return UiText.Msg("Hiện {0} / {1} câu · Đã dịch {2} · Chưa dịch {3} · Cần xem lại {4}", CsvEditorVisibleCount.ToString("N0"), _csvEditorRows.Count.ToString("N0"), translated.ToString("N0"), (_csvEditorRows.Count - translated).ToString("N0"), review.ToString("N0"));
        }
    }

    public bool CsvEditorLoading
    {
        get => _csvEditorLoading;
        private set
        {
            if (Set(ref _csvEditorLoading, value))
            {
                ChooseInputCommand.RaiseCanExecuteChanged();
                ChooseOutputCommand.RaiseCanExecuteChanged();
                ReloadCsvEditorCommand.RaiseCanExecuteChanged();
                ValidateCsvEditorCommand.RaiseCanExecuteChanged();
                ClearBlockedCsvCommand.RaiseCanExecuteChanged();
                RetranslateBlockedCsvCommand.RaiseCanExecuteChanged();
                Raise(nameof(CsvEditorBusy));
                Raise(nameof(CsvEditorUserValidationMessage));
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
                Raise(nameof(CsvEditorUserValidationMessage));
            }
        }
    }

    public bool CsvEditorSaving
    {
        get => _csvEditorSaving;
        private set
        {
            if (!Set(ref _csvEditorSaving, value)) return;
            ReloadCsvEditorCommand.RaiseCanExecuteChanged();
            OpenCsvEditorFileCommand.RaiseCanExecuteChanged();
            SaveCsvEditorCommand.RaiseCanExecuteChanged();
            ValidateCsvEditorCommand.RaiseCanExecuteChanged();
            ChooseInputCommand.RaiseCanExecuteChanged();
            ChooseOutputCommand.RaiseCanExecuteChanged();
            ValidateTranslationCsvCommand.RaiseCanExecuteChanged();
            ClearBlockedCsvCommand.RaiseCanExecuteChanged();
            RetranslateBlockedCsvCommand.RaiseCanExecuteChanged();
            BulkReplaceCsvCommand.RaiseCanExecuteChanged();
            ApplyBulkReplaceCsvCommand.RaiseCanExecuteChanged();
            UndoBulkReplaceCsvCommand.RaiseCanExecuteChanged();
            Raise(nameof(CsvEditorSavingText));
            Raise(nameof(CsvEditorGridReadOnly));
            Raise(nameof(CsvEditorUserValidationMessage));
            Raise(nameof(CsvEditorBusy));
        }
    }

    /// <summary>The grid is read-only while a save runs or any worker task is busy: a running task
    /// (translate/patch/extract) rewrites the same CSV package and would overwrite edits made meanwhile.</summary>
    public bool CsvEditorGridReadOnly => CsvEditorSaving || Busy;

    public string CsvEditorLockText => Busy && _csvEditorRows.Count > 0
        ? "Đang chạy tác vụ — tạm khóa chỉnh sửa CSV để tác vụ không ghi đè thay đổi của bạn."
        : "";

    public string CsvEditorSavingText => UiText.Msg("Đang kiểm tra và lưu {0} dòng…", _csvEditorRows.Count.ToString("N0"));

    public bool CsvEditorBusy => CsvEditorLoading || CsvEditorValidating || CsvEditorSaving;

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
    public RelayCommand ApplyBulkReplaceCsvCommand { get; private set; } = null!;
    public RelayCommand UndoBulkReplaceCsvCommand { get; private set; } = null!;

    private void InitCsvEditorCommands()
    {
        ApproveCsvMemoryCommand = new RelayCommand(_ => ApproveCsvMemory(), _ => CanApproveCsvMemory());
        PropertyChanged += (_, e) =>
        {
            if (e.PropertyName is nameof(Busy) or nameof(CsvEditorDirty) or nameof(CsvEditorLoading) or nameof(CsvEditorPath))
                ApproveCsvMemoryCommand.RaiseCanExecuteChanged();
            if (e.PropertyName is nameof(CsvEditorDirty) or nameof(CsvEditorSaving))
            {
                RunExtractCommand.RaiseCanExecuteChanged();
                RunTranslateCommand.RaiseCanExecuteChanged();
                RunPatchCommand.RaiseCanExecuteChanged();
                ImportExistingTranslationCommand.RaiseCanExecuteChanged();
                ExportCloudRepairPackageCommand.RaiseCanExecuteChanged();
                ChooseTranslationCsvCommand.RaiseCanExecuteChanged();
                ClearBlockedCsvCommand.RaiseCanExecuteChanged();
                RetranslateBlockedCsvCommand.RaiseCanExecuteChanged();
                BulkReplaceCsvCommand.RaiseCanExecuteChanged();
                ApplyBulkReplaceCsvCommand.RaiseCanExecuteChanged();
                UndoBulkReplaceCsvCommand.RaiseCanExecuteChanged();
            }
        };
        OpenCsvEditorFileCommand = new RelayCommand(_ => ChooseCsvEditorFile(), _ => !CsvEditorSaving && !CsvEditorLoading);
        PropertyChanged += (_, e) =>
        {
            if (e.PropertyName == nameof(CsvEditorUserValidationMessage)) Raise(nameof(CsvEditorUserValidationShort));
            if (e.PropertyName is nameof(PatchPreflightOk) or nameof(PatchPreflightEvaluated) or nameof(CsvValidationOk) or nameof(PatchResultsAvailable)) RaisePatchBadge();
        };
        ToggleCsvBulkCommand = new RelayCommand(_ => { _csvBulkUserChoice = true; CsvBulkExpanded = !CsvBulkExpanded; });
        ToggleCsvBulkPreviewDetailCommand = new RelayCommand(_ => { _csvBulkPreviewDetailOpen = !_csvBulkPreviewDetailOpen; RaiseCsvBulkPreviewParts(); });
        ReloadCsvEditorCommand = new RelayCommand(
            _ => LoadCsvEditor(reload: true),
            _ => !string.IsNullOrWhiteSpace(CsvEditorPath) && !CsvEditorLoading && !CsvEditorSaving);
        SaveCsvEditorCommand = new RelayCommand(_ => _ = SaveCsvEditorAsync(), _ => CsvEditorDirty && !Busy && !string.IsNullOrWhiteSpace(CsvEditorPath) && !CsvEditorLoading && !CsvEditorSaving);
        ValidateCsvEditorCommand = new RelayCommand(
            _ => ValidateCsvEditor(showLog: true),
            _ => !CsvEditorLoading && !_csvEditorValidating && !CsvEditorSaving && _csvEditorRows.Count > 0);
        OpenCsvEditorFromPatchCommand = new RelayCommand(_ => OpenCsvEditorFromPatch());
        ClearBlockedCsvCommand = new RelayCommand(_ => ClearBlockedCsvTranslations(), _ => CanRunCsvBatchAction());
        RetranslateBlockedCsvCommand = new RelayCommand(_ => _ = RetranslateBlockedCsvRowsAsync(), _ => CanRunCsvBatchAction(allowDirty: true) && !Busy);
        BulkReplaceCsvCommand = new RelayCommand(_ => PreviewBulkReplaceTranslation(), _ => CanRunCsvBatchAction() && !Busy && !string.IsNullOrWhiteSpace(CsvBulkFind));
        ApplyBulkReplaceCsvCommand = new RelayCommand(_ => ApplyBulkReplaceTranslation(), _ => CsvBulkCanApply && CanRunCsvBatchAction() && !Busy);
        UndoBulkReplaceCsvCommand = new RelayCommand(_ => UndoBulkReplace(), _ => !Busy && !CsvEditorSaving && !CsvEditorDirty && !string.IsNullOrWhiteSpace(_csvBulkLastBackup) && File.Exists(_csvBulkLastBackup));
    }

    internal void UpdateCsvEditorSelection(System.Collections.IList selectedItems)
    {
        _csvEditorSelectedKeys.Clear();
        foreach (var item in selectedItems)
        {
            if (item is CsvEditorRow row && !string.IsNullOrWhiteSpace(row.Key))
                _csvEditorSelectedKeys.Add(row.Key);
        }
        Raise(nameof(CsvEditorSelectionDetails));
        Raise(nameof(CsvEditorSelectionDetailsVisible));
        ClearBlockedCsvCommand.RaiseCanExecuteChanged();
        RetranslateBlockedCsvCommand.RaiseCanExecuteChanged();
        ApproveCsvMemoryCommand.RaiseCanExecuteChanged();
    }

    private bool CanRunCsvBatchAction(bool allowDirty = false) =>
        !string.IsNullOrWhiteSpace(CsvEditorPath) && _csvEditorRows.Count > 0 && !Busy && !CsvEditorLoading && !CsvEditorSaving
        && (allowDirty || !CsvEditorDirty);

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
            CsvEditorStatus = UiText.Msg("Đã hủy tải CSV ({0})", UiText.Key(reason));
            AppendLog($"[csv] Hủy tải: {reason}");
        }
    }

    private void ChooseCsvEditorFile()
    {
        var path = _pathPicker.PickTranslationCsvFile(CsvEditorPickerTitle);
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
        LoadCsvEditor(path, reload: true);
        SelectedTab = WorkflowTabs.EditCsv;
    }

    private void LoadCsvEditor(bool reload) => LoadCsvEditor(CsvEditorPath, reload);

    private async void LoadCsvEditor(string? path, bool reload)
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync())
            return;
        path = (path ?? "").Trim();
        if (string.IsNullOrEmpty(path))
        {
            CsvEditorStatus = "Chưa chọn translation.csv";
            return;
        }
        if (!reload && path == CsvEditorPath && _csvEditorRows.Count > 0 && !CsvEditorLoading)
            return;
        if (CsvEditorDirty)
        {
            var choice = CsvEditorMessageBox("CSV có thay đổi chưa lưu. Lưu trước khi mở lại hoặc chọn file khác?",
                "Thay đổi CSV chưa lưu", MessageBoxButton.YesNoCancel, MessageBoxImage.Warning);
            if (choice == MessageBoxResult.Cancel)
                return;
            if (choice == MessageBoxResult.Yes && !await SaveCsvEditorAsync())
                return;
            if (choice == MessageBoxResult.No)
                DiscardCsvEditorChanges();
        }

        var gen = Interlocked.Increment(ref _csvLoadGeneration);
        _csvLoadCts?.Cancel();
        _csvLoadCts?.Dispose();
        _csvLoadCts = new CancellationTokenSource();
        var ct = _csvLoadCts.Token;
        var pathCopy = path;

        // The open document stays untouched until the new file is proven readable (a rejected file must not blank the editor
        // or leave a title that names another file); ResetCsvEditorDocumentState runs when the new document is applied.
        CsvEditorLoading = true;
        CsvEditorLoadError = "";
        CsvEditorStatus = "Đang tải CSV…";
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
                    FailCsvEditorLoad(pathCopy, err);
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

    private void ResetCsvEditorDocumentState()
    {
        CsvEditorStaleOnDisk = false;
        _csvEditorSourceSha256 = null;
        CsvEditorValidationMessage = "";
        CsvEditorWarningSummary = "";
        CsvEditorSaveError = "";                      // a loaded document starts clean
        CsvEditorPatchEligible = 0;
        CsvEditorPatchBlocked = 0;
        CsvEditorBatchActionable = 0;
        _csvEditorAllTranslationsEmpty = false;
        Raise(nameof(CsvEditorGateStats));
        CsvEditorVisibleCount = 0;
    }

    private void FailCsvEditorLoad(string rejectedPath, string reason)
    {
        CsvEditorLoading = false;
        object rejected = string.IsNullOrWhiteSpace(rejectedPath) ? UiText.Key("CSV đã chọn") : Path.GetFileName(rejectedPath);
        var keeping = string.IsNullOrWhiteSpace(CsvEditorPath)
            ? "chưa có file nào đang mở"
            : UiText.Msg("đang giữ {0}", Path.GetFileName(CsvEditorPath));
        CsvEditorLoadError = UiText.Msg("Không mở được {0}: {1} ({2}).", rejected, UiText.Key(reason), UiText.Key(keeping));
        CsvEditorStatus = CsvEditorLoadError;
        AppendLog($"CSV editor: {CsvEditorLoadError}");
        ShowToast(CsvEditorLoadError, "error");
        SaveCsvEditorCommand?.RaiseCanExecuteChanged();
    }

    /// <summary>Count, reason and the way to the affected rows for a validation that passed with warnings; empty otherwise.</summary>
    internal static string BuildCsvWarningSummary(CsvEditorValidateResult validation)
    {
        if (!validation.Ok || !validation.HasWarnings || validation.IssueCount <= 0)
            return "";
        var reasons = validation.IssuesDisplayByKey.Values
            .Where(text => !string.IsNullOrWhiteSpace(text))
            .GroupBy(text => text)
            .OrderByDescending(group => group.Count())
            .Take(2)
            .Select(group => UiText.Msg("{0}× {1}", group.Count().ToString("N0"), UiText.Key(group.Key)))
            .ToList();
        object detail = reasons.Count > 0 ? UiText.Join("; ", reasons) : UiText.Key(validation.Summary);
        return UiText.Msg("Cảnh báo: {0} dòng cần xem lại — {1}. Xem cột Trạng thái hoặc lọc “Chỉ dòng lỗi”.", validation.IssueCount.ToString("N0"), detail);
    }

    private void ApplyCsvDocumentSync(CsvEditorDocument doc)
    {
        if (!doc.Ok)
        {
            FailCsvEditorLoad(doc.CsvPath, doc.Error ?? "Không mở được CSV");
            return;
        }

        ResetCsvEditorDocumentState();
        _csvEditorFields.Clear();
        _csvEditorFields.AddRange(doc.Fields);
        _csvEditorSourceSha256 = doc.SourceSha256;
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
        CsvEditorStatus = UiText.Msg("Đã mở {0} dòng — {1}", _csvEditorRows.Count, Path.GetFileName(doc.CsvPath));
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
        ResetCsvEditorDocumentState();
        _csvEditorFields.Clear();
        _csvEditorFields.AddRange(doc.Fields);
        _csvEditorSourceSha256 = doc.SourceSha256;
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
                    CsvEditorStatus = UiText.Msg("Đang tải CSV… {0}/{1}", (i + 1).ToString("N0"), built.Count.ToString("N0"));
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
        CsvEditorStatus = UiText.Msg("Đã mở {0} dòng — {1} (đang kiểm tra…)", _csvEditorRows.Count.ToString("N0"), Path.GetFileName(doc.CsvPath));
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
        Interlocked.Increment(ref _csvEditorEditGeneration);
        if (_csvBulkPendingPreview is not null) InvalidateCsvBulkPreview("CSV đã được chỉnh sửa — hãy xem trước lại.");
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

    /// <summary>
    /// Bulk preview/apply/undo spawn the Python CSV engine; run them off the UI thread (a 27k-row
    /// package took seconds, freezing the window and leaving the confirm overlay on screen).  The
    /// editor stays locked (same lock as a save) so nothing edits the rows underneath the call.
    /// </summary>
    // Everything a bulk preview/apply result depends on.  Captured BEFORE the off-thread call and
    // compared after it: the find/replace boxes, filter, scope, selection and the load/edit
    // generations can change while the Python engine runs, and a result computed for the old
    // inputs must never be stored as the pending preview of the new ones.
    private (string Signature, string Selection, int LoadGeneration, long EditGeneration) CsvBulkStamp() =>
        (CsvBulkSignature(), string.Join("\u001e", _csvEditorSelectedKeys),
         Volatile.Read(ref _csvLoadGeneration), Volatile.Read(ref _csvEditorEditGeneration));

    internal Func<Func<object?>, Task<object?>> CsvEditorBackgroundExecutor { get; set; } = work => Task.Run(work);

    private async Task<T> RunCsvEditorBackgroundAsync<T>(Func<T> work)
    {
        CsvEditorSaving = true;
        try { return (T)(await CsvEditorBackgroundExecutor(() => work()).ConfigureAwait(true))!; }
        finally { CsvEditorSaving = false; }
    }

    private async void PreviewBulkReplaceTranslation()
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
        var stamp = CsvBulkStamp();
        var (previewPath, previewFields, previewFind, previewReplace) = (CsvEditorPath, _csvEditorFields.ToList(), CsvBulkFind, CsvBulkReplace);
        var preview = await RunCsvEditorBackgroundAsync(() => TranslationCsvEditorService.PreviewReplace(
            previewPath, previewFields, rows, previewFind, previewReplace, keys));
        if (stamp != CsvBulkStamp() || !string.Equals(previewPath, CsvEditorPath, StringComparison.OrdinalIgnoreCase))
        {
            InvalidateCsvBulkPreview("Chuỗi tìm/thay, bộ lọc hoặc dữ liệu đã đổi trong lúc xem trước — hãy xem trước lại.");
            return;
        }
        if (!preview.Ok)
        {
            CsvBulkPreview = preview.Error ?? "Không xem trước được thao tác thay thế.";
            ShowToast(CsvBulkPreview, "error");
            return;
        }
        _csvBulkPendingPreview = preview.Count == 0 ? null : preview;
        _csvBulkPendingSignature = preview.Count == 0 ? "" : stamp.Signature;
        Raise(nameof(CsvBulkCanApply));
        ApplyBulkReplaceCsvCommand?.RaiseCanExecuteChanged();
        CsvBulkPreview = preview.Count == 0
            ? "Không tìm thấy chuỗi trong cột Bản dịch."
            : UiText.Msg("Sẽ thay {0} lần trong {1} dòng ({2}).", preview.ReplacementCount.ToString("N0"), preview.Count.ToString("N0"), UiText.Key(keys is null ? "toàn bộ CSV" : "dòng đang lọc"));
        if (preview.Count > 0)
        {
            var samples = rows.Where(row => row.TryGetValue("key", out var key) && preview.Keys.Contains(key))
                .Take(3).Select(row => row.TryGetValue("translation", out var text) ? text : "")
                .Select(text => UiText.Msg("Trước: {0}" + "\n" + "Sau: {1}", text, text.Replace(previewFind, previewReplace, StringComparison.Ordinal)));
            CsvBulkPreview = UiText.Lines(new[] { CsvBulkPreview }.Concat(samples).ToArray());
        }
        if (preview.Count == 0)
        {
            ShowToast(CsvBulkPreview, "info");
            return;
        }

    }

    private async void ApplyBulkReplaceTranslation()
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return;
        if (!CsvBulkCanApply || string.IsNullOrWhiteSpace(CsvEditorPath))
            return;
        if (CsvEditorDirty)
        {
            ShowToast("Hãy lưu hoặc tải lại chỉnh sửa hiện tại trước khi áp dụng thay thế hàng loạt.", "warning");
            return;
        }
        var expectedPreview = _csvBulkPendingPreview!;
        var rows = BuildCsvSaveRows();
        var keys = ResolveCsvBulkKeys();
        var stamp = CsvBulkStamp();
        var (applyPath, applyFields, applyFind, applyReplace) = (CsvEditorPath, _csvEditorFields.ToList(), CsvBulkFind, CsvBulkReplace);
        var preview = await RunCsvEditorBackgroundAsync(() => TranslationCsvEditorService.PreviewReplace(
            applyPath, applyFields, rows, applyFind, applyReplace, keys));
        if (stamp != CsvBulkStamp() || !string.Equals(applyPath, CsvEditorPath, StringComparison.OrdinalIgnoreCase))
        {
            InvalidateCsvBulkPreview("Chuỗi tìm/thay, bộ lọc hoặc dữ liệu đã đổi trong lúc kiểm tra — hãy xem trước lại.");
            return;
        }
        if (!preview.Ok || preview.Count != expectedPreview.Count || preview.ReplacementCount != expectedPreview.ReplacementCount ||
            !preview.Keys.SequenceEqual(expectedPreview.Keys, StringComparer.OrdinalIgnoreCase))
        {
            InvalidateCsvBulkPreview(preview.Error ?? "CSV đã thay đổi — hãy xem trước thao tác lần nữa.");
            return;
        }
        var confirm = UiText.Lines(
            UiText.Msg("Thay thế {0} lần trong {1} dòng?", preview.ReplacementCount.ToString("N0"), preview.Count.ToString("N0")),
            "",
            UiText.Msg("Tìm: {0}" + "\n" + "Thay bằng: {1}", applyFind, applyReplace),
            "Chỉ sửa cột Bản dịch; cột Nguyên bản/key giữ nguyên.",
            "Ứng dụng sẽ tạo bản lưu khôi phục và kiểm tra file sau khi lưu.");
        if (AppDialogService.Show(confirm, "Xác nhận thay thế hàng loạt", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
            return;
        // The confirm dialog is modal but the boxes were editable before it opened; the exact
        // values the user confirmed (applyFind/applyReplace/keys) are the ones written below.

        var result = await RunCsvEditorBackgroundAsync(() => TranslationCsvEditorService.ReplaceTranslation(
            applyPath, applyFields, rows, applyFind, applyReplace, keys));
        if (!result.Ok)
        {
            CsvBulkPreview = result.Error ?? "Thay thế hàng loạt thất bại.";
            ShowToast(CsvBulkPreview, "error");
            AppendLog(CsvBulkPreview);
            return;
        }

        InvalidateCsvBulkPreview("Đã áp dụng thay thế hàng loạt.");

        _csvBulkLastBackup = result.BackupPath;
        UndoBulkReplaceCsvCommand.RaiseCanExecuteChanged();
        var keySet = new HashSet<string>(preview.Keys, StringComparer.OrdinalIgnoreCase);
        foreach (var row in _csvEditorRows)
        {
            if (!keySet.Contains(row.Key))
                continue;
            row.Translation = Regex.Replace(row.Translation, Regex.Escape(applyFind), _ => applyReplace, RegexOptions.IgnoreCase);
        }
        CsvEditorDirty = false;
        ApplyValidationFromBatch(result.IssuesByKey, result.IssuesDisplayByKey, result.Summary,
            result.PatchEligible, result.PatchBlocked, result.BatchActionable);
        CsvBulkPreview = UiText.Msg("Đã thay {0} lần trong {1} dòng. Có thể hoàn tác; đã tạo bản lưu khôi phục.", result.ReplacementCount.ToString("N0"), result.Count.ToString("N0"));
        AppendLog($"Bulk replace translation: {CsvBulkPreview} Backup={result.BackupPath}");
        ShowToast(CsvBulkPreview, result.PatchBlocked > 0 ? "warning" : "success");
        LoadCsvEditor(applyPath, reload: true);
    }

    private string CsvBulkSignature() => string.Join("\u001f", CsvEditorPath, CsvBulkFind, CsvBulkReplace, CsvBulkScope,
        CsvEditorSearch, CsvFilterMode);

    private void InvalidateCsvBulkPreview(string message)
    {
        _csvBulkPendingPreview = null;
        _csvBulkPendingSignature = "";
        CsvBulkPreview = message;
        Raise(nameof(CsvBulkCanApply));
        ApplyBulkReplaceCsvCommand?.RaiseCanExecuteChanged();
    }

    private async void UndoBulkReplace()
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return;
        if (string.IsNullOrWhiteSpace(CsvEditorPath) || string.IsNullOrWhiteSpace(_csvBulkLastBackup))
            return;
        if (CsvEditorDirty)
        {
            ShowToast("Hãy lưu hoặc tải lại chỉnh sửa hiện tại trước khi hoàn tác.", "warning");
            return;
        }
        if (AppDialogService.Show("Khôi phục CSV về trước lần thay thế hàng loạt gần nhất?", "Xác nhận hoàn tác", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
            return;
        var (undoPath, undoBackup) = (CsvEditorPath, _csvBulkLastBackup);
        var result = await RunCsvEditorBackgroundAsync(() => TranslationCsvEditorService.Undo(undoPath, undoBackup));
        if (!result.Ok)
        {
            ShowToast(result.Error ?? "Hoàn tác thất bại.", "error");
            return;
        }
        _csvBulkLastBackup = null;
        UndoBulkReplaceCsvCommand.RaiseCanExecuteChanged();
        CsvBulkPreview = UiText.Msg("Đã hoàn tác — khôi phục {0} dòng từ bản lưu khôi phục.", result.RowCount.ToString("N0"));
        AppendLog(CsvBulkPreview);
        ShowToast(CsvBulkPreview, "success");
        LoadCsvEditor(CsvEditorPath, reload: true);
    }

    // ---- One cell edit is a transaction: Enter/Tab commit it, Escape restores the value the cell had before the edit began ----
    // The translation binding writes through on every keystroke, so the row already holds the typed text when the grid reports the cancel.
    // The snapshot lets the cancel put the previous text back and leave every other pending edit (and the dirty state) exactly as it was.
    private CsvEditorRow? _cellEditRow;
    private string _cellEditOriginal = "";
    private bool _cellEditWasDirty, _cellEditKeyWasEdited;

    internal void BeginCsvCellEdit(CsvEditorRow? row)
    {
        if (row is null) return;
        _cellEditRow = row;
        _cellEditOriginal = row.Translation;
        _cellEditWasDirty = CsvEditorDirty;
        _cellEditKeyWasEdited = _csvEditorEditedKeys.Contains(row.Key);
    }

    internal void EndCsvCellEdit(CsvEditorRow? row, bool canceled)
    {
        var transaction = ReferenceEquals(row, _cellEditRow);
        var original = _cellEditOriginal;
        var wasDirty = _cellEditWasDirty;
        var keyWasEdited = _cellEditKeyWasEdited;
        _cellEditRow = null;
        if (!canceled || !transaction || row is null)
        {
            OnCsvEditorTranslationChanged(row);
            return;
        }
        if (!string.Equals(row.Translation, original, StringComparison.Ordinal)) row.Translation = original;
        if (!keyWasEdited) _csvEditorEditedKeys.Remove(row.Key);
        if (!wasDirty && CsvEditorDirty && _csvEditorEditedKeys.Count == 0) CsvEditorDirty = false;
        Raise(nameof(CsvEditorDirtySummary));
        Raise(nameof(CsvEditorGateStats));
    }

    internal void OnCsvEditorTranslationChanged(CsvEditorRow? row = null)
    {
        if (row is not null) _csvEditorEditedKeys.Add(row.Key);
        MarkCsvEditorDirty();
        Raise(nameof(CsvEditorDirtySummary));
        void RefreshSummary() { Raise(nameof(CsvEditorGateStats)); Raise(nameof(CsvEditorUserValidationMessage)); }
        if (Application.Current?.Dispatcher is { } dispatcher) dispatcher.BeginInvoke(new Action(RefreshSummary));
        else RefreshSummary();
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
        _csvEditorAllTranslationsEmpty = _csvEditorRows.Count > 0
            && result.ReasonCounts.TryGetValue("no_translation", out var emptyTranslations)
            && emptyTranslations >= _csvEditorRows.Count;
        Raise(nameof(CsvEditorGateStats));
        CsvEditorValidationMessage = _csvEditorAllTranslationsEmpty
            ? "Chưa có bản dịch — chuyển sang Dịch tự động để dịch CSV."
            : result.Summary;
        CsvEditorWarningSummary = BuildCsvWarningSummary(result);

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
        if (label == "no_translation")
            display = "";
        else if (result.IssuesDisplayByKey.TryGetValue(row.Key, out var d))
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

    internal Task<bool> SaveCsvEditorAsync()
    {
        // Direct-entry guard (the command's CanExecute is not the only caller): never write the CSV
        // while a worker task owns the package, or its later write would silently replace the edit.
        if (Busy)
        {
            CsvEditorStatus = "Chưa lưu — đang có tác vụ chạy trên gói này; hãy đợi tác vụ kết thúc hoặc hủy tác vụ rồi lưu lại.";
            CsvEditorValidationMessage = CsvEditorStatus;
            ShowToast(CsvEditorStatus, "warning");
            return Task.FromResult(false);
        }
        if (_csvEditorSaveTask is { IsCompleted: false } inFlight)
            return inFlight;
        if (CsvEditorSaving)
            return WaitForCsvEditorSaveAsync();
        _csvEditorSaveTask = SaveCsvEditorCoreAsync();
        return _csvEditorSaveTask;
    }

    private async Task<bool> SaveCsvEditorCoreAsync()
    {
        if (!CsvEditorDirty)
            return true;
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

        var path = CsvEditorPath;
        var fields = _csvEditorFields.ToList();
        var rows = BuildCsvSaveRows();
        var editGeneration = Volatile.Read(ref _csvEditorEditGeneration);
        var expectedSha256 = _csvEditorSourceSha256;
        if (string.IsNullOrWhiteSpace(expectedSha256))
        {
            CsvEditorStatus = "Chưa lưu — không xác minh được CSV gốc; hãy tải lại file.";
            CsvEditorValidationMessage = CsvEditorStatus;
            SetCsvEditorSaveError(path, "không xác minh được CSV gốc", CsvSaveKeepsDraftRecovery);
            ShowToast(CsvEditorStatus, "error");
            return false;
        }
        var duplicates = CsvEditorDiagnostics.FindDuplicateKeys(_csvEditorRows);
        if (duplicates.Count > 0)
        {
            var duplicateMessage = CsvEditorDiagnostics.FormatDuplicateMessage(duplicates);
            CsvEditorValidationMessage = duplicateMessage;
            CsvEditorStatus = UiText.Msg("Chưa lưu — {0} key trùng", duplicates.Count);
            SetCsvEditorSaveError(path, UiText.Msg("{0} key trùng — {1}", duplicates.Count, duplicateMessage), CsvSaveFixRecovery);
            AppendLog(duplicateMessage);
            ShowToast(duplicateMessage, "error");
            return false;
        }

        CsvEditorSaving = true;
        CsvEditorStatus = UiText.Msg("Đang kiểm tra và lưu {0} dòng…", rows.Count.ToString("N0"));
        CsvEditorValidationMessage = "Đang kiểm tra CSV trước khi lưu…";
        try
        {
            var attempt = await CsvEditorSaveExecutor(() => RunCsvEditorSave(path, fields, rows, expectedSha256));
            var unchanged = FinishCsvEditorSave(attempt, path, editGeneration);
            if (attempt.Save is { Ok: true, SourceSha256: not null }
                && string.Equals(path, CsvEditorPath, StringComparison.OrdinalIgnoreCase))
                await ValidateTranslationCsvAfterEditorSaveAsync(path);
            return unchanged;
        }
        catch (Exception ex)
        {
            CsvEditorStatus = UiText.Msg("Lưu thất bại: {0}", ex.Message);
            CsvEditorValidationMessage = CsvEditorStatus;
            SetCsvEditorSaveError(path, ex.Message, CsvSaveKeepsDraftRecovery);
            AppendLog(CsvEditorStatus);
            ShowToast(CsvEditorStatus, "error");
            return false;
        }
        finally
        {
            CsvEditorSaving = false;
            _csvEditorSaveTask = null;
        }
    }

    private static CsvEditorSaveAttempt RunCsvEditorSave(
        string path,
        IReadOnlyList<string> fields,
        IReadOnlyList<Dictionary<string, string>> rows,
        string? expectedSha256)
    {
        var validation = TranslationCsvEditorService.Validate(path, rows);
        if (!validation.Ok)
            return new CsvEditorSaveAttempt(validation, null);
        var save = TranslationCsvEditorService.Save(path, fields, rows, expectedSha256);
        return new CsvEditorSaveAttempt(validation, save);
    }

    private bool FinishCsvEditorSave(CsvEditorSaveAttempt attempt, string path, long editGeneration)
    {
        var validation = attempt.Validation;
        if (!validation.Ok)
        {
            CsvEditorValidationMessage = validation.Error ?? "Không thể lưu — kiểm tra thất bại";
            CsvEditorStatus = CsvEditorValidationMessage;
            AppendLog(CsvEditorValidationMessage);
            SetCsvEditorSaveError(path, CsvEditorValidationMessage, CsvSaveFixRecovery);
            ShowToast(CsvEditorValidationMessage, "error");
            return false;
        }
        var save = attempt.Save;
        if (save is not { Ok: true })
        {
            CsvEditorStatus = save?.Error ?? "Lưu thất bại";
            CsvEditorValidationMessage = CsvEditorStatus;
            AppendLog(CsvEditorStatus);
            SetCsvEditorSaveError(path, CsvEditorStatus, CsvSaveKeepsDraftRecovery);
            ShowToast(CsvEditorStatus, "error");
            return false;
        }

        if (string.IsNullOrWhiteSpace(save.SourceSha256))
        {
            CsvEditorStatus = "Lưu thất bại — không nhận được mã xác minh file đã lưu. Hãy tải lại CSV trước khi tiếp tục.";
            CsvEditorValidationMessage = CsvEditorStatus;
            AppendLog(CsvEditorStatus);
            SetCsvEditorSaveError(path, "không nhận được mã xác minh file đã lưu", CsvSaveKeepsDraftRecovery);
            ShowToast(CsvEditorStatus, "error");
            return false;
        }
        _csvEditorSourceSha256 = save.SourceSha256;
        if (string.Equals(path, CsvEditorPath, StringComparison.OrdinalIgnoreCase))
            CsvEditorSaveError = "";                      // only a successful save of this document clears a refusal
        // The Patch results describe ONE CSV revision. Saving the CSV the Patch page currently uses changes that revision, so its
        // preflight/counts/readiness/delivery text are dropped (the artifact on disk is untouched); saving some other CSV leaves them alone.
        var patchSource = TranslationCsvPath;
        var savedCurrentPatchCsv = !string.IsNullOrWhiteSpace(patchSource) && SameCsvPath(patchSource, path);
        if (string.IsNullOrWhiteSpace(patchSource) || savedCurrentPatchCsv)
        {
            if (savedCurrentPatchCsv) InvalidatePatchSourceState(csvRevisionChanged: true);
            TranslationCsvPath = path;
            if (savedCurrentPatchCsv) RefreshWorkflow();      // an older Patch folder no longer reads as "finished" for this revision
        }
        var unchanged = editGeneration == Volatile.Read(ref _csvEditorEditGeneration)
            && string.Equals(path, CsvEditorPath, StringComparison.OrdinalIgnoreCase);
        if (unchanged)
            CsvEditorDirty = false;
        var savedMsg = UiText.Msg("Đã lưu {0} dòng — {1}", save.RowCount.ToString("N0"), Path.GetFileName(path));
        CsvEditorStatus = unchanged
            ? UiText.Msg("{0} (UTF-8 BOM, giữ nguyên cột)", savedMsg)
            : UiText.Msg("{0}; còn chỉnh sửa mới chưa lưu", savedMsg);
        if (unchanged)
            ApplyValidationFromBatch(validation.IssuesByKey, validation.IssuesDisplayByKey, validation.Summary,
                validation.PatchEligible, validation.PatchBlocked, validation.BatchActionable);
        CsvEditorValidationMessage = validation.Summary;
        CsvEditorWarningSummary = BuildCsvWarningSummary(validation);
        StatusText = "Đã lưu CSV";
        AppendLog($"Đã lưu translation.csv: {path}");
        if (validation.HasWarnings)
            AppendLog($"Cảnh báo trước khi lưu: {validation.Summary}");
        if (CsvEditorWarningSummary.Length > 0)
            CsvEditorStatus = UiText.Compose(CsvEditorStatus, " — ", CsvEditorWarningSummary);
        ShowToast(CsvEditorWarningSummary.Length > 0 ? UiText.Compose(savedMsg, ". ", CsvEditorWarningSummary) : savedMsg,
            validation.HasWarnings ? "warning" : "success");
        LogExpanded = true;
        SaveCsvEditorCommand.RaiseCanExecuteChanged();
        return unchanged;
    }

    internal Task<bool> TrySaveCsvEditorForExitAsync() => SaveCsvEditorAsync();

    internal Task<bool> WaitForCsvEditorSaveAsync() => _csvEditorSaveTask ?? Task.FromResult(true);

    internal void DiscardCsvEditorChanges()
    {
        if (CsvEditorSaving) return;
        CsvEditorDirty = false;
        SaveCsvEditorCommand.RaiseCanExecuteChanged();
    }

    private List<Dictionary<string, string>> BuildCsvSaveRows() =>
        BuildCsvSaveRowsFrom(_csvEditorRows, _csvEditorFields);

    private async void ClearBlockedCsvTranslations()
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return;
        if (string.IsNullOrWhiteSpace(CsvEditorPath))
        {
            ShowToast("Chưa chọn file CSV.", "warning");
            return;
        }
        if (CsvEditorDirty)
        {
            ShowToast("Hãy lưu hoặc tải lại chỉnh sửa hiện tại trước khi xóa bản dịch lỗi.", "warning");
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

        var msg = UiText.Lines(
            UiText.Msg("Xóa cột translation của {0} dòng bị Patch Gate chặn?", preview.Count.ToString("N0")),
            "",
            "Chỉ xóa bản dịch — giữ nguyên key và source.",
            "File backup sẽ được tạo trước khi ghi.");
        if (AppDialogService.Show(msg, "Xác nhận xóa bản dịch lỗi", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
            return;

        var result = TranslationCsvEditorService.ClearBlocked(CsvEditorPath, _csvEditorFields, rows, targetKeys);
        if (!result.Ok)
        {
            ShowToast(result.Error ?? "Xóa bản dịch thất bại", "error");
            AppendLog(result.Error ?? "Xóa bản dịch lỗi thất bại");
            return;
        }

        var backupNote = string.IsNullOrWhiteSpace(result.BackupPath) ? "" : $" Backup: {result.BackupPath}";
        AppendLog($"Đã xóa bản dịch {result.Count:N0} dòng lỗi.{backupNote}");
        ShowToast(UiText.Msg("Đã xóa bản dịch {0} dòng — {1}", result.Count.ToString("N0"), UiText.Key(result.Summary)), "success");
        LoadCsvEditor(CsvEditorPath, reload: true);
    }

    internal async Task RetranslateBlockedCsvRowsAsync()
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return;
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
        var msg = UiText.Lines(
            UiText.Msg("Dịch lại {0} dòng bằng {1}?", preview.Count.ToString("N0"), engineLabel),
            "",
            "Chỉ các dòng đã chọn hoặc đang bị gate chặn (cấu trúc).",
            "Backup CSV sẽ được tạo trước khi ghi. Validation chạy sau khi dịch.");
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
            if (saveFirst == MessageBoxResult.Yes && !await SaveCsvEditorAsync())
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
        }, UiText.Msg("Đang dịch lại {0} dòng lỗi…", preview.Count.ToString("N0")));
    }

    private bool _csvEditorStaleOnDisk;

    /// <summary>True when the file changed on disk (for example MT finished) while the editor kept unsaved/different state.</summary>
    public bool CsvEditorStaleOnDisk
    {
        get => _csvEditorStaleOnDisk;
        private set => Set(ref _csvEditorStaleOnDisk, value);
    }

    private static string? TryHashFile(string path)
    {
        try
        {
            using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            return Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(stream)).ToLowerInvariant();
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            return null;
        }
    }

    /// <summary>
    /// After a translate task ends, a CSV opened in the editor DURING the run holds the rows it
    /// read mid-run (for example 2560/3000) and would stay stale until a manual Reload.  Refresh
    /// the editor only when it is clean, idle, shows exactly the translated file and no newer
    /// load/edit generation exists; otherwise keep the user's view and mark it stale.
    /// </summary>
    internal async Task RefreshCsvEditorAfterTranslateAsync(string translatedCsvPath)
    {
        var editorPath = CsvEditorPath;
        if (string.IsNullOrWhiteSpace(editorPath) || string.IsNullOrWhiteSpace(translatedCsvPath)
            || _csvEditorRows.Count == 0 || string.IsNullOrEmpty(_csvEditorSourceSha256))
            return;
        string a, b;
        try { a = Path.GetFullPath(editorPath); b = Path.GetFullPath(translatedCsvPath); }
        catch (Exception ex) when (ex is ArgumentException or NotSupportedException or PathTooLongException) { return; }
        if (!string.Equals(a, b, StringComparison.OrdinalIgnoreCase))
            return;
        var loadGeneration = Volatile.Read(ref _csvLoadGeneration);
        var editGeneration = Volatile.Read(ref _csvEditorEditGeneration);
        var openedSha = _csvEditorSourceSha256;
        var diskSha = await Task.Run(() => TryHashFile(a)).ConfigureAwait(true);
        if (diskSha is null || string.Equals(diskSha, openedSha, StringComparison.OrdinalIgnoreCase)
            || string.Equals(diskSha, _csvEditorSourceSha256, StringComparison.OrdinalIgnoreCase))
            return; // already showing exactly what is on disk (nothing to refresh, nothing stale)
        var unchangedSinceCompletion =
            loadGeneration == Volatile.Read(ref _csvLoadGeneration)
            && editGeneration == Volatile.Read(ref _csvEditorEditGeneration)
            && string.Equals(openedSha, _csvEditorSourceSha256, StringComparison.OrdinalIgnoreCase)
            && string.Equals(a, Path.GetFullPath(CsvEditorPath), StringComparison.OrdinalIgnoreCase);
        if (!unchangedSinceCompletion || CsvEditorDirty || CsvEditorLoading || CsvEditorSaving)
        {
            CsvEditorStaleOnDisk = true;
            CsvEditorStatus = "File CSV đã đổi sau khi dịch xong — bấm Tải lại để xem bản mới (thay đổi chưa lưu được giữ nguyên).";
            AppendLog("[csv] Editor giữ nguyên vì có thay đổi/lần tải mới; đã đánh dấu cũ so với file trên đĩa.");
            return;
        }
        AppendLog("[csv] Dịch xong — tải lại editor vì file trên đĩa đã đổi và editor chưa có thay đổi.");
        LoadCsvEditor(a, reload: true);
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

            if (row.IssueLabel == "no_translation")
                row.IssueDisplay = "";
            else if (issuesDisplay.TryGetValue(row.Key, out var display))
                row.IssueDisplay = display;
            else if (!string.IsNullOrWhiteSpace(row.IssueLabel) && row.IssueLabel != "no_translation")
                row.IssueDisplay = row.IssueLabel;
            else
                row.IssueDisplay = "";
        }
        CsvEditorPatchEligible = eligible;
        CsvEditorPatchBlocked = blocked;
        CsvEditorBatchActionable = actionable;
        _csvEditorAllTranslationsEmpty = _csvEditorRows.Count > 0
            && _csvEditorRows.All(row => string.IsNullOrWhiteSpace(row.Translation));
        Raise(nameof(CsvEditorGateStats));
        CsvEditorValidationMessage = _csvEditorAllTranslationsEmpty
            ? "Chưa có bản dịch — chuyển sang Dịch tự động để dịch CSV."
            : summary;
        ApplyCsvEditorFilter();
    }
}
