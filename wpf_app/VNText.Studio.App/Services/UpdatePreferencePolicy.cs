namespace VNText.Studio.App.Services;

internal static class UpdatePreferencePolicy
{
    public static bool CanDownload(AppSettings settings, bool busy, bool dirty, string version) =>
        settings.BackgroundUpdateDownload && !busy && !dirty && !string.IsNullOrWhiteSpace(version) && settings.SkippedUpdateVersion != version;
    public static bool CanRemind(AppSettings settings, DateTime utcNow, string version) =>
        settings.NotifyUpdates && settings.SkippedUpdateVersion != version && settings.NextUpdateReminderUtc <= utcNow;
}
