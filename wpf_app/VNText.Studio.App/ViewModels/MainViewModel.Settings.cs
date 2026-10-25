using System.Diagnostics;
using System.IO;
using System.Windows;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    private string _settingsStatus = "";
    public string SettingsStatus
    {
        get => UiText.Translate(_settingsStatus);
        private set { if (Set(ref _settingsStatus,value) && !string.IsNullOrWhiteSpace(value)) AppendLog(value); }
    }
    public sealed class SettingsChoice(string key, string label) : System.ComponentModel.INotifyPropertyChanged
    {
        public string Key { get; } = key;
        public string Label => UiText.Translate(label);
        public event System.ComponentModel.PropertyChangedEventHandler? PropertyChanged;
        internal void RefreshLabel() => PropertyChanged?.Invoke(this, new(nameof(Label)));
    }
    public SettingsChoice[] LanguageOptions { get; } = [new("vi", "Tiếng Việt"), new("en", "English")];
    public SettingsChoice[] ThemeOptions { get; } = [new("light", "Sáng"), new("dark", "Tối"), new("system", "Theo hệ thống")];
    public SettingsChoice[] CloseActionOptions { get; } = [new("exit", "Thoát ứng dụng"), new("tray", "Ẩn xuống khay hệ thống")];
    public SettingsChoice[] UpdateReminderOptions { get; } = [new("4", "Sau 4 giờ"), new("24", "Sau 1 ngày"), new("168", "Sau 1 tuần")];
    public string Language { get => _settings.Language; set { if (value is not ("vi" or "en") || value == _settings.Language) return; _settings.Language = value; Raise(); SaveSettings(); } }
    public string Theme { get => _settings.Theme; set { if (value is not ("light" or "dark" or "system") || value == _settings.Theme) return; _settings.Theme = value; Raise(); SaveSettings(); } }
    public string CloseAction { get => _settings.CloseAction; set { if (value is not ("exit" or "tray") || value == _settings.CloseAction) return; _settings.CloseAction = value; Raise(); SaveSettings(); } }
    public bool StartMinimized { get => _settings.StartMinimized; set { if (_settings.StartMinimized == value) return; _settings.StartMinimized = value; Raise(); SaveSettings(); } }
    public double[] BackgroundStrengthOptions => Enumerable.Range(0, 11).Select(n => n * 10d).Append(BackgroundStrength).Distinct().Order().ToArray();
    public double BackgroundStrength { get => _settings.BackgroundStrength; set { if (!double.IsFinite(value)) return; value = Math.Clamp(value, 0, 100); if (_settings.BackgroundStrength == value) return; _settings.BackgroundStrength = value; Raise(); SaveSettings(); } }
    public bool BackgroundUpdateDownload { get => _settings.BackgroundUpdateDownload; set { if (_settings.BackgroundUpdateDownload == value) return; _settings.BackgroundUpdateDownload = value; Raise(); SaveSettings(); } }
    public string UpdateReminder { get => _settings.UpdateReminderHours.ToString(); set { if (!int.TryParse(value, out var h) || h is not (4 or 24 or 168) || h == _settings.UpdateReminderHours) return; _settings.UpdateReminderHours = h; Raise(); SaveSettings(); } }
    internal void RefreshLocalizedOptions()
    {
        foreach (var option in ThemeOptions.Concat(CloseActionOptions).Concat(UpdateReminderOptions)) option.RefreshLabel();
        Raise(nameof(Theme)); Raise(nameof(CloseAction)); Raise(nameof(UpdateReminder));
        Raise(nameof(InputDisplay)); Raise(nameof(AnalyzeStatusText)); Raise(nameof(ModelStatus)); Raise(nameof(WorkerStatus)); Raise(nameof(SettingsStatus));
        Raise(nameof(HeroTitle)); Raise(nameof(HeroHint)); Raise(nameof(SelectedTab));
    }
    public double[] UiScaleOptions { get; } = [1, 1.1, 1.2];
    public double UiScale
    {
        get => _settings.UiScale;
        set { if (UiScaleOptions.Contains(value) && _settings.UiScale != value) { _settings.UiScale = value; Raise(); SaveSettings(); } }
    }
    public bool RememberWindow
    {
        get => _settings.RememberWindow;
        set { _settings.RememberWindow = value; Raise(); SaveSettings(); }
    }
    public bool AutoCheckUpdates
    {
        get => _settings.AutoCheckUpdates;
        set { _settings.AutoCheckUpdates = value; Raise(); SaveSettings(); ScheduleUpdateChecks(); }
    }
    public bool NotifyUpdates
    {
        get => _settings.NotifyUpdates;
        set { _settings.NotifyUpdates = value; Raise(); SaveSettings(); ScheduleUpdateReminder(); }
    }
    public string DataFolder => WorkerPaths.AppDataRoot();
    private string _modelFolder = "";
    private string _modelStatus = "Đang kiểm tra mô hình dịch…";
    public string ModelFolder => _modelFolder;
    public string ModelStatus => UiText.Translate(_modelStatus);
    public string WorkerStatus
    {
        get { try { return UiText.Translate(File.Exists(WorkerPaths.PythonExecutable()) ? "Python worker có sẵn" : "Thiếu Python worker"); }
              catch (Exception ex) { return "Worker chưa sẵn sàng: " + ex.Message; } }
    }
    public RelayCommand OpenDataFolderCommand => new(_ => OpenSettingsFolder(DataFolder));
    public RelayCommand OpenModelFolderCommand => new(_ => OpenSettingsFolder(ModelFolder));
    public RelayCommand OpenRepositoryCommand => new(_ => OpenSettingsLink("https://github.com/CaLanh24/VnText"));
    public RelayCommand OpenFeedbackCommand => new(_ => OpenSettingsLink("https://github.com/CaLanh24/VnText/issues"));
    public event Action? ReleaseNotesRequested;
    public RelayCommand OpenReleaseNotesCommand => new(parameter => { _ = RefreshReleaseHistoryAsync(); ReleaseNotesRequested?.Invoke(); });
    private bool _releaseHistoryLoading;
    private string _releaseNotesStatus = "";
    public string ReleaseNotesStatus { get => _releaseNotesStatus; private set => Set(ref _releaseNotesStatus, value); }
    private async Task RefreshReleaseHistoryAsync()
    {
        if (_releaseHistoryLoading) return;
        _releaseHistoryLoading = true; ReleaseNotesStatus = "Đang tải lịch sử phát hành…";
        try
        {
            var result = await WpfUpdateService.ReadReleaseNotesHistoryAsync(_githubHttpHandler);
            if (_disposed != 0) return;
            foreach (var entry in result.Entries)
            {
                var existing = ReleaseNotesHistory.FirstOrDefault(old => old.Version == entry.Version);
                if (existing is not null) ReleaseNotesHistory.Remove(existing);
                ReleaseNotesHistory.Add(entry);
            }
            var ordered = ReleaseNotesHistory.OrderByDescending(entry => System.Version.TryParse(entry.Version, out var v) ? v : new System.Version()).Take(20).ToArray();
            ReleaseNotesHistory.Clear(); foreach (var entry in ordered) ReleaseNotesHistory.Add(entry);
            _settings.ReleaseNotesHistory = ordered.ToList();
            if (result.Entries.Count > 0) SaveSettings();
            ReleaseNotesStatus = result.Error;
        }
        finally { _releaseHistoryLoading = false; }
    }
    public ReleaseNotesCacheEntry? SelectedReleaseNotesEntry
    {
        get => _selectedReleaseNotesEntry;
        set { if (Set(ref _selectedReleaseNotesEntry, value)) { Raise(nameof(SelectedReleaseNotesTitle)); Raise(nameof(SelectedReleaseNotesBody)); } }
    }
    public string SelectedReleaseNotesTitle => SelectedReleaseNotesEntry is null
        ? "Chưa có ghi chú được lưu. Hãy kết nối mạng và kiểm tra cập nhật để lưu ghi chú phát hành."
        : $"v{SelectedReleaseNotesEntry.Version}" + (string.IsNullOrWhiteSpace(SelectedReleaseNotesEntry.ReleaseDate) ? "" : $" · {SelectedReleaseNotesEntry.ReleaseDate}");
    public string SelectedReleaseNotesBody => SelectedReleaseNotesEntry?.Notes ?? "";
    private void OpenSettingsLink(string url)
    {
        try { Process.Start(new ProcessStartInfo(url) { UseShellExecute = true }); }
        catch (Exception ex) { SettingsStatus = "Không mở được liên kết: " + ex.Message; }
    }
    private async Task LoadModelStatusAsync()
    {
        try
        {
            var start = new ProcessStartInfo(WorkerPaths.PythonExecutable())
            {
                WorkingDirectory = WorkerPaths.RepoRoot(), UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = System.Text.Encoding.UTF8, StandardErrorEncoding = System.Text.Encoding.UTF8,
            };
            start.ArgumentList.Add("-B"); start.ArgumentList.Add("-c");
            start.ArgumentList.Add("import json; from vntext.mt_ct2_model import model_status; print(json.dumps(model_status(), ensure_ascii=False))");
            WorkerPaths.ConfigureReleaseEnvironment(start.Environment);
            start.Environment["PYTHONUTF8"] = "1";
            start.Environment["HF_HUB_OFFLINE"] = "1";
            start.Environment["TRANSFORMERS_OFFLINE"] = "1";
            using var process = Process.Start(start) ?? throw new InvalidOperationException("Không khởi chạy được kiểm tra model.");
            var output = process.StandardOutput.ReadToEndAsync();
            var error = process.StandardError.ReadToEndAsync();
            try { await process.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(15)); }
            catch (TimeoutException) { process.Kill(entireProcessTree: true); await process.WaitForExitAsync(); throw; }
            if (process.ExitCode != 0) throw new InvalidOperationException($"Kiểm tra model exit {process.ExitCode}: {await error}");
            using var result = System.Text.Json.JsonDocument.Parse(await output);
            _modelFolder = result.RootElement.GetProperty("path").GetString() ?? "";
            var modelReady = result.RootElement.GetProperty("ready").GetBoolean();
            var modelMessage = result.RootElement.TryGetProperty("message", out var messageElement)
                ? messageElement.GetString()
                : null;
            _translationModelChecked = true;
            _translationModelUnavailable = !modelReady;
            _modelStatus = string.IsNullOrWhiteSpace(modelMessage)
                ? modelReady ? "Mô hình dịch đã sẵn sàng." : "Chưa có mô hình dịch trên máy."
                : modelMessage;
        }
        catch (Exception ex)
        {
            _translationModelChecked = true;
            _translationModelUnavailable = true;
            _modelStatus = "Không kiểm tra được mô hình dịch: " + ex.Message;
        }
        if (_disposed != 0) return;
        Raise(nameof(ModelFolder)); Raise(nameof(ModelStatus)); Raise(nameof(TranslateReadinessText)); Raise(nameof(TranslateWorkflowStatusText));
        RunTranslateCommand?.RaiseCanExecuteChanged();
    }
    private void OpenSettingsFolder(string path)
    {
        try { if (!Directory.Exists(path)) throw new DirectoryNotFoundException("Thư mục chưa có."); Process.Start(new ProcessStartInfo(path) { UseShellExecute = true }); }
        catch (Exception ex) { SettingsStatus = "Không mở được thư mục: " + ex.Message; }
    }
    private void SaveSettings()
    {
        try { AppSettingsStore.Save(_settings); SettingsStatus = ""; }
        catch (Exception ex) { SettingsStatus = "Không lưu được cài đặt; file hiện có được giữ nguyên: " + ex.Message; }
    }
    internal void RestoreWindow(Window window)
    {
        if (!_settings.RememberWindow) return;
        var area = SystemParameters.WorkArea;
        window.Width = Math.Clamp(double.IsFinite(_settings.WindowWidth) ? _settings.WindowWidth : 1440, 1040, Math.Max(1040, area.Width));
        window.Height = Math.Clamp(double.IsFinite(_settings.WindowHeight) ? _settings.WindowHeight : 920, 720, Math.Max(720, area.Height));
        if (double.IsFinite(_settings.WindowLeft) && double.IsFinite(_settings.WindowTop))
        {
            window.WindowStartupLocation = WindowStartupLocation.Manual;
            window.Left = Math.Clamp(_settings.WindowLeft, area.Left, Math.Max(area.Left, area.Right - window.Width));
            window.Top = Math.Clamp(_settings.WindowTop, area.Top, Math.Max(area.Top, area.Bottom - window.Height));
        }
    }
    internal void SaveWindow(Window window)
    {
        if (!_settings.RememberWindow) return;
        var bounds = window.WindowState == WindowState.Normal ? new Rect(window.Left, window.Top, window.Width, window.Height) : window.RestoreBounds;
        _settings.WindowLeft = bounds.Left; _settings.WindowTop = bounds.Top;
        _settings.WindowWidth = bounds.Width; _settings.WindowHeight = bounds.Height;
        SaveSettings();
    }
}
