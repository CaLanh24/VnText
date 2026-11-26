using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

/// <summary>
/// 0.1.37 step guidance (external UX review: a newcomer could not tell the order of the four steps or what to press after one finished).
/// The sidebar numbers the steps 1-4 (Lấy text → Dịch → Sửa bản dịch → Tạo bản Việt hóa), shows a check once a step is done, and a
/// "Tiếp: …→" button on the page header jumps to the next step.  Presentation only: no state of the workflow itself changes here.
/// </summary>
public sealed partial class MainViewModel
{
    public RelayCommand NextStepCommand { get; private set; } = null!;

    private void InitGuide()
    {
        NextStepCommand = new RelayCommand(_ => { var target = NextStepTarget(); if (target is not null) NavigateTab(target); }, _ => !Busy && NextStepTarget() is not null);
        PropertyChanged += (_, e) =>
        {
            if (e.PropertyName is nameof(ExtractStepState) or nameof(TranslateStepState) or nameof(PatchStepState) or nameof(SelectedTab)
                or nameof(Busy) or nameof(ReadyForPatch) or nameof(CsvEditorDirty))
                RaiseGuide();
        };
    }

    private void RaiseGuide()
    {
        Raise(nameof(StepMark1)); Raise(nameof(StepMark2)); Raise(nameof(StepMark3)); Raise(nameof(StepMark4));
        Raise(nameof(NextStepLabel)); Raise(nameof(HasNextStep));
        NextStepCommand?.RaiseCanExecuteChanged();
    }

    private static string Mark(string state, int number) => state == WorkflowStepState.Done ? "✓" : number.ToString();
    public string StepMark1 => Mark(ExtractStepState, 1);
    public string StepMark2 => Mark(TranslateStepState, 2);
    /// <summary>Editing the translation is optional and has no state of its own: it counts as done once the whole chain reached the last step.</summary>
    public string StepMark3 => Mark(PatchStepState, 3);
    public string StepMark4 => Mark(PatchStepState, 4);

    /// <summary>The tab the person should visit next, or null when the current page is not a finished step.</summary>
    internal string? NextStepTarget()
    {
        if (SelectedTab == WorkflowTabs.Extract && ExtractStepState == WorkflowStepState.Done) return WorkflowTabs.Translate;
        if (SelectedTab == WorkflowTabs.Translate && TranslateStepState == WorkflowStepState.Done) return WorkflowTabs.EditCsv;
        if (SelectedTab == WorkflowTabs.EditCsv && ReadyForPatch && !CsvEditorDirty) return WorkflowTabs.Patch;
        return null;
    }

    internal void TestSetSteps(string tab, string extract, string translate, string patch, bool readyForPatch)
    {
        SelectedTab = tab; ExtractStepState = extract; TranslateStepState = translate; PatchStepState = patch; ReadyForPatch = readyForPatch;
        RaiseGuide();
    }

    public bool HasNextStep => NextStepTarget() is not null;

    public string NextStepLabel => NextStepTarget() switch
    {
        WorkflowTabs.Translate => UiText.Translate("Tiếp: Dịch →"),
        WorkflowTabs.EditCsv => UiText.Translate("Tiếp: Sửa bản dịch →"),
        WorkflowTabs.Patch => UiText.Translate("Tiếp: Tạo bản Việt hóa →"),
        _ => "",
    };
}
