using System.Collections.Concurrent;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Threading;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;


namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    private void RefreshWorkflow()
    {
        RefreshTranslateReadiness();
        var input = InputPath;
        var output = _csvValidationOk && !string.IsNullOrWhiteSpace(TranslationCsvPath)
            ? Path.GetDirectoryName(TranslationCsvPath)! : OutputPath;
        var epoch = Interlocked.Increment(ref _refreshEpoch);
        var dispatcher = Application.Current?.Dispatcher;

        void Apply(WorkflowSnapshot snap)
        {
            if (epoch != Volatile.Read(ref _refreshEpoch))
                return;
            ApplyWorkflowSnapshot(snap);
        }

        // Console / unit-test hosts have no dispatcher — keep sync.
        // Only offload when already on the UI thread (worker complete → refresh).
        if (dispatcher is null || !dispatcher.CheckAccess())
        {
            Apply(WorkflowStatus.Evaluate(input, output));
            return;
        }

        // Large Unity translation.csv: HasTranslations / package checks must not block UI.
        Task.Run(() =>
        {
            try
            {
                var snap = WorkflowStatus.Evaluate(input, output);
                dispatcher.BeginInvoke(() => Apply(snap));
            }
            catch
            {
                /* ignore evaluate I/O failures */
            }
        });
    }

    private bool CanStartTranslate()
    {
        if (Busy || CsvEditorSaving || CsvEditorDirty || !_translationModelChecked || _translationModelUnavailable || !_translatePackageReady)
            return false;
        try
        {
            return string.Equals(_translateReadinessPath, Path.GetFullPath(GetTranslateReadinessPath()), StringComparison.OrdinalIgnoreCase);
        }
        catch
        {
            return false;
        }
    }

    public string TranslateReadinessText
    {
        get
        {
            if (Busy && (_runningTask is "translate" or "image_batch" or "image_render"))
                return "Đang xử lý — xem bước, mục, thời gian và ETA bên dưới.";
            if (!_translationModelChecked)
                return "Đang kiểm tra mô hình dịch…";
            if (_translationModelUnavailable)
                return string.IsNullOrWhiteSpace(_modelStatus)
                    ? "Không xác minh được runtime dịch; Dịch tự động đang bị khóa. Xem Cài đặt để biết chi tiết."
                    : $"Dịch tự động đang bị khóa — {_modelStatus}";
            if (_translatePackageChecking)
                return "Đang kiểm tra translation.csv và manifest…";
            if (!_translatePackageReady)
                return string.IsNullOrWhiteSpace(_translatePackageMessage)
                    ? "Chọn gói dịch có translation.csv và manifest.json hợp lệ."
                    : _translatePackageMessage;
            var count = _translatePackageRowCount == 1 ? "1 dòng" : $"{_translatePackageRowCount:N0} dòng";
            var ready = $"Sẵn sàng dịch · {count} · đã có bản dịch {_translatePackageTranslatedCount:N0}";
            return _translateLastRunCancelled ? $"{ready} · lần dịch trước đã hủy; chạy lại để dịch tiếp" : ready;
        }
    }

    internal void TestSetTranslationModelReady(bool ready, string? message = null)
    {
        _translationModelChecked = true;
        _translationModelUnavailable = !ready;
        _modelStatus = ready ? "Mô hình dịch đã sẵn sàng." : message ?? "Chưa có mô hình dịch trên máy.";
        Raise(nameof(ModelStatus));
        Raise(nameof(TranslateReadinessText));
        Raise(nameof(TranslateWorkflowStatusText));
        RunTranslateCommand?.RaiseCanExecuteChanged();
    }

    private string GetTranslateReadinessPath()
    {
        if (_csvValidationOk && !string.IsNullOrWhiteSpace(TranslationCsvPath))
            return TranslationCsvPath;
        return Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "translation.csv");
    }

    private void RefreshTranslateReadiness(bool syncCsvValidation = false, bool cancelledSummary = false)
    {
        var epoch = Interlocked.Increment(ref _translateReadinessEpoch);
        string path;
        try { path = Path.GetFullPath(GetTranslateReadinessPath()); }
        catch
        {
            _translatePackageReady = false;
            _translatePackageChecking = false;
            _translatePackageMessage = "Không đọc được đường dẫn gói dịch.";
            _translateReadinessPath = "";
            Raise(nameof(TranslateReadinessText));
            Raise(nameof(TranslateWorkflowStatusText));
            RunTranslateCommand?.RaiseCanExecuteChanged();
            return;
        }
        _translatePackageReady = false;
        _translatePackageChecking = true;
        _translatePackageMessage = "Đang kiểm tra translation.csv và manifest…";
        _translateReadinessPath = path;
        Raise(nameof(TranslateReadinessText));
        Raise(nameof(TranslateWorkflowStatusText));
        RunTranslateCommand?.RaiseCanExecuteChanged();

        var dispatcher = Application.Current?.Dispatcher;
        void Apply(CsvValidationResult raw)
        {
            if (epoch != Volatile.Read(ref _translateReadinessEpoch)) return;
            var result = raw;
            if (!raw.Ok && raw.Message == CsvPackageValidator.MissingFileMessage && string.IsNullOrWhiteSpace(TranslationCsvPath))
                result = raw with { Message = CsvPackageValidator.NoCsvChosenMessage };
            if (syncCsvValidation)
            {
                // Extract created this package, so replace any earlier missing-file
                // caption. Patch readiness remains governed by its stricter gate.
                CsvValidationOk = result.Ok;
                CsvValidationMessage = result.Message;
            }
            if (cancelledSummary)
            {
                // CsvValidationOk stays as it was: GetTranslateReadinessPath() falls back to
                // <output>/translation.csv when it is false, which is not the file the user picked.
                CsvValidationMessage = result.Ok
                    ? $"Đã hủy — đã dịch an toàn {result.TranslatedRows:N0}/{result.TotalRows:N0} dòng; chạy lại để dịch tiếp."
                    : result.Message;
            }
            _translatePackageReady = result.Ok;
            _translatePackageChecking = false;
            _translatePackageMessage = result.Message;
            _translatePackageRowCount = result.TotalRows;
            _translatePackageTranslatedCount = result.TranslatedRows;
            Raise(nameof(TranslateReadinessText));
            Raise(nameof(TranslateWorkflowStatusText));
            RunTranslateCommand?.RaiseCanExecuteChanged();
        }
        if (dispatcher is null || !dispatcher.CheckAccess())
        {
            Apply(CsvPackageValidator.Validate(path, requireTranslations: false));
            return;
        }
        _ = Task.Run(() => CsvPackageValidator.Validate(path, requireTranslations: false))
            .ContinueWith(task =>
            {
                var result = task.Status == TaskStatus.RanToCompletion
                    ? task.Result
                    : new CsvValidationResult(false, "CSV chưa sẵn sàng", 0, 0, path, null);
                if (!dispatcher.HasShutdownStarted && !dispatcher.HasShutdownFinished)
                    dispatcher.BeginInvoke(() => Apply(result));
            }, TaskScheduler.Default);
    }

    private void ApplyWorkflowSnapshot(WorkflowSnapshot snap)
    {
        CurrentWorkflowStep = snap.Current;
        StepStatusLine = snap.StepStatusLine;
        HasExtract = snap.HasExtract;
        ReadyForPatch = snap.ReadyForPatch;
        _hasTranslations = snap.HasTranslations;

        if (string.IsNullOrEmpty(TranslationCsvPath) && snap.HasExtract)
            TranslationCsvPath = Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "translation.csv");

        // Do not run CsvPackageValidator / patch_gate here — both scan the full CSV (and
        // patch_gate starts Python) synchronously. That freezes the UI after extract/translate
        // on large Unity packages. Explicit validate / StartPatch still run those checks.

        if (Busy && !string.IsNullOrEmpty(_runningTask))
        {
            ApplyRunningNav(_runningTask);
        }
        else
        {
            ExtractStepState = snap.ExtractState;
            TranslateStepState = snap.TranslateState;
            PatchStepState = snap.PatchState;
        }

        TranslateButtonGreen = SelectedTab == WorkflowTabs.Translate
            && !snap.HasTranslations
            && _runningTask != "translate"
            && _lastCompletedTask != "translate";

        UpdateHeroForTab();
    }

    private void UpdateHeroForTab()
    {
        switch (SelectedTab)
        {
            case WorkflowTabs.Translate:
                HeroTitle = "Dịch tự động";
                HeroIcon = "translate";
                HeroHint = _hasTranslations
                    ? "Có thể dịch tiếp hoặc chuyển sang Tạo patch."
                    : "Dịch bằng mô hình local hoặc chọn CSV đã dịch.";
                break;
            case WorkflowTabs.Patch:
                HeroTitle = "Tạo patch";
                HeroIcon = "patch";
                HeroHint = PatchPreflightOk
                    ? $"Sẵn sàng đóng gói {PatchEligibleCount} dòng; {PatchBlockedCount} dòng bị chặn."
                    : ReadyForPatch
                        ? "Kiểm tra CSV để xem dòng hợp lệ / bị chặn trước khi patch."
                        : "Chọn game và bản dịch để kiểm tra rồi đóng gói patch.";
                break;
            case WorkflowTabs.EditCsv:
                HeroTitle = "Sửa CSV";
                HeroIcon = "copy";
                HeroHint = CsvEditorDirty
                    ? "Có thay đổi chưa lưu — bấm «Lưu CSV» trước khi patch."
                    : "Chỉnh translation trực tiếp; Patch dùng file đã lưu.";
                break;
            case WorkflowTabs.Settings:
                HeroTitle = "Cài đặt";
                HeroIcon = "gear";
                HeroHint = "Thiết lập giao diện, dữ liệu và cập nhật.";
                break;
            case WorkflowTabs.Journal:
                HeroTitle = "Nhật ký";
                HeroIcon = "log";
                HeroHint = "";
                break;
            default:
                HeroTitle = "Lấy text";
                HeroIcon = "extract";
                HeroHint = string.IsNullOrWhiteSpace(InputPath)
                    ? "Chọn game, rồi bấm Lấy text."
                    : "Lấy text từ game đã chọn vào thư mục xuất.";
                break;
        }
    }

    private void ApplyRunningNav(string task)
    {
        // This method runs on the UI thread when a command starts. Do not evaluate
        // the package here: a large translation.csv must never be scanned synchronously.
        switch (task)
        {
            case "extract":
                ExtractStepState = WorkflowStepState.Running;
                break;
            case "analyze":
                SelectedTab = WorkflowTabs.Extract;
                break;
            case "translate":
                TranslateStepState = WorkflowStepState.Running;
                break;
            case "cloud_export":
            case "cloud_import":
            case "external_translation_import":
                TranslateStepState = WorkflowStepState.Running;
                SelectedTab = WorkflowTabs.Translate;
                break;
            case "patch":
                PatchStepState = WorkflowStepState.Running;
                break;
        }
        SelectedTab = task switch
        {
            "extract" => WorkflowTabs.Extract,
            "translate" => WorkflowTabs.Translate,
            "cloud_export" => WorkflowTabs.Translate,
            "cloud_import" => WorkflowTabs.Translate,
            "external_translation_import" => WorkflowTabs.Translate,
            "patch" => WorkflowTabs.Patch,
            _ => SelectedTab,
        };

        StepStatusLine = task switch
        {
            "analyze" => "Đang chạy: Phân tích game read-only…",
            "extract" => "Đang chạy: Lấy text (extract)…",
            "translate" => "Đang chạy: Dịch tự động…",
            "cloud_export" => "Đang chạy: Tạo gói Cloud Repair…",
            "cloud_import" => "Đang chạy: Kiểm tra Cloud Repair…",
            "external_translation_import" => "Đang chạy: Đối chiếu bản dịch cũ…",
            "patch" => "Đang chạy: Tạo patch…",
            _ => StepStatusLine,
        };
        TranslateButtonGreen = false;
    }

    private async void RunExtract()
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return;
        if (CsvEditorDirty && !await SaveCsvEditorAsync()) return;
        if (Busy) return;
        if (string.IsNullOrWhiteSpace(InputPath))
        {
            AppendLog("Chọn game / asset trước khi extract.");
            StatusText = "Chưa chọn game";
            SelectedTab = WorkflowTabs.Extract;
            return;
        }
        if (string.IsNullOrWhiteSpace(OutputPath))
        {
            AppendLog("Chọn thư mục xuất trước khi extract.");
            StatusText = "Chưa chọn thư mục xuất";
            return;
        }
        var existingPackage = WorkflowStatus.ResolvePackageDir(OutputPath);
        if (File.Exists(Path.Combine(existingPackage, "translation.csv")) || File.Exists(Path.Combine(existingPackage, "manifest.json")))
        {
            StatusText = "Chọn thư mục xuất mới";
            AppendLog("Giữ nguyên gói dịch hiện có. Để lấy lại text với SDK hoặc mức quét mới, hãy chọn thư mục xuất mới; không ghi đè CSV.");
            SelectedTab = WorkflowTabs.Extract;
            return;
        }
        BeginTask("extract", new
        {
            src = InputPath,
            @out = OutputPath,
            mode = "deep",
            level = ExtractLevel,
            separate_review = SeparateReview,
            renpy_sdk_path = RenpySdkPath,
            renpy_sdk_action = RenpySdkAction,
        }, RenpySdkAction == "download" ? "Đang tải Ren'Py SDK rồi lấy text…" : "Đang extract text…");
    }

    private void RunRenpySdkAction(string action)
    {
        RenpySdkAction = action;
        RenpySdkError = "";
        RunExtract();
    }

    private async void RunTranslate()
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return;
        if (CsvEditorDirty && !await SaveCsvEditorAsync()) return;
        if (Busy) return;
        SelectedTab = WorkflowTabs.Translate;
        var csv = ResolveActiveCsvPath();
        if (string.IsNullOrWhiteSpace(csv))
        {
            AppendLog("Chọn thư mục gói dịch trước khi dịch.");
            StatusText = "Chưa chọn thư mục xuất";
            return;
        }
        StatusText = "Đang kiểm tra gói dịch…";
        CsvValidationResult validation;
        try
        {
            validation = await Task.Run(() => CsvPackageValidator.Validate(csv, requireTranslations: false));
        }
        catch (Exception ex)
        {
            AppendLog($"Không kiểm tra được gói dịch: {ex.Message}");
            StatusText = "Lỗi kiểm tra gói";
            return;
        }
        if (!validation.Ok)
        {
            AppendLog($"Chưa thể dịch {csv}: {validation.Message}");
            StatusText = "CSV chưa sẵn sàng";
            return;
        }
        TranslateButtonGreen = false;
        BeginTask("translate", BuildTranslateParameters(csv), "Đang dịch offline…");
    }

    private void ExportCloudRepairPackage()
    {
        SelectedTab = WorkflowTabs.Translate;
        var csv = ResolveActiveCsvPath();
        var validation = CsvPackageValidator.Validate(csv);
        if (!validation.Ok)
        {
            AppendLog($"Cloud Repair: {validation.Message}");
            StatusText = "Chưa thể tạo gói Cloud Repair";
            ShowToast($"Không thể tạo gói Cloud Repair: {validation.Message}", "warning");
            return;
        }
        if (!string.Equals(Path.GetFileName(csv), "translation.csv", StringComparison.OrdinalIgnoreCase))
        {
            const string message = "Cloud Repair cần file translation.csv của gói hiện tại.";
            AppendLog(message);
            StatusText = "Chưa thể tạo gói Cloud Repair";
            ShowToast(message, "warning");
            return;
        }

        var packageDir = Path.GetDirectoryName(csv);
        if (string.IsNullOrWhiteSpace(packageDir))
        {
            const string message = "Không xác định được thư mục gói translation.csv.";
            AppendLog(message);
            StatusText = "Chưa thể tạo gói Cloud Repair";
            ShowToast(message, "warning");
            return;
        }

        var outputZip = PickCloudRepairPackagePath();
        if (string.IsNullOrWhiteSpace(outputZip))
            return;

        CloudRepairPackageReady = false;
        CloudRepairPackagePath = outputZip;
        BeginTask(
            "cloud_export",
            new
            {
                cloud_action = "export",
                package_dir = packageDir,
                output_zip = outputZip,
            },
            "Đang tạo gói Cloud Repair…",
            workerTask: "patch");
    }

    private void BeginCloudRepairImport(string resultCsv)
    {
        if (string.IsNullOrWhiteSpace(CloudRepairPackagePath) || !File.Exists(CloudRepairPackagePath))
        {
            const string message = "Hãy xuất gói dịch bên ngoài ở tab Dịch trước khi chọn CSV kết quả.";
            AppendLog(message);
            StatusText = "Chưa có gói Cloud Repair";
            ShowToast(message, "warning");
            return;
        }

        var activeCsv = ResolveActiveCsvPath();
        var packageDir = Path.GetDirectoryName(activeCsv);
        if (string.IsNullOrWhiteSpace(packageDir) || !File.Exists(Path.Combine(packageDir, "manifest.json")))
        {
            const string message = "Thiếu manifest.json của gói hiện tại; không thể nhận kết quả Cloud Repair.";
            AppendLog(message);
            StatusText = "Thiếu manifest gói";
            ShowToast(message, "warning");
            return;
        }

        var outputCsv = Path.Combine(packageDir, "translation.cloud_repair.csv");
        _pendingCloudRepairImportOutputPath = outputCsv;
        BeginTask(
            "cloud_import",
            new
            {
                cloud_action = "import",
                package_zip = CloudRepairPackagePath,
                result_csv = resultCsv,
                output_csv = outputCsv,
            },
            "Đang kiểm tra kết quả Cloud Repair…",
            workerTask: "patch");
    }

    private async void ImportExistingTranslation()
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return;
        if (CsvEditorDirty && !await SaveCsvEditorAsync()) return;
        if (Busy) return;
        SelectedTab = WorkflowTabs.Translate;
        var packageDir = WorkflowStatus.ResolvePackageDir(OutputPath);
        var targetCsv = Path.Combine(packageDir, "translation.csv");
        if (!File.Exists(targetCsv) || !File.Exists(Path.Combine(packageDir, "manifest.json")))
        {
            const string message = "Hãy extract gói hiện tại trước khi nhập bản dịch cũ.";
            AppendLog(message);
            StatusText = "Chưa có gói hiện tại";
            ShowToast(message, "warning");
            return;
        }

        var sourceCsv = _pathPicker.PickTranslationCsvFile(ImportTranslatedCsvPickerTitle);
        if (string.IsNullOrWhiteSpace(sourceCsv))
            return;
        if (string.Equals(Path.GetFullPath(targetCsv), Path.GetFullPath(sourceCsv), StringComparison.OrdinalIgnoreCase))
        {
            const string message = "Hãy chọn translation.csv từ gói cũ, không phải gói hiện tại.";
            AppendLog(message);
            StatusText = "Chưa chọn bản dịch cũ";
            ShowToast(message, "warning");
            return;
        }

        _pendingExternalTranslationImportTargetPath = targetCsv;
        BeginTask(
            "external_translation_import",
            new
            {
                cloud_action = "external_import",
                target_csv = targetCsv,
                source_csv = sourceCsv,
            },
            "Đang đối chiếu bản dịch cũ…",
            workerTask: "patch");
    }

    private async void RunPatch()
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return;
        if (CsvEditorDirty && !await SaveCsvEditorAsync()) return;
        if (Busy) return;
        SelectedTab = WorkflowTabs.Patch;
        if (string.IsNullOrWhiteSpace(InputPath))
        {
            AppendLog("Chọn game / asset trước khi tạo patch.");
            StatusText = "Chưa chọn game";
            return;
        }
        if (!ValidateTranslationCsv(silent: false))
        {
            StatusText = "CSV chưa hợp lệ";
            return;
        }
        if (!RunPatchPreflight(silent: false))
        {
            StatusText = "Không có dòng hợp lệ để patch";
            return;
        }
        var csv = ResolveActiveCsvPath();
        var manifest = Path.Combine(Path.GetDirectoryName(csv)!, "manifest.json");
        BeginTask("patch", new
        {
            src = InputPath,
            @out = OutputPath,
            csv_path = csv,
            manifest_path = manifest,
        }, "Đang tạo patch…");
    }

    private string ResolveActiveCsvPath()
    {
        if (_csvValidationOk && !string.IsNullOrWhiteSpace(TranslationCsvPath) && File.Exists(TranslationCsvPath))
            return TranslationCsvPath;
        return Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "translation.csv");
    }

    private object BuildTranslateParameters(string csvPath) => new
    {
        @out = OutputPath,
        csv_path = csvPath,
        overwrite = OverwriteTranslation,
        human_review_required = HumanReviewRequired,
        model = "ct2",
        model_dir = TranslationModelDir,
    };

    private void BeginTask(string task, object parameters, string statusLabel, string? workerTask = null)
    {
        if (Busy) return;
        _cancelWatchdog?.Cancel();
        _cancelWatchdog?.Dispose();
        _cancelWatchdog = null;
        _activeTaskId = $"task-{Guid.NewGuid():N}";
        _completionHandledKey = null;
        _translateLastRunCancelled = false;
        _runningTask = task;
        BeginTaskLog(_activeTaskId, task, statusLabel);
        _lastCompletedTask = null;
        ClearDiagnostic();
        if (task == "patch")
        {
            PatchDeliveryReady = false;
            PatchDeliveryLabel = "";
            PatchInstallInstructions = "";
        }
        Busy = true;
        StatusText = statusLabel;
        ApplyRunningNav(task);
        ProgressSubtitle = "Đang bắt đầu…";
        ProgressPercent = 0;
        if (task is "extract" or "analyze")
        {
            _extractProgressStep = statusLabel; _extractProgressItem = ""; _extractProgressEta = "";
            Raise(nameof(ExtractProgressStep)); Raise(nameof(ExtractProgressItem)); Raise(nameof(ExtractProgressEta)); Raise(nameof(ExtractProgressHasEta));
            _extractTaskStopwatch.Restart(); Raise(nameof(ExtractProgressElapsed));
            StartWorkflowElapsedTimer();
        }
        else if (task == "patch")
        {
            _patchProgressStep = statusLabel; _patchProgressItem = ""; _patchProgressEta = "";
            Raise(nameof(PatchProgressStep)); Raise(nameof(PatchProgressItem)); Raise(nameof(PatchProgressEta)); Raise(nameof(PatchProgressHasEta));
            _patchTaskStopwatch.Restart(); Raise(nameof(PatchProgressElapsed));
            StartWorkflowElapsedTimer();
        }
        if (OwnsTranslateProgressTask(task))
        {
            _translateProgressStep = statusLabel;
            _translateProgressItem = "";
            _translateProgressEta = "";
            Raise(nameof(TranslateProgressStep)); Raise(nameof(TranslateProgressItem)); Raise(nameof(TranslateProgressEta)); Raise(nameof(TranslateProgressHasEta));
            _translateTaskStopwatch.Restart();
            _translateElapsedTimer ??= new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
            _translateElapsedTimer.Tick -= OnTranslateElapsedTick;
            _translateElapsedTimer.Tick += OnTranslateElapsedTick;
            _translateElapsedTimer.Start();
            _translateProgressRunning = true;
            Raise(nameof(TranslateProgressElapsed));
        }
        SetOwnedProgress(task, 0, statusLabel);
        AppendLog($"Gửi lệnh worker: {task}");
        try
        {
            _worker.RunTask(_activeTaskId, workerTask ?? task, parameters);
        }
        catch (Exception ex)
        {
            Busy = false;
            _runningTask = null;
            AppendLog($"Lỗi gửi task: {ex.Message}");
            StatusText = "Lỗi";
            StepStatusLine = $"Lỗi — {ex.Message}";
            RefreshWorkflow();
        }
    }

    private void OnTranslateElapsedTick(object? sender, EventArgs e) => Raise(nameof(TranslateProgressElapsed));

    private void StartWorkflowElapsedTimer()
    {
        _workflowElapsedTimer ??= new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
        _workflowElapsedTimer.Tick -= OnWorkflowElapsedTick;
        _workflowElapsedTimer.Tick += OnWorkflowElapsedTick;
        _workflowElapsedTimer.Start();
    }

    private void OnWorkflowElapsedTick(object? sender, EventArgs e)
    {
        if (_extractTaskStopwatch.IsRunning) Raise(nameof(ExtractProgressElapsed));
        if (_patchTaskStopwatch.IsRunning) Raise(nameof(PatchProgressElapsed));
    }

    private static bool OwnsTranslateProgressTask(string? task) => task is
        "translate" or "image_batch" or "image_render" or "cloud_export" or "cloud_import" or "external_translation_import";

    private void CancelTask()
    {
        if (!Busy) return;
        AppendLog("Yêu cầu hủy tác vụ…");
        StatusText = "Đang hủy…";
        ProgressSubtitle = "Đã yêu cầu hủy; đang chờ worker xác nhận…";
        var taskId = _activeTaskId;
        SetOwnedProgress(_runningTask, text: ProgressSubtitle);
        try
        {
            _worker.Cancel(taskId);
            _cancelWatchdog?.Cancel();
            _cancelWatchdog?.Dispose();
            _cancelWatchdog = new CancellationTokenSource();
            _ = WatchCancelTimeoutAsync(taskId, _cancelWatchdog.Token);
        }
        catch (Exception ex)
        {
            StatusText = "Chưa gửi được yêu cầu hủy";
            AppendLog($"Không gửi được yêu cầu hủy: {ex.Message}");
        }
    }

    private void CancelAndExit()
    {
        if (!Busy) return;
        _exitAfterTask = true;
        CancelTask();
    }

    private void FinishCancelAndExit()
    {
        if (!_exitAfterTask) return;
        _exitAfterTask = false;
        ExitAfterTaskRequested?.Invoke(this, EventArgs.Empty);
    }

    private void MarkTaskTerminal(string taskId)
    {
        if (string.IsNullOrWhiteSpace(taskId) || !_terminalTaskIds.Add(taskId)) return;
        _terminalTaskIdOrder.Enqueue(taskId);
        while (_terminalTaskIdOrder.Count > 512)
            _terminalTaskIds.Remove(_terminalTaskIdOrder.Dequeue());
    }

    private async Task WatchCancelTimeoutAsync(string taskId, CancellationToken token)
    {
        try { await Task.Delay(TimeSpan.FromSeconds(30), token).ConfigureAwait(false); }
        catch (OperationCanceledException) { return; }
        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher is null)
        {
            ReportCancelTimeout(taskId, token);
            return;
        }
        if (dispatcher.HasShutdownStarted || dispatcher.HasShutdownFinished) return;
        _ = dispatcher.BeginInvoke(new Action(() =>
        {
            ReportCancelTimeout(taskId, token);
        }));
    }

    private void ReportCancelTimeout(string taskId, CancellationToken token)
    {
        if (!token.IsCancellationRequested && Busy
            && string.Equals(taskId, _activeTaskId, StringComparison.Ordinal))
        {
            StatusText = "Hủy vẫn đang chờ tác vụ dừng an toàn";
            ProgressSubtitle = "Chưa có kết quả cuối sau 30 giây; hãy tiếp tục chờ và không đóng ứng dụng cưỡng bức.";
            SetOwnedProgress(_runningTask, text: ProgressSubtitle);
            AddTaskProgress(taskId, ProgressSubtitle);
        }
    }

}
