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
    private string _analyzeEngineSummary = "Chưa xác định engine";
    private bool _analyzeInventoryComplete;
    private int _analyzeResourceCount;
    private int _analyzeTextCandidateCount;
    private int _analyzePatchableCount;
    private int _analyzeExtractOnlyCount;
    private int _analyzeReviewRiskCount;
    private int _analyzeUnknownCount;
    private int _analyzeScanErrorCount;

    public string AnalyzeStatusText
    {
        get => UiText.Translate(_analyzeStatusText);
        private set => Set(ref _analyzeStatusText, value);
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

    private void RunAnalyze()
    {
        AnalyzeResultsExpanded = false;
        AnalyzeHasReport = false;
        AnalyzeReportPath = "";
        if (string.IsNullOrWhiteSpace(InputPath))
        {
            AnalyzeStatusText = "Chưa chọn game / asset";
            AnalyzeResultsExpanded = true;
            StatusText = "Chưa chọn game";
            AppendLog("Chọn game / asset trước khi phân tích.");
            SelectedTab = WorkflowTabs.Extract;
            return;
        }
        if (string.IsNullOrWhiteSpace(OutputPath))
        {
            AnalyzeStatusText = "Chưa chọn thư mục xuất";
            AnalyzeResultsExpanded = true;
            StatusText = "Chưa chọn thư mục xuất";
            AppendLog("Chọn thư mục xuất trước khi phân tích.");
            SelectedTab = WorkflowTabs.Extract;
            return;
        }

        var reportDirectory = WorkflowStatus.ResolvePackageDir(OutputPath);
        AnalyzeStatusText = "Đang phân tích game…";
        AnalyzeReportPath = "";
        AnalyzeScanErrorText = "Đang kiểm tra tính đầy đủ của danh mục tài nguyên…";
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
            AnalyzeEngineSummary = "Engine: chưa xác định — không đủ bằng chứng để phân loại.";
            AnalyzeStatusText = evt.Ok
                ? "Đã chạy nhưng không đọc được report"
                : "Phân tích thất bại";
            AnalyzeReportPath = AnalyzeHasReport ? reportPath : "";
            AnalyzeScanErrorText = string.IsNullOrWhiteSpace(error)
                ? "Không tìm thấy báo cáo unity_analysis.json; chưa xác minh đủ tài nguyên."
                : $"Không đọc được report: {error}";
            return;
        }

        AnalyzeInventoryComplete = snapshot.InventoryComplete && evt.Ok;
        AnalyzeUnityStatus = snapshot.UnityStatus;
        var renpySource = false;
        try { renpySource = RenpyGameDetector.HasLooseSourceFiles(InputPath, CancellationToken.None); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.Security.SecurityException)
        { /* Detection remains unknown when the filesystem cannot be inspected. */ }
        AnalyzeEngineSummary = snapshot.UnityStatus == "DETECTED" && renpySource
            ? "Engine: Unity + Ren’Py evidence detected — mixed engine; confidence score unavailable."
            : snapshot.UnityStatus == "DETECTED"
                ? "Engine: Unity detected by analyzer report; other engines not classified; confidence score unavailable."
                : renpySource
                    ? "Engine: Ren’Py loose source detected from .rpy/.rpym files; other engines not classified; confidence score unavailable."
                    : "Engine: unknown — no supported engine signature was confirmed; mixed status unknown.";
        AnalyzeResourceCount = snapshot.ResourceCount;
        AnalyzeTextCandidateCount = snapshot.TextCandidateCount;
        AnalyzePatchableCount = snapshot.PatchableCount;
        AnalyzeExtractOnlyCount = snapshot.ExtractOnlyCount;
        AnalyzeReviewRiskCount = snapshot.ReviewRiskCount;
        AnalyzeUnknownCount = snapshot.UnknownCount;
        AnalyzeScanErrorCount = snapshot.ScanErrorCount;
        AnalyzeReportPath = snapshot.ReportPath;
        AnalyzeHasReport = true;
        AnalyzeStatusText = AnalyzeInventoryComplete
            ? "Đã phân tích • danh mục tài nguyên đầy đủ"
            : "Cần xem lại • danh mục tài nguyên chưa đầy đủ";
        AnalyzeScanErrorText = snapshot.ScanErrorCount == 0
            ? "Không ghi nhận lỗi quét."
            : $"Có {snapshot.ScanErrorCount:N0} lỗi quét — danh mục tài nguyên chưa đầy đủ.";
    }

    private string ResolveAnalyzeReportPath()
    {
        var package = WorkflowStatus.ResolvePackageDir(OutputPath);
        return Path.Combine(package, "unity_analysis.json");
    }

    private void ResetAnalyzeMetrics()
    {
        AnalyzeInventoryComplete = false;
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
