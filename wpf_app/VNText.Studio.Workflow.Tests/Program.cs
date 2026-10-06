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
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static class Program
{
    private static int Main(string[] args)
    {
        var failures = new List<string>();
        if (args.Contains("--full-app-update-only", StringComparer.Ordinal))
        {
            Run("FullAppUpdate_AppliesAddReplaceDeleteAndKeepsDataAndModel", FullAppUpdate_AppliesAddReplaceDeleteAndKeepsDataAndModel, failures);
            Run("FullAppUpdate_HealthFailureRollsBack", FullAppUpdate_HealthFailureRollsBack, failures);
            Run("FullAppUpdate_InterruptedTransactionRecovers", FullAppUpdate_InterruptedTransactionRecovers, failures);
            Run("FullAppUpdate_TamperAndBaselineMismatchFailClosed", FullAppUpdate_TamperAndBaselineMismatchFailClosed, failures);
            Run("FullAppUpdate_GitHubAssetPathSizeAndHashAreBound", FullAppUpdate_GitHubAssetPathSizeAndHashAreBound, failures);
            if (failures.Count == 0)
            {
                Console.WriteLine("Focused full-app updater tests: PASS (5)");
                return 0;
            }
            Console.Error.WriteLine($"Focused full-app updater tests: FAIL ({failures.Count})");
            foreach (var f in failures) Console.Error.WriteLine(" - " + f);
            return 1;
        }
        Run("NoGame_CurrentIsExtract", NoGame_CurrentIsExtract, failures);
        Run("RenpyGameDetector_OnlyShowsForLooseSource", RenpyGameDetector_OnlyShowsForLooseSource, failures);
        Run("RenpySdkOptionsVisibility_FollowsSelectedGame", RenpySdkOptionsVisibility_FollowsSelectedGame, failures);
        Run("AfterExtract_CurrentTranslate", AfterExtract_CurrentTranslate, failures);
        Run("AfterTranslate_CurrentPatch", AfterTranslate_CurrentPatch, failures);
        Run("AfterPatch_CurrentDone", AfterPatch_CurrentDone, failures);
        Run("HasTranslations_ParsesQuotedCsv", HasTranslations_ParsesQuotedCsv, failures);
        Run("CsvValidator_AndWorkflowCountQuotedMultilineRecords", CsvValidator_AndWorkflowCountQuotedMultilineRecords, failures);
        Run("MissingTranslateStatus_PartialCsvStaysIncomplete", MissingTranslateStatus_PartialCsvStaysIncomplete, failures);
        Run("CorruptTranslateStatus_PartialCsvStaysIncomplete", CorruptTranslateStatus_PartialCsvStaysIncomplete, failures);
        Run("ChooseInput_UsesFolderPicker", ChooseInput_UsesFolderPicker, failures);
        Run("ChooseOutput_UsesFolderPicker", ChooseOutput_UsesFolderPicker, failures);
        Run("DropInput_UpdatesWorkflow", DropInput_UpdatesWorkflow, failures);
        Run("PartialTranslateComplete_UpdatesStatus", PartialTranslateComplete_UpdatesStatus, failures);
        Run("HumanReviewRequired_UpdatesStatus", HumanReviewRequired_UpdatesStatus, failures);
        Run("RenpySdkMissing_ReportsPartialExtraction", RenpySdkMissing_ReportsPartialExtraction, failures);
        Run("DiagnosticCompletion_IsVisibleAndActionable", DiagnosticCompletion_IsVisibleAndActionable, failures);
        Run("WorkerEvent_ParsesDiagnosticFields", WorkerEvent_ParsesDiagnosticFields, failures);
        Run("PatchDelivery_RoutesRenPyInstructions", PatchDelivery_RoutesRenPyInstructions, failures);
        Run("PartialPackage_TranslateNotComplete", PartialPackage_TranslateNotComplete, failures);
        Run("BlockedCompletion_IsNotAccepted", BlockedCompletion_IsNotAccepted, failures);
        Run("NavigateTab_ChangesSelectedTab", NavigateTab_ChangesSelectedTab, failures);
        Run("ExtractComplete_NavigatesToTranslate", ExtractComplete_NavigatesToTranslate, failures);
        Run("ExternalCsv_ValidatesReadyForPatch", ExternalCsv_ValidatesReadyForPatch, failures);
        Run("CsvValidator_RejectsEmptyTranslation", CsvValidator_RejectsEmptyTranslation, failures);
        Run("TranslateComplete_NavigatesToPatch", TranslateComplete_NavigatesToPatch, failures);
        Run("ExtractLevel_Persists", ExtractLevel_Persists, failures);
        Run("PatchPreflight_BlocksGarbage", PatchPreflight_BlocksGarbage, failures);
        Run("PatchPreflight_AllowsCleanRow", PatchPreflight_AllowsCleanRow, failures);
        Run("NavigateTab_EditCsv", NavigateTab_EditCsv, failures);
        Run("CsvEditor_SearchFiltersRows", CsvEditor_SearchFiltersRows, failures);
        Run("CsvEditor_LoadSaveRoundtrip", CsvEditor_LoadSaveRoundtrip, failures);
        Run("CsvEditor_MultilineRecordsRoundtrip", CsvEditor_MultilineRecordsRoundtrip, failures);
        Run("CsvEditor_RetranslateSaveFailureKeepsEditsAndStops", CsvEditor_RetranslateSaveFailureKeepsEditsAndStops, failures);
        Run("CsvEditor_RetranslateSaveSuccessContinues", CsvEditor_RetranslateSaveSuccessContinues, failures);
        Run("CsvEditor_RetranslateNoContinuesWithoutSaving", CsvEditor_RetranslateNoContinuesWithoutSaving, failures);
        Run("CsvEditor_RetranslateCancelStopsWithoutSaving", CsvEditor_RetranslateCancelStopsWithoutSaving, failures);
        Run("CsvEditor_DuplicateKeysReported", CsvEditor_DuplicateKeysReported, failures);
        Run("CsvEditor_ClearBlockedBackup", CsvEditor_ClearBlockedBackup, failures);
        Run("Toast_ShowsOnSimulatedComplete", Toast_ShowsOnSimulatedComplete, failures);
        Run("TranslateCsvSelection_PersistsAndBuildsPath", TranslateCsvSelection_PersistsAndBuildsPath, failures);
        Run("TranslateCsvSelection_InvalidKeepsCurrent", TranslateCsvSelection_InvalidKeepsCurrent, failures);
        Run("CompletionNotification_ExactlyOncePerOutcome", CompletionNotification_ExactlyOncePerOutcome, failures);
        Run("ReleaseVerifyRunner_ForwardsReport", ReleaseVerifyRunner_ForwardsReport, failures);
        Run("ReleaseVerifyRunner_ValidatesExactPortablePythonHome", ReleaseVerifyRunner_ValidatesExactPortablePythonHome, failures);
        Run("WorkerPaths_FallsBackFromUnusableArtifactsRoot", WorkerPaths_FallsBackFromUnusableArtifactsRoot, failures);
        Run("SmokeWorker_UsesFreshWorkPath", SmokeWorker_UsesFreshWorkPath, failures);
        Run("SmokeWorker_FindsLegacyPatchOutput", SmokeWorker_FindsLegacyPatchOutput, failures);
        Run("SmokeWorker_IgnoresLegacyWorkPath", SmokeWorker_IgnoresLegacyWorkPath, failures);
        Run("AnalyzeReportReader_ParsesCoverage", AnalyzeReportReader_ParsesCoverage, failures);
        Run("AnalyzeComplete_StaysOnExtractAndShowsEvidence", AnalyzeComplete_StaysOnExtractAndShowsEvidence, failures);
        Run("ReleaseManagedPaths_StayUnderInstallRoot", ReleaseManagedPaths_StayUnderInstallRoot, failures);
        Run("WpfUpdate_VersionOrderRejectsInvalidAndNonIncreasing", WpfUpdate_VersionOrderRejectsInvalidAndNonIncreasing, failures);
        Run("WpfUpdate_ReadsVersionBeyondMaxPath", WpfUpdate_ReadsVersionBeyondMaxPath, failures);
        Run("WpfUpdate_InvalidOfferIsHiddenAndRejected", WpfUpdate_InvalidOfferIsHiddenAndRejected, failures);
        Run("WpfUpdate_FaultThenRetryIgnoresPriorStagingAndBackup", WpfUpdate_FaultThenRetryIgnoresPriorStagingAndBackup, failures);
        Run("FullAppUpdate_AppliesAddReplaceDeleteAndKeepsDataAndModel", FullAppUpdate_AppliesAddReplaceDeleteAndKeepsDataAndModel, failures);
        Run("FullAppUpdate_HealthFailureRollsBack", FullAppUpdate_HealthFailureRollsBack, failures);
        Run("FullAppUpdate_InterruptedTransactionRecovers", FullAppUpdate_InterruptedTransactionRecovers, failures);
        Run("FullAppUpdate_TamperAndBaselineMismatchFailClosed", FullAppUpdate_TamperAndBaselineMismatchFailClosed, failures);
        Run("WpfUpdate_GitHubSelectsNewestStableAndVerifiesAsset", WpfUpdate_GitHubSelectsNewestStableAndVerifiesAsset, failures);
        Run("WpfUpdate_AcceptsV01AndOnlyIdentityCaseVariation", WpfUpdate_AcceptsV01AndOnlyIdentityCaseVariation, failures);
        Run("WpfUpdate_GitHubNewestStableWithoutWpfDoesNotFallback", WpfUpdate_GitHubNewestStableWithoutWpfDoesNotFallback, failures);
        Run("WpfUpdate_GitHubRejectsChunkedOversizedMetadata", WpfUpdate_GitHubRejectsChunkedOversizedMetadata, failures);
        Run("WpfUpdate_GitHubClassifiesMalformedAndMissingPackages", WpfUpdate_GitHubClassifiesMalformedAndMissingPackages, failures);
        Run("WpfUpdate_GitHubClassifiesOfflineTimeoutRateLimitAndUnconfigured", WpfUpdate_GitHubClassifiesOfflineTimeoutRateLimitAndUnconfigured, failures);
        Run("WpfUpdate_GitHubAppliesAndRollsBackWithDataPreserved", WpfUpdate_GitHubAppliesAndRollsBackWithDataPreserved, failures);
        Run("WpfUpdate_GitHubStartupAndManualChecksAreAsync", WpfUpdate_GitHubStartupAndManualChecksAreAsync, failures);
        Run("WpfUpdate_GitHubButtonStateMapping", WpfUpdate_GitHubButtonStateMapping, failures);
        Run("WpfUpdate_GitHubCandidateIsReplacedOnRecheck", WpfUpdate_GitHubCandidateIsReplacedOnRecheck, failures);
        Run("WpfUpdate_GitHubCandidateIsDeletedOnClose", WpfUpdate_GitHubCandidateIsDeletedOnClose, failures);
        Run("WpfUpdate_GitHubHandedOffCandidateSurvivesOwnerDispose", WpfUpdate_GitHubHandedOffCandidateSurvivesOwnerDispose, failures);
        Run("WpfUpdate_GitHubRedirectsOnlyToTrustedCdn", WpfUpdate_GitHubRedirectsOnlyToTrustedCdn, failures);

        if (failures.Count == 0)
        {
            Console.WriteLine("WPF workflow tests: PASS (70)");
            return 0;
        }

        Console.Error.WriteLine($"WPF workflow tests: FAIL ({failures.Count})");
        foreach (var f in failures)
            Console.Error.WriteLine(" - " + f);
        return 1;
    }

    private static void Run(string name, Action test, List<string> failures)
    {
        try
        {
            test();
        }
        catch (Exception ex)
        {
            failures.Add($"{name}: {ex.Message}");
        }
    }

    private static void NoGame_CurrentIsExtract()
    {
        var snap = WorkflowStatus.Evaluate("", "/tmp/out");
        AssertEqual("extract", snap.Current);
        AssertEqual(WorkflowStepState.Current, snap.ExtractState);
        AssertTrue(snap.StepStatusLine.Contains("Chọn game"));
    }

    private static void AfterExtract_CurrentTranslate()
    {
        var root = CreatePackage(withTranslation: false, withPatch: false);
        try
        {
            var snap = WorkflowStatus.Evaluate(@"C:\game", root);
            AssertEqual("translate", snap.Current);
            AssertEqual(WorkflowStepState.Done, snap.ExtractState);
            AssertEqual(WorkflowStepState.Current, snap.TranslateState);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void AfterTranslate_CurrentPatch()
    {
        var root = CreatePackage(withTranslation: true, withPatch: false);
        try
        {
            var snap = WorkflowStatus.Evaluate(@"C:\game", root);
            AssertEqual("patch", snap.Current);
            AssertEqual(WorkflowStepState.Done, snap.TranslateState);
            AssertEqual(WorkflowStepState.Current, snap.PatchState);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void AfterPatch_CurrentDone()
    {
        var root = CreatePackage(withTranslation: true, withPatch: true);
        try
        {
            var snap = WorkflowStatus.Evaluate(@"C:\game", root);
            AssertEqual("done", snap.Current);
            AssertTrue(snap.StepStatusLine.Contains("Hoàn tất"));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void HasTranslations_ParsesQuotedCsv()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var csv = Path.Combine(root, "quoted.csv");
            File.WriteAllText(csv, "key,source_text,translation\r\nk1,\"Hello, world\",\"Xin chào, bạn\"\r\n", Encoding.UTF8);
            AssertTrue(WorkflowStatus.HasTranslations(csv));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void ChooseInput_UsesFolderPicker()
    {
        var selectedInput = Path.Combine(TestTempRoot(), "vntext_input_game");
        var picker = new FakePathPicker { InputPath = selectedInput };
        using var worker = new PythonWorkerHost();
        var vm = new MainViewModel(picker, worker, startWorker: false);
        vm.ChooseInputCommand.Execute(null);
        AssertEqual(selectedInput, vm.InputPath);
    }

    private static void ChooseOutput_UsesFolderPicker()
    {
        var selectedOutput = Path.Combine(TestTempRoot(), "vntext_output_pkg");
        var picker = new FakePathPicker { OutputFolder = selectedOutput };
        using var worker = new PythonWorkerHost();
        var vm = new MainViewModel(picker, worker, startWorker: false);
        vm.ChooseOutputCommand.Execute(null);
        AssertEqual(selectedOutput, vm.OutputPath);
    }

    private static void DropInput_UpdatesWorkflow()
    {
        var picker = new FakePathPicker();
        using var worker = new PythonWorkerHost();
        var vm = new MainViewModel(picker, worker, startWorker: false)
        {
            // Avoid the user's real Documents package — it can already be past extract.
            OutputPath = Path.Combine(TestTempRoot(), "vntext_wpf_drop_" + Guid.NewGuid().ToString("N")),
        };
        vm.SetInputPathFromDrop(@"C:\fixture\SampleGame.exe");
        AssertEqual("extract", vm.CurrentWorkflowStep);
        AssertEqual(WorkflowStepState.Current, vm.ExtractStepState);
    }

    private static void PartialTranslateComplete_UpdatesStatus()
    {
        var package = Path.Combine(RepoRoot(), "TEST_RUN", "external_unity_fixture", "package");
        if (!File.Exists(Path.Combine(package, "translation.csv")))
            return;

        var picker = new FakePathPicker();
        using var worker = new PythonWorkerHost();
        var vm = new MainViewModel(picker, worker, startWorker: false)
        {
            InputPath = Path.Combine(TestTempRoot(), "vntext_test_game_copy"),
            OutputPath = package,
        };
        vm.TestHandleWorkerEvent(new WorkerEvent
        {
            Type = "complete",
            Ok = true,
            Complete = false,
            Pending = 261,
            ReviewOnly = 262,
            Translated = 26109,
            Summary = "partial translate",
        });
        AssertEqual("Dịch một phần", vm.StatusText);
        AssertTrue(vm.ProgressSubtitle.Contains("pending 261"));
        AssertTrue(vm.ProgressSubtitle.Contains("review 262"));
        AssertFalse(vm.ProgressSubtitle.Contains("Hoàn tất"));
        AssertTrue(vm.StepStatusLine.Contains("Dịch một phần"));
        AssertTrue(vm.StepStatusLine.Contains("review 262"));
    }

    private static void RenpyGameDetector_OnlyShowsForLooseSource()
    {
        var configuredRoot = Environment.GetEnvironmentVariable("VNTEXT_WPF_TEST_WORK_ROOT");
        var workRoot = string.IsNullOrWhiteSpace(configuredRoot)
            ? Path.Combine(RepoRoot(), "TEST_RUN")
            : configuredRoot;
        var root = Path.Combine(workRoot, "wpf_renpy_detect_" + Guid.NewGuid().ToString("N"));
        var game = Path.Combine(root, "game");
        Directory.CreateDirectory(Path.Combine(game, "scripts"));
        File.WriteAllText(Path.Combine(game, "scripts", "script.rpy"), "label start:\\n", Encoding.UTF8);
        try
        {
            AssertTrue(RenpyGameDetector.IsLooseSourceGame(root, CancellationToken.None));
            File.Delete(Path.Combine(game, "scripts", "script.rpy"));
            File.WriteAllText(Path.Combine(game, "scripts", "script.rpyc"), "compiled", Encoding.UTF8);
            AssertFalse(RenpyGameDetector.IsLooseSourceGame(root, CancellationToken.None));
            File.WriteAllText(Path.Combine(game, "scripts", "script.rpy"), "label start:\\n", Encoding.UTF8);
            Directory.CreateDirectory(Path.Combine(root, "Sample_Data"));
            AssertFalse(RenpyGameDetector.IsLooseSourceGame(root, CancellationToken.None));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void CsvValidator_AndWorkflowCountQuotedMultilineRecords()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_multiline_status_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(root, ".mt"));
        try
        {
            File.WriteAllText(Path.Combine(root, "manifest.json"), "{\"entries\":[]}\n", Encoding.UTF8);
            var csv = Path.Combine(root, "translation.csv");
            File.WriteAllText(
                csv,
                "key,source_text,translation\r\n" +
                "k1,\"Source first\r\nSource second\",\" \r\nDòng tiếng Việt\"\r\n" +
                "k2,Waiting,\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            File.WriteAllText(
                Path.Combine(root, "review_only.csv"),
                "key,source_text,translation\r\n" +
                "r1,\"Review first\r\nReview second\",\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));

            var validation = CsvPackageValidator.Validate(csv);
            AssertTrue(validation.Ok);
            AssertEqual(2, validation.TotalRows);
            AssertEqual(1, validation.TranslatedRows);
            AssertTrue(WorkflowStatus.HasTranslations(csv));

            var progress = WorkflowStatus.EvaluateTranslateProgress(root);
            AssertTrue(progress.HasTranslations);
            AssertFalse(progress.IsComplete);
            AssertEqual(1, progress.Pending);
            AssertEqual(1, progress.ReviewOnly);
            var snapshot = WorkflowStatus.Evaluate(@"C:\game", root);
            AssertEqual("translate", snapshot.Current);
            AssertFalse(snapshot.TranslateComplete);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void MissingTranslateStatus_PartialCsvStaysIncomplete() =>
        AssertPartialPackageWithoutTrustedStatus(statusJson: null);

    private static void CorruptTranslateStatus_PartialCsvStaysIncomplete() =>
        AssertPartialPackageWithoutTrustedStatus(statusJson: "{not-json");

    private static void AssertPartialPackageWithoutTrustedStatus(string? statusJson)
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_partial_status_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(root, ".mt"));
        try
        {
            File.WriteAllText(Path.Combine(root, "manifest.json"), "{\"entries\":[]}\n", Encoding.UTF8);
            File.WriteAllText(
                Path.Combine(root, "translation.csv"),
                "key,source_text,translation\r\n" +
                "k1,Translated,Đã dịch\r\n" +
                "k2,Waiting,\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            File.WriteAllText(
                Path.Combine(root, "review_only.csv"),
                "key,source_text,translation\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            if (statusJson is not null)
                File.WriteAllText(Path.Combine(root, ".mt", "translate_status.json"), statusJson, Encoding.UTF8);

            var snapshot = WorkflowStatus.Evaluate(@"C:\game", root);
            var progress = WorkflowStatus.EvaluateTranslateProgress(root);
            AssertTrue(snapshot.HasTranslations);
            AssertFalse(snapshot.TranslateComplete);
            AssertEqual("translate", snapshot.Current);
            AssertEqual(WorkflowStepState.Current, snapshot.TranslateState);
            AssertFalse(progress.StatusKnown);
            AssertEqual(1, progress.Pending);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void RenpySdkOptionsVisibility_FollowsSelectedGame()
    {
        var configuredRoot = Environment.GetEnvironmentVariable("VNTEXT_WPF_TEST_WORK_ROOT");
        var workRoot = string.IsNullOrWhiteSpace(configuredRoot)
            ? Path.Combine(RepoRoot(), "TEST_RUN")
            : configuredRoot;
        var root = Path.Combine(workRoot, "wpf_renpy_visibility_" + Guid.NewGuid().ToString("N"));
        var game = Path.Combine(root, "Renpy", "game");
        var unity = Path.Combine(root, "Unity");
        Directory.CreateDirectory(game);
        Directory.CreateDirectory(Path.Combine(unity, "Demo_Data"));
        File.WriteAllText(Path.Combine(game, "script.rpy"), "label start", Encoding.UTF8);
        try
        {
            var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false);
            vm.InputPath = Path.Combine(root, "Renpy");
            AssertTrue(SpinWait.SpinUntil(() => vm.RenpySdkOptionsVisible, TimeSpan.FromSeconds(5)));
            vm.InputPath = unity;
            AssertFalse(vm.RenpySdkOptionsVisible);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void HumanReviewRequired_UpdatesStatus()
    {
        var picker = new FakePathPicker();
        using var worker = new PythonWorkerHost();
        var vm = new MainViewModel(picker, worker, startWorker: false);
        vm.TestSimulateTaskComplete("translate", new WorkerEvent
        {
            Type = "complete",
            Ok = false,
            Complete = false,
            Pending = 0,
            ReviewOnly = 2,
            HumanReviewRequiredCount = 2,
            Error = "Cần duyệt thủ công 2 dòng trước khi Patch",
        });

        AssertEqual("Dịch một phần", vm.StatusText);
        AssertEqual("Cần duyệt thủ công 2 dòng trước khi Patch", vm.ProgressSubtitle);
        AssertTrue(vm.StepStatusLine.Contains("Cần duyệt thủ công 2 dòng trước khi Patch"));
        AssertFalse(vm.StepStatusLine.Contains("Lỗi —"));
    }

    private static void RenpySdkMissing_ReportsPartialExtraction()
    {
        var picker = new FakePathPicker();
        using var worker = new PythonWorkerHost();
        var workRoot = Environment.GetEnvironmentVariable("VNTEXT_WPF_TEST_WORK_ROOT");
        if (string.IsNullOrWhiteSpace(workRoot))
            workRoot = Path.Combine(RepoRoot(), "TEST_RUN");
        var vm = new MainViewModel(picker, worker, startWorker: false)
        {
            InputPath = Path.Combine(workRoot, "renpy_missing_sdk_game"),
            OutputPath = Path.Combine(workRoot, "renpy_missing_sdk_package"),
        };
        vm.TestSimulateTaskComplete("extract", new WorkerEvent
        {
            Type = "complete",
            Ok = false,
            Complete = false,
            ReviewOnly = 2,
            RenpySdkMissing = true,
            Summary = "Lấy text chưa đầy đủ do thiếu công cụ Ren'Py.",
            Error = "Lấy text chưa đầy đủ do chưa có công cụ Ren'Py. 2 lời thoại cần xem lại.",
        });

        AssertEqual("Lấy text chưa đầy đủ", vm.StatusText);
        AssertTrue(vm.ProgressSubtitle.Contains("thiếu công cụ Ren'Py", StringComparison.Ordinal));
        AssertTrue(vm.StepStatusLine.Contains("2 lời thoại cần xem lại", StringComparison.Ordinal));
        AssertFalse(vm.StepStatusLine.Contains("Lỗi —", StringComparison.Ordinal));
        AssertTrue(vm.LogLines.Any(line => line.Contains("chưa có công cụ Ren'Py", StringComparison.Ordinal)));
        AssertFalse(vm.LogLines.Any(line => line.Contains("Lỗi: Lấy text chưa đầy đủ", StringComparison.Ordinal)));
    }

    private static void PartialPackage_TranslateNotComplete()
    {
        // Fixture độc lập dưới TEST_RUN — không phụ thuộc package E2E đã complete.
        var configuredRoot = Environment.GetEnvironmentVariable("VNTEXT_WPF_TEST_WORK_ROOT");
        var packageRoot = string.IsNullOrWhiteSpace(configuredRoot)
            ? Path.Combine(RepoRoot(), "TEST_RUN")
            : configuredRoot;
        var package = Path.Combine(packageRoot, "partial_translate_pkg_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(package, ".mt"));
        try
        {
            File.WriteAllText(Path.Combine(package, "manifest.json"), "{\"entries\":[]}\n", Encoding.UTF8);
            File.WriteAllText(
                Path.Combine(package, "translation.csv"),
                "key,source_text,translation,context,file_path,object_info,import_method,safety,backend,byte_limit,patch_note\r\n"
                + "k1,Hello,Xin chào,line:1,x.txt,,plain_text_line,safe,plain_text,,\r\n"
                + "k2,World,,line:2,x.txt,,plain_text_line,safe,plain_text,,\r\n",
                Encoding.UTF8);
            File.WriteAllText(
                Path.Combine(package, "review_only.csv"),
                "key,source_text,translation,context,file_path,object_info,import_method,safety,backend,byte_limit,patch_note\r\n"
                + "k_rev,{HARD}=blocked,,line:3,x.txt,,plain_text_line,review,plain_text,,\r\n",
                Encoding.UTF8);
            File.WriteAllText(
                Path.Combine(package, ".mt", "translate_status.json"),
                "{\"complete\":false,\"pending\":1,\"review_only\":1,\"blocked\":1,\"translated\":1}\n",
                Encoding.UTF8);

            var snap = WorkflowStatus.Evaluate(Path.Combine(package, "game"), package);
            AssertEqual("translate", snap.Current);
            AssertEqual(WorkflowStepState.Current, snap.TranslateState);
            AssertFalse(snap.TranslateState == WorkflowStepState.Done);
            AssertTrue(snap.StepStatusLine.Contains("Dịch một phần"));
            AssertTrue(snap.StepStatusLine.Contains("review"));
        }
        finally
        {
            if (Directory.Exists(package))
                Directory.Delete(package, recursive: true);
        }
    }

    private static void DiagnosticCompletion_IsVisibleAndActionable()
    {
        var picker = new FakePathPicker();
        using var worker = new PythonWorkerHost();
        var vm = new MainViewModel(picker, worker, startWorker: false);
        vm.TestSimulateTaskComplete("translate", new WorkerEvent
        {
            Type = "complete",
            Ok = false,
            Complete = false,
            Pending = 3,
            ReviewOnly = 1,
            Blocked = 1,
            DiagnosticPath = @"C:\package\.mt\diagnostic_summary.json",
            DiagnosticStage = "TRANSLATE",
            DiagnosticRootCause = "TRANSLATION_MISSED",
            DiagnosticAffectedCount = 3,
            DiagnosticAction = "Review translation blockers and retry.",
            DiagnosticStatus = "FAILED",
            Error = "translation failed",
        });

        AssertEqual("TRANSLATE", vm.DiagnosticStage);
        AssertEqual("TRANSLATION_MISSED", vm.DiagnosticRootCause);
        AssertEqual(3, vm.DiagnosticAffectedCount);
        AssertEqual(@"C:\package\.mt\diagnostic_summary.json", vm.DiagnosticPath);
        AssertTrue(vm.DiagnosticStatusLine.Contains("Review translation blockers", StringComparison.Ordinal));
        AssertTrue(vm.StepStatusLine.Contains("TRANSLATION_MISSED", StringComparison.Ordinal));
        AssertTrue(vm.LogLines.Any(line => line.Contains("Diagnostic evidence", StringComparison.Ordinal)));
    }

    private static void WorkerEvent_ParsesDiagnosticFields()
    {
        var evt = WorkerEvent.FromJson(
            "{\"type\":\"complete\",\"ok\":false,\"complete\":false,"
            + "\"diagnostic_stage\":\"PATCH\","
            + "\"diagnostic_root_cause\":\"PATCH_VERIFY_FAILED\","
            + "\"diagnostic_affected_count\":2,"
            + "\"diagnostic_action\":\"Inspect read-back evidence.\","
            + "\"diagnostic_path\":\"package/.mt/diagnostic_summary.json\","
            + "\"diagnostic_status\":\"FAILED\","
            + "\"renpy_sdk_missing\":true,"
            + "\"human_review_required_count\":5,"
            + "\"applied\":7,"
            + "\"patch_engine\":\"renpy\","
            + "\"patch_delivery\":\"renpy_native_overlay\","
            + "\"patch_payload_path\":\"package/Patch_Viet_Hoa/COPY_TO_GAME_ROOT\","
            + "\"patch_install_instructions\":\"Copy overlay into the Ren'Py game root.\"}");

        AssertTrue(evt is not null);
        AssertEqual("PATCH", evt!.DiagnosticStage);
        AssertEqual("PATCH_VERIFY_FAILED", evt.DiagnosticRootCause);
        AssertEqual(2, evt.DiagnosticAffectedCount);
        AssertEqual("Inspect read-back evidence.", evt.DiagnosticAction);
        AssertEqual("package/.mt/diagnostic_summary.json", evt.DiagnosticPath);
        AssertEqual("FAILED", evt.DiagnosticStatus);
        AssertTrue(evt.RenpySdkMissing);
        AssertEqual(5, evt.HumanReviewRequiredCount);
        AssertEqual(7, evt.Applied);
        AssertEqual("renpy", evt.PatchEngine);
        AssertEqual("renpy_native_overlay", evt.PatchDelivery);
        AssertEqual("package/Patch_Viet_Hoa/COPY_TO_GAME_ROOT", evt.PatchPayloadPath);
        AssertEqual("Copy overlay into the Ren'Py game root.", evt.PatchInstallInstructions);
    }

    private static void PatchDelivery_RoutesRenPyInstructions()
    {
        using var worker = new PythonWorkerHost();
        var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false);
        vm.TestSimulateTaskComplete("patch", new WorkerEvent
        {
            Type = "complete",
            Id = "patch-delivery-renpy",
            Ok = true,
            Complete = true,
            PatchEngine = "renpy",
            PatchDelivery = "renpy_native_overlay",
            PatchPayloadPath = @"C:\package\Patch_Viet_Hoa\COPY_TO_GAME_ROOT",
            PatchInstallInstructions = "Copy toàn bộ nội dung COPY_TO_GAME_ROOT vào game root Ren'Py.",
        });

        AssertTrue(vm.PatchDeliveryLabel.Contains("Ren'Py", StringComparison.Ordinal));
        AssertTrue(vm.PatchInstallInstructions.Contains("COPY_TO_GAME_ROOT", StringComparison.Ordinal));
        AssertTrue(!vm.PatchInstallInstructions.Contains("installer", StringComparison.OrdinalIgnoreCase));
        AssertTrue(vm.StepStatusLine.Contains("Ren'Py", StringComparison.Ordinal));
        AssertTrue(vm.LogLines.Any(line => line.Contains("Gói cài đặt", StringComparison.Ordinal)));
    }

    private static void BlockedCompletion_IsNotAccepted()
    {
        var root = CreatePackage(withTranslation: true, withPatch: false);
        try
        {
            Directory.CreateDirectory(Path.Combine(root, ".mt"));
            File.WriteAllText(
                Path.Combine(root, ".mt", "translate_status.json"),
                "{\"complete\":true,\"pending\":0,\"review_only\":0,\"blocked\":1,\"translated\":1}\n",
                Encoding.UTF8);

            var snapshot = WorkflowStatus.Evaluate(Path.Combine(root, "game"), root);
            AssertFalse(snapshot.TranslateComplete);
            AssertEqual("translate", snapshot.Current);
            AssertTrue(snapshot.StepStatusLine.Contains("blocked 1"));

            var picker = new FakePathPicker();
            using var worker = new PythonWorkerHost();
            var vm = new MainViewModel(picker, worker, startWorker: false)
            {
                InputPath = @"C:\game",
                OutputPath = root,
                SelectedTab = WorkflowTabs.Translate,
            };
            vm.TestSimulateTaskComplete("translate", new WorkerEvent
            {
                Type = "complete",
                Ok = true,
                Complete = true,
                Blocked = 1,
                Translated = 1,
            });
            AssertEqual(WorkflowTabs.Translate, vm.SelectedTab);
            AssertEqual("Dịch một phần", vm.StatusText);
            AssertTrue(vm.StepStatusLine.Contains("blocked 1"));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void NavigateTab_ChangesSelectedTab()
    {
        var picker = new FakePathPicker();
        using var worker = new PythonWorkerHost();
        var vm = new MainViewModel(picker, worker, startWorker: false);
        AssertEqual(WorkflowTabs.Extract, vm.SelectedTab);
        vm.NavigateTabCommand.Execute(WorkflowTabs.Patch);
        AssertEqual(WorkflowTabs.Patch, vm.SelectedTab);
        vm.NavigateTabCommand.Execute(WorkflowTabs.Translate);
        AssertEqual(WorkflowTabs.Translate, vm.SelectedTab);
    }

    private static void ExtractComplete_NavigatesToTranslate()
    {
        var root = CreatePackage(withTranslation: false, withPatch: false);
        try
        {
            var picker = new FakePathPicker();
            using var worker = new PythonWorkerHost();
            var vm = new MainViewModel(picker, worker, startWorker: false)
            {
                InputPath = @"C:\game",
                OutputPath = root,
                SelectedTab = WorkflowTabs.Extract,
            };
            vm.TestSimulateTaskComplete("extract", new WorkerEvent
            {
                Type = "complete",
                Ok = true,
                Complete = true,
                Summary = "extract ok",
            });
            AssertEqual(WorkflowTabs.Translate, vm.SelectedTab);
            AssertFalse(vm.Busy);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void ExternalCsv_ValidatesReadyForPatch()
    {
        var root = CreatePackage(withTranslation: true, withPatch: false);
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            var picker = new FakePathPicker { TranslationCsv = csv };
            using var worker = new PythonWorkerHost();
            var vm = new MainViewModel(picker, worker, startWorker: false)
            {
                InputPath = @"C:\game",
                OutputPath = root,
            };
            vm.ChooseTranslationCsvCommand.Execute(null);
            AssertTrue(vm.CsvValidationOk);
            AssertTrue(vm.ReadyForPatch);
            vm.NavigateTabCommand.Execute(WorkflowTabs.Patch);
            AssertEqual(WorkflowTabs.Patch, vm.SelectedTab);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void CsvValidator_RejectsEmptyTranslation()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            File.WriteAllText(csv, "key,source_text,translation\r\nk1,Hello,\r\n", Encoding.UTF8);
            File.WriteAllText(Path.Combine(root, "manifest.json"), "{}", Encoding.UTF8);
            var result = CsvPackageValidator.Validate(csv);
            AssertFalse(result.Ok);
            AssertTrue(result.Message.Contains("chưa có bản dịch"));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void TranslateComplete_NavigatesToPatch()
    {
        var root = CreatePackage(withTranslation: true, withPatch: false);
        try
        {
            var picker = new FakePathPicker();
            using var worker = new PythonWorkerHost();
            var vm = new MainViewModel(picker, worker, startWorker: false)
            {
                InputPath = @"C:\game",
                OutputPath = root,
                SelectedTab = WorkflowTabs.Translate,
            };
            vm.TestSimulateTaskComplete("translate", new WorkerEvent
            {
                Type = "complete",
                Ok = true,
                Complete = true,
                Summary = "translate ok",
            });
            AssertEqual(WorkflowTabs.Patch, vm.SelectedTab);
            AssertFalse(vm.Busy);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void ExtractLevel_Persists()
    {
        var path = AppSettingsStore.SettingsPath();
        AppSettings? prior = null;
        if (File.Exists(path))
        {
            prior = AppSettingsStore.Load();
            File.Delete(path);
        }
        try
        {
            var picker = new FakePathPicker();
            using var worker = new PythonWorkerHost();
            var vm = new MainViewModel(picker, worker, startWorker: false);
            AssertEqual(ExtractLevels.Balanced, vm.ExtractLevel);
            vm.ExtractLevel = ExtractLevels.Exhaustive;
            AssertEqual(ExtractLevels.Exhaustive, vm.ExtractLevel);
            var reloaded = AppSettingsStore.Load();
            AssertEqual(ExtractLevels.Exhaustive, reloaded.ExtractLevel);
            vm.ExtractLevel = "invalid";
            AssertEqual(ExtractLevels.Balanced, vm.ExtractLevel);
            AssertEqual("extract", vm.HeroIcon);
            vm.NavigateTabCommand.Execute(WorkflowTabs.Translate);
            AssertEqual("translate", vm.HeroIcon);
            AssertEqual("Dịch tự động", vm.HeroTitle);
        }
        finally
        {
            if (File.Exists(path))
                File.Delete(path);
            if (prior is not null)
                AppSettingsStore.Save(prior);
        }
    }

    private static string RepoRoot()
    {
        var dir = AppContext.BaseDirectory;
        while (!string.IsNullOrEmpty(dir))
        {
            if (File.Exists(Path.Combine(dir, "VERSION.txt")) && Directory.Exists(Path.Combine(dir, "wpf_app")))
                return dir;
            dir = Directory.GetParent(dir)?.FullName ?? "";
        }
        throw new InvalidOperationException("repo root not found");
    }

    private static void AnalyzeReportReader_ParsesCoverage()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_analyze_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var report = Path.Combine(root, "unity_analysis.json");
            File.WriteAllText(report, """
                {
                  "inventory_complete": true,
                  "unity": {"status": "DETECTED"},
                  "summary": {"resource_count": 12, "unknown_resources": 2, "scan_error_count": 0},
                  "coverage": {"text_candidates": 19, "patchable_text": 3, "extract_only_text": 4, "review_required": 5, "unsupported": 1},
                  "scan_errors": []
                }
                """, Encoding.UTF8);

            var snapshot = UnityAnalysisReportReader.TryRead(report, out _);
            AssertTrue(snapshot is not null);
            AssertEqual("DETECTED", snapshot!.UnityStatus);
            AssertTrue(snapshot.InventoryComplete);
            AssertEqual(12, snapshot.ResourceCount);
            AssertEqual(19, snapshot.TextCandidateCount);
            AssertEqual(3, snapshot.PatchableCount);
            AssertEqual(4, snapshot.ExtractOnlyCount);
            AssertEqual(6, snapshot.ReviewRiskCount);
            AssertEqual(2, snapshot.UnknownCount);
            AssertEqual(0, snapshot.ScanErrorCount);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void AnalyzeComplete_StaysOnExtractAndShowsEvidence()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_analyze_vm_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var report = Path.Combine(root, "unity_analysis.json");
            File.WriteAllText(report, """
                {
                  "inventory_complete": true,
                  "unity": {"status": "DETECTED"},
                  "summary": {"resource_count": 12, "unknown_resources": 2, "scan_error_count": 0},
                  "coverage": {"text_candidates": 19, "patchable_text": 3, "extract_only_text": 4, "review_required": 5, "unsupported": 1},
                  "scan_errors": []
                }
                """, Encoding.UTF8);

            using var worker = new PythonWorkerHost();
            var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false)
            {
                InputPath = @"C:\game",
                OutputPath = root,
                SelectedTab = WorkflowTabs.Extract,
            };

            AssertTrue(vm.AnalyzeCommand.CanExecute(null));
            vm.TestSimulateTaskComplete("analyze", new WorkerEvent
            {
                Type = "complete",
                Ok = true,
                Complete = true,
                Summary = "Unity analyzer: DETECTED; resources=12; unknown=2; scan_errors=0",
            });

            AssertFalse(vm.Busy);
            AssertEqual(WorkflowTabs.Extract, vm.SelectedTab);
            AssertEqual("DETECTED", vm.AnalyzeUnityStatus);
            AssertTrue(vm.AnalyzeInventoryComplete);
            AssertEqual(12, vm.AnalyzeResourceCount);
            AssertEqual(19, vm.AnalyzeTextCandidateCount);
            AssertEqual(3, vm.AnalyzePatchableCount);
            AssertEqual(6, vm.AnalyzeReviewRiskCount);
            AssertEqual(2, vm.AnalyzeUnknownCount);
            AssertTrue(vm.AnalyzeStatusText.Contains("inventory đầy đủ", StringComparison.Ordinal));
            AssertTrue(vm.AnalyzeScanErrorText.Contains("Patch verification chưa chạy", StringComparison.Ordinal));
            AssertEqual(report, vm.AnalyzeReportPath);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void PatchPreflight_BlocksGarbage()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            var garbage = "Đồng bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán bán lao";
            File.WriteAllText(csv,
                $"key,source_text,translation,context,file_path,import_method\r\nk1,Escort,{garbage},UI:Text,game/data.unity3d,unity_ui_text\r\n",
                Encoding.UTF8);
            File.WriteAllText(Path.Combine(root, "manifest.json"),
                """{"entries":[{"key":"k1","source_text":"Escort","file_path":"game/data.unity3d","import_method":"unity_ui_text"}]}""",
                Encoding.UTF8);
            var result = PatchPreflightService.Run(csv, Path.Combine(root, "manifest.json"));
            AssertEqual(0, result.Eligible);
            AssertTrue(result.Blocked >= 1);
            AssertTrue(result.ReasonCounts.ContainsKey("garbage_repetition"));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void PatchPreflight_AllowsCleanRow()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            File.WriteAllText(csv,
                "key,source_text,translation,context,file_path,import_method\r\nk1,Hello,Xin chào,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                Encoding.UTF8);
            File.WriteAllText(Path.Combine(root, "manifest.json"),
                """{"entries":[{"key":"k1","source_text":"Hello","file_path":"game/data.unity3d","import_method":"unity_textasset_line"}]}""",
                Encoding.UTF8);
            var result = PatchPreflightService.Run(csv, Path.Combine(root, "manifest.json"));
            AssertTrue(result.Ok);
            AssertEqual(1, result.Eligible);
            AssertEqual(0, result.Blocked);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void NavigateTab_EditCsv()
    {
        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
        vm.NavigateTabCommand.Execute(WorkflowTabs.EditCsv);
        AssertEqual(WorkflowTabs.EditCsv, vm.SelectedTab);
        AssertEqual("Sửa CSV", vm.HeroTitle);
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
        }
        finally
        {
            Directory.Delete(root, true);
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

    private static void AssertCsvEditorRetranslateDecision(
        MessageBoxResult saveDecision,
        bool failSave,
        bool expectStart,
        bool expectSaved)
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_retranslate_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        FileStream? readLock = null;
        try
        {
            var csv = Path.Combine(root, "translation.csv");
            File.WriteAllText(
                csv,
                "key,source_text,translation,context,file_path,import_method\r\n" +
                "k1,Hello,Original,UI:Text,game/data.unity3d,unity_textasset_line\r\n",
                new UTF8Encoding(encoderShouldEmitUTF8Identifier: true));
            File.WriteAllText(Path.Combine(root, "manifest.json"), "{\"entries\":[{\"key\":\"k1\"}]}\n", Encoding.UTF8);
            var original = File.ReadAllBytes(csv);

            using var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(new FakePathPicker { TranslationCsv = csv }, worker, startWorker: false)
            {
                OutputPath = root,
                TranslationModelDir = Path.Combine(root, "missing-model"),
            };
            vm.OpenCsvEditorFileCommand.Execute(null);
            AssertEqual(1, vm.CsvEditorRows.Count);
            vm.CsvEditorRows[0].Translation = "Bản dịch chỉnh sửa";
            vm.OnCsvEditorTranslationChanged();
            vm.UpdateCsvEditorSelection(new[] { vm.CsvEditorRows[0] });
            AssertTrue(vm.CsvEditorDirty);

            var promptCount = 0;
            vm.CsvEditorMessageBox = (_, caption, _, _) =>
            {
                promptCount++;
                if (caption == "Xác nhận dịch lại dòng lỗi")
                    return MessageBoxResult.Yes;
                if (caption == "Lưu CSV")
                {
                    if (failSave)
                        readLock = new FileStream(csv, FileMode.Open, FileAccess.Read, FileShare.Read);
                    return saveDecision;
                }
                throw new InvalidOperationException($"Unexpected prompt: {caption}");
            };

            vm.RetranslateBlockedCsvCommand.Execute(null);

            AssertEqual(2, promptCount);
            var taskStarted = vm.LogLines.Any(line => line.Contains("Gửi lệnh worker: translate", StringComparison.Ordinal));
            AssertEqual(expectStart, taskStarted);
            AssertEqual("Bản dịch chỉnh sửa", vm.CsvEditorRows[0].Translation);
            AssertEqual(expectSaved, !File.ReadAllBytes(csv).SequenceEqual(original));
            AssertEqual(!expectSaved, vm.CsvEditorDirty);
            if (expectSaved)
                AssertTrue(File.ReadAllText(csv, Encoding.UTF8).Contains("Bản dịch chỉnh sửa", StringComparison.Ordinal));
        }
        finally
        {
            readLock?.Dispose();
            if (Directory.Exists(root))
                Directory.Delete(root, recursive: true);
        }
    }

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

    private static void Toast_ShowsOnSimulatedComplete()
    {
        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
        vm.TestShowToast("Lấy text hoàn tất", "success", playSound: false);
        AssertEqual(true, vm.ToastVisible);
        AssertEqual("success", vm.ToastKind);
        AssertEqual("Lấy text hoàn tất", vm.ToastMessage);
    }

    private static void TranslateCsvSelection_PersistsAndBuildsPath()
    {
        var package = CreatePackage(withTranslation: true, withPatch: false);
        var external = CreatePackage(withTranslation: true, withPatch: false);
        try
        {
            var externalCsv = Path.Combine(external, "translation.csv");
            var picker = new FakePathPicker { TranslationCsv = externalCsv };
            using var worker = new PythonWorkerHost();
            var vm = new MainViewModel(picker, worker, startWorker: false)
            {
                InputPath = @"C:\game",
                OutputPath = package,
            };

            vm.ChooseTranslationCsvCommand.Execute(null);
            AssertEqual(externalCsv, vm.TranslationCsvPath);
            AssertEqual(externalCsv, vm.TranslationCsvDisplay);
            AssertEqual(externalCsv, vm.TestResolveActiveCsvPath());

            vm.NavigateTabCommand.Execute(WorkflowTabs.Settings);
            vm.NavigateTabCommand.Execute(WorkflowTabs.Translate);
            AssertEqual(externalCsv, vm.TranslationCsvPath);
            AssertEqual(externalCsv, vm.TestResolveActiveCsvPath());
        }
        finally
        {
            Directory.Delete(package, true);
            Directory.Delete(external, true);
        }
    }

    private static void TranslateCsvSelection_InvalidKeepsCurrent()
    {
        var package = CreatePackage(withTranslation: true, withPatch: false);
        var invalidDir = Path.Combine(TestTempRoot(), "vntext_wpf_invalid_csv_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(invalidDir);
        try
        {
            var validCsv = Path.Combine(package, "translation.csv");
            var invalidCsv = Path.Combine(invalidDir, "invalid.csv");
            File.WriteAllText(invalidCsv, "key,source_text,translation\r\nk1,Hello,\r\n", Encoding.UTF8);
            var picker = new FakePathPicker { TranslationCsv = validCsv };
            using var worker = new PythonWorkerHost();
            var vm = new MainViewModel(picker, worker, startWorker: false)
            {
                InputPath = @"C:\game",
                OutputPath = package,
            };

            vm.ChooseTranslationCsvCommand.Execute(null);
            AssertEqual(validCsv, vm.TranslationCsvPath);

            picker.TranslationCsv = invalidCsv;
            vm.ChooseTranslationCsvCommand.Execute(null);
            AssertEqual(validCsv, vm.TranslationCsvPath);
            AssertTrue(vm.CsvValidationOk);

            picker.TranslationCsv = null;
            vm.ChooseTranslationCsvCommand.Execute(null);
            AssertEqual(validCsv, vm.TranslationCsvPath);
        }
        finally
        {
            Directory.Delete(package, true);
            Directory.Delete(invalidDir, true);
        }
    }

    private static void CompletionNotification_ExactlyOncePerOutcome()
    {
        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
        var notifications = new List<CompletionNotification>();
        vm.CompletionRequested += (_, notification) => notifications.Add(notification);

        var success = new WorkerEvent
        {
            Type = "complete", Id = "completion-success", Ok = true, Complete = true,
        };
        vm.TestSimulateTaskComplete("extract", success);
        vm.TestHandleWorkerEvent(success);

        var partial = new WorkerEvent
        {
            Type = "complete", Id = "completion-partial", Ok = true, Complete = false,
            Pending = 2, ReviewOnly = 1, Translated = 7,
        };
        vm.TestSimulateTaskComplete("translate", partial);
        vm.TestHandleWorkerEvent(partial);

        var error = new WorkerEvent
        {
            Type = "complete", Id = "completion-error", Ok = false, Error = "CSV lỗi",
        };
        vm.TestSimulateTaskComplete("patch", error);
        vm.TestHandleWorkerEvent(error);

        AssertEqual(3, notifications.Count);
        AssertEqual("success", notifications[0].Kind);
        AssertEqual("warning", notifications[1].Kind);
        AssertEqual("error", notifications[2].Kind);
        AssertTrue(notifications[0].Message.Contains("Lấy text"));
        AssertTrue(notifications[1].Message.Contains("pending 2"));
        AssertEqual("CSV lỗi", notifications[2].Message);
    }

    private static void ReleaseVerifyRunner_ValidatesExactPortablePythonHome()
    {
        var work = Environment.GetEnvironmentVariable("VNTEXT_WPF_TEST_WORK_ROOT")
            ?? throw new InvalidOperationException("Portable-home test needs its owned work root.");
        var bundled = Path.GetFullPath(Path.Combine(work, "portable-home", "python"));
        AssertTrue(ReleaseVerifyRunner.PortablePythonHomeMatches("home = " + bundled + "\nversion = 3.12.14\n", bundled));
        AssertTrue(ReleaseVerifyRunner.PortablePythonHomeMatches("home = __VNText_INSTALL_ROOT__\\app\\worker\\python\n", bundled));
        AssertFalse(ReleaseVerifyRunner.PortablePythonHomeMatches("home = __VNText_INSTALL_ROOT__\\outside\\python\n", bundled));
        AssertFalse(ReleaseVerifyRunner.PortablePythonHomeMatches("home = __VNText_INSTALL_ROOT__\\app\\worker\\python\\extra\n", bundled));
        AssertFalse(ReleaseVerifyRunner.PortablePythonHomeMatches("# " + bundled + "\nhome = C:\\other-python\n", bundled));
        AssertFalse(ReleaseVerifyRunner.PortablePythonHomeMatches("home = ..\\python\n", bundled));
        AssertFalse(ReleaseVerifyRunner.PortablePythonHomeMatches("home = " + bundled + "\nhome = " + bundled, bundled));
        AssertFalse(ReleaseVerifyRunner.PortablePythonHomeMatches("version = 3.12.14\n", bundled));
    }

    private static void ReleaseVerifyRunner_ForwardsReport()
    {
        var arguments = ReleaseVerifyRunner.BuildPythonArguments(
            "vntext.release_verify",
            "run_release_verify",
            @"C:\evidence\release_verify.json");
        AssertEqual("-c", arguments[0]);
        AssertTrue(arguments[1].Contains("run_release_verify"));
        AssertEqual("--report", arguments[2]);
        AssertEqual(@"C:\evidence\release_verify.json", arguments[3]);
    }

    private static void SmokeWorker_IgnoresLegacyWorkPath()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_smoke_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            File.WriteAllText(Path.Combine(root, "smoke_m3"), "blocked", Encoding.UTF8);
            var work = SmokeWorker.PrepareWorkRoot(root);
            AssertTrue(!string.Equals(work, Path.Combine(root, "smoke_m3"), StringComparison.OrdinalIgnoreCase));
            File.WriteAllText(Path.Combine(work, "sample.txt"), "ok", Encoding.UTF8);
            AssertTrue(File.Exists(Path.Combine(work, "sample.txt")));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void SmokeWorker_FindsLegacyPatchOutput()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_smoke_patch_" + Guid.NewGuid().ToString("N"));
        var legacySample = Path.Combine(root, "COPY_TO_GAME_ROOT", "sample.txt");
        Directory.CreateDirectory(Path.GetDirectoryName(legacySample)!);
        File.WriteAllText(legacySample, "patched", Encoding.UTF8);
        try
        {
            AssertEqual(legacySample, SmokeWorker.FindPatchedSamplePath(root));
            var versionedRoot = Path.Combine(root, "Patch_Viet_Hoa", "VNTextPatch_v1", "COPY_TO_GAME_ROOT");
            var versionedSample = Path.Combine(versionedRoot, "sample.txt");
            Directory.CreateDirectory(versionedRoot);
            File.WriteAllText(versionedSample, "versioned", Encoding.UTF8);
            AssertEqual(versionedSample, SmokeWorker.FindPatchedSamplePath(root));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void SmokeWorker_UsesFreshWorkPath()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_smoke_fresh_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(root, "smoke_m3", "package", "COPY_TO_GAME_ROOT"));
        File.WriteAllText(
            Path.Combine(root, "smoke_m3", "package", "COPY_TO_GAME_ROOT", "sample.txt"),
            "stale",
            Encoding.UTF8);
        try
        {
            var first = SmokeWorker.PrepareWorkRoot(root);
            var second = SmokeWorker.PrepareWorkRoot(root);
            AssertTrue(!string.Equals(first, second, StringComparison.OrdinalIgnoreCase));
            AssertTrue(!string.Equals(first, Path.Combine(root, "smoke_m3"), StringComparison.OrdinalIgnoreCase));
            AssertTrue(!File.Exists(Path.Combine(first, "package", "COPY_TO_GAME_ROOT", "sample.txt")));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void WorkerPaths_FallsBackFromUnusableArtifactsRoot()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_artifacts_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var primary = Path.Combine(root, "blocked");
            var fallback = Path.Combine(root, "fallback");
            File.WriteAllText(primary, "blocked", Encoding.UTF8);
            var actual = WorkerPaths.ResolveWritableWorkArtifactsRoot(primary, fallback);
            AssertEqual(fallback, actual);
            AssertTrue(Directory.Exists(actual));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void ReleaseManagedPaths_StayUnderInstallRoot()
    {
        var work = Environment.GetEnvironmentVariable("VNTEXT_WPF_TEST_WORK_ROOT");
        if (String.IsNullOrWhiteSpace(work)) throw new InvalidOperationException("workflow test work root missing");
        var priorWorkRoot = Environment.GetEnvironmentVariable("VNTEXT_WORK_ARTIFACTS_ROOT");
        var configuredWorkRoot = Path.Combine(work, "dev-work-override");
        try
        {
            Environment.SetEnvironmentVariable("VNTEXT_WORK_ARTIFACTS_ROOT", configuredWorkRoot);
            AssertEqual(configuredWorkRoot, WorkerPaths.WorkArtifactsRoot());
        }
        finally
        {
            Environment.SetEnvironmentVariable("VNTEXT_WORK_ARTIFACTS_ROOT", priorWorkRoot);
        }
        var root = Path.Combine(work, "release-path-fixture");
        var app = Path.Combine(root, "app");
        var worker = Path.Combine(app, "worker");
        Directory.CreateDirectory(Path.Combine(worker, "vntext_worker"));
        Directory.CreateDirectory(Path.Combine(worker, ".venv", "Scripts"));
        File.WriteAllText(Path.Combine(worker, ".venv", "Scripts", "python.exe"), "fixture");
        Directory.CreateDirectory(Path.Combine(worker, "python"));
        Directory.CreateDirectory(Path.Combine(worker, ".venv", "Lib", "site-packages"));
        File.WriteAllText(Path.Combine(worker, "python", "python.exe"), "bundled-runtime-fixture");
        var cfg = Path.Combine(worker, ".venv", "pyvenv.cfg");
        var cfgBytes = Encoding.UTF8.GetBytes("home = __VNText_INSTALL_ROOT__\\app\\worker\\python\ninclude-system-site-packages = false\nversion = 3.12.14\n");
        File.WriteAllBytes(cfg, cfgBytes);
        File.WriteAllText(Path.Combine(root, WorkerPaths.MainExeName), "fixture");
        File.WriteAllText(Path.Combine(app, "VERSION.txt"), "1.0");
        var prior = Environment.CurrentDirectory;
        try
        {
            Environment.CurrentDirectory = app;
            AssertTrue(WorkerPaths.IsReleaseLayout());
            var data = Path.Combine(root, "data");
            AssertEqual(app, WorkerPaths.AppRoot());
            AssertEqual(worker, WorkerPaths.WorkerRoot());
            AssertEqual(Path.Combine(root, WorkerPaths.MainExeName), WorkerPaths.MainExePath());
            AssertEqual(data, WorkerPaths.AppDataRoot());
            AssertEqual(Path.Combine(data, "work"), WorkerPaths.WorkArtifactsRoot());
            AssertEqual(Path.Combine(data, "wpf_settings.json"), AppSettingsStore.SettingsPath());
            var childEnvironment = new Dictionary<string, string?> { ["TEMP"] = "outside", ["VNTEXT_RENPY_TOOL_ROOT"] = "outside" };
            WorkerPaths.ConfigureReleaseEnvironment(childEnvironment);
            AssertEqual(Path.Combine(data, "temp"), childEnvironment["TEMP"]);
            AssertEqual(Path.Combine(data, "tools"), childEnvironment["VNTEXT_RENPY_TOOL_ROOT"]);
            AssertEqual(Path.Combine(worker, "python", "python.exe"), WorkerPaths.PythonExecutable());
            AssertTrue(cfgBytes.SequenceEqual(File.ReadAllBytes(cfg)));
            AssertEqual(Path.Combine(worker, "python"), childEnvironment["PYTHONHOME"]);
            AssertEqual(Path.Combine(worker, ".venv", "Lib", "site-packages"), childEnvironment["PYTHONPATH"]);
            AssertEqual("1", childEnvironment["PYTHONNOUSERSITE"]);
            AssertEqual("1", childEnvironment["PYTHONDONTWRITEBYTECODE"]);
            using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
            AssertEqual(Path.Combine(data, "output"), vm.OutputPath);
            var partial = Path.Combine(work, "partial-release");
            Directory.CreateDirectory(partial);
            File.WriteAllText(Path.Combine(partial, "VERSION.txt"), "1.0");
            File.WriteAllText(Path.Combine(partial, WorkerPaths.MainExeName), "fixture");
            Environment.CurrentDirectory = partial;
            AssertTrue(WorkerPaths.IsReleaseLayout());
            AssertEqual(Path.Combine(partial, "data"), WorkerPaths.AppDataRoot());
        }
        finally
        {
            Environment.CurrentDirectory = prior;
        }
    }

    private static string CreatePackage(bool withTranslation, bool withPatch)
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        var translation = withTranslation ? "Xin chào" : "";
        File.WriteAllText(Path.Combine(root, "translation.csv"), $"key,source_text,translation\r\nk1,Hello,{translation}\r\n", Encoding.UTF8);
        File.WriteAllText(Path.Combine(root, "manifest.json"),
            """{"entries":[{"key":"k1","source_text":"Hello","file_path":"game/data.unity3d","import_method":"unity_textasset_line"}]}""",
            Encoding.UTF8);
        if (withTranslation)
        {
            var mt = Path.Combine(root, ".mt");
            Directory.CreateDirectory(mt);
            File.WriteAllText(Path.Combine(mt, "translate_status.json"),
                "{\"complete\":true,\"pending\":0,\"review_only\":0,\"blocked\":0,\"translated\":1}",
                Encoding.UTF8);
        }
        if (withPatch)
        {
            var patch = Path.Combine(root, "Patch_Viet_Hoa");
            Directory.CreateDirectory(patch);
            File.WriteAllText(Path.Combine(patch, "readme.txt"), "ok", Encoding.UTF8);
        }
        return root;
    }

    private static void WpfUpdate_VersionOrderRejectsInvalidAndNonIncreasing()
    {
        AssertTrue(WpfUpdateService.IsStrictlyNewerVersion("1.44.9-dev", "1.44.10-dev"));
        AssertTrue(WpfUpdateService.IsStrictlyNewerVersion("1.44.9-dev", "1.44.9"));
        AssertFalse(WpfUpdateService.IsStrictlyNewerVersion("1.44.9", "1.44.9-dev"));
        AssertFalse(WpfUpdateService.IsStrictlyNewerVersion("1.44.9-dev", "1.44.9-dev"));
        AssertFalse(WpfUpdateService.IsStrictlyNewerVersion("1.44.10-dev", "1.44.9-dev"));
        AssertFalse(WpfUpdateService.IsStrictlyNewerVersion("not-a-version", "1.44.10-dev"));
        AssertFalse(WpfUpdateService.IsStrictlyNewerVersion("1.44.9-dev", "1.44.10-"));
        AssertFalse(WpfUpdateService.IsStrictlyNewerVersion("1.44.9-alpha", "1.44.9-dev"));
    }

    private static void WpfUpdate_ReadsVersionBeyondMaxPath()
    {
        var candidate = Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")
            ?? throw new InvalidOperationException("candidate fixture executable missing");
        var root = TestTempRoot();
        var nameLength = 265 - root.Length - 2 - "VNText Studio.exe".Length;
        if (nameLength is < 1 or > 200)
            throw new InvalidOperationException("test work root cannot create a 265-character executable path");
        var directory = Path.Combine(root, new string('x', nameLength));
        var longPath = Path.Combine(directory, "VNText Studio.exe");
        try
        {
            Directory.CreateDirectory(directory);
            File.Copy(candidate, longPath);
            AssertEqual(265, longPath.Length);
            AssertEqual(HashFile(candidate), HashFile(longPath));
            AssertEqual(ReadExecutableProductVersion(candidate), WpfUpdateService.ReadExecutableProductVersion(longPath));
        }
        finally { if (Directory.Exists(directory)) Directory.Delete(directory, recursive: true); }
    }

    private static void WpfUpdate_AcceptsV01AndOnlyIdentityCaseVariation()
    {
        if (!WpfUpdateService.TryParseStableTag("v0.1", out var normalized, out var version) ||
            normalized != "0.1.0" || version != new Version(0, 1, 0))
            throw new InvalidOperationException("The planned v0.1 tag must normalize to stable version 0.1.0.");
        if (WpfUpdateService.TryParseStableTag("v0.01", out _, out _))
            throw new InvalidOperationException("Non-canonical two-part version tags must remain invalid.");

        const string owner = "test-owner";
        const string repository = "test-repo";
        const string tag = "v0.1";
        const string asset = "wpf-update-0.1.0.zip";
        bool Matches(string path) => WpfUpdateService.IsExpectedGitHubAssetPath(path, owner, repository, tag, asset);

        if (!Matches("/Test-Owner/Test-Repo/releases/download/v0.1/wpf-update-0.1.0.zip"))
            throw new InvalidOperationException("GitHub owner/repository path casing should not invalidate a trusted asset.");
        if (Matches("/test-owner/test-repo/Releases/download/v0.1/wpf-update-0.1.0.zip") ||
            Matches("/test-owner/test-repo/releases/download/V0.1/wpf-update-0.1.0.zip") ||
            Matches("/test-owner/test-repo/releases/download/v0.1/WPF-UPDATE-0.1.0.ZIP"))
            throw new InvalidOperationException("Release route, tag and asset filename must remain exact.");
    }

    private static void WpfUpdate_GitHubSelectsNewestStableAndVerifiesAsset()
    {
        var fixture = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(fixture, "test-owner", "test-repo");
            var baselineReleaseHash = HashFile(Path.Combine(fixture.Root, "app", "RELEASE.json"));
            var baselineVersionHash = HashFile(Path.Combine(fixture.Root, "app", "VERSION.txt"));
            var package = File.ReadAllBytes(fixture.PackagePath);
            var digest = HashBytes(package);
            var assetName = $"wpf-update-1.0.1-{digest[..16]}.zip";
            var downloadUrl = $"https://github.com/Test-Owner/Test-Repo/releases/download/v1.0.1/{assetName}";
            var setupUrl = "https://github.com/test-owner/test-repo/releases/download/v1.0.1/Setup.exe";
            var releases = JsonSerializer.Serialize(new object[]
            {
                GitHubRelease("v99.0.0", true, false),
                GitHubRelease("v50.0.0-rc.1", false, true),
                GitHubRelease("v1.0.0", false, false, GitHubAsset("Setup.exe", "sha256:" + digest, package.LongLength, setupUrl)),
                GitHubRelease("v1.0.1", false, false,
                    GitHubAsset(assetName, "sha256:" + digest, package.LongLength, downloadUrl),
                    GitHubAsset("Setup.exe", "sha256:" + digest, package.LongLength, setupUrl)),
            });
            var apiUrl = new Uri("https://api.github.com/repos/test-owner/test-repo/releases?per_page=100");
            var handler = new TestHttpMessageHandler((request, _) =>
            {
                if (request.RequestUri == apiUrl)
                    return Task.FromResult(JsonResponse(releases));
                if (request.RequestUri == new Uri(downloadUrl))
                    return Task.FromResult(BinaryResponse(package));
                throw new HttpRequestException("Unexpected HTTP target: " + request.RequestUri);
            });

            var result = WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root, handler).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.UpdateAvailable, result.State);
            AssertEqual("1.0.1", result.Version);
            AssertEqual(digest, result.PackageSha256);
            AssertEqual(2, handler.Requests.Count);
            AssertEqual(apiUrl, handler.Requests[0]);
            AssertEqual(new Uri(downloadUrl), handler.Requests[1]);
            AssertTrue(File.Exists(result.PackagePath));
            AssertEqual(digest, HashFile(result.PackagePath));
            AssertEqual(baselineReleaseHash, HashFile(Path.Combine(fixture.Root, "app", "RELEASE.json")));
            AssertEqual(baselineVersionHash, HashFile(Path.Combine(fixture.Root, "app", "VERSION.txt")));
            AssertTrue(result.PackagePath.StartsWith(Path.Combine(fixture.Root, ".update", "work"), StringComparison.OrdinalIgnoreCase));
            AssertFalse(result.PackagePath.StartsWith(Path.Combine(fixture.Root, "data"), StringComparison.OrdinalIgnoreCase));
            AssertEqual("user data remains unchanged", File.ReadAllText(Path.Combine(fixture.Root, "data", "keep.bin")));
        }
        finally { DeleteUpdateFixture(fixture); }
    }

    private static void WpfUpdate_GitHubNewestStableWithoutWpfDoesNotFallback()
    {
        var fixture = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(fixture, "test-owner", "test-repo");
            var package = File.ReadAllBytes(fixture.PackagePath);
            var digest = HashBytes(package);
            var assetName = $"wpf-update-1.0.1-{digest[..16]}.zip";
            var olderUrl = $"https://github.com/test-owner/test-repo/releases/download/v1.0.1/{assetName}";
            var releases = JsonSerializer.Serialize(new object[]
            {
                GitHubRelease("v1.0.1", false, false, GitHubAsset(assetName, "sha256:" + digest, package.LongLength, olderUrl)),
                GitHubRelease("v1.0.2", false, false),
            });
            var apiUrl = new Uri("https://api.github.com/repos/test-owner/test-repo/releases?per_page=100");
            var handler = new TestHttpMessageHandler((request, _) =>
            {
                if (request.RequestUri == apiUrl)
                    return Task.FromResult(JsonResponse(releases));
                if (request.RequestUri == new Uri(olderUrl))
                    return Task.FromResult(BinaryResponse(package));
                throw new HttpRequestException("Unexpected HTTP target: " + request.RequestUri);
            });

            var result = WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root, handler).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.SetupRequired, result.State);
            AssertEqual("1.0.2", result.Version);
            AssertEqual("https://github.com/test-owner/test-repo/releases/latest", result.ReleasesUrl);
            AssertEqual(1, handler.Requests.Count);
            AssertEqual(apiUrl, handler.Requests[0]);
            AssertFalse(Directory.Exists(Path.Combine(fixture.Root, ".update", "work")));
        }
        finally { DeleteUpdateFixture(fixture); }
    }

    private static void WpfUpdate_GitHubRejectsChunkedOversizedMetadata()
    {
        var fixture = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(fixture, "test-owner", "test-repo");
            const long maximumBytes = 10L * 1024 * 1024;
            var contentStream = new OversizedJsonStream(maximumBytes * 4);
            var content = new StreamContent(contentStream);
            AssertEqual<long?>(null, content.Headers.ContentLength);
            var handler = new TestHttpMessageHandler((request, _) =>
            {
                if (request.RequestUri?.Host == "api.github.com")
                    return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = content });
                throw new HttpRequestException("Oversized metadata must stop before asset download.");
            });

            var result = WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root, handler).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.InvalidMetadata, result.State);
            AssertTrue(contentStream.BytesRead <= maximumBytes + 64 * 1024);
            AssertTrue(contentStream.BytesRead < contentStream.TotalLength);
            AssertEqual(1, handler.Requests.Count);
        }
        finally { DeleteUpdateFixture(fixture); }
    }

    private static void WpfUpdate_GitHubClassifiesMalformedAndMissingPackages()
    {
        var malformedJson = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(malformedJson, "test-owner", "test-repo");
            var result = CheckGitHubResponse(malformedJson, "{");
            AssertEqual(GitHubUpdateState.InvalidMetadata, result.State);
        }
        finally { DeleteUpdateFixture(malformedJson); }

        var invalidTag = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(invalidTag, "test-owner", "test-repo");
            var result = CheckGitHubResponse(invalidTag, JsonSerializer.Serialize(new[] { GitHubRelease("v1.0.x", false, false) }));
            AssertEqual(GitHubUpdateState.InvalidMetadata, result.State);
        }
        finally { DeleteUpdateFixture(invalidTag); }

        var missingDigest = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(missingDigest, "test-owner", "test-repo");
            var result = CheckGitHubResponse(missingDigest, GitHubReleaseListWithAsset("v1.0.1", "wpf-update-1.0.1.zip", null, 10, "https://github.com/test-owner/test-repo/releases/download/v1.0.1/wpf-update-1.0.1.zip"));
            AssertEqual(GitHubUpdateState.InvalidMetadata, result.State);
        }
        finally { DeleteUpdateFixture(missingDigest); }

        var invalidDigest = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(invalidDigest, "test-owner", "test-repo");
            var expectedHash = HashFile(invalidDigest.PackagePath);
            var name = $"wpf-update-1.0.1-{expectedHash[..16]}.zip";
            var url = $"https://github.com/test-owner/test-repo/releases/download/v1.0.1/{name}";
            var result = CheckGitHubResponse(invalidDigest, GitHubReleaseListWithAsset("v1.0.1", name,
                "sha256:" + new string('z', 64), new FileInfo(invalidDigest.PackagePath).Length, url));
            AssertEqual(GitHubUpdateState.InvalidMetadata, result.State);
        }
        finally { DeleteUpdateFixture(invalidDigest); }

        var externalHost = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(externalHost, "test-owner", "test-repo");
            var packageHash = HashFile(externalHost.PackagePath);
            var name = $"wpf-update-1.0.1-{packageHash[..16]}.zip";
            var url = "https://example.invalid/releases/" + name;
            var result = CheckGitHubResponse(externalHost, GitHubReleaseListWithAsset("v1.0.1", name, "sha256:" + packageHash, new FileInfo(externalHost.PackagePath).Length, url));
            AssertEqual(GitHubUpdateState.InvalidMetadata, result.State);
        }
        finally { DeleteUpdateFixture(externalHost); }

        var missingAsset = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(missingAsset, "test-owner", "test-repo");
            var result = CheckGitHubResponse(missingAsset, JsonSerializer.Serialize(new[] { GitHubRelease("v1.0.1", false, false, GitHubAsset("Setup.exe", "sha256:" + new string('a', 64), 10, "https://github.com/test-owner/test-repo/releases/download/v1.0.1/Setup.exe")) }));
            AssertEqual(GitHubUpdateState.SetupRequired, result.State);
            AssertEqual("https://github.com/test-owner/test-repo/releases/latest", result.ReleasesUrl);
        }
        finally { DeleteUpdateFixture(missingAsset); }

        var baselineMismatch = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(baselineMismatch, "test-owner", "test-repo");
            File.AppendAllText(Path.Combine(baselineMismatch.Root, "app", "RELEASE.json"), " ");
            var result = CheckGitHubPackage(baselineMismatch);
            AssertEqual(GitHubUpdateState.SetupRequired, result.State);
            AssertEqual("https://github.com/test-owner/test-repo/releases/latest", result.ReleasesUrl);
        }
        finally { DeleteUpdateFixture(baselineMismatch); }

        var oversized = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(oversized, "test-owner", "test-repo");
            var digest = HashFile(oversized.PackagePath);
            var name = $"wpf-update-1.0.1-{digest[..16]}.zip";
            var url = $"https://github.com/test-owner/test-repo/releases/download/v1.0.1/{name}";
            var result = CheckGitHubResponse(oversized, GitHubReleaseListWithAsset("v1.0.1", name, "sha256:" + digest, WpfUpdateService.MaxGitHubUpdatePackageBytes + 1, url));
            AssertEqual(GitHubUpdateState.InvalidPackage, result.State);
        }
        finally { DeleteUpdateFixture(oversized); }

        var tampered = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(tampered, "test-owner", "test-repo");
            var bytes = File.ReadAllBytes(tampered.PackagePath);
            var modifiedBytes = bytes.ToArray();
            modifiedBytes[0] ^= 0x01;
            var digest = HashBytes(bytes);
            var name = $"wpf-update-1.0.1-{digest[..16]}.zip";
            var url = $"https://github.com/test-owner/test-repo/releases/download/v1.0.1/{name}";
            var metadata = GitHubReleaseListWithAsset("v1.0.1", name, "sha256:" + digest, bytes.LongLength, url);
            var handler = new TestHttpMessageHandler((request, _) =>
            {
                if (request.RequestUri?.Host == "api.github.com")
                    return Task.FromResult(JsonResponse(metadata));
                if (request.RequestUri == new Uri(url))
                    return Task.FromResult(BinaryResponse(modifiedBytes));
                throw new HttpRequestException("Unexpected HTTP target: " + request.RequestUri);
            });
            var result = WpfUpdateService.CheckGitHubUpdateAsync(tampered.Root, handler).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.InvalidPackage, result.State);
            AssertEqual(2, handler.Requests.Count);
        }
        finally { DeleteUpdateFixture(tampered); }
    }

    private static void WpfUpdate_GitHubClassifiesOfflineTimeoutRateLimitAndUnconfigured()
    {
        var fixture = CreateUpdateFixture("1.0.1");
        try
        {
            var unused = new TestHttpMessageHandler((_, _) => throw new HttpRequestException("must not be called"));
            var unconfigured = WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root, unused).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.Unconfigured, unconfigured.State);
            AssertEqual(0, unused.Requests.Count);

            ConfigureGitHubSource(fixture, "test-owner", "test-repo");
            var offline = WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root,
                new TestHttpMessageHandler((_, _) => throw new HttpRequestException("offline"))).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.Offline, offline.State);

            var timeout = WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root,
                new TestHttpMessageHandler((_, _) => throw new TaskCanceledException("simulated timeout"))).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.Timeout, timeout.State);

            var rateLimit = WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root,
                new TestHttpMessageHandler((_, _) =>
                {
                    var response = new HttpResponseMessage(HttpStatusCode.Forbidden);
                    response.Headers.TryAddWithoutValidation("X-RateLimit-Remaining", "0");
                    return Task.FromResult(response);
                })).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.RateLimited, rateLimit.State);
        }
        finally { DeleteUpdateFixture(fixture); }
    }

    private static void WpfUpdate_GitHubAppliesAndRollsBackWithDataPreserved()
    {
        var fixture = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(fixture, "test-owner", "test-repo");
            var check = CheckGitHubPackage(fixture);
            AssertEqual(GitHubUpdateState.UpdateAvailable, check.State);
            var candidateReleaseHash = HashZipEntry(fixture.PackagePath, "app/RELEASE.json");
            var candidateVersionHash = HashZipEntry(fixture.PackagePath, "app/VERSION.txt");
            var dataPath = Path.Combine(fixture.Root, "data", "keep.bin");
            var dataHash = HashFile(dataPath);
            var healthChecks = 0;
            var restarts = 0;
            var code = WpfUpdateService.RunGitHubUpdaterForTest(fixture.SourcePath, fixture.Root,
                check.PackagePath, check.PackageSha256, check.Version, restartApp: true,
                healthCheck: (exe, root) =>
                {
                    healthChecks++;
                    return root == fixture.Root && HashFile(exe) == fixture.CandidateExeHash;
                }, startApp: _ => restarts++);
            AssertEqual(0, code);
            AssertEqual(fixture.CandidateExeHash, HashFile(Path.Combine(fixture.Root, "VNText Studio.exe")));
            AssertEqual(candidateReleaseHash, HashFile(Path.Combine(fixture.Root, "app", "RELEASE.json")));
            AssertEqual(candidateVersionHash, HashFile(Path.Combine(fixture.Root, "app", "VERSION.txt")));
            AssertEqual(dataHash, HashFile(dataPath));
            AssertEqual(1, healthChecks);
            AssertEqual(1, restarts);
        }
        finally { DeleteUpdateFixture(fixture); }

        var rollback = CreateUpdateFixture("1.0.1", faultInject: true);
        try
        {
            ConfigureGitHubSource(rollback, "test-owner", "test-repo");
            var check = CheckGitHubPackage(rollback);
            var dataPath = Path.Combine(rollback.Root, "data", "keep.bin");
            var dataHash = HashFile(dataPath);
            var baseReleaseHash = HashFile(Path.Combine(rollback.Root, "app", "RELEASE.json"));
            var baseVersionHash = HashFile(Path.Combine(rollback.Root, "app", "VERSION.txt"));
            var healthChecks = 0;
            var restarts = 0;
            var code = WpfUpdateService.RunGitHubUpdaterForTest(rollback.SourcePath, rollback.Root,
                check.PackagePath, check.PackageSha256, check.Version, restartApp: true,
                healthCheck: (exe, root) =>
                {
                    healthChecks++;
                    return root == rollback.Root && HashFile(exe) == rollback.BaselineExeHash;
                }, startApp: _ => restarts++);
            AssertEqual(5, code);
            AssertEqual(rollback.BaselineExeHash, HashFile(Path.Combine(rollback.Root, "VNText Studio.exe")));
            AssertEqual(baseReleaseHash, HashFile(Path.Combine(rollback.Root, "app", "RELEASE.json")));
            AssertEqual(baseVersionHash, HashFile(Path.Combine(rollback.Root, "app", "VERSION.txt")));
            AssertEqual(dataHash, HashFile(dataPath));
            AssertEqual(1, healthChecks);
            AssertEqual(1, restarts);
        }
        finally { DeleteUpdateFixture(rollback); }
    }

    private static void WpfUpdate_GitHubStartupAndManualChecksAreAsync()
    {
        var fixture = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(fixture, "test-owner", "test-repo");
            var pending = new TaskCompletionSource<HttpResponseMessage>(TaskCreationOptions.RunContinuationsAsynchronously);
            var requests = 0;
            var handler = new TestHttpMessageHandler((_, _) =>
            {
                requests++;
                return requests == 1
                    ? pending.Task
                    : Task.FromResult(JsonResponse("[]"));
            });
            using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false,
                githubHttpHandler: handler, updateInstallRoot: fixture.Root);
            AssertTrue(vm.RecheckUpdateCommand.CanExecute(null));
            AssertEqual("Kiểm tra cập nhật", vm.GitHubUpdateButtonText);
            AssertTrue(vm.GitHubUpdateButtonEnabled);
            vm.RecheckUpdateCommand.Execute(null);
            AssertTrue(vm.GitHubUpdateStatus.Contains("Đang kiểm tra", StringComparison.Ordinal));
            AssertEqual("Đang kiểm tra…", vm.GitHubUpdateButtonText);
            AssertFalse(vm.GitHubUpdateButtonEnabled);
            AssertFalse(vm.RecheckUpdateCommand.CanExecute(null));
            AssertEqual(1, requests);

            pending.SetResult(JsonResponse("[]"));
            vm.GitHubUpdateCheckTask.GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.Current, vm.GitHubUpdateState);
            AssertEqual("Bạn đang dùng phiên bản mới nhất.", vm.GitHubUpdateStatus);
            AssertEqual("Đã cập nhật", vm.GitHubUpdateButtonText);
            AssertFalse(vm.GitHubUpdateButtonEnabled);
            AssertTrue(vm.RecheckUpdateCommand.CanExecute(null));
            vm.RecheckUpdateCommand.Execute(null);
            vm.GitHubUpdateCheckTask.GetAwaiter().GetResult();
            AssertEqual(2, requests);
            AssertEqual(GitHubUpdateState.Current, vm.GitHubUpdateState);
        }
        finally { DeleteUpdateFixture(fixture); }
    }

    private static void WpfUpdate_GitHubButtonStateMapping()
    {
        var idleFixture = CreateUpdateFixture("1.0.1");
        try
        {
            var idle = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false,
                updateInstallRoot: idleFixture.Root);
            try
            {
                AssertEqual("Kiểm tra cập nhật", idle.GitHubUpdateButtonText);
                AssertTrue(idle.GitHubUpdateButtonEnabled);
            }
            finally { idle.Dispose(); }

            ConfigureGitHubSource(idleFixture, "test-owner", "test-repo");
            var error = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false,
                githubHttpHandler: new TestHttpMessageHandler((_, _) => throw new HttpRequestException("offline")),
                updateInstallRoot: idleFixture.Root);
            try
            {
                error.RecheckUpdateCommand.Execute(null);
                error.GitHubUpdateCheckTask.GetAwaiter().GetResult();
                AssertEqual(GitHubUpdateState.Offline, error.GitHubUpdateState);
                AssertTrue(error.GitHubUpdateStatus.Contains("offline", StringComparison.OrdinalIgnoreCase));
                AssertEqual("Kiểm tra lại", error.GitHubUpdateButtonText);
                AssertTrue(error.GitHubUpdateButtonEnabled);
            }
            finally { error.Dispose(); }

            var availableFixture = CreateUpdateFixture("1.0.1");
            ConfigureGitHubSource(availableFixture, "test-owner", "test-repo");
            var available = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false,
                githubHttpHandler: CreateGitHubPackageHandler(availableFixture), updateInstallRoot: availableFixture.Root);
            try
            {
                available.RecheckUpdateCommand.Execute(null);
                available.GitHubUpdateCheckTask.GetAwaiter().GetResult();
                AssertEqual(GitHubUpdateState.UpdateAvailable, available.GitHubUpdateState);
                AssertEqual("Cài cập nhật", available.GitHubUpdateButtonText);
                AssertTrue(available.GitHubUpdateButtonEnabled);
            }
            finally
            {
                available.Dispose();
                DeleteUpdateFixture(availableFixture);
            }
        }
        finally { DeleteUpdateFixture(idleFixture); }
    }

    private static void WpfUpdate_GitHubCandidateIsReplacedOnRecheck()
    {
        var fixture = CreateUpdateFixture("1.0.1");
        ConfigureGitHubSource(fixture, "test-owner", "test-repo");
        var handler = CreateGitHubPackageHandler(fixture);
        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false,
            githubHttpHandler: handler, updateInstallRoot: fixture.Root);
        try
        {
            vm.RecheckUpdateCommand.Execute(null);
            vm.GitHubUpdateCheckTask.GetAwaiter().GetResult();
            var packageDirectory = Path.Combine(fixture.Root, ".update", "work");
            var firstCandidate = Directory.GetFiles(packageDirectory, "github-update-*.zip").Single();

            vm.RecheckGitHubUpdateForTest();
            vm.GitHubUpdateCheckTask.GetAwaiter().GetResult();

            var currentCandidates = Directory.GetFiles(packageDirectory, "github-update-*.zip");
            AssertFalse(File.Exists(firstCandidate));
            AssertEqual(1, currentCandidates.Length);
            AssertTrue(!string.Equals(firstCandidate, currentCandidates[0], StringComparison.OrdinalIgnoreCase));
        }
        finally
        {
            vm.Dispose();
            DeleteUpdateFixture(fixture);
        }
    }

    private static void WpfUpdate_GitHubCandidateIsDeletedOnClose()
    {
        var fixture = CreateUpdateFixture("1.0.1");
        ConfigureGitHubSource(fixture, "test-owner", "test-repo");
        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false,
            githubHttpHandler: CreateGitHubPackageHandler(fixture), updateInstallRoot: fixture.Root);
        try
        {
            vm.RecheckUpdateCommand.Execute(null);
            vm.GitHubUpdateCheckTask.GetAwaiter().GetResult();
            var packageDirectory = Path.Combine(fixture.Root, ".update", "work");
            var candidate = Directory.GetFiles(packageDirectory, "github-update-*.zip").Single();

            vm.Dispose();

            AssertFalse(File.Exists(candidate));
        }
        finally
        {
            vm.Dispose();
            DeleteUpdateFixture(fixture);
        }
    }

    private static void WpfUpdate_GitHubHandedOffCandidateSurvivesOwnerDispose()
    {
        var fixture = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(fixture, "test-owner", "test-repo");
            var check = CheckGitHubPackage(fixture);
            AssertEqual(GitHubUpdateState.UpdateAvailable, check.State);
            var dataPath = Path.Combine(fixture.Root, "data", "keep.bin");
            var dataHash = HashFile(dataPath);
            using (var lease = new GitHubUpdatePackageLease(fixture.Root, check))
            {
                lease.TransferToUpdater();
            }

            AssertTrue(File.Exists(check.PackagePath));
            var result = WpfUpdateService.RunGitHubUpdaterForTest(fixture.SourcePath, fixture.Root,
                check.PackagePath, check.PackageSha256, check.Version);
            AssertEqual(0, result);
            AssertFalse(File.Exists(check.PackagePath));
            AssertEqual(dataHash, HashFile(dataPath));
        }
        finally { DeleteUpdateFixture(fixture); }
    }

    private static void WpfUpdate_GitHubRedirectsOnlyToTrustedCdn()
    {
        var allowed = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(allowed, "test-owner", "test-repo");
            var package = File.ReadAllBytes(allowed.PackagePath);
            var digest = HashBytes(package);
            var name = $"wpf-update-1.0.1-{digest[..16]}.zip";
            var apiUrl = new Uri("https://api.github.com/repos/test-owner/test-repo/releases?per_page=100");
            var assetUrl = new Uri($"https://github.com/test-owner/test-repo/releases/download/v1.0.1/{name}");
            var cdnUrl = new Uri("https://release-assets.githubusercontent.com/vntext/test-package.zip");
            var metadata = GitHubReleaseListWithAsset("v1.0.1", name, "sha256:" + digest,
                package.LongLength, assetUrl.AbsoluteUri);
            var handler = new TestHttpMessageHandler((request, _) =>
            {
                if (request.RequestUri == apiUrl) return Task.FromResult(JsonResponse(metadata));
                if (request.RequestUri == assetUrl) return Task.FromResult(RedirectResponse(cdnUrl));
                if (request.RequestUri == cdnUrl) return Task.FromResult(BinaryResponse(package));
                throw new HttpRequestException("Unexpected HTTP target: " + request.RequestUri);
            });

            var result = WpfUpdateService.CheckGitHubUpdateAsync(allowed.Root, handler).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.UpdateAvailable, result.State);
            AssertEqual(3, handler.Requests.Count);
            AssertEqual(apiUrl, handler.Requests[0]);
            AssertEqual(assetUrl, handler.Requests[1]);
            AssertEqual(cdnUrl, handler.Requests[2]);
        }
        finally { DeleteUpdateFixture(allowed); }

        var rejected = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(rejected, "test-owner", "test-repo");
            var package = File.ReadAllBytes(rejected.PackagePath);
            var digest = HashBytes(package);
            var name = $"wpf-update-1.0.1-{digest[..16]}.zip";
            var apiUrl = new Uri("https://api.github.com/repos/test-owner/test-repo/releases?per_page=100");
            var assetUrl = new Uri($"https://github.com/test-owner/test-repo/releases/download/v1.0.1/{name}");
            var untrustedUrl = new Uri("https://untrusted.invalid/package.zip");
            var metadata = GitHubReleaseListWithAsset("v1.0.1", name, "sha256:" + digest,
                package.LongLength, assetUrl.AbsoluteUri);
            var handler = new TestHttpMessageHandler((request, _) =>
            {
                if (request.RequestUri == apiUrl) return Task.FromResult(JsonResponse(metadata));
                if (request.RequestUri == assetUrl) return Task.FromResult(RedirectResponse(untrustedUrl));
                throw new HttpRequestException("Untrusted redirect must not be requested.");
            });

            var result = WpfUpdateService.CheckGitHubUpdateAsync(rejected.Root, handler).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.InvalidPackage, result.State);
            AssertEqual(2, handler.Requests.Count);
            AssertFalse(handler.Requests.Contains(untrustedUrl));
            AssertEqual(0, Directory.GetFiles(Path.Combine(rejected.Root, ".update", "work"), "github-update-*.zip").Length);
        }
        finally { DeleteUpdateFixture(rejected); }
    }

    private static TestHttpMessageHandler CreateGitHubPackageHandler(UpdateFixture fixture)
    {
        var package = File.ReadAllBytes(fixture.PackagePath);
        var digest = HashBytes(package);
        var name = $"wpf-update-1.0.1-{digest[..16]}.zip";
        var apiUrl = new Uri("https://api.github.com/repos/test-owner/test-repo/releases?per_page=100");
        var downloadUrl = new Uri($"https://github.com/test-owner/test-repo/releases/download/v1.0.1/{name}");
        var metadata = GitHubReleaseListWithAsset("v1.0.1", name, "sha256:" + digest, package.LongLength, downloadUrl.AbsoluteUri);
        return new TestHttpMessageHandler((request, _) =>
        {
            if (request.RequestUri == apiUrl) return Task.FromResult(JsonResponse(metadata));
            if (request.RequestUri == downloadUrl) return Task.FromResult(BinaryResponse(package));
            throw new HttpRequestException("Unexpected HTTP target: " + request.RequestUri);
        });
    }

    private static GitHubUpdateCheckResult CheckGitHubResponse(UpdateFixture fixture, string json, byte[]? package = null)
    {
        var handler = new TestHttpMessageHandler((request, _) =>
        {
            if (request.RequestUri?.Host == "api.github.com")
                return Task.FromResult(JsonResponse(json));
            return Task.FromResult(BinaryResponse(package ?? File.ReadAllBytes(fixture.PackagePath)));
        });
        return WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root, handler).GetAwaiter().GetResult();
    }

    private static GitHubUpdateCheckResult CheckGitHubPackage(UpdateFixture fixture)
    {
        var package = File.ReadAllBytes(fixture.PackagePath);
        var digest = HashBytes(package);
        var name = $"wpf-update-1.0.1-{digest[..16]}.zip";
        var url = $"https://github.com/test-owner/test-repo/releases/download/v1.0.1/{name}";
        return CheckGitHubResponse(fixture, GitHubReleaseListWithAsset("v1.0.1", name,
            "sha256:" + digest, package.LongLength, url), package);
    }

    private static string GitHubReleaseListWithAsset(string tag, string name, string? digest, long size, string url)
    {
        object asset = digest is null
            ? new { name, size, browser_download_url = url }
            : GitHubAsset(name, digest, size, url);
        return JsonSerializer.Serialize(new[] { GitHubRelease(tag, false, false, asset) });
    }

    private static object GitHubRelease(string tag, bool draft, bool prerelease, params object[] assets) =>
        new { tag_name = tag, draft, prerelease, assets };

    private static object GitHubAsset(string name, string digest, long size, string url) =>
        new { name, digest, size, browser_download_url = url };

    private static HttpResponseMessage JsonResponse(string json) => new(HttpStatusCode.OK)
    {
        Content = new StringContent(json, Encoding.UTF8, "application/json")
    };

    private static HttpResponseMessage BinaryResponse(byte[] bytes) => new(HttpStatusCode.OK)
    {
        Content = new ByteArrayContent(bytes)
    };

    private static HttpResponseMessage RedirectResponse(Uri location)
    {
        var response = new HttpResponseMessage(HttpStatusCode.Redirect);
        response.Headers.Location = location;
        return response;
    }

    private static void ConfigureGitHubSource(UpdateFixture fixture, string owner, string repository)
    {
        var source = JsonSerializer.Deserialize<Dictionary<string, object>>(File.ReadAllText(fixture.SourcePath))!;
        source["github_owner"] = owner;
        source["github_repository"] = repository;
        File.WriteAllText(fixture.SourcePath, JsonSerializer.Serialize(source));
    }

    private static void WpfUpdate_InvalidOfferIsHiddenAndRejected()
    {
        var baselineVersion = RequiredExecutableProductVersion("VNTEXT_WPF_BASELINE_EXE");
        var candidateVersion = RequiredExecutableProductVersion("VNTEXT_WPF_CANDIDATE_EXE");
        var ordinaryInstall = Path.Combine(TestTempRoot(), "ordinary_install_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(ordinaryInstall);
        try
        {
            AssertFalse(WpfUpdateService.TryGetAvailableUpdateVersion(ordinaryInstall, out _, out var unavailable));
            AssertTrue(unavailable.Contains("Không thể kiểm tra nguồn cập nhật", StringComparison.Ordinal));
            using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
            AssertTrue(vm.UpdateCheckEnabled);
            AssertFalse(vm.UpdateEnabled);
            AssertTrue(vm.RecheckUpdateCommand.CanExecute(null));
            AssertFalse(vm.ApplyUpdateCommand.CanExecute(null));
        }
        finally { Directory.Delete(ordinaryInstall, recursive: true); }

        var badHash = CreateUpdateFixture();
        try
        {
            AssertTrue(WpfUpdateService.TryGetAvailableUpdateVersion(badHash.Root, out var version));
            AssertEqual(candidateVersion, version);
            var feed = JsonSerializer.Deserialize<Dictionary<string, object>>(File.ReadAllText(badHash.FeedPath))!;
            feed["package_sha256"] = new string('0', 64);
            File.WriteAllText(badHash.FeedPath, JsonSerializer.Serialize(feed));
            AssertFalse(WpfUpdateService.TryGetAvailableUpdateVersion(badHash.Root, out _, out var badHashStatus));
            AssertTrue(badHashStatus.Contains("SHA-256 mismatch", StringComparison.Ordinal));
            AssertEqual(5, WpfUpdateService.RunUpdaterForTest(badHash.SourcePath, badHash.Root));
            AssertEqual(badHash.BaselineExeHash, HashFile(Path.Combine(badHash.Root, "VNText Studio.exe")));
            AssertEqual(baselineVersion, File.ReadAllText(Path.Combine(badHash.Root, "app", "VERSION.txt")).Trim());
        }
        finally { DeleteUpdateFixture(badHash); }

        var malformed = CreateUpdateFixture();
        try
        {
            File.WriteAllText(malformed.PackagePath, "not a zip package");
            var feed = JsonSerializer.Deserialize<Dictionary<string, object>>(File.ReadAllText(malformed.FeedPath))!;
            feed["package_sha256"] = HashFile(malformed.PackagePath);
            File.WriteAllText(malformed.FeedPath, JsonSerializer.Serialize(feed));
            AssertFalse(WpfUpdateService.TryGetAvailableUpdateVersion(malformed.Root, out _));
            AssertEqual(5, WpfUpdateService.RunUpdaterForTest(malformed.SourcePath, malformed.Root));
            AssertEqual(malformed.BaselineExeHash, HashFile(Path.Combine(malformed.Root, "VNText Studio.exe")));
        }
        finally { DeleteUpdateFixture(malformed); }

        var stale = CreateUpdateFixture(
            baselineVersion,
            candidateExePathOverride: Environment.GetEnvironmentVariable("VNTEXT_WPF_BASELINE_EXE"));
        try
        {
            AssertFalse(WpfUpdateService.TryGetAvailableUpdateVersion(stale.Root, out _));
            AssertEqual(5, WpfUpdateService.RunUpdaterForTest(stale.SourcePath, stale.Root));
        }
        finally { DeleteUpdateFixture(stale); }

        var invalidVersion = CreateUpdateFixture("1.44.x-dev");
        try
        {
            AssertFalse(WpfUpdateService.TryGetAvailableUpdateVersion(invalidVersion.Root, out _));
            AssertEqual(5, WpfUpdateService.RunUpdaterForTest(invalidVersion.SourcePath, invalidVersion.Root));
            AssertEqual(invalidVersion.BaselineExeHash, HashFile(Path.Combine(invalidVersion.Root, "VNText Studio.exe")));
            AssertEqual(baselineVersion, File.ReadAllText(Path.Combine(invalidVersion.Root, "app", "VERSION.txt")).Trim());
        }
        finally { DeleteUpdateFixture(invalidVersion); }

        var badBaseline = CreateUpdateFixture();
        try
        {
            File.AppendAllText(Path.Combine(badBaseline.Root, "VNText Studio.exe"), "changed");
            AssertFalse(WpfUpdateService.TryGetAvailableUpdateVersion(badBaseline.Root, out _));
            AssertEqual(5, WpfUpdateService.RunUpdaterForTest(badBaseline.SourcePath, badBaseline.Root));
        }
        finally { DeleteUpdateFixture(badBaseline); }
    }

    private static void WpfUpdate_FaultThenRetryIgnoresPriorStagingAndBackup()
    {
        var baselineVersion = RequiredExecutableProductVersion("VNTEXT_WPF_BASELINE_EXE");
        var candidateVersion = RequiredExecutableProductVersion("VNTEXT_WPF_CANDIDATE_EXE");
        var fixture = CreateUpdateFixture(faultInject: true);
        try
        {
            var dataFile = Path.Combine(fixture.Root, "data", "keep.bin");
            var dataHash = HashFile(dataFile);
            var baseReleaseHash = HashFile(Path.Combine(fixture.Root, "app", "RELEASE.json"));
            var baseVersionHash = HashFile(Path.Combine(fixture.Root, "app", "VERSION.txt"));
            var backupParent = Path.Combine(fixture.Root, "update", "backup");
            var stagingParent = Path.Combine(fixture.Root, "update", "staging");
            var oldBackup = Path.Combine(backupParent, "txn-prior", "VNText Studio.exe");
            var oldStaging = Path.Combine(stagingParent, "txn-prior", "VNText Studio.exe");
            Directory.CreateDirectory(Path.GetDirectoryName(oldBackup)!);
            Directory.CreateDirectory(Path.GetDirectoryName(oldStaging)!);
            File.WriteAllText(oldBackup, "prior backup");
            File.WriteAllText(oldStaging, "prior staging");

            AssertEqual(5, WpfUpdateService.RunUpdaterForTest(fixture.SourcePath, fixture.Root));
            AssertEqual(fixture.BaselineExeHash, HashFile(Path.Combine(fixture.Root, "VNText Studio.exe")));
            AssertEqual(baselineVersion, File.ReadAllText(Path.Combine(fixture.Root, "app", "VERSION.txt")).Trim());
            AssertEqual(baseReleaseHash, HashFile(Path.Combine(fixture.Root, "app", "RELEASE.json")));
            AssertEqual(baseVersionHash, HashFile(Path.Combine(fixture.Root, "app", "VERSION.txt")));
            AssertEqual(dataHash, HashFile(dataFile));
            AssertEqual("prior backup", File.ReadAllText(oldBackup));
            AssertEqual("prior staging", File.ReadAllText(oldStaging));

            var source = JsonSerializer.Deserialize<Dictionary<string, object>>(File.ReadAllText(fixture.SourcePath))!;
            source["fault_inject_after_first_replace"] = false;
            File.WriteAllText(fixture.SourcePath, JsonSerializer.Serialize(source));
            AssertEqual(0, WpfUpdateService.RunUpdaterForTest(fixture.SourcePath, fixture.Root));
            AssertEqual(fixture.CandidateExeHash, HashFile(Path.Combine(fixture.Root, "VNText Studio.exe")));
            AssertEqual(candidateVersion, File.ReadAllText(Path.Combine(fixture.Root, "app", "VERSION.txt")).Trim());
            AssertEqual(dataHash, HashFile(dataFile));
            AssertEqual("prior backup", File.ReadAllText(oldBackup));
            AssertEqual("prior staging", File.ReadAllText(oldStaging));
            AssertEqual(Path.Combine(backupParent, "txn-prior"), Directory.GetDirectories(backupParent, "txn-*", SearchOption.TopDirectoryOnly).Single());
            AssertEqual(Path.Combine(stagingParent, "txn-prior"), Directory.GetDirectories(stagingParent, "txn-*", SearchOption.TopDirectoryOnly).Single());
        }
        finally { DeleteUpdateFixture(fixture); }
    }

    private static void FullAppUpdate_AppliesAddReplaceDeleteAndKeepsDataAndModel()
    {
        var fixture = CreateFullAppUpdateFixture();
        try
        {
            var dataPath = Path.Combine(fixture.Root, "data", "keep.bin");
            var dataHash = HashFile(dataPath);
            var modelPath = Path.Combine(fixture.Root, "app", "worker", "models", "pinned.bin");
            var modelHash = HashFile(modelPath);
            var starts = 0;
            var exit = FullAppUpdateService.RunForTest(fixture.SourcePath, fixture.Root, restartApp: true,
                healthCheck: (exe, root) => root == fixture.Root &&
                    HashFile(exe) == fixture.CandidateExeHash &&
                    File.Exists(Path.Combine(root, "app", "worker", "added.txt")),
                startApp: _ => starts++);

            if (exit != 0) throw new InvalidOperationException($"expected exit 0, got {exit}; log: {ReadFullAppUpdateLog(fixture)}");
            AssertEqual(0, exit);
            AssertEqual(1, starts);
            AssertEqual(dataHash, HashFile(dataPath));
            AssertEqual(modelHash, HashFile(modelPath));
            AssertEqual("candidate content", File.ReadAllText(Path.Combine(fixture.Root, "app", "worker", "replace.txt")));
            AssertEqual("new worker file", File.ReadAllText(Path.Combine(fixture.Root, "app", "worker", "added.txt")));
            AssertFalse(File.Exists(Path.Combine(fixture.Root, "app", "worker", "obsolete.txt")));
            AssertTrue(File.Exists(Path.Combine(fixture.Root, FullAppUpdateService.OwnershipName.Replace('/', Path.DirectorySeparatorChar))));
            var owned = JsonSerializer.Deserialize<string[]>(File.ReadAllText(Path.Combine(fixture.Root, FullAppUpdateService.OwnershipName.Replace('/', Path.DirectorySeparatorChar))))!;
            AssertTrue(owned.Contains("app/worker/added.txt", StringComparer.Ordinal));
            AssertFalse(File.Exists(Path.Combine(fixture.Root, ".update", "pending-full-app-update.json")));
        }
        finally { DeleteFullAppUpdateFixture(fixture); }
    }

    private static void FullAppUpdate_HealthFailureRollsBack()
    {
        var fixture = CreateFullAppUpdateFixture();
        try
        {
            var baselineExeHash = fixture.BaselineExeHash;
            var dataPath = Path.Combine(fixture.Root, "data", "keep.bin");
            var dataHash = HashFile(dataPath);
            var starts = 0;
            var exit = FullAppUpdateService.RunForTest(fixture.SourcePath, fixture.Root, restartApp: true,
                healthCheck: (exe, _) => HashFile(exe) == baselineExeHash,
                startApp: _ => starts++);

            AssertEqual(5, exit);
            AssertEqual(1, starts);
            AssertEqual(baselineExeHash, HashFile(Path.Combine(fixture.Root, "VNText Studio.exe")));
            AssertEqual("baseline content", File.ReadAllText(Path.Combine(fixture.Root, "app", "worker", "replace.txt")));
            AssertTrue(File.Exists(Path.Combine(fixture.Root, "app", "worker", "obsolete.txt")));
            AssertFalse(File.Exists(Path.Combine(fixture.Root, "app", "worker", "added.txt")));
            AssertEqual(dataHash, HashFile(dataPath));
            AssertFalse(File.Exists(Path.Combine(fixture.Root, ".update", "pending-full-app-update.json")));
        }
        finally { DeleteFullAppUpdateFixture(fixture); }
    }

    private static void FullAppUpdate_InterruptedTransactionRecovers()
    {
        var fixture = CreateFullAppUpdateFixture(faultInject: true);
        try
        {
            var exit = FullAppUpdateService.RunForTest(fixture.SourcePath, fixture.Root);
            if (exit != 7) throw new InvalidOperationException($"expected exit 7, got {exit}; log: {ReadFullAppUpdateLog(fixture)}");
            AssertEqual(7, exit);
            AssertEqual(fixture.CandidateExeHash, HashFile(Path.Combine(fixture.Root, "VNText Studio.exe")));
            AssertTrue(File.ReadAllText(Path.Combine(fixture.Root, "app", "RELEASE.json")).Contains("source_tree_sha256"));
            AssertTrue(File.Exists(Path.Combine(fixture.Root, ".update", "pending-full-app-update.json")));
            AssertTrue(FullAppUpdateService.RecoverInterruptedUpdate(fixture.Root));
            AssertEqual(fixture.BaselineExeHash, HashFile(Path.Combine(fixture.Root, "VNText Studio.exe")));
            AssertEqual("baseline content", File.ReadAllText(Path.Combine(fixture.Root, "app", "worker", "replace.txt")));
            AssertTrue(File.Exists(Path.Combine(fixture.Root, "app", "worker", "obsolete.txt")));
            AssertFalse(File.Exists(Path.Combine(fixture.Root, "app", "worker", "added.txt")));
            AssertEqual("user data remains unchanged", File.ReadAllText(Path.Combine(fixture.Root, "data", "keep.bin")));
            AssertFalse(File.Exists(Path.Combine(fixture.Root, ".update", "pending-full-app-update.json")));
        }
        finally { DeleteFullAppUpdateFixture(fixture); }
    }

    private static void FullAppUpdate_TamperAndBaselineMismatchFailClosed()
    {
        var tampered = CreateFullAppUpdateFixture();
        try
        {
            File.AppendAllText(tampered.PackagePath, "tamper");
            AssertEqual(5, FullAppUpdateService.RunForTest(tampered.SourcePath, tampered.Root));
            AssertEqual(tampered.BaselineExeHash, HashFile(Path.Combine(tampered.Root, "VNText Studio.exe")));
            AssertEqual("baseline content", File.ReadAllText(Path.Combine(tampered.Root, "app", "worker", "replace.txt")));
        }
        finally { DeleteFullAppUpdateFixture(tampered); }

        var mismatch = CreateFullAppUpdateFixture();
        try
        {
            File.WriteAllText(Path.Combine(mismatch.Root, "app", "unowned.txt"), "not in the pinned baseline");
            AssertEqual(5, FullAppUpdateService.RunForTest(mismatch.SourcePath, mismatch.Root));
            AssertEqual(mismatch.BaselineExeHash, HashFile(Path.Combine(mismatch.Root, "VNText Studio.exe")));
            AssertTrue(File.Exists(Path.Combine(mismatch.Root, "app", "unowned.txt")));
        }
        finally { DeleteFullAppUpdateFixture(mismatch); }
    }

    private static void FullAppUpdate_GitHubAssetPathSizeAndHashAreBound()
    {
        var valid = CreateFullAppUpdateFixture();
        try
        {
            var bytes = File.ReadAllBytes(valid.PackagePath);
            var digest = HashBytes(bytes);
            var url = FullAppAssetUrl(valid, digest);
            var handler = CreateFullAppGitHubHandler(valid, digest, bytes.LongLength, url, bytes);
            var result = WpfUpdateService.CheckGitHubUpdateAsync(valid.Root, handler).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.UpdateAvailable, result.State);
            AssertTrue(result.FullAppPackage);
            AssertEqual(digest, result.PackageSha256);
            AssertEqual(2, handler.Requests.Count);
            AssertEqual(digest, HashFile(result.PackagePath));
            AssertTrue(FullAppUpdateService.IsExpectedFullAppAssetPath(
                new Uri(url).AbsolutePath, "test-owner", "test-repo", "v" + ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")!),
                $"full-app-update-{ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")!)}-{digest[..16]}.zip"));
            WpfUpdateService.DeleteGitHubUpdateCandidate(valid.Root, result);
        }
        finally { DeleteFullAppUpdateFixture(valid); }

        var oversized = CreateFullAppUpdateFixture();
        try
        {
            var bytes = File.ReadAllBytes(oversized.PackagePath);
            var digest = HashBytes(bytes);
            var result = WpfUpdateService.CheckGitHubUpdateAsync(oversized.Root,
                CreateFullAppGitHubHandler(oversized, digest, WpfUpdateService.MaxGitHubUpdatePackageBytes + 1,
                    FullAppAssetUrl(oversized, digest), bytes)).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.InvalidPackage, result.State);
        }
        finally { DeleteFullAppUpdateFixture(oversized); }

        var wrongPath = CreateFullAppUpdateFixture();
        try
        {
            var bytes = File.ReadAllBytes(wrongPath.PackagePath);
            var digest = HashBytes(bytes);
            var url = FullAppAssetUrl(wrongPath, digest).Replace("/test-repo/", "/other-repo/", StringComparison.Ordinal);
            var result = WpfUpdateService.CheckGitHubUpdateAsync(wrongPath.Root,
                CreateFullAppGitHubHandler(wrongPath, digest, bytes.LongLength, url, bytes)).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.InvalidMetadata, result.State);
        }
        finally { DeleteFullAppUpdateFixture(wrongPath); }

        var badHash = CreateFullAppUpdateFixture();
        try
        {
            var bytes = File.ReadAllBytes(badHash.PackagePath);
            var actualDigest = HashBytes(bytes);
            var publishedDigest = new string(actualDigest[0] == '0' ? '1' : '0', 64);
            var result = WpfUpdateService.CheckGitHubUpdateAsync(badHash.Root,
                CreateFullAppGitHubHandler(badHash, publishedDigest, bytes.LongLength,
                    FullAppAssetUrl(badHash, publishedDigest), bytes)).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.InvalidPackage, result.State);
        }
        finally { DeleteFullAppUpdateFixture(badHash); }
    }

    private static string FullAppAssetUrl(FullAppUpdateFixture fixture, string digest)
    {
        var version = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")!);
        var name = $"full-app-update-{version}-{digest[..16]}.zip";
        return $"https://github.com/test-owner/test-repo/releases/download/v{version}/{name}";
    }

    private static TestHttpMessageHandler CreateFullAppGitHubHandler(FullAppUpdateFixture fixture,
        string digest, long size, string downloadUrl, byte[] packageBytes)
    {
        var source = JsonSerializer.Deserialize<Dictionary<string, object>>(File.ReadAllText(fixture.SourcePath))!;
        source["github_owner"] = "test-owner";
        source["github_repository"] = "test-repo";
        File.WriteAllText(fixture.SourcePath, JsonSerializer.Serialize(source));
        var version = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")!);
        var assetName = $"full-app-update-{version}-{digest[..16]}.zip";
        var releases = JsonSerializer.Serialize(new[]
        {
            GitHubRelease("v" + version, false, false,
                GitHubAsset(assetName, "sha256:" + digest, size, downloadUrl)),
        });
        var apiUrl = new Uri("https://api.github.com/repos/test-owner/test-repo/releases?per_page=100");
        return new TestHttpMessageHandler((request, _) =>
        {
            if (request.RequestUri == apiUrl) return Task.FromResult(JsonResponse(releases));
            if (request.RequestUri == new Uri(downloadUrl)) return Task.FromResult(BinaryResponse(packageBytes));
            throw new HttpRequestException("Unexpected HTTP target: " + request.RequestUri);
        });
    }

    private static FullAppUpdateFixture CreateFullAppUpdateFixture(bool faultInject = false)
    {
        var baselineExePath = Environment.GetEnvironmentVariable("VNTEXT_WPF_BASELINE_EXE");
        var candidateExePath = Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE");
        if (string.IsNullOrWhiteSpace(baselineExePath) || !File.Exists(baselineExePath) ||
            string.IsNullOrWhiteSpace(candidateExePath) || !File.Exists(candidateExePath))
            throw new InvalidOperationException("versioned WPF A/B executables are required for full-app updater tests");

        var baselineVersion = ReadExecutableProductVersion(baselineExePath);
        var candidateVersion = ReadExecutableProductVersion(candidateExePath);
        if (!Version.TryParse(candidateVersion, out var newVersion) || !Version.TryParse(baselineVersion, out var oldVersion) || newVersion <= oldVersion)
            throw new InvalidOperationException("full-app update test candidate executable must be newer than the baseline executable");

        var root = Path.Combine(TestTempRoot(), "full_app_update_" + Guid.NewGuid().ToString("N"));
        var updates = Path.Combine(TestTempRoot(), "full_app_updates_" + Guid.NewGuid().ToString("N"));
        var app = Path.Combine(root, "app");
        var worker = Path.Combine(app, "worker");
        var model = Path.Combine(worker, "models");
        Directory.CreateDirectory(model);
        Directory.CreateDirectory(Path.Combine(root, "data"));
        Directory.CreateDirectory(updates);

        var baselineExe = File.ReadAllBytes(baselineExePath);
        var candidateExe = File.ReadAllBytes(candidateExePath);
        var baselineExeHash = HashBytes(baselineExe);
        var candidateExeHash = HashBytes(candidateExe);
        File.WriteAllBytes(Path.Combine(root, "VNText Studio.exe"), baselineExe);
        File.WriteAllText(Path.Combine(root, "data", "keep.bin"), "user data remains unchanged");
        File.WriteAllText(Path.Combine(app, "VERSION.txt"), baselineVersion + "\n");
        File.WriteAllText(Path.Combine(app, "RELEASE.json"), JsonSerializer.Serialize(new { version = baselineVersion, sha256 = baselineExeHash }));
        File.WriteAllText(Path.Combine(app, "keep.txt"), "unchanged");
        File.WriteAllText(Path.Combine(worker, "replace.txt"), "baseline content");
        File.WriteAllText(Path.Combine(worker, "obsolete.txt"), "delete this file");
        File.WriteAllText(Path.Combine(model, "pinned.bin"), "model bytes must stay pinned");

        const string sourceSha = "0000000000000000000000000000000000000000";
        const string sourceTreeSha256 = "1111111111111111111111111111111111111111111111111111111111111111";
        var targetBytes = new Dictionary<string, byte[]>(StringComparer.Ordinal)
        {
            ["VNText Studio.exe"] = candidateExe,
            ["app/RELEASE.json"] = Encoding.UTF8.GetBytes(JsonSerializer.Serialize(new
            {
                version = candidateVersion, sha256 = candidateExeHash, source_sha = sourceSha, source_tree_sha256 = sourceTreeSha256,
            })),
            ["app/VERSION.txt"] = Encoding.UTF8.GetBytes(candidateVersion + "\n"),
            ["app/keep.txt"] = Encoding.UTF8.GetBytes("unchanged"),
            ["app/worker/replace.txt"] = Encoding.UTF8.GetBytes("candidate content"),
            ["app/worker/added.txt"] = Encoding.UTF8.GetBytes("new worker file"),
            ["app/worker/models/pinned.bin"] = Encoding.UTF8.GetBytes("model bytes must stay pinned"),
        };
        var baselineBytes = new Dictionary<string, byte[]>(StringComparer.Ordinal)
        {
            ["VNText Studio.exe"] = baselineExe,
            ["app/RELEASE.json"] = File.ReadAllBytes(Path.Combine(app, "RELEASE.json")),
            ["app/VERSION.txt"] = Encoding.UTF8.GetBytes(baselineVersion + "\n"),
            ["app/keep.txt"] = Encoding.UTF8.GetBytes("unchanged"),
            ["app/worker/replace.txt"] = Encoding.UTF8.GetBytes("baseline content"),
            ["app/worker/obsolete.txt"] = Encoding.UTF8.GetBytes("delete this file"),
            ["app/worker/models/pinned.bin"] = Encoding.UTF8.GetBytes("model bytes must stay pinned"),
        };
        static Dictionary<string, object> Records(Dictionary<string, byte[]> files) => files.ToDictionary(
            pair => pair.Key,
            pair => (object)new { sha256 = HashBytes(pair.Value), size = pair.Value.LongLength },
            StringComparer.Ordinal);
        var targetRecords = Records(targetBytes);
        var baseRecords = Records(baselineBytes);
        var addRecords = new Dictionary<string, object>(StringComparer.Ordinal) { ["app/worker/added.txt"] = targetRecords["app/worker/added.txt"] };
        var replaceRecords = new Dictionary<string, object>(StringComparer.Ordinal)
        {
            ["VNText Studio.exe"] = targetRecords["VNText Studio.exe"],
            ["app/RELEASE.json"] = targetRecords["app/RELEASE.json"],
            ["app/VERSION.txt"] = targetRecords["app/VERSION.txt"],
            ["app/worker/replace.txt"] = targetRecords["app/worker/replace.txt"],
        };
        var manifest = new
        {
            schema = 2, kind = "full-app", version = candidateVersion, source_sha = sourceSha,
            source_tree_sha256 = sourceTreeSha256, notes = "test full-app update",
            files = targetRecords, base_files = baseRecords, add_files = addRecords, replace_files = replaceRecords,
            delete_files = new[] { "app/worker/obsolete.txt" },
        };
        var packagePath = Path.Combine(updates, "full-app-update-test.zip");
        using (var archive = ZipFile.Open(packagePath, ZipArchiveMode.Create))
        {
            WriteZipEntry(archive, FullAppUpdateService.PackageManifestName, Encoding.UTF8.GetBytes(JsonSerializer.Serialize(manifest)));
            foreach (var name in addRecords.Keys.Concat(replaceRecords.Keys)) WriteZipEntry(archive, name, targetBytes[name]);
        }
        var sourcePath = Path.Combine(root, ".vntext-update-source.json");
        File.WriteAllText(sourcePath, JsonSerializer.Serialize(new
        {
            updates_root = updates,
            work_root = Path.Combine(root, ".update", "work"),
            backup_root = Path.Combine(root, ".update", "backup"),
            staging_root = Path.Combine(root, ".update", "staging"),
            updater_path = Path.Combine(root, ".update", "updater.exe"),
            log_path = Path.Combine(root, ".update", "update.log"),
            fault_inject_interrupt_after_first_replace = faultInject,
        }));
        var feed = new
        {
            schema = 1, package_file = Path.GetFileName(packagePath), package_sha256 = HashFile(packagePath), manifest,
        };
        File.WriteAllText(Path.Combine(updates, FullAppUpdateService.FeedName), JsonSerializer.Serialize(feed));
        return new FullAppUpdateFixture(root, updates, sourcePath, packagePath, baselineExeHash, candidateExeHash);
    }

    private static void DeleteFullAppUpdateFixture(FullAppUpdateFixture fixture)
    {
        if (Directory.Exists(fixture.Root)) Directory.Delete(fixture.Root, recursive: true);
        if (Directory.Exists(fixture.UpdatesRoot)) Directory.Delete(fixture.UpdatesRoot, recursive: true);
    }

    private static string ReadFullAppUpdateLog(FullAppUpdateFixture fixture)
    {
        var path = Path.Combine(fixture.Root, ".update", "update.log");
        return File.Exists(path) ? File.ReadAllText(path) : "<no updater log>";
    }

    private sealed record FullAppUpdateFixture(string Root, string UpdatesRoot, string SourcePath, string PackagePath,
        string BaselineExeHash, string CandidateExeHash);

    private static UpdateFixture CreateUpdateFixture(
        string? candidateVersion = null,
        bool faultInject = false,
        string? candidateExePathOverride = null)
    {
        var baselineExePath = Environment.GetEnvironmentVariable("VNTEXT_WPF_BASELINE_EXE");
        var candidateExePath = candidateExePathOverride ?? Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE");
        if (string.IsNullOrWhiteSpace(baselineExePath) || !File.Exists(baselineExePath) ||
            string.IsNullOrWhiteSpace(candidateExePath) || !File.Exists(candidateExePath))
            throw new InvalidOperationException("versioned WPF A/B executables are required for updater tests");

        var baselineVersion = ReadExecutableProductVersion(baselineExePath);
        candidateVersion ??= ReadExecutableProductVersion(candidateExePath);

        var root = Path.Combine(TestTempRoot(), "wpf_update_" + Guid.NewGuid().ToString("N"));
        var app = Path.Combine(root, "app");
        var update = Path.Combine(TestTempRoot(), "wpf_updates_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(app);
        Directory.CreateDirectory(Path.Combine(root, "data"));
        File.WriteAllText(Path.Combine(root, "data", "keep.bin"), "user data remains unchanged");

        var baselineExe = File.ReadAllBytes(baselineExePath);
        File.WriteAllBytes(Path.Combine(root, "VNText Studio.exe"), baselineExe);
        var candidateExe = File.ReadAllBytes(candidateExePath);
        var candidateExeHash = HashBytes(candidateExe);
        var baselineExeHash = HashBytes(baselineExe);
        File.WriteAllText(Path.Combine(app, "VERSION.txt"), baselineVersion + "\n");
        var baselineRelease = JsonSerializer.Serialize(new { version = baselineVersion, sha256 = baselineExeHash });
        File.WriteAllText(Path.Combine(app, "RELEASE.json"), baselineRelease);
        var candidateRelease = JsonSerializer.Serialize(new { version = candidateVersion, sha256 = candidateExeHash });
        var candidateVersionBytes = Encoding.UTF8.GetBytes(candidateVersion + "\n");
        var candidateReleaseBytes = Encoding.UTF8.GetBytes(candidateRelease);
        var files = new Dictionary<string, byte[]>(StringComparer.Ordinal)
        {
            ["VNText Studio.exe"] = candidateExe,
            ["app/RELEASE.json"] = candidateReleaseBytes,
            ["app/VERSION.txt"] = candidateVersionBytes,
        };
        var baseFiles = new Dictionary<string, byte[]>(StringComparer.Ordinal)
        {
            ["VNText Studio.exe"] = baselineExe,
            ["app/RELEASE.json"] = Encoding.UTF8.GetBytes(baselineRelease),
            ["app/VERSION.txt"] = Encoding.UTF8.GetBytes(baselineVersion + "\n"),
        };
        var records = files.ToDictionary(pair => pair.Key, pair => new { sha256 = HashBytes(pair.Value), size = pair.Value.LongLength });
        var baseRecords = baseFiles.ToDictionary(pair => pair.Key, pair => new { sha256 = HashBytes(pair.Value), size = pair.Value.LongLength });
        var packageManifest = new { schema = 1, version = candidateVersion, source_sha = new string('0', 40), source_tree_sha256 = (string?)null, notes = "test", files = records, base_files = baseRecords };
        Directory.CreateDirectory(update);
        var package = Path.Combine(update, "wpf-update-test.zip");
        using (var zip = ZipFile.Open(package, ZipArchiveMode.Create))
        {
            WriteZipEntry(zip, "wpf-update-manifest.json", Encoding.UTF8.GetBytes(JsonSerializer.Serialize(packageManifest)));
            foreach (var pair in files)
                WriteZipEntry(zip, pair.Key, pair.Value);
        }
        var sourcePath = Path.Combine(root, ".vntext-update-source.json");
        var source = new
        {
            updates_root = update,
            work_root = Path.Combine(root, ".update", "work"),
            backup_root = Path.Combine(root, ".update", "backup"),
            staging_root = Path.Combine(root, ".update", "staging"),
            updater_path = Path.Combine(root, ".update", "updater.exe"),
            log_path = Path.Combine(root, ".update", "update.log"),
            fault_inject_after_first_replace = faultInject,
        };
        File.WriteAllText(sourcePath, JsonSerializer.Serialize(source));
        var feedPath = Path.Combine(update, "wpf-update-current.json");
        File.WriteAllText(feedPath, JsonSerializer.Serialize(new
        {
            schema = 1,
            package_file = Path.GetFileName(package),
            package_sha256 = HashFile(package),
            manifest = packageManifest,
        }));
        return new UpdateFixture(root, sourcePath, package, feedPath, update, baselineExeHash, candidateExeHash);
    }

    private static string RequiredExecutableProductVersion(string environmentVariable)
    {
        var path = Environment.GetEnvironmentVariable(environmentVariable);
        if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            throw new InvalidOperationException(environmentVariable + " must identify a versioned WPF executable");
        return ReadExecutableProductVersion(path);
    }

    private static string ReadExecutableProductVersion(string path)
    {
        var version = FileVersionInfo.GetVersionInfo(path).ProductVersion?.Split('+', 2)[0].Trim();
        if (string.IsNullOrWhiteSpace(version))
            throw new InvalidOperationException("WPF executable has no ProductVersion: " + path);
        return version;
    }

    private static void DeleteUpdateFixture(UpdateFixture fixture)
    {
        if (Directory.Exists(fixture.Root)) Directory.Delete(fixture.Root, recursive: true);
        if (Directory.Exists(fixture.UpdatesRoot)) Directory.Delete(fixture.UpdatesRoot, recursive: true);
    }

    private static void WriteZipEntry(ZipArchive zip, string name, byte[] bytes)
    {
        var entry = zip.CreateEntry(name, CompressionLevel.Fastest);
        using var stream = entry.Open();
        stream.Write(bytes);
    }

    private static string HashFile(string path) => HashBytes(File.ReadAllBytes(path));

    private static string HashZipEntry(string packagePath, string entryName)
    {
        using var archive = ZipFile.OpenRead(packagePath);
        using var entry = archive.GetEntry(entryName)!.Open();
        using var bytes = new MemoryStream();
        entry.CopyTo(bytes);
        return HashBytes(bytes.ToArray());
    }

    private static string HashBytes(byte[] bytes) => Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();

    private static string TestTempRoot()
    {
        var work = Environment.GetEnvironmentVariable("VNTEXT_WPF_TEST_WORK_ROOT");
        if (string.IsNullOrWhiteSpace(work))
            throw new InvalidOperationException("workflow test work root missing");
        var root = Path.Combine(work, "test-temp");
        Directory.CreateDirectory(root);
        return root;
    }

    private sealed record UpdateFixture(string Root, string SourcePath, string PackagePath, string FeedPath, string UpdatesRoot, string BaselineExeHash, string CandidateExeHash);

    private static void AssertEqual<T>(T expected, T actual)
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
            throw new InvalidOperationException($"expected {expected}, got {actual}");
    }

    private static void AssertTrue(bool value)
    {
        if (!value) throw new InvalidOperationException("assertion failed");
    }

    private static void AssertFalse(bool value)
    {
        if (value) throw new InvalidOperationException("assertion failed");
    }

    private sealed class TestHttpMessageHandler(
        Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> send) : HttpMessageHandler
    {
        public List<Uri> Requests { get; } = [];

        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Requests.Add(request.RequestUri ?? throw new InvalidOperationException("request URI missing"));
            return send(request, cancellationToken);
        }
    }

    private sealed class OversizedJsonStream(long totalLength) : Stream
    {
        private long _position;

        public long TotalLength { get; } = totalLength;
        public long BytesRead => _position;
        public override bool CanRead => true;
        public override bool CanSeek => false;
        public override bool CanWrite => false;
        public override long Length => throw new NotSupportedException();
        public override long Position { get => _position; set => throw new NotSupportedException(); }

        public override int Read(byte[] buffer, int offset, int count) => Read(buffer.AsSpan(offset, count));

        public override int Read(Span<byte> buffer)
        {
            var count = (int)Math.Min(buffer.Length, TotalLength - _position);
            for (var index = 0; index < count; index++)
            {
                var absolute = _position + index;
                buffer[index] = absolute == 0 ? (byte)'[' : absolute == 1 ? (byte)']' : (byte)' ';
            }
            _position += count;
            return count;
        }

        public override ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return ValueTask.FromResult(Read(buffer.Span));
        }

        public override Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken) =>
            Task.FromResult(Read(buffer, offset, count));

        public override void Flush() => throw new NotSupportedException();
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }

    private sealed class FakePathPicker : IPathPickerService
    {
        public string? InputPath { get; set; }
        public string? OutputFolder { get; set; }
        public string? TranslationCsv { get; set; }
        public string? RenpySdkFolder { get; set; }
        public string? PickInputPath() => InputPath;
        public string? PickOutputFolder() => OutputFolder;
        public string? PickTranslationCsvFile() => TranslationCsv;
        public string? PickRenpySdkFolder() => RenpySdkFolder;
        public bool OpenPath(string path) => true;
    }
}
