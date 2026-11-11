using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private static void CsvEditor_BulkRefusesChangedOpenedRevision()
    {
        var root = Path.Combine(TestTempRoot(), "bulk-cas-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            File.WriteAllText(csv, "key,source_text,translation\r\nk,Hello,Xin chào\r\n", new UTF8Encoding(false));
            var document = TranslationCsvEditorService.Load(csv);
            AssertTrue(document.Ok);
            var rows = document.Rows;
            var foreign = File.ReadAllBytes(csv).Concat(Encoding.UTF8.GetBytes("\r\n")).ToArray();
            File.WriteAllBytes(csv, foreign);
            var result = TranslationCsvEditorService.ReplaceTranslation(csv, document.Fields, rows, "chào", "chúc", expectedSha256: document.SourceSha256);
            AssertFalse(result.Ok);
            AssertTrue(File.ReadAllBytes(csv).SequenceEqual(foreign));
        }
        finally { Directory.Delete(root, true); }
    }


    private static void CsvEditor_RejectedFileKeepsOpenDocumentAndShowsInlineError()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_reject_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var good = Path.Combine(root, "translation.csv");
            File.WriteAllText(good,
                "key,source_text,translation,context,file_path,import_method\r\n" +
                "k1,Hello,Hi,UI:Text,game/data.unity3d,unity_textasset_line\r\n" +
                "k2,Bye,Tam biet,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            File.WriteAllText(Path.Combine(root, "manifest.json"),
                """{"entries":[{"key":"k1","source_text":"Hello"},{"key":"k2","source_text":"Bye"}]}""", Encoding.UTF8);
            var bad = Path.Combine(root, "bad.csv");
            const string badText = "wrong,header\r\nx,y\r\n";
            File.WriteAllText(bad, badText);
            using var worker = new PythonWorkerHost();
            var picker = new FakePathPicker { TranslationCsv = good };
            using var vm = new MainViewModel(picker, worker, startWorker: false);
            vm.OpenCsvEditorFileCommand.Execute(null);
            AssertEqual(2, vm.CsvEditorRows.Count);
            AssertEqual("translation.csv", vm.CsvEditorPathDisplay);
            AssertFalse(vm.HasCsvEditorLoadError);

            picker.TranslationCsv = bad;
            vm.OpenCsvEditorFileCommand.Execute(null);
            // The open document, its title and its rows stay; the rejected file and the reason are shown inline.
            Require(vm.CsvEditorRows.Count == 2, "rows kept: " + vm.CsvEditorRows.Count);
            Require(vm.CsvEditorPathDisplay == "translation.csv", "title kept: " + vm.CsvEditorPathDisplay);
            Require(vm.HasCsvEditorLoadError, "inline error shown");
            Require(vm.CsvEditorLoadError.Contains("bad.csv", StringComparison.Ordinal), "error names the rejected file: " + vm.CsvEditorLoadError);
            Require(vm.CsvEditorLoadError.Contains("translation.csv", StringComparison.Ordinal), "error says which document stays: " + vm.CsvEditorLoadError);
            AssertFalse(vm.CsvEditorLoading);
            AssertEqual(badText, File.ReadAllText(bad));   // never repaired or rewritten

            picker.TranslationCsv = good;
            vm.OpenCsvEditorFileCommand.Execute(null);
            AssertFalse(vm.HasCsvEditorLoadError);
            AssertEqual(2, vm.CsvEditorRows.Count);
        }
        finally
        {
            try { Directory.Delete(root, true); } catch { /* best effort */ }
        }
    }

    private static void CsvEditor_WarningSummaryCountsReasonAndPointsToRows()
    {
        var warnings = new CsvEditorValidateResult(
            true, "3 dòng cần xem lại", 3, new Dictionary<string, int> { ["placeholder_missing"] = 2, ["number_changed"] = 1 },
            new Dictionary<string, string> { ["k1"] = "placeholder_missing", ["k2"] = "placeholder_missing", ["k3"] = "number_changed" },
            new Dictionary<string, string> { ["k1"] = "thiếu {name}", ["k2"] = "thiếu {name}", ["k3"] = "đổi số" },
            2, 0, 0, true);
        var text = MainViewModel.BuildCsvWarningSummary(warnings);
        Require(text.Contains("3 dòng", StringComparison.Ordinal), "count: " + text);
        Require(text.Contains("2× thiếu {name}", StringComparison.Ordinal), "most frequent reason first: " + text);
        Require(text.Contains("Trạng thái", StringComparison.Ordinal), "tells where to look: " + text);
        AssertEqual("", MainViewModel.BuildCsvWarningSummary(warnings with { HasWarnings = false }));   // no warning, no noise
        AssertEqual("", MainViewModel.BuildCsvWarningSummary(warnings with { Ok = false }));
    }

    private static void CsvEditor_ConflictSaveKeepsDurableInlineErrorUntilLoadOrSuccess()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_conflict_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            const string header = "key,source_text,translation,context,file_path,import_method\r\n";
            File.WriteAllText(csv, header + "k1,Hello,Original,UI:Text,game/data.unity3d,unity_textasset_line\r\nk2,Bye,Tam biet,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            File.WriteAllText(Path.Combine(root, "manifest.json"), """{"entries":[{"key":"k1","source_text":"Hello"},{"key":"k2","source_text":"Bye"}]}""", Encoding.UTF8);
            using var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(new FakePathPicker { TranslationCsv = csv }, worker, startWorker: false);
            vm.OpenCsvEditorFileCommand.Execute(null);
            vm.CsvEditorRows[0].Translation = "Bản nháp của tôi";
            vm.OnCsvEditorTranslationChanged(vm.CsvEditorRows[0]);
            AssertTrue(vm.CsvEditorDirty);
            AssertFalse(vm.HasCsvEditorSaveError);

            // a REAL external change: the saved hash no longer matches
            File.WriteAllText(csv, header + "k1,Hello,Chỉnh sửa bên ngoài,UI:Text,game/data.unity3d,unity_textasset_line\r\nk2,Bye,Tam biet,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            var externalBytes = File.ReadAllBytes(csv);

            AssertFalse(vm.SaveCsvEditorAsync().GetAwaiter().GetResult());
            AssertFalse(vm.CsvEditorSaving);
            Require(vm.HasCsvEditorSaveError, "the refusal is shown inline");
            Require(vm.CsvEditorSaveError.StartsWith("Không lưu được:", StringComparison.Ordinal), vm.CsvEditorSaveError);
            Require(vm.CsvEditorSaveError.Contains("Tải lại", StringComparison.Ordinal) && vm.CsvEditorSaveError.Contains("không bị ghi đè", StringComparison.Ordinal), "safe recovery, no forced overwrite: " + vm.CsvEditorSaveError);
            // the getter no longer falls back to the generic text once saving ended
            AssertEqual(vm.CsvEditorSaveError, vm.CsvEditorUserValidationMessage);
            AssertTrue(vm.CsvEditorDirty);
            AssertEqual("Bản nháp của tôi", vm.CsvEditorRows[0].Translation);
            AssertTrue(externalBytes.SequenceEqual(File.ReadAllBytes(csv)));
            var error = vm.CsvEditorSaveError;

            // ordinary edit, filter, tab navigation and a cancelled reload do NOT clear it
            vm.CsvEditorRows[1].Translation = "Sửa thêm";
            vm.OnCsvEditorTranslationChanged(vm.CsvEditorRows[1]);
            AssertEqual(error, vm.CsvEditorSaveError);
            vm.CsvEditorSearch = "Hello";
            AssertEqual(error, vm.CsvEditorSaveError);
            vm.CsvEditorSearch = "";
            vm.SelectedTab = WorkflowTabs.Translate;
            vm.SelectedTab = WorkflowTabs.EditCsv;
            AssertEqual(error, vm.CsvEditorSaveError);
            vm.CsvEditorMessageBox = (_, _, _, _) => MessageBoxResult.Cancel;
            vm.ReloadCsvEditorCommand.Execute(null);
            AssertEqual(error, vm.CsvEditorSaveError);
            AssertTrue(vm.CsvEditorDirty);
            AssertEqual("Bản nháp của tôi", vm.CsvEditorRows[0].Translation);

            // an explicit discard + reload loads the external file: only then does the error go
            vm.CsvEditorMessageBox = (_, _, _, _) => MessageBoxResult.No;
            vm.ReloadCsvEditorCommand.Execute(null);
            AssertFalse(vm.HasCsvEditorSaveError);
            AssertEqual("Chỉnh sửa bên ngoài", vm.CsvEditorRows[0].Translation);
            AssertFalse(vm.CsvEditorDirty);

            // a later successful save keeps it clear, and a new refusal appears again
            vm.CsvEditorRows[0].Translation = "Lưu được";
            vm.OnCsvEditorTranslationChanged(vm.CsvEditorRows[0]);
            AssertTrue(vm.SaveCsvEditorAsync().GetAwaiter().GetResult());
            AssertFalse(vm.HasCsvEditorSaveError);
        }
        finally
        {
            try { Directory.Delete(root, true); } catch { /* best effort */ }
        }
    }

    private static void CsvEditor_RefreshesOnlyACleanMatchingEditorAfterTranslate()
    {
        Exception? failure = null;
        var thread = new Thread(() =>
        {
            var previousContext = SynchronizationContext.Current;
            var dispatcher = Dispatcher.CurrentDispatcher;
            SynchronizationContext.SetSynchronizationContext(new DispatcherSynchronizationContext(dispatcher));
            try { CsvEditorRefreshBody(dispatcher); }
            catch (Exception ex) { failure = ex; }
            finally { SynchronizationContext.SetSynchronizationContext(previousContext); }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        if (failure is not null) throw new InvalidOperationException(failure.Message, failure);
    }

    private static void CsvEditorRefreshBody(Dispatcher dispatcher)
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_csv_refresh_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            string Csv(string translation) =>
                "key,source_text,translation,context,file_path,import_method\r\n" +
                $"k1,Hello,{translation},UI:Text,game/data.unity3d,unity_textasset_line\r\n";
            var csv = Path.Combine(root, "translation.csv");
            File.WriteAllText(Path.Combine(root, "manifest.json"), """{"entries":[{"key":"k1","source_text":"Hello"}]}""", Encoding.UTF8);
            var utf8Bom = new UTF8Encoding(encoderShouldEmitUTF8Identifier: true);
            File.WriteAllText(csv, Csv("Mid-run"), utf8Bom);
            using var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(new FakePathPicker { TranslationCsv = csv }, worker, startWorker: false);
            vm.OpenCsvEditorFileCommand.Execute(null);
            AssertEqual("Mid-run", vm.CsvEditorRows[0].Translation);

            // MT finishes and rewrites the file: the clean editor showing exactly that file follows it.
            File.WriteAllText(csv, Csv("Final"), utf8Bom);
            PumpUntilDone(vm.RefreshCsvEditorAfterTranslateAsync(csv), dispatcher);
            AssertEqual("Final", vm.CsvEditorRows[0].Translation);
            AssertFalse(vm.CsvEditorStaleOnDisk);

            // Nothing changed on disk: no reload and no stale marker.
            PumpUntilDone(vm.RefreshCsvEditorAfterTranslateAsync(csv), dispatcher);
            AssertFalse(vm.CsvEditorStaleOnDisk);

            // A different file than the one the editor shows is never touched.
            var other = Path.Combine(root, "other.csv");
            File.WriteAllText(other, Csv("Other"), utf8Bom);
            File.WriteAllText(csv, Csv("Newer"), utf8Bom);
            PumpUntilDone(vm.RefreshCsvEditorAfterTranslateAsync(other), dispatcher);
            AssertEqual("Final", vm.CsvEditorRows[0].Translation);
            AssertFalse(vm.CsvEditorStaleOnDisk);

            // Dirty editor: the user's unsaved edit survives, the file on disk is not overwritten, the view is marked stale.
            vm.CsvEditorRows[0].Translation = "Bản sửa tay chưa lưu";
            vm.OnCsvEditorTranslationChanged(vm.CsvEditorRows[0]);
            AssertTrue(vm.CsvEditorDirty);
            var diskBefore = File.ReadAllBytes(csv);
            PumpUntilDone(vm.RefreshCsvEditorAfterTranslateAsync(csv), dispatcher);
            AssertEqual("Bản sửa tay chưa lưu", vm.CsvEditorRows[0].Translation);
            AssertTrue(vm.CsvEditorDirty);
            AssertTrue(vm.CsvEditorStaleOnDisk);
            AssertTrue(vm.CsvEditorStatus.Contains("Tải lại", StringComparison.Ordinal));
            AssertTrue(diskBefore.AsSpan().SequenceEqual(File.ReadAllBytes(csv)));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void CsvEditor_BulkOperationsRunOffTheUiThread()
    {
        Exception? failure = null;
        var thread = new Thread(() =>
        {
            var root = Path.Combine(TestTempRoot(), "vntext_wpf_bulk_ui_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            var previousContext = SynchronizationContext.Current;
            var dispatcher = Dispatcher.CurrentDispatcher;
            SynchronizationContext.SetSynchronizationContext(new DispatcherSynchronizationContext(dispatcher));
            try
            {
                var csv = Path.Combine(root, "translation.csv");
                File.WriteAllText(csv,
                    "key,source_text,translation,context,file_path,import_method\r\n" +
                    "k1,Hello,Chào cậu,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                    new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
                File.WriteAllText(Path.Combine(root, "manifest.json"), """{"entries":[{"key":"k1","source_text":"Hello"}]}""", Encoding.UTF8);
                using var worker = new PythonWorkerHost();
                using var vm = new MainViewModel(new FakePathPicker { TranslationCsv = csv }, worker, startWorker: false);
                vm.OpenCsvEditorFileCommand.Execute(null);
                vm.CsvBulkFind = "cậu";
                vm.CsvBulkReplace = "bạn";

                var uiThread = Environment.CurrentManagedThreadId;
                var workThread = -1;
                var started = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
                var release = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
                vm.CsvEditorBackgroundExecutor = async work =>
                {
                    started.TrySetResult(true);
                    await release.Task;
                    return await Task.Run(() => { workThread = Environment.CurrentManagedThreadId; return work(); });
                };

                vm.BulkReplaceCsvCommand.Execute(null);   // must return while the work is still pending
                AssertTrue(started.Task.IsCompleted);
                AssertTrue(vm.CsvEditorSaving);
                AssertTrue(vm.CsvEditorGridReadOnly);
                AssertFalse(vm.BulkReplaceCsvCommand.CanExecute(null));
                AssertFalse(vm.UndoBulkReplaceCsvCommand.CanExecute(null));

                // The UI thread keeps pumping messages while the Python engine call is outstanding.
                var pumped = false;
                var probe = new DispatcherFrame();
                dispatcher.BeginInvoke(DispatcherPriority.Background, new Action(() => { pumped = true; probe.Continue = false; }));
                Dispatcher.PushFrame(probe);
                AssertTrue(pumped);

                release.TrySetResult(true);
                var deadline = DateTime.UtcNow.AddSeconds(60);
                while (vm.CsvEditorSaving && DateTime.UtcNow < deadline)
                {
                    var tick = new DispatcherFrame();
                    dispatcher.BeginInvoke(DispatcherPriority.Background, new Action(() => tick.Continue = false));
                    Dispatcher.PushFrame(tick);
                    Thread.Sleep(20);
                }
                AssertFalse(vm.CsvEditorSaving);
                AssertTrue(workThread > 0 && workThread != uiThread);
                AssertTrue(vm.CsvBulkPreview.Contains("Sẽ thay", StringComparison.Ordinal));
                AssertTrue(vm.CsvBulkCanApply);
                // The preview never writes the CSV.
                AssertTrue(File.ReadAllText(csv).Contains("Chào cậu", StringComparison.Ordinal));
            }
            catch (Exception ex) { failure = ex; }
            finally
            {
                SynchronizationContext.SetSynchronizationContext(previousContext);
                try { Directory.Delete(root, true); } catch (IOException) { }
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        if (failure is not null) throw new InvalidOperationException(failure.Message, failure);
    }

    private static void CsvEditor_BulkPreviewForOldInputsIsDiscarded()
    {
        Exception? failure = null;
        var thread = new Thread(() =>
        {
            var root = Path.Combine(TestTempRoot(), "vntext_wpf_bulk_stamp_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            var previousContext = SynchronizationContext.Current;
            var dispatcher = Dispatcher.CurrentDispatcher;
            SynchronizationContext.SetSynchronizationContext(new DispatcherSynchronizationContext(dispatcher));
            try
            {
                var csv = Path.Combine(root, "translation.csv");
                File.WriteAllText(csv,
                    "key,source_text,translation,context,file_path,import_method\r\n" +
                    "k1,Hello,Chào cậu,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                    new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
                File.WriteAllText(Path.Combine(root, "manifest.json"), """{"entries":[{"key":"k1","source_text":"Hello"}]}""", Encoding.UTF8);
                using var worker = new PythonWorkerHost();
                using var vm = new MainViewModel(new FakePathPicker { TranslationCsv = csv }, worker, startWorker: false);
                vm.OpenCsvEditorFileCommand.Execute(null);
                vm.CsvBulkFind = "cậu";
                vm.CsvBulkReplace = "bạn";
                var started = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
                var release = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
                vm.CsvEditorBackgroundExecutor = async work =>
                {
                    started.TrySetResult(true);
                    await release.Task;
                    return await Task.Run(work);
                };
                vm.BulkReplaceCsvCommand.Execute(null);
                AssertTrue(started.Task.IsCompleted);
                // The find box changes while the engine call for the OLD text is still pending.
                vm.CsvBulkFind = "khác";
                release.TrySetResult(true);
                var deadline = DateTime.UtcNow.AddSeconds(60);
                while (vm.CsvEditorSaving && DateTime.UtcNow < deadline)
                {
                    var tick = new DispatcherFrame();
                    dispatcher.BeginInvoke(DispatcherPriority.Background, new Action(() => tick.Continue = false));
                    Dispatcher.PushFrame(tick);
                    Thread.Sleep(20);
                }
                AssertFalse(vm.CsvEditorSaving);
                // The result for "cậu" must not become the pending preview of "khác".
                AssertFalse(vm.CsvBulkCanApply);
                AssertTrue(vm.CsvBulkPreview.Contains("đã đổi", StringComparison.Ordinal));
                AssertTrue(File.ReadAllText(csv).Contains("Chào cậu", StringComparison.Ordinal));
            }
            catch (Exception ex) { failure = ex; }
            finally
            {
                SynchronizationContext.SetSynchronizationContext(previousContext);
                try { Directory.Delete(root, true); } catch (IOException) { }
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        if (failure is not null) throw new InvalidOperationException(failure.Message, failure);
    }

    private static void CsvEditor_LoadSaveRoundtrip()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            File.WriteAllText(csv,
                "key,source_text,translation,context,file_path,import_method\r\n" +
                "k1,Hello,Hi,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            File.WriteAllText(Path.Combine(root, "manifest.json"),
                """{"entries":[{"key":"k1","source_text":"Hello","file_path":"game/data.unity3d"}]}""",
                Encoding.UTF8);

            var loaded = TranslationCsvEditorService.Load(csv);
            AssertTrue(loaded.Ok);
            AssertEqual(1, loaded.Rows.Count);

            var rows = loaded.Rows.Select(r => new Dictionary<string, string>(r, StringComparer.OrdinalIgnoreCase)).ToList();
            rows[0]["translation"] = "Xin chào";
            var saved = TranslationCsvEditorService.Save(csv, loaded.Fields, rows);
            AssertTrue(saved.Ok);

            var reloaded = TranslationCsvEditorService.Load(csv);
            AssertEqual("Xin chào", reloaded.Rows[0]["translation"]);
            var bytes = File.ReadAllBytes(csv);
            AssertTrue(bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF);
            foreach (var invalid in new[] {
                "key,source_text,translation,translation\nk1,Hello,X,Y\n",
                "key,source_text,translation\nk1,Hello,X,discarded\n",
                "key,source_text,translation\nk1,\"unfinished,X\n" })
            {
                var invalidPath = Path.Combine(root, "invalid.csv");
                File.WriteAllText(invalidPath, invalid);
                AssertFalse(TranslationCsvEditorService.Load(invalidPath).Ok);
                AssertEqual(invalid, File.ReadAllText(invalidPath));
            }
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void CsvEditor_SaveAsyncKeepsDispatcherResponsiveAndCoalesces()
    {
        Exception? failure = null;
        var thread = new Thread(() =>
        {
            try { CsvEditor_SaveAsyncKeepsDispatcherResponsiveAndCoalescesOnSta(); }
            catch (Exception ex) { failure = ex; }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        if (failure is not null)
            throw new InvalidOperationException("STA async save check failed", failure);
    }

    private static void CsvEditor_SaveAsyncKeepsDispatcherResponsiveAndCoalescesOnSta()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_save_async_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var previousContext = SynchronizationContext.Current;
        var dispatcher = Dispatcher.CurrentDispatcher;
        SynchronizationContext.SetSynchronizationContext(new DispatcherSynchronizationContext(dispatcher));
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            File.WriteAllText(csv,
                "key,source_text,translation,context,file_path,import_method\r\n" +
                "k1,Hello,Hi,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            File.WriteAllText(Path.Combine(root, "manifest.json"),
                """{"entries":[{"key":"k1","source_text":"Hello"}]}""", Encoding.UTF8);

            using var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(new FakePathPicker { TranslationCsv = csv }, worker, startWorker: false);
            vm.OpenCsvEditorFileCommand.Execute(null);
            vm.CsvEditorRows[0].Translation = "Bản dịch đã sửa";
            vm.OnCsvEditorTranslationChanged(vm.CsvEditorRows[0]);

            var started = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            var release = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            vm.CsvEditorSaveExecutor = async work =>
            {
                started.TrySetResult(true);
                await release.Task;
                return await Task.Run(work);
            };

            var saveTask = vm.SaveCsvEditorAsync();
            started.Task.GetAwaiter().GetResult();
            AssertTrue(vm.CsvEditorSaving);
            AssertFalse(vm.SaveCsvEditorCommand.CanExecute(null));
            AssertTrue(ReferenceEquals(saveTask, vm.TrySaveCsvEditorForExitAsync()));

            var actionRanDuringSave = false;
            var frame = new DispatcherFrame();
            dispatcher.BeginInvoke(DispatcherPriority.Background, new Action(() =>
            {
                actionRanDuringSave = !saveTask.IsCompleted;
                release.TrySetResult(true);
            }));
            _ = saveTask.ContinueWith(
                _ => dispatcher.BeginInvoke(DispatcherPriority.Send, new Action(() => frame.Continue = false)),
                TaskScheduler.Default);
            Dispatcher.PushFrame(frame);

            AssertTrue(actionRanDuringSave);
            AssertTrue(saveTask.GetAwaiter().GetResult());
            AssertFalse(vm.CsvEditorSaving);
            AssertFalse(vm.CsvEditorDirty);
            AssertEqual("Bản dịch đã sửa", TranslationCsvEditorService.Load(csv).Rows[0]["translation"]);
        }
        finally
        {
            SynchronizationContext.SetSynchronizationContext(previousContext);
            if (Directory.Exists(root))
                Directory.Delete(root, recursive: true);
        }
    }

    private static void CsvEditor_BusyTaskLocksEditingAndRefusesDirectSave()
    {
        Exception? failure = null;
        var thread = new Thread(() =>
        {
            var root = Path.Combine(TestTempRoot(), "vntext_wpf_busy_lock_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            try
            {
                var csv = Path.Combine(root, "translation.csv");
                File.WriteAllText(csv,
                    "key,source_text,translation,context,file_path,import_method\r\n" +
                    "k1,Hello,Hi,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                    new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
                File.WriteAllText(Path.Combine(root, "manifest.json"),
                    """{"entries":[{"key":"k1","source_text":"Hello"}]}""", Encoding.UTF8);
                var before = File.ReadAllBytes(csv);
                using var worker = new PythonWorkerHost();
                using var vm = new MainViewModel(new FakePathPicker { TranslationCsv = csv }, worker, startWorker: false);
                vm.OpenCsvEditorFileCommand.Execute(null);
                AssertFalse(vm.CsvEditorGridReadOnly);
                AssertEqual("", vm.CsvEditorLockText);

                vm.TestSetActiveTask("translate-running", "translate");   // a real task owns the package
                AssertTrue(vm.CsvEditorGridReadOnly);
                AssertTrue(vm.CsvEditorLockText.Contains("tác vụ", StringComparison.Ordinal));
                // Even if an edit slipped through (programmatic path), saving is refused at the entry point.
                vm.CsvEditorRows[0].Translation = "Sửa trong lúc dịch";
                vm.OnCsvEditorTranslationChanged(vm.CsvEditorRows[0]);
                AssertFalse(vm.SaveCsvEditorCommand.CanExecute(null));
                AssertFalse(vm.SaveCsvEditorAsync().GetAwaiter().GetResult());
                AssertFalse(vm.TrySaveCsvEditorForExitAsync().GetAwaiter().GetResult());
                AssertTrue(vm.CsvEditorStatus.Contains("tác vụ", StringComparison.Ordinal));
                AssertEqual(Convert.ToHexString(before), Convert.ToHexString(File.ReadAllBytes(csv)));
                AssertFalse(vm.CsvEditorSaving);

                vm.TestMarkTaskTerminal("translate-running");
                AssertFalse(vm.CsvEditorGridReadOnly);
                AssertTrue(vm.SaveCsvEditorCommand.CanExecute(null));
                AssertTrue(vm.SaveCsvEditorAsync().GetAwaiter().GetResult());
                AssertEqual("Sửa trong lúc dịch", TranslationCsvEditorService.Load(csv).Rows[0]["translation"]);
            }
            catch (Exception ex) { failure = ex; }
            finally { if (Directory.Exists(root)) Directory.Delete(root, recursive: true); }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        if (failure is not null)
            throw new InvalidOperationException("Busy lock check failed", failure);
    }

    private static void CsvEditor_ValidationTextReturnsToFriendlySummaryAfterSave()
    {
        Exception? failure = null;
        var thread = new Thread(() =>
        {
            var root = Path.Combine(TestTempRoot(), "vntext_wpf_friendly_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            var previousContext = SynchronizationContext.Current;
            var dispatcher = Dispatcher.CurrentDispatcher;
            SynchronizationContext.SetSynchronizationContext(new DispatcherSynchronizationContext(dispatcher));
            try
            {
                var csv = Path.Combine(root, "translation.csv");
                File.WriteAllText(csv,
                    "key,source_text,translation,context,file_path,import_method\r\n" +
                    "k1,Hello,Hi,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                    new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
                File.WriteAllText(Path.Combine(root, "manifest.json"),
                    """{"entries":[{"key":"k1","source_text":"Hello"}]}""", Encoding.UTF8);
                using var worker = new PythonWorkerHost();
                using var vm = new MainViewModel(new FakePathPicker { TranslationCsv = csv }, worker, startWorker: false);
                vm.OpenCsvEditorFileCommand.Execute(null);
                vm.CsvEditorRows[0].Translation = "Bản dịch đã sửa";
                vm.OnCsvEditorTranslationChanged(vm.CsvEditorRows[0]);
                var changed = new List<string>();
                vm.PropertyChanged += (_, e) => changed.Add(e.PropertyName ?? "");
                var release = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
                vm.CsvEditorSaveExecutor = async work => { await release.Task; return await Task.Run(work); };
                var save = vm.SaveCsvEditorAsync();
                AssertTrue(vm.CsvEditorSaving);
                AssertTrue(vm.CsvEditorUserValidationMessage.Contains("kiểm tra", StringComparison.OrdinalIgnoreCase));
                release.TrySetResult(true);
                var frame = new DispatcherFrame();
                _ = save.ContinueWith(_ => dispatcher.BeginInvoke(DispatcherPriority.Send, new Action(() => frame.Continue = false)), TaskScheduler.Default);
                Dispatcher.PushFrame(frame);
                AssertTrue(save.GetAwaiter().GetResult());
                AssertFalse(vm.CsvEditorSaving);
                // The saving->false transition must notify the bound user text...
                AssertTrue(changed.Contains(nameof(MainViewModel.CsvEditorUserValidationMessage)));
                // ...and that text is the friendly summary, never the technical validator output.
                var friendly = new[]
                {
                    "Chưa có bản dịch — chuyển sang Dịch tự động để bắt đầu.",
                    "Một số câu cần xem lại trước khi tạo gói. Chọn câu để xem lý do và chỉnh bản dịch.",
                    "Bản dịch được kiểm tra tự động. Bạn có thể chỉnh ngữ cảnh, xưng hô và cách diễn đạt.",
                };
                AssertTrue(friendly.Contains(vm.CsvEditorUserValidationMessage));
                AssertFalse(vm.CsvEditorUserValidationMessage.Contains("Hợp lệ", StringComparison.Ordinal));
                AssertFalse(vm.CsvEditorUserValidationMessage.Contains("placeholder", StringComparison.OrdinalIgnoreCase));
            }
            catch (Exception ex) { failure = ex; }
            finally
            {
                SynchronizationContext.SetSynchronizationContext(previousContext);
                if (Directory.Exists(root)) Directory.Delete(root, recursive: true);
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        if (failure is not null)
            throw new InvalidOperationException("Friendly validation text check failed", failure);
    }

    private static void CsvEditor_SaveExternalEditFailsClosedAndKeepsDirty()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_save_cas_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            File.WriteAllText(csv,
                "key,source_text,translation,context,file_path,import_method\r\n" +
                "k1,Hello,Original,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            File.WriteAllText(Path.Combine(root, "manifest.json"),
                """{"entries":[{"key":"k1","source_text":"Hello"}]}""", Encoding.UTF8);

            using var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(new FakePathPicker { TranslationCsv = csv }, worker, startWorker: false);
            vm.OpenCsvEditorFileCommand.Execute(null);
            vm.CsvEditorRows[0].Translation = "Bản dịch trong editor";
            vm.OnCsvEditorTranslationChanged(vm.CsvEditorRows[0]);
            AssertTrue(vm.CsvEditorDirty);

            File.WriteAllText(csv,
                "key,source_text,translation,context,file_path,import_method\r\n" +
                "k1,Hello,Chỉnh sửa bên ngoài,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            var externalBytes = File.ReadAllBytes(csv);

            AssertFalse(vm.SaveCsvEditorAsync().GetAwaiter().GetResult());
            AssertTrue(vm.CsvEditorDirty);
            AssertTrue(externalBytes.SequenceEqual(File.ReadAllBytes(csv)));
        }
        finally
        {
            Directory.Delete(root, recursive: true);
        }
    }

    private static void CsvEditor_DuplicateKeysReported()
    {
        var rows = new List<CsvEditorRow>
        {
            new() { Index = 0, Key = "same-key" },
            new() { Index = 4, Key = " same-key " },
            new() { Index = 8, Key = "unique-key" },
        };

        var duplicates = CsvEditorDiagnostics.FindDuplicateKeys(rows);
        AssertEqual(1, duplicates.Count);
        AssertEqual("same-key", duplicates[0].Key);
        AssertEqual("2, 6", string.Join(", ", duplicates[0].DataRows));
        var message = CsvEditorDiagnostics.FormatDuplicateMessage(duplicates);
        AssertTrue(message.Contains("key 'same-key'", StringComparison.Ordinal));
        AssertTrue(message.Contains("dòng dữ liệu 2, 6", StringComparison.Ordinal));
    }

    private static void CsvEditor_SearchFiltersRows()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_search_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            File.WriteAllText(csv,
                "key,source_text,translation\r\n" +
                "k1,Escort,Hộ tống\r\n" +
                "k2,Hello,Xin chào\r\n" +
                "k3,Another escort,Đường khác\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            File.WriteAllText(Path.Combine(root, "manifest.json"),
                "{\"entries\":[{\"key\":\"k1\",\"source_text\":\"Escort\"},{\"key\":\"k2\",\"source_text\":\"Hello\"},{\"key\":\"k3\",\"source_text\":\"Another escort\"}]}",
                Encoding.UTF8);

            var picker = new FakePathPicker { TranslationCsv = csv };
            using var worker = new PythonWorkerHost();
            var vm = new MainViewModel(picker, worker, startWorker: false);
            vm.OpenCsvEditorFileCommand.Execute(null);

            AssertEqual(3, vm.CsvEditorRows.Count);
            vm.CsvEditorSearch = "escort";
            AssertEqual(2, vm.CsvEditorVisibleCount);
            vm.CsvEditorSearch = "missing";
            AssertEqual(0, vm.CsvEditorVisibleCount);
            vm.CsvEditorSearch = "";
            AssertEqual(3, vm.CsvEditorVisibleCount);
            vm.CsvEditorRows[1].Translation = "";
            vm.CsvBulkFind = "Hello";
            AssertEqual(1, vm.CsvEditorVisibleCount);
            AssertEqual("Hello", vm.CsvEditorSearch);
            vm.CsvBulkFind = "";
            var original = File.ReadAllBytes(csv);
            vm.CsvEditorRows[0].Translation = "Chưa lưu";
            vm.OnCsvEditorTranslationChanged();
            vm.CsvEditorMessageBox = (_, _, _, _) => MessageBoxResult.Cancel;
            vm.ReloadCsvEditorCommand.Execute(null);
            AssertEqual("Chưa lưu", vm.CsvEditorRows[0].Translation);
            AssertTrue(vm.CsvEditorDirty);
            AssertTrue(original.SequenceEqual(File.ReadAllBytes(csv)));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void CsvEditor_MultilineRecordsRoundtrip()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_multiline_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            File.WriteAllText(csv,
                "key,source_text,translation\r\n" +
                "k1,\"Line one\r\nLine two\",\"Dòng một\r\nDòng hai\"\r\n" +
                "k2,Simple,Đơn giản\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));

            var loaded = TranslationCsvEditorService.Load(csv);
            AssertTrue(loaded.Ok);
            AssertEqual(2, loaded.Rows.Count);
            AssertEqual("Line one\r\nLine two", loaded.Rows[0]["source_text"]);
            AssertEqual("Dòng một\r\nDòng hai", loaded.Rows[0]["translation"]);

            var saved = TranslationCsvEditorService.Save(
                csv,
                loaded.Fields,
                loaded.Rows.Select(row => new Dictionary<string, string>(row, StringComparer.OrdinalIgnoreCase)).ToList());
            if (!saved.Ok)
                throw new InvalidOperationException(saved.Error ?? "multiline save failed");
            var reloaded = TranslationCsvEditorService.Load(csv);
            AssertEqual(2, reloaded.Rows.Count);
            AssertEqual("Dòng một\r\nDòng hai", reloaded.Rows[0]["translation"]);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void CsvEditor_RetranslateSaveFailureKeepsEditsAndStops() =>
        AssertCsvEditorRetranslateDecision(MessageBoxResult.Yes, failSave: true, expectStart: false, expectSaved: false);

    private static void CsvEditor_RetranslateSaveSuccessContinues() =>
        AssertCsvEditorRetranslateDecision(MessageBoxResult.Yes, failSave: false, expectStart: true, expectSaved: true);

    private static void CsvEditor_RetranslateNoContinuesWithoutSaving() =>
        AssertCsvEditorRetranslateDecision(MessageBoxResult.No, failSave: false, expectStart: true, expectSaved: false);

    private static void CsvEditor_RetranslateCancelStopsWithoutSaving() =>
        AssertCsvEditorRetranslateDecision(MessageBoxResult.Cancel, failSave: false, expectStart: false, expectSaved: false);

    private static void CsvEditor_ClearBlockedBackup()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_clear_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            var garbage =
                "Đồng bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
                + "bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán "
                + "bán bán bán bán bán bán bán bán bán bán bán bán lao";
            File.WriteAllText(csv,
                "key,source_text,translation,context,file_path,import_method\r\n"
                + $"k1,Hello,{garbage},UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));

            var loaded = TranslationCsvEditorService.Load(csv);
            AssertTrue(loaded.Ok);
            var rows = loaded.Rows.Select(r => new Dictionary<string, string>(r, StringComparer.OrdinalIgnoreCase)).ToList();
            var preview = TranslationCsvEditorService.PreviewClearBlocked(csv, loaded.Fields, rows, null);
            AssertTrue(preview.Ok);
            AssertEqual(1, preview.Count);

            var cleared = TranslationCsvEditorService.ClearBlocked(csv, loaded.Fields, rows, null);
            AssertTrue(cleared.Ok);
            AssertEqual(1, cleared.Count);
            AssertTrue(!string.IsNullOrWhiteSpace(cleared.BackupPath));
            AssertTrue(File.Exists(cleared.BackupPath!));

            var reloaded = TranslationCsvEditorService.Load(csv);
            AssertEqual("", reloaded.Rows[0]["translation"]);
            AssertEqual("Hello", reloaded.Rows[0]["source_text"]);

            var validation = TranslationCsvEditorService.Validate(csv, reloaded.Rows);
            AssertTrue(validation.Ok);
            AssertEqual(0, validation.PatchBlocked);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

}
