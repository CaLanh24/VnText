using System.IO;
using System.Security.Cryptography;
using System.Text.Json;
using System.Windows;
using VNText.Studio.App;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App.Services;

/// <summary>
/// Drives the production WPF ViewModel and PythonWorkerHost through the normal
/// Extract -> Translate -> Patch commands for an external fixture.
/// </summary>
internal static class WpfWorkflowE2eProbe
{
    public static async Task<int> RunAsync(
        MainWindow window,
        string inputPath,
        string outputPath,
        string reportPath,
        string requestedModel = "ct2",
        string modelDir = "",
        string modelRevision = "")
    {
        var model = (requestedModel ?? "").Trim().ToLowerInvariant();
        var report = new Dictionary<string, object?>
        {
            ["input"] = inputPath,
            ["output"] = outputPath,
            ["model"] = model,
            ["requested_model"] = model,
            ["requested_model_dir"] = modelDir,
            ["requested_model_revision"] = modelRevision,
            ["source_sha"] = Environment.GetEnvironmentVariable("VNTEXT_SOURCE_SHA") ?? "unavailable",
            ["steps"] = new List<object>(),
        };

        if (model != "ct2")
        {
            report["ok"] = false;
            report["verdict"] = "MODEL_SELECTION_WIRING_FAILURE";
            report["error"] = $"Unsupported --translation-model: {requestedModel}";
            WriteReport(reportPath, report);
            return 1;
        }

        try
        {
            if (string.IsNullOrWhiteSpace(inputPath) || !Directory.Exists(inputPath))
                throw new DirectoryNotFoundException($"WPF E2E input missing: {inputPath}");
            if (string.IsNullOrWhiteSpace(outputPath))
                throw new ArgumentException("WPF E2E output is required", nameof(outputPath));
            Directory.CreateDirectory(outputPath);

            var vm = await window.Dispatcher.InvokeAsync(() =>
            {
                var value = window.DataContext as MainViewModel
                    ?? throw new InvalidOperationException("MainWindow DataContext is not MainViewModel");
                value.SuppressCompletionNotifications = true;
                value.InputPath = Path.GetFullPath(inputPath);
                value.OutputPath = Path.GetFullPath(outputPath);
                value.ExtractLevel = ExtractLevels.Balanced;
                value.SeparateReview = true;
                value.OverwriteTranslation = false;
                value.TranslationModelDir = modelDir;
                report["effective_model_dir"] = modelDir;
                return value;
            });

            var timeout = ReadTimeout();
            await WaitForWorkerReadyAsync(window, vm, timeout);

            await RunStepAsync(
                window,
                vm,
                "extract",
                vm.RunExtractCommand,
                timeout,
                () => ValidateExtract(outputPath),
                report);
            await RunStepAsync(
                window,
                vm,
                "translate",
                vm.RunTranslateCommand,
                timeout,
                () => ValidateTranslate(outputPath, model, modelRevision),
                report);
            await RunStepAsync(
                window,
                vm,
                "patch",
                vm.RunPatchCommand,
                timeout,
                () => ValidatePatch(outputPath),
                report);

            report["ok"] = true;
            report["verdict"] = "WORKFLOW_PASS_LIMITED";
            report["translation_evidence"] = ReadTranslationEvidence(outputPath, model, modelRevision);
            report["ui_final"] = await SnapshotAsync(window, vm);
            WriteReport(reportPath, report);
            return 0;
        }
        catch (Exception ex)
        {
            report["ok"] = false;
            report["verdict"] = ex.Message.Contains("MODEL_SELECTION_WIRING_FAILURE", StringComparison.Ordinal)
                ? "MODEL_SELECTION_WIRING_FAILURE"
                : "WORKFLOW_BLOCKED";
            report["error"] = ex.ToString();
            if (!string.IsNullOrWhiteSpace(outputPath) && Directory.Exists(outputPath))
            {
                try
                {
                    report["translation_evidence"] = ReadTranslationEvidence(outputPath, model, modelRevision);
                }
                catch (Exception evidenceError)
                {
                    report["translation_evidence_error"] = evidenceError.ToString();
                }
            }
            WriteReport(reportPath, report);
            return 1;
        }
    }

