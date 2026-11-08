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
        Run("GameCollectionBlocksExtractAndSwitchingToGameClearsBoundary", () =>
        {
            var parent=Path.Combine(TestTempRoot(),"game-collection");
            var game=Path.Combine(parent,"Example");
            foreach(var name in new[]{"game","renpy","lib"}) Directory.CreateDirectory(Path.Combine(game,name));
            File.WriteAllText(Path.Combine(game,"Example.exe"),"fixture");
            using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);
            vm.InputPath=parent;
            AssertFalse(vm.RunExtractCommand.CanExecute(null));
            AssertFalse(vm.AnalyzeInventoryComplete);
            AssertTrue(vm.ExtractStatusText.Contains(game));
            AssertFalse(vm.ExtractStatusText.Contains("Sẵn sàng lấy text"));
            vm.InputPath=game;
            AssertTrue(vm.RunExtractCommand.CanExecute(null));
            AssertFalse(vm.ExtractStatusText.Contains("thư mục chứa game"));
        }, failures);
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
            foreach(var (id,task) in new[]{("res-1","resources"),("tr-1","translate"),("pa-1","patch"),("img-1","image_batch"),("inv-1","image_inventory")})
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
            AssertTrue(vm.JournalStore.Files().Any(f=>vm.JournalStore.Read(f).Contains("foreign-resources")));   // the sidebar journal keeps the general audit copy
        }, failures);
        Run("AutoAnalyzeRunsAreWrittenToTheExtractJournalWithSummaryAndStaleGuards", () =>
        {
            ResetExtractRuns();
            var root=Path.Combine(TestTempRoot(),"analyze-journal-"+Guid.NewGuid().ToString("N"));
            var a=Path.Combine(root,"A"); var b=Path.Combine(root,"B");
            Directory.CreateDirectory(Path.Combine(a,"game")); Directory.CreateDirectory(Path.Combine(b,"game"));
            try
            {
                File.WriteAllText(Path.Combine(a,"game","a.rpy"),"label start:\n    return\n");
                File.WriteAllText(Path.Combine(b,"game","b.rpy"),"label start:\n    return\n");
                File.WriteAllText(Path.Combine(a,"unity_analysis.json"),"""
                    {"inventory_complete": true, "unity": {"status": "DETECTED"},
                     "summary": {"resource_count": 30, "unknown_resources": 0, "scan_error_count": 0},
                     "coverage": {"text_candidates": 30, "patchable_text": 0, "extract_only_text": 0, "review_required": 0, "unsupported": 0},
                     "scan_errors": []}
                    """);
                using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false){InputPath=a,OutputPath=a};
                // success: START, a step, result and the final status all land in the SAME journal; the summary names the engine and does not claim patchability
                vm.TestBeginTaskLog("an-ok","analyze"); vm.TestMarkAnalyzeStarted();
                vm.TestHandleWorkerEvent(new WorkerEvent{Type="progress",Id="an-ok",Done=2,Total=10,Step="scan",Item="item-ok"});
                AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("Bắt đầu")));
                AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("item-ok")));
                vm.TestSimulateTaskComplete("analyze",new WorkerEvent{Type="complete",Id="an-ok",Ok=true,Complete=true});
                AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("Đã phân tích")));
                AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("Engine")));
                AssertEqual("Phân tích xong",vm.ExtractRuns[0].Status);
                AssertFalse(vm.AnalyzeBusy);
                AssertTrue(vm.AnalyzeNextActionText.Contains("Đã nhận diện",StringComparison.Ordinal));
                AssertTrue(vm.AnalyzeNextActionText.Contains("chưa xác minh khả năng tạo patch",StringComparison.Ordinal));
                AssertEqual(1,vm.ExtractRuns.Count);
                vm.TestMarkTaskTerminal("an-ok");
                AssertTrue(ReadShared(vm.ExtractRuns[0].FilePath).Any(s=>s.Contains("item-ok")));        // durable file, same as extraction runs

                // A -> B while a run is live: the running result is discarded, never shown for B, and the discard is journaled once
                vm.InputPath=a; vm.OutputPath=a;
                vm.TestBeginTaskLog("an-stale","analyze"); vm.TestMarkAnalyzeStarted(); vm.TestSetActiveTask("an-stale","analyze");
                AssertTrue(vm.AnalyzeBusy);
                vm.InputPath=b; vm.OutputPath=b;
                AssertEqual(1,vm.ExtractLogLines.Count(s=>s.Contains("Đầu vào đã đổi")));
                vm.TestHandleWorkerEvent(new WorkerEvent{Type="complete",Id="an-stale",Ok=true,Complete=true});
                AssertEqual("Đã bỏ kết quả cũ",vm.ExtractRuns[0].Status);
                AssertEqual(0,vm.AnalyzeResourceCount);
                AssertFalse(vm.AnalyzeNextActionText.Contains("Đã nhận diện",StringComparison.Ordinal));
                AssertEqual(2,vm.ExtractRuns.Count);                                                      // history kept, nothing cleared twice
                AssertTrue(ReadShared(vm.ExtractRuns[1].FilePath).Any(s=>s.Contains("item-ok")||s.Contains("Đã phân tích")));

                // error: the reason is journaled, the run ends as an error and the summary says analysis did not finish
                vm.InputPath=a; vm.OutputPath=a;
                File.Delete(Path.Combine(a,"unity_analysis.json"));
                vm.TestBeginTaskLog("an-err","analyze"); vm.TestMarkAnalyzeStarted();
                vm.TestSimulateTaskComplete("analyze",new WorkerEvent{Type="complete",Id="an-err",Ok=false,Error="analyzer exploded"});
                AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("analyzer exploded")));
                AssertEqual("Lỗi",vm.ExtractRuns[0].Status);
                AssertTrue(vm.AnalyzeNextActionText.Contains("Phân tích không hoàn tất",StringComparison.Ordinal));
                vm.TestMarkTaskTerminal("an-err");

                // cancel: journaled, no result kept
                vm.TestBeginTaskLog("an-cancel","analyze"); vm.TestMarkAnalyzeStarted();
                vm.TestSimulateTaskComplete("analyze",new WorkerEvent{Type="complete",Id="an-cancel",Ok=false,Error="cancelled"});
                AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("Đã hủy phân tích game")));
                AssertEqual("Đã hủy",vm.ExtractRuns[0].Status);
                AssertTrue(vm.AnalyzeNextActionText.Contains("Đã hủy phân tích",StringComparison.Ordinal));
                AssertEqual(0,vm.AnalyzeResourceCount);
                vm.TestMarkTaskTerminal("an-cancel");
                AssertTrue(vm.ExtractRuns.Count>=4);
            }
            finally { Directory.Delete(root,true); }
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
            vm.TestHandleWorkerEvent(new WorkerEvent {Type="complete",Id="ext-warn",Ok=false,Complete=false,ExtractStatus="PARTIAL",Severity="warning",PatchScope="VERIFIED_MAIN_SUBSET",ReviewOnly=8,
                Error="Đã lấy xong text tĩnh nhưng chưa đầy đủ: Mã .rpy trong archive đã được khôi phục; 3 biểu thức động chỉ có giá trị lúc chạy game."});
            AssertTrue(vm.HasPersistentError);                                       // persistent and readable, not just a toast
            AssertTrue(vm.PersistentErrorIsWarning);
            AssertFalse(vm.PersistentErrorHeading.StartsWith("Lỗi",StringComparison.Ordinal));
            AssertTrue(vm.PersistentErrorHeading.StartsWith("Cảnh báo",StringComparison.Ordinal));
            AssertTrue(vm.PersistentErrorText.Contains("biểu thức động"));
            AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("[cảnh báo]")&&s.Contains("biểu thức động")));   // the same text sits in the inline journal
            AssertFalse(vm.ExtractLogLines.Any(s=>s.Contains("[lỗi]")));
            AssertFalse(vm.ExtractLogLines.Any(s=>s.Contains("Đã dừng") || s.Contains("— Lỗi —")));
            AssertTrue(vm.ExtractLogLines.Last().Contains("Lấy text một phần"));
            AssertTrue(vm.StepStatusLine.Contains("biểu thức động"));
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
            AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("Đã dừng")));
            AssertTrue(vm.ExtractLogLines.Last().Contains("Lỗi"));
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
        Console.WriteLine($"Resource flow checks: {13-failures.Count}/13 PASS");
        return failures.Count==0?0:1;
    }
}
