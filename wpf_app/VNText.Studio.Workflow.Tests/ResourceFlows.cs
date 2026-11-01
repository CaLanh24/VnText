using System.IO;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private static void ResetExtractRuns()
    {
        var runs=Path.Combine(WorkerPaths.AppDataRoot(),"extract-runs");
        if(Directory.Exists(runs)) Directory.Delete(runs,true);
    }
    private static string[] ReadShared(string path)
    {
        using var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite);
        using var reader=new StreamReader(stream);
        var lines=new List<string>();
        for(var line=reader.ReadLine();line is not null;line=reader.ReadLine()) lines.Add(line);
        return lines.ToArray();
    }
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
        Run("ExtractJournalKeepsEveryLineOfALongRunAndItsError", () =>
        {
            ResetExtractRuns();
            using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);
            vm.TestSetActiveTask("ext-long","extract");
            vm.TestBeginTaskLog("ext-long","extract");
            for(var i=0;i<1500;i++)
            {
                vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="ext-long",Done=i,Total=1500,Step=i<1000?"scan":"image text",Item=$"item-{i}"});
                if(i==750) vm.TestHandleWorkerEvent(new WorkerEvent {Type="log",Id="ext-long",Text="middle-marker plain worker log"});
            }
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="complete",Id="ext-long",Ok=false,Error="SDK failure: provenance\nsecond error line"});
            var lines=vm.ExtractLogLines;
            AssertTrue(lines.Count>1500);                                                   // > 1000 and > 200: nothing evicted
            AssertTrue(lines[0].Contains("Bắt đầu"));                                       // first line still there after the run
            AssertTrue(lines.Any(s=>s.Contains("item-0")&&s.Contains("Mục")));
            AssertTrue(lines.Any(s=>s.Contains("middle-marker")));
            AssertTrue(lines.Any(s=>s.Contains("item-1499")));
            AssertTrue(lines.Any(s=>s.Contains("SDK failure: provenance")));                // the task error stays with the progress
            AssertTrue(lines.Any(s=>s.Contains("second error line")));
            AssertTrue(lines.Count(s=>s.Contains("──"))>=3);                                // labelled phases (scan, image text) and the terminal marker
            AssertTrue(lines[^1].Contains("──"));
            AssertTrue(ReferenceEquals(vm.ExtractLogShown,vm.ExtractLogLines));
            var run=vm.ExtractRuns[0];
            var onDisk=ReadShared(run.FilePath);
            AssertEqual(lines.Count,onDisk.Length);                                         // durable copy is identical and complete
            AssertEqual(lines[0],onDisk[0]);
            AssertEqual(lines[^1],onDisk[^1]);
            vm.TestMarkTaskTerminal("ext-long");
        }, failures);
        Run("OtherTasksNeverEnterTheExtractJournal", () =>
        {
            ResetExtractRuns();
            using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);
            vm.TestBeginTaskLog("ext-live","extract");
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="ext-live",Done=1,Total=10,Step="scan",Item="own-item"});
            var before=vm.ExtractLogLines.Count;
            foreach(var (id,task) in new[]{("an-1","analyze"),("res-1","resources"),("tr-1","translate"),("pa-1","patch"),("img-1","image_batch"),("inv-1","image_inventory")})
            {
                vm.TestBeginTaskLog(id,task);
                vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id=id,Done=3,Total=10,Step="other step",Item="foreign-"+task});
                vm.TestHandleWorkerEvent(new WorkerEvent {Type="log",Id=id,Text="foreign log "+task});
                vm.TestHandleWorkerEvent(new WorkerEvent {Type="error",Id=id,Error="foreign error "+task});
            }
            AssertEqual(before,vm.ExtractLogLines.Count);
            AssertFalse(vm.ExtractLogLines.Any(s=>s.Contains("foreign")));
            AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("own-item")));
            AssertTrue(ReadShared(vm.ExtractRuns[0].FilePath).All(s=>!s.Contains("foreign")));
            AssertTrue(vm.JournalStore.Files().Any(f=>vm.JournalStore.Read(f).Contains("foreign-analyze")));   // the sidebar journal keeps the general audit copy
        }, failures);
        Run("ANewExtractRunKeepsThePreviousHistoryReachableInline", () =>
        {
            ResetExtractRuns();
            using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);
            vm.TestBeginTaskLog("run-a","extract");
            for(var i=0;i<400;i++) vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="run-a",Done=i,Total=400,Item=$"a-item-{i}"});
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="log",Id="run-a",Text="a-error: first run failed"});
            var aCount=vm.ExtractLogLines.Count;
            vm.TestBeginTaskLog("run-b","extract");
            AssertEqual(2,vm.ExtractRuns.Count);
            AssertTrue(vm.ExtractRunSelectorVisible);
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="run-b",Done=1,Total=5,Item="b-item-1"});
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="run-a",Done=399,Total=400,Item="a-late-event"});   // a late event of the old run cannot leak in
            AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("b-item-1")));
            AssertFalse(vm.ExtractLogLines.Any(s=>s.Contains("a-item-")||s.Contains("a-late-event")));
            vm.SelectedExtractRun=vm.ExtractRuns[1];                                         // the previous run, inline
            var shown=vm.ExtractLogShown.Cast<string>().ToList();
            AssertEqual(aCount+1,shown.Count);                                               // + the "interrupted" marker written when run B started
            AssertTrue(shown[^1].Contains("──"));
            AssertTrue(shown[0].Contains("Bắt đầu"));
            AssertTrue(shown.Any(s=>s.Contains("a-item-200")));
            AssertTrue(shown.Any(s=>s.Contains("a-error: first run failed")));
            AssertFalse(shown.Any(s=>s.Contains("b-item-1")));
            vm.SelectedExtractRun=vm.ExtractRuns[0];
            AssertTrue(ReferenceEquals(vm.ExtractLogShown,vm.ExtractLogLines));
            AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("b-item-1")));
            using var reopened=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);      // history survives a restart
            AssertTrue(reopened.ExtractRuns.Count>=2);
            AssertTrue(reopened.ExtractLogShown.Cast<string>().Any(s=>s.Contains("b-item-1")));
        }, failures);
        Run("ExtractJournalAppendCostStaysLinear", () =>
        {
            ResetExtractRuns();
            using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);
            vm.TestBeginTaskLog("ext-perf","extract");
            var watch=System.Diagnostics.Stopwatch.StartNew();
            for(var i=0;i<5000;i++) vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="ext-perf",Done=i,Total=20000,Item=$"p-{i}"});
            var firstBlock=watch.Elapsed.TotalMilliseconds;
            watch.Restart();
            for(var i=5000;i<20000;i++) vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="ext-perf",Done=i,Total=20000,Item=$"p-{i}"});
            var largeBlock=watch.Elapsed.TotalMilliseconds;
            AssertTrue(vm.ExtractLogLines.Count>=20000);
            AssertTrue(largeBlock < firstBlock*6+500);                                     // 3x the events must not cost quadratically more
            AssertTrue(largeBlock < 30000);
        }, failures);
        Run("PartialExtractWithLimitationsIsANeutralPersistentWarningNotARedError", () =>
        {
            ResetExtractRuns();
            using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);
            vm.TestSetActiveTask("ext-warn","extract");
            vm.TestBeginTaskLog("ext-warn","extract");
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="ext-warn",Done=5,Total=10,Step="scan",Item="a"});
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="complete",Id="ext-warn",Ok=false,Complete=false,ExtractStatus="PARTIAL",Severity="warning",ReviewOnly=0,
                Error="Đã lấy xong text tĩnh nhưng chưa đầy đủ: Mã .rpy trong archive đã được khôi phục; 3 biểu thức động chỉ có giá trị lúc chạy game."});
            AssertTrue(vm.HasPersistentError);                                       // persistent and readable, not just a toast
            AssertTrue(vm.PersistentErrorIsWarning);
            AssertFalse(vm.PersistentErrorHeading.StartsWith("Lỗi",StringComparison.Ordinal));
            AssertTrue(vm.PersistentErrorHeading.StartsWith("Cảnh báo",StringComparison.Ordinal));
            AssertTrue(vm.PersistentErrorText.Contains("biểu thức động"));
            AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("[cảnh báo]")&&s.Contains("biểu thức động")));   // the same text sits in the inline journal
            AssertFalse(vm.ExtractLogLines.Any(s=>s.Contains("[lỗi]")));
            vm.TestMarkTaskTerminal("ext-warn");
            vm.AcknowledgePersistentError();
            AssertFalse(vm.HasPersistentError);
        }, failures);
        Run("GenuineExtractFailureBesideAPartialPackageStaysARedError", () =>
        {
            ResetExtractRuns();
            using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);
            vm.TestSetActiveTask("ext-err","extract");
            vm.TestBeginTaskLog("ext-err","extract");
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="complete",Id="ext-err",Ok=false,Complete=false,ExtractStatus="PARTIAL",Severity="error",
                Error="Extract chưa hoàn tất do lỗi discovery/extract: game/broken.rpy:2: malformed"});
            AssertTrue(vm.HasPersistentError);
            AssertFalse(vm.PersistentErrorIsWarning);
            AssertTrue(vm.PersistentErrorHeading.StartsWith("Lỗi",StringComparison.Ordinal));
            AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("[lỗi]")&&s.Contains("malformed")));
            vm.TestMarkTaskTerminal("ext-err");
            // a later clean run of the same task resolves the banner
            vm.TestSetActiveTask("ext-ok","extract");
            vm.TestBeginTaskLog("ext-ok","extract");
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="complete",Id="ext-ok",Ok=true,Complete=true,ExtractStatus="COMPLETE",Severity="ok",Summary="done"});
            AssertFalse(vm.HasPersistentError);
            vm.TestMarkTaskTerminal("ext-ok");
        }, failures);
        Run("WorkerCompleteEventCarriesSeverity", () =>
        {
            var evt=WorkerEvent.FromJson("{\"type\":\"complete\",\"id\":\"x\",\"ok\":false,\"extract_status\":\"PARTIAL\",\"severity\":\"warning\",\"error\":\"limit\"}");
            AssertTrue(evt is not null);
            AssertEqual("warning",evt!.Severity);
            AssertEqual("PARTIAL",evt.ExtractStatus);
        }, failures);
        foreach(var failure in failures) Console.Error.WriteLine(failure);
        Console.WriteLine($"Resource flow checks: {12-failures.Count}/12 PASS");
        return failures.Count==0?0:1;
    }
}
