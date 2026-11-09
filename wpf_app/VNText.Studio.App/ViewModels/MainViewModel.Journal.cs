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
    internal void PersistJournal(string message, string? level = null)
    {
        try { JournalStore.Append(message, level); _journalWriteFailed=false; }
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

    // The Extract tab journal holds the extraction run AND the automatic game analysis that precedes it (each is its own run in the selector);
    // resources/image tasks keep their audit copy in the sidebar Journal only.
    private static string LogOwner(string? task) => task switch
    {
        "extract" or "analyze" => WorkflowTabs.Extract,
        "translate" or "image_render" or "cloud_export" or "cloud_import" or "external_translation_import" => WorkflowTabs.Translate,
        "patch" or "image_delivery" or "image_apply" or "image_rollback" => WorkflowTabs.Patch,
        _ => ""
    };

    private void BeginTaskLog(string id,string task,string message)
    {
        if (_logTaskOwners.Count >= 64) _logTaskOwners.Remove(_logTaskOwners.Keys.First());
        _logTaskOwners[id] = LogOwner(task);
        if (task is "extract" or "analyze") StartExtractRun(id, task);
        AddTaskProgress(id,message);
    }

    /// <summary>Worker log severity metadata ("warning"/"error"/"ok") as a display level; anything else stays unmarked (text-derived default).</summary>
    internal static string? KnownLogLevel(string? severity) => severity switch { "warning" => "WARN", "error" => "ERROR", "ok" => "SUCCESS", _ => null };

    private void AddTaskProgress(string id,string message,string? fallbackTask=null,string? level=null)
    {
        var owner = _logTaskOwners.TryGetValue(id,out var known) ? known : LogOwner(fallbackTask);
        if (string.IsNullOrWhiteSpace(message)) return;
        var content = message.Trim();
        PersistJournal($"[task {id} / {(owner.Length == 0 ? "other" : owner)}] {content}", level);        // general audit copy (sidebar Journal)
        if (owner == WorkflowTabs.Extract) { AddExtractRunLine(id, content); return; }              // complete, never truncated or evicted
        var lines = owner switch { WorkflowTabs.Translate => TranslateLogLines, WorkflowTabs.Patch => PatchLogLines, _ => null };
        if (lines is null) return;

        if (lines.Count > 0 && lines[^1].EndsWith("] " + content,StringComparison.Ordinal)) return;
        var stamped = $"[{DateTime.Now:HH:mm:ss}] {content}";
        lines.Add(level is null ? stamped : VNText.Studio.App.Converters.LogSeverityConverter.Mark(stamped, level));

    }

    internal void TestBeginTaskLog(string id,string task) => BeginTaskLog(id,task,"Bắt đầu");
}
