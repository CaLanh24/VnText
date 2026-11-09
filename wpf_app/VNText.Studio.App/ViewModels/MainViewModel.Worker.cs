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
    private static string FormatUserProgressStep(string? step, string? task)
    {
        var value = step?.Trim() ?? "";
        if (value.Length == 0)
            return "Đang xử lý";

        return value switch
        {
            "unity_enumerate" => "Đang quét danh mục tài nguyên",
            "unity_classify" when task == "extract" => "Đang phân loại tài nguyên để lấy text",
            "unity_classify" => "Đang phân loại tài nguyên",
            "unity_hash" => "Đang kiểm tra tài nguyên",
            _ => value,
        };
    }

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

    // True only while the terminal event of an analysis for an input that has since changed is being handled: NO completion dialog or sound for it.
    private bool _completingSuperseded;

    private void HandleWorkerEvent(WorkerEvent evt)
    {
        try { HandleWorkerEventCore(evt); }
        finally { _completingSuperseded = false; }
    }

    private void HandleWorkerEventCore(WorkerEvent evt)
    {
        switch (evt.Type)
        {
            case "cancel_ack":
                if (Busy && string.Equals(evt.Id, _activeTaskId, StringComparison.Ordinal)
                    && evt.State == "accepted")
                {
                    AppendLog("Worker đã nhận yêu cầu hủy; đang chờ tác vụ dừng an toàn…");
                    StatusText = "Worker đã nhận yêu cầu hủy; đang chờ tác vụ dừng an toàn…";
                    ProgressSubtitle = "Worker đã nhận yêu cầu hủy; đang chờ tác vụ dừng an toàn…";
                    SetOwnedProgress(_runningTask, text: ProgressSubtitle);
                    AddTaskProgress(evt.Id, ProgressSubtitle);
                }
                break;
            case "log":
                if (!string.IsNullOrWhiteSpace(evt.Text))
                {
                    var level = KnownLogLevel(evt.Severity);
                    AppendLog(evt.Text, level);
                    AddTaskProgress(evt.Id, evt.Text, level: level); // retain the whole owned task log, not just errors
                }
                break;
            case "progress":
                if (!string.IsNullOrWhiteSpace(evt.Id) && _terminalTaskIds.Contains(evt.Id))
                    break;
                if (evt.Total > 0)
                {
                    var pct = (int)Math.Round(evt.Done * 100.0 / evt.Total);
                    var boundedPercent = Math.Clamp(pct, 0, 99);
                    var userStep = FormatUserProgressStep(evt.Step, _runningTask);
                    var parts = new List<string> { $"{boundedPercent}%" };
                    if (!string.IsNullOrWhiteSpace(evt.Step)) parts.Add(UiText.Msg("Bước: {0}", UiText.Key(userStep)));
                    if (!string.IsNullOrWhiteSpace(evt.Item)) parts.Add(UiText.Msg("Mục: {0}", evt.Item));
                    var eta = ProgressEtaFormatter.Format(evt.Eta);
                    if (!string.IsNullOrWhiteSpace(eta)) parts.Add(UiText.Msg("ETA: {0}", UiText.Key(eta)));
                    var eventSubtitle = UiText.Join(" • ", parts);
                    NoteExtractPhase(evt.Id, evt.Step, userStep);
                    AddTaskProgress(evt.Id, eventSubtitle);
                    // A queued event from an older run may update its own journal,
                    // but it cannot overwrite the active page or a terminal card.
                    if (!Busy || string.IsNullOrWhiteSpace(_runningTask)
                        || !string.Equals(evt.Id, _activeTaskId, StringComparison.Ordinal))
                        break;
                    if (OwnsTranslateProgressTask(_runningTask))
                    {
                        _translateProgressStep = userStep;
                        _translateProgressItem = evt.Item;
                        _translateProgressEta = eta;
                        Raise(nameof(TranslateProgressStep)); Raise(nameof(TranslateProgressItem)); Raise(nameof(TranslateProgressEta)); Raise(nameof(TranslateProgressHasEta));
                    }
                    else if (_runningTask is "extract" or "analyze" or "image_inventory" or "image_extract")
                    {
                        _extractProgressStep = userStep;
                        _extractProgressItem = evt.Item ?? "";
                        _extractProgressEta = eta;
                        Raise(nameof(ExtractProgressStep)); Raise(nameof(ExtractProgressItem)); Raise(nameof(ExtractProgressEta)); Raise(nameof(ExtractProgressHasEta));
                    }
                    else if (_runningTask is "patch" or "image_delivery" or "image_apply" or "image_rollback")
                    {
                        _patchProgressStep = userStep;
                        _patchProgressItem = evt.Item ?? "";
                        _patchProgressEta = eta;
                        Raise(nameof(PatchProgressStep)); Raise(nameof(PatchProgressItem)); Raise(nameof(PatchProgressEta)); Raise(nameof(PatchProgressHasEta));
                    }
                    ProgressPercent = boundedPercent;
                    ProgressSubtitle = eventSubtitle;
                    SetOwnedProgress(_runningTask, ProgressPercent, ProgressSubtitle);
                }
                break;
            case "complete":
                if (!TryClaimCompletion(evt))
                    break;
                MarkTaskTerminal(evt.Id);

                _cancelWatchdog?.Cancel();
                _cancelWatchdog?.Dispose();
                _cancelWatchdog = null;

                var completedTask = _runningTask;
                _completingSuperseded = completedTask == "analyze" && _analyzeRejectLate;
                var extractWarning = completedTask == "extract" && evt.ExtractStatus == "PARTIAL"
                    && evt.Severity == "warning" && evt.Error?.Contains("cancel", StringComparison.OrdinalIgnoreCase) != true;
                if (!string.IsNullOrWhiteSpace(evt.Error))
                    AddTaskProgress(evt.Id, completedTask == "extract" && evt.Error.IndexOf("cancel", StringComparison.OrdinalIgnoreCase) < 0
                        ? (evt.Severity == "warning" ? "[cảnh báo] " : "[lỗi] ") + evt.Error
                        : (evt.Severity == "warning" ? "[warning] " : evt.Ok || evt.Error.Contains("cancel", StringComparison.OrdinalIgnoreCase) ? "" : "[error] ") + evt.Error, completedTask);
                if (!evt.Ok && !extractWarning && !string.IsNullOrWhiteSpace(evt.Error) && !evt.Error.Contains("cancelled", StringComparison.OrdinalIgnoreCase))
                    RecordPersistentError(completedTask, evt.Error);
                AddTaskProgress(evt.Id, evt.Ok && evt.Complete != false ? "Hoàn tất"
                    : extractWarning ? "Lấy text một phần — xem cảnh báo" : "Đã dừng — xem Nhật ký", completedTask);
                if (completedTask != "analyze")      // the analysis run stays open until its result (or the stale-input verdict) has been written
                    EndExtractRun(evt.Id, evt.Ok && evt.Complete != false ? "Hoàn tất"
                        : extractWarning ? "Lấy text một phần"
                        : evt.Error?.Contains("cancel", StringComparison.OrdinalIgnoreCase) == true ? "Đã hủy" : "Lỗi");
                if (completedTask == "cloud_export")
                    CloudRepairPackageReady = evt.Ok && (evt.Complete ?? evt.Ok) && File.Exists(CloudRepairPackagePath);
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
                _runningTask = null; RefreshResourcesActive();
                if (completedTask == "resources")
                {
                    CompleteResources(evt);
                    AddTaskProgress(evt.Id, evt.Ok ? "Tài nguyên sẵn sàng" : evt.Error ?? "Tài nguyên chưa sẵn sàng", completedTask);
                    break;
                }
                if (completedTask is "image_batch" or "image_inventory" or "image_extract" or "image_render" or "image_delivery" or "image_apply" or "image_rollback")
                {
                    if (!evt.Ok && evt.Error?.Contains("cancelled", StringComparison.OrdinalIgnoreCase) != true)
                        RecordPersistentError(completedTask, evt.Error ?? "Xử lý ảnh chưa hoàn tất.");
                    var imageCancelled = !evt.Ok && evt.Error?.Contains("cancelled", StringComparison.OrdinalIgnoreCase) == true;
                    SetOwnedProgress(completedTask, evt.Ok ? 100 : null, evt.Ok ? "Hoàn tất" : imageCancelled ? "Đã hủy" : "Đã dừng — xem Nhật ký");
                    CompleteImageTask(completedTask, evt);
                    FinishCancelAndExit();
                    break;
                }
                ApplyDiagnostic(evt);
                if (completedTask == "extract" && evt.Error?.Contains("cancelled", StringComparison.OrdinalIgnoreCase) != true
                    && !CsvEditorDirty && SameCsvPath(CsvEditorPath, Path.Combine(OutputPath, "translation.csv"))
                    && File.Exists(CsvEditorPath))
                    LoadCsvEditor(CsvEditorPath, reload: true);
                var isAnalyze = completedTask == "analyze";
                var retranslateOwnsEditorReload = _csvEditorRetranslatePending;
                var cancelled = evt.Error?.Contains("cancelled", StringComparison.OrdinalIgnoreCase) == true;
                if (completedTask == "translate" && cancelled)
                {
                    _translateProgressStep = "Đã hủy";
                    _translateProgressItem = "";
                    _translateProgressEta = "";
                    Raise(nameof(TranslateProgressStep));
                    Raise(nameof(TranslateProgressItem));
                    Raise(nameof(TranslateProgressEta));
                    Raise(nameof(TranslateProgressHasEta));
                }
                var renpySdkIncomplete = completedTask == "extract" && evt.RenpySdkMissing;
                if (completedTask == "extract")
                {
                    RenpySdkAction = RenpySdkRecovery.ResolveAction(
                        RenpySdkAction, evt.RenpySdkMissing, evt.Ok, cancelled);
                    RenpySdkError = RenpySdkAction is "missing" or "error" ? evt.Error ?? evt.Summary ?? "" : "";
                    if (evt.RenpySdkMissing)
                        ExposeRenpySdkRecoveryOptions();
                }
                var extractionIncomplete = completedTask == "extract"
                    && (evt.ExtractStatus is "PARTIAL" or "EMPTY" || (evt.Ok && evt.Complete == false));
                if (completedTask == "patch" && (cancelled || !evt.Ok || evt.Complete == false))
                {
                    PatchResultsAvailable = true;
                    PatchResultsExpanded = true;
                }
                var needsHumanReview = evt.HumanReviewRequiredCount > 0;
                var isExternalTranslationImport = completedTask == "external_translation_import";
                var externalRemaining = Math.Max(evt.Pending, evt.ReviewOnly);
                // A count is only real when the worker wrote a package (it then reports its extract status); an SDK recovery
                // failure (download, chosen SDK) carries no evidence count and must not invent one.
                var manualReviewText = renpySdkIncomplete
                    ? !string.IsNullOrWhiteSpace(evt.ExtractStatus)
                        ? $"Lấy text chưa đầy đủ do thiếu công cụ Ren'Py; đã xuất {evt.ReviewOnly} dòng chỉ để xem lại (không dịch, không tạo patch)."
                        : "Lấy text chưa đầy đủ do thiếu công cụ Ren'Py; chưa tạo gói. Chọn SDK đã cài hoặc thử tải lại."
                    : extractionIncomplete
                    ? evt.ExtractStatus == "EMPTY"
                        ? "Không có text sử dụng được — xem report, kiểm input hoặc mức quét."
                        : evt.PatchScope == "VERIFIED_MAIN_SUBSET" && !string.IsNullOrWhiteSpace(evt.Error)
                        ? evt.Error
                        : $"Lấy text một phần — {evt.ReviewOnly} dòng cần xem lại; mở CSV/report và xử lý lỗi trước khi dịch."
                    : isExternalTranslationImport
                    ? $"Đã nhập {evt.Applied} dòng an toàn; còn {externalRemaining} dòng cần sửa trong CSV"
                    : needsHumanReview
                    ? $"Cần duyệt thủ công {evt.HumanReviewRequiredCount} dòng trước khi Patch"
                    : $"Dịch một phần — chưa dịch {evt.Pending}, cần xem lại {evt.ReviewOnly}, chưa thể dùng {evt.Blocked}";
                var fullyComplete = isAnalyze
                    ? evt.Ok && !cancelled
                    : evt.Ok && (evt.Complete ?? evt.Ok)
                    && evt.Pending == 0
                    && evt.ReviewOnly == 0
                    && evt.Blocked == 0;
                var partialOk = !isAnalyze && !fullyComplete && !cancelled && (evt.Ok || needsHumanReview || renpySdkIncomplete || extractionIncomplete);
                if (fullyComplete)
                    ProgressPercent = 100;
                ProgressSubtitle = cancelled ? "Đã hủy"
                    : fullyComplete ? "Hoàn tất"
                    : partialOk ? manualReviewText
                    : "Lỗi";
                SetOwnedProgress(completedTask, fullyComplete ? 100 : null, ProgressSubtitle);
                StatusText = cancelled ? "Đã hủy"
                    : isAnalyze ? (fullyComplete ? "Đã phân tích" : "Phân tích lỗi")
                    : fullyComplete ? "Hoàn tất"
                    : partialOk ? (renpySdkIncomplete ? "Lấy text chưa đầy đủ" : extractionIncomplete ? (evt.ExtractStatus == "EMPTY" ? "Không có text" : "Lấy text một phần") : isExternalTranslationImport ? "Cần sửa CSV" : "Dịch một phần")
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
                            ? renpySdkIncomplete || extractionIncomplete
                                ? manualReviewText
                                : needsHumanReview
                                ? manualReviewText
                                : isExternalTranslationImport
                                    ? manualReviewText
                                    : $"Dịch một phần — đã dịch {evt.Translated}, chưa dịch {evt.Pending}, cần xem lại {evt.ReviewOnly}, chưa thể dùng {evt.Blocked}"
                            : UiText.Msg("Lỗi — {0}", evt.Error ?? "worker báo lỗi");
                if (!string.IsNullOrWhiteSpace(evt.Summary)) AppendLog(evt.Summary);
                if (!string.IsNullOrWhiteSpace(evt.Error))
                    AppendLog(cancelled
                        ? CancelledTerminalText(completedTask, evt)
                        : needsHumanReview || renpySdkIncomplete || extractionIncomplete ? evt.Error : $"Lỗi: {evt.Error}");

                if (cancelled)
                {
                    if (completedTask == "analyze")
                    {
                        AnalyzeStatusText = "Đã hủy phân tích game";
                        AnalyzeScanErrorText = "Không có inventory hoàn tất để sử dụng.";
                        var reportPath = ResolveAnalyzeReportPath();
                        AnalyzeHasReport = File.Exists(reportPath);
                        AnalyzeReportPath = AnalyzeHasReport ? reportPath : "";
                        AnalyzeResultsExpanded = true;
                    }
                    RequestCompletion("VNText Studio — Đã hủy", "Đã hủy tác vụ.", "info");
                }
                else if (!evt.Ok && !partialOk)
                {
                    var errMsg = string.IsNullOrWhiteSpace(evt.Error) ? "Tác vụ thất bại" : evt.Error!;
                    RequestCompletion("VNText Studio — Lỗi", errMsg, "error");
                    RecordPersistentError(completedTask, errMsg, RenpySdkAction is "missing" or "error"
                        ? "Mở Cài đặt › Dữ liệu để chuẩn bị hoặc chọn Ren'Py SDK, rồi lấy text lại."
                        : "");      // the toast is transient; this stays until acknowledged
                    LogExpanded = true;
                }
                else if (fullyComplete)
                {
                    ResolvePersistentErrorIfSameTask(completedTask);
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
                    if (!(completedTask == "analyze" && _analyzeRejectLate))
                    {
                        RequestCompletion("VNText Studio — Hoàn tất", doneMsg, "success");
                        LogExpanded = true;
                    }
                }
                else if (partialOk)
                {
                    // A partial extract keeps ONE persistent, readable banner: a neutral review warning for expected limits,
                    // the red error banner only when the worker reports a genuine discovery/extract failure alongside the package.
                    var genuineExtractFailure = completedTask == "extract" && evt.Severity == "error";
                    RequestCompletion(
                        genuineExtractFailure ? "VNText Studio — Lỗi lấy text"
                        : renpySdkIncomplete ? "VNText Studio — Lấy text chưa đầy đủ" : "VNText Studio — Chưa hoàn tất",
                        manualReviewText,
                        genuineExtractFailure ? "error" : "warning");
                    if (completedTask == "extract")
                    {
                        var persistentText = string.IsNullOrWhiteSpace(evt.Error) ? manualReviewText : evt.Error!;
                        if (genuineExtractFailure) RecordPersistentError("extract", persistentText);
                        else RecordPersistentNotice("extract", persistentText);
                    }
                    LogExpanded = true;
                }

                if (completedTask == "analyze" && (cancelled || _analyzeRejectLate)) _extractAfterAnalyze = false;
                var analyzeRunId = evt.Id;
                var analyzeRunStatus = "Lỗi";
                if (!cancelled && completedTask == "analyze" && _analyzeRejectLate)
                {
                    // The inputs changed while this analysis ran: its report describes the OLD input.
                    StatusText = "Đầu vào đã đổi";
                    StepStatusLine = "Kết quả phân tích của đầu vào cũ đã bị bỏ — hãy phân tích lại";
                    AddExtractRunLine(analyzeRunId, "Đầu vào đã đổi trong lúc phân tích: bỏ kết quả của đầu vào cũ.");
                    analyzeRunStatus = "Đã bỏ kết quả cũ";
                    AppendLog("Bỏ kết quả phân tích cũ vì đầu vào đã đổi trong lúc chạy.");
                }
                else if (!cancelled && completedTask == "analyze")
                {
                    ApplyAnalyzeResult(evt);
                    WriteAnalyzeResultToRun(analyzeRunId);
                    analyzeRunStatus = evt.Ok ? "Phân tích xong" : "Lỗi";
                    if (!_analyzeAuto)
                    {
                        SelectedTab = WorkflowTabs.Extract;
                        AppendLog(evt.Ok
                            ? "Phân tích game xong — xem coverage rồi quyết định Lấy text."
                            : "Phân tích game chưa đủ inventory — xem lỗi quét trước khi Lấy text.");
                    }
                    AfterAnalyzeTerminal(!evt.Ok);
                }
                else if (!cancelled && evt.Ok && completedTask is not null)
                {
                    _lastCompletedTask = completedTask;
                    if (completedTask == "extract" && fullyComplete)
                    {
                        var extractedCsv = Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "translation.csv");
                        TranslationCsvPath = extractedCsv;
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

                if (completedTask == "analyze")
                {
                    if (cancelled)
                    {
                        _analyzeOutcome = AnalyzeOutcome.Cancelled;
                        AddExtractRunLine(analyzeRunId, "Đã hủy phân tích game; không có kết quả nào được giữ.");
                        analyzeRunStatus = "Đã hủy";
                    }
                    EndExtractRun(analyzeRunId, analyzeRunStatus);
                    RaiseAnalyzeSummary();
                }
                if (completedTask == "patch" && evt.Ok && !cancelled)
                {
                    _patchArtifactBehindCsv = false;          // a Build of the CURRENT CSV revision succeeded: its artifact is fresh again
                    RaisePatchBadge();
                }
                if (completedTask == "translate")
                {
                    if (!retranslateOwnsEditorReload)
                        _ = RefreshCsvEditorAfterTranslateAsync(TranslationCsvPath);
                    PatchResultsAvailable = true;
                    PatchResultsExpanded = true;
                    PatchPreflightEvaluated = false;
                    // A cancelled terminal carries sentinel counts, not measurements; the
                    // on-disk readiness refresh below supplies the truthful safe count.
                    CsvValidationMessage = cancelled
                        ? "Đã hủy — đang đọc lại số dòng đã dịch an toàn…"
                        : $"Đã dịch {evt.Translated}; chưa dịch {evt.Pending}, cần xem lại {evt.ReviewOnly}, chưa thể dùng {evt.Blocked}";
                    _translateLastRunCancelled = cancelled;
                    Raise(nameof(TranslateReadinessText));
                    PatchPreflightOk = false;
                    PatchEligibleCount = 0;
                    PatchBlockedCount = 0;
                    PatchPreflightMessage = fullyComplete
                        ? "CSV đã đổi sau dịch — kiểm tra lại trước khi Patch."
                        : "Dịch chưa hoàn tất — chưa thể tạo Patch.";
                }
                RefreshWorkflow();
                if (completedTask == "translate" && cancelled)
                    RefreshTranslateReadiness(cancelledSummary: true);
                // The selected CSV can already point at this same path from a
                // previous readiness check. Revalidate after Extract has closed
                // and written its package so a stale "file missing" result cannot
                // survive the automatic navigation to Translate.
                if (completedTask == "extract" && fullyComplete)
                {
                    TranslationCsvPath = Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "translation.csv");
                    RefreshTranslateReadiness(syncCsvValidation: true);
                }
                else if (completedTask == "extract" && !cancelled)
                {
                    // A text-less package (EMPTY/PARTIAL) can still hold OCR'd images: refresh the
                    // Translate card so it says so instead of keeping a stale readiness line.
                    RefreshTranslateReadiness();
                }
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
                    StepStatusLine = UiText.Msg("Lỗi — {0}", evt.Error ?? "worker báo lỗi");
                }
                else if (fullyComplete)
                {
                    ProgressPercent = 100;
                    var lateAnalyze = isAnalyze && _analyzeRejectLate;
                    ProgressSubtitle = lateAnalyze ? "Đầu vào đã đổi" : isAnalyze ? "Phân tích hoàn tất" : "Hoàn tất";
                    StatusText = lateAnalyze ? "Đầu vào đã đổi" : isAnalyze ? "Đã phân tích" : "Hoàn tất";
                    StepStatusLine = lateAnalyze
                        ? "Kết quả phân tích của đầu vào cũ đã bị bỏ — hãy phân tích lại"
                        : isAnalyze
                        ? "Phân tích game hoàn tất — xem coverage trước khi Lấy text"
                        : "Hoàn tất bước — cập nhật quy trình";
                }
                else if (partialOk)
                {
                    ProgressSubtitle = manualReviewText;
                    StatusText = renpySdkIncomplete
                        ? "Lấy text chưa đầy đủ"
                        : extractionIncomplete ? (evt.ExtractStatus == "EMPTY" ? "Không có text" : "Lấy text một phần")
                        : isExternalTranslationImport ? "Cần sửa CSV" : "Dịch một phần";
                    StepStatusLine =
                        (renpySdkIncomplete || extractionIncomplete
                            ? manualReviewText
                            : needsHumanReview
                            ? manualReviewText
                            : isExternalTranslationImport
                                ? manualReviewText
                                : $"Dịch một phần — đã dịch {evt.Translated}, chưa dịch {evt.Pending}, cần xem lại {evt.ReviewOnly}, chưa thể dùng {evt.Blocked}");
                }
                if (!string.IsNullOrWhiteSpace(DiagnosticStatusLine))
                    StepStatusLine = $"{StepStatusLine} — {DiagnosticStatusLine}";
                if (completedTask == "patch" && fullyComplete)
                    ApplyPatchDelivery(evt);
                FinishCancelAndExit();
                break;
            case "error":
                AppendLog($"Lỗi: {evt.Error}");
                AddExtractRunLine(evt.Id, "[error] " + evt.Error);
                if (!string.IsNullOrWhiteSpace(evt.Id) && _terminalTaskIds.Contains(evt.Id))
                    break;
                if (Busy && !string.IsNullOrWhiteSpace(evt.Id)
                    && !string.Equals(evt.Id, _activeTaskId, StringComparison.Ordinal))
                    break;
                if (Busy && (string.IsNullOrWhiteSpace(evt.Id)
                    || string.Equals(evt.Id, _activeTaskId, StringComparison.Ordinal)))
                {
                    StatusText = "Lỗi worker";
                    ProgressSubtitle = "Worker báo lỗi; đang chờ kết quả cuối để dừng an toàn…";
                    SetOwnedProgress(_runningTask, text: ProgressSubtitle);
                    AddTaskProgress(_activeTaskId, ProgressSubtitle);
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
        PatchPreflightEvaluated = false;
        PatchResultsAvailable = true;
        PatchResultsExpanded = true;
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
        PatchPreflightEvaluated = false;
        PatchResultsAvailable = true;
        PatchResultsExpanded = true;
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

    /// <summary>
    /// The cancelled-terminal line is task specific: the "keep the safe part, run again to continue translating" copy
    /// belongs to translation only.  A cancelled Patch states what happened to its output directory (the worker keeps it untouched
    /// and says it may be partial) and tells the user to choose a new empty output directory.
    /// </summary>
    internal static string CancelledTerminalText(string? task, WorkerEvent evt)
    {
        if (string.Equals(task, "patch", StringComparison.Ordinal))
            return !string.IsNullOrWhiteSpace(evt.PatchInstallInstructions)
                ? evt.PatchInstallInstructions!
                : "Đã hủy tạo patch — thư mục xuất chưa được xác nhận là patch hoàn chỉnh; kiểm tra hoặc chọn thư mục xuất trống rồi tạo lại. Game gốc không bị thay đổi.";
        return "Đã hủy tác vụ — phần đã hoàn tất an toàn được giữ nguyên; chạy lại để dịch tiếp.";
    }

    /// <summary>The delivery heading names the file the current build actually produced; no fixed stub name is assumed.</summary>
    internal static string PatchDeliveryLabelFor(string? payloadPath, string? instructions = null)
    {
        var name = string.IsNullOrWhiteSpace(payloadPath) ? "" : Path.GetFileName(payloadPath.TrimEnd('\\', '/'));
        if (!name.EndsWith(".exe", StringComparison.OrdinalIgnoreCase))      // folder payload: the installer the worker itself names in its instructions
            name = !string.IsNullOrEmpty(instructions) && instructions.Contains("VNTextPatchInstaller.exe", StringComparison.Ordinal) ? "VNTextPatchInstaller.exe" : "";
        return name.Length > 0 ? UiText.Msg("Gói patch có installer — {0}", name) : "Gói patch có installer";
    }

    private void ApplyPatchDelivery(WorkerEvent evt)
    {
        if (string.Equals(evt.PatchDelivery, "renpy_native_overlay", StringComparison.OrdinalIgnoreCase))
        {
            PatchDeliveryLabel = "Ren'Py — native overlay (copy vào game root)";
            PatchInstallInstructions = evt.PatchInstallInstructions ?? "";
            PatchDeliveryReady = true;
            StepStatusLine = "Ren'Py overlay đã sẵn sàng — copy COPY_TO_GAME_ROOT vào game root.";
        }
        else if (string.Equals(evt.PatchDelivery, "unity_installer", StringComparison.OrdinalIgnoreCase)
            || string.Equals(evt.PatchDelivery, "renpy_installer", StringComparison.OrdinalIgnoreCase))
        {
            // The installer route also delivers plain text and other supported formats: name the delivery, not an engine.
            PatchDeliveryLabel = PatchDeliveryLabelFor(evt.PatchPayloadPath, evt.PatchInstallInstructions);
            PatchInstallInstructions = evt.PatchInstallInstructions ?? "";
            PatchDeliveryReady = true;
        }
        if (!string.IsNullOrWhiteSpace(evt.PatchPayloadPath))
            AppendLog($"Gói cài đặt: {evt.PatchPayloadPath}");
        if (!string.IsNullOrWhiteSpace(evt.PatchInstallInstructions))
            AppendLog(evt.PatchInstallInstructions);
    }

}