    private static async Task RunStepAsync(
        MainWindow window,
        MainViewModel vm,
        string task,
        RelayCommand command,
        TimeSpan timeout,
        Func<Dictionary<string, object?>> validateOutput,
        Dictionary<string, object?> reportRoot)
    {
        await window.Dispatcher.InvokeAsync(() => command.Execute(null));
        if (!await WaitUntilAsync(window, () => vm.Busy, TimeSpan.FromSeconds(30)))
        {
            throw new InvalidOperationException(
                $"{task} did not start: {JsonSerializer.Serialize(await SnapshotAsync(window, vm))}");
        }

        if (!await WaitUntilAsync(window, () => !vm.Busy, timeout))
        {
            await window.Dispatcher.InvokeAsync(() => vm.CancelCommand.Execute(null));
            throw new TimeoutException($"WPF {task} timed out after {timeout}");
        }

        var state = await SnapshotAsync(window, vm);
        var status = (string)state["status_text"]!;
        if (status.Contains("Lỗi", StringComparison.OrdinalIgnoreCase)
            || status.Contains("error", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException($"WPF {task} failed: {JsonSerializer.Serialize(state)}");
        }

        var result = validateOutput();
        result["task"] = task;
        result["ui"] = state;
        ((List<object>)reportRoot["steps"]!).Add(result);
    }

    private static async Task WaitForWorkerReadyAsync(
        MainWindow window,
        MainViewModel vm,
        TimeSpan timeout)
    {
        var ready = await WaitUntilAsync(
            window,
            () => vm.LogLines.Any(line => line.Contains("worker sẵn sàng", StringComparison.OrdinalIgnoreCase)),
            TimeSpan.FromSeconds(Math.Min(60, Math.Max(10, timeout.TotalSeconds))));
        if (!ready)
            throw new TimeoutException("WPF Python worker did not become ready");
    }

    private static async Task<bool> WaitUntilAsync(
        MainWindow window,
        Func<bool> predicate,
        TimeSpan timeout)
    {
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline)
        {
            var value = await window.Dispatcher.InvokeAsync(predicate);
            if (value)
                return true;
            await Task.Delay(250).ConfigureAwait(false);
        }
        return false;
    }

    private static async Task<Dictionary<string, object?>> SnapshotAsync(
        MainWindow window,
        MainViewModel vm)
    {
        return await window.Dispatcher.InvokeAsync(() => new Dictionary<string, object?>
        {
            ["busy"] = vm.Busy,
            ["status_text"] = vm.StatusText,
            ["progress_percent"] = vm.ProgressPercent,
            ["progress_subtitle"] = vm.ProgressSubtitle,
            ["step_status"] = vm.StepStatusLine,
            ["selected_tab"] = vm.SelectedTab,
        });
    }

    private static Dictionary<string, object?> ValidateExtract(string outputPath)
    {
        var csv = Path.Combine(outputPath, "translation.csv");
        var manifest = Path.Combine(outputPath, "manifest.json");
        if (!File.Exists(csv) || !File.Exists(manifest))
            throw new InvalidDataException("Extract did not produce translation.csv and manifest.json");
        return new Dictionary<string, object?>
        {
            ["translation_csv"] = csv,
            ["manifest"] = manifest,
            ["csv_bytes"] = new FileInfo(csv).Length,
        };
    }

    private static Dictionary<string, object?> ValidateTranslate(
        string outputPath,
        string requestedModel,
        string requestedRevision)
    {
        var evidence = ReadTranslationEvidence(outputPath, requestedModel, requestedRevision);
        var complete = (bool)evidence["complete"]!;
        var pending = (int)evidence["pending"]!;
        var review = (int)evidence["review_only"]!;
        var blocked = (int)evidence["blocked"]!;
        if (!(bool)evidence["status_available"]! || !(bool)evidence["backend_match"]!)
            throw new InvalidDataException(
                $"MODEL_SELECTION_WIRING_FAILURE: {JsonSerializer.Serialize(evidence)}");
        if (!complete || pending != 0 || review != 0 || blocked != 0)
        {
            throw new InvalidDataException(
                $"Translate incomplete: complete={complete}, pending={pending}, review={review}, blocked={blocked}");
        }
        return evidence;
    }

