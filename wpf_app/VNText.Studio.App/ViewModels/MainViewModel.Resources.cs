using System.IO;
using System.Text.Json;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    private string _resourceStatus = "Chuẩn bị mô hình dịch và Ren’Py SDK trước khi chọn game. OCR dùng gói tiếng Anh của Windows.";
    public string ResourceStatus { get => UiText.TranslateDynamic(_resourceStatus); private set => Set(ref _resourceStatus, value); }
    public RelayCommand CheckResourcesCommand { get; private set; } = null!;
    public RelayCommand DownloadResourcesCommand { get; private set; } = null!;
    public RelayCommand OpenResourcesCommand { get; private set; } = null!;
    public int SelectedSettingsTab { get; set; } = 1;
    private int _resourceProgressPercent;
    private string _resourceProgressText = "";
    // Resource progress/cancel belong to the resources task ONLY; any other busy task may disable the buttons but never shows here.
    public bool ResourcesActive => Busy && _runningTask == "resources";
    public int ResourceProgressPercent { get => _resourceProgressPercent; private set => Set(ref _resourceProgressPercent, value); }
    public string ResourceProgressText => UiText.Translate(_resourceProgressText);
    public RelayCommand CancelResourcesCommand { get; private set; } = null!;
    // Real readiness is READ (check-only task) when the Settings page is first opened; nothing is downloaded until the user asks for recovery.
    private bool _resourcesChecked, _resourcesAllReady, _resourceAutoCheckStarted;
    public bool ResourcesNeedRecovery => _resourcesChecked && !_resourcesAllReady;
    public bool ResourcesAllReady => _resourcesChecked && _resourcesAllReady;
    internal void AutoCheckResourcesOnce()
    {
        if (_resourceAutoCheckStarted || Busy || _disposed != 0) return;
        _resourceAutoCheckStarted = true;
        StartResources(false);
    }
    private void RaiseResourceReadiness()
    {
        Raise(nameof(ResourcesNeedRecovery)); Raise(nameof(ResourcesAllReady));
    }
    internal void RefreshResourcesActive()
    {
        Raise(nameof(ResourcesActive));
        CancelResourcesCommand?.RaiseCanExecuteChanged();
    }
    private void SetResourceProgress(int? percent, string? text)
    {
        if (percent.HasValue) ResourceProgressPercent = percent.Value;
        if (text is not null) { _resourceProgressText = text; Raise(nameof(ResourceProgressText)); }
    }
    private void CancelResources()
    {
        if (!ResourcesActive) return;
        CancelTask();
    }
    private void InitResourceCommands()
    {
        CancelResourcesCommand = new RelayCommand(_ => CancelResources(), _ => ResourcesActive);
        CheckResourcesCommand = new RelayCommand(_ => StartResources(false), _ => !Busy);
        DownloadResourcesCommand = new RelayCommand(_ => StartResources(true), _ => !Busy);
        OpenResourcesCommand = new RelayCommand(_ => { SelectedSettingsTab = 1; Raise(nameof(SelectedSettingsTab)); SelectedTab = WorkflowTabs.Settings; });
    }
    private void StartResources(bool download)
    {
        if (Busy) return;
        ResourceStatus = download ? "Đang chuẩn bị tài nguyên… Có thể hủy và thử lại; game không bị thay đổi." : "Đang kiểm tra tài nguyên…";
        _statusBeforeResources = StatusText;                 // Q1: what the status line said before this task claimed it
        BeginTask("resources", new { download }, ResourceStatus);
        _resourcesRunningStatus = StatusText;                // the exact text THIS task published (identity of its ownership)
        _resourcesStatusTaskId = _activeTaskId ?? "";
    }
    private string _statusBeforeResources = "", _resourcesRunningStatus = "", _resourcesStatusTaskId = "";
    // Cancellation and its acknowledgement/watchdog are still statuses of this resource task.
    // Keep ownership only across those real lifecycle transitions, never by matching arbitrary progress words.
    private void SetTaskLifecycleStatus(string text)
    {
        if (_runningTask == "resources" && _resourcesStatusTaskId == _activeTaskId
            && !string.IsNullOrEmpty(_resourcesRunningStatus) && StatusText == _resourcesRunningStatus)
            _resourcesRunningStatus = text;
        StatusText = text;
    }
    /// <summary>Test seam for the status ownership of <see cref="StartResources"/> without a worker (BeginTask publishes the label as StatusText).</summary>
    internal void TestClaimResourcesStatus(bool download)
    {
        TestSetActiveTask("test-resources-" + Guid.NewGuid().ToString("N"), "resources");
        ResourceStatus = download ? "Đang chuẩn bị tài nguyên… Có thể hủy và thử lại; game không bị thay đổi." : "Đang kiểm tra tài nguyên…";
        _statusBeforeResources = StatusText; StatusText = ResourceStatus; _resourcesRunningStatus = StatusText;
        _resourcesStatusTaskId = _activeTaskId ?? "";
    }
    /// <summary>Q1: the resources task ends with a terminal status.  Only if the status line is still the running text this task published is it replaced
    /// (the earlier status when there was one, "ready" otherwise, or a short blocked/cancelled line); any other task's status stays untouched, and a late
    /// completion never replays the running text.  The detail stays in <c>ResourceStatus</c>/the log; errors stay in the persistent banner.</summary>
    private void SettleResourcesStatus(VNText.Studio.App.Models.WorkerEvent evt)
    {
        if (string.IsNullOrEmpty(_resourcesStatusTaskId) || evt.Id != _resourcesStatusTaskId) return;
        var owned = _resourcesRunningStatus; var before = _statusBeforeResources;
        _resourcesRunningStatus = ""; _statusBeforeResources = ""; _resourcesStatusTaskId = "";
        if (string.IsNullOrEmpty(owned) || StatusText != owned) return;
        var cancelled = !evt.Ok && evt.Error?.Contains("cancelled", StringComparison.OrdinalIgnoreCase) == true;
        StatusText = cancelled ? "Đã hủy chuẩn bị tài nguyên; có thể tải lại. Tài nguyên đã cài vẫn được giữ."
            : !evt.Ok || !_resourcesAllReady ? "Tài nguyên chưa sẵn sàng — xem Cài đặt › Dữ liệu."
            : !string.IsNullOrEmpty(before) && before != owned ? before : "Sẵn sàng";
    }
    private void CompleteResources(VNText.Studio.App.Models.WorkerEvent evt)
    {
        if (!evt.Ok && evt.Error?.Contains("cancelled", StringComparison.OrdinalIgnoreCase) == true)
        {
            ResourceStatus = "Đã hủy chuẩn bị tài nguyên; có thể tải lại. Tài nguyên đã cài vẫn được giữ.";
            RaiseResourceReadiness();
            AppendLog(ResourceStatus);
            return;
        }
        ResourceStatus = evt.Summary ?? "Đã kiểm tra tài nguyên.";
        try
        {
            var dataRoot = Environment.GetEnvironmentVariable("VNTEXT_DATA_ROOT");
            if (string.IsNullOrWhiteSpace(dataRoot)) dataRoot = WorkerPaths.AppDataRoot();
            using var report = JsonDocument.Parse(File.ReadAllText(Path.Combine(dataRoot, "resource-status.json")));
            var lines = new List<string>();
            var allReady = true; var count = 0;
            foreach (var resource in report.RootElement.GetProperty("resources").EnumerateArray())
            {
                var name = resource.GetProperty("resource").GetString();
                var ready = resource.GetProperty("ready").GetBoolean();
                allReady &= ready; count++;
                var detail = ready ? resource.GetProperty("path").GetString() : resource.GetProperty("error").GetString();
                lines.Add($"{name}: {(ready ? "Sẵn sàng" : "Chưa sẵn sàng")} · {detail}");
                if (name == "renpy" && ready) { RenpySdkPath = detail ?? ""; RenpySdkAction = "existing"; RenpySdkError = ""; }
            }
            _resourcesChecked = count > 0; _resourcesAllReady = count > 0 && allReady;
            AppendLog(string.Join("\n", lines));      // the per-resource detail stays in the log; the page shows one brief state
            ResourceStatus = _resourcesAllReady
                ? "Sẵn sàng · mô hình dịch, Ren’Py SDK và OCR đã cài trên máy."
                : "Còn thiếu hoặc hỏng tài nguyên — dùng “Sửa/tải tài nguyên còn thiếu”. Phần đã cài được giữ nguyên.\n" + string.Join("\n", lines.Where(line => line.Contains("Chưa sẵn sàng")));
            RaiseResourceReadiness();
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException or InvalidOperationException or KeyNotFoundException)
        {
            _resourcesChecked = true; _resourcesAllReady = false;
            ResourceStatus = UiText.Msg("Không đọc được trạng thái tài nguyên: {0}", ex.Message);
            RaiseResourceReadiness();
            AppendLog(ResourceStatus, "WARN");
        }
        if (!evt.Ok) { if (!string.IsNullOrWhiteSpace(evt.Error) && !_resourceStatus.Contains(evt.Error.Trim(), StringComparison.Ordinal)) ResourceStatus += "\n" + evt.Error; RecordPersistentError("resources", evt.Error ?? "Không chuẩn bị được tài nguyên."); }
        else ResolvePersistentErrorIfSameTask("resources");
        if (!_resourcesAllReady) AppendLog(ResourceStatus);
        CheckResourcesCommand.RaiseCanExecuteChanged(); DownloadResourcesCommand.RaiseCanExecuteChanged();
        _ = LoadModelStatusAsync();
    }
}
