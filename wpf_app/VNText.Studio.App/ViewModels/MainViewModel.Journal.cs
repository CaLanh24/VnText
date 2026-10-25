using System.Collections.ObjectModel;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    internal AppJournalStore JournalStore { get; } = new(System.IO.Path.Combine(WorkerPaths.AppDataRoot(),"logs"));
    internal event Action? JournalRequested;
    private bool _journalWriteFailed;
    internal bool JournalWriteFailed => _journalWriteFailed;
    internal void PersistJournal(string message)
    {
        try { JournalStore.Append(message); _journalWriteFailed=false; }
        catch(Exception ex)
        {
            if(!_journalWriteFailed) LogLines.Add($"[{DateTime.Now:HH:mm:ss}] Không ghi được nhật ký: {ex.Message}");
            _journalWriteFailed=true;
        }
    }
    public ObservableCollection<string> ExtractLogLines { get; } = new();
    public ObservableCollection<string> TranslateLogLines { get; } = new();
    public ObservableCollection<string> PatchLogLines { get; } = new();
    private readonly Dictionary<string,string> _logTaskOwners = new();

    private static string LogOwner(string? task) => task switch
    {
        "extract" or "analyze" or "image_inventory" or "image_extract" => WorkflowTabs.Extract,
        "translate" or "image_batch" or "image_render" or "cloud_export" or "cloud_import" or "external_translation_import" => WorkflowTabs.Translate,
        "patch" or "image_delivery" or "image_apply" or "image_rollback" => WorkflowTabs.Patch,
        _ => ""
    };

    private void BeginTaskLog(string id,string task,string message)
    {
        if (_logTaskOwners.Count >= 64) _logTaskOwners.Remove(_logTaskOwners.Keys.First());
        _logTaskOwners[id] = LogOwner(task);
        AddTaskProgress(id,message);
    }

    private void AddTaskProgress(string id,string message,string? fallbackTask=null)
    {
        var owner = _logTaskOwners.TryGetValue(id,out var known) ? known : LogOwner(fallbackTask);
        var lines = owner switch { WorkflowTabs.Extract => ExtractLogLines, WorkflowTabs.Translate => TranslateLogLines, WorkflowTabs.Patch => PatchLogLines, _ => null };
        if (lines is null || string.IsNullOrWhiteSpace(message)) return;
        var content = message.Trim();
        if (content.Length > 1000) content = content[..1000];
        if (lines.Count > 0 && lines[^1].EndsWith("] " + content,StringComparison.Ordinal)) return;
        lines.Add($"[{DateTime.Now:HH:mm:ss}] {content}");
        while(lines.Count > 200) lines.RemoveAt(0);
    }

    internal void TestBeginTaskLog(string id,string task) => BeginTaskLog(id,task,"Bắt đầu");
}