    private static Dictionary<string, object?> ReadTranslationEvidence(
        string outputPath,
        string requestedModel,
        string requestedRevision)
    {
        var statusPath = Path.Combine(outputPath, ".mt", "translate_status.json");
        if (!File.Exists(statusPath))
            return new Dictionary<string, object?>
            {
                ["status_available"] = false,
                ["status_path"] = statusPath,
                ["complete"] = false,
                ["pending"] = 0,
                ["review_only"] = 0,
                ["blocked"] = 0,
                ["translated"] = 0,
                ["backend_match"] = false,
                ["structural"] = new Dictionary<string, object?> { ["status"] = "NOT_PROVEN" },
                ["quality"] = new Dictionary<string, object?> { ["status"] = "NOT_PROVEN" },
                ["semantic"] = new Dictionary<string, object?>
                {
                    ["status"] = "MANUAL_REVIEW_REQUIRED",
                    ["automated"] = false,
                },
            };

        using var doc = JsonDocument.Parse(File.ReadAllText(statusPath));
        var root = doc.RootElement;
        var metadata = root.TryGetProperty("model_metadata", out var metadataElement)
            ? ElementValue(metadataElement)
            : null;
        var actualAdapter = metadataElement.ValueKind == JsonValueKind.Object
            ? StringValue(metadataElement, "adapter_id")
            : "";
        var actualModelId = metadataElement.ValueKind == JsonValueKind.Object
            ? StringValue(metadataElement, "model_id")
            : "";
        var actualModelEngine = metadataElement.ValueKind == JsonValueKind.Object
            ? StringValue(metadataElement, "model_engine")
            : "";
        var actualModelDir = metadataElement.ValueKind == JsonValueKind.Object
            ? StringValue(metadataElement, "model_path")
            : "";
        const string expectedAdapter = "ct2";
        var actualRevision = metadataElement.ValueKind == JsonValueKind.Object
            ? StringValue(metadataElement, "model_revision")
            : "";
        var revisionMatch = string.IsNullOrWhiteSpace(requestedRevision)
            || string.Equals(actualRevision, requestedRevision, StringComparison.Ordinal);
        var backendMatch = string.Equals(actualAdapter, expectedAdapter, StringComparison.Ordinal)
            && revisionMatch;
        var blocker = ReadBlockerEvidence(Path.Combine(outputPath, ".mt", "blocker_inventory.json"));
        return new Dictionary<string, object?>
        {
            ["status_available"] = true,
            ["status_path"] = statusPath,
            ["complete"] = ReadBool(root, "complete"),
            ["pending"] = ReadInt(root, "pending"),
            ["review_only"] = ReadInt(root, "review_only"),
            ["blocked"] = ReadInt(root, "blocked"),
            ["translated"] = ReadInt(root, "translated"),
            ["model_metadata"] = metadata,
            ["actual_adapter_id"] = actualAdapter,
            ["actual_model_id"] = actualModelId,
            ["actual_model_engine"] = actualModelEngine,
            ["actual_model_dir"] = actualModelDir,
            ["actual_model_revision"] = actualRevision,
            ["requested_model_revision_match"] = revisionMatch,
            ["backend_match"] = backendMatch,
            ["provenance_source"] = "translate_status.json",
            ["classifier_policy_hash"] = ReadClassifierPolicyHash(outputPath),
            ["corpus_identity"] = CorpusIdentity(outputPath),
            ["structural"] = blocker["structural"]!,
            ["quality"] = blocker["quality"]!,
            ["semantic"] = new Dictionary<string, object?>
            {
                ["status"] = "MANUAL_REVIEW_REQUIRED",
                ["automated"] = false,
                ["reason"] = "Machine translation QA cannot prove natural meaning.",
            },
        };
    }

    private static Dictionary<string, object?> ReadBlockerEvidence(string path)
    {
        if (!File.Exists(path))
            return new Dictionary<string, object?>
            {
                ["structural"] = new Dictionary<string, object?> { ["status"] = "NOT_PROVEN" },
                ["quality"] = new Dictionary<string, object?> { ["status"] = "NOT_PROVEN" },
            };
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var structural = 0;
        var quality = 0;
        var rows = 0;
        if (doc.RootElement.TryGetProperty("rows", out var rowArray) && rowArray.ValueKind == JsonValueKind.Array)
        {
            foreach (var row in rowArray.EnumerateArray())
            {
                rows++;
                if (!row.TryGetProperty("groups", out var groups) || groups.ValueKind != JsonValueKind.Array)
                    continue;
                foreach (var groupElement in groups.EnumerateArray())
                {
                    var group = groupElement.GetString() ?? "";
                    if (group.Contains("structural", StringComparison.OrdinalIgnoreCase)
                        || group.Contains("placeholder", StringComparison.OrdinalIgnoreCase)
                        || group.Contains("tag", StringComparison.OrdinalIgnoreCase)
                        || group.Contains("newline", StringComparison.OrdinalIgnoreCase)
                        || group.Contains("randpick", StringComparison.OrdinalIgnoreCase)
                        || group.Contains("segment", StringComparison.OrdinalIgnoreCase))
                        structural++;
                    else
                        quality++;
                }
            }
        }
        return new Dictionary<string, object?>
        {
            ["structural"] = new Dictionary<string, object?>
            {
                ["status"] = structural == 0 ? "PASS" : "FAIL",
                ["failures"] = structural,
                ["blocked_rows"] = rows,
            },
            ["quality"] = new Dictionary<string, object?>
            {
                ["status"] = quality == 0 ? "PASS" : "REVIEW_REQUIRED",
                ["failures"] = quality,
                ["blocked_rows"] = rows,
            },
        };
    }

