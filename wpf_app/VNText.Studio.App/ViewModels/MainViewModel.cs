using System.Collections.Concurrent;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Threading;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel : NotifyBase, IDisposable
{
    private readonly PythonWorkerHost _worker;
    private readonly IPathPickerService _pathPicker;
    private readonly AppSettings _settings;
    private string _inputPath = "";
    private string _outputPath = "";
    private string _selectedTab = WorkflowTabs.Extract;
    private string _workflowStep = WorkflowTabs.Extract;
    private string _extractStepState = WorkflowStepState.Current;
    private string _translateStepState = WorkflowStepState.Pending;
    private string _patchStepState = WorkflowStepState.Pending;
    private string _stepStatusLine = "Bước 1/3: Chọn game — chưa có đường dẫn game / asset";
    private string _patchDeliveryLabel = "";
    private string _patchInstallInstructions = "";
    private string _diagnosticStatusLine = "";
    private string _diagnosticPath = "";
    private string _diagnosticStage = "";
    private string _diagnosticRootCause = "";
    private int? _diagnosticAffectedCount;
    private string _diagnosticAction = "";
    private string _diagnosticStatus = "";
    private string _heroTitle = "Lấy text";
    private string _heroIcon = "extract";
    private string _heroHint = "Chọn game bên dưới, rồi bấm «Lấy text» để xuất CSV.";
    private string _progressSubtitle = "Chưa bắt đầu";
    private string _logSubtitle = "Nhật ký hoạt động sẽ hiển thị ở đây.";
    private string _statusText = "Sẵn sàng";
    private bool _translateLastRunCancelled;
    private string _version = "vunknown";
    private bool _busy;
    private bool _exitAfterTask;
    private bool _progressExpanded;
    private bool _logExpanded;
    private bool _advancedToolsExpanded = true;
    private bool _separateReview = true;
    private bool _overwriteTranslation;
    private bool _humanReviewRequired;
    private string _extractLevel = ExtractLevels.Balanced;
    private string _renpySdkPath = "";
    private string _renpySdkAction = "auto";
    private string _renpySdkError = "";
    private CancellationTokenSource? _renpyDetectionCancellation;
    private bool _renpySdkOptionsVisible;
    private string _translationModelDir = "";
    private bool _translateButtonGreen = true;
    private bool _readyForPatch;
    private bool _hasExtract;
    private bool _hasTranslations;
    private string _translationCsvPath = "";
    private string _csvValidationMessage = "";
    private bool _csvValidationOk;
    private bool _translatePackageReady;
    private bool _translationModelUnavailable;
    private bool _translationModelChecked;
    private bool _translatePackageChecking;
    private string _translatePackageMessage = "";
    private int _translatePackageRowCount;
    private int _translatePackageTranslatedCount;
    private string _translateReadinessPath = "";
    private int _translateReadinessEpoch;
    private string _patchPreflightMessage = "";
    private bool _patchPreflightOk;
    private bool _patchPreflightEvaluated;
    private bool _patchResultsAvailable;
    private bool _patchResultsExpanded;
    private bool _patchDeliveryReady;
    private int _patchEligibleCount;
    private int _patchBlockedCount;
    private int _progressPercent;
    private int _extractProgressPercent;
    private int _translateProgressPercent;
    private string _translateProgressStep = "Chưa bắt đầu";
    private string _translateProgressItem = "";
    private string _translateProgressEta = "";
    private readonly Stopwatch _translateTaskStopwatch = new();
    private readonly Stopwatch _extractTaskStopwatch = new();
    private readonly Stopwatch _patchTaskStopwatch = new();
    private DispatcherTimer? _translateElapsedTimer;
    private DispatcherTimer? _workflowElapsedTimer;
    private bool _translateProgressRunning;
    private int _patchProgressPercent;
    private string _extractProgressText = "";
    private string _translateProgressText = "";
    private string _patchProgressText = "";
    private string _extractProgressStep = "Chưa bắt đầu";
    private string _extractProgressItem = "";
    private string _extractProgressEta = "";
    private string _patchProgressStep = "Chưa bắt đầu";
    private string _patchProgressItem = "";
    private string _patchProgressEta = "";
    private string _cloudRepairPackagePath = "";
    private bool _cloudRepairPackageReady;
    private string _pendingCloudRepairImportOutputPath = "";
    private string _pendingExternalTranslationImportTargetPath = "";
    private string _activeTaskId = "";
    private bool _updateAvailable;
    private string _updateStatus = "";
    private string _githubUpdateStatus = "Kiểm tra phiên bản mới khi bạn sẵn sàng.";
    private GitHubUpdateState _githubUpdateState = GitHubUpdateState.Unconfigured;
    private GitHubUpdateCheckResult _githubUpdateResult = new(GitHubUpdateState.Unconfigured);
    private GitHubUpdatePackageLease? _githubUpdatePackageLease;
    private readonly HttpMessageHandler? _githubHttpHandler;
    private readonly string? _updateInstallRoot;
    private CancellationTokenSource? _githubUpdateCancellation;
    private Task _githubUpdateCheckTask = Task.CompletedTask;
    private bool _githubUpdateChecking;
    private string? _runningTask;
    private string? _lastCompletedTask;
    private CancellationTokenSource? _cancelWatchdog;
    private int _refreshEpoch;
    private WorkerEvent? _pendingProgressEvent;
    private int _progressDispatchPosted;
    private readonly ConcurrentQueue<WorkerEvent> _pendingLogEvents = new();
    private readonly HashSet<string> _terminalTaskIds = new(StringComparer.Ordinal);
    private readonly Queue<string> _terminalTaskIdOrder = new();
    private int _logDispatchPosted;
    private int _disposed;
    private ReleaseNotesCacheEntry? _selectedReleaseNotesEntry;
    public ObservableCollection<ReleaseNotesCacheEntry> ReleaseNotesHistory { get; } = [];

    public MainViewModel()
        : this(new WpfPathPickerService(), new PythonWorkerHost(), startWorker: true)
    {
    }

    internal MainViewModel(IPathPickerService pathPicker, PythonWorkerHost worker, bool startWorker,
        HttpMessageHandler? githubHttpHandler = null, string? updateInstallRoot = null)
    {
        _pathPicker = pathPicker;
        _worker = worker;
        _githubHttpHandler = githubHttpHandler;
        _updateInstallRoot = updateInstallRoot;
        _settings = AppSettingsStore.Load(out var settingsError);
        foreach (var entry in _settings.ReleaseNotesHistory)
            ReleaseNotesHistory.Add(entry);
        if (!string.IsNullOrWhiteSpace(_settings.DownloadedUpdateVersion) && !string.IsNullOrWhiteSpace(_settings.DownloadedUpdateNotes)
            && ReleaseNotesHistory.All(entry => entry.Version != _settings.DownloadedUpdateVersion))
            ReleaseNotesHistory.Insert(0, new ReleaseNotesCacheEntry { Version = _settings.DownloadedUpdateVersion,
                Notes = _settings.DownloadedUpdateNotes[..Math.Min(16000, _settings.DownloadedUpdateNotes.Length)] });
        _selectedReleaseNotesEntry = ReleaseNotesHistory.FirstOrDefault();
        _settingsStatus = settingsError;
        _separateReview = _settings.SeparateReview;
        _overwriteTranslation = _settings.OverwriteTranslation;
        _humanReviewRequired = _settings.HumanReviewRequired;
        // Owner-selected product default: exhaustive extraction. Older persisted choices are ignored.
        _extractLevel = ExtractLevels.Exhaustive;
        LogLines = new ObservableCollection<string>();
        if (!string.IsNullOrWhiteSpace(settingsError)) AppendLog(settingsError);
        LoadVersion();
        NavigateTabCommand = new RelayCommand(p => NavigateTab(p as string));
        AnalyzeCommand = new RelayCommand(_ => RunAnalyze(), _ => !Busy && !string.IsNullOrWhiteSpace(InputPath) && !string.IsNullOrWhiteSpace(OutputPath));
        RunExtractCommand = new RelayCommand(_ => RunExtract(), _ => !Busy && !CsvEditorSaving && !CsvEditorDirty);
        RunTranslateCommand = new RelayCommand(_ => RunTranslate(), _ => CanStartTranslate());
        ExportCloudRepairPackageCommand = new RelayCommand(_ => ExportCloudRepairPackage(), _ => !Busy && !CsvEditorSaving && !CsvEditorDirty);
        ImportExistingTranslationCommand = new RelayCommand(_ => ImportExistingTranslation(), _ => !Busy && !CsvEditorSaving && !CsvEditorDirty);
        RunPatchCommand = new RelayCommand(_ => RunPatch(), _ => !Busy && !CsvEditorSaving && !CsvEditorDirty && ReadyForPatch);
        CancelCommand = new RelayCommand(_ => CancelTask(), _ => Busy);
        CancelAndExitCommand = new RelayCommand(_ => CancelAndExit(), _ => Busy);
        ChooseInputCommand = new RelayCommand(_ => ChooseInput(), _ => !Busy && !CsvEditorLoading && !CsvEditorSaving);
        ChooseOutputCommand = new RelayCommand(_ => ChooseOutput(), _ => !Busy && !CsvEditorLoading && !CsvEditorSaving);
        OpenInputCommand = new RelayCommand(_ => OpenInput(), _ => CanOpenInput());
        OpenOutputCommand = new RelayCommand(_ => OpenOutput(), _ => CanOpenOutput());
        ChooseTranslationCsvCommand = new RelayCommand(_ => ChooseTranslationCsv(), _ => !Busy && !CsvEditorSaving && !CsvEditorDirty);
        ChooseRenpySdkCommand = new RelayCommand(_ => ChooseRenpySdk(), _ => !Busy);
        DownloadRenpySdkCommand = new RelayCommand(_ => RunRenpySdkAction("download"), _ => !Busy);
        ContinueWithoutRenpySdkCommand = new RelayCommand(_ => RunRenpySdkAction("none"), _ => !Busy);
        RecheckUpdateCommand = new RelayCommand(_ => StartGitHubUpdateCheck(metadataOnly: true, manual: true), _ => !Busy && !CsvEditorDirty && !_githubUpdateChecking && !DownloadingUpdate);
        ApplyUpdateCommand = new RelayCommand(_ => ApplyWpfUpdate(), _ => !Busy && _updateAvailable);
        ApplyGitHubUpdateCommand = new RelayCommand(_ => ApplyGitHubUpdate(), _ => !Busy && GitHubApplyEnabled && !_githubUpdateChecking);
        OpenGitHubSetupCommand = new RelayCommand(_ => OpenGitHubSetup(), _ => GitHubSetupRequired && !_githubUpdateChecking);
        ValidateTranslationCsvCommand = new RelayCommand(_ => ValidateTranslationCsv(silent: false));
        ToggleProgressCommand = new RelayCommand(_ => ProgressExpanded = !ProgressExpanded);
        ToggleLogCommand = new RelayCommand(_ => LogExpanded = !LogExpanded);
        ToggleAdvancedToolsCommand = new RelayCommand(_ => AdvancedToolsExpanded = !AdvancedToolsExpanded);
        InitImageTextCommands();
        InitCsvEditorCommands();
        InitGlossaryCommands();

        OutputPath = WorkerPaths.IsReleaseLayout()
            ? Path.Combine(WorkerPaths.AppDataRoot(), "output")
            : Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "VNText_Output",
                "Unity_Translation_Package");

        _worker.EventReceived += OnWorkerEvent;
        RefreshWorkflow();
        if (startWorker)
            _ = InitializeWorkerAsync();
    }

    public ObservableCollection<string> LogLines { get; }

    public string SelectedTab
    {
        get => _selectedTab;
        set
        {
            if (Set(ref _selectedTab, value))
            {
                UpdateHeroForTab();
                if (value == WorkflowTabs.EditCsv)
                    OnCsvEditorTabSelected();
                // Do not cancel in-flight CSV load when leaving the tab — populate yields
                // and must be allowed to finish for large packages (~27k rows).
            }
        }
    }

    public string InputPath
    {
        get => _inputPath;
        set
        {
            if (Set(ref _inputPath, value))
            {
                Raise(nameof(InputDisplay));
                Raise(nameof(ExtractStatusText));
                InvalidateAnalyzeIfInputsChanged();
                RefreshWorkflow();
                RefreshRenpySdkOptionsVisibility(value);
                OpenInputCommand?.RaiseCanExecuteChanged();
                AnalyzeCommand?.RaiseCanExecuteChanged();
                RefreshImageCommands();
            }
        }
    }

    public string OutputPath
    {
        get => _outputPath;
        set
        {
            if (Set(ref _outputPath, value))
            {
                Raise(nameof(OutputDisplay));
                InvalidateAnalyzeIfInputsChanged();
                RefreshWorkflow();
                RefreshTranslateReadiness();
                OpenOutputCommand?.RaiseCanExecuteChanged();
                AnalyzeCommand?.RaiseCanExecuteChanged();
                RefreshImageCommands();
            }
        }
    }

    public string TranslationCsvPath
    {
        get => _translationCsvPath;
        private set
        {
            if (Set(ref _translationCsvPath, value))
            {
                _translateLastRunCancelled = false;
                Raise(nameof(TranslationCsvDisplay));
                LoadPackageGlossary();
                RefreshTranslateReadiness();
            }
        }
    }

    public string TranslationCsvDisplay =>
        string.IsNullOrWhiteSpace(TranslationCsvPath)
            ? "Dùng translation.csv trong thư mục xuất…"
            : TranslationCsvPath;

    public string CloudRepairPackagePath
    {
        get => _cloudRepairPackagePath;
        private set
        {
            if (Set(ref _cloudRepairPackagePath, value))
                Raise(nameof(CloudRepairPackageDisplay));
        }
    }

    public string CloudRepairPackageDisplay =>
        CloudRepairPackageReady && File.Exists(CloudRepairPackagePath)
            ? CloudRepairPackagePath
            : "";

    public bool CloudRepairPackageReady
    {
        get => _cloudRepairPackageReady;
        private set
        {
            if (Set(ref _cloudRepairPackageReady, value))
                Raise(nameof(CloudRepairPackageDisplay));
        }
    }

    public bool PatchResultsAvailable
    {
        get => _patchResultsAvailable;
        private set => Set(ref _patchResultsAvailable, value);
    }

    public bool PatchResultsExpanded
    {
        get => _patchResultsExpanded;
        set => Set(ref _patchResultsExpanded, value);
    }

    public bool PatchPreflightEvaluated
    {
        get => _patchPreflightEvaluated;
        private set => Set(ref _patchPreflightEvaluated, value);
    }

    public bool PatchDeliveryReady
    {
        get => _patchDeliveryReady;
        private set => Set(ref _patchDeliveryReady, value);
    }

    public string CsvValidationMessage
    {
        get => _csvValidationMessage;
        private set => Set(ref _csvValidationMessage, value);
    }

    public bool CsvValidationOk
    {
        get => _csvValidationOk;
        private set => Set(ref _csvValidationOk, value);
    }

    public string PatchPreflightMessage
    {
        get => _patchPreflightMessage;
        private set => Set(ref _patchPreflightMessage, value);
    }

    public bool PatchPreflightOk
    {
        get => _patchPreflightOk;
        private set => Set(ref _patchPreflightOk, value);
    }

    public int PatchEligibleCount
    {
        get => _patchEligibleCount;
        private set => Set(ref _patchEligibleCount, value);
    }

    public int PatchBlockedCount
    {
        get => _patchBlockedCount;
        private set => Set(ref _patchBlockedCount, value);
    }

    public string InputDisplay => string.IsNullOrWhiteSpace(InputPath) ? UiText.Translate("Chọn thư mục game...") : InputPath;
    public string OutputDisplay => string.IsNullOrWhiteSpace(OutputPath) ? "Chọn thư mục xuất..." : OutputPath;

    public string CurrentWorkflowStep
    {
        get => _workflowStep;
        private set => Set(ref _workflowStep, value);
    }

    public string ExtractStepState
    {
        get => _extractStepState;
        private set => Set(ref _extractStepState, value);
    }

    public string TranslateStepState
    {
        get => _translateStepState;
        private set => Set(ref _translateStepState, value);
    }

    public string PatchStepState
    {
        get => _patchStepState;
        private set => Set(ref _patchStepState, value);
    }

    public string StepStatusLine
    {
        get => _stepStatusLine;
        private set => Set(ref _stepStatusLine, value);
    }

    public string PatchDeliveryLabel
    {
        get => _patchDeliveryLabel;
        private set => Set(ref _patchDeliveryLabel, value);
    }

    public string PatchInstallInstructions
    {
        get => _patchInstallInstructions;
        private set => Set(ref _patchInstallInstructions, value);
    }

    public string DiagnosticStatusLine
    {
        get => _diagnosticStatusLine;
        private set => Set(ref _diagnosticStatusLine, value);
    }

    public string DiagnosticPath
    {
        get => _diagnosticPath;
        private set => Set(ref _diagnosticPath, value);
    }

    public string DiagnosticStage
    {
        get => _diagnosticStage;
        private set => Set(ref _diagnosticStage, value);
    }

    public string DiagnosticRootCause
    {
        get => _diagnosticRootCause;
        private set => Set(ref _diagnosticRootCause, value);
    }

    public int? DiagnosticAffectedCount
    {
        get => _diagnosticAffectedCount;
        private set => Set(ref _diagnosticAffectedCount, value);
    }

    public string DiagnosticAction
    {
        get => _diagnosticAction;
        private set => Set(ref _diagnosticAction, value);
    }

    public string DiagnosticStatus
    {
        get => _diagnosticStatus;
        private set => Set(ref _diagnosticStatus, value);
    }

    public string HeroTitle
    {
        get => UiText.Translate(_heroTitle);
        private set => Set(ref _heroTitle, value);
    }

    public string HeroIcon
    {
        get => _heroIcon;
        private set => Set(ref _heroIcon, value);
    }

    public string HeroHint
    {
        get => UiText.Translate(_heroHint);
        private set => Set(ref _heroHint, value);
    }

    public bool TranslateButtonGreen
    {
        get => _translateButtonGreen;
        private set => Set(ref _translateButtonGreen, value);
    }

    public bool ReadyForPatch
    {
        get => _readyForPatch;
        private set
        {
            if (Set(ref _readyForPatch, value)) RunPatchCommand?.RaiseCanExecuteChanged();
        }
    }

    public bool HasExtract
    {
        get => _hasExtract;
        private set => Set(ref _hasExtract, value);
    }

    public string ProgressSubtitle
    {
        get => _progressSubtitle;
        set
        {
            if (Set(ref _progressSubtitle, value))
                Raise(nameof(ExtractProgressSubtitle));
        }
    }

    public string ExtractProgressSubtitle => _extractProgressText;
    public string ExtractProgressHeading => UiText.Translate(
        Busy && _runningTask == "extract" && RenpySdkAction == "download" ? "Tiến trình tải SDK và lấy text" : "Tiến trình quét");
    public string ExtractProgressStep => _extractProgressStep;
    public string ExtractProgressItem => string.IsNullOrWhiteSpace(_extractProgressItem) ? "—" : _extractProgressItem;
    public string ExtractProgressEta => _extractProgressEta;
    public bool ExtractProgressHasEta => !string.IsNullOrWhiteSpace(_extractProgressEta);
    public bool ExtractProgressActive => Busy && _runningTask is "extract" or "analyze" or "image_inventory" or "image_extract";
    public string ExtractProgressElapsed => $"Đã chạy {ProgressEtaFormatter.Format(_extractTaskStopwatch.Elapsed.TotalSeconds.ToString(System.Globalization.CultureInfo.InvariantCulture))}";
    public string TranslateProgressSubtitle => _translateProgressText;
    public string TranslateWorkflowStatusText => Busy && OwnsTranslateProgressTask(_runningTask)
        ? (string.IsNullOrWhiteSpace(_translateProgressText) ? "Đang xử lý…" : _translateProgressText)
        : TranslateReadinessText;
    public string TranslateProgressStep => _translateProgressStep;
    public string TranslateProgressItem => string.IsNullOrWhiteSpace(_translateProgressItem) ? "—" : _translateProgressItem;
    public string TranslateProgressEta => _translateProgressEta;
    public bool TranslateProgressHasEta => !string.IsNullOrWhiteSpace(_translateProgressEta);
    public bool TranslateProgressActive => Busy && OwnsTranslateProgressTask(_runningTask);
    public string TranslateProgressElapsed => $"Đã chạy {ProgressEtaFormatter.Format(_translateTaskStopwatch.Elapsed.TotalSeconds.ToString(System.Globalization.CultureInfo.InvariantCulture))}";
    public string PatchProgressSubtitle => _patchProgressText;
    public string PatchProgressStep => _patchProgressStep;
    public string PatchProgressItem => string.IsNullOrWhiteSpace(_patchProgressItem) ? "—" : _patchProgressItem;
    public string PatchProgressEta => _patchProgressEta;
    public bool PatchProgressHasEta => !string.IsNullOrWhiteSpace(_patchProgressEta);
    public bool PatchProgressActive => Busy && _runningTask is "patch" or "image_delivery" or "image_apply" or "image_rollback";
    public string PatchProgressElapsed => $"Đã chạy {ProgressEtaFormatter.Format(_patchTaskStopwatch.Elapsed.TotalSeconds.ToString(System.Globalization.CultureInfo.InvariantCulture))}";
    public int ExtractProgressPercent { get => _extractProgressPercent; private set => Set(ref _extractProgressPercent, value); }
    public int TranslateProgressPercent { get => _translateProgressPercent; private set => Set(ref _translateProgressPercent, value); }
    public int PatchProgressPercent { get => _patchProgressPercent; private set => Set(ref _patchProgressPercent, value); }

    public string ExtractStatusText => Busy && _runningTask is not ("extract" or "analyze" or "image_inventory" or "image_extract")
        ? ""
        : StatusText == "Sẵn sàng"
            ? (string.IsNullOrWhiteSpace(InputPath) ? "" : "Sẵn sàng lấy text")
            : StatusText;

    public string LogSubtitle
    {
        get => _logSubtitle;
        set => Set(ref _logSubtitle, value);
    }

    public string StatusText
    {
        get => _statusText;
        set
        {
            if (Set(ref _statusText, value))
            {
                Raise(nameof(ExtractStatusText));
                Raise(nameof(TranslateReadinessText));
                Raise(nameof(TranslateWorkflowStatusText));
            }
        }
    }

    public string Version
    {
        get => _version;
        set
        {
            if (Set(ref _version, value))
                Raise(nameof(CurrentVersionDisplay));
        }
    }

    public string CurrentVersionDisplay => Version.TrimStart('v');

    public bool SeparateReview
    {
        get => _separateReview;
        set
        {
            if (Set(ref _separateReview, value))
            {
                _settings.SeparateReview = value;
                SaveSettings();
            }
        }
    }

    public bool OverwriteTranslation
    {
        get => _overwriteTranslation;
        set
        {
            if (Set(ref _overwriteTranslation, value))
            {
                _settings.OverwriteTranslation = value;
                SaveSettings();
            }
        }
    }

    public bool HumanReviewRequired
    {
        get => _humanReviewRequired;
        set
        {
            if (Set(ref _humanReviewRequired, value))
            {
                _settings.HumanReviewRequired = value;
                SaveSettings();
            }
        }
    }

    public bool UpdateEnabled => _updateAvailable;
    public bool UpdateCheckEnabled => true;
    public string UpdateStatus => _updateStatus;
    public string GitHubUpdateStatus => _githubUpdateStatus;
    public bool GitHubUpdateChecking => _githubUpdateChecking;
    public string GitHubUpdateVersion => string.IsNullOrWhiteSpace(_githubUpdateResult.Version) ? "" : $"v{_githubUpdateResult.Version}";
    public bool GitHubUpdateVersionVisible => _githubUpdateState == GitHubUpdateState.UpdateAvailable;
    public string GitHubUpdateButtonText => _githubUpdateChecking
        ? "Đang kiểm tra…"
        : _githubUpdateState == GitHubUpdateState.UpdateAvailable ? "Cài cập nhật"
        : _githubUpdateState == GitHubUpdateState.Current ? "Đã cập nhật"
        : _githubUpdateState is GitHubUpdateState.Offline or GitHubUpdateState.Timeout or
            GitHubUpdateState.RateLimited or GitHubUpdateState.InvalidMetadata or GitHubUpdateState.InvalidPackage
            ? "Kiểm tra lại"
        : "Kiểm tra cập nhật";
    public bool GitHubUpdateButtonEnabled => !_githubUpdateChecking && !Busy &&
        _githubUpdateState != GitHubUpdateState.Current;
    public GitHubUpdateState GitHubUpdateState => _githubUpdateState;
    public bool GitHubApplyEnabled => _githubUpdateState == GitHubUpdateState.UpdateAvailable &&
        _githubUpdatePackageLease is not null;
    public bool GitHubSetupRequired => _githubUpdateState == GitHubUpdateState.SetupRequired &&
        !string.IsNullOrWhiteSpace(_githubUpdateResult.ReleasesUrl);
    internal Task GitHubUpdateCheckTask => _githubUpdateCheckTask;

    // Probe-only override for deterministic CT2 workflow verification.
    internal string TranslationModelDir
    {
        get => _translationModelDir;
        set => _translationModelDir = value ?? "";
    }

    public string RenpySdkPath
    {
        get => _renpySdkPath;
        private set
        {
            if (Set(ref _renpySdkPath, value ?? ""))
                Raise(nameof(RenpySdkStatus));
        }
    }

    public string RenpySdkAction
    {
        get => _renpySdkAction;
        private set
        {
            if (Set(ref _renpySdkAction, value ?? "auto"))
            {
                Raise(nameof(RenpySdkStatus));
                Raise(nameof(ExtractProgressHeading));
            }
        }
    }

    public string RenpySdkError
    {
        get => _renpySdkError;
        private set
        {
            if (Set(ref _renpySdkError, value ?? ""))
                Raise(nameof(RenpySdkStatus));
        }
    }

    public bool RenpySdkOptionsVisible
    {
        get => _renpySdkOptionsVisible;
        private set => Set(ref _renpySdkOptionsVisible, value);
    }

    public string RenpySdkStatus => RenpySdkRecovery.FormatStatus(RenpySdkAction, RenpySdkError);

    private void ExposeRenpySdkRecoveryOptions()
    {
        var pending = Interlocked.Exchange(ref _renpyDetectionCancellation, null);
        pending?.Cancel();
        RenpySdkOptionsVisible = true;
        pending?.Dispose();
    }

    private void RefreshRenpySdkOptionsVisibility(string inputPath)
    {
        var previous = Interlocked.Exchange(ref _renpyDetectionCancellation, null);
        previous?.Cancel();
        RenpySdkOptionsVisible = false;
        RenpySdkAction = "auto";
        RenpySdkError = "";
        if (string.IsNullOrWhiteSpace(inputPath))
            return;

        var cancellation = new CancellationTokenSource();
        _renpyDetectionCancellation = cancellation;
        _ = UpdateRenpySdkOptionsVisibilityAsync(inputPath, cancellation);
    }

    private async Task UpdateRenpySdkOptionsVisibilityAsync(string inputPath, CancellationTokenSource cancellation)
    {
        try
        {
            var detected = await Task.Run(
                () => RenpyGameDetector.HasSdkRecoveryEvidence(inputPath, cancellation.Token),
                cancellation.Token);
            if (!cancellation.IsCancellationRequested
                && ReferenceEquals(Volatile.Read(ref _renpyDetectionCancellation), cancellation))
                RenpySdkOptionsVisible = detected;
        }
        catch (OperationCanceledException)
        {
        }
        catch
        {
            if (ReferenceEquals(Volatile.Read(ref _renpyDetectionCancellation), cancellation))
                RenpySdkOptionsVisible = false;
        }
        finally
        {
            Interlocked.CompareExchange(ref _renpyDetectionCancellation, null, cancellation);
            cancellation.Dispose();
        }
    }

    public IReadOnlyList<ExtractLevelOption> ExtractLevelOptions => ExtractLevels.Options;

    public string ExtractLevel
    {
        get => _extractLevel;
        set => Set(ref _extractLevel, ExtractLevels.Exhaustive);
    }

    public bool Busy
    {
        get => _busy;
        set
        {
            if (Set(ref _busy, value))
            {
                Raise(nameof(ExtractProgressActive));
                Raise(nameof(ExtractProgressHeading));
                Raise(nameof(TranslateProgressActive));
                Raise(nameof(PatchProgressActive));
                Raise(nameof(TranslateReadinessText));
                Raise(nameof(TranslateWorkflowStatusText));
                RunExtractCommand.RaiseCanExecuteChanged();
                ChooseInputCommand.RaiseCanExecuteChanged();
                ChooseOutputCommand.RaiseCanExecuteChanged();
                ChooseRenpySdkCommand.RaiseCanExecuteChanged();
                AnalyzeCommand.RaiseCanExecuteChanged();
                RunTranslateCommand.RaiseCanExecuteChanged();
                ExportCloudRepairPackageCommand.RaiseCanExecuteChanged();
                ImportExistingTranslationCommand.RaiseCanExecuteChanged();
                RunPatchCommand.RaiseCanExecuteChanged();
                DownloadRenpySdkCommand.RaiseCanExecuteChanged();
                ContinueWithoutRenpySdkCommand.RaiseCanExecuteChanged();
                CancelCommand.RaiseCanExecuteChanged();
                CancelAndExitCommand.RaiseCanExecuteChanged();
                RetranslateBlockedCsvCommand.RaiseCanExecuteChanged();
                SaveCsvEditorCommand.RaiseCanExecuteChanged();
                Raise(nameof(CsvEditorGridReadOnly));
                Raise(nameof(CsvEditorLockText));
                RecheckUpdateCommand.RaiseCanExecuteChanged();
                ApplyUpdateCommand.RaiseCanExecuteChanged();
                ApplyGitHubUpdateCommand.RaiseCanExecuteChanged();
                OpenGitHubSetupCommand.RaiseCanExecuteChanged();
                RefreshImageCommands();
                if (!value)
                {
                    if (_translateProgressRunning)
                    {
                        _translateElapsedTimer?.Stop();
                        _translateTaskStopwatch.Stop();
                        _translateProgressRunning = false;
                        Raise(nameof(TranslateProgressElapsed));
                    }
                    _workflowElapsedTimer?.Stop();
                    if (_extractTaskStopwatch.IsRunning) { _extractTaskStopwatch.Stop(); Raise(nameof(ExtractProgressElapsed)); }
                    if (_patchTaskStopwatch.IsRunning) { _patchTaskStopwatch.Stop(); Raise(nameof(PatchProgressElapsed)); }
                    ResumeDeferredOffer();
                    _runningTask = null;
                    RefreshWorkflow();
                }
                RaiseGitHubUpdateCard();
            }
        }
    }

    public bool ProgressExpanded
    {
        get => _progressExpanded;
        set => Set(ref _progressExpanded, value);
    }

    public bool LogExpanded
    {
        get => _logExpanded;
        set => Set(ref _logExpanded, value);
    }

    public bool AdvancedToolsExpanded
    {
        get => _advancedToolsExpanded;
        set => Set(ref _advancedToolsExpanded, value);
    }

    public int ProgressPercent
    {
        get => _progressPercent;
        set => Set(ref _progressPercent, value);
    }

    private void SetOwnedProgress(string? task, int? percent = null, string? text = null)
    {
        switch (task)
        {
            case "extract": case "analyze": case "image_inventory": case "image_extract":
                if (percent.HasValue) ExtractProgressPercent = percent.Value;
                if (text is not null) { _extractProgressText = text; Raise(nameof(ExtractProgressSubtitle)); }
                break;
            case "translate": case "image_batch": case "image_render": case "cloud_export": case "cloud_import": case "external_translation_import":
                if (percent.HasValue) TranslateProgressPercent = percent.Value;
                if (text is not null) { _translateProgressText = text; Raise(nameof(TranslateProgressSubtitle)); Raise(nameof(TranslateReadinessText)); Raise(nameof(TranslateWorkflowStatusText)); }
                break;
            case "patch": case "image_delivery": case "image_apply": case "image_rollback":
                if (percent.HasValue) PatchProgressPercent = percent.Value;
                if (text is not null) { _patchProgressText = text; Raise(nameof(PatchProgressSubtitle)); }
                break;
        }
    }

    public RelayCommand NavigateTabCommand { get; }
    public RelayCommand AnalyzeCommand { get; }
    public RelayCommand RunExtractCommand { get; }
    public RelayCommand RunTranslateCommand { get; }
    public RelayCommand ExportCloudRepairPackageCommand { get; }
    public RelayCommand ImportExistingTranslationCommand { get; }
    public RelayCommand RunPatchCommand { get; }
    public RelayCommand CancelCommand { get; }
    public RelayCommand CancelAndExitCommand { get; }
    public event EventHandler? ExitAfterTaskRequested;
    public RelayCommand ChooseInputCommand { get; }
    public RelayCommand ChooseOutputCommand { get; }
    public RelayCommand OpenInputCommand { get; }
    public RelayCommand OpenOutputCommand { get; }
    public RelayCommand ChooseTranslationCsvCommand { get; }
    public RelayCommand ChooseRenpySdkCommand { get; }
    public RelayCommand DownloadRenpySdkCommand { get; }
    public RelayCommand ContinueWithoutRenpySdkCommand { get; }
    public RelayCommand RecheckUpdateCommand { get; }
    public RelayCommand ApplyUpdateCommand { get; }
    public RelayCommand ApplyGitHubUpdateCommand { get; }
    public RelayCommand OpenGitHubSetupCommand { get; }
    public RelayCommand ValidateTranslationCsvCommand { get; }
    public RelayCommand ToggleProgressCommand { get; }
    public RelayCommand ToggleLogCommand { get; }
    public RelayCommand ToggleAdvancedToolsCommand { get; }
    public RelayCommand AddGlossaryEntryCommand { get; private set; } = null!;
    public RelayCommand RemoveGlossaryEntryCommand { get; private set; } = null!;

    public async void SetInputPathFromDrop(string path)
    {
        if (Busy || string.IsNullOrWhiteSpace(path)) return;
        if (await ConfirmCsvBeforeSourceChangeAsync())
            InputPath = path.Trim().Trim('"');
    }

    internal void NavigateTab(string? tab)
    {
        if (string.IsNullOrWhiteSpace(tab))
            return;
        if(tab == WorkflowTabs.Journal && JournalRequested is not null)
        {
            JournalRequested.Invoke();
            return;
        }
        var sw = Stopwatch.StartNew();
        var from = SelectedTab;
        SelectedTab = tab;
        sw.Stop();
        AppendLog($"[tab] {from} → {tab} setter={sw.ElapsedMilliseconds}ms loading_csv={CsvEditorLoading}");
    }

    private async Task InitializeWorkerAsync()
    {
        try
        {
            await _worker.StartAsync().ConfigureAwait(true);
            AppendLog("Python worker sẵn sàng (JSON stdin/stdout).");
        }
        catch (Exception ex)
        {
            AppendLog($"Không khởi động được worker: {ex.Message}");
            StatusText = "Lỗi worker";
            StepStatusLine = "Lỗi worker — không khởi động được Python worker";
        }
    }

    private void ApplyWpfUpdate()
    {
        if (Busy)
            return;
        RefreshWpfUpdateAvailability();
        if (!_updateAvailable)
            return;
        if (AppDialogService.Show("Đóng VNText Studio và áp dụng bản cập nhật?", "Cập nhật VNText Studio",
                MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
            return;
        try
        {
            WpfUpdateService.StartUpdate(_worker.ProcessId);
        }
        catch (Exception ex)
        {
            AppDialogService.Show($"Không thể khởi chạy updater: {ex.Message}", "Cập nhật VNText Studio",
                MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void RecheckUpdateSources()
    {
        if (Busy || _githubUpdateChecking)
            return;
        StartGitHubUpdateCheck();
    }

    private void StartGitHubUpdateCheck(bool metadataOnly = false, bool manual = false)
    {
        if (_githubUpdateChecking || DownloadingUpdate)
            return;
        if (metadataOnly && manual && GitHubApplyEnabled)
        {
            UpdatePopupRequested?.Invoke();
            return;
        }
        DisposeGitHubUpdatePackageLease();
        RaiseGitHubUpdateCommands();
        var cancellation = new CancellationTokenSource();
        _githubUpdateCancellation = cancellation;
        _githubUpdateChecking = true;
        _githubUpdateStatus = "Đang kiểm tra cập nhật…";
        RaiseGitHubUpdateCard();
        RaiseGitHubUpdateCommands();
        RecheckUpdateCommand?.RaiseCanExecuteChanged();

        string? installRoot = null;
        try
        {
            installRoot = _updateInstallRoot ?? Path.GetDirectoryName(WorkerPaths.MainExePath())!;
            _githubUpdateCheckTask = CompleteGitHubUpdateCheckAsync(
                WpfUpdateService.CheckGitHubUpdateAsync(installRoot, _githubHttpHandler, cancellation.Token, metadataOnly),
                cancellation, installRoot);
            if (metadataOnly)
                _ = ShowOfferAfterCheckAsync(_githubUpdateCheckTask, manual);
        }
        catch (Exception ex)
        {
            _githubUpdateCheckTask = CompleteGitHubUpdateCheckAsync(
                Task.FromResult(new GitHubUpdateCheckResult(GitHubUpdateState.InvalidMetadata, Message: ex.Message)),
                cancellation, installRoot);
        }
        Raise(nameof(GitHubUpdateCheckTask));
    }

    private async Task CompleteGitHubUpdateCheckAsync(Task<GitHubUpdateCheckResult> checkTask,
        CancellationTokenSource cancellation, string? installRoot)
    {
        try
        {
            var result = await checkTask;
            if (cancellation.IsCancellationRequested || !ReferenceEquals(_githubUpdateCancellation, cancellation))
            {
                if (installRoot is not null)
                    WpfUpdateService.DeleteGitHubUpdateCandidate(installRoot, result);
                return;
            }
            DisposeGitHubUpdatePackageLease();
            if (result.State == GitHubUpdateState.UpdateAvailable && installRoot is not null)
                _githubUpdatePackageLease = new GitHubUpdatePackageLease(installRoot, result);
            _githubUpdateResult = result;
            CacheReleaseNotes(result);
            if (Set(ref _githubUpdateState, result.State))
                Raise(nameof(GitHubUpdateState));
            _githubUpdateStatus = GitHubStatusMessage(result.State, result.Version, result.Message);
            RaiseGitHubUpdateCard();
        }
        catch (TaskCanceledException)
        {
            if (cancellation.IsCancellationRequested || !ReferenceEquals(_githubUpdateCancellation, cancellation))
                return;
            _githubUpdateResult = new(GitHubUpdateState.Timeout);
            Set(ref _githubUpdateState, GitHubUpdateState.Timeout);
            _githubUpdateStatus = GitHubStatusMessage(GitHubUpdateState.Timeout, "");
            Raise(nameof(GitHubUpdateState));
            RaiseGitHubUpdateCard();
        }
        catch (Exception ex)
        {
            if (cancellation.IsCancellationRequested || !ReferenceEquals(_githubUpdateCancellation, cancellation))
                return;
            _githubUpdateResult = new(GitHubUpdateState.InvalidMetadata, Message: ex.Message);
            Set(ref _githubUpdateState, GitHubUpdateState.InvalidMetadata);
            _githubUpdateStatus = GitHubStatusMessage(GitHubUpdateState.InvalidMetadata, "");
            Raise(nameof(GitHubUpdateState));
            RaiseGitHubUpdateCard();
        }
        finally
        {
            if (ReferenceEquals(_githubUpdateCancellation, cancellation))
            {
                _githubUpdateCancellation = null;
                _githubUpdateChecking = false;
                cancellation.Dispose();
                RaiseGitHubUpdateCommands();
                RaiseGitHubUpdateCard();
            }
        }
    }

    private static string GitHubStatusMessage(GitHubUpdateState state, string version, string message = "")
    {
        if (state == GitHubUpdateState.UpdateAvailable && message.StartsWith("ROUTE_STATUS:", StringComparison.Ordinal))
            return message["ROUTE_STATUS:".Length..];
        if (state is GitHubUpdateState.Offline or GitHubUpdateState.Timeout or GitHubUpdateState.RateLimited)
            return string.IsNullOrWhiteSpace(message) ? "Chưa thể kiểm tra. Hãy thử lại sau." : message;
        if (state is GitHubUpdateState.InvalidMetadata or GitHubUpdateState.InvalidPackage)
            return string.IsNullOrWhiteSpace(message) ? "Không thể kiểm tra bản cập nhật." : $"Không thể kiểm tra bản cập nhật: {message}";
        return state switch
        {
            GitHubUpdateState.Unconfigured => "Chưa cấu hình nguồn cập nhật.",
            GitHubUpdateState.Current => "Bạn đang dùng phiên bản mới nhất.",
            GitHubUpdateState.OfferAvailable => "Có bản cập nhật mới; chưa tải gói.",
            GitHubUpdateState.UpdateAvailable => "Đã kiểm tra gói. Sẵn sàng cập nhật.",
            GitHubUpdateState.SetupRequired => "Bản cập nhật này cần bộ cài mới.",
            _ => "Chưa thể kiểm tra cập nhật.",
        };
    }

    private void HandleUpdateAction()
    {
        if (GitHubApplyEnabled)
            ApplyGitHubUpdate();
        else
            RecheckUpdateSources();
    }

    internal void RecheckGitHubUpdateForTest() => RecheckUpdateSources();

    private void RaiseGitHubUpdateCard()
    {
        Raise(nameof(OfferedVersion));
        Raise(nameof(UpdateNotes));
        Raise(nameof(GitHubUpdateStatus));
        Raise(nameof(GitHubUpdateChecking));
        Raise(nameof(GitHubUpdateVersion));
        Raise(nameof(GitHubUpdateVersionVisible));
        Raise(nameof(GitHubUpdateButtonText));
        Raise(nameof(GitHubUpdateButtonEnabled));
        RecheckUpdateCommand?.RaiseCanExecuteChanged();
    }

    private void RaiseGitHubUpdateCommands()
    {
        RecheckUpdateCommand?.RaiseCanExecuteChanged();
        Raise(nameof(GitHubApplyEnabled));
        Raise(nameof(GitHubSetupRequired));
        ApplyGitHubUpdateCommand?.RaiseCanExecuteChanged();
        OpenGitHubSetupCommand?.RaiseCanExecuteChanged();
    }

    private void DisposeGitHubUpdatePackageLease() =>
        Interlocked.Exchange(ref _githubUpdatePackageLease, null)?.Dispose();

    private void ApplyGitHubUpdate()
    {
        if (Busy || CsvEditorDirty || !GitHubApplyEnabled || _githubUpdateChecking)
            return;
        if (AppDialogService.Show($"Đóng VNText Studio và áp dụng bản cập nhật WPF ổn định v{_githubUpdateResult.Version}?",
                "VNText Studio update", MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
            return;
        try
        {
            var packageLease = _githubUpdatePackageLease;
            if (packageLease is null)
                return;
            WpfUpdateService.StartGitHubUpdate(_worker.ProcessId, packageLease);
        }
        catch (Exception ex)
        {
            AppDialogService.Show($"Không thể khởi chạy updater đã xác minh: {ex.Message}", "Cập nhật VNText Studio",
                MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void OpenGitHubSetup()
    {
        if (!GitHubSetupRequired)
            return;
        try
        {
            Process.Start(new ProcessStartInfo(_githubUpdateResult.ReleasesUrl) { UseShellExecute = true });
        }
        catch (Exception ex)
        {
            _githubUpdateStatus = "Could not open the official Releases page: " + ex.Message;
            Raise(nameof(GitHubUpdateStatus));
        }
    }

    private void RefreshWpfUpdateAvailability()
    {
        _updateAvailable = WpfUpdateService.TryGetAvailableUpdateVersion(
            Path.GetDirectoryName(WorkerPaths.MainExePath())!, out var candidateVersion, out var status);
        _updateStatus = _updateAvailable
            ? $"Local Updates preview: v{candidateVersion} is available."
            : "Local Updates preview: " + status;
        Raise(nameof(UpdateCheckEnabled));
        Raise(nameof(UpdateEnabled));
        Raise(nameof(UpdateStatus));
        RecheckUpdateCommand?.RaiseCanExecuteChanged();
        ApplyUpdateCommand?.RaiseCanExecuteChanged();
    }

    private void LoadVersion()
    {
        try
        {
            var path = Path.Combine(WorkerPaths.AppRoot(), "VERSION.txt");
            if (File.Exists(path))
            {
                var line = File.ReadLines(path).FirstOrDefault()?.Trim();
                if (!string.IsNullOrEmpty(line))
                    Version = $"v{line}";
            }
        }
        catch { /* ignore */ }
    }

    private void AppendLog(string line)
    {
        if (string.IsNullOrWhiteSpace(line))
            return;
        var content = line.Trim();
        if (content.Length > 4000) content = content[..4000];
        var stamped = $"[{DateTime.Now:HH:mm:ss}] {content}";
        LogLines.Add(stamped);
        PersistJournal(content);
        const int max = 1000;
        while (LogLines.Count > max)
            LogLines.RemoveAt(0);
        LogSubtitle = $"{LogLines.Count} dòng";
    }

    internal void TestHandleWorkerEvent(WorkerEvent evt) => HandleWorkerEvent(evt);
    internal void TestReportCancelTimeout(string id) => ReportCancelTimeout(id, CancellationToken.None);
    internal void TestBeginCancelAndExit() => CancelAndExit();
    internal void TestMarkAnalyzeStarted() { _analyzeIdentity = AnalyzeIdentityOf(InputPath, OutputPath); _analyzeRejectLate = false; }
    internal void TestSetRenpySdkAction(string action) => RenpySdkAction = action;
    internal void TestSetActiveTask(string id, string task) { _activeTaskId = id; _runningTask = task; Busy = true; }
    internal void TestMarkTaskTerminal(string id) { MarkTaskTerminal(id); Busy = false; _runningTask = null; }
    internal void RecordAppError(Exception error) => AppendLog($"Lỗi ứng dụng: {error}");

    internal void TestSetCloudRepairPackagePath(string path) => CloudRepairPackagePath = path;

    internal string TestResolveActiveCsvPath() => ResolveActiveCsvPath();

    internal void TestSimulateTaskComplete(string task, WorkerEvent evt)
    {
        var testTaskId = string.IsNullOrWhiteSpace(evt.Id) ? $"test-{task}" : evt.Id;
        if (!string.Equals(_activeTaskId, testTaskId, StringComparison.Ordinal))
        {
            _activeTaskId = testTaskId;
            _completionHandledKey = null;
        }
        _runningTask = task;
        Busy = true;
        HandleWorkerEvent(evt);
    }

    public void Dispose()
    {
        if (Interlocked.Exchange(ref _disposed, 1) != 0)
            return;
        _translateElapsedTimer?.Stop();
        _updateReminderTimer?.Stop(); _updateCheckTimer?.Stop();
        _cancelWatchdog?.Cancel(); _cancelWatchdog?.Dispose(); _cancelWatchdog = null;
        var githubCancellation = Interlocked.Exchange(ref _githubUpdateCancellation, null);
        githubCancellation?.Cancel();
        githubCancellation?.Dispose();
        DisposeGitHubUpdatePackageLease();
        Interlocked.Exchange(ref _renpyDetectionCancellation, null)?.Cancel();
        _worker.Dispose();
    }
}
