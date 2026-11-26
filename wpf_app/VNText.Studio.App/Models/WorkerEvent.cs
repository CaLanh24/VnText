using System.Text.Json;

namespace VNText.Studio.App.Models;

public sealed class WorkerEvent
{
    public string Type { get; set; } = "";
    public string Id { get; set; } = "";
    public string State { get; set; } = "";
    public string Text { get; set; } = "";
    public int Done { get; set; }
    public int Total { get; set; }
    public string Step { get; set; } = "";
    public string Item { get; set; } = "";
    public string? Eta { get; set; }
    /// <summary>Whole-task percentage when the worker reports one; Done/Total then describe only the current step.</summary>
    public int? Overall { get; set; }
    public bool Ok { get; set; }
    public bool? Complete { get; set; }
    public bool RenpySdkMissing { get; set; }
    public string ExtractStatus { get; set; } = "";
    public string PatchScope { get; set; } = "";
    /// <summary>"ok" | "warning" (expected limits: PARTIAL review warning) | "error" (a genuine discovery/extract failure); empty from older workers.</summary>
    public string Severity { get; set; } = "";
    public int Pending { get; set; }
    public int ReviewOnly { get; set; }
    public int Blocked { get; set; }
    public int Translated { get; set; }
    public string ImageSummary { get; set; } = "";
    public int ImagePending { get; set; }
    public bool ImageScanPending { get; set; }
    public int Applied { get; set; }
    public int HumanReviewRequiredCount { get; set; }
    /// <summary>"selected_rows" for "Dịch đã chọn"; its per-row outcomes (plain Vietnamese) are in <see cref="SelectedMessages"/>.</summary>
    public string OperationScope { get; set; } = "";
    public List<string> SelectedMessages { get; } = new();
    public string Summary { get; set; } = "";
    public string Error { get; set; } = "";
    public string? DiagnosticPath { get; set; }
    public string? DiagnosticStage { get; set; }
    public string? DiagnosticRootCause { get; set; }
    public int? DiagnosticAffectedCount { get; set; }
    public string? DiagnosticAction { get; set; }
    public string? DiagnosticStatus { get; set; }
    public string? PatchEngine { get; set; }
    public string? PatchDelivery { get; set; }
    public string? PatchPayloadPath { get; set; }
    public string? PatchInstallInstructions { get; set; }

