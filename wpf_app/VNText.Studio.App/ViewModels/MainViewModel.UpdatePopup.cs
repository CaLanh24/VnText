using System.Threading;
using System.Windows;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    public event Action? UpdatePopupRequested;
    public event Action<string>? UpdateSuccessRequested;
    private string _deferredVersion = "";
    public string UpdateNotes => string.IsNullOrWhiteSpace(_githubUpdateResult.ReleaseNotes)
        ? "Phiên bản này chưa cung cấp ghi chú phát hành." : _githubUpdateResult.ReleaseNotes;
    public string OfferedVersion => _githubUpdateResult.Version;
    public string VerifiedSuccessNotes { get; private set; } = "";
    public bool DownloadingUpdate { get; private set; }
    private long _downloadReceived;
    private long _downloadTotal;
    public long DownloadReceived => _downloadReceived;
    public long DownloadTotal => _downloadTotal;
    public async Task CheckUpdatesOnStartupAsync()
    {
        var modelStatus = LoadModelStatusAsync();
        ShowVerifiedUpdateSuccess();
        if (_settings.AutoCheckUpdates)
        {
            StartGitHubUpdateCheck(metadataOnly: true);
            await _githubUpdateCheckTask;
        }
        await modelStatus;
    }
    private void ShowVerifiedUpdateSuccess()
    {
        if (!WorkerPaths.IsReleaseLayout()) return;
        try
        {
            var exe = WorkerPaths.MainExePath();
            var root = System.IO.Path.GetDirectoryName(exe)!;
            var version = System.Diagnostics.FileVersionInfo.GetVersionInfo(exe).ProductVersion ?? "";
            var transaction = FullAppUpdateService.ReadVerifiedSuccess(root, version, _settings.AcknowledgedUpdateTransaction);
            if (transaction is null) return;
            VerifiedSuccessNotes = _settings.DownloadedUpdateVersion == version && !string.IsNullOrWhiteSpace(_settings.DownloadedUpdateNotes)
                ? _settings.DownloadedUpdateNotes[..Math.Min(16000, _settings.DownloadedUpdateNotes.Length)]
                : "Phiên bản này chưa lưu ghi chú phát hành. Xem ghi chú trong Cài đặt → Giới thiệu.";
            UpdateSuccessRequested?.Invoke(version);
            _settings.AcknowledgedUpdateTransaction = transaction;
            SaveSettings();
        }
        catch (Exception ex) { AppendLog("Không xác minh được receipt cập nhật: " + ex.Message); }
    }
    internal void ResumeDeferredOffer()
    {
        if (_githubUpdateResult.State == GitHubUpdateState.OfferAvailable)
            _ = ShowOfferAfterCheckAsync(Task.CompletedTask, manual: false);
    }
    private async Task ShowOfferAfterCheckAsync(Task check, bool manual)
    {
        await check;
        if (_disposed != 0 || _githubUpdateResult.State != GitHubUpdateState.OfferAvailable) return;
        if (Busy || CsvEditorDirty) return;
        if (!manual && (!_settings.NotifyUpdates || _settings.SkippedUpdateVersion == OfferedVersion || _deferredVersion == OfferedVersion)) return;
        UpdatePopupRequested?.Invoke();
    }
    public void DeferUpdate(bool skip)
    {
        if (string.IsNullOrWhiteSpace(OfferedVersion)) return;
        _deferredVersion = OfferedVersion;
        if (skip) { _settings.SkippedUpdateVersion = OfferedVersion; SaveSettings(); }
    }
    public async Task DownloadOfferedUpdateAsync()
    {
        if (DownloadingUpdate || _githubUpdateChecking || Busy || CsvEditorDirty) return;
        if (_githubUpdateResult.State != GitHubUpdateState.OfferAvailable)
        {
            StartGitHubUpdateCheck(metadataOnly: true);
            await _githubUpdateCheckTask;
            if (_disposed != 0 || Busy || CsvEditorDirty || _githubUpdateResult.State != GitHubUpdateState.OfferAvailable) return;
        }
        DownloadingUpdate = true;
        _downloadReceived = 0; _downloadTotal = 0;
        RaiseGitHubUpdateCommands();
        var cancellation = new CancellationTokenSource();
        _githubUpdateCancellation = cancellation;
        try
        {
            var progress = new Progress<(long Received, long Total)>(p =>
            {
                _downloadReceived = p.Received; _downloadTotal = p.Total;
                Raise(nameof(DownloadReceived)); Raise(nameof(DownloadTotal));
            });
            var root = _updateInstallRoot ?? System.IO.Path.GetDirectoryName(WorkerPaths.MainExePath())!;
            var result = await WpfUpdateService.CheckGitHubUpdateAsync(root, _githubHttpHandler,
                cancellation.Token, expectedOffer: _githubUpdateResult, progress: progress);
            if (cancellation.IsCancellationRequested || _disposed != 0)
            {
                WpfUpdateService.DeleteGitHubUpdateCandidate(root, result);
                return;
            }
            DisposeGitHubUpdatePackageLease();
            _githubUpdateResult = result;
            _githubUpdateState = result.State;
            if (result.State == GitHubUpdateState.UpdateAvailable)
            {
                _githubUpdatePackageLease = new GitHubUpdatePackageLease(root, result);
                _settings.DownloadedUpdateVersion = result.Version;
                _settings.DownloadedUpdateNotes = result.ReleaseNotes;
                SaveSettings();
            }
            _githubUpdateStatus = GitHubStatusMessage(result.State, result.Version, result.Message);
            RaiseGitHubUpdateCard(); RaiseGitHubUpdateCommands();
        }
        finally
        {
            DownloadingUpdate = false;
            RaiseGitHubUpdateCommands();
            if (ReferenceEquals(_githubUpdateCancellation, cancellation)) _githubUpdateCancellation = null;
            cancellation.Dispose();
        }
    }
    public void CancelUpdateDownload() => _githubUpdateCancellation?.Cancel();
    public void RestartForUpdate()
    {
        if (Busy || CsvEditorDirty || DownloadingUpdate || !GitHubApplyEnabled) return;
        var lease = _githubUpdatePackageLease;
        if (lease is not null) WpfUpdateService.StartGitHubUpdate(_worker.ProcessId, lease);
    }
}
