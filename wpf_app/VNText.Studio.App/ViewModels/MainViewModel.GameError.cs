using System.IO;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Windows;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

/// <summary>
/// 0.1.42: errors of the PATCHED game (Ren'Py's traceback.txt) and the saved location of the bug package.  Both use the short-lived Python process of the
/// bug report, so they work while the worker is busy.  Nothing leaves the machine from here.
/// </summary>
public sealed partial class MainViewModel
{
    public RelayCommand ReportGameErrorCommand { get; private set; } = null!;
    public RelayCommand OpenBugReportFolderCommand { get; private set; } = null!;

    private string _lastBugReportZip = "";
    private bool _gameErrorRunning;

    private void InitializeGameErrorCommands()
    {
        ReportGameErrorCommand = new RelayCommand(_ => ReportGameError(), _ => !_gameErrorRunning && !string.IsNullOrWhiteSpace(InputPath));
        OpenBugReportFolderCommand = new RelayCommand(_ => OpenBugReportFolder(), _ => !string.IsNullOrWhiteSpace(OutputPath) || !string.IsNullOrWhiteSpace(_lastBugReportZip));
    }

    /// <summary>Remember where a finished package was saved (the message of the worker names it: "Gói cũng được lưu tại …").</summary>
    internal void RememberBugReportZip(string? text)
    {
        if (string.IsNullOrWhiteSpace(text)) return;
        var m = Regex.Match(text, @"Gói cũng được lưu tại (?<p>.+?) —", RegexOptions.CultureInvariant);
        if (!m.Success) m = Regex.Match(text, @"Đã tạo gói báo lỗi ẩn danh: (?<p>[^\r\n]+)", RegexOptions.CultureInvariant);
        if (m.Success) { _lastBugReportZip = m.Groups["p"].Value.Trim(); OpenBugReportFolderCommand?.RaiseCanExecuteChanged(); }
    }

    private string BugReportFolderToOpen()
    {
        try
        {
            if (!string.IsNullOrWhiteSpace(_lastBugReportZip) && File.Exists(_lastBugReportZip))
                return Path.GetDirectoryName(_lastBugReportZip) ?? "";
            if (!string.IsNullOrWhiteSpace(OutputPath))
            {
                var folder = Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "bug-reports");
                if (Directory.Exists(folder)) return folder;
            }
        }
        catch (Exception exc) when (exc is IOException or UnauthorizedAccessException or ArgumentException) { }
        return "";
    }

    private void OpenBugReportFolder()
    {
        var folder = BugReportFolderToOpen();
        if (string.IsNullOrEmpty(folder))
        {
            ShowToast(UiText.Translate("Chưa có gói báo lỗi nào; bấm “Tạo gói báo lỗi” trước."), "info");
            return;
        }
        _pathPicker.OpenPath(folder);
    }

    /// <summary>"Báo lỗi game": reads traceback.txt and the generated translation file of the patched game, shows what it found, builds the anonymous package
    /// on a yes, and offers to take the broken lines out of the game (with a backup) on a second yes.</summary>
    private async void ReportGameError()
    {
        if (_gameErrorRunning || string.IsNullOrWhiteSpace(InputPath)) return;
        _gameErrorRunning = true; ReportGameErrorCommand?.RaiseCanExecuteChanged();
        try
        {
            var package = string.IsNullOrWhiteSpace(OutputPath) ? "" : WorkflowStatus.ResolvePackageDir(OutputPath);
            var manifest = package.Length > 0 ? Path.Combine(package, "manifest.json") : "";
            ShowToast(UiText.Translate("Đang đọc lỗi của game…"), "info");
            var scan = await Task.Run(() => BugReportProcess.RunAsync(new { action = "game_error_scan", src = InputPath, manifest }));
            if (!scan.Ok) { ShowToast(scan.Text, "error"); return; }
            AppendLog(scan.Text);
            var blocks = new List<int[]>();
            var revertable = false;
            if (scan.Json is { } element)
            {
                if (element.TryGetProperty("revertable", out var r) && r.ValueKind == JsonValueKind.True) revertable = true;
                if (element.TryGetProperty("blocks", out var b) && b.ValueKind == JsonValueKind.Array)
                    foreach (var pair in b.EnumerateArray()) blocks.Add(pair.EnumerateArray().Select(x => x.GetInt32()).ToArray());
            }
            var ask = scan.Text + "\n\n" + UiText.Translate("Tạo gói báo lỗi game (ẩn danh: không có tên game, tên tệp hay câu thoại) để đưa cho người hỗ trợ?");
            if (AppDialogService.Show(ask, UiText.Translate("Báo lỗi game"), MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes)
            {
                var folder = package.Length > 0 ? Path.Combine(package, "bug-reports") : Path.Combine(Path.GetTempPath(), "VNText-bug-reports");
                var built = await Task.Run(() => BugReportProcess.RunAsync(new
                {
                    src = InputPath, @out = folder, log_lines = LogLines.TakeLast(400).ToArray(), analysis_report = ResolveAnalyzeReportPath(),
                    extract_status = package.Length > 0 ? Path.Combine(package, "extract_status.json") : "", app_version = Version, game_error = true, manifest,
                }));
                AppendLog(built.Text);
                if (built.Ok) { _lastBugReportZip = built.Path; OpenBugReportFolderCommand?.RaiseCanExecuteChanged(); }
                RequestCompletion(UiText.Translate("VNText Studio — Báo lỗi game"), built.Text, built.Ok ? "info" : "error");
            }
            if (revertable && blocks.Count > 0 &&
                AppDialogService.Show(UiText.Translate("Gỡ các dòng gây lỗi khỏi bản Việt hóa trong game? Game sẽ dùng câu gốc ở những chỗ đó. Tệp được sao lưu cạnh nó, game gốc khác không bị đụng tới."),
                    UiText.Translate("Gỡ dòng gây lỗi"), MessageBoxButton.YesNo, MessageBoxImage.Warning) == MessageBoxResult.Yes)
            {
                var done = await Task.Run(() => BugReportProcess.RunAsync(new { action = "game_error_revert", src = InputPath, blocks }));
                AppendLog(done.Text);
                RequestCompletion(UiText.Translate("VNText Studio — Gỡ dòng gây lỗi"), done.Text, done.Ok ? "info" : "error");
            }
        }
        finally
        {
            _gameErrorRunning = false; ReportGameErrorCommand?.RaiseCanExecuteChanged();
        }
    }
}
