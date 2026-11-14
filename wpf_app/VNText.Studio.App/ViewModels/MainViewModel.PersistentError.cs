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
    private sealed record SavedNotice(string Task, string Time, string Text, string Hint, bool Warning);
    private readonly Dictionary<string, SavedNotice> _pageNotices = new(StringComparer.Ordinal);

    private void SelectPersistentErrorForPage()
    {
        if (_pageNotices.TryGetValue(SelectedTab, out var notice))
        {
            _persistentErrorTask = notice.Task; _persistentErrorTime = notice.Time;
            _persistentErrorText = notice.Text; _persistentErrorHint = notice.Hint; _persistentIsWarning = notice.Warning;
        }
        else
        {
            _persistentErrorTask = _persistentErrorTime = _persistentErrorText = _persistentErrorHint = "";
            _persistentIsWarning = false;
        }
        RaisePersistentError();
    }

    internal string LastErrorFilePath => Path.Combine(WorkerPaths.AppDataRoot(), "last_error.json");

    public bool HasPersistentError => _persistentErrorText.Length > 0;
    public bool HasPagePersistentError => HasPersistentError && SelectedTab == ErrorTab(_persistentErrorTask);
    internal static string ErrorTab(string task) => task switch
    {
        "analyze" or "extract" => WorkflowTabs.Extract,
        "patch" or "patch_preflight" => WorkflowTabs.Patch,
        "resources" => WorkflowTabs.Settings,
        _ when task.StartsWith("image_", StringComparison.Ordinal) => WorkflowTabs.Images,
        _ when task.StartsWith("csv_", StringComparison.Ordinal) => WorkflowTabs.EditCsv,
        _ => WorkflowTabs.Translate,
    };
    public string PersistentErrorText => _persistentErrorText;
    public string PersistentNoticeSummary
    {
        get
        {
            if (!_persistentIsWarning || _persistentErrorText.Length <= 240) return _persistentErrorText;
            var first = _persistentErrorText.IndexOf(". ", StringComparison.Ordinal);
            return (first is > 0 and < 240 ? _persistentErrorText[..(first + 1)] : _persistentErrorText[..220] + "…")
                + " " + UiText.Translate("Chi tiết được giữ đầy đủ trong Nhật ký.");
        }
    }
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
        "image_batch" or "image_inventory" or "image_extract" or "image_render" or "image_delivery" or "image_apply" or "image_rollback" => "dịch ảnh",
        "resources" => "tài nguyên",
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
        _pageNotices[ErrorTab(_persistentErrorTask)] = new(_persistentErrorTask, _persistentErrorTime, text, hint, warning);
        WriteLastErrorFile();
        SelectPersistentErrorForPage();
    }

    /// <summary>The same kind of task finished successfully: the earlier error is resolved (it stays in the journal history).</summary>
    internal void ResolvePersistentErrorIfSameTask(string? task)
    {
        if (_pageNotices.TryGetValue(ErrorTab(task ?? ""), out var notice) && notice.Task == (task ?? ""))
        {
            _pageNotices.Remove(ErrorTab(task ?? ""));
            SelectPersistentErrorForPage();
            WriteLastErrorFile();
        }
    }

    internal void AcknowledgePersistentError()
    {
        if (!HasPersistentError) return;
        _pageNotices.Remove(ErrorTab(_persistentErrorTask));
        AppendLog($"Đã xác nhận lỗi {PersistentErrorStage(_persistentErrorTask)} ({_persistentErrorTime}); nội dung đầy đủ vẫn nằm trong Nhật ký.", "INFO");
        _persistentErrorText = "";
        _persistentErrorTask = "";
        _persistentErrorTime = "";
        _persistentErrorHint = "";
        _persistentIsWarning = false;
        try { if (_pageNotices.Count == 0 && File.Exists(LastErrorFilePath)) File.Delete(LastErrorFilePath); else WriteLastErrorFile(); }
        catch (IOException ex) { AppendLog($"Không xóa được trạng thái lỗi chưa xác nhận: {ex.Message}", "WARN"); }
        catch (UnauthorizedAccessException ex) { AppendLog($"Không xóa được trạng thái lỗi chưa xác nhận: {ex.Message}", "WARN"); }
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
            AppendLog($"Không chép được lỗi vào clipboard: {ex.Message}", "WARN");
        }
    }

    private void RaisePersistentError()
    {
        Raise(nameof(HasPersistentError));
        Raise(nameof(HasPagePersistentError));
        Raise(nameof(PersistentErrorText)); Raise(nameof(PersistentNoticeSummary));
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
            File.WriteAllText(temp, JsonSerializer.Serialize(new { task = _persistentErrorTask, time = _persistentErrorTime, text = _persistentErrorText, hint = _persistentErrorHint, severity = _persistentIsWarning ? "warning" : "error", notices = _pageNotices }));
            File.Move(temp, LastErrorFilePath, overwrite: true);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            AppendLog($"Không lưu được trạng thái lỗi chưa xác nhận: {ex.Message}", "WARN");
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
            if (root.TryGetProperty("notices", out var notices))
                foreach (var pair in JsonSerializer.Deserialize<Dictionary<string, SavedNotice>>(notices.GetRawText()) ?? [])
                    _pageNotices[ErrorTab(pair.Value.Task)] = pair.Value;
            else if (_persistentErrorText.Length > 0)
                _pageNotices[ErrorTab(_persistentErrorTask)] = new(_persistentErrorTask, _persistentErrorTime, _persistentErrorText, _persistentErrorHint, _persistentIsWarning);
            SelectPersistentErrorForPage();
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException)
        {
            _persistentErrorText = $"Không đọc được lỗi chưa xác nhận của phiên trước ({ex.Message}); xem Nhật ký.";
            _persistentErrorTime = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
        }
    }
}
