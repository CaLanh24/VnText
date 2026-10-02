using System.IO;
using System.Text;
using System.Text.Json;

namespace VNText.Studio.App.Services;

public sealed record WorkflowSnapshot(
    string Current,
    string ExtractState,
    string TranslateState,
    string PatchState,
    string StepStatusLine,
    string HeroTitle,
    string HeroHint,
    string HeroActionLabel,
    bool HasExtract,
    bool HasTranslations,
    bool TranslateComplete,
    bool ReadyForPatch);

public sealed record TranslateProgress(
    bool HasTranslations,
    bool IsComplete,
    int Pending,
    int ReviewOnly,
    int Blocked,
    bool StatusKnown);

public static class WorkflowStatus
{
    public static WorkflowSnapshot Evaluate(string inputPath, string outputPath)
    {
        var hasGame = !string.IsNullOrWhiteSpace(inputPath);
        var package = ResolvePackageDir(outputPath);
        var csvPath = Path.Combine(package, "translation.csv");
        var manifestPath = Path.Combine(package, "manifest.json");
        var patchDir = Path.Combine(package, "Patch_Viet_Hoa");

        var hasExtract = File.Exists(csvPath) && File.Exists(manifestPath);
        var translateProgress = hasExtract
            ? EvaluateTranslateProgress(package)
            : new TranslateProgress(false, false, 0, 0, 0, false);
        var hasTranslate = translateProgress.HasTranslations;
        var translateComplete = translateProgress.IsComplete;
        var hasPatch = Directory.Exists(patchDir) && Directory.EnumerateFileSystemEntries(patchDir).Any();
        var readyForPatch = hasExtract && hasTranslate;

        var extractState = hasExtract ? WorkflowStepState.Done : WorkflowStepState.Pending;
        var translateState = translateComplete
            ? WorkflowStepState.Done
            : hasTranslate
                ? WorkflowStepState.Current
                : WorkflowStepState.Pending;
        var patchState = hasPatch ? WorkflowStepState.Done : WorkflowStepState.Pending;

        string current;
        if (!hasGame || !hasExtract)
        {
            current = "extract";
            extractState = WorkflowStepState.Current;
        }
        else if (!translateComplete)
        {
            current = "translate";
            translateState = WorkflowStepState.Current;
        }
        else if (!hasPatch)
        {
            current = "patch";
            patchState = WorkflowStepState.Current;
        }
        else
        {
            current = "done";
        }

        var stepLine = BuildStepStatusLine(
            current,
            hasGame,
            hasExtract,
            hasTranslate,
            translateComplete,
            translateProgress.Pending,
            translateProgress.ReviewOnly,
            hasPatch,
            translateProgress.Blocked,
            translateProgress.StatusKnown);
        var hero = BuildHero(current, hasGame);

        return new WorkflowSnapshot(
            current,
            extractState,
            translateState,
            patchState,
            stepLine,
            hero.Title,
            hero.Hint,
            hero.Action,
            hasExtract,
            hasTranslate,
            translateComplete,
            readyForPatch);
    }

    public static TranslateProgress EvaluateTranslateProgress(string packageDir)
    {
        var csvPath = Path.Combine(packageDir, "translation.csv");
        var statusPath = Path.Combine(packageDir, ".mt", "translate_status.json");
        if (File.Exists(statusPath))
        {
            try
            {
                using var doc = JsonDocument.Parse(File.ReadAllText(statusPath));
                var root = doc.RootElement;
                var pending = root.TryGetProperty("pending", out var pendingEl) ? pendingEl.GetInt32() : 0;
                var reviewOnly = root.TryGetProperty("review_only", out var reviewEl) ? reviewEl.GetInt32() : 0;
                var blocked = root.TryGetProperty("blocked", out var blockedEl) ? blockedEl.GetInt32() : 0;
                var complete = root.TryGetProperty("complete", out var completeEl)
                    && completeEl.GetBoolean()
                    && pending == 0
                    && reviewOnly == 0
                    && blocked == 0;
                var translated = root.TryGetProperty("translated", out var trEl) ? trEl.GetInt32() : 0;
                // Prefer status counts — avoid full CSV scan on large Unity packages (UI hang).
                var hasTranslations = translated > 0;
                return new TranslateProgress(hasTranslations, complete, pending, reviewOnly, blocked, true);
            }
            catch
            {
                /* fall through */
            }
        }

        var translationCounts = CountCsvTranslations(csvPath);
        var hasTranslationsFallback = translationCounts.Translated > 0;
        var reviewFallback = CountCsvDataRows(Path.Combine(packageDir, "review_only.csv"));
        var pendingFallback = Math.Max(0, translationCounts.Total - translationCounts.Translated);
        // CSV cells and the review ledger cannot prove package-wide blocked state.
        // Missing or corrupt status is therefore unknown and never complete.
        return new TranslateProgress(hasTranslationsFallback, false, pendingFallback, reviewFallback, 0, false);
    }

