using System.IO;
using System.Text.Json;
using System.Windows;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

/// <summary>
/// A failed task leaves a durable error: the full reason (never truncated, never a toast only) stays on the page until the user
/// acknowledges it or the same task later succeeds, survives a restart, and its history stays readable in the app journal.
/// </summary>
public sealed partial class MainViewModel
{
    private string _persistentErrorText = "";
    private string _persistentErrorTask = "";
    private string _persistentErrorTime = "";
    private string _persistentErrorHint = "";
    private bool _persistentIsWarning;

    internal string LastErrorFilePath => Path.Combine(WorkerPaths.AppDataRoot(), "last_error.json");

    public bool HasPersistentError => _persistentErrorText.Length > 0;
    public string PersistentErrorText => _persistentErrorText;
    // A limitation of a SUCCESSFUL run (PARTIAL) is a neutral review warning, never the red "Lỗi" of an actual failure.
    public bool PersistentErrorIsWarning => _persistentIsWarning;
    public string PersistentErrorHeading => !HasPersistentError ? ""
        : _persistentIsWarning
            ? UiText.Msg("Cảnh báo {0} lúc {1}", PersistentErrorStage(_persistentErrorTask), _persistentErrorTime)
            : UiText.Msg("Lỗi {0} lúc {1}", PersistentErrorStage(_persistentErrorTask), _persistentErrorTime);
    public string PersistentErrorHint => _persistentErrorHint;

    public RelayCommand CopyErrorCommand { get; private set; } = null!;
    public RelayCommand DismissErrorCommand { get; private set; } = null!;
    public RelayCommand OpenErrorJournalCommand { get; private set; } = null!;

    private void InitializePersistentError()
    {
        CopyErrorCommand = new RelayCommand(_ => CopyPersistentError(), _ => HasPersistentError);
        DismissErrorCommand = new RelayCommand(_ => AcknowledgePersistentError(), _ => HasPersistentError);
        OpenErrorJournalCommand = new RelayCommand(_ => NavigateTab(WorkflowTabs.Journal));
        LoadPersistentErrorFromDisk();
    }

    private static string PersistentErrorStage(string task) => task switch
    {
        "extract" => "lấy text",
        "translate" => "dịch tự động",
        "patch" => "tạo patch",
        "analyze" => "phân tích game",
        "" => "tác vụ",
        _ => task,
    };

    /// <summary>Called for every terminal failure; the text is stored in full (the journal line is written by the normal log path).</summary>
    internal void RecordPersistentNotice(string? task, string message, string hint = "") => RecordPersistent(task, message, hint, warning: true);

    internal void RecordPersistentError(string? task, string message, string hint = "") => RecordPersistent(task, message, hint, warning: false);

    private void RecordPersistent(string? task, string message, string hint, bool warning)
    {
        var text = (message ?? "").Trim();
        if (text.Length == 0) return;
        _persistentErrorText = text;
        _persistentErrorTask = task ?? "";
        _persistentErrorTime = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
        _persistentErrorHint = hint;
        _persistentIsWarning = warning;
        WriteLastErrorFile();
        RaisePersistentError();
    }

    /// <summary>The same kind of task finished successfully: the earlier error is resolved (it stays in the journal history).</summary>
    internal void ResolvePersistentErrorIfSameTask(string? task)
    {
        if (HasPersistentError && string.Equals(_persistentErrorTask, task ?? "", StringComparison.Ordinal))
            AcknowledgePersistentError();
    }

    internal void AcknowledgePersistentError()
    {
        if (!HasPersistentError) return;
        AppendLog($"Đã xác nhận lỗi {PersistentErrorStage(_persistentErrorTask)} ({_persistentErrorTime}); nội dung đầy đủ vẫn nằm trong Nhật ký.");
        _persistentErrorText = "";
        _persistentErrorTask = "";
        _persistentErrorTime = "";
        _persistentErrorHint = "";
        _persistentIsWarning = false;
        try { if (File.Exists(LastErrorFilePath)) File.Delete(LastErrorFilePath); }
        catch (IOException ex) { AppendLog($"Không xóa được trạng thái lỗi chưa xác nhận: {ex.Message}"); }
        catch (UnauthorizedAccessException ex) { AppendLog($"Không xóa được trạng thái lỗi chưa xác nhận: {ex.Message}"); }
        RaisePersistentError();
    }

    private void CopyPersistentError()
    {
        try
        {
            Clipboard.SetText($"VNText Studio {Version}\n{PersistentErrorHeading}\n\n{_persistentErrorText}");
        }
        catch (System.Runtime.InteropServices.ExternalException ex)
        {
            AppendLog($"Không chép được lỗi vào clipboard: {ex.Message}");
        }
    }

    private void RaisePersistentError()
    {
        Raise(nameof(HasPersistentError));
        Raise(nameof(PersistentErrorText));
        Raise(nameof(PersistentErrorHeading));
        Raise(nameof(PersistentErrorIsWarning));
        Raise(nameof(PersistentErrorHint));
        CopyErrorCommand?.RaiseCanExecuteChanged();
        DismissErrorCommand?.RaiseCanExecuteChanged();
    }

    private void WriteLastErrorFile()
    {
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(LastErrorFilePath)!);
            var temp = LastErrorFilePath + ".tmp";
            File.WriteAllText(temp, JsonSerializer.Serialize(new { task = _persistentErrorTask, time = _persistentErrorTime, text = _persistentErrorText, hint = _persistentErrorHint, severity = _persistentIsWarning ? "warning" : "error" }));
            File.Move(temp, LastErrorFilePath, overwrite: true);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            AppendLog($"Không lưu được trạng thái lỗi chưa xác nhận: {ex.Message}");
        }
    }

    private void LoadPersistentErrorFromDisk()
    {
        try
        {
            if (!File.Exists(LastErrorFilePath)) return;
            using var document = JsonDocument.Parse(File.ReadAllText(LastErrorFilePath));
            var root = document.RootElement;
            _persistentErrorText = root.TryGetProperty("text", out var text) ? text.GetString() ?? "" : "";
            _persistentErrorTask = root.TryGetProperty("task", out var task) ? task.GetString() ?? "" : "";
            _persistentErrorTime = root.TryGetProperty("time", out var time) ? time.GetString() ?? "" : "";
            _persistentErrorHint = root.TryGetProperty("hint", out var hint) ? hint.GetString() ?? "" : "";
            _persistentIsWarning = root.TryGetProperty("severity", out var severity) && severity.GetString() == "warning";
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException)
        {
            _persistentErrorText = $"Không đọc được lỗi chưa xác nhận của phiên trước ({ex.Message}); xem Nhật ký.";
            _persistentErrorTime = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
        }
    }
}
