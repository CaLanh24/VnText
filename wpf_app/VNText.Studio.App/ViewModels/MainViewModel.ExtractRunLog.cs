using System.Collections.ObjectModel;
using System.ComponentModel;
using System.IO;
using System.Text;
using System.Windows;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

/// <summary>One extraction run: a durable, append-only file plus (for the live run) the complete in-memory line list.</summary>
public sealed class ExtractRunInfo : INotifyPropertyChanged
{
    private string _status = "";
    public ExtractRunInfo(string filePath, DateTime started, string status = "")
    {
        FilePath = filePath;
        Started = started;
        _status = status;
    }
    public string FilePath { get; }
    public DateTime Started { get; }
    public string Status
    {
        get => _status;
        set
        {
            _status = value;
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(Status)));
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(Title)));
        }
    }
    public string Title => Started.ToString("dd/MM HH:mm:ss") + (_status.Length == 0 ? "" : " · " + UiText.Translate(_status));
    public void RefreshTitle() => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(nameof(Title)));
    public event PropertyChangedEventHandler? PropertyChanged;
}

/// <summary>
/// The Extract tab's own task journal. Every line of the CURRENT extraction run (progress, worker log, errors, phases) is kept in full
/// for the whole run and after it ends, in a virtualized list; each run also lives in its own append-only file so earlier runs stay
/// readable from the inline run selector. Other tasks (analyze/resources/translate/patch/image batch) never enter this journal; the
/// sidebar Journal keeps general audit copies and is NOT a substitute for it.
/// </summary>
public sealed partial class MainViewModel
{
    internal const int ExtractLineMaxChars = 60000;
    private ObservableCollection<string> _extractHistoryLines = new();
    private ExtractRunInfo? _liveRun;
    private ExtractRunInfo? _selectedExtractRun;
    private string _liveRunTaskId = "";
    private string _liveRunLastStep = "";
    private StreamWriter? _liveRunWriter;
    private bool _liveRunWriteFailed;

    public ObservableCollection<ExtractRunInfo> ExtractRuns { get; } = new();
    internal string ExtractRunsRoot => Path.Combine(WorkerPaths.AppDataRoot(), "extract-runs");
    public bool ExtractRunSelectorVisible => ExtractRuns.Count > 1;
    public string ExtractLogTitle => UiText.Translate("Nhật ký");
    public string ExtractLogSummary => UiText.Format("{0} dòng nhật ký", ExtractLogShown.Count);
    public System.Collections.IList ExtractLogShown =>
        _selectedExtractRun is null || ReferenceEquals(_selectedExtractRun, _liveRun) ? ExtractLogLines : _extractHistoryLines;
    public RelayCommand CopyExtractLogCommand { get; private set; } = null!;

    public ExtractRunInfo? SelectedExtractRun
    {
        get => _selectedExtractRun;
        set
        {
            if (ReferenceEquals(value, _selectedExtractRun)) return;
            _selectedExtractRun = value;
            if (value is not null && !ReferenceEquals(value, _liveRun)) LoadExtractHistory(value);
            RaiseExtractLog();
            Raise(nameof(SelectedExtractRun));
        }
    }

    private void InitializeExtractRuns()
    {
        CopyExtractLogCommand = new RelayCommand(_ => CopyExtractLog(), _ => ExtractLogShown.Count > 0);
        try
        {
            if (!Directory.Exists(ExtractRunsRoot)) return;
            foreach (var file in Directory.EnumerateFiles(ExtractRunsRoot, "run-*.log").OrderByDescending(f => f, StringComparer.Ordinal))
            {
                var name = Path.GetFileName(file);
                // run-yyyyMMdd-HHmmssfff-<id>.log
                var started = name.Length >= 24 && DateTime.TryParseExact(name.Substring(4, 18), "yyyyMMdd-HHmmssfff",
                    System.Globalization.CultureInfo.InvariantCulture, System.Globalization.DateTimeStyles.None, out var parsed)
                    ? parsed : File.GetCreationTime(file);
                ExtractRuns.Add(new ExtractRunInfo(file, started));
            }
            if (ExtractRuns.Count > 0)
            {
                _selectedExtractRun = ExtractRuns[0];
                LoadExtractHistory(ExtractRuns[0]);
            }
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            ExtractLogLines.Add($"[{DateTime.Now:HH:mm:ss}] Không đọc được danh sách lần lấy text trước: {ex.Message}");
        }
    }

