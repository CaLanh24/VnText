using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.Json;

namespace VNText.Studio.App.Services;

public sealed record CsvEditorDocument(
    bool Ok,
    string CsvPath,
    IReadOnlyList<string> Fields,
    IReadOnlyList<Dictionary<string, string>> Rows,
    IReadOnlySet<string> ReviewKeys,
    string? Error = null);

public sealed record CsvEditorSaveResult(bool Ok, string? Error = null, int RowCount = 0);

public sealed record CsvEditorValidateResult(
    bool Ok,
    string Summary,
    int IssueCount,
    IReadOnlyDictionary<string, int> ReasonCounts,
    IReadOnlyDictionary<string, string> IssuesByKey,
    IReadOnlyDictionary<string, string> IssuesDisplayByKey,
    int PatchEligible,
    int PatchBlocked,
    int BatchActionable,
    bool HasWarnings,
    string? Error = null);

public sealed record CsvEditorBatchPreviewResult(
    bool Ok,
    int Count,
    IReadOnlyList<string> Keys,
    string? Error = null);

public sealed record CsvEditorReplacePreviewResult(
    bool Ok,
    int Count,
    int ReplacementCount,
    IReadOnlyList<string> Keys,
    string? Error = null);

public sealed record CsvEditorBatchResult(
    bool Ok,
    int Count,
    string? BackupPath,
    string Summary,
    int PatchEligible,
    int PatchBlocked,
    int BatchActionable,
    IReadOnlyDictionary<string, string> IssuesByKey,
    IReadOnlyDictionary<string, string> IssuesDisplayByKey,
    string? Error = null);

public sealed record CsvEditorReplaceResult(
    bool Ok,
    int Count,
    int ReplacementCount,
    string? BackupPath,
    string Summary,
    int PatchEligible,
    int PatchBlocked,
    int BatchActionable,
    IReadOnlyDictionary<string, string> IssuesByKey,
    IReadOnlyDictionary<string, string> IssuesDisplayByKey,
    string? Error = null);

public static class TranslationCsvEditorService
{
    public static CsvEditorDocument Load(string? csvPath)
    {
        var path = (csvPath ?? "").Trim().Trim('"');
        if (string.IsNullOrEmpty(path))
            return new CsvEditorDocument(false, "", [], [], new HashSet<string>(), "Chưa chọn translation.csv");
        // Native C# parse — avoid Python→JSON megablob (~27k rows) that stalls UI via GC.
        try
        {
            return LoadNative(path);
        }
        catch (Exception ex)
        {
            try
            {
                return ParseDocument(RunPython("load", path, null, null), path);
            }
            catch
            {
                return new CsvEditorDocument(false, path, [], [], new HashSet<string>(), ex.Message);
            }
        }
    }

