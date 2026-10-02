using System.Text.Json;

namespace VNText.Studio.App.Models;

public sealed class WorkerEvent
{
    public string Type { get; set; } = "";
    public string Id { get; set; } = "";
    public string Text { get; set; } = "";
    public int Done { get; set; }
    public int Total { get; set; }
    public string Step { get; set; } = "";
    public string Item { get; set; } = "";
    public string? Eta { get; set; }
    public bool Ok { get; set; }
    public bool? Complete { get; set; }
    public bool RenpySdkMissing { get; set; }
    public int Pending { get; set; }
    public int ReviewOnly { get; set; }
    public int Blocked { get; set; }
    public int Translated { get; set; }
    public int Applied { get; set; }
    public int HumanReviewRequiredCount { get; set; }
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
            if (root.TryGetProperty("text", out var textEl)) evt.Text = textEl.GetString() ?? "";
            if (root.TryGetProperty("message", out var msgEl)) evt.Error = msgEl.GetString() ?? "";
            if (root.TryGetProperty("done", out var doneEl)) evt.Done = doneEl.GetInt32();
            if (root.TryGetProperty("total", out var totalEl)) evt.Total = totalEl.GetInt32();
            if (root.TryGetProperty("step", out var stepEl)) evt.Step = stepEl.GetString() ?? "";
            if (root.TryGetProperty("item", out var itemEl)) evt.Item = itemEl.GetString() ?? "";
            if (root.TryGetProperty("eta", out var etaEl)) evt.Eta = etaEl.GetString();
            if (root.TryGetProperty("ok", out var okEl)) evt.Ok = okEl.GetBoolean();
            if (root.TryGetProperty("complete", out var compEl)) evt.Complete = compEl.GetBoolean();
            if (root.TryGetProperty("renpy_sdk_missing", out var renpySdkEl)) evt.RenpySdkMissing = renpySdkEl.GetBoolean();
            if (root.TryGetProperty("pending", out var pendEl)) evt.Pending = pendEl.GetInt32();
            if (root.TryGetProperty("review_only", out var revEl)) evt.ReviewOnly = revEl.GetInt32();
            if (root.TryGetProperty("blocked", out var blkEl)) evt.Blocked = blkEl.GetInt32();
            if (root.TryGetProperty("translated", out var trEl)) evt.Translated = trEl.GetInt32();
            if (root.TryGetProperty("applied", out var appliedEl)) evt.Applied = appliedEl.GetInt32();
            if (root.TryGetProperty("human_review_required_count", out var hrEl)) evt.HumanReviewRequiredCount = hrEl.GetInt32();
            if (root.TryGetProperty("summary", out var sumEl)) evt.Summary = sumEl.GetString() ?? "";
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
