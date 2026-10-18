using System.IO;
using System.Text.Json;

namespace VNText.Studio.App.Services;

public sealed class AppSettings
{
    public bool SeparateReview { get; set; } = true;
    public bool OverwriteTranslation { get; set; }
    public bool HumanReviewRequired { get; set; }
    public string ExtractLevel { get; set; } = ExtractLevels.Balanced;
    public double UiScale { get; set; } = 1;
    public bool RememberWindow { get; set; } = true;
    public double WindowLeft { get; set; } = double.NaN;
    public double WindowTop { get; set; } = double.NaN;
    public double WindowWidth { get; set; } = 1440;
    public double WindowHeight { get; set; } = 920;
    public string Language { get; set; } = "vi";
    public string Theme { get; set; } = "light";
    public string CloseAction { get; set; } = "exit";
    public bool StartMinimized { get; set; }
    public double BackgroundStrength { get; set; } = 100;
    public bool BackgroundUpdateDownload { get; set; }
    public int UpdateReminderHours { get; set; } = 24;
    public DateTime NextUpdateReminderUtc { get; set; } = DateTime.MinValue;
    public bool AutoCheckUpdates { get; set; } = true;
    public bool NotifyUpdates { get; set; } = true;
    public string SkippedUpdateVersion { get; set; } = "";
    public string AcknowledgedUpdateTransaction { get; set; } = "";
    public string DownloadedUpdateVersion { get; set; } = "";
    public string DownloadedUpdateNotes { get; set; } = "";
}

public static class AppSettingsStore
{
    private static readonly JsonSerializerOptions JsonOpts = new() { WriteIndented = true,
        NumberHandling = System.Text.Json.Serialization.JsonNumberHandling.AllowNamedFloatingPointLiterals };

    public static string SettingsPath()
    {
        return Path.Combine(WorkerPaths.AppDataRoot(), "wpf_settings.json");
    }

    public static AppSettings Load() => Load(out _);

    public static AppSettings Load(out string error)
    {
        error = "";
        var path = SettingsPath(); // Fail clearly when the selected Release install folder is read-only.
        try
        {
            if (!File.Exists(path))
                return new AppSettings();
            var json = File.ReadAllText(path);
            var loaded = JsonSerializer.Deserialize<AppSettings>(json, JsonOpts)
                ?? throw new JsonException("Settings must be an object.");
            loaded.ExtractLevel = ExtractLevels.Normalize(loaded.ExtractLevel);
            loaded.UiScale = loaded.UiScale is 1 or 1.1 or 1.2 ? loaded.UiScale : 1;
            loaded.Language = loaded.Language is "vi" or "en" ? loaded.Language : "vi";
            loaded.Theme = loaded.Theme is "light" or "dark" or "system" ? loaded.Theme : "light";
            loaded.CloseAction = loaded.CloseAction is "exit" or "tray" ? loaded.CloseAction : "exit";
            loaded.BackgroundStrength = double.IsFinite(loaded.BackgroundStrength) ? Math.Clamp(loaded.BackgroundStrength, 0, 100) : 100;
            loaded.UpdateReminderHours = loaded.UpdateReminderHours is 4 or 24 or 168 ? loaded.UpdateReminderHours : 24;
            return loaded;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or JsonException)
        {
            error = "Không đọc được cài đặt. File hiện có được giữ nguyên: " + ex.Message;
            return new AppSettings();
        }
    }

    public static void Save(AppSettings settings)
    {
        var path = SettingsPath();
        if (File.Exists(path))
            _ = JsonSerializer.Deserialize<AppSettings>(File.ReadAllText(path), JsonOpts)
                ?? throw new JsonException("Settings must be an object.");
        var temp = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            File.WriteAllText(temp, JsonSerializer.Serialize(settings, JsonOpts));
            File.Move(temp, path, overwrite: true);
        }
        finally { if (File.Exists(temp)) File.Delete(temp); }
    }
}
