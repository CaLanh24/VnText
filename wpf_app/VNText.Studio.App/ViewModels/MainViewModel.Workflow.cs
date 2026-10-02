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
        var input = InputPath;
        var output = OutputPath;
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

    private void ApplyWorkflowSnapshot(WorkflowSnapshot snap)
    {
        CurrentWorkflowStep = snap.Current;
        StepStatusLine = snap.StepStatusLine;
        HasExtract = snap.HasExtract;
        ReadyForPatch = snap.ReadyForPatch || _csvValidationOk;
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
                    ? "Đã có bản dịch trong translation.csv. Có thể dịch tiếp hoặc chuyển sang Tạo patch."
                    : "Dịch offline CTranslate2 + OPUS-MT en→vi (INT8). Hoặc chọn file CSV đã dịch tay ở tab Tạo patch.";
                break;
            case WorkflowTabs.Patch:
                HeroTitle = "Tạo patch";
                HeroIcon = "patch";
                HeroHint = PatchPreflightOk
                    ? $"Sẵn sàng patch {PatchEligibleCount} dòng (chặn {PatchBlockedCount}). Bấm «Tạo patch»."
                    : ReadyForPatch
                        ? "Kiểm tra CSV để xem dòng hợp lệ / bị chặn trước khi patch."
                        : "Cần translation.csv hợp lệ (có bản dịch) và manifest.json cùng thư mục.";
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
                HeroHint = "Thiết lập extract, dịch và workspace local.";
                break;
            default:
                HeroTitle = "Lấy text";
                HeroIcon = "extract";
                HeroHint = string.IsNullOrWhiteSpace(InputPath)
                    ? "Chọn game bên dưới, rồi bấm «Lấy text» để xuất CSV."
                    : "Xuất translation.csv từ game đã chọn vào thư mục xuất.";
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

    private void RunExtract()
    {
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
        BeginTask("extract", new
        {
            src = InputPath,
            @out = OutputPath,
            mode = "deep",
            level = ExtractLevel,
            separate_review = SeparateReview,
            renpy_sdk_path = RenpySdkPath,
            renpy_sdk_action = RenpySdkAction,
        }, "Đang extract text…");
    }

    private void RunRenpySdkAction(string action)
    {
        RenpySdkAction = action;
        RunExtract();
    }

    private async void RunTranslate()
    {
        SelectedTab = WorkflowTabs.Translate;
        if (string.IsNullOrWhiteSpace(OutputPath))
        {
            AppendLog("Chọn thư mục gói dịch trước khi dịch.");
            StatusText = "Chưa chọn thư mục xuất";
            return;
        }
        var input = InputPath;
        var output = OutputPath;
        StatusText = "Đang kiểm tra gói dịch…";
        WorkflowSnapshot snap;
        try
        {
            snap = await Task.Run(() => WorkflowStatus.Evaluate(input, output));
        }
        catch (Exception ex)
        {
            AppendLog($"Không kiểm tra được gói dịch: {ex.Message}");
            StatusText = "Lỗi kiểm tra gói";
            return;
        }
        if (!snap.HasExtract)
        {
            AppendLog("Chưa có translation.csv — hãy extract trước.");
            StatusText = "Cần extract trước";
            SelectedTab = WorkflowTabs.Extract;
            return;
        }
        TranslateButtonGreen = false;
        var csv = ResolveActiveCsvPath();
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

    private void ImportExistingTranslation()
    {
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

        var sourceCsv = _pathPicker.PickTranslationCsvFile();
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

    private void RunPatch()
    {
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
        _activeTaskId = $"task-{DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()}";
        _completionHandledKey = null;
        _runningTask = task;
        _lastCompletedTask = null;
        ClearDiagnostic();
        if (task == "patch")
        {
            PatchDeliveryLabel = "Đang xác định cách cài đặt theo engine…";
            PatchInstallInstructions = "";
        }
        Busy = true;
        StatusText = statusLabel;
        ApplyRunningNav(task);
        ProgressSubtitle = "Đang bắt đầu…";
        ProgressPercent = 0;
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

    private void CancelTask()
    {
        if (!Busy) return;
        AppendLog("Yêu cầu hủy tác vụ…");
        StatusText = "Đang hủy…";
        _worker.Cancel(_activeTaskId);
    }

}