    public static WorkerEvent? FromJson(string line)
    {
        try
        {
            using var doc = JsonDocument.Parse(line);
            var root = doc.RootElement;
            if (!root.TryGetProperty("type", out var typeEl))
                return null;

            var evt = new WorkerEvent { Type = typeEl.GetString() ?? "" };
            if (root.TryGetProperty("id", out var idEl)) evt.Id = idEl.GetString() ?? "";
            if (root.TryGetProperty("state", out var stateEl)) evt.State = stateEl.GetString() ?? "";
            if (root.TryGetProperty("text", out var textEl)) evt.Text = textEl.GetString() ?? "";
            if (root.TryGetProperty("message", out var msgEl)) evt.Error = msgEl.GetString() ?? "";
            if (root.TryGetProperty("done", out var doneEl)) evt.Done = doneEl.GetInt32();
            if (root.TryGetProperty("total", out var totalEl)) evt.Total = totalEl.GetInt32();
            if (root.TryGetProperty("step", out var stepEl)) evt.Step = stepEl.GetString() ?? "";
            if (root.TryGetProperty("item", out var itemEl)) evt.Item = itemEl.GetString() ?? "";
            if (root.TryGetProperty("eta", out var etaEl))
                evt.Eta = etaEl.ValueKind switch
                {
                    JsonValueKind.String => etaEl.GetString(),
                    JsonValueKind.Number when etaEl.TryGetDouble(out var seconds) && double.IsFinite(seconds) && seconds >= 0
                        => seconds.ToString(System.Globalization.CultureInfo.InvariantCulture),
                    _ => null,
                };
            if (root.TryGetProperty("ok", out var okEl)) evt.Ok = okEl.GetBoolean();
            if (root.TryGetProperty("image_summary", out var imageSummary)) evt.ImageSummary = imageSummary.GetString() ?? "";
            if (root.TryGetProperty("image_pending", out var imagePending)) evt.ImagePending = imagePending.GetInt32();
            if (root.TryGetProperty("overall", out var overallEl) && overallEl.TryGetInt32(out var overallPct)) evt.Overall = Math.Clamp(overallPct, 0, 100);
            if (root.TryGetProperty("image_scan_pending", out var imageScanPending) && imageScanPending.ValueKind == JsonValueKind.True) evt.ImageScanPending = true;
            if (root.TryGetProperty("complete", out var compEl)) evt.Complete = compEl.GetBoolean();
            if (root.TryGetProperty("renpy_sdk_missing", out var renpySdkEl)) evt.RenpySdkMissing = renpySdkEl.GetBoolean();
            if (root.TryGetProperty("pending", out var pendEl)) evt.Pending = pendEl.GetInt32();
            if (root.TryGetProperty("review_only", out var revEl)) evt.ReviewOnly = revEl.GetInt32();
            if (root.TryGetProperty("blocked", out var blkEl)) evt.Blocked = blkEl.GetInt32();
            if (root.TryGetProperty("translated", out var trEl)) evt.Translated = trEl.GetInt32();
            if (root.TryGetProperty("applied", out var appliedEl)) evt.Applied = appliedEl.GetInt32();
            if (root.TryGetProperty("human_review_required_count", out var hrEl)) evt.HumanReviewRequiredCount = hrEl.GetInt32();
            if (root.TryGetProperty("operation_scope", out var scopeOpEl) && scopeOpEl.ValueKind == JsonValueKind.String) evt.OperationScope = scopeOpEl.GetString() ?? "";
            if (root.TryGetProperty("selected_outcomes", out var outcomesEl) && outcomesEl.ValueKind == JsonValueKind.Array)
                foreach (var outcome in outcomesEl.EnumerateArray())
                    if (outcome.TryGetProperty("message", out var outcomeMsgEl) && outcomeMsgEl.ValueKind == JsonValueKind.String)
                        evt.SelectedMessages.Add(outcomeMsgEl.GetString() ?? "");
            if (root.TryGetProperty("summary", out var sumEl)) evt.Summary = sumEl.GetString() ?? "";
            if (root.TryGetProperty("extract_status", out var extractEl)) evt.ExtractStatus = extractEl.GetString() ?? "";
            if (root.TryGetProperty("patch_scope", out var scopeEl)) evt.PatchScope = scopeEl.GetString() ?? "";
            if (root.TryGetProperty("severity", out var severityEl)) evt.Severity = severityEl.GetString() ?? "";
            if (root.TryGetProperty("error", out var errEl)) evt.Error = errEl.GetString() ?? "";
            if (root.TryGetProperty("diagnostic_path", out var diagPathEl)) evt.DiagnosticPath = diagPathEl.GetString();
            if (root.TryGetProperty("diagnostic_stage", out var diagStageEl)) evt.DiagnosticStage = diagStageEl.GetString();
            if (root.TryGetProperty("diagnostic_root_cause", out var diagRootEl)) evt.DiagnosticRootCause = diagRootEl.GetString();
            if (root.TryGetProperty("diagnostic_affected_count", out var diagCountEl) && diagCountEl.TryGetInt32(out var diagCount))
                evt.DiagnosticAffectedCount = diagCount;
            if (root.TryGetProperty("diagnostic_action", out var diagActionEl)) evt.DiagnosticAction = diagActionEl.GetString();
            if (root.TryGetProperty("diagnostic_status", out var diagStatusEl)) evt.DiagnosticStatus = diagStatusEl.GetString();
            if (root.TryGetProperty("patch_engine", out var patchEngineEl)) evt.PatchEngine = patchEngineEl.GetString();
            if (root.TryGetProperty("patch_delivery", out var patchDeliveryEl)) evt.PatchDelivery = patchDeliveryEl.GetString();
            if (root.TryGetProperty("patch_payload_path", out var patchPayloadEl)) evt.PatchPayloadPath = patchPayloadEl.GetString();
            if (root.TryGetProperty("patch_install_instructions", out var patchInstructionsEl)) evt.PatchInstallInstructions = patchInstructionsEl.GetString();
            return evt;
        }
        catch
        {
            return null;
        }
    }
}
