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

    private void InvalidateAnalyzeIfInputsChanged()
    {
        if (_analyzeIdentity is null || _analyzeIdentity == AnalyzeIdentityOf(InputPath, OutputPath))
            return;
        _analyzeIdentity = null;
        _analyzeRejectLate = true;
        AnalyzeInventoryComplete = false;
        AnalyzeUnityStatus = "NOT_DETECTED";
        AnalyzeEngineSummary = "Chưa xác định engine";
        AnalyzeEngineDetails = "";
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
    }

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

    public string AnalyzeEngineDetails
    {
        get => UiText.Translate(_analyzeEngineDetails);
        private set => Set(ref _analyzeEngineDetails, value);
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
        _analyzeIdentity = AnalyzeIdentityOf(InputPath, OutputPath);
        _analyzeRejectLate = false;
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
            AnalyzeEngineSummary = "Engine: chưa xác định";
            AnalyzeEngineDetails = "Không đọc được báo cáo Unity; chưa có đủ bằng chứng để phân loại engine.";
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
        string renpyEvidence;
        try { renpyEvidence = RenpyGameDetector.GetRenpyEvidenceKind(InputPath, CancellationToken.None); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.Security.SecurityException)
        { renpyEvidence = "unknown"; }
        AnalyzeEngineSummary = snapshot.UnityStatus == "DETECTED" && renpyEvidence is not "none"
            ? "Engine: Unity + Ren’Py evidence"
            : snapshot.UnityStatus == "DETECTED"
                ? "Engine: Unity"
                : renpyEvidence is "loose_source" or "compiled_source" or "archive_source"
                    ? "Engine: Ren’Py"
                    : "Engine: chưa xác định";
        AnalyzeEngineDetails = BuildAnalyzeEngineDetails(snapshot.UnityStatus, renpyEvidence);
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

    private static string BuildAnalyzeEngineDetails(string unityStatus, string renpyEvidence)
    {
        var unity = unityStatus == "DETECTED" ? "Unity: có bằng chứng trong báo cáo phân tích." : "Unity: báo cáo không xác nhận engine này.";
        var renpy = renpyEvidence switch
        {
            "loose_source" => "Ren’Py: tìm thấy tệp .rpy/.rpym trong game/.",
            "compiled_source" => "Ren’Py: tìm thấy bytecode .rpyc/.rpymc có header RPC2 trong game/.",
            "archive_source" => "Ren’Py: tìm thấy archive RPA hợp lệ cùng cấu trúc runtime.",
            "unknown" => "Ren’Py: chưa kiểm tra được nguồn tệp.",
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