    private static CsvEditorDocument LoadNative(string path)
    {
        if (!File.Exists(path))
            return new CsvEditorDocument(false, path, [], [], new HashSet<string>(), "File không tồn tại");

        var review = LoadReviewKeys(Path.GetDirectoryName(path) ?? "");
        var rows = new List<Dictionary<string, string>>(capacity: 8192);
        using var reader = new StreamReader(path, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
        using var records = CsvFieldReader.ReadRecords(reader).GetEnumerator();
        if (!records.MoveNext())
            return new CsvEditorDocument(false, path, [], [], review, "CSV trống");

        var fields = records.Current
            .Select(f => f.Trim())
            .Where(f => f.Length > 0)
            .ToList();
        if (fields.Count == 0)
            return new CsvEditorDocument(false, path, [], [], review, "Thiếu header CSV");

        while (records.MoveNext())
            AppendCsvDataRow(rows, fields, records.Current);

        return new CsvEditorDocument(true, path, fields, rows, review);
    }

    private static void AppendCsvDataRow(
        List<Dictionary<string, string>> rows,
        IReadOnlyList<string> fields,
        IReadOnlyList<string> parts)
    {
        if (parts.Count == 0 || parts.All(string.IsNullOrWhiteSpace))
            return;
        var row = new Dictionary<string, string>(fields.Count, StringComparer.OrdinalIgnoreCase);
        for (var i = 0; i < fields.Count; i++)
            row[fields[i]] = i < parts.Count ? parts[i] : "";
        rows.Add(row);
    }

    private static HashSet<string> LoadReviewKeys(string packageDir)
    {
        var keys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (string.IsNullOrWhiteSpace(packageDir))
            return keys;
        var reviewPath = Path.Combine(packageDir, "review_only.csv");
        if (!File.Exists(reviewPath))
            return keys;
        try
        {
            using var reader = new StreamReader(reviewPath, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
            using var records = CsvFieldReader.ReadRecords(reader).GetEnumerator();
            if (!records.MoveNext())
                return keys;
            var cols = records.Current;
            var keyIdx = -1;
            for (var i = 0; i < cols.Length; i++)
            {
                if (string.Equals(cols[i].Trim(), "key", StringComparison.OrdinalIgnoreCase))
                {
                    keyIdx = i;
                    break;
                }
            }
            if (keyIdx < 0)
                return keys;
            while (records.MoveNext())
            {
                var parts = records.Current;
                if (parts.All(string.IsNullOrWhiteSpace))
                    continue;
                if (keyIdx < parts.Length)
                {
                    var key = parts[keyIdx].Trim();
                    if (key.Length > 0)
                        keys.Add(key);
                }
            }
        }
        catch
        {
            /* ignore review_only read errors — validate still uses Python */
        }
        return keys;
    }

    public static CsvEditorSaveResult Save(string csvPath, IReadOnlyList<string> fields, IReadOnlyList<Dictionary<string, string>> rows)
    {
        var payloadPath = WriteTempPayload(fields, rows);
        try
        {
            var json = RunPython("save", csvPath, payloadPath, null);
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;
            if (!root.TryGetProperty("ok", out var okEl) || !okEl.GetBoolean())
            {
                var err = root.TryGetProperty("error", out var errEl) ? errEl.GetString() : "Lưu thất bại";
                return new CsvEditorSaveResult(false, err);
            }
            var count = root.TryGetProperty("row_count", out var cEl) ? cEl.GetInt32() : rows.Count;
            return new CsvEditorSaveResult(true, null, count);
        }
        catch (Exception ex)
        {
            return new CsvEditorSaveResult(false, ex.Message);
        }
        finally
        {
            try { File.Delete(payloadPath); } catch { /* ignore */ }
        }
    }

    public static CsvEditorValidateResult Validate(string csvPath, IReadOnlyList<Dictionary<string, string>>? rows = null)
    {
        string? payloadPath = null;
        try
        {
            if (rows is not null)
                payloadPath = WriteTempPayload([], rows);
            var json = RunPython("validate", csvPath, payloadPath, null);
            return ParseValidate(json);
        }
        catch (Exception ex)
        {
            return new CsvEditorValidateResult(false, ex.Message, 0, new Dictionary<string, int>(), new Dictionary<string, string>(), new Dictionary<string, string>(), 0, 0, 0, false, ex.Message);
        }
        finally
        {
            if (payloadPath is not null)
            {
                try { File.Delete(payloadPath); } catch { /* ignore */ }
            }
        }
    }

    public static CsvEditorBatchPreviewResult PreviewClearBlocked(
        string csvPath,
        IReadOnlyList<string> fields,
        IReadOnlyList<Dictionary<string, string>> rows,
        IReadOnlyList<string>? keys = null)
    {
        return ParseBatchPreview(RunBatch("preview-clear", csvPath, fields, rows, keys, dryRun: false));
    }

    public static CsvEditorBatchResult ClearBlocked(
        string csvPath,
        IReadOnlyList<string> fields,
        IReadOnlyList<Dictionary<string, string>> rows,
        IReadOnlyList<string>? keys = null)
    {
        return ParseBatchResult(RunBatch("clear-blocked", csvPath, fields, rows, keys, dryRun: false));
    }

    public static CsvEditorBatchPreviewResult PreviewRetranslate(
        string csvPath,
        IReadOnlyList<Dictionary<string, string>> rows,
        IReadOnlyList<string>? keys = null)
    {
        return ParseBatchPreview(RunBatch("preview-retranslate", csvPath, [], rows, keys, dryRun: false));
    }

    public static CsvEditorReplacePreviewResult PreviewReplace(
        string csvPath,
        IReadOnlyList<string> fields,
        IReadOnlyList<Dictionary<string, string>> rows,
        string findText,
        string replacement,
        IReadOnlyList<string>? keys = null)
    {
        return ParseReplacePreview(RunReplace("preview-replace", csvPath, fields, rows, findText, replacement, keys, dryRun: true));
    }

    public static CsvEditorReplaceResult ReplaceTranslation(
        string csvPath,
        IReadOnlyList<string> fields,
        IReadOnlyList<Dictionary<string, string>> rows,
        string findText,
        string replacement,
        IReadOnlyList<string>? keys = null)
    {
        return ParseReplaceResult(RunReplace("replace", csvPath, fields, rows, findText, replacement, keys, dryRun: false));
    }

    public static CsvEditorSaveResult Undo(string csvPath, string backupPath)
    {
        try
        {
            var json = RunPython("undo", csvPath, null, null, false, new[] { backupPath });
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;
            var ok = root.TryGetProperty("ok", out var okEl) && okEl.GetBoolean();
            var error = root.TryGetProperty("error", out var errEl) ? errEl.GetString() : null;
            var count = root.TryGetProperty("row_count", out var cEl) ? cEl.GetInt32() : 0;
            return new CsvEditorSaveResult(ok, error, count);
        }
        catch (Exception ex)
        {
            return new CsvEditorSaveResult(false, ex.Message);
        }
    }

    private static CsvEditorValidateResult ParseValidate(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        if (!root.TryGetProperty("ok", out var okEl) || !okEl.GetBoolean())
        {
            var err = root.TryGetProperty("error", out var errEl) ? errEl.GetString() : "Validate thất bại";
            return new CsvEditorValidateResult(false, err ?? "", 0, new Dictionary<string, int>(), new Dictionary<string, string>(), new Dictionary<string, string>(), 0, 0, 0, false, err);
        }
        var counts = ReadStringIntMap(root, "reason_counts");
        var issuesByKey = ReadStringStringMap(root, "issues_by_key");
        if (issuesByKey.Count == 0)
            issuesByKey = ReadIssuesFromArray(root);
        var issuesDisplay = ReadStringStringMap(root, "issues_display");
        var summary = root.TryGetProperty("summary", out var sEl) ? sEl.GetString() ?? "" : "";
        var issueCount = root.TryGetProperty("issue_count", out var icEl) ? icEl.GetInt32() : 0;
        var hasWarnings = root.TryGetProperty("has_warnings", out var hwEl) && hwEl.GetBoolean();
        var eligible = root.TryGetProperty("patch_eligible", out var peEl) ? peEl.GetInt32() : 0;
        var blocked = root.TryGetProperty("patch_blocked", out var pbEl) ? pbEl.GetInt32() : 0;
        var actionable = root.TryGetProperty("batch_actionable", out var baEl) ? baEl.GetInt32() : 0;
        return new CsvEditorValidateResult(true, summary, issueCount, counts, issuesByKey, issuesDisplay, eligible, blocked, actionable, hasWarnings);
    }

    private static Dictionary<string, string> ReadIssuesFromArray(JsonElement root)
    {
        var issues = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (!root.TryGetProperty("issues", out var issuesEl) || issuesEl.ValueKind != JsonValueKind.Array)
            return issues;
        foreach (var item in issuesEl.EnumerateArray())
        {
            var key = item.TryGetProperty("key", out var kEl) ? kEl.GetString() ?? "" : "";
            var reason = item.TryGetProperty("reason", out var rEl) ? rEl.GetString() ?? "" : "";
            if (!string.IsNullOrEmpty(key) && !issues.ContainsKey(key))
                issues[key] = reason;
        }
        return issues;
    }

    private static Dictionary<string, int> ReadStringIntMap(JsonElement root, string name)
    {
        var map = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        if (!root.TryGetProperty(name, out var el) || el.ValueKind != JsonValueKind.Object)
            return map;
        foreach (var prop in el.EnumerateObject())
            if (prop.Value.TryGetInt32(out var n))
                map[prop.Name] = n;
        return map;
    }

    private static Dictionary<string, string> ReadStringStringMap(JsonElement root, string name)
    {
        var map = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (!root.TryGetProperty(name, out var el) || el.ValueKind != JsonValueKind.Object)
            return map;
        foreach (var prop in el.EnumerateObject())
            map[prop.Name] = prop.Value.GetString() ?? "";
        return map;
    }

    private static CsvEditorBatchPreviewResult ParseBatchPreview(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        if (!root.TryGetProperty("ok", out var okEl) || !okEl.GetBoolean())
        {
            var err = root.TryGetProperty("error", out var errEl) ? errEl.GetString() : "Preview thất bại";
            return new CsvEditorBatchPreviewResult(false, 0, [], err);
        }
        var count = root.TryGetProperty("count", out var cEl) ? cEl.GetInt32() : 0;
        var keys = ReadStringArray(root, "keys");
        return new CsvEditorBatchPreviewResult(true, count, keys);
    }

    private static CsvEditorBatchResult ParseBatchResult(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        if (!root.TryGetProperty("ok", out var okEl) || !okEl.GetBoolean())
        {
            var err = root.TryGetProperty("error", out var errEl) ? errEl.GetString() : "Thao tác thất bại";
            return new CsvEditorBatchResult(false, 0, null, err ?? "", 0, 0, 0, new Dictionary<string, string>(), new Dictionary<string, string>(), err);
        }
        var count = root.TryGetProperty("count", out var cEl) ? cEl.GetInt32() : 0;
        var backup = root.TryGetProperty("backup_path", out var bEl) ? bEl.GetString() : null;
        var summary = root.TryGetProperty("summary", out var sEl) ? sEl.GetString() ?? "" : "";
        var eligible = root.TryGetProperty("patch_eligible", out var peEl) ? peEl.GetInt32() : 0;
        var blocked = root.TryGetProperty("patch_blocked", out var pbEl) ? pbEl.GetInt32() : 0;
        var actionable = root.TryGetProperty("batch_actionable", out var baEl) ? baEl.GetInt32() : 0;
        var issuesByKey = ReadStringStringMap(root, "issues_by_key");
        var issuesDisplay = ReadStringStringMap(root, "issues_display");
        return new CsvEditorBatchResult(true, count, backup, summary, eligible, blocked, actionable, issuesByKey, issuesDisplay);
    }

    private static CsvEditorReplacePreviewResult ParseReplacePreview(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        if (!root.TryGetProperty("ok", out var okEl) || !okEl.GetBoolean())
        {
            var err = root.TryGetProperty("error", out var errEl) ? errEl.GetString() : "Preview thay thế thất bại";
            return new CsvEditorReplacePreviewResult(false, 0, 0, [], err);
        }
        var count = root.TryGetProperty("count", out var cEl) ? cEl.GetInt32() : 0;
        var replacements = root.TryGetProperty("replacement_count", out var rEl) ? rEl.GetInt32() : count;
        return new CsvEditorReplacePreviewResult(true, count, replacements, ReadStringArray(root, "keys"));
    }

    private static CsvEditorReplaceResult ParseReplaceResult(string json)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        if (!root.TryGetProperty("ok", out var okEl) || !okEl.GetBoolean())
        {
            var err = root.TryGetProperty("error", out var errEl) ? errEl.GetString() : "Thay thế thất bại";
            return new CsvEditorReplaceResult(false, 0, 0, null, err ?? "", 0, 0, 0,
                new Dictionary<string, string>(), new Dictionary<string, string>(), err);
        }
        var count = root.TryGetProperty("count", out var cEl) ? cEl.GetInt32() : 0;
        var replacements = root.TryGetProperty("replacement_count", out var rEl) ? rEl.GetInt32() : count;
        var backup = root.TryGetProperty("backup_path", out var bEl) ? bEl.GetString() : null;
        var summary = root.TryGetProperty("summary", out var sEl) ? sEl.GetString() ?? "" : "";
        var eligible = root.TryGetProperty("patch_eligible", out var peEl) ? peEl.GetInt32() : 0;
        var blocked = root.TryGetProperty("patch_blocked", out var pbEl) ? pbEl.GetInt32() : 0;
        var actionable = root.TryGetProperty("batch_actionable", out var baEl) ? baEl.GetInt32() : 0;
        return new CsvEditorReplaceResult(true, count, replacements, backup, summary, eligible, blocked, actionable,
            ReadStringStringMap(root, "issues_by_key"), ReadStringStringMap(root, "issues_display"));
    }

    private static List<string> ReadStringArray(JsonElement root, string name)
    {
        var keys = new List<string>();
        if (!root.TryGetProperty(name, out var el) || el.ValueKind != JsonValueKind.Array)
            return keys;
        foreach (var item in el.EnumerateArray())
        {
            var key = item.GetString();
            if (!string.IsNullOrEmpty(key))
                keys.Add(key);
        }
        return keys;
    }

    private static string RunBatch(
        string command,
        string csvPath,
        IReadOnlyList<string> fields,
        IReadOnlyList<Dictionary<string, string>> rows,
        IReadOnlyList<string>? keys,
        bool dryRun)
    {
        string? payloadPath = null;
        string? keysPath = null;
        try
        {
            payloadPath = WriteTempPayload(fields, rows);
            if (keys is { Count: > 0 })
            {
                keysPath = Path.Combine(WorkerPaths.WorkArtifactsRoot(), $"csv_editor_keys_{Guid.NewGuid():N}.json");
                Directory.CreateDirectory(Path.GetDirectoryName(keysPath)!);
                File.WriteAllText(keysPath, JsonSerializer.Serialize(keys), new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
            }
            return RunPython(command, csvPath, payloadPath, keysPath, dryRun);
        }
        finally
        {
            if (payloadPath is not null)
            {
                try { File.Delete(payloadPath); } catch { /* ignore */ }
            }
            if (keysPath is not null)
            {
                try { File.Delete(keysPath); } catch { /* ignore */ }
            }
        }
    }

    private static string RunReplace(
        string command,
        string csvPath,
        IReadOnlyList<string> fields,
        IReadOnlyList<Dictionary<string, string>> rows,
        string findText,
        string replacement,
        IReadOnlyList<string>? keys,
        bool dryRun)
    {
        string? payloadPath = null;
        string? keysPath = null;
        try
        {
            payloadPath = WriteTempPayload(fields, rows);
            if (keys is { Count: > 0 })
            {
                keysPath = Path.Combine(WorkerPaths.WorkArtifactsRoot(), $"csv_editor_keys_{Guid.NewGuid():N}.json");
                Directory.CreateDirectory(Path.GetDirectoryName(keysPath)!);
                File.WriteAllText(keysPath, JsonSerializer.Serialize(keys), new UTF8Encoding(false));
            }
            return RunPython(command, csvPath, payloadPath, keysPath, dryRun,
                new[] { "--find", findText, "--replace", replacement });
        }
        finally
        {
            if (payloadPath is not null)
            {
                try { File.Delete(payloadPath); } catch { /* ignore */ }
            }
            if (keysPath is not null)
            {
                try { File.Delete(keysPath); } catch { /* ignore */ }
            }
        }
    }

    private static CsvEditorDocument ParseDocument(string json, string path)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        if (!root.TryGetProperty("ok", out var okEl) || !okEl.GetBoolean())
        {
            var err = root.TryGetProperty("error", out var errEl) ? errEl.GetString() : "Không đọc được CSV";
            return new CsvEditorDocument(false, path, [], [], new HashSet<string>(), err);
        }
        var fields = new List<string>();
        if (root.TryGetProperty("fields", out var fieldsEl) && fieldsEl.ValueKind == JsonValueKind.Array)
        {
            foreach (var f in fieldsEl.EnumerateArray())
            {
                var name = f.GetString();
                if (!string.IsNullOrEmpty(name))
                    fields.Add(name);
            }
        }
        var rows = new List<Dictionary<string, string>>();
        if (root.TryGetProperty("rows", out var rowsEl) && rowsEl.ValueKind == JsonValueKind.Array)
        {
            foreach (var rowEl in rowsEl.EnumerateArray())
            {
                var row = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                foreach (var prop in rowEl.EnumerateObject())
                    row[prop.Name] = prop.Value.ValueKind == JsonValueKind.Null ? "" : prop.Value.ToString();
                rows.Add(row);
            }
        }
        var review = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (root.TryGetProperty("review_keys", out var rkEl) && rkEl.ValueKind == JsonValueKind.Array)
        {
            foreach (var k in rkEl.EnumerateArray())
            {
                var key = k.GetString();
                if (!string.IsNullOrEmpty(key))
                    review.Add(key);
            }
        }
        return new CsvEditorDocument(true, path, fields, rows, review);
    }

    private static string WriteTempPayload(IReadOnlyList<string> fields, IReadOnlyList<Dictionary<string, string>> rows)
    {
        var dir = WorkerPaths.WorkArtifactsRoot();
        Directory.CreateDirectory(dir);
        var path = Path.Combine(dir, $"csv_editor_payload_{Guid.NewGuid():N}.json");
        var payload = new { fields, rows };
        File.WriteAllText(path, JsonSerializer.Serialize(payload), new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
        return path;
    }

    private static string RunPython(
        string command,
        string csvPath,
        string? payloadPath,
        string? keysPath,
        bool dryRun = false,
        IReadOnlyList<string>? extraArgs = null)
    {
        var args = $"-m vntext.csv_editor_api {command} \"{csvPath}\"";
        if (!string.IsNullOrEmpty(payloadPath))
            args += $" --payload \"{payloadPath}\"";
        if (!string.IsNullOrEmpty(keysPath))
            args += $" --keys \"{keysPath}\"";
        if (dryRun)
            args += " --dry-run";
        if (extraArgs is not null)
        {
            for (var i = 0; i < extraArgs.Count; i++)
                args += $" {QuoteProcessArgument(extraArgs[i])}";
        }

        var psi = new ProcessStartInfo
        {
            FileName = WorkerPaths.PythonExecutable(),
            Arguments = args,
            WorkingDirectory = WorkerPaths.RepoRoot(),
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        psi.Environment["PYTHONUTF8"] = "1";
        psi.Environment["PYTHONIOENCODING"] = "utf-8";

        using var proc = Process.Start(psi) ?? throw new InvalidOperationException("Không khởi chạy được Python");
        var stdout = proc.StandardOutput.ReadToEnd();
        var stderr = proc.StandardError.ReadToEnd();
        proc.WaitForExit(TimeSpan.FromMinutes(30));
        if (string.IsNullOrWhiteSpace(stdout))
            throw new InvalidOperationException(string.IsNullOrWhiteSpace(stderr) ? "CSV editor API không trả output" : stderr.Trim());
        var jsonText = stdout.Trim();
        var start = jsonText.IndexOf('{');
        if (start > 0)
            jsonText = jsonText[start..];
        return jsonText;
    }

    private static string QuoteProcessArgument(string value) =>
        "\"" + (value ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
}
