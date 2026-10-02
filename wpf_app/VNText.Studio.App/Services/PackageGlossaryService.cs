using System.IO;
using System.Text;
using System.Text.Json;

namespace VNText.Studio.App.Services;

public static class PackageGlossaryService
{
    public static string ResolvePath(string? csvPath)
    {
        var path = (csvPath ?? "").Trim().Trim('"');
        return string.IsNullOrWhiteSpace(path)
            ? ""
            : Path.Combine(Path.GetDirectoryName(path) ?? "", ".mt", "glossary.json");
    }

    public static Dictionary<string, string> Load(string? csvPath)
    {
        var path = ResolvePath(csvPath);
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            return new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        try
        {
            using var doc = JsonDocument.Parse(File.ReadAllText(path, Encoding.UTF8));
            if (doc.RootElement.ValueKind != JsonValueKind.Object)
                return new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (var item in doc.RootElement.EnumerateObject())
            {
                var value = item.Value.GetString();
                if (!string.IsNullOrWhiteSpace(item.Name) && !string.IsNullOrWhiteSpace(value))
                    result[item.Name.Trim()] = value.Trim();
            }
            return result;
        }
        catch
        {
            return new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        }
    }

    public static void Save(string? csvPath, IReadOnlyDictionary<string, string> entries)
    {
        var path = ResolvePath(csvPath);
        if (string.IsNullOrWhiteSpace(path))
            throw new InvalidOperationException("Chưa chọn CSV để lưu glossary.");
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var tmp = path + ".tmp";
        var json = JsonSerializer.Serialize(entries.OrderBy(x => x.Key, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(x => x.Key, x => x.Value), new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(tmp, json + Environment.NewLine, new UTF8Encoding(false));
        File.Move(tmp, path, overwrite: true);
    }
}
