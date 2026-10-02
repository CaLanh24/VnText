using System.IO;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    private string _analyzeStatusText = "Chưa phân tích game";
    private string _analyzeReportPath = "Báo cáo sẽ được ghi ngoài thư mục game.";
    private string _analyzeScanErrorText = "Chưa có lỗi quét được ghi nhận.";
    private string _analyzeUnityStatus = "NOT_DETECTED";
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
        get => _analyzeStatusText;
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

    public string AnalyzeUnityStatus
    {
        get => _analyzeUnityStatus;
        private set => Set(ref _analyzeUnityStatus, value);
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
        if (string.IsNullOrWhiteSpace(InputPath))
        {
            AnalyzeStatusText = "Chưa chọn game / asset";
            StatusText = "Chưa chọn game";
            AppendLog("Chọn game / asset trước khi phân tích.");
            SelectedTab = WorkflowTabs.Extract;
            return;
        }
        if (string.IsNullOrWhiteSpace(OutputPath))
        {
            AnalyzeStatusText = "Chưa chọn thư mục xuất";
            StatusText = "Chưa chọn thư mục xuất";
            AppendLog("Chọn thư mục xuất trước khi phân tích.");
            SelectedTab = WorkflowTabs.Extract;
            return;
        }

        var reportDirectory = WorkflowStatus.ResolvePackageDir(OutputPath);
        AnalyzeStatusText = "Đang phân tích game…";
        AnalyzeReportPath = Path.Combine(reportDirectory, "unity_analysis.json");
        AnalyzeScanErrorText = "Đang kiểm tra tính đầy đủ của inventory…";
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
        if (snapshot is null)
        {
            AnalyzeInventoryComplete = false;
            AnalyzeUnityStatus = "UNKNOWN";
            AnalyzeStatusText = evt.Ok
                ? "Đã chạy nhưng không đọc được report"
                : "Phân tích thất bại";
            AnalyzeReportPath = reportPath;
            AnalyzeScanErrorText = string.IsNullOrWhiteSpace(error)
                ? "Không tìm thấy unity_analysis.json; chưa đủ bằng chứng inventory."
                : $"Không đọc được report: {error}";
            return;
        }

        AnalyzeInventoryComplete = snapshot.InventoryComplete && evt.Ok;
        AnalyzeUnityStatus = snapshot.UnityStatus;
        AnalyzeResourceCount = snapshot.ResourceCount;
        AnalyzeTextCandidateCount = snapshot.TextCandidateCount;
        AnalyzePatchableCount = snapshot.PatchableCount;
        AnalyzeExtractOnlyCount = snapshot.ExtractOnlyCount;
        AnalyzeReviewRiskCount = snapshot.ReviewRiskCount;
        AnalyzeUnknownCount = snapshot.UnknownCount;
        AnalyzeScanErrorCount = snapshot.ScanErrorCount;
        AnalyzeReportPath = snapshot.ReportPath;
        AnalyzeStatusText = AnalyzeInventoryComplete
            ? $"Đã phân tích • Unity {snapshot.UnityStatus} • inventory đầy đủ"
            : $"Cần xem lại • Unity {snapshot.UnityStatus} • inventory chưa đầy đủ";
        AnalyzeScanErrorText = snapshot.ScanErrorCount == 0
            ? "Không có lỗi quét được ghi nhận. Đây là inventory read-only; Patch verification chưa chạy."
            : $"Có {snapshot.ScanErrorCount:N0} lỗi quét — không coi inventory là đầy đủ.";
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
