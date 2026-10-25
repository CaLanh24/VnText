using System.Threading;
using System.Windows;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    public event Action? UpdatePopupRequested;
    public event Action<string>? UpdateSuccessRequested;
    private System.Windows.Threading.DispatcherTimer? _updateReminderTimer;
    private System.Windows.Threading.DispatcherTimer? _updateCheckTimer;
    public string UpdateNotes => string.IsNullOrWhiteSpace(_githubUpdateResult.ReleaseNotes)
        ? "Phiên bản này chưa cung cấp ghi chú phát hành." : _githubUpdateResult.ReleaseNotes;
    public string OfferedVersion => _githubUpdateResult.Version;
    public string OfferedReleaseDate => _githubUpdateResult.ReleaseDate;
    public string VerifiedSuccessNotes { get; private set; } = "";
    public bool DownloadingUpdate { get; private set; }
    private long _downloadReceived;
    private long _downloadTotal;
    public long DownloadReceived => _downloadReceived;
    public long DownloadTotal => _downloadTotal;
    private void CacheReleaseNotes(GitHubUpdateCheckResult result)
    {
        if (string.IsNullOrWhiteSpace(result.Version) || string.IsNullOrWhiteSpace(result.ReleaseNotes)) return;
        var existing = ReleaseNotesHistory.FirstOrDefault(entry => string.Equals(entry.Version, result.Version, StringComparison.Ordinal));
        var entry = new ReleaseNotesCacheEntry
        {
            Version = result.Version,
            ReleaseDate = result.ReleaseDate,
            Notes = new string(result.ReleaseNotes.Take(16000).Where(c => !char.IsControl(c) || c is '\n' or '\r' or '\t').ToArray()),
            CachedAtUtc = DateTime.UtcNow,
        };
        if (existing is not null) ReleaseNotesHistory.Remove(existing);
        ReleaseNotesHistory.Insert(0, entry);
        while (ReleaseNotesHistory.Count > 20) ReleaseNotesHistory.RemoveAt(ReleaseNotesHistory.Count - 1);
        _settings.ReleaseNotesHistory = ReleaseNotesHistory.ToList();
        _settings.DownloadedUpdateVersion = entry.Version;
        _settings.DownloadedUpdateNotes = entry.Notes;
        SelectedReleaseNotesEntry = entry;
        SaveSettings();
    }
    public async Task CheckUpdatesOnStartupAsync()
    {
        var modelStatus = LoadModelStatusAsync();
        ShowVerifiedUpdateSuccess();
        if (_settings.AutoCheckUpdates)
        {
            StartGitHubUpdateCheck(metadataOnly: true);
            await _githubUpdateCheckTask;
        }
        ScheduleUpdateReminder(); ScheduleUpdateChecks();
        await modelStatus;
    }
    private void ScheduleUpdateChecks()
    {
        _updateCheckTimer?.Stop();
        if (!_settings.AutoCheckUpdates || _disposed != 0) return;
        if (_updateCheckTimer is null)
        {
            _updateCheckTimer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromHours(6) };
            _updateCheckTimer.Tick += (_, _) =>
            {
                if (_disposed == 0 && !Busy && !CsvEditorDirty && !GitHubApplyEnabled) StartGitHubUpdateCheck(metadataOnly: true);
            };
        }
        _updateCheckTimer.Start();
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
        if (!manual)
        {
            if (_settings.SkippedUpdateVersion == OfferedVersion) return;
            if (UpdatePreferencePolicy.CanDownload(_settings, Busy, CsvEditorDirty, OfferedVersion))
            {
                await DownloadOfferedUpdateAsync();
                if (_disposed == 0 && _settings.NotifyUpdates && _githubUpdateResult.State == GitHubUpdateState.UpdateAvailable) UpdatePopupRequested?.Invoke();
                return;
            }
            if (!UpdatePreferencePolicy.CanRemind(_settings, DateTime.UtcNow, OfferedVersion)) return;
        }
        UpdatePopupRequested?.Invoke();
    }
    public void DeferUpdate(bool skip)
    {
        if (string.IsNullOrWhiteSpace(OfferedVersion)) return;
        if (skip) _settings.SkippedUpdateVersion = OfferedVersion;
        else _settings.NextUpdateReminderUtc = DateTime.UtcNow.AddHours(_settings.UpdateReminderHours);
        SaveSettings(); ScheduleUpdateReminder();
    }
    private void ScheduleUpdateReminder()
    {
        _updateReminderTimer?.Stop();
        if (!_settings.NotifyUpdates || _settings.NextUpdateReminderUtc == DateTime.MinValue) return;
        var delay = _settings.NextUpdateReminderUtc - DateTime.UtcNow;
        _updateReminderTimer ??= new System.Windows.Threading.DispatcherTimer();
        _updateReminderTimer.Interval = delay > TimeSpan.Zero ? delay : TimeSpan.FromMinutes(1);
        _updateReminderTimer.Tick -= OnUpdateReminder;
        _updateReminderTimer.Tick += OnUpdateReminder;
        _updateReminderTimer.Start();
    }
    private void OnUpdateReminder(object? sender, EventArgs e)
    {
        _updateReminderTimer?.Stop();
        if (_disposed != 0) return;
        if (Busy || CsvEditorDirty) { ScheduleUpdateReminder(); return; }
        ResumeDeferredOffer();
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
        Raise(nameof(DownloadingUpdate));
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
            CacheReleaseNotes(result);
            if (result.State == GitHubUpdateState.UpdateAvailable)
            {
                _githubUpdatePackageLease = new GitHubUpdatePackageLease(root, result);
            }
            _githubUpdateStatus = GitHubStatusMessage(result.State, result.Version, result.Message);
            RaiseGitHubUpdateCard(); RaiseGitHubUpdateCommands();
        }
        finally
        {
            DownloadingUpdate = false;
            Raise(nameof(DownloadingUpdate));
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
