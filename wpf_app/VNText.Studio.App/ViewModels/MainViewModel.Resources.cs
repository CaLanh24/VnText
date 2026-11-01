using System.IO;
using System.Text.Json;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    private string _resourceStatus = "Chuẩn bị mô hình dịch và Ren’Py SDK trước khi chọn game. OCR dùng gói tiếng Anh của Windows.";
    public string ResourceStatus { get => UiText.Translate(_resourceStatus); private set => Set(ref _resourceStatus, value); }
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
        BeginTask("resources", new { download }, ResourceStatus);
    }
    private void CompleteResources(VNText.Studio.App.Models.WorkerEvent evt)
    {
        if (!evt.Ok && evt.Error?.Contains("cancelled", StringComparison.OrdinalIgnoreCase) == true)
        {
            ResourceStatus = "Đã hủy chuẩn bị tài nguyên; có thể tải lại. Tài nguyên đã cài vẫn được giữ.";
            AppendLog(ResourceStatus);
            return;
        }
        ResourceStatus = evt.Summary ?? "Đã kiểm tra tài nguyên.";
        try
        {
            using var report = JsonDocument.Parse(File.ReadAllText(Path.Combine(WorkerPaths.AppDataRoot(), "resource-status.json")));
            var lines = new List<string>();
            foreach (var resource in report.RootElement.GetProperty("resources").EnumerateArray())
            {
                var name = resource.GetProperty("resource").GetString();
                var ready = resource.GetProperty("ready").GetBoolean();
                var detail = ready ? resource.GetProperty("path").GetString() : resource.GetProperty("error").GetString();
                lines.Add($"{name}: {(ready ? "Sẵn sàng" : "Chưa sẵn sàng")} · {detail}");
                if (name == "renpy" && ready) { RenpySdkPath = detail ?? ""; RenpySdkAction = "existing"; RenpySdkError = ""; }
            }
            ResourceStatus = string.Join("\n", lines);
        }
        catch (Exception ex) when (ex is IOException or JsonException or InvalidOperationException) { AppendLog("Không đọc được trạng thái tài nguyên: " + ex.Message); }
        if (!evt.Ok) { ResourceStatus += "\n" + evt.Error; RecordPersistentError("resources", evt.Error ?? "Không chuẩn bị được tài nguyên."); }
        else ResolvePersistentErrorIfSameTask("resources");
        AppendLog(ResourceStatus);
        CheckResourcesCommand.RaiseCanExecuteChanged(); DownloadResourcesCommand.RaiseCanExecuteChanged();
        _ = LoadModelStatusAsync();
    }
}
