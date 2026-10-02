using System.IO;
using System.Text;

namespace VNText.Studio.App.Services;

public sealed record CsvValidationResult(
    bool Ok,
    string Message,
    int TotalRows,
    int TranslatedRows,
    string CsvPath,
    string? ManifestPath);

public static class CsvPackageValidator
{
    public static CsvValidationResult Validate(string? csvPath)
    {
        var path = (csvPath ?? "").Trim().Trim('"');
        if (string.IsNullOrEmpty(path))
            return Fail("", "Chưa chọn translation.csv");

        if (!File.Exists(path))
            return Fail(path, "File không tồn tại");

        if (!string.Equals(Path.GetExtension(path), ".csv", StringComparison.OrdinalIgnoreCase))
            return Fail(path, "Phải là file .csv");

        var dir = Path.GetDirectoryName(path) ?? "";
        var manifest = Path.Combine(dir, "manifest.json");
        if (!File.Exists(manifest))
            return Fail(path, "Thiếu manifest.json cùng thư mục với translation.csv");

        try
        {
            using var reader = new StreamReader(path, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
            using var records = CsvFieldReader.ReadRecords(reader).GetEnumerator();
            if (!records.MoveNext() ||
                (records.Current.Length == 1 && string.IsNullOrWhiteSpace(records.Current[0])))
                return Fail(path, "CSV trống hoặc thiếu header");

            var cols = records.Current;
            var keyIdx = IndexOf(cols, "key");
            var srcIdx = IndexOf(cols, "source_text");
            var transIdx = IndexOf(cols, "translation", "translated_text");
            if (keyIdx < 0 || srcIdx < 0 || transIdx < 0)
                return Fail(path, "Header thiếu cột bắt buộc: key, source_text, translation");

            var total = 0;
            var translated = 0;
            while (records.MoveNext())
            {
                var parts = records.Current;
                if (parts.Length == 1 && string.IsNullOrWhiteSpace(parts[0]))
                    continue;
                total++;
                if (transIdx < parts.Length && !string.IsNullOrWhiteSpace(parts[transIdx]))
                    translated++;
            }

            if (total == 0)
                return Fail(path, "CSV không có dòng dữ liệu");

            if (translated == 0)
                return Fail(path, $"CSV hợp lệ nhưng chưa có bản dịch (0/{total} dòng)");

            return new CsvValidationResult(
                true,
                $"Hợp lệ — {translated}/{total} dòng có translation",
                total,
                translated,
                path,
                manifest);
        }
        catch (Exception ex)
        {
            return Fail(path, $"Không đọc được CSV: {ex.Message}");
        }
    }

    public static CsvValidationResult ValidatePackageDir(string outputPath)
    {
        var package = WorkflowStatus.ResolvePackageDir(outputPath);
        if (string.IsNullOrEmpty(package))
            return Fail("", "Chưa chọn thư mục xuất");
        return Validate(Path.Combine(package, "translation.csv"));
    }

    private static int IndexOf(string[] cols, params string[] names)
    {
        for (var i = 0; i < cols.Length; i++)
        {
            var name = cols[i].Trim();
            if (names.Any(n => string.Equals(n, name, StringComparison.OrdinalIgnoreCase)))
                return i;
        }
        return -1;
    }

    private static CsvValidationResult Fail(string csvPath, string message) =>
        new(false, message, 0, 0, csvPath, null);
}