    private void LoadExtractHistory(ExtractRunInfo run)
    {
        try
        {
            using var stream = new FileStream(run.FilePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            using var reader = new StreamReader(stream, Encoding.UTF8);
            var all = new List<string>();
            for (var line = reader.ReadLine(); line is not null; line = reader.ReadLine()) all.Add(line);
            _extractHistoryLines = new ObservableCollection<string>(all);
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            _extractHistoryLines = new ObservableCollection<string> { $"[{DateTime.Now:HH:mm:ss}] Không đọc được nhật ký lần chạy này: {ex.Message}" };
        }
    }

    private void RaiseExtractLog()
    {
        Raise(nameof(ExtractLogShown));
        Raise(nameof(ExtractLogSummary));
        Raise(nameof(ExtractRunSelectorVisible));
        CopyExtractLogCommand?.RaiseCanExecuteChanged();
    }

    internal bool IsLiveExtractRun(string? id) => _liveRun is not null && _liveRunTaskId.Length > 0 && string.Equals(id, _liveRunTaskId, StringComparison.Ordinal);

    /// <summary>A new extraction starts a NEW run: the previous run stays in its file and in the selector; nothing is deleted.</summary>
    private void StartExtractRun(string id)
    {
        EndExtractRun(null, "Bị gián đoạn");
        var started = DateTime.Now;
        var safe = new string(id.Where(char.IsLetterOrDigit).Take(12).ToArray());
        var file = Path.Combine(ExtractRunsRoot, $"run-{started:yyyyMMdd-HHmmssfff}-{safe}.log");
        _liveRunWriteFailed = false;
        try
        {
            Directory.CreateDirectory(ExtractRunsRoot);
            _liveRunWriter = new StreamWriter(new FileStream(file, FileMode.CreateNew, FileAccess.Write, FileShare.ReadWrite), new UTF8Encoding(false)) { AutoFlush = true };
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            _liveRunWriter = null;
            _liveRunWriteFailed = true;
            PersistJournal($"Không tạo được tệp lịch sử lần lấy text: {ex.Message}");
        }
        _liveRun = new ExtractRunInfo(file, started, "Đang chạy");
        _liveRunTaskId = id;
        _liveRunLastStep = "";
        ExtractRuns.Insert(0, _liveRun);
        ExtractLogLines.Clear();
        _selectedExtractRun = _liveRun;
        RaiseExtractLog();
        Raise(nameof(SelectedExtractRun));
    }

    private void EndExtractRun(string? id, string status)
    {
        if (_liveRun is null || _liveRunTaskId.Length == 0) return;
        if (id is not null && !string.Equals(id, _liveRunTaskId, StringComparison.Ordinal)) return;
        AddExtractRunLine(_liveRunTaskId, $"── {UiText.Translate(status)} ──");
        _liveRunTaskId = "";
        try { _liveRunWriter?.Dispose(); } catch (IOException) { }
        _liveRunWriter = null;
        _liveRun.Status = status;
        RaiseExtractLog();
    }

    internal void NoteExtractPhase(string? id, string? step, string userStep)
    {
        if (!IsLiveExtractRun(id) || string.IsNullOrWhiteSpace(step) || string.Equals(step, _liveRunLastStep, StringComparison.Ordinal)) return;
        _liveRunLastStep = step;
        AddExtractRunLine(id!, $"── {userStep} ──");
    }

    /// <summary>Appends the complete text (every line, no eviction); only the live run's own task id is accepted.</summary>
    internal void AddExtractRunLine(string? id, string text)
    {
        if (!IsLiveExtractRun(id) || string.IsNullOrWhiteSpace(text)) return;
        var stamp = DateTime.Now.ToString("HH:mm:ss");
        var rows = text.Trim().Replace("\r", "").Split('\n');
        var first = true;
        foreach (var raw in rows)
        {
            var content = raw.TrimEnd();
            if (content.Length == 0) continue;
            if (content.Length > ExtractLineMaxChars)
                content = content[..ExtractLineMaxChars] + $" […đã cắt {content.Length - ExtractLineMaxChars} ký tự vượt giới hạn một dòng]";
            if (first && rows.Length == 1 && ExtractLogLines.Count > 0 && ExtractLogLines[^1].EndsWith("] " + content, StringComparison.Ordinal))
                return;                                    // identical consecutive progress line
            var line = first ? $"[{stamp}] {content}" : $"           {content}";
            first = false;
            ExtractLogLines.Add(line);
            WriteExtractRunLine(line);
        }
        if ((ExtractLogLines.Count & 31) == 0) { Raise(nameof(ExtractLogSummary)); CopyExtractLogCommand?.RaiseCanExecuteChanged(); }
    }

    private void WriteExtractRunLine(string line)
    {
        if (_liveRunWriter is null) return;
        try { _liveRunWriter.WriteLine(line); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            _liveRunWriter = null;
            if (!_liveRunWriteFailed)
            {
                _liveRunWriteFailed = true;
                ExtractLogLines.Add($"[{DateTime.Now:HH:mm:ss}] Không ghi được lịch sử lần chạy ra tệp (nhật ký trong bộ nhớ vẫn đầy đủ): {ex.Message}");
            }
        }
    }

    private void CopyExtractLog()
    {
        try { Clipboard.SetText(string.Join(Environment.NewLine, ExtractLogShown.Cast<string>())); }
        catch (System.Runtime.InteropServices.ExternalException ex) { AppendLog($"Không chép được nhật ký lấy text: {ex.Message}"); }
    }

    internal void RefreshExtractLogLanguage()
    {
        foreach (var run in ExtractRuns) run.RefreshTitle();
        Raise(nameof(ExtractLogTitle));
        Raise(nameof(ExtractLogSummary));
    }
}
