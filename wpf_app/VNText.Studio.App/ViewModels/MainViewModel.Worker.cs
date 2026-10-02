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
    private void OnWorkerEvent(object? sender, WorkerEvent evt)
    {
        // Never block the worker stdout reader on UI work. Progress can arrive much
        // faster than WPF can render it, so keep only the newest pending progress.
        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher is null)
        {
            HandleWorkerEvent(evt);
            return;
        }

        if (evt.Type == "progress")
        {
            Interlocked.Exchange(ref _pendingProgressEvent, evt);
            if (Interlocked.Exchange(ref _progressDispatchPosted, 1) == 0)
            {
                dispatcher.BeginInvoke(
                    DispatcherPriority.Background,
                    new Action(() => DrainPendingProgress(dispatcher)));
            }
            return;
        }

        if (evt.Type == "log")
        {
            _pendingLogEvents.Enqueue(evt);
            QueuePendingLogs(dispatcher);
            return;
        }

        dispatcher.BeginInvoke(DispatcherPriority.Normal, new Action(() => HandleWorkerEvent(evt)));
    }

    private void DrainPendingProgress(Dispatcher dispatcher)
    {
        try
        {
            var evt = Interlocked.Exchange(ref _pendingProgressEvent, null);
            if (evt is not null)
                HandleWorkerEvent(evt);
        }
        finally
        {
            Volatile.Write(ref _progressDispatchPosted, 0);
            if (Volatile.Read(ref _pendingProgressEvent) is not null)
            {
                Interlocked.Exchange(ref _progressDispatchPosted, 1);
                dispatcher.BeginInvoke(
                    DispatcherPriority.Background,
                    new Action(() => DrainPendingProgress(dispatcher)));
            }
        }
    }

    private void QueuePendingLogs(Dispatcher dispatcher)
    {
        if (Interlocked.Exchange(ref _logDispatchPosted, 1) != 0)
            return;

        dispatcher.BeginInvoke(
            DispatcherPriority.Background,
            new Action(() => DrainPendingLogs(dispatcher)));
    }

    private void DrainPendingLogs(Dispatcher dispatcher)
    {
        try
        {
            // Keep each UI turn bounded so a large Extract cannot monopolize WPF.
            for (var i = 0; i < 32 && _pendingLogEvents.TryDequeue(out var evt); i++)
                HandleWorkerEvent(evt);
        }
        finally
        {
            Volatile.Write(ref _logDispatchPosted, 0);
            if (!_pendingLogEvents.IsEmpty)
                QueuePendingLogs(dispatcher);
        }
    }

    private void HandleWorkerEvent(WorkerEvent evt)
    {
        switch (evt.Type)
        {
            case "log":
                if (!string.IsNullOrWhiteSpace(evt.Text))
                    AppendLog(evt.Text);
                break;
            case "progress":
                if (evt.Total > 0)
                {
                    var pct = (int)Math.Round(evt.Done * 100.0 / evt.Total);
                    ProgressPercent = Math.Clamp(pct, 0, 99);
                    var parts = new List<string> { $"{ProgressPercent}%" };
                    if (!string.IsNullOrWhiteSpace(evt.Step)) parts.Add(evt.Step);
                    if (!string.IsNullOrWhiteSpace(evt.Item)) parts.Add(evt.Item);
                    if (!string.IsNullOrWhiteSpace(evt.Eta)) parts.Add($"ETA {evt.Eta}");
                    ProgressSubtitle = string.Join(" • ", parts);
                }
                break;
            case "complete":
                if (!TryClaimCompletion(evt))
                    break;

                var completedTask = _runningTask;
                if (completedTask == "cloud_import" && evt.Ok && evt.Complete != false
                    && !TryActivateCloudRepairImport(out var cloudImportError))
                {
                    evt.Ok = false;
                    evt.Complete = false;
                    evt.Error = cloudImportError;
                }
                if (completedTask == "external_translation_import" && evt.Ok
                    && !TryActivateExternalTranslationImport(out var externalImportError))
                {
                    evt.Ok = false;
                    evt.Complete = false;
                    evt.Error = externalImportError;
                }
                if (completedTask == "cloud_import")
                    _pendingCloudRepairImportOutputPath = "";
                if (completedTask == "external_translation_import")
                    _pendingExternalTranslationImportTargetPath = "";
                Busy = false;
                _runningTask = null;
                ApplyDiagnostic(evt);
                var isAnalyze = completedTask == "analyze";
                var renpySdkIncomplete = completedTask == "extract" && evt.RenpySdkMissing;
                var cancelled = evt.Error?.Contains("cancelled", StringComparison.OrdinalIgnoreCase) == true;
                var needsHumanReview = evt.HumanReviewRequiredCount > 0;
                var isExternalTranslationImport = completedTask == "external_translation_import";
                var externalRemaining = Math.Max(evt.Pending, evt.ReviewOnly);
                var manualReviewText = renpySdkIncomplete
                    ? $"Lấy text chưa đầy đủ do thiếu công cụ Ren'Py; {evt.ReviewOnly} lời thoại cần xem lại."
                    : isExternalTranslationImport
                    ? $"Đã nhập {evt.Applied} dòng an toàn; còn {externalRemaining} dòng cần sửa trong CSV"
                    : needsHumanReview
                    ? $"Cần duyệt thủ công {evt.HumanReviewRequiredCount} dòng trước khi Patch"
                    : $"Dịch một phần — còn pending {evt.Pending}, review {evt.ReviewOnly}, blocked {evt.Blocked}";
                var fullyComplete = isAnalyze
                    ? evt.Ok && !cancelled
                    : (evt.Complete ?? evt.Ok)
                    && evt.Pending == 0
                    && evt.ReviewOnly == 0
                    && evt.Blocked == 0;
                var partialOk = !isAnalyze && !fullyComplete && !cancelled && (evt.Ok || needsHumanReview || renpySdkIncomplete);
                if (fullyComplete)
                    ProgressPercent = 100;
                ProgressSubtitle = cancelled ? "Đã hủy"
                    : fullyComplete ? "Hoàn tất"
                    : partialOk ? manualReviewText
                    : "Lỗi";
                StatusText = cancelled ? "Đã hủy"
                    : isAnalyze ? (fullyComplete ? "Đã phân tích" : "Phân tích lỗi")
                    : fullyComplete ? "Hoàn tất"
                    : partialOk ? (renpySdkIncomplete ? "Lấy text chưa đầy đủ" : isExternalTranslationImport ? "Cần sửa CSV" : "Dịch một phần")
                    : "Lỗi";
                StepStatusLine = cancelled
                    ? "Đã hủy tác vụ"
                    : isAnalyze
                        ? fullyComplete
                            ? "Phân tích game hoàn tất — xem coverage trước khi Lấy text"
                            : $"Phân tích game lỗi — {evt.Error ?? "inventory chưa đầy đủ"}"
                    : fullyComplete
                        ? "Hoàn tất bước — cập nhật quy trình"
                        : partialOk
                            ? renpySdkIncomplete
                                ? manualReviewText
                                : needsHumanReview
                                ? manualReviewText
                                : isExternalTranslationImport
                                    ? manualReviewText
                                    : $"Dịch một phần — đã dịch {evt.Translated}, còn pending {evt.Pending}, review {evt.ReviewOnly}, blocked {evt.Blocked}"
                            : $"Lỗi — {evt.Error ?? "worker báo lỗi"}";
                if (!string.IsNullOrWhiteSpace(evt.Summary)) AppendLog(evt.Summary);
                if (!string.IsNullOrWhiteSpace(evt.Error))
                    AppendLog(needsHumanReview || renpySdkIncomplete ? evt.Error : $"Lỗi: {evt.Error}");

                if (cancelled)
                {
                    if (completedTask == "analyze")
                    {
                        AnalyzeStatusText = "Đã hủy phân tích game";
                        AnalyzeScanErrorText = "Không có inventory hoàn tất để sử dụng.";
                    }
                    RequestCompletion("VNText Studio — Đã hủy", "Đã hủy tác vụ.", "info");
                }
                else if (!evt.Ok && !partialOk)
                {
                    var errMsg = string.IsNullOrWhiteSpace(evt.Error) ? "Tác vụ thất bại" : evt.Error!;
                    RequestCompletion("VNText Studio — Lỗi", errMsg, "error");
                    LogExpanded = true;
                }
                else if (fullyComplete)
                {
                    var doneMsg = completedTask switch
                    {
                        "extract" => "Lấy text hoàn tất",
                        "translate" => "Dịch tự động hoàn tất",
                        "cloud_export" => "Đã tạo gói Cloud Repair — tải ZIP lên dịch vụ bên ngoài.",
                        "cloud_import" => "Đã nhập Cloud Repair — CSV mới đã được kiểm tra.",
                        "external_translation_import" => "Đã nhập bản dịch cũ — có thể tạo patch.",
                        "patch" when string.Equals(evt.PatchEngine, "renpy", StringComparison.OrdinalIgnoreCase)
                            => "Tạo overlay Ren'Py hoàn tất",
                        "patch" => "Tạo patch hoàn tất",
                        "analyze" => "Phân tích game hoàn tất",
                        _ => string.IsNullOrWhiteSpace(evt.Summary) ? "Hoàn tất" : evt.Summary!,
                    };
                    RequestCompletion("VNText Studio — Hoàn tất", doneMsg, "success");
                    LogExpanded = true;
                }
                else if (partialOk)
                {
                    RequestCompletion(
                        renpySdkIncomplete ? "VNText Studio — Lấy text chưa đầy đủ" : "VNText Studio — Chưa hoàn tất",
                        manualReviewText,
                        "warning");
                    LogExpanded = true;
                }

                if (!cancelled && completedTask == "analyze")
                {
                    ApplyAnalyzeResult(evt);
                    SelectedTab = WorkflowTabs.Extract;
                    AppendLog(evt.Ok
                        ? "Phân tích game xong — xem coverage rồi quyết định Lấy text."
                        : "Phân tích game chưa đủ inventory — xem lỗi quét trước khi Lấy text.");
                }
                else if (!cancelled && evt.Ok && completedTask is not null)
                {
                    _lastCompletedTask = completedTask;
                    if (completedTask == "extract")
                    {
                        TranslationCsvPath = Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "translation.csv");
                        SelectedTab = WorkflowTabs.Translate;
                        AppendLog("Extract xong — chuyển sang tab Dịch tự động.");
                    }
                    else if (completedTask == "cloud_import" && fullyComplete)
                    {
                        SelectedTab = WorkflowTabs.Patch;
                        AppendLog("Cloud Repair xong — chuyển sang tab Tạo patch.");
                    }
                    else if (completedTask == "external_translation_import")
                    {
                        SelectedTab = fullyComplete ? WorkflowTabs.Patch : WorkflowTabs.EditCsv;
                        AppendLog(fullyComplete
                            ? "Đã nhập đủ bản dịch cũ — chuyển sang tab Tạo patch."
                            : "Còn dòng chưa nhập được — chuyển sang tab Sửa CSV.");
                    }
                    else if (completedTask == "translate" && fullyComplete)
                    {
                        if (_csvEditorRetranslatePending)
                        {
                            OnCsvEditorRetranslateComplete(true);
                            AppendLog("Dịch lại dòng lỗi xong — đã tải lại CSV editor.");
                        }
                        else
                        {
                            SelectedTab = WorkflowTabs.Patch;
                            AppendLog("Dịch xong — chuyển sang tab Tạo patch.");
                        }
                    }
                    else if (completedTask == "translate" && _csvEditorRetranslatePending)
                    {
                        OnCsvEditorRetranslateComplete(evt.Ok && fullyComplete);
                    }
                }
                else if (cancelled && _csvEditorRetranslatePending)
                {
                    _csvEditorRetranslatePending = false;
                }
                else if (!evt.Ok && _csvEditorRetranslatePending)
                {
                    _csvEditorRetranslatePending = false;
                }

                RefreshWorkflow();
                // Worker event counts may be ahead of on-disk translate_status; re-apply UI after refresh.
                if (cancelled)
                {
                    ProgressSubtitle = "Đã hủy";
                    StatusText = "Đã hủy";
                    StepStatusLine = "Đã hủy tác vụ";
                }
                else if (!evt.Ok && !partialOk)
                {
                    ProgressSubtitle = "Lỗi";
                    StatusText = "Lỗi";
                    StepStatusLine = $"Lỗi — {evt.Error ?? "worker báo lỗi"}";
                }
                else if (fullyComplete)
                {
                    ProgressPercent = 100;
                    ProgressSubtitle = isAnalyze ? "Phân tích hoàn tất" : "Hoàn tất";
                    StatusText = isAnalyze ? "Đã phân tích" : "Hoàn tất";
                    StepStatusLine = isAnalyze
                        ? "Phân tích game hoàn tất — xem coverage trước khi Lấy text"
                        : "Hoàn tất bước — cập nhật quy trình";
                }
                else if (partialOk)
                {
                    ProgressSubtitle = manualReviewText;
                    StatusText = renpySdkIncomplete
                        ? "Lấy text chưa đầy đủ"
                        : isExternalTranslationImport ? "Cần sửa CSV" : "Dịch một phần";
                    StepStatusLine =
                        (renpySdkIncomplete
                            ? manualReviewText
                            : needsHumanReview
                            ? manualReviewText
                            : isExternalTranslationImport
                                ? manualReviewText
                                : $"Dịch một phần — đã dịch {evt.Translated}, còn pending {evt.Pending}, review {evt.ReviewOnly}, blocked {evt.Blocked}");
                }
                if (!string.IsNullOrWhiteSpace(DiagnosticStatusLine))
                    StepStatusLine = $"{StepStatusLine} — {DiagnosticStatusLine}";
                if (completedTask == "patch" && fullyComplete)
                    ApplyPatchDelivery(evt);
                break;
            case "error":
                AppendLog($"Lỗi: {evt.Error}");
                if (Busy && evt.Error.Contains("exited", StringComparison.OrdinalIgnoreCase))
                {
                    Busy = false;
                    _runningTask = null;
                    ProgressSubtitle = "Lỗi / Hủy";
                    StatusText = "Lỗi worker";
                    StepStatusLine = "Lỗi worker — process Python thoát bất ngờ";
                    RefreshWorkflow();
                }
                else if (!Busy)
                {
                    StatusText = "Lỗi";
                }
                break;
        }
    }

    private void ClearDiagnostic()
    {
        DiagnosticStatusLine = "";
        DiagnosticPath = "";
        DiagnosticStage = "";
        DiagnosticRootCause = "";
        DiagnosticAffectedCount = null;
        DiagnosticAction = "";
        DiagnosticStatus = "";
    }

    private bool TryActivateCloudRepairImport(out string error)
    {
        error = "";
        var path = _pendingCloudRepairImportOutputPath;
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
        {
            error = "Cloud Repair đã báo thành công nhưng không tìm thấy CSV output đã kiểm tra.";
            return false;
        }

        var validation = CsvPackageValidator.Validate(path);
        if (!validation.Ok)
        {
            error = $"CSV Cloud Repair sau khi nhập không hợp lệ: {validation.Message}";
            return false;
        }

        TranslationCsvPath = path;
        CsvValidationOk = true;
        CsvValidationMessage = validation.Message;
        ReadyForPatch = true;
        PatchPreflightOk = false;
        PatchEligibleCount = 0;
        PatchBlockedCount = 0;
        PatchPreflightMessage = "Cloud Repair đã nhập; kiểm tra trước khi tạo patch.";
        return true;
    }

    private bool TryActivateExternalTranslationImport(out string error)
    {
        error = "";
        var path = _pendingExternalTranslationImportTargetPath;
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
        {
            error = "Không tìm thấy translation.csv hiện tại sau khi nhập bản dịch cũ.";
            return false;
        }

        var validation = CsvPackageValidator.Validate(path);
        if (!validation.Ok)
        {
            error = $"translation.csv sau khi nhập không hợp lệ: {validation.Message}";
            return false;
        }

        TranslationCsvPath = path;
        CsvValidationOk = true;
        CsvValidationMessage = validation.Message;
        ReadyForPatch = true;
        PatchPreflightOk = false;
        PatchEligibleCount = 0;
        PatchBlockedCount = 0;
        PatchPreflightMessage = "Đã nhập bản dịch cũ; kiểm tra trước khi tạo patch.";
        return true;
    }

    private void ApplyDiagnostic(WorkerEvent evt)
    {
        var hasDiagnostic =
            !string.IsNullOrWhiteSpace(evt.DiagnosticStage)
            || !string.IsNullOrWhiteSpace(evt.DiagnosticRootCause)
            || !string.IsNullOrWhiteSpace(evt.DiagnosticAction)
            || !string.IsNullOrWhiteSpace(evt.DiagnosticPath);
        if (!hasDiagnostic)
            return;

        DiagnosticPath = evt.DiagnosticPath ?? "";
        DiagnosticStage = evt.DiagnosticStage ?? "WORKFLOW";
        DiagnosticRootCause = evt.DiagnosticRootCause ?? "UNKNOWN";
        DiagnosticAffectedCount = evt.DiagnosticAffectedCount;
        DiagnosticAction = evt.DiagnosticAction ?? "Mở diagnostic evidence và xử lý nguyên nhân trước khi chạy lại bước này.";
        DiagnosticStatus = evt.DiagnosticStatus ?? "FAILED";
        var affected = evt.DiagnosticAffectedCount is int count ? $" ({count} dòng)" : "";
        DiagnosticStatusLine = $"Chẩn đoán {DiagnosticStage}/{DiagnosticRootCause}{affected}: {DiagnosticAction}";
        AppendLog(DiagnosticStatusLine);
        if (!string.IsNullOrWhiteSpace(DiagnosticPath))
            AppendLog($"Diagnostic evidence: {DiagnosticPath}");
    }

    private void ApplyPatchDelivery(WorkerEvent evt)
    {
        if (string.Equals(evt.PatchDelivery, "renpy_native_overlay", StringComparison.OrdinalIgnoreCase))
        {
            PatchDeliveryLabel = "Ren'Py — native overlay (copy vào game root)";
            PatchInstallInstructions = evt.PatchInstallInstructions ?? "";
            StepStatusLine = "Ren'Py overlay đã sẵn sàng — copy COPY_TO_GAME_ROOT vào game root.";
        }
        else if (string.Equals(evt.PatchDelivery, "unity_installer", StringComparison.OrdinalIgnoreCase))
        {
            PatchDeliveryLabel = "Unity/Naninovel — VNTextPatchInstaller.exe";
            PatchInstallInstructions = evt.PatchInstallInstructions ?? "";
        }
        if (!string.IsNullOrWhiteSpace(evt.PatchPayloadPath))
            AppendLog($"Gói cài đặt: {evt.PatchPayloadPath}");
        if (!string.IsNullOrWhiteSpace(evt.PatchInstallInstructions))
            AppendLog(evt.PatchInstallInstructions);
    }

}