    private static string ReadClassifierPolicyHash(string outputPath)
    {
        var tracePath = Path.Combine(outputPath, ".mt", "trace_export.jsonl");
        if (!File.Exists(tracePath))
            return "";
        foreach (var line in File.ReadLines(tracePath))
        {
            try
            {
                using var doc = JsonDocument.Parse(line);
                if (doc.RootElement.TryGetProperty("payload", out var payload)
                    && payload.TryGetProperty("classifier_v2", out var classifier)
                    && classifier.TryGetProperty("policy_hash", out var hash))
                    return hash.GetString() ?? "";
            }
            catch (JsonException)
            {
                // Keep the report fail-closed; the status/trace path remains evidence.
            }
        }
        return "";
    }

    private static Dictionary<string, object?> CorpusIdentity(string outputPath)
    {
        var manifest = Path.Combine(outputPath, "manifest.json");
        return new Dictionary<string, object?>
        {
            ["manifest_path"] = manifest,
            ["manifest_sha256"] = File.Exists(manifest) ? Sha256(manifest) : "",
        };
    }

    private static object? ElementValue(JsonElement value) => value.ValueKind switch
    {
        JsonValueKind.Object => value.EnumerateObject().ToDictionary(item => item.Name, item => ElementValue(item.Value)),
        JsonValueKind.Array => value.EnumerateArray().Select(ElementValue).ToList(),
        JsonValueKind.String => value.GetString(),
        JsonValueKind.Number when value.TryGetInt64(out var integer) => integer,
        JsonValueKind.Number => value.GetDouble(),
        JsonValueKind.True => true,
        JsonValueKind.False => false,
        _ => null,
    };

    private static string StringValue(JsonElement root, string name) =>
        root.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String
            ? value.GetString() ?? ""
            : "";

    private static bool ReadBool(JsonElement root, string name) =>
        root.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.True;

    private static string Sha256(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static Dictionary<string, object?> ValidatePatch(string outputPath)
    {
        var patchRoot = Path.Combine(outputPath, "COPY_TO_GAME_ROOT");
        var reportPath = Path.Combine(outputPath, "import_report.txt");
        if (!Directory.Exists(patchRoot) || !File.Exists(reportPath))
            throw new InvalidDataException("Patch did not produce COPY_TO_GAME_ROOT/import_report.txt");
        var report = File.ReadAllText(reportPath);
        if (!report.Contains("patch_verification_status: PASS", StringComparison.OrdinalIgnoreCase)
            || !report.Contains("per_target_readback: PASS", StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidDataException("Patch read-back report is not PASS");
        }
        return new Dictionary<string, object?>
        {
            ["patch_root"] = patchRoot,
            ["import_report"] = reportPath,
            ["readback"] = "PASS",
        };
    }

    private static int ReadInt(JsonElement root, string name) =>
        root.TryGetProperty(name, out var value) && value.TryGetInt32(out var result) ? result : 0;

    private static TimeSpan ReadTimeout()
    {
        var raw = Environment.GetEnvironmentVariable("VNTEXT_WPF_E2E_TIMEOUT_SECONDS");
        return int.TryParse(raw, out var seconds) && seconds >= 60
            ? TimeSpan.FromSeconds(seconds)
            : TimeSpan.FromHours(2);
    }

    private static void WriteReport(string path, Dictionary<string, object?> report)
    {
        var full = Path.GetFullPath(path);
        Directory.CreateDirectory(Path.GetDirectoryName(full)!);
        File.WriteAllText(full, JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
    }
}