    public static string BuildStepStatusLine(
        string current,
        bool hasGame,
        bool hasExtract,
        bool hasTranslate,
        bool translateComplete,
        int pending,
        int reviewOnly,
        bool hasPatch,
        int blocked = 0,
        bool statusKnown = true)
    {
        if (!hasGame)
            return "Bước 1/3: Chọn game — chưa có đường dẫn game / asset";

        if (current == "translate" && hasTranslate && !translateComplete && !statusKnown)
        {
            return $"Bước 2/3: Trạng thái dịch chưa được xác minh — pending {pending}, review {reviewOnly}; chưa thể Patch";
        }

        if (current == "translate" && hasTranslate && !translateComplete)
        {
            return $"Bước 2/3: Dịch một phần — pending {pending}, review {reviewOnly}, blocked {blocked}";
        }

        return current switch
        {
            "extract" when !hasExtract => "Bước 1/3: Lấy text — chưa có translation.csv",
            "translate" => "Bước 2/3: Dịch tự động — cần bản dịch trong translation.csv",
            "patch" when !hasTranslate => "Bước 3/3: Tạo patch — cần translation.csv có bản dịch",
            "patch" => "Bước 3/3: Tạo patch — đóng gói bản dịch",
            "done" => "Hoàn tất — gói dịch và patch đã sẵn sàng",
            _ => "Bước 1/3: Lấy text",
        };
    }

    private static (string Title, string Hint, string Action) BuildHero(string current, bool hasGame)
    {
        return current switch
        {
            "translate" => (
                "Dịch tự động",
                "Dịch offline CTranslate2 + OPUS-MT en→vi (INT8) trên translation.csv.",
                "Dịch tự động"),
            "patch" => (
                "Tạo patch Việt hóa",
                "Đóng gói bản dịch thành patch cài vào game.",
                "Tạo patch"),
            "done" => (
                "Workflow hoàn tất",
                "Gói dịch và patch đã sẵn sàng. Có thể chạy lại bất kỳ bước nào.",
                "Tạo patch"),
            _ when !hasGame => (
                "Chọn thư mục game",
                "Chọn game bên dưới, rồi bấm «Lấy text» để xuất CSV.",
                "Lấy text"),
            _ => (
                "Lấy text từ game",
                "Chọn game bên dưới, rồi bấm «Lấy text» để xuất CSV.",
                "Lấy text"),
        };
    }

    public static string ResolvePackageDir(string outputPath)
    {
        var text = (outputPath ?? "").Trim().Trim('"');
        if (string.IsNullOrEmpty(text))
            return text;
        if (File.Exists(text) && string.Equals(Path.GetExtension(text), ".csv", StringComparison.OrdinalIgnoreCase))
            return Path.GetDirectoryName(text) ?? text;
        return text;
    }

    public static bool HasTranslations(string csvPath)
        => CountCsvTranslations(csvPath).Translated > 0;

    private static (int Total, int Translated) CountCsvTranslations(string csvPath)
    {
        try
        {
            using var reader = new StreamReader(csvPath, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
            using var records = CsvFieldReader.ReadRecords(reader).GetEnumerator();
            if (!records.MoveNext()) return default;

            var cols = records.Current;
            var transIdx = -1;
            for (var i = 0; i < cols.Length; i++)
            {
                var name = cols[i].Trim();
                if (name is "translation" or "translated_text")
                {
                    transIdx = i;
                    break;
                }
            }
            if (transIdx < 0) return default;

            var total = 0;
            var translated = 0;
            while (records.MoveNext())
            {
                var parts = records.Current;
                if (parts.Length == 1 && string.IsNullOrWhiteSpace(parts[0]))
                    continue;
                total++;
                if (parts.Length < cols.Length)
                    continue;
                if (!string.IsNullOrWhiteSpace(parts[transIdx]))
                    translated++;
            }
            return (total, translated);
        }
        catch
        {
            return default;
        }
    }

    private static int CountCsvDataRows(string csvPath)
    {
        if (!File.Exists(csvPath))
            return 0;
        try
        {
            var count = 0;
            using var reader = new StreamReader(csvPath, Encoding.UTF8, detectEncodingFromByteOrderMarks: true);
            using var records = CsvFieldReader.ReadRecords(reader).GetEnumerator();
            if (!records.MoveNext())
                return 0;
            while (records.MoveNext())
            {
                var parts = records.Current;
                if (parts.Length != 1 || !string.IsNullOrWhiteSpace(parts[0]))
                    count++;
            }
            return count;
        }
        catch
        {
            return 0;
        }
    }
}
