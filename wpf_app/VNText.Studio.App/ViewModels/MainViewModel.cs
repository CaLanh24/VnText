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
    private string _patchDeliveryLabel = "Hướng dẫn cài patch sẽ hiện sau khi đóng gói.";
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
    private string _version = "vunknown";
    private bool _busy;
    private bool _progressExpanded;
    private bool _logExpanded;
    private bool _advancedToolsExpanded = true;
    private bool _separateReview = true;
    private bool _overwriteTranslation;
    private bool _humanReviewRequired;
    private string _extractLevel = ExtractLevels.Balanced;
    private string _renpySdkPath = "";
    private string _renpySdkAction = "auto";
    private CancellationTokenSource? _renpyDetectionCancellation;
    private bool _renpySdkOptionsVisible;
    private string _translationModelDir = "";
    private bool _translateButtonGreen = true;
    private bool _readyForPatch;
    private bool _hasExtract;
    private bool _hasTranslations;
    private string _translationCsvPath = "";
    private string _csvValidationMessage = "Chưa kiểm tra translation.csv";
    private bool _csvValidationOk;
    private string _patchPreflightMessage = "Chưa kiểm tra chất lượng patch";
    private bool _patchPreflightOk;
    private int _patchEligibleCount;
    private int _patchBlockedCount;
    private int _progressPercent;
    private string _cloudRepairPackagePath = "";
    private string _pendingCloudRepairImportOutputPath = "";
    private string _pendingExternalTranslationImportTargetPath = "";
    private string _activeTaskId = "";
    private bool _updateAvailable;
    private string _updateStatus = "";
    private string _githubUpdateStatus = "Not checked";
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
    private int _refreshEpoch;
    private WorkerEvent? _pendingProgressEvent;
    private int _progressDispatchPosted;
    private readonly ConcurrentQueue<WorkerEvent> _pendingLogEvents = new();
    private int _logDispatchPosted;
    private int _disposed;

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
        _settings = AppSettingsStore.Load();
        _separateReview = _settings.SeparateReview;
        _overwriteTranslation = _settings.OverwriteTranslation;
        _humanReviewRequired = _settings.HumanReviewRequired;
        _extractLevel = ExtractLevels.Normalize(_settings.ExtractLevel);
        LogLines = new ObservableCollection<string>();
        LoadVersion();
        RefreshWpfUpdateAvailability();

        NavigateTabCommand = new RelayCommand(p => NavigateTab(p as string));
        AnalyzeCommand = new RelayCommand(_ => RunAnalyze(), _ => !Busy && !string.IsNullOrWhiteSpace(InputPath) && !string.IsNullOrWhiteSpace(OutputPath));
        RunExtractCommand = new RelayCommand(_ => RunExtract(), _ => !Busy);
        RunTranslateCommand = new RelayCommand(_ => RunTranslate(), _ => !Busy);
        ExportCloudRepairPackageCommand = new RelayCommand(_ => ExportCloudRepairPackage(), _ => !Busy);
        ImportExistingTranslationCommand = new RelayCommand(_ => ImportExistingTranslation(), _ => !Busy);
        RunPatchCommand = new RelayCommand(_ => RunPatch(), _ => !Busy);
        CancelCommand = new RelayCommand(_ => CancelTask(), _ => Busy);
        ChooseInputCommand = new RelayCommand(_ => ChooseInput());
        ChooseOutputCommand = new RelayCommand(_ => ChooseOutput());
        OpenInputCommand = new RelayCommand(_ => OpenInput(), _ => CanOpenInput());
        OpenOutputCommand = new RelayCommand(_ => OpenOutput(), _ => CanOpenOutput());
        ChooseTranslationCsvCommand = new RelayCommand(_ => ChooseTranslationCsv());
        ChooseRenpySdkCommand = new RelayCommand(_ => ChooseRenpySdk());
        DownloadRenpySdkCommand = new RelayCommand(_ => RunRenpySdkAction("download"), _ => !Busy);
        ContinueWithoutRenpySdkCommand = new RelayCommand(_ => RunRenpySdkAction("none"), _ => !Busy);
        RecheckUpdateCommand = new RelayCommand(_ => RecheckUpdateSources(), _ => !Busy && UpdateCheckEnabled && !_githubUpdateChecking);
        ApplyUpdateCommand = new RelayCommand(_ => ApplyWpfUpdate(), _ => !Busy && _updateAvailable);
        ApplyGitHubUpdateCommand = new RelayCommand(_ => ApplyGitHubUpdate(), _ => !Busy && GitHubApplyEnabled && !_githubUpdateChecking);
        OpenGitHubSetupCommand = new RelayCommand(_ => OpenGitHubSetup(), _ => GitHubSetupRequired && !_githubUpdateChecking);
        ValidateTranslationCsvCommand = new RelayCommand(_ => ValidateTranslationCsv(silent: false));
        ToggleProgressCommand = new RelayCommand(_ => ProgressExpanded = !ProgressExpanded);
        ToggleLogCommand = new RelayCommand(_ => LogExpanded = !LogExpanded);
        ToggleAdvancedToolsCommand = new RelayCommand(_ => AdvancedToolsExpanded = !AdvancedToolsExpanded);
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
        StartGitHubUpdateCheck();
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
                RefreshWorkflow();
                RefreshRenpySdkOptionsVisibility(value);
                OpenInputCommand?.RaiseCanExecuteChanged();
                AnalyzeCommand?.RaiseCanExecuteChanged();
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
                RefreshWorkflow();
                OpenOutputCommand?.RaiseCanExecuteChanged();
                AnalyzeCommand?.RaiseCanExecuteChanged();
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
                Raise(nameof(TranslationCsvDisplay));
                LoadPackageGlossary();
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
        string.IsNullOrWhiteSpace(CloudRepairPackagePath)
            ? "Chưa tạo gói Cloud Repair"
            : CloudRepairPackagePath;

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

    public string InputDisplay => string.IsNullOrWhiteSpace(InputPath) ? "Chọn thư mục game..." : InputPath;
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
        get => _heroTitle;
        private set => Set(ref _heroTitle, value);
    }

    public string HeroIcon
    {
        get => _heroIcon;
        private set => Set(ref _heroIcon, value);
    }

    public string HeroHint
    {
        get => _heroHint;
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
        private set => Set(ref _readyForPatch, value);
    }

    public bool HasExtract
    {
        get => _hasExtract;
        private set => Set(ref _hasExtract, value);
    }

    public string ProgressSubtitle
    {
        get => _progressSubtitle;
        set => Set(ref _progressSubtitle, value);
    }

    public string LogSubtitle
    {
        get => _logSubtitle;
        set => Set(ref _logSubtitle, value);
    }

    public string StatusText
    {
        get => _statusText;
        set => Set(ref _statusText, value);
    }

    public string Version
    {
        get => _version;
        set => Set(ref _version, value);
    }

    public bool SeparateReview
    {
        get => _separateReview;
        set
        {
            if (Set(ref _separateReview, value))
            {
                _settings.SeparateReview = value;
                AppSettingsStore.Save(_settings);
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
                AppSettingsStore.Save(_settings);
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
                AppSettingsStore.Save(_settings);
            }
        }
    }

    public bool UpdateEnabled => _updateAvailable;
    public bool UpdateCheckEnabled => true;
    public string UpdateStatus => _updateStatus;
    public string GitHubUpdateStatus => _githubUpdateStatus;
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
                Raise(nameof(RenpySdkStatus));
        }
    }

    public bool RenpySdkOptionsVisible
    {
        get => _renpySdkOptionsVisible;
        private set => Set(ref _renpySdkOptionsVisible, value);
    }

    public string RenpySdkStatus => RenpySdkAction switch
    {
        "download" => "Sẽ tải công cụ Ren'Py rồi lấy text.",
        "existing" => "Sẽ dùng thư mục công cụ Ren'Py đã chọn.",
        "none" => "Sẽ tiếp tục không có công cụ; một số lời thoại cần xem lại.",
        _ => "Khi lấy text, app tự dùng công cụ đã có; nếu chưa có, kết quả sẽ được báo là chưa đầy đủ.",
    };

    private void RefreshRenpySdkOptionsVisibility(string inputPath)
    {
        var previous = Interlocked.Exchange(ref _renpyDetectionCancellation, null);
        previous?.Cancel();
        RenpySdkOptionsVisible = false;
        RenpySdkAction = "auto";
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
                () => RenpyGameDetector.IsLooseSourceGame(inputPath, cancellation.Token),
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
        set
        {
            var normalized = ExtractLevels.Normalize(value);
            if (Set(ref _extractLevel, normalized))
            {
                _settings.ExtractLevel = normalized;
                AppSettingsStore.Save(_settings);
            }
        }
    }

    public bool Busy
    {
        get => _busy;
        set
        {
            if (Set(ref _busy, value))
            {
                RunExtractCommand.RaiseCanExecuteChanged();
                AnalyzeCommand.RaiseCanExecuteChanged();
                RunTranslateCommand.RaiseCanExecuteChanged();
                ExportCloudRepairPackageCommand.RaiseCanExecuteChanged();
                ImportExistingTranslationCommand.RaiseCanExecuteChanged();
                RunPatchCommand.RaiseCanExecuteChanged();
                DownloadRenpySdkCommand.RaiseCanExecuteChanged();
                ContinueWithoutRenpySdkCommand.RaiseCanExecuteChanged();
                CancelCommand.RaiseCanExecuteChanged();
                RetranslateBlockedCsvCommand.RaiseCanExecuteChanged();
                RecheckUpdateCommand.RaiseCanExecuteChanged();
                ApplyUpdateCommand.RaiseCanExecuteChanged();
                ApplyGitHubUpdateCommand.RaiseCanExecuteChanged();
                OpenGitHubSetupCommand.RaiseCanExecuteChanged();
                if (!value)
                {
                    _runningTask = null;
                    RefreshWorkflow();
                }
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

    public RelayCommand NavigateTabCommand { get; }
    public RelayCommand AnalyzeCommand { get; }
    public RelayCommand RunExtractCommand { get; }
    public RelayCommand RunTranslateCommand { get; }
    public RelayCommand ExportCloudRepairPackageCommand { get; }
    public RelayCommand ImportExistingTranslationCommand { get; }
    public RelayCommand RunPatchCommand { get; }
    public RelayCommand CancelCommand { get; }
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

    public void SetInputPathFromDrop(string path)
    {
        if (!string.IsNullOrWhiteSpace(path))
            InputPath = path.Trim().Trim('"');
    }

    internal void NavigateTab(string? tab)
    {
        if (string.IsNullOrWhiteSpace(tab))
            return;
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
        if (MessageBox.Show("Đóng VNText Studio và áp dụng bản cập nhật?", "Cập nhật VNText Studio",
                MessageBoxButton.YesNo, MessageBoxImage.Question) != MessageBoxResult.Yes)
            return;
        try
        {
            WpfUpdateService.StartUpdate(_worker.ProcessId);
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Không thể khởi chạy updater: {ex.Message}", "Cập nhật VNText Studio",
                MessageBoxButton.OK, MessageBoxImage.Error);
        }
    }

    private void RecheckUpdateSources()
    {
        if (Busy || _githubUpdateChecking)
            return;
        RefreshWpfUpdateAvailability();
        StartGitHubUpdateCheck();
    }

    private void StartGitHubUpdateCheck()
    {
        if (_githubUpdateChecking)
            return;
        DisposeGitHubUpdatePackageLease();
        RaiseGitHubUpdateCommands();
        var cancellation = new CancellationTokenSource();
        _githubUpdateCancellation = cancellation;
        _githubUpdateChecking = true;
        _githubUpdateStatus = "Checking GitHub stable releases…";
        Raise(nameof(GitHubUpdateStatus));
        RaiseGitHubUpdateCommands();
        RecheckUpdateCommand?.RaiseCanExecuteChanged();

        string? installRoot = null;
        try
        {
            installRoot = _updateInstallRoot ?? Path.GetDirectoryName(WorkerPaths.MainExePath())!;
            _githubUpdateCheckTask = CompleteGitHubUpdateCheckAsync(
                WpfUpdateService.CheckGitHubUpdateAsync(installRoot, _githubHttpHandler, cancellation.Token),
                cancellation, installRoot);
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
            var result = await checkTask.ConfigureAwait(true);
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
            if (Set(ref _githubUpdateState, result.State))
                Raise(nameof(GitHubUpdateState));
            _githubUpdateStatus = string.IsNullOrWhiteSpace(result.Message)
                ? GitHubStatusMessage(result.State, result.Version)
                : result.Message;
            Raise(nameof(GitHubUpdateStatus));
        }
        catch (TaskCanceledException)
        {
            if (cancellation.IsCancellationRequested || !ReferenceEquals(_githubUpdateCancellation, cancellation))
                return;
            _githubUpdateResult = new(GitHubUpdateState.Timeout);
            Set(ref _githubUpdateState, GitHubUpdateState.Timeout);
            _githubUpdateStatus = GitHubStatusMessage(GitHubUpdateState.Timeout, "");
            Raise(nameof(GitHubUpdateState));
            Raise(nameof(GitHubUpdateStatus));
        }
        catch (Exception ex)
        {
            if (cancellation.IsCancellationRequested || !ReferenceEquals(_githubUpdateCancellation, cancellation))
                return;
            _githubUpdateResult = new(GitHubUpdateState.InvalidMetadata, Message: ex.Message);
            Set(ref _githubUpdateState, GitHubUpdateState.InvalidMetadata);
            _githubUpdateStatus = GitHubStatusMessage(GitHubUpdateState.InvalidMetadata, "") + " " + ex.Message;
            Raise(nameof(GitHubUpdateState));
            Raise(nameof(GitHubUpdateStatus));
        }
        finally
        {
            if (ReferenceEquals(_githubUpdateCancellation, cancellation))
            {
                _githubUpdateCancellation = null;
                _githubUpdateChecking = false;
                cancellation.Dispose();
                RaiseGitHubUpdateCommands();
                RecheckUpdateCommand?.RaiseCanExecuteChanged();
            }
        }
    }

    private static string GitHubStatusMessage(GitHubUpdateState state, string version) => state switch
    {
        GitHubUpdateState.Unconfigured => "GitHub stable updates are not configured.",
        GitHubUpdateState.Current => "VNText Studio is up to date with stable GitHub releases.",
        GitHubUpdateState.UpdateAvailable => $"Stable WPF update available: v{version}.",
        GitHubUpdateState.SetupRequired => "A newer stable release requires Setup; open the official Releases page.",
        GitHubUpdateState.InvalidMetadata => "GitHub release metadata is invalid.",
        GitHubUpdateState.InvalidPackage => "GitHub WPF update package is invalid.",
        GitHubUpdateState.Offline => "GitHub releases are unavailable (offline or server error).",
        GitHubUpdateState.Timeout => "GitHub update check timed out.",
        GitHubUpdateState.RateLimited => "GitHub rate limit reached; try again later.",
        _ => "GitHub update status is unavailable.",
    };

    private void RaiseGitHubUpdateCommands()
    {
        Raise(nameof(GitHubApplyEnabled));
        Raise(nameof(GitHubSetupRequired));
        ApplyGitHubUpdateCommand?.RaiseCanExecuteChanged();
        OpenGitHubSetupCommand?.RaiseCanExecuteChanged();
    }

    private void DisposeGitHubUpdatePackageLease() =>
        Interlocked.Exchange(ref _githubUpdatePackageLease, null)?.Dispose();

    private void ApplyGitHubUpdate()
    {
        if (Busy || !GitHubApplyEnabled || _githubUpdateChecking)
            return;
        if (MessageBox.Show($"Close VNText Studio and apply stable WPF update v{_githubUpdateResult.Version}?",
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
            MessageBox.Show($"Could not start the verified WPF updater: {ex.Message}", "VNText Studio update",
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
        var stamped = $"[{DateTime.Now:HH:mm:ss}] {line.Trim()}";
        LogLines.Add(stamped);
        LogSubtitle = $"{LogLines.Count} dòng";
        const int max = 200;
        while (LogLines.Count > max)
            LogLines.RemoveAt(0);
    }

    internal void TestHandleWorkerEvent(WorkerEvent evt) => HandleWorkerEvent(evt);

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
        var githubCancellation = Interlocked.Exchange(ref _githubUpdateCancellation, null);
        githubCancellation?.Cancel();
        githubCancellation?.Dispose();
        DisposeGitHubUpdatePackageLease();
        Interlocked.Exchange(ref _renpyDetectionCancellation, null)?.Cancel();
        _worker.Dispose();
    }
}
