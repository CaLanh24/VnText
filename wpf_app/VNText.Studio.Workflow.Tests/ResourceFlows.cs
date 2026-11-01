using System.IO;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private static int RunResourceFlows()
    {
        var failures = new List<string>();
        Run("PersistentErrorSurvivesProgressWindowAndRestart", () =>
        {
            using (var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker:false))
            {
                vm.RecordPersistentError("extract", "SDK network failure\nfull diagnostic");
                vm.TestBeginTaskLog("resource-error", "extract");
                vm.TestHandleWorkerEvent(new WorkerEvent {Type="error",Id="resource-error",Error="SDK network failure"});
                for(var i=0;i<230;i++) vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="resource-error",Done=i,Total=230,Step="scan"});
                AssertTrue(vm.HasPersistentError);
                AssertTrue(vm.JournalStore.Files().Any(file=>vm.JournalStore.Read(file).Contains("SDK network failure")));
            }
            using var reopened = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker:false);
            AssertTrue(reopened.PersistentErrorText.Contains("full diagnostic"));
            reopened.AcknowledgePersistentError();
            AssertFalse(reopened.HasPersistentError);
        }, failures);
        Run("JournalKeepsHistoryBeyondThirtyFiles", () =>
        {
            var root=Path.Combine(TestTempRoot(),"history-retention");Directory.CreateDirectory(root);
            try
            {
                var store=new AppJournalStore(root);
                for(var i=0;i<35;i++) File.WriteAllText(store.FilePath($"app.log.2026-01-01.{i:00}"),"old entry "+i);
                store.Append("new error entry");
                AssertTrue(store.Files().Length>=35);
                AssertEqual("old entry 0",store.Read("app.log.2026-01-01.00"));
            }
            finally { Directory.Delete(root,true); }
        }, failures);
        Run("ResourceCommandsWorkWithoutGameAndRespectBusy", () =>
        {
            using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);
            AssertTrue(vm.DownloadResourcesCommand.CanExecute(null));
            vm.OpenResourcesCommand.Execute(null);
            AssertEqual(WorkflowTabs.Settings,vm.SelectedTab);
            AssertEqual(1,vm.SelectedSettingsTab);
            vm.TestSetBusy(true);AssertFalse(vm.DownloadResourcesCommand.CanExecute(null));vm.TestSetBusy(false);
        }, failures);
        foreach(var failure in failures) Console.Error.WriteLine(failure);
        Console.WriteLine($"Resource flow checks: {3-failures.Count}/3 PASS");
        return failures.Count==0?0:1;
    }
}
