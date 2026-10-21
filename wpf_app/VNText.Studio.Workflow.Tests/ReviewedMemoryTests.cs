using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private static void ReviewedMemory_ExplicitSelectionCancelAndState()
    {
        var language = UiText.Language;
        try
        {
            UiText.SetLanguage("en");
            AssertEqual("Confirm reviewed translations", UiText.Translate("Xác nhận đã duyệt"));
            AssertEqual("Source:", UiText.Translate("Nguồn:"));
            AssertEqual("Cancel", UiText.Translate("Hủy"));
            AssertEqual("Selected rows: 1.", string.Format(UiText.Translate("{0} dòng đã chọn."), 1));
            AssertEqual("Selected rows: 2.", string.Format(UiText.Translate("{0} dòng đã chọn."), 2));
            AssertEqual("Approved rows: 1 for reuse in the current package.", string.Format(UiText.Translate("Đã duyệt {0} dòng để dùng trong gói hiện tại."), 1));
            UiText.SetLanguage("vi");
            AssertEqual("Xác nhận đã duyệt", UiText.Translate("Xác nhận đã duyệt"));
        }
        finally { UiText.SetLanguage(language); }
        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
        typeof(MainViewModel).GetProperty(nameof(vm.CsvEditorPath))!.SetValue(vm, "fixture/translation.csv");
        var selected = new CsvEditorRow { Key = "reviewed" };
        vm.UpdateCsvEditorSelection(new[] { selected });
        var requests = new List<string?>();
        vm.ReviewMemoryRequest = (path, keys, token) =>
        {
            AssertEqual("fixture/translation.csv", path);
            AssertEqual(1, keys.Count); AssertEqual("reviewed", keys[0]);
            requests.Add(token);
            return new ReviewedMemoryResult(true, null, 1, "preview-token", false, "Exact scope", []);
        };
        vm.ReviewMemoryConfirmation = _ => false;
        AssertTrue(vm.ApproveCsvMemoryCommand.CanExecute(null));
        vm.ApproveCsvMemoryCommand.Execute(null);
        AssertEqual(1, requests.Count); AssertTrue(requests[0] is null);
        requests.Clear(); vm.ReviewMemoryConfirmation = _ => true;
        vm.ApproveCsvMemoryCommand.Execute(null);
        AssertEqual(2, requests.Count); AssertEqual("preview-token", requests[1]);
        requests.Clear();
        vm.ReviewMemoryConfirmation = _ => { vm.UpdateCsvEditorSelection(Array.Empty<CsvEditorRow>()); return true; };
        vm.ApproveCsvMemoryCommand.Execute(null);
        AssertEqual(1, requests.Count);
        AssertFalse(vm.ApproveCsvMemoryCommand.CanExecute(null));
        vm.UpdateCsvEditorSelection(new[] { selected });
        typeof(MainViewModel).GetProperty(nameof(vm.CsvEditorDirty))!.SetValue(vm, true);
        AssertFalse(vm.ApproveCsvMemoryCommand.CanExecute(null));
        requests.Clear(); vm.ApproveCsvMemoryCommand.Execute(null); AssertEqual(0, requests.Count);
    }
}
