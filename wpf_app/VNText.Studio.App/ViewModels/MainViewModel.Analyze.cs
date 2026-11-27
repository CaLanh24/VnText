using System.IO;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    private string _analyzeStatusText = "Chưa phân tích game";
    private string _analyzeReportPath = "";
    private string _analyzeScanErrorText = "";
    private bool _analyzeHasReport;
    private bool _analyzeResultsExpanded;
    private string _analyzeUnityStatus = "NOT_DETECTED";
    private string _analyzeEngineSummary = "Chưa xác định loại game";
    private string _analyzeEngineDetails = "";
    private bool _analyzeInventoryComplete;
    private int _analyzeResourceCount;
    private int _analyzeTextCandidateCount;
    private int _analyzePatchableCount;
    private int _analyzeExtractOnlyCount;
    private int _analyzeReviewRiskCount;
    private int _analyzeUnknownCount;
    private int _analyzeScanErrorCount;
    // Identity (input + output package) of the analysis that is running or shown.  Null means
    // nothing is attributed to the current inputs.  A change of either path clears the shown
    // result and makes the still-running analysis of the OLD input ignorable (late event).
    private string? _analyzeIdentity;
    private bool _analyzeRejectLate;
    // What the inline summary under "Thư mục game và nơi lưu bản dịch" reports for the CURRENT input.  Anything attributed to an older input is cleared by InvalidateAnalyzeIfInputsChanged.
    internal enum AnalyzeOutcome { None, Identified, IdentifiedIncomplete, Unsupported, Failed, Cancelled }
    private AnalyzeOutcome _analyzeOutcome;
    private string? _nestedRuntimePath;
    private bool _gameFolderReadError;
    private string _gameFolderBoundaryMessage => _gameFolderReadError
        ? UiText.Translate("Không thể kiểm tra thư mục game. Hãy chọn lại thư mục có thể đọc.")
        : _nestedRuntimePath is null ? ""
        : UiText.Msg("Đây là thư mục chứa game. Hãy chọn thư mục game cụ thể, ví dụ: {0}", _nestedRuntimePath);

    private void RefreshGameFolderBoundary()
    {
        try
        {
            _nestedRuntimePath = GameFolderBoundary.FindNestedRuntime(InputPath);
            _gameFolderReadError = false;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.Security.SecurityException or ArgumentException)
        {
            _nestedRuntimePath = null;
            _gameFolderReadError = true;
        }
        if (!string.IsNullOrEmpty(_gameFolderBoundaryMessage))
        {
            AnalyzeStatusText = _gameFolderBoundaryMessage;
            AnalyzeEngineSummary = "Chưa xác định loại game";
            AnalyzeInventoryComplete = false;
        }
        Raise(nameof(ExtractStatusText));
        RunExtractCommand?.RaiseCanExecuteChanged();
        AnalyzeCommand?.RaiseCanExecuteChanged();
    }

    internal static string AnalyzeIdentityOf(string? input, string? output)
    {
        static string Norm(string? p)
        {
            if (string.IsNullOrWhiteSpace(p)) return "";
            try { return Path.GetFullPath(p.Trim().Trim('"')).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar).ToUpperInvariant(); }
            catch (Exception ex) when (ex is ArgumentException or NotSupportedException or PathTooLongException)
            { return p.Trim().ToUpperInvariant(); }
        }
        return Norm(input) + "|" + Norm(output);
    }

    /// <summary>
    /// Detection reads the SOURCE; choosing only another output folder does not change what was detected.  When the current, successful
    /// analysis belongs to exactly this source and the previous output, it is re-keyed to the new output instead of being run (and announced) again.
    /// Any other state (changed source, running/failed/cancelled/unsupported analysis, late-rejected result, empty output) keeps the full path.
    /// </summary>
    private bool TryReuseSourceAnalysisForNewOutput(string? previousOutput, string? newOutput)
    {
        if (string.IsNullOrWhiteSpace(newOutput) || string.IsNullOrWhiteSpace(InputPath) || Busy || _analyzeRejectLate) return false;
        if (_analyzeOutcome is not (AnalyzeOutcome.Identified or AnalyzeOutcome.IdentifiedIncomplete)) return false;
        if (_analyzeIdentity is null || _analyzeIdentity != AnalyzeIdentityOf(InputPath, previousOutput)) return false;
        _analyzeIdentity = AnalyzeIdentityOf(InputPath, newOutput);
        _autoAnalyzeRevision++;                       // a debounce still pending for the old output must not start a second run
        _autoAnalyzeDebouncing = false;
        _autoAnalyzeWaitsForIdle = false;
        RaiseAnalyzeSummary();
        return true;
    }

    private void InvalidateAnalyzeIfInputsChanged()
    {
        if (_analyzeIdentity is null || _analyzeIdentity == AnalyzeIdentityOf(InputPath, OutputPath))
            return;
        _analyzeIdentity = null;
        _analyzeRejectLate = true;
        _analyzeOutcome = AnalyzeOutcome.None;
        if (Busy && _runningTask == "analyze") AddExtractRunLine(_activeTaskId, "Đầu vào đã đổi: kết quả phân tích đang chạy sẽ bị bỏ.");
        AnalyzeInventoryComplete = false;
        AnalyzeUnityStatus = "NOT_DETECTED";
        AnalyzeEngineSummary = "Chưa xác định loại game";
        AnalyzeEngineDetails = "";
        AnalyzeAssetLines = Array.Empty<string>();
        AnalyzeResourceCount = 0;
        AnalyzeTextCandidateCount = 0;
        AnalyzePatchableCount = 0;
        AnalyzeExtractOnlyCount = 0;
        AnalyzeReviewRiskCount = 0;
        AnalyzeUnknownCount = 0;
        AnalyzeScanErrorCount = 0;
        AnalyzeReportPath = "";
        AnalyzeHasReport = false;
        AnalyzeResultsExpanded = false;
        AnalyzeScanErrorText = "";
        AnalyzeStatusText = "Đầu vào đã đổi • cần phân tích lại";
        RaiseAnalyzeSummary();
    }

    /// <summary>One persistent sentence for the person: the engine that was identified and what they can do next, or why nothing could be identified.
    /// Identifying an engine is NOT a claim that patching works; the sentence says so and the counts below keep the evidence.</summary>
    public string AnalyzeNextActionText
    {
        get
        {
            if (!string.IsNullOrEmpty(_gameFolderBoundaryMessage)) return UiText.Translate("Chọn thư mục game cụ thể để tiếp tục.");
            if (AnalyzeBusy) return UiText.Translate("Đang nhận diện loại game…");
            if (string.IsNullOrWhiteSpace(InputPath)) return UiText.Translate("Chọn thư mục game để tự nhận diện loại game.");
            if (_analyzeIdentity is null) return UiText.Translate("Đầu vào đã đổi; hệ thống sẽ nhận diện lại khi đủ nguồn và nơi lưu bản dịch.");
            return _analyzeOutcome switch
            {
                AnalyzeOutcome.Identified => UiText.Format("{0} · Sẵn sàng lấy text.", UiText.Translate(_analyzeEngineSummary).Replace("Engine: ", "").Replace("Loại game: ", "")),
                AnalyzeOutcome.IdentifiedIncomplete => UiText.Format("Đã nhận diện: {0}, nhưng danh sách dữ liệu của game chưa đầy đủ. Xem lỗi quét trước khi Lấy text.", UiText.Translate(_analyzeEngineSummary).Replace("Engine: ", "").Replace("Loại game: ", "")),
                AnalyzeOutcome.Unsupported => UiText.Translate("Chưa nhận diện được loại game được hỗ trợ trong thư mục này. Kiểm tra lại thư mục game đã chọn."),
                AnalyzeOutcome.Failed => UiText.Translate("Phân tích không hoàn tất. Xem Nhật ký, rồi chọn lại nguồn để thử lại."),
                AnalyzeOutcome.Cancelled => UiText.Translate("Đã hủy phân tích. Chọn lại nguồn để nhận diện lại."),
                _ => "",
            };
        }
    }

    /// <summary>True while detection is debouncing, waiting for the worker, or running.</summary>
    public bool AnalyzeBusy => AnalysisInFlightOrPending;

    internal void RaiseAnalyzeSummary()
    {
        Raise(nameof(AnalyzeNextActionText));
        Raise(nameof(AnalyzeBusy));
    }

    private void WriteAnalyzeResultToRun(string? runId)
    {
        AddExtractRunLine(runId, UiText.Translate(_analyzeStatusText));
        AddExtractRunLine(runId, UiText.Translate(_analyzeEngineSummary));
        AddExtractRunLine(runId, _analyzeScanErrorText.Length > 0 ? UiText.Translate(_analyzeScanErrorText) : "");
        if (!string.IsNullOrWhiteSpace(_analyzeReportPath)) AddExtractRunLine(runId, UiText.Format("Báo cáo: {0}", _analyzeReportPath));
    }

    public string AnalyzeStatusText
    {
        get => !string.IsNullOrEmpty(_gameFolderBoundaryMessage) ? _gameFolderBoundaryMessage : UiText.Translate(_analyzeStatusText);
        private set { if (Set(ref _analyzeStatusText, value)) RaiseAnalyzeSummary(); }
    }

    public string AnalyzeReportPath
    {
        get => _analyzeReportPath;
        private set => Set(ref _analyzeReportPath, value);
    }

    public string AnalyzeScanErrorText
    {
        get => _analyzeScanErrorText;
        private set => Set(ref _analyzeScanErrorText, value);
    }

    public bool AnalyzeHasReport
    {
        get => _analyzeHasReport;
        private set => Set(ref _analyzeHasReport, value);
    }

    public bool AnalyzeResultsExpanded
    {
        get => _analyzeResultsExpanded;
        set => Set(ref _analyzeResultsExpanded, value);
    }

    public string AnalyzeUnityStatus
    {
        get => _analyzeUnityStatus;
        private set => Set(ref _analyzeUnityStatus, value);
    }

    public string AnalyzeEngineSummary
    {
        get => _analyzeEngineSummary;
        private set => Set(ref _analyzeEngineSummary, value);
    }

    public string AnalyzeEngineDetails
    {
        get => UiText.Translate(_analyzeEngineDetails);
        private set => Set(ref _analyzeEngineDetails, value);
    }

    private IReadOnlyList<string> _analyzeAssetLines = Array.Empty<string>();
    private const int AnalyzeAssetLineCap = 14;

    /// <summary>Per-font / per-image scan status for a Ren'Py game, shown under the scan counts (bounded; the full list stays in the report).</summary>
    public IReadOnlyList<string> AnalyzeAssetLines
    {
        get => _analyzeAssetLines;
        private set { if (Set(ref _analyzeAssetLines, value)) Raise(nameof(AnalyzeHasAssets)); }
    }

    public bool AnalyzeHasAssets => _analyzeAssetLines.Count > 0;

    private static IReadOnlyList<string> CapAssetLines(IReadOnlyList<string> lines)
    {
        if (lines.Count <= AnalyzeAssetLineCap) return lines;
        var shown = lines.Take(AnalyzeAssetLineCap - 1).ToList();
        shown.Add(UiText.Format("… và {0} dòng nữa; xem đầy đủ trong báo cáo phân tích.", lines.Count - shown.Count));
        return shown;
    }

    public bool AnalyzeInventoryComplete
    {
        get => _analyzeInventoryComplete;
        private set => Set(ref _analyzeInventoryComplete, value);
    }

    public int AnalyzeResourceCount
    {
        get => _analyzeResourceCount;
        private set => Set(ref _analyzeResourceCount, value);
    }

    public int AnalyzeTextCandidateCount
    {
        get => _analyzeTextCandidateCount;
        private set => Set(ref _analyzeTextCandidateCount, value);
    }

    public int AnalyzePatchableCount
    {
        get => _analyzePatchableCount;
        private set => Set(ref _analyzePatchableCount, value);
    }

    public int AnalyzeExtractOnlyCount
    {
        get => _analyzeExtractOnlyCount;
        private set => Set(ref _analyzeExtractOnlyCount, value);
    }

    public int AnalyzeReviewRiskCount
    {
        get => _analyzeReviewRiskCount;
        private set => Set(ref _analyzeReviewRiskCount, value);
    }

    public int AnalyzeUnknownCount
    {
        get => _analyzeUnknownCount;
        private set => Set(ref _analyzeUnknownCount, value);
    }

    public int AnalyzeScanErrorCount
    {
        get => _analyzeScanErrorCount;
        private set => Set(ref _analyzeScanErrorCount, value);
    }

    // Engine detection is automatic: choosing the source (or output) schedules one debounced analysis.  Every schedule bumps the
    // revision, so a stale delay, a stale run or a stale result of an older input can never apply; Extract waits for the detection
    // of the CURRENT input and then runs under the same readiness guards.
    internal const int AutoAnalyzeDebounceMilliseconds = 350;
    private bool _autoAnalyzeEnabled;
    private int _autoAnalyzeRevision;
    private bool _autoAnalyzeDebouncing;
    private bool _autoAnalyzeWaitsForIdle;
    private bool _analyzeAuto;
    private bool _extractAfterAnalyze;

    internal bool AnalysisInFlightOrPending => _autoAnalyzeDebouncing || _autoAnalyzeWaitsForIdle || (Busy && _runningTask == "analyze");

    private async void ScheduleAutoAnalyze()
    {
        if (!_autoAnalyzeEnabled) return;
        var revision = ++_autoAnalyzeRevision;
        _autoAnalyzeWaitsForIdle = false;
        _extractAfterAnalyze = false;
        _extractReadyAfterAnalyze = false;
        if (!string.IsNullOrEmpty(_gameFolderBoundaryMessage))
        {
            _autoAnalyzeDebouncing = false;
            return;
        }
        if (string.IsNullOrWhiteSpace(InputPath))
        {
            _autoAnalyzeDebouncing = false;
            return;
        }
        if (string.IsNullOrWhiteSpace(OutputPath))
        {
            _autoAnalyzeDebouncing = false;
            AnalyzeStatusText = "Chọn nơi lưu bản dịch để tự nhận diện loại game";
            return;
        }
        _autoAnalyzeDebouncing = true;
        AnalyzeStatusText = "Đang nhận diện loại game…";
        await Task.Delay(AutoAnalyzeDebounceMilliseconds);
        if (revision != _autoAnalyzeRevision || _disposed != 0) return;
        _autoAnalyzeDebouncing = false;
        StartAutoAnalyze();
    }

    private void StartAutoAnalyze()
    {
        if (string.IsNullOrWhiteSpace(InputPath) || string.IsNullOrWhiteSpace(OutputPath)) return;
        if (Busy)
        {
            _autoAnalyzeWaitsForIdle = true;
            return;
        }
        _autoAnalyzeWaitsForIdle = false;
        RunAnalyze(auto: true);
    }

    private bool _extractReadyAfterAnalyze;

    private void ResumeAutoAnalyzeWhenIdle()
    {
        if (Busy) return;
        if (_extractReadyAfterAnalyze)
        {
            _extractReadyAfterAnalyze = false;
            RunExtract();
            return;
        }
        if (_autoAnalyzeWaitsForIdle) StartAutoAnalyze();
    }

    /// <summary>Extract pressed while detection of this input is pending or running: start/finish it, then extract exactly once.</summary>
    private bool DeferExtractUntilDetected()
    {
        if (!AnalysisInFlightOrPending) return false;
        _extractAfterAnalyze = true;
        StatusText = "Đang nhận diện loại game; sẽ lấy text ngay sau đó";
        if (_autoAnalyzeDebouncing)
        {
            _autoAnalyzeRevision++;
            _autoAnalyzeDebouncing = false;
            StartAutoAnalyze();
        }
        return true;
    }

    private void AfterAnalyzeTerminal(bool lateOrCancelled)
    {
        var extract = _extractAfterAnalyze && !lateOrCancelled && !_analyzeRejectLate;
        _extractAfterAnalyze = false;
        _extractReadyAfterAnalyze = extract;      // runs when the analyze task has released Busy
    }

    private void RunAnalyze(bool auto = false)
    {
        RefreshGameFolderBoundary();
        if (!string.IsNullOrEmpty(_gameFolderBoundaryMessage)) return;
        _analyzeAuto = auto;
        AnalyzeResultsExpanded = false;
        AnalyzeHasReport = false;
        AnalyzeReportPath = "";
        if (string.IsNullOrWhiteSpace(InputPath))
        {
            AnalyzeStatusText = "Chưa chọn thư mục game";
            AnalyzeResultsExpanded = true;
            StatusText = "Chưa chọn game";
            AppendLog("Chọn thư mục game trước khi phân tích.");
            SelectedTab = WorkflowTabs.Extract;
            return;
        }
        if (string.IsNullOrWhiteSpace(OutputPath))
        {
            AnalyzeStatusText = "Chưa chọn nơi lưu bản dịch";
            AnalyzeResultsExpanded = true;
            StatusText = "Chưa chọn nơi lưu bản dịch";
            AppendLog("Chọn nơi lưu bản dịch trước khi phân tích.");
            SelectedTab = WorkflowTabs.Extract;
            return;
        }

        var reportDirectory = WorkflowStatus.ResolvePackageDir(OutputPath);
        _analyzeIdentity = AnalyzeIdentityOf(InputPath, OutputPath);
        _analyzeRejectLate = false;
        _analyzeOutcome = AnalyzeOutcome.None;
        AnalyzeStatusText = "Đang phân tích game…";
        AnalyzeReportPath = "";
        AnalyzeScanErrorText = "";   // the running engine/progress line already says it is checking; real scan errors appear on completion
        ResetAnalyzeMetrics();
        BeginTask("analyze", new
        {
            src = InputPath,
            report_out = reportDirectory,
            include_sha256 = true,
            probe_unity_objects = true,
        }, "Đang phân tích game…");
    }

    private void ApplyAnalyzeResult(WorkerEvent evt)
    {
        var reportPath = ResolveAnalyzeReportPath();
        var snapshot = UnityAnalysisReportReader.TryRead(reportPath, out var error);
        AnalyzeResultsExpanded = true;
        AnalyzeHasReport = File.Exists(reportPath);
        if (snapshot is null)
        {
            AnalyzeInventoryComplete = false;
            AnalyzeUnityStatus = "UNKNOWN";
            AnalyzeEngineSummary = "Loại game: chưa xác định";
            AnalyzeEngineDetails = "Không đọc được báo cáo Unity; chưa có đủ bằng chứng để xác định loại game.";
            _analyzeOutcome = AnalyzeOutcome.Failed;
            RaiseAnalyzeSummary();
            AnalyzeStatusText = evt.Ok
                ? "Đã chạy nhưng không đọc được report"
                : "Phân tích thất bại";
            AnalyzeReportPath = AnalyzeHasReport ? reportPath : "";
            AnalyzeScanErrorText = string.IsNullOrWhiteSpace(error)
                ? "Không tìm thấy báo cáo unity_analysis.json; chưa xác minh đủ dữ liệu của game."
                : $"Không đọc được report: {error}";
            return;
        }

        AnalyzeInventoryComplete = snapshot.InventoryComplete && evt.Ok;
        AnalyzeUnityStatus = snapshot.UnityStatus;
        // The worker classified the engine once during this very scan; the app never walks the game folder again, so the engine,
        // the font/image inventory and the status always come from the same source and the same moment.
        string renpyEvidence;
        if (!string.IsNullOrEmpty(snapshot.EngineDetection))
            renpyEvidence = snapshot.EngineDetection switch
            {
                "RENPY_LOOSE_SOURCE" => "loose_source",
                "RENPY_COMPILED_ONLY" => "compiled_source",
                "RENPY_ARCHIVE_SOURCE" => "archive_source",
                "MIXED" => "loose_source",
                "RENPY_ARCHIVE_UNSUPPORTED" => "archive_unsupported",
                _ => snapshot.HasRenpyAssets ? "assets_only" : "none",
            };
        else
        {
            try { renpyEvidence = RenpyGameDetector.GetRenpyEvidenceKind(InputPath, CancellationToken.None); }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.Security.SecurityException)
            { renpyEvidence = "unknown"; }
        }
        var unityDetected = snapshot.UnityStatus == "DETECTED" || snapshot.EngineDetection == "UNITY";
        AnalyzeEngineSummary = unityDetected && renpyEvidence is not ("none" or "assets_only")
            ? "Loại game: Unity + Ren’Py"
            : unityDetected
                ? "Loại game: Unity"
                : renpyEvidence is "loose_source" or "compiled_source" or "archive_source" or "archive_unsupported" or "assets_only"
                    ? "Loại game: Ren’Py"
                    : "Loại game: chưa xác định";
        AnalyzeEngineDetails = BuildAnalyzeEngineDetails(unityDetected ? "DETECTED" : snapshot.UnityStatus, renpyEvidence);
        AnalyzeAssetLines = CapAssetLines(snapshot.AssetLines);
        AnalyzeResourceCount = snapshot.ResourceCount;
        AnalyzeTextCandidateCount = snapshot.TextCandidateCount;
        AnalyzePatchableCount = snapshot.PatchableCount;
        AnalyzeExtractOnlyCount = snapshot.ExtractOnlyCount;
        AnalyzeReviewRiskCount = snapshot.ReviewRiskCount;
        AnalyzeUnknownCount = snapshot.UnknownCount;
        AnalyzeScanErrorCount = snapshot.ScanErrorCount;
        AnalyzeReportPath = snapshot.ReportPath;
        AnalyzeHasReport = true;
        var engineKnown = !_analyzeEngineSummary.EndsWith("chưa xác định", StringComparison.Ordinal);
        var renpyScriptsUnproven = renpyEvidence is "assets_only" or "archive_unsupported";
        _analyzeOutcome = !evt.Ok ? AnalyzeOutcome.Failed
            : !engineKnown ? AnalyzeOutcome.Unsupported
            : AnalyzeInventoryComplete && !renpyScriptsUnproven ? AnalyzeOutcome.Identified : AnalyzeOutcome.IdentifiedIncomplete;
        AnalyzeStatusText = AnalyzeInventoryComplete
            ? "Đã phân tích • danh sách dữ liệu của game đầy đủ"
            : "Cần xem lại • danh sách dữ liệu của game chưa đầy đủ";
        RaiseAnalyzeSummary();
        AnalyzeScanErrorText = snapshot.ScanErrorCount == 0
            ? renpyEvidence == "archive_unsupported" ? "Archive RPA lỗi hoặc chưa hỗ trợ; xem Nhật ký."
              : renpyEvidence == "assets_only" ? "Chưa thấy script Ren’Py đọc được để lấy text; xem Nhật ký."
              : ""
            : $"Có {snapshot.ScanErrorCount:N0} lỗi quét — danh sách dữ liệu của game chưa đầy đủ.";
        WriteAnalyzeDetailsToLog(snapshot);
    }

    /// <summary>Everything a technician needs (counts, per-font / per-image rows, reasons, step timings) goes to the log, not the scan screen.</summary>
    private void WriteAnalyzeDetailsToLog(UnityAnalysisReportSnapshot snapshot)
    {
        void Line(string text) { AppendLog(text); AddExtractRunLine(_activeTaskId, text); }
        Line($"[quét] Loại game: {_analyzeEngineSummary.Replace("Engine: ", "").Replace("Loại game: ", "")} ({(string.IsNullOrEmpty(snapshot.EngineDetection) ? "báo cáo cũ" : snapshot.EngineDetection)}) — {snapshot.EngineDetectionReason}");
        Line($"[quét] Tệp dữ liệu {snapshot.ResourceCount:N0}; có thể là văn bản {snapshot.TextCandidateCount:N0}; có đường ghi lại {snapshot.PatchableCount:N0}; chỉ lấy văn bản {snapshot.ExtractOnlyCount:N0}; cần xem lại/chưa hỗ trợ {snapshot.ReviewRiskCount:N0}; chưa xác định {snapshot.UnknownCount:N0}; lỗi quét {snapshot.ScanErrorCount:N0}.");
        foreach (var line in snapshot.AssetLines) Line("[quét] " + line);
        if (!string.IsNullOrEmpty(snapshot.TimingsText)) Line("[quét] Thời gian từng bước (giây): " + snapshot.TimingsText);
        if (!string.IsNullOrEmpty(snapshot.ReportPath)) Line("[quét] Báo cáo đầy đủ: " + snapshot.ReportPath);
    }

    private static string BuildAnalyzeEngineDetails(string unityStatus, string renpyEvidence)
    {
        var unity = unityStatus == "DETECTED" ? "Unity: có bằng chứng trong báo cáo phân tích." : "Unity: báo cáo không xác nhận loại game này.";
        var renpy = renpyEvidence switch
        {
            "loose_source" => "Ren’Py: tìm thấy tệp .rpy/.rpym trong game/.",
            "compiled_source" => "Ren’Py: tìm thấy bytecode .rpyc/.rpymc có header RPC2 trong game/.",
            "archive_source" => "Ren’Py: tìm thấy archive RPA hợp lệ cùng cấu trúc runtime.",
            "unknown" => "Ren’Py: chưa kiểm tra được nguồn tệp.",
            "archive_unsupported" => "Ren’Py: có archive RPA lỗi hoặc chưa hỗ trợ; chưa thể lấy text từ archive đó.",
            "assets_only" => "Ren’Py: thấy thư mục game cùng font/ảnh nhưng chưa thấy script đọc được để lấy text.",
            _ => "Ren’Py: chưa xác nhận được bằng chứng hỗ trợ.",
        };
        return string.Join(" ", new[]
        {
            UiText.Translate(unity),
            UiText.Translate(renpy),
            UiText.Translate("Phân tích chỉ đọc; chưa xác minh patch/write-back."),
        });
    }

    private string ResolveAnalyzeReportPath()
    {
        var package = WorkflowStatus.ResolvePackageDir(OutputPath);
        return Path.Combine(package, "unity_analysis.json");
    }

    private void ResetAnalyzeMetrics()
    {
        AnalyzeInventoryComplete = false;
        AnalyzeAssetLines = Array.Empty<string>();
        AnalyzeUnityStatus = "ĐANG CHẠY";
        AnalyzeResourceCount = 0;
        AnalyzeTextCandidateCount = 0;
        AnalyzePatchableCount = 0;
        AnalyzeExtractOnlyCount = 0;
        AnalyzeReviewRiskCount = 0;
        AnalyzeUnknownCount = 0;
        AnalyzeScanErrorCount = 0;
    }
}
