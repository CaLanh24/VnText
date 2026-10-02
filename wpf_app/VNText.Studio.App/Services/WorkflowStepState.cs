namespace VNText.Studio.App.Services;

/// <summary>Visual state for a workflow nav step: pending | current | done | running.</summary>
public static class WorkflowStepState
{
    public const string Pending = "pending";
    public const string Current = "current";
    public const string Done = "done";
    public const string Running = "running";
}
