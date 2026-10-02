using System.IO;
using System.Text.Json;

namespace VNText.Studio.App.Services;

public sealed class AppSettings
{
    public bool SeparateReview { get; set; } = true;
    public bool OverwriteTranslation { get; set; }
    public bool HumanReviewRequired { get; set; }
    public string ExtractLevel { get; set; } = ExtractLevels.Balanced;
}

public static class AppSettingsStore
{
    private static readonly JsonSerializerOptions JsonOpts = new() { WriteIndented = true };

    public static string SettingsPath()
    {
        return Path.Combine(WorkerPaths.AppDataRoot(), "wpf_settings.json");
    }

    public static AppSettings Load()
    {
        var path = SettingsPath(); // Fail clearly when the selected Release install folder is read-only.
        try
        {
            if (!File.Exists(path))
                return new AppSettings();
            var json = File.ReadAllText(path);
            var loaded = JsonSerializer.Deserialize<AppSettings>(json) ?? new AppSettings();
            loaded.ExtractLevel = ExtractLevels.Normalize(loaded.ExtractLevel);
            return loaded;
        }
        catch
        {
            return new AppSettings();
        }
    }

    public static void Save(AppSettings settings)
    {
        var path = SettingsPath();
        File.WriteAllText(path, JsonSerializer.Serialize(settings, JsonOpts));
    }
}
