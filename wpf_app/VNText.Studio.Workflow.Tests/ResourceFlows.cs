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
        Run("ResourceProgressAndCancelBelongOnlyToTheResourcesTask", () =>
        {
            using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);
            foreach(var other in new[]{"extract","image_batch","image_extract","analyze"})
            {
                vm.TestSetActiveTask("other-"+other,other);
                vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="other-"+other,Done=23,Total=100,Step="filtering image"});
                AssertFalse(vm.ResourcesActive);
                AssertEqual(0,vm.ResourceProgressPercent);
                AssertEqual("",vm.ResourceProgressText);
                AssertFalse(vm.CancelResourcesCommand.CanExecute(null));
                AssertFalse(vm.DownloadResourcesCommand.CanExecute(null));      // an unrelated task may disable the buttons...
                vm.CancelResourcesCommand.Execute(null);                        // ...but never cancels on their behalf
                AssertFalse(vm.ResourcesActive);
                vm.TestMarkTaskTerminal("other-"+other);
            }
            var statusBefore=vm.ResourceStatus;
            vm.TestSetActiveTask("res-1","resources");
            AssertTrue(vm.ResourcesActive);
            AssertTrue(vm.CancelResourcesCommand.CanExecute(null));
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="res-1",Done=50,Total=100,Step="Tải Ren'Py SDK 8.5.3"});
            AssertTrue(vm.ResourceProgressPercent>0);
            AssertTrue(vm.ResourceProgressText.Length>0);
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="complete",Id="res-1",Ok=false,Error="cancelled"});
            AssertFalse(vm.ResourcesActive);
            AssertFalse(vm.CancelResourcesCommand.CanExecute(null));
            var statusAfter=vm.ResourceStatus;
            AssertTrue(statusAfter!=statusBefore);                                // the resources task owns and wrote its terminal status
            vm.TestSetActiveTask("ext-2","extract");
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="res-1",Done=90,Total=100,Step="stale resources event"});
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="complete",Id="res-1",Ok=true,Summary="stale"});
            AssertFalse(vm.ResourcesActive);
            AssertEqual(statusAfter,vm.ResourceStatus);                           // a stale completion cannot overwrite the finished status
            vm.TestMarkTaskTerminal("ext-2");
        }, failures);
        Run("SeparateReviewIsAlwaysOnEvenForAnOldFalsePreference", () =>
        {
            using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);
            AssertTrue(vm.SeparateReview);
            vm.SeparateReview=false;
            AssertTrue(vm.SeparateReview);
        }, failures);
        foreach(var failure in failures) Console.Error.WriteLine(failure);
        Console.WriteLine($"Resource flow checks: {5-failures.Count}/5 PASS");
        return failures.Count==0?0:1;
    }
}
