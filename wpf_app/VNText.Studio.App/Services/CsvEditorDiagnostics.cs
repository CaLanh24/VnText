using VNText.Studio.App.Models;

namespace VNText.Studio.App.Services;

internal sealed record CsvDuplicateKeyInfo(string Key, IReadOnlyList<int> DataRows);

internal static class CsvEditorDiagnostics
{
    public static IReadOnlyList<CsvDuplicateKeyInfo> FindDuplicateKeys(IReadOnlyList<CsvEditorRow> rows)
    {
        var locations = new Dictionary<string, List<int>>(StringComparer.Ordinal);
        foreach (var row in rows)
        {
            var key = row.Key.Trim();
            if (key.Length == 0)
                continue;

            if (!locations.TryGetValue(key, out var dataRows))
            {
                dataRows = [];
                locations[key] = dataRows;
            }

            // CSV has a header on line 1; Index is the zero-based data-row index.
            dataRows.Add(row.Index + 2);
        }

        return locations
            .Where(pair => pair.Value.Count > 1)
            .OrderBy(pair => pair.Value[0])
            .Select(pair => new CsvDuplicateKeyInfo(pair.Key, pair.Value))
            .ToList();
    }

    public static string FormatDuplicateMessage(IReadOnlyList<CsvDuplicateKeyInfo> duplicates)
    {
        if (duplicates.Count == 0)
            return "";

        var details = duplicates
            .Take(8)
            .Select(item => $"{FormatKey(item.Key)} (dòng dữ liệu {string.Join(", ", item.DataRows)})")
            .ToList();
        if (duplicates.Count > details.Count)
            details.Add($"… và thêm {duplicates.Count - details.Count} key");

        return $"Không thể lưu: phát hiện {duplicates.Count} key trùng. " +
               string.Join("; ", details) + ". Hãy giữ lại một dòng cho mỗi key rồi lưu lại.";
    }

    private static string FormatKey(string key)
    {
        var safe = key.Replace("\r", "\\r").Replace("\n", "\\n");
        return safe.Length <= 80 ? $"key '{safe}'" : $"key '{safe[..80]}…'";
    }
}
