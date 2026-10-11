using System.Diagnostics;
using System.IO;
using System.Windows;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    private string _settingsStatus = "";
    public string SettingsStatus { get => _settingsStatus; private set => Set(ref _settingsStatus, value); }
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
        set { _settings.AutoCheckUpdates = value; Raise(); SaveSettings(); }
    }
    public bool NotifyUpdates
    {
        get => _settings.NotifyUpdates;
        set { _settings.NotifyUpdates = value; Raise(); SaveSettings(); }
    }
    public string DataFolder => WorkerPaths.AppDataRoot();
    private string _modelFolder = "";
    private string _modelStatus = "Chưa kiểm tra model.";
    public string ModelFolder => _modelFolder;
    public string ModelStatus => _modelStatus;
    public string WorkerStatus
    {
        get { try { return File.Exists(WorkerPaths.PythonExecutable()) ? "Python worker có sẵn" : "Thiếu Python worker"; }
              catch (Exception ex) { return "Worker chưa sẵn sàng: " + ex.Message; } }
    }
    public RelayCommand OpenDataFolderCommand => new(_ => OpenSettingsFolder(DataFolder));
    public RelayCommand OpenModelFolderCommand => new(_ => OpenSettingsFolder(ModelFolder));
    public RelayCommand OpenRepositoryCommand => new(_ => OpenSettingsLink("https://github.com/CaLanh24/VnText"));
    public RelayCommand OpenReleaseNotesCommand => new(_ => OpenSettingsLink("https://github.com/CaLanh24/VnText/releases"));
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
            _modelStatus = result.RootElement.GetProperty("ready").GetBoolean()
                ? "File model OPUS-MT INT8 có sẵn." : "Thiếu file model OPUS-MT INT8.";
        }
        catch (Exception ex) { _modelStatus = "Không kiểm tra được model: " + ex.Message; }
        if (_disposed != 0) return;
        Raise(nameof(ModelFolder)); Raise(nameof(ModelStatus));
    }
    private void OpenSettingsFolder(string path)
    {
        try { if (!Directory.Exists(path)) throw new DirectoryNotFoundException("Thư mục chưa có."); Process.Start(new ProcessStartInfo(path) { UseShellExecute = true }); }
        catch (Exception ex) { SettingsStatus = "Không mở được thư mục: " + ex.Message; }
    }
    private void SaveSettings()
    {
        try { AppSettingsStore.Save(_settings); SettingsStatus = "Đã lưu cài đặt."; }
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
