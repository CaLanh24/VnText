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
    private static int Main(string[] args)
    {
        if (args.Contains("--app-dialog-fixture", StringComparer.Ordinal))
            return RunAppDialogFixture(args);
        if (args.Contains("--image-workspace-fixture", StringComparer.Ordinal))
            return RunImageWorkspaceFixture();

        if (args.Contains("--preferences-only", StringComparer.Ordinal))
        {
            var result=1; var thread=new Thread(() => { try { result=PreferencesTests.Run(); } catch(Exception ex) { Console.Error.WriteLine(ex); } });
            thread.SetApartmentState(ApartmentState.STA); thread.Start(); thread.Join(); return result;
        }

        if (args.Contains("--eta-only", StringComparer.Ordinal))
        {
            var etaFailures = new List<string>();
            Run("WorkerEvent_FormatsNumericEta", WorkerEvent_FormatsNumericEta, etaFailures);
            if (etaFailures.Count == 0)
            {
                Console.WriteLine("Focused ETA boundary checks: PASS (1)");
                return 0;
            }
            foreach (var failure in etaFailures) Console.Error.WriteLine(" - " + failure);
            return 1;
        }

        if (args.Contains("--progress-only", StringComparer.Ordinal))
        {
            var progressFailures = new List<string>();
            Run("Progress_StaleAndTerminalEventsCannotOverwriteOwnedState", Progress_StaleAndTerminalEventsCannotOverwriteOwnedState, progressFailures);
            Run("WorkerEvent_ParsesCancelAcknowledgement", WorkerEvent_ParsesCancelAcknowledgement, progressFailures);
            Run("CancelAcknowledgementAndTimeout_AreVisibleInTranslateCard", CancelAcknowledgementAndTimeout_AreVisibleInTranslateCard, progressFailures);
            Run("TranslateCancellationPayload_WinsErrorRaceAndClearsStaleProgress", TranslateCancellationPayload_WinsErrorRaceAndClearsStaleProgress, progressFailures);
            Run("WorkerExitCompletion_CancelAndExitWaitsAndStaleErrorIsIgnored", WorkerExitCompletion_CancelAndExitWaitsAndStaleErrorIsIgnored, progressFailures);
            Run("WorkerHost_ErrorKeepsTaskOwnerUntilActualProcessExit", WorkerHost_ErrorKeepsTaskOwnerUntilActualProcessExit, progressFailures);
            Run("CancelAndExit_CancelledTerminalRequestsExitOnce", CancelAndExit_CancelledTerminalRequestsExitOnce, progressFailures);
            Run("OrdinaryFailureTerminal_IsNotPresentedAsCancellation", OrdinaryFailureTerminal_IsNotPresentedAsCancellation, progressFailures);
            Run("CancelAndExitCommand_FollowsBusyLifecycle", CancelAndExitCommand_FollowsBusyLifecycle, progressFailures);
            Run("CancelledTranslate_ReportsMeasuredSafeCountsWithoutErrorLog", CancelledTranslate_ReportsMeasuredSafeCountsWithoutErrorLog, progressFailures);
            Run("CsvPickers_UseContextSpecificTitles", CsvPickers_UseContextSpecificTitles, progressFailures);
            Run("CancelledTranslate_KeepsThePickedCsvAndRestoresReadiness", CancelledTranslate_KeepsThePickedCsvAndRestoresReadiness, progressFailures);
            Run("RetryAfterCancel_StaleTerminalCannotEndRetryOrRequestExit", RetryAfterCancel_StaleTerminalCannotEndRetryOrRequestExit, progressFailures);
            if (progressFailures.Count == 0)
            {
                Console.WriteLine("Focused task lifecycle checks: PASS (13)");
                return 0;
            }
            foreach (var failure in progressFailures) Console.Error.WriteLine(" - " + failure);
            return 1;
        }

        if (args.Contains("--csv-editor-only", StringComparer.Ordinal))
        {
            var csvFailures = new List<string>();
            Run("CsvEditor_SearchFiltersRows", CsvEditor_SearchFiltersRows, csvFailures);
            Run("CsvEditor_LoadSaveRoundtrip", CsvEditor_LoadSaveRoundtrip, csvFailures);
            Run("CsvEditor_SaveAsyncKeepsDispatcherResponsiveAndCoalesces", CsvEditor_SaveAsyncKeepsDispatcherResponsiveAndCoalesces, csvFailures);
            Run("CsvEditor_SaveExternalEditFailsClosedAndKeepsDirty", CsvEditor_SaveExternalEditFailsClosedAndKeepsDirty, csvFailures);
            Run("CsvEditor_BusyTaskLocksEditingAndRefusesDirectSave", CsvEditor_BusyTaskLocksEditingAndRefusesDirectSave, csvFailures);
            Run("CsvEditor_ValidationTextReturnsToFriendlySummaryAfterSave", CsvEditor_ValidationTextReturnsToFriendlySummaryAfterSave, csvFailures);
            Run("CsvEditor_MultilineRecordsRoundtrip", CsvEditor_MultilineRecordsRoundtrip, csvFailures);
            Run("CsvEditor_RetranslateSaveFailureKeepsEditsAndStops", CsvEditor_RetranslateSaveFailureKeepsEditsAndStops, csvFailures);
            Run("CsvEditor_RetranslateSaveSuccessContinues", CsvEditor_RetranslateSaveSuccessContinues, csvFailures);
            Run("CsvEditor_RetranslateNoContinuesWithoutSaving", CsvEditor_RetranslateNoContinuesWithoutSaving, csvFailures);
            Run("CsvEditor_RetranslateCancelStopsWithoutSaving", CsvEditor_RetranslateCancelStopsWithoutSaving, csvFailures);
            Run("CsvEditor_DuplicateKeysReported", CsvEditor_DuplicateKeysReported, csvFailures);
            Run("CsvEditor_ClearBlockedBackup", CsvEditor_ClearBlockedBackup, csvFailures);
            if (csvFailures.Count == 0)
            {
                Console.WriteLine("Focused CSV editor protection checks: PASS (13)");
                return 0;
            }
            foreach (var failure in csvFailures) Console.Error.WriteLine(" - " + failure);
            return 1;
        }

        if (args.Contains("--renpy-sdk-only", StringComparer.Ordinal))
        {
            var sdkFailures = new List<string>();
            Run("RenpyGameDetector_RequiresCredibleRecoveryEvidence", RenpyGameDetector_RequiresCredibleRecoveryEvidence, sdkFailures);
            Run("RenpySdkOptionsVisibility_FollowsSelectedGame", RenpySdkOptionsVisibility_FollowsSelectedGame, sdkFailures);
            Run("RenpySdkMissing_ReportsPartialExtraction", RenpySdkMissing_ReportsPartialExtraction, sdkFailures);
            if (sdkFailures.Count == 0)
            {
                Console.WriteLine("Focused Ren'Py SDK recovery checks: PASS (3)");
                return 0;
            }
            foreach (var failure in sdkFailures) Console.Error.WriteLine(" - " + failure);
            return 1;
        }

        if (args.Contains("--translate-readiness-only", StringComparer.Ordinal))
        {
            var readinessFailures = new List<string>();
            Run("TranslateCommand_RequiresValidatedPackageReadiness", TranslateCommand_RequiresValidatedPackageReadiness, readinessFailures);
            Run("TranslateCsvSelection_AllBlankExtractPackageIsReadyForTranslation", TranslateCsvSelection_AllBlankExtractPackageIsReadyForTranslation, readinessFailures);
            Run("ExtractComplete_NavigatesToTranslate", ExtractComplete_NavigatesToTranslate, readinessFailures);
            if (readinessFailures.Count == 0)
            {
                Console.WriteLine("Focused translate readiness checks: PASS (2)");
                return 0;
            }
            foreach (var failure in readinessFailures) Console.Error.WriteLine(" - " + failure);
            return 1;
        }

        if (args.Contains("--updater-presentation-fixture", StringComparer.Ordinal))
        {
            var code = 1;
            var thread = new Thread(() => { try { code = RunPresentationFixture(args); } catch (Exception ex) { Console.Error.WriteLine(ex); } });
            thread.SetApartmentState(ApartmentState.STA); thread.Start(); thread.Join(); return code;
        }

        if (args.Contains("--native-update-ui", StringComparer.Ordinal))
        {
            var code = 1;
            var thread = new Thread(() =>
            {
                try { code = RunNativeUpdateUi(layoutOnly: args.Contains("--layout-only", StringComparer.Ordinal)); }
                catch (Exception ex) { Console.Error.WriteLine(ex); }
            });
            thread.SetApartmentState(ApartmentState.STA);
            thread.Start(); thread.Join();
            return code;
        }
        var failures = new List<string>();
        Run("ReviewedMemory_ExplicitSelectionCancelAndState", ReviewedMemory_ExplicitSelectionCancelAndState, failures);
        Run("UpdaterPresentation_DynamicStatesAndSafeActions", UpdaterPresentation_DynamicStatesAndSafeActions, failures);
        if (args.Contains("--full-app-update-only", StringComparer.Ordinal))
        {
            Run("FullAppUpdate_AppliesAddReplaceDeleteAndKeepsDataAndModel", FullAppUpdate_AppliesAddReplaceDeleteAndKeepsDataAndModel, failures);
            Run("FullAppUpdate_HealthFailureRollsBack", FullAppUpdate_HealthFailureRollsBack, failures);
            Run("FullAppUpdate_InterruptedTransactionRecovers", FullAppUpdate_InterruptedTransactionRecovers, failures);
            Run("FullAppUpdate_TamperAndBaselineMismatchFailClosed", FullAppUpdate_TamperAndBaselineMismatchFailClosed, failures);
            Run("FullAppUpdate_Retries1175AgainstExactPreState", FullAppUpdate_Retries1175AgainstExactPreState, failures);
            Run("FullAppUpdate_Persistent1175RollsBack", FullAppUpdate_Persistent1175RollsBack, failures);
            Run("FullAppUpdate_1175RefusesChangedStagedAndTarget", FullAppUpdate_1175RefusesChangedStagedAndTarget, failures);
            Run("FullAppUpdate_GitHubAssetPathSizeAndHashAreBound", FullAppUpdate_GitHubAssetPathSizeAndHashAreBound, failures);
        Run("FullAppUpdate_BaselineRoutesChooseVerifiedHop", FullAppUpdate_BaselineRoutesChooseVerifiedHop, failures);
            Run("FullAppUpdate_RouteUpdaterCleansEveryOwnedPackageOnHashFailure", FullAppUpdate_RouteUpdaterCleansEveryOwnedPackageOnHashFailure, failures);
            if (failures.Count == 0)
            {
                Console.WriteLine("Focused full-app updater tests: PASS (9)");
                return 0;
            }
            Console.Error.WriteLine($"Focused full-app updater tests: FAIL ({failures.Count})");
            foreach (var f in failures) Console.Error.WriteLine(" - " + f);
            return 1;
        }
        if (args.Contains("--github-handoff-only", StringComparer.Ordinal))
        {
            Run("WpfUpdate_GitHubHandedOffCandidateSurvivesOwnerDispose", WpfUpdate_GitHubHandedOffCandidateSurvivesOwnerDispose, failures);
            Run("WpfUpdate_GitHubRetries1175AgainstExactPreState", WpfUpdate_GitHubRetries1175AgainstExactPreState, failures);
            Run("WpfUpdate_GitHubRetryRefusesChangedInputsAndBoundsPersistent1175", WpfUpdate_GitHubRetryRefusesChangedInputsAndBoundsPersistent1175, failures);
            if (failures.Count == 0)
            {
                Console.WriteLine("Focused GitHub handoff/retry tests: PASS (3)");
                return 0;
            }
            Console.Error.WriteLine($"Focused GitHub handoff/retry tests: FAIL ({failures.Count})");
            foreach (var failure in failures) Console.Error.WriteLine(" - " + failure);
            return 1;
        }
        Run("NoGame_CurrentIsExtract", NoGame_CurrentIsExtract, failures);
        Run("JournalStore_BoundsHistorySearchSeverityAndClear", JournalStore_BoundsHistorySearchSeverityAndClear, failures);
        Run("Journal_RoutesProgressAndErrorsWithoutCrossTabLeak", Journal_RoutesProgressAndErrorsWithoutCrossTabLeak, failures);
        Run("Progress_StaleAndTerminalEventsCannotOverwriteOwnedState", Progress_StaleAndTerminalEventsCannotOverwriteOwnedState, failures);
        Run("WorkerEvent_ParsesCancelAcknowledgement", WorkerEvent_ParsesCancelAcknowledgement, failures);
        Run("CancelAcknowledgementAndTimeout_AreVisibleInTranslateCard", CancelAcknowledgementAndTimeout_AreVisibleInTranslateCard, failures);
        Run("TranslateCancellationPayload_WinsErrorRaceAndClearsStaleProgress", TranslateCancellationPayload_WinsErrorRaceAndClearsStaleProgress, failures);
        Run("WorkerExitCompletion_CancelAndExitWaitsAndStaleErrorIsIgnored", WorkerExitCompletion_CancelAndExitWaitsAndStaleErrorIsIgnored, failures);
        Run("WorkerHost_ErrorKeepsTaskOwnerUntilActualProcessExit", WorkerHost_ErrorKeepsTaskOwnerUntilActualProcessExit, failures);
        Run("CancelAndExit_CancelledTerminalRequestsExitOnce", CancelAndExit_CancelledTerminalRequestsExitOnce, failures);
        Run("OrdinaryFailureTerminal_IsNotPresentedAsCancellation", OrdinaryFailureTerminal_IsNotPresentedAsCancellation, failures);
        Run("CancelAndExitCommand_FollowsBusyLifecycle", CancelAndExitCommand_FollowsBusyLifecycle, failures);
        Run("CancelledTranslate_ReportsMeasuredSafeCountsWithoutErrorLog", CancelledTranslate_ReportsMeasuredSafeCountsWithoutErrorLog, failures);
        Run("CsvPickers_UseContextSpecificTitles", CsvPickers_UseContextSpecificTitles, failures);
        Run("CancelledTranslate_KeepsThePickedCsvAndRestoresReadiness", CancelledTranslate_KeepsThePickedCsvAndRestoresReadiness, failures);
        Run("RetryAfterCancel_StaleTerminalCannotEndRetryOrRequestExit", RetryAfterCancel_StaleTerminalCannotEndRetryOrRequestExit, failures);
        Run("RenpyGameDetector_RequiresCredibleRecoveryEvidence", RenpyGameDetector_RequiresCredibleRecoveryEvidence, failures);
        Run("RenpySdkOptionsVisibility_FollowsSelectedGame", RenpySdkOptionsVisibility_FollowsSelectedGame, failures);
        Run("RenpySdkRecovery_StatusRequiresSuccessfulEvidence", RenpySdkRecovery_StatusRequiresSuccessfulEvidence, failures);
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
        Run("WorkerEvent_FormatsNumericEta", WorkerEvent_FormatsNumericEta, failures);
        Run("PatchDelivery_RoutesRenPyInstructions", PatchDelivery_RoutesRenPyInstructions, failures);
        Run("PartialPackage_TranslateNotComplete", PartialPackage_TranslateNotComplete, failures);
        Run("BlockedCompletion_IsNotAccepted", BlockedCompletion_IsNotAccepted, failures);
        Run("NavigateTab_ChangesSelectedTab", NavigateTab_ChangesSelectedTab, failures);
        Run("ExtractComplete_NavigatesToTranslate", ExtractComplete_NavigatesToTranslate, failures);
        Run("ImageText_ReviewAndApprovalStayIndependent", ImageText_ReviewAndApprovalStayIndependent, failures);
        Run("ImageText_EditInvalidatesApproval", ImageText_EditInvalidatesApproval, failures);
        Run("ExtractPartialAndEmpty_DoNotAdvance", ExtractPartialAndEmpty_DoNotAdvance, failures);
        Run("ExternalCsv_ValidatesReadyForPatch", ExternalCsv_ValidatesReadyForPatch, failures);
        Run("CsvValidator_RejectsEmptyTranslation", CsvValidator_RejectsEmptyTranslation, failures);
        Run("TranslateComplete_NavigatesToPatch", TranslateComplete_NavigatesToPatch, failures);
        Run("ExtractLevel_Persists", ExtractLevel_Persists, failures);
        Run("PatchPreflight_BlocksGarbage", PatchPreflight_BlocksGarbage, failures);
        Run("PatchPreflight_AllowsCleanRow", PatchPreflight_AllowsCleanRow, failures);
        Run("NavigateTab_EditCsv", NavigateTab_EditCsv, failures);
        Run("CsvEditor_SearchFiltersRows", CsvEditor_SearchFiltersRows, failures);
        Run("CsvEditor_LoadSaveRoundtrip", CsvEditor_LoadSaveRoundtrip, failures);
        Run("CsvEditor_SaveAsyncKeepsDispatcherResponsiveAndCoalesces", CsvEditor_SaveAsyncKeepsDispatcherResponsiveAndCoalesces, failures);
        Run("CsvEditor_SaveExternalEditFailsClosedAndKeepsDirty", CsvEditor_SaveExternalEditFailsClosedAndKeepsDirty, failures);
        Run("CsvEditor_BusyTaskLocksEditingAndRefusesDirectSave", CsvEditor_BusyTaskLocksEditingAndRefusesDirectSave, failures);
        Run("CsvEditor_ValidationTextReturnsToFriendlySummaryAfterSave", CsvEditor_ValidationTextReturnsToFriendlySummaryAfterSave, failures);
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
        Run("Analyze_InputChangeMarksResultStaleAndRejectsLateEvent", Analyze_InputChangeMarksResultStaleAndRejectsLateEvent, failures);
        Run("CsvEditor_RefreshesOnlyACleanMatchingEditorAfterTranslate", CsvEditor_RefreshesOnlyACleanMatchingEditorAfterTranslate, failures);
        Run("Copy_NoCsvChosenIsActionableAndSdkDownloadIsLabelled", Copy_NoCsvChosenIsActionableAndSdkDownloadIsLabelled, failures);
        Run("CsvEditor_BulkOperationsRunOffTheUiThread", CsvEditor_BulkOperationsRunOffTheUiThread, failures);
        Run("CsvEditor_BulkPreviewForOldInputsIsDiscarded", CsvEditor_BulkPreviewForOldInputsIsDiscarded, failures);
        Run("OcrOnlyPackage_TranslateCardPointsToTheImageStep", OcrOnlyPackage_TranslateCardPointsToTheImageStep, failures);
        Run("WindowGeometry_FitsNarrowShortAndHighDpiWorkAreas", WindowGeometry_FitsNarrowShortAndHighDpiWorkAreas, failures);
        Run("ImagePackageProbe_ToleratesMalformedReportsWithoutThrowing", ImagePackageProbe_ToleratesMalformedReportsWithoutThrowing, failures);
        Run("ImagePackageProbe_SelectionIsDeterministicAndBounded", ImagePackageProbe_SelectionIsDeterministicAndBounded, failures);
        Run("OcrOnlyPackage_MalformedReportNeverReachesTheGetterAsAnException", OcrOnlyPackage_MalformedReportNeverReachesTheGetterAsAnException, failures);
        Run("ContentDisclosure_InitialIsQuietAndFailuresExpand", ContentDisclosure_InitialIsQuietAndFailuresExpand, failures);
        Run("CloudRepairPackage_IsShownOnlyAfterSuccessfulExport", CloudRepairPackage_IsShownOnlyAfterSuccessfulExport, failures);
        Run("ReleaseManagedPaths_StayUnderInstallRoot", ReleaseManagedPaths_StayUnderInstallRoot, failures);
        Run("WpfUpdate_VersionOrderRejectsInvalidAndNonIncreasing", WpfUpdate_VersionOrderRejectsInvalidAndNonIncreasing, failures);
        Run("WpfUpdate_ReadsVersionBeyondMaxPath", WpfUpdate_ReadsVersionBeyondMaxPath, failures);
        Run("WpfUpdate_InvalidOfferIsHiddenAndRejected", WpfUpdate_InvalidOfferIsHiddenAndRejected, failures);
        Run("WpfUpdate_FaultThenRetryIgnoresPriorStagingAndBackup", WpfUpdate_FaultThenRetryIgnoresPriorStagingAndBackup, failures);
        Run("FullAppUpdate_AppliesAddReplaceDeleteAndKeepsDataAndModel", FullAppUpdate_AppliesAddReplaceDeleteAndKeepsDataAndModel, failures);
        Run("FullAppUpdate_HealthFailureRollsBack", FullAppUpdate_HealthFailureRollsBack, failures);
        Run("FullAppUpdate_InterruptedTransactionRecovers", FullAppUpdate_InterruptedTransactionRecovers, failures);
        Run("FullAppUpdate_TamperAndBaselineMismatchFailClosed", FullAppUpdate_TamperAndBaselineMismatchFailClosed, failures);
        Run("FullAppUpdate_Retries1175AgainstExactPreState", FullAppUpdate_Retries1175AgainstExactPreState, failures);
        Run("FullAppUpdate_Persistent1175RollsBack", FullAppUpdate_Persistent1175RollsBack, failures);
        Run("FullAppUpdate_1175RefusesChangedStagedAndTarget", FullAppUpdate_1175RefusesChangedStagedAndTarget, failures);
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
        Run("WpfUpdate_GitHubRetries1175AgainstExactPreState", WpfUpdate_GitHubRetries1175AgainstExactPreState, failures);
        Run("WpfUpdate_GitHubRetryRefusesChangedInputsAndBoundsPersistent1175", WpfUpdate_GitHubRetryRefusesChangedInputsAndBoundsPersistent1175, failures);
        Run("WpfUpdate_GitHubRedirectsOnlyToTrustedCdn", WpfUpdate_GitHubRedirectsOnlyToTrustedCdn, failures);

        if (failures.Count == 0)
        {
            Console.WriteLine($"WPF workflow tests: PASS ({_executed})");
            return 0;
        }

        Console.Error.WriteLine($"WPF workflow tests: FAIL ({failures.Count})");
        foreach (var f in failures)
            Console.Error.WriteLine(" - " + f);
        return 1;
    }

    private static int _executed;
    private static void Run(string name, Action test, List<string> failures)
    {
        _executed++;
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

    private static void JournalStore_BoundsHistorySearchSeverityAndClear()
    {
        var root=CreatePackage(withTranslation:false,withPatch:false);
        try
        {
            var store=new AppJournalStore(Path.Combine(root,"logs"));
            store.Append("Started fixture");store.Append("[warning] caution fixture");store.Append("Lỗi fixture [a.b]");
            AssertEqual("INFO", AppJournalStore.Level("Unity analyzer: NOT_DETECTED; resources=2; unknown=0; scan_errors=0"));
            AssertEqual("ERROR", AppJournalStore.Level("Unity analyzer: NOT_DETECTED; resources=2; unknown=0; scan_errors=1"));
            AssertEqual("ERROR", AppJournalStore.Level("Lỗi quét fixture"));
            var file=store.Files().Single();var text=store.Read(file);
            AssertEqual(3,AppJournalStore.Filter(text,"","ALL",false).Length);
            AssertEqual(1,AppJournalStore.Filter(text,"","ERROR",false).Length);
            AssertEqual(1,AppJournalStore.Filter(text,"CAUTION","WARN",false).Length);
            AssertEqual(1,AppJournalStore.Filter(text,"[a.b]","ALL",false).Length);
            AssertEqual(1,AppJournalStore.Filter(text,"Started.*fixture","INFO",true).Length);
            var refused=false;try{store.Read("../owner.csv");}catch(IOException){refused=true;}AssertTrue(refused);
            refused=false;try{AppJournalStore.Filter(text,"[","ALL",true);}catch(ArgumentException){refused=true;}AssertTrue(refused);
            for(var i=0;i<300;i++)store.Append(new string('x',4000));
            AssertTrue(store.Files().Length>=2);
            AssertTrue(store.Files().All(f=>new FileInfo(store.FilePath(f)).Length<=AppJournalStore.MaxFileBytes));
            var other=store.Files().First(f=>f!=file);var preserved=store.Read(other);
            var count=store.Files().Length;store.Clear(file);AssertFalse(File.Exists(store.FilePath(file)));AssertEqual(count-1,store.Files().Length);AssertEqual(preserved,store.Read(other));
            using var vm=new MainViewModel(new FakePathPicker(),new PythonWorkerHost(),startWorker:false);
            var before=vm.SelectedTab;var opened=0;vm.JournalRequested+=()=>opened++;
            vm.NavigateTab(WorkflowTabs.Journal);AssertEqual(1,opened);AssertEqual(before,vm.SelectedTab);
        }
        finally{Directory.Delete(root,true);}
    }

    private static void Journal_RoutesProgressAndErrorsWithoutCrossTabLeak()
    {
        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker:false);
        vm.TestBeginTaskLog("extract-log", "extract");
        vm.TestBeginTaskLog("translate-log", "translate");
        vm.TestBeginTaskLog("patch-log", "patch");
        vm.NavigateTab(WorkflowTabs.Journal);
        AssertEqual("Nhật ký",vm.HeroTitle);
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="progress", Id="extract-log",Done=1,Total=10,Step="Extract fixture" });
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="progress", Id="translate-log",Done=2,Total=10,Step="Translate fixture" });
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="progress", Id="patch-log",Done=3,Total=10,Step="Patch fixture" });
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="log", Id="extract-log",Text="[stderr] diagnostic fixture" });
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="error", Id="patch-log",Error="journal-error-fixture" });
        AssertTrue(vm.ExtractLogLines.Any(s=>s.Contains("Extract fixture")));
        AssertTrue(vm.TranslateLogLines.Any(s=>s.Contains("Translate fixture")));
        AssertTrue(vm.PatchLogLines.Any(s=>s.Contains("Patch fixture")));
        AssertFalse(vm.ExtractLogLines.Concat(vm.TranslateLogLines).Concat(vm.PatchLogLines).Any(s=>s.Contains("diagnostic fixture")||s.Contains("journal-error-fixture")));
        AssertFalse(vm.TranslateLogLines.Any(s=>s.Contains("Extract fixture")));
        AssertFalse(vm.PatchLogLines.Any(s=>s.Contains("Translate fixture")));
        AssertTrue(vm.LogLines.Any(s=>s.Contains("journal-error-fixture")));
        AssertTrue(vm.LogLines.Any(s=>s.Contains("diagnostic fixture")));
        vm.RecordAppError(new InvalidOperationException("ui-exception-fixture"));
        AssertTrue(vm.LogLines.Any(s=>s.Contains("ui-exception-fixture")));
        vm.NavigateTab(WorkflowTabs.Settings);
        for(var i=0;i<210;i++) vm.TestHandleWorkerEvent(new WorkerEvent {Type="progress",Id="extract-log",Done=i,Total=300,Item=$"item-{i}"});
        AssertEqual(200,vm.ExtractLogLines.Count);
        for(var i=0;i<1010;i++) vm.TestHandleWorkerEvent(new WorkerEvent {Type="log",Text=$"bounded-{i}"});
        AssertEqual(1000,vm.LogLines.Count);
        AssertFalse(vm.TranslateLogLines.Any(s=>s.Contains("item-")));
    }

    private static void Progress_StaleAndTerminalEventsCannotOverwriteOwnedState()
    {
        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker:false);
        vm.TestBeginTaskLog("old-extract", "extract");
        vm.TestSetActiveTask("current-translate", "translate");
        AssertTrue(vm.TranslateProgressActive);
        AssertFalse(vm.ExtractProgressActive);
        AssertFalse(vm.PatchProgressActive);
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="progress", Id="old-extract", Done=9, Total=10, Step="stale" });
        AssertEqual(0, vm.TranslateProgressPercent);
        AssertEqual(0, vm.ExtractProgressPercent);
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="progress", Id="current-translate", Done=3, Total=4, Step="current" });
        AssertEqual(75, vm.TranslateProgressPercent);
        AssertFalse(vm.TranslateProgressHasEta);
        AssertEqual("", vm.TranslateProgressEta);
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="progress", Id="current-translate", Done=3, Total=4, Step="current", Eta="3661" });
        AssertTrue(vm.TranslateProgressHasEta);
        AssertEqual("1 giờ 1 phút", vm.TranslateProgressEta);
        vm.TestReportCancelTimeout("old-extract");
        AssertEqual("Sẵn sàng", vm.StatusText);
        vm.TestReportCancelTimeout("current-translate");
        AssertTrue(vm.StatusText.Contains("chờ tác vụ dừng an toàn", StringComparison.Ordinal));
        AssertTrue(vm.ProgressSubtitle.Contains("30 giây", StringComparison.Ordinal));
        AssertTrue(vm.TranslateWorkflowStatusText.Contains("30 giây", StringComparison.Ordinal));
        var terminalText = vm.TranslateProgressSubtitle;
        vm.TestMarkTaskTerminal("current-translate");
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="progress", Id="current-translate", Done=4, Total=4, Step="late" });
        AssertEqual(75, vm.TranslateProgressPercent);
        AssertEqual(terminalText, vm.TranslateProgressSubtitle);

        // Translate fields are a retained snapshot. Extract and Patch events must not
        // rewrite that snapshot after the Translate task has finished.
        var translateStep = vm.TranslateProgressStep;
        var translateItem = vm.TranslateProgressItem;
        var translateEta = vm.TranslateProgressEta;
        vm.TestSetActiveTask("next-extract", "extract");
        AssertTrue(vm.ExtractProgressActive);
        AssertFalse(vm.TranslateProgressActive);
        AssertFalse(vm.PatchProgressActive);
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="progress", Id="next-extract", Done=8, Total=10, Step="Extract next", Item="file.rpy", Eta="12" });
        AssertEqual("Extract next", vm.ExtractProgressStep);
        AssertEqual("file.rpy", vm.ExtractProgressItem);
        AssertEqual("12 giây", vm.ExtractProgressEta);
        AssertTrue(vm.ExtractProgressHasEta);
        AssertEqual(translateStep, vm.TranslateProgressStep);
        AssertEqual(translateItem, vm.TranslateProgressItem);
        AssertEqual(translateEta, vm.TranslateProgressEta);
        vm.TestMarkTaskTerminal("next-extract");
        vm.TestSetActiveTask("next-patch", "patch");
        AssertTrue(vm.PatchProgressActive);
        AssertFalse(vm.ExtractProgressActive);
        AssertFalse(vm.TranslateProgressActive);
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="progress", Id="next-patch", Done=9, Total=10, Step="Patch next", Item="game.rpy" });
        AssertEqual("Patch next", vm.PatchProgressStep);
        AssertEqual("game.rpy", vm.PatchProgressItem);
        AssertFalse(vm.PatchProgressHasEta);
        AssertEqual(translateStep, vm.TranslateProgressStep);
        AssertEqual(translateItem, vm.TranslateProgressItem);
        AssertEqual(translateEta, vm.TranslateProgressEta);

        vm.TestSetActiveTask("renpy-extract", "extract");
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="progress", Id="renpy-extract", Done=99, Total=100, Step="unity_classify", Item="game/script.rpy" });
        AssertEqual("Đang phân loại tài nguyên để lấy text", vm.ExtractProgressStep);
        AssertTrue(vm.ProgressSubtitle.Contains("Đang phân loại tài nguyên để lấy text", StringComparison.Ordinal));
        AssertFalse(vm.ProgressSubtitle.Contains("unity_classify", StringComparison.Ordinal));

        // A subsequent Translate owns and resets its own progress fields.
        vm.TestMarkTaskTerminal("next-patch");
        AssertFalse(vm.PatchProgressActive);
        vm.TestSetActiveTask("next-translate", "translate");
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="progress", Id="next-translate", Done=1, Total=2, Step="Translate again", Item="row 1" });
        AssertEqual("Translate again", vm.TranslateProgressStep);
        AssertEqual("row 1", vm.TranslateProgressItem);
        AssertFalse(vm.TranslateProgressHasEta);
        AssertEqual("", vm.TranslateProgressEta);
    }

    private static void WorkerEvent_ParsesCancelAcknowledgement()
    {
        var evt = WorkerEvent.FromJson("{\"v\":1,\"type\":\"cancel_ack\",\"id\":\"task-cancel-fixture\",\"state\":\"accepted\"}");
        AssertTrue(evt is not null);
        AssertEqual("cancel_ack", evt!.Type);
        AssertEqual("task-cancel-fixture", evt.Id);
        AssertEqual("accepted", evt.State);
    }

    private static void CancelAcknowledgementAndTimeout_AreVisibleInTranslateCard()
    {
        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker:false);
        vm.TestBeginTaskLog("cancel-visible", "translate");
        vm.TestSetActiveTask("cancel-visible", "translate");
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="cancel_ack", Id="cancel-visible", State="accepted" });
        AssertTrue(vm.TranslateWorkflowStatusText.Contains("đã nhận yêu cầu hủy", StringComparison.OrdinalIgnoreCase));
        AssertTrue(vm.LogLines.Any(line => line.Contains("Worker đã nhận yêu cầu hủy", StringComparison.Ordinal)));
        vm.TestReportCancelTimeout("cancel-visible");
        AssertTrue(vm.TranslateWorkflowStatusText.Contains("30 giây", StringComparison.Ordinal));
        AssertTrue(vm.TranslateWorkflowStatusText.Contains("không đóng ứng dụng cưỡng bức", StringComparison.Ordinal));
    }

    private static void TranslateCancellationPayload_WinsErrorRaceAndClearsStaleProgress()
    {
        const string payload = "{\"v\":1,\"type\":\"complete\",\"id\":\"translate-cancelled\",\"ok\":false,\"summary\":\"\",\"error\":\"cancelled\",\"complete\":false,\"pending\":1,\"review_only\":1,\"blocked\":1,\"translated\":0,\"diagnostic_stage\":\"WORKFLOW\",\"diagnostic_root_cause\":\"UNKNOWN\",\"diagnostic_affected_count\":1,\"diagnostic_action\":\"A task was cancelled or interrupted; inspect its saved checkpoint before retrying.\",\"diagnostic_status\":\"FAILED\"}";
        var terminal = WorkerEvent.FromJson(payload);
        AssertTrue(terminal is not null);
        AssertEqual("cancelled", terminal!.Error);

        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
        var notifications = new List<CompletionNotification>();
        vm.CompletionRequested += (_, notification) => notifications.Add(notification);
        vm.TestBeginTaskLog("translate-cancelled", "translate");
        vm.TestSetActiveTask("translate-cancelled", "translate");
        vm.TestHandleWorkerEvent(new WorkerEvent
        {
            Type = "progress", Id = "translate-cancelled", Done = 1, Total = 2,
            Step = "Đang dịch offline", Item = "2/2", Eta = "00:30",
        });
        vm.TestHandleWorkerEvent(new WorkerEvent
        {
            Type = "cancel_ack", Id = "translate-cancelled", State = "accepted",
        });
        vm.TestHandleWorkerEvent(new WorkerEvent
        {
            Type = "error", Id = "translate-cancelled", Error = "Tác vụ thất bại",
        });
        vm.TestHandleWorkerEvent(terminal);

        AssertFalse(vm.Busy);
        AssertEqual("Đã hủy", vm.StatusText);
        AssertTrue(vm.StepStatusLine.Contains("Đã hủy tác vụ", StringComparison.Ordinal));
        AssertEqual("Đã hủy", vm.TranslateProgressStep);
        AssertEqual("—", vm.TranslateProgressItem);
        AssertEqual("", vm.TranslateProgressEta);
        AssertEqual(1, notifications.Count);
        AssertEqual("info", notifications[0].Kind);
        AssertEqual("Đã hủy tác vụ.", notifications[0].Message);
    }

    private static void WorkerExitCompletion_CancelAndExitWaitsAndStaleErrorIsIgnored()
    {
        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker:false);
        vm.TestSetActiveTask("crashed-task", "translate");
        var exitRequests = 0;
        vm.ExitAfterTaskRequested += (_, _) => exitRequests++;
        vm.TestBeginCancelAndExit();
        AssertTrue(vm.Busy);
        AssertEqual(0, exitRequests);

        var activeStatus = vm.StatusText;
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="error", Id="old-task", Error="Worker process exited" });
        AssertTrue(vm.Busy);
        AssertEqual(activeStatus, vm.StatusText);
        AssertEqual(0, exitRequests);

        vm.TestHandleWorkerEvent(new WorkerEvent { Type="complete", Id="crashed-task", Ok=false, Complete=false, Error="Worker process exited unexpectedly" });
        AssertFalse(vm.Busy);
        AssertEqual(1, exitRequests);
        var terminalStatus = vm.StatusText;
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="error", Id="crashed-task", Error="Worker process exited" });
        AssertEqual(terminalStatus, vm.StatusText);
        AssertEqual(1, exitRequests);
    }

    private static void CancelAndExit_CancelledTerminalRequestsExitOnce()
    {
        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker:false);
        vm.TestBeginTaskLog("exit-cancelled", "translate");
        vm.TestSetActiveTask("exit-cancelled", "translate");
        var exitRequests = 0;
        vm.ExitAfterTaskRequested += (_, _) => exitRequests++;
        vm.TestBeginCancelAndExit();
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="cancel_ack", Id="exit-cancelled", State="accepted" });
        AssertTrue(vm.Busy);
        AssertEqual(0, exitRequests);

        vm.TestHandleWorkerEvent(new WorkerEvent { Type="complete", Id="exit-cancelled", Ok=false, Complete=false, Error="cancelled" });
        AssertFalse(vm.Busy);
        AssertEqual("Đã hủy", vm.StatusText);
        AssertEqual(1, exitRequests);
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="complete", Id="exit-cancelled", Ok=false, Complete=false, Error="cancelled" });
        AssertEqual(1, exitRequests);
    }

    private static void CancelAndExitCommand_FollowsBusyLifecycle()
    {
        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker:false);
        var cancelEvents = 0;
        var exitEvents = 0;
        vm.CancelCommand.CanExecuteChanged += (_, _) => cancelEvents++;
        vm.CancelAndExitCommand.CanExecuteChanged += (_, _) => exitEvents++;
        AssertFalse(vm.CancelCommand.CanExecute(null));
        AssertFalse(vm.CancelAndExitCommand.CanExecute(null));

        vm.TestSetActiveTask("busy-task", "translate");
        AssertTrue(vm.CancelCommand.CanExecute(null));
        AssertTrue(vm.CancelAndExitCommand.CanExecute(null));
        AssertEqual(1, cancelEvents);
        AssertEqual(1, exitEvents);

        vm.TestMarkTaskTerminal("busy-task");
        AssertFalse(vm.CancelCommand.CanExecute(null));
        AssertFalse(vm.CancelAndExitCommand.CanExecute(null));
        AssertEqual(2, cancelEvents);
        AssertEqual(2, exitEvents);
    }

    private static void CancelledTranslate_ReportsMeasuredSafeCountsWithoutErrorLog()
    {
        const string payload = "{\"v\":1,\"type\":\"complete\",\"id\":\"measured-cancel\",\"ok\":false,\"summary\":\"\",\"error\":\"cancelled\",\"complete\":false,\"pending\":1,\"review_only\":1,\"blocked\":1,\"translated\":0,\"diagnostic_stage\":\"WORKFLOW\",\"diagnostic_root_cause\":\"UNKNOWN\",\"diagnostic_affected_count\":1,\"diagnostic_action\":\"A task was cancelled or interrupted; inspect its saved checkpoint before retrying.\",\"diagnostic_status\":\"FAILED\"}";
        var terminal = WorkerEvent.FromJson(payload);
        AssertTrue(terminal is not null);
        var package = CreatePackage(withTranslation: false, withPatch: false);
        try
        {
            File.WriteAllText(Path.Combine(package, "translation.csv"),
                "key,source_text,translation\r\nk1,Hello,Xin chào\r\nk2,World,Thế giới\r\nk3,Gate,\r\nk4,Road,\r\n", Encoding.UTF8);
            using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker:false);
            vm.TestSetTranslationModelReady(true);
            vm.OutputPath = package;
            AssertTrue(SpinWait.SpinUntil(() => vm.RunTranslateCommand.CanExecute(null), TimeSpan.FromSeconds(5)));

            vm.TestBeginTaskLog("measured-cancel", "translate");
            vm.TestSetActiveTask("measured-cancel", "translate");
            vm.TestHandleWorkerEvent(terminal!);

            AssertFalse(vm.Busy);
            AssertEqual("Đã hủy", vm.StatusText);
            // The worker's 0/1/1/1 are sentinels; the summary must come from the file on disk.
            AssertTrue(SpinWait.SpinUntil(
                () => vm.CsvValidationMessage.Contains("đã dịch an toàn 2/4", StringComparison.Ordinal),
                TimeSpan.FromSeconds(5)));
            AssertTrue(vm.CsvValidationMessage.StartsWith("Đã hủy", StringComparison.Ordinal));
            AssertFalse(vm.CsvValidationMessage.Contains("chưa dịch 1", StringComparison.Ordinal));
            AssertFalse(vm.CsvValidationMessage.Contains("Đã dịch 0", StringComparison.Ordinal));
            AssertFalse(vm.CsvValidationOk);
            // The prior cancelled run stays visible on the card instead of a bare "Sẵn sàng".
            AssertTrue(SpinWait.SpinUntil(
                () => vm.TranslateReadinessText.Contains("lần dịch trước đã hủy", StringComparison.Ordinal),
                TimeSpan.FromSeconds(5)));
            AssertTrue(vm.TranslateReadinessText.Contains("đã có bản dịch 2", StringComparison.Ordinal));
            // A cancellation is an INFO outcome, never an ERROR journal line.
            AssertTrue(vm.LogLines.Any(line => line.Contains("Đã hủy tác vụ", StringComparison.Ordinal)));
            AssertFalse(vm.LogLines.Any(line => AppJournalStore.Level(line) == "ERROR"
                && line.Contains("cancelled", StringComparison.OrdinalIgnoreCase)));
            AssertFalse(vm.LogLines.Any(line => line.Contains("Lỗi: cancelled", StringComparison.Ordinal)));
        }
        finally
        {
            Directory.Delete(package, true);
        }
    }

    private static void CancelledTranslate_KeepsThePickedCsvAndRestoresReadiness()
    {
        const string payload = "{\"v\":1,\"type\":\"complete\",\"id\":\"picked-cancel\",\"ok\":false,\"summary\":\"\",\"error\":\"cancelled\",\"complete\":false,\"pending\":1,\"review_only\":1,\"blocked\":1,\"translated\":0,\"diagnostic_stage\":\"WORKFLOW\",\"diagnostic_root_cause\":\"UNKNOWN\",\"diagnostic_affected_count\":1,\"diagnostic_action\":\"cancelled\",\"diagnostic_status\":\"FAILED\"}";
        var terminal = WorkerEvent.FromJson(payload);
        AssertTrue(terminal is not null);
        var package = CreatePackage(withTranslation: false, withPatch: false);
        try
        {
            var csv = Path.Combine(package, "translation.csv");
            // The CSV is picked directly (no extracted output folder), exactly like the native 3000-row run.
            using var vm = new MainViewModel(new FakePathPicker { TranslationCsv = csv }, new PythonWorkerHost(), startWorker: false);
            vm.TestSetTranslationModelReady(true);
            vm.NavigateTabCommand.Execute(WorkflowTabs.Translate);
            vm.ChooseTranslationCsvCommand.Execute(null);
            AssertEqual(csv, vm.TranslationCsvPath);
            AssertTrue(SpinWait.SpinUntil(() => vm.RunTranslateCommand.CanExecute(null), TimeSpan.FromSeconds(5)));
            AssertTrue(vm.CsvValidationOk);

            vm.TestBeginTaskLog("picked-cancel", "translate");
            vm.TestSetActiveTask("picked-cancel", "translate");
            vm.TestHandleWorkerEvent(terminal!);

            AssertFalse(vm.Busy);
            AssertTrue(SpinWait.SpinUntil(
                () => !vm.TranslateReadinessText.Contains("Đang kiểm tra", StringComparison.Ordinal)
                      && vm.CsvValidationMessage.StartsWith("Đã hủy", StringComparison.Ordinal),
                TimeSpan.FromSeconds(5)));
            AssertFalse(vm.TranslateReadinessText.Contains("không tồn tại", StringComparison.OrdinalIgnoreCase));
            AssertFalse(vm.CsvValidationMessage.Contains("không tồn tại", StringComparison.OrdinalIgnoreCase));
            AssertTrue(vm.CsvValidationOk);                      // still the file the user picked
            AssertEqual(csv, vm.TranslationCsvPath);
            AssertTrue(vm.RunTranslateCommand.CanExecute(null)); // Start is available again without reselecting
        }
        finally
        {
            Directory.Delete(package, true);
        }
    }

    private static void CsvPickers_UseContextSpecificTitles()
    {
        var package = CreatePackage(withTranslation: false, withPatch: false);
        try
        {
            var picker = new FakePathPicker { TranslationCsv = Path.Combine(package, "translation.csv") };
            using var vm = new MainViewModel(picker, new PythonWorkerHost(), startWorker:false);
            vm.TestSetTranslationModelReady(true);
            vm.ChooseTranslationCsvCommand.Execute(null);
            AssertEqual("Chọn CSV cần dịch", picker.LastCsvTitle);
            AssertFalse(picker.LastCsvTitle!.Contains("đã dịch", StringComparison.OrdinalIgnoreCase));

            picker.LastCsvTitle = null;
            vm.OpenCsvEditorFileCommand.Execute(null);
            AssertEqual("Chọn CSV để sửa", picker.LastCsvTitle);
        }
        finally
        {
            Directory.Delete(package, true);
        }
    }

    private static void OrdinaryFailureTerminal_IsNotPresentedAsCancellation()
    {
        const string payload = "{\"v\":1,\"type\":\"complete\",\"id\":\"translate-failed\",\"ok\":false,\"summary\":\"\",\"error\":\"unsupported operand type(s) for /: 'str' and 'str'\",\"complete\":false,\"pending\":1,\"review_only\":1,\"blocked\":1,\"translated\":0,\"diagnostic_stage\":\"TRANSLATE\",\"diagnostic_root_cause\":\"UNKNOWN\",\"diagnostic_affected_count\":1,\"diagnostic_action\":\"Review the recorded task failure and its evidence before retrying.\",\"diagnostic_status\":\"FAILED\"}";
        var terminal = WorkerEvent.FromJson(payload);
        AssertTrue(terminal is not null);

        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker:false);
        var notifications = new List<CompletionNotification>();
        vm.CompletionRequested += (_, notification) => notifications.Add(notification);
        vm.TestBeginTaskLog("translate-failed", "translate");
        vm.TestSetActiveTask("translate-failed", "translate");
        vm.TestHandleWorkerEvent(terminal!);

        AssertFalse(vm.Busy);
        AssertEqual("Lỗi", vm.StatusText);
        AssertFalse(vm.StepStatusLine.Contains("Đã hủy", StringComparison.Ordinal));
        AssertFalse(vm.TranslateProgressStep == "Đã hủy");
        AssertFalse(notifications.Any(notification => notification.Message == "Đã hủy tác vụ."));
    }

    private static void RetryAfterCancel_StaleTerminalCannotEndRetryOrRequestExit()
    {
        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker:false);
        var exitRequests = 0;
        vm.ExitAfterTaskRequested += (_, _) => exitRequests++;
        vm.TestBeginTaskLog("first-run", "translate");
        vm.TestSetActiveTask("first-run", "translate");
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="complete", Id="first-run", Ok=false, Complete=false, Error="cancelled" });
        AssertFalse(vm.Busy);
        AssertEqual("Đã hủy", vm.StatusText);

        vm.TestBeginTaskLog("retry-run", "translate");
        vm.TestSetActiveTask("retry-run", "translate");
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="complete", Id="first-run", Ok=false, Complete=false, Error="cancelled" });
        vm.TestHandleWorkerEvent(new WorkerEvent { Type="error", Id="first-run", Error="Worker process exited" });
        AssertTrue(vm.Busy);

        vm.TestHandleWorkerEvent(new WorkerEvent { Type="complete", Id="retry-run", Ok=false, Complete=false, Error="retry fixture failure" });
        AssertFalse(vm.Busy);
        AssertEqual("Lỗi", vm.StatusText);
        AssertEqual(0, exitRequests);
    }

    private static void WorkerHost_ErrorKeepsTaskOwnerUntilActualProcessExit()
    {
        using var worker = new PythonWorkerHost();
        var events = new List<WorkerEvent>();
        worker.EventReceived += (_, evt) => events.Add(evt);
        worker.TestSetActiveTaskId("host-error-race");
        worker.TestHandleWorkerEvent(new WorkerEvent { Type="error", Id="host-error-race", Error="task failed before process exit" });
        AssertTrue(worker.IsBusy);
        worker.TestHandleWorkerEvent(new WorkerEvent { Type="error", Id="older-task", Error="stale error" });
        AssertTrue(worker.IsBusy);
        AssertFalse(events.Any(evt => evt.Type == "complete"));

        worker.TestReportProcessExited();
        AssertFalse(worker.IsBusy);
        AssertEqual(4, events.Count(evt => evt.Type is "complete" or "error"));
        AssertEqual("complete", events[^2].Type);
        AssertEqual("host-error-race", events[^2].Id);
        AssertEqual("error", events[^1].Type);
        AssertEqual("host-error-race", events[^1].Id);
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

    private static void RenpyGameDetector_RequiresCredibleRecoveryEvidence()
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
            AssertEqual("loose_source", RenpyGameDetector.GetRenpyEvidenceKind(root, CancellationToken.None));
            File.Delete(Path.Combine(game, "scripts", "script.rpy"));
            File.WriteAllBytes(Path.Combine(game, "scripts", "script.rpyc"), Encoding.ASCII.GetBytes("RENPY RPC2"));
            AssertTrue(RenpyGameDetector.IsLooseSourceGame(root, CancellationToken.None));
            AssertEqual("compiled_source", RenpyGameDetector.GetRenpyEvidenceKind(root, CancellationToken.None));
            File.WriteAllText(Path.Combine(game, "scripts", "script.rpy"), "label start:\\n", Encoding.UTF8);
            Directory.CreateDirectory(Path.Combine(root, "Sample_Data"));
            AssertFalse(RenpyGameDetector.HasSdkRecoveryEvidence(root, CancellationToken.None));
            Directory.Delete(Path.Combine(root, "Sample_Data"));
            File.Delete(Path.Combine(game, "scripts", "script.rpy"));
            File.Delete(Path.Combine(game, "scripts", "script.rpyc"));
            File.WriteAllBytes(Path.Combine(game, "scripts", "unrelated.rpa"), Encoding.ASCII.GetBytes("RPA-3.0"));
            AssertFalse(RenpyGameDetector.HasSdkRecoveryEvidence(root, CancellationToken.None));
            Directory.CreateDirectory(Path.Combine(root, "lib"));
            Directory.CreateDirectory(Path.Combine(root, "renpy"));
            File.WriteAllBytes(Path.Combine(root, "CustomGame.exe"), new byte[] { 0x4d, 0x5a });
            AssertFalse(RenpyGameDetector.HasSdkRecoveryEvidence(root, CancellationToken.None));
            File.WriteAllText(Path.Combine(game, "scripts", "unrelated.rpa"), "RPA-3.0 0000000000000000 00000000\n", Encoding.ASCII);
            AssertTrue(RenpyGameDetector.HasSdkRecoveryEvidence(root, CancellationToken.None));
            AssertEqual("archive_source", RenpyGameDetector.GetRenpyEvidenceKind(root, CancellationToken.None));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void TranslateCommand_RequiresValidatedPackageReadiness()
    {
        var configuredRoot = Environment.GetEnvironmentVariable("VNTEXT_WPF_TEST_WORK_ROOT");
        var workRoot = string.IsNullOrWhiteSpace(configuredRoot)
            ? Path.Combine(RepoRoot(), "TEST_RUN")
            : configuredRoot;
        var root = Path.Combine(workRoot, "wpf_translate_readiness_" + Guid.NewGuid().ToString("N"));
        var empty = Path.Combine(root, "empty");
        var valid = Path.Combine(root, "valid");
        Directory.CreateDirectory(empty);
        Directory.CreateDirectory(valid);
        File.WriteAllText(Path.Combine(valid, "manifest.json"), "{}", Encoding.UTF8);
        File.WriteAllText(Path.Combine(valid, "translation.csv"), "key,source_text,translation\nrow-1,Hello,\n", Encoding.UTF8);
        try
        {
            using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
            vm.TestSetTranslationModelReady(true);
            vm.OutputPath = empty;
            AssertFalse(vm.RunTranslateCommand.CanExecute(null));
            AssertTrue(vm.TranslateReadinessText.Contains("không tồn tại", StringComparison.OrdinalIgnoreCase));
            vm.OutputPath = valid;
            AssertTrue(SpinWait.SpinUntil(() => vm.RunTranslateCommand.CanExecute(null), TimeSpan.FromSeconds(5)));
            AssertTrue(vm.TranslateReadinessText.Contains("1 dòng", StringComparison.Ordinal));
            vm.TestSetTranslationModelReady(false);
            AssertFalse(vm.RunTranslateCommand.CanExecute(null));
            AssertTrue(vm.TranslateReadinessText.Contains("Thiếu model OPUS-MT INT8", StringComparison.Ordinal));
            vm.TestSetTranslationModelReady(false, "Không nạp được runtime CTranslate2 (ModuleNotFoundError: No module named 'ctranslate2').");
            AssertFalse(vm.RunTranslateCommand.CanExecute(null));
            AssertTrue(vm.TranslateReadinessText.Contains("CTranslate2", StringComparison.Ordinal));
            AssertFalse(vm.TranslateReadinessText.Contains("Sẵn sàng dịch", StringComparison.Ordinal));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void TranslateCsvSelection_AllBlankExtractPackageIsReadyForTranslation()
    {
        var package = CreatePackage(withTranslation: false, withPatch: false);
        try
        {
            var csv = Path.Combine(package, "translation.csv");
            var picker = new FakePathPicker { TranslationCsv = csv };
            using var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(picker, worker, startWorker: false)
            {
                InputPath = @"C:\game",
                OutputPath = Path.Combine(package, "other-output"),
            };
            vm.TestSetTranslationModelReady(true);
            vm.NavigateTabCommand.Execute(WorkflowTabs.Translate);

            vm.ChooseTranslationCsvCommand.Execute(null);

            AssertEqual(csv, vm.TranslationCsvPath);
            AssertTrue(vm.CsvValidationOk);
            AssertTrue(vm.CsvValidationMessage.Contains("0/1", StringComparison.Ordinal));
            AssertTrue(SpinWait.SpinUntil(() => vm.RunTranslateCommand.CanExecute(null), TimeSpan.FromSeconds(5)));
            AssertTrue(vm.TranslateReadinessText.Contains("1 dòng", StringComparison.Ordinal));
            AssertTrue(vm.TranslateReadinessText.Contains("đã có bản dịch 0", StringComparison.Ordinal));
            AssertFalse(vm.ReadyForPatch);
        }
        finally
        {
            Directory.Delete(package, true);
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
        var archived = Path.Combine(root, "ArchiveRenpy");
        Directory.CreateDirectory(game);
        Directory.CreateDirectory(Path.Combine(unity, "Demo_Data"));
        File.WriteAllText(Path.Combine(game, "script.rpy"), "label start", Encoding.UTF8);
        Directory.CreateDirectory(Path.Combine(archived, "game"));
        Directory.CreateDirectory(Path.Combine(archived, "lib"));
        Directory.CreateDirectory(Path.Combine(archived, "renpy"));
        File.WriteAllBytes(Path.Combine(archived, "CustomGame.exe"), new byte[] { 0x4d, 0x5a });
        File.WriteAllBytes(Path.Combine(archived, "game", "scripts.rpa"), Encoding.ASCII.GetBytes("RPA-3.0 0000000000000000 00000000\n"));
        try
        {
            var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false);
            vm.InputPath = Path.Combine(root, "Renpy");
            AssertTrue(SpinWait.SpinUntil(() => vm.RenpySdkOptionsVisible, TimeSpan.FromSeconds(5)));
            vm.InputPath = archived;
            AssertTrue(SpinWait.SpinUntil(() => vm.RenpySdkOptionsVisible, TimeSpan.FromSeconds(5)));
            vm.InputPath = unity;
            AssertFalse(vm.RenpySdkOptionsVisible);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void RenpySdkRecovery_StatusRequiresSuccessfulEvidence()
    {
        AssertEqual("ready", RenpySdkRecovery.ResolveAction("download", sdkMissing: false, operationOk: true, cancelled: false));
        AssertEqual("ready", RenpySdkRecovery.ResolveAction("existing", sdkMissing: false, operationOk: true, cancelled: false));
        AssertEqual("error", RenpySdkRecovery.ResolveAction("download", sdkMissing: false, operationOk: false, cancelled: false));
        AssertEqual("cancelled", RenpySdkRecovery.ResolveAction("existing", sdkMissing: false, operationOk: false, cancelled: true));
        AssertEqual("error", RenpySdkRecovery.ResolveAction("download", sdkMissing: true, operationOk: false, cancelled: false));
        AssertEqual("error", RenpySdkRecovery.ResolveAction("existing", sdkMissing: true, operationOk: false, cancelled: false));
        AssertEqual("auto", RenpySdkRecovery.ResolveAction("auto", sdkMissing: false, operationOk: false, cancelled: false));
        AssertTrue(RenpySdkRecovery.FormatStatus("error", "download hash mismatch").Contains("thử tải lại", StringComparison.OrdinalIgnoreCase));
        AssertTrue(RenpySdkRecovery.FormatStatus("error", new string('x', 500)).Length < 300);
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

    private static void ImageText_EditInvalidatesApproval()
    {
        var region = new ImageTextRegion { SourceText = "Hello", Translation = "Xin chào", Approved = true, FlatBackgroundApproved = true, TransparentTextApproved = true };
        region.Translation = "Chào";
        AssertTrue(!region.Approved);
        region.Approved = true; region.X = 20;
        AssertTrue(!region.Approved && !region.FlatBackgroundApproved);
        region.Approved = true; region.FlatBackgroundApproved = true; region.TransparentTextApproved = true; region.Background = "#000000";
        AssertTrue(!region.Approved && !region.FlatBackgroundApproved && !region.TransparentTextApproved);
        region.Approved = true; region.CloneBackgroundApproved = true; region.DonorX = 40;
        AssertFalse(region.Approved || region.CloneBackgroundApproved);
        region.Approved = true; region.CloneBackgroundApproved = true; region.DonorY = 60;
        AssertFalse(region.Approved || region.CloneBackgroundApproved);
    }

    private static void ImageText_ReviewAndApprovalStayIndependent()
    {
        var root = Path.Combine(TestTempRoot(), "image_review_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
        var review = Path.Combine(root, "image_text.json");
        var source = Path.Combine(root, "source.png");
        var pixels = Enumerable.Repeat((byte)255, 300 * 120 * 4).ToArray();
        var bitmap = System.Windows.Media.Imaging.BitmapSource.Create(300,120,96,96,System.Windows.Media.PixelFormats.Bgra32,null,pixels,300*4);
        var encoder = new System.Windows.Media.Imaging.PngBitmapEncoder();
        encoder.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(bitmap));
        using (var stream = File.Create(source)) encoder.Save(stream);
        var sourceHash = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(source))).ToLowerInvariant();
        File.WriteAllText(review, JsonSerializer.Serialize(new ImageTextDocument { SourcePath = source, SourceSha256 = sourceHash, Width = 300, Height = 120, Status = "REVIEW_REQUIRED",
            Regions = new List<ImageTextRegion> { new() { Id = "fixed-region", Box = new[] {10,10,200,40}, SourceText = "Hello" } } }, MainViewModel.ImageJson));
        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
        var renderEnabled = false;
        var saveEnabled = false;
        vm.RenderImageCommand.CanExecuteChanged += (_, _) => renderEnabled = vm.RenderImageCommand.CanExecute(null);
        vm.SaveImageReviewCommand.CanExecuteChanged += (_, _) => saveEnabled = vm.SaveImageReviewCommand.CanExecute(null);
        vm.OutputPath = root;
        AssertTrue(vm.TryLoadImageReview(review));
        AssertTrue(renderEnabled && saveEnabled);
        AssertTrue(vm.ImageRegions.Count == 1 && vm.ImageRegions[0].Id == "fixed-region");
        vm.RenderImageCommand.Execute(null);
        AssertTrue(!vm.Busy && vm.ImageStatus.Contains("Duyệt"));
        AssertTrue(!vm.HasExtract && vm.SelectedTab == WorkflowTabs.Extract);
        vm.ImageRegions[0].Translation = "Xin chào";
        vm.SaveImageReviewCommand.Execute(null);
        var saved = Directory.GetFiles(root, "image_text.json", SearchOption.AllDirectories).Single(p => p != review);
        using var json = JsonDocument.Parse(File.ReadAllText(saved));
        AssertTrue(json.RootElement.GetProperty("source_sha256").GetString() == sourceHash);
        AssertTrue(json.RootElement.GetProperty("regions")[0].GetProperty("translation").GetString() == "Xin chào");
        AssertTrue(vm.TryLoadImageReview(saved));
        AssertTrue(vm.ImagePreview is not null && vm.ImageRegions[0].Translation == "Xin chào");
        AssertFalse(vm.ImageRegions[0].Approved);
        var preview = Path.Combine(Path.GetDirectoryName(saved)!, "source-preview.png");
        File.WriteAllText(preview, "untrusted sidecar preview");
        AssertTrue(vm.TryLoadImageReview(saved));
        AssertTrue(vm.ImagePreview is not null && vm.ImagePath == source);
        var tampered = JsonSerializer.Deserialize<ImageTextDocument>(File.ReadAllText(saved), MainViewModel.ImageJson)!;
        tampered.SourceSha256 = new string('0', 64);
        File.WriteAllText(saved, JsonSerializer.Serialize(tampered, MainViewModel.ImageJson));
        AssertFalse(vm.TryLoadImageReview(saved));
        AssertTrue(vm.ImagePreview is null && vm.ImageRegions.Count == 0 && vm.ImagePath == "");
        AssertFalse(vm.RenderImageCommand.CanExecute(null));
        AssertFalse(vm.SaveImageReviewCommand.CanExecute(null));
        AssertFalse(renderEnabled || saveEnabled);
        File.WriteAllText(saved, "{bad");
        AssertFalse(vm.TryLoadImageReview(saved));
        AssertTrue(vm.ImagePreview is null && vm.ImageRegions.Count == 0 && vm.ImagePath == "");
        File.WriteAllText(review,"{bad");
        AssertTrue(!vm.TryLoadImageReview(review));
        }
        finally { Directory.Delete(root, true); }
    }

    private static void ExtractPartialAndEmpty_DoNotAdvance()
    {
        foreach (var state in new[] { "PARTIAL", "EMPTY" })
        {
            var root = Path.Combine(TestTempRoot(), "extract_status_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
            try
            {
                File.WriteAllText(Path.Combine(root, "translation.csv"), "key,source_text,translation\nk,Hello,\n");
                File.WriteAllText(Path.Combine(root, "manifest.json"), "{}");
                File.WriteAllText(Path.Combine(root, "extract_status.json"),
                    JsonSerializer.Serialize(new { complete = false, status = state, main = 1, review = 1, errors = 0 }));
                var snapshot = WorkflowStatus.Evaluate("synthetic-game", root);
                AssertEqual("extract", snapshot.Current);
                AssertFalse(snapshot.HasExtract);
                AssertFalse(snapshot.ReadyForPatch);
                using var worker = new PythonWorkerHost();
                var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false)
                    { InputPath = "synthetic-game", OutputPath = root };
                vm.TestSimulateTaskComplete("extract", new WorkerEvent
                    { Type = "complete", Ok = false, Complete = false, ExtractStatus = state, ReviewOnly = 1 });
                AssertEqual(state == "EMPTY" ? "Không có text" : "Lấy text một phần", vm.StatusText);
                AssertEqual(WorkflowTabs.Extract, vm.SelectedTab);
                AssertFalse(vm.ProgressSubtitle.Contains("Hoàn tất"));
                AssertEqual("extract", vm.CurrentWorkflowStep);
                vm.RunExtractCommand.Execute(null);
                AssertEqual("Chọn thư mục xuất mới", vm.StatusText);
                AssertFalse(vm.Busy);
            }
            finally { Directory.Delete(root, true); }
        }
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
        AssertTrue(vm.RenpySdkOptionsVisible);
        AssertEqual("missing", vm.RenpySdkAction);
        AssertTrue(vm.DownloadRenpySdkCommand.CanExecute(null));
        AssertTrue(vm.ChooseRenpySdkCommand.CanExecute(null));
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
            AssertFalse(snap.ReadyForPatch);
            var picker = new FakePathPicker { TranslationCsv = Path.Combine(package, "translation.csv") };
            using var worker = new PythonWorkerHost();
            var vm = new MainViewModel(picker, worker, startWorker: false) { OutputPath = Path.Combine(package, "unused-output") };
            vm.ChooseTranslationCsvCommand.Execute(null);
            vm.TestSimulateTaskComplete("translate", new WorkerEvent { Type = "complete", Ok = true, Complete = false, Translated = 1, Pending = 1, ReviewOnly = 1, Blocked = 1 });
            AssertFalse(vm.ReadyForPatch);
            AssertFalse(vm.RunPatchCommand.CanExecute(null));
            AssertFalse(vm.PatchPreflightOk);
            AssertEqual(0, vm.PatchEligibleCount);
            AssertTrue(vm.CsvValidationMessage.Contains("Đã dịch 1"));
            AssertTrue(vm.PatchPreflightMessage.Contains("chưa thể tạo Patch"));
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

    private static void WorkerEvent_FormatsNumericEta()
    {
        var evt = WorkerEvent.FromJson("{\"type\":\"progress\",\"done\":2,\"total\":10,\"eta\":3661.4}");
        AssertTrue(evt is not null);
        AssertEqual("3661.4", evt!.Eta);
        AssertEqual("1 giờ 1 phút", ProgressEtaFormatter.Format(evt.Eta));
        AssertEqual("45 giây", ProgressEtaFormatter.Format("45"));
        AssertEqual("", ProgressEtaFormatter.Format("NaN"));
        AssertEqual("59 giây", ProgressEtaFormatter.Format("59"));
        AssertEqual("1 phút", ProgressEtaFormatter.Format("60"));
        AssertEqual("1 giờ", ProgressEtaFormatter.Format("3600"));
        AssertEqual("1 ngày", ProgressEtaFormatter.Format("86400"));
        AssertEqual("365 ngày", ProgressEtaFormatter.Format("31536000"));
        AssertEqual("", ProgressEtaFormatter.Format("31536001"));
        AssertEqual("", ProgressEtaFormatter.Format("1e308"));
        AssertEqual("", ProgressEtaFormatter.Format("Infinity"));
        AssertEqual("", ProgressEtaFormatter.Format("-1"));

        using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
        vm.TestSetActiveTask("eta-task", "extract");
        vm.TestHandleWorkerEvent(new WorkerEvent { Type = "progress", Id = "eta-task", Done = 2, Total = 10, Eta = "1e308" });
        AssertFalse(vm.ExtractProgressSubtitle.Contains("ước tính thời gian", StringComparison.OrdinalIgnoreCase));
    }

    private static void PatchDelivery_RoutesRenPyInstructions()
    {
        using var worker = new PythonWorkerHost();
        var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false);
        AssertFalse(vm.PatchDeliveryReady);
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

        AssertTrue(vm.PatchDeliveryReady);
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
            AssertTrue(vm.StepStatusLine.Contains("chưa thể dùng 1"));
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
            var changed = new List<string?>();
            vm.PropertyChanged += (_, e) => changed.Add(e.PropertyName);
            vm.TestSimulateTaskComplete("extract", new WorkerEvent
            {
                Type = "complete",
                Ok = true,
                Complete = true,
                Summary = "extract ok",
            });
            AssertEqual(WorkflowTabs.Translate, vm.SelectedTab);
            AssertFalse(vm.Busy);
            AssertEqual(Path.Combine(root, "translation.csv"), vm.TranslationCsvPath);
            vm.TestSetTranslationModelReady(true);
            if (!vm.TranslateReadinessText.Contains("0/1", StringComparison.Ordinal)
                && !vm.TranslateReadinessText.Contains("đã có bản dịch 0", StringComparison.Ordinal))
                throw new InvalidOperationException("Translate readiness after Extract: " + vm.TranslateReadinessText);
            AssertTrue(vm.CsvValidationOk);
            AssertTrue(vm.CsvValidationMessage.Contains("0/1", StringComparison.Ordinal));
            AssertTrue(vm.TranslateWorkflowStatusText.Contains("đã có bản dịch 0", StringComparison.Ordinal));
            AssertTrue(changed.Contains(nameof(vm.TranslateWorkflowStatusText)));
            AssertFalse(vm.ReadyForPatch);
            if (!vm.RunTranslateCommand.CanExecute(null))
                throw new InvalidOperationException("Translate command stayed disabled after Extract: " + vm.TranslateReadinessText);
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
            var draft = CsvPackageValidator.Validate(csv, requireTranslations: false);
            AssertTrue(draft.Ok);
            AssertEqual(0, draft.TranslatedRows);
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
            AssertEqual(ExtractLevels.Exhaustive, vm.ExtractLevel);
            vm.ExtractLevel = ExtractLevels.Exhaustive;
            AssertEqual(ExtractLevels.Exhaustive, vm.ExtractLevel);
            var reloaded = AppSettingsStore.Load();
            AssertEqual(ExtractLevels.Balanced, reloaded.ExtractLevel);
            vm.UiScale = 1.2;
            vm.AutoCheckUpdates = false;
            vm.NotifyUpdates = false;
            vm.RememberWindow = false;
            reloaded = AppSettingsStore.Load();
            AssertEqual(1.2, reloaded.UiScale);
            AssertFalse(reloaded.AutoCheckUpdates);
            AssertFalse(reloaded.NotifyUpdates);
            AssertFalse(reloaded.RememberWindow);
            AssertEqual(ExtractLevels.Balanced, reloaded.ExtractLevel);
            File.WriteAllText(path, "{broken");
            _ = AppSettingsStore.Load(out var error);
            AssertTrue(!string.IsNullOrWhiteSpace(error));
            vm.UiScale = 1.1;
            AssertEqual("{broken", File.ReadAllText(path));
            AssertTrue(vm.SettingsStatus.Contains("Không lưu được", StringComparison.Ordinal));
            File.Delete(path);
            vm.ExtractLevel = "clean";
            AssertEqual(ExtractLevels.Exhaustive, vm.ExtractLevel);
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
            Directory.CreateDirectory(Path.Combine(root, "game"));
            File.WriteAllText(Path.Combine(root, "game", "script.rpy"), "label start: pass\n", Encoding.UTF8);
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
                InputPath = root,
                OutputPath = root,
                SelectedTab = WorkflowTabs.Extract,
            };

            AssertTrue(vm.AnalyzeCommand.CanExecute(null));
            AssertFalse(vm.AnalyzeResultsExpanded);
            AssertFalse(vm.AnalyzeHasReport);
            AssertEqual("", vm.AnalyzeScanErrorText);
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
            AssertEqual("Engine: Unity + Ren’Py evidence", vm.AnalyzeEngineSummary);
            AssertTrue(vm.AnalyzeEngineDetails.Contains(".rpy/.rpym", StringComparison.Ordinal));
            AssertTrue(vm.AnalyzeEngineDetails.Contains("chưa xác minh patch/write-back", StringComparison.Ordinal));
            AssertTrue(vm.AnalyzeInventoryComplete);
            AssertEqual(12, vm.AnalyzeResourceCount);
            AssertEqual(19, vm.AnalyzeTextCandidateCount);
            AssertEqual(3, vm.AnalyzePatchableCount);
            AssertEqual(6, vm.AnalyzeReviewRiskCount);
            AssertEqual(2, vm.AnalyzeUnknownCount);
            AssertTrue(vm.AnalyzeStatusText.Contains("danh mục tài nguyên đầy đủ", StringComparison.Ordinal));
            AssertEqual("Không ghi nhận lỗi quét.", vm.AnalyzeScanErrorText);
            AssertTrue(vm.AnalyzeResultsExpanded);
            AssertTrue(vm.AnalyzeHasReport);
            AssertEqual(report, vm.AnalyzeReportPath);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void Analyze_InputChangeMarksResultStaleAndRejectsLateEvent()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_analyze_stale_" + Guid.NewGuid().ToString("N"));
        var first = Path.Combine(root, "analyzed");
        var second = Path.Combine(root, "other");
        Directory.CreateDirectory(Path.Combine(first, "game"));
        Directory.CreateDirectory(Path.Combine(second, "game"));
        try
        {
            File.WriteAllText(Path.Combine(first, "game", "a.rpy"), "label start:\n    return\n", Encoding.UTF8);
            File.WriteAllText(Path.Combine(second, "game", "b.rpy"), "label start:\n    return\n", Encoding.UTF8);
            File.WriteAllText(Path.Combine(first, "unity_analysis.json"), """
                {"inventory_complete": true, "unity": {"status": "DETECTED"},
                 "summary": {"resource_count": 30, "unknown_resources": 0, "scan_error_count": 0},
                 "coverage": {"text_candidates": 30, "patchable_text": 0, "extract_only_text": 0, "review_required": 0, "unsupported": 0},
                 "scan_errors": []}
                """, Encoding.UTF8);
            using var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false) { InputPath = first, OutputPath = first };
            vm.TestMarkAnalyzeStarted();
            vm.TestSimulateTaskComplete("analyze", new WorkerEvent { Type = "complete", Id = "analyze-A", Ok = true, Complete = true });
            AssertEqual(30, vm.AnalyzeResourceCount);
            AssertTrue(vm.AnalyzeHasReport);
            AssertTrue(vm.AnalyzeStatusText.Contains("Đã phân tích", StringComparison.Ordinal));

            // A -> B: the shown analysis described A, so it must not stay attributed to B.
            vm.TestMarkTaskTerminal("analyze-A");
            vm.InputPath = second;
            vm.OutputPath = second;
            AssertEqual("Đầu vào đã đổi • cần phân tích lại", vm.AnalyzeStatusText);
            AssertEqual(0, vm.AnalyzeResourceCount);
            AssertEqual(0, vm.AnalyzeTextCandidateCount);
            AssertEqual("Chưa xác định engine", vm.AnalyzeEngineSummary);
            AssertEqual("NOT_DETECTED", vm.AnalyzeUnityStatus);
            AssertFalse(vm.AnalyzeHasReport);
            AssertFalse(vm.AnalyzeResultsExpanded);
            AssertFalse(vm.AnalyzeInventoryComplete);

            // Late event: an analysis started for A completes after the input moved to B.
            vm.InputPath = first;
            vm.OutputPath = first;
            vm.TestMarkAnalyzeStarted();
            vm.TestSetActiveTask("analyze-late", "analyze");
            vm.InputPath = second;
            vm.OutputPath = second;
            vm.TestHandleWorkerEvent(new WorkerEvent { Type = "complete", Id = "analyze-late", Ok = true, Complete = true });
            AssertFalse(vm.Busy);
            AssertEqual(0, vm.AnalyzeResourceCount);
            AssertFalse(vm.AnalyzeHasReport);
            AssertEqual("Đầu vào đã đổi • cần phân tích lại", vm.AnalyzeStatusText);
            AssertEqual("Đầu vào đã đổi", vm.StatusText);

            // Same identity (a trailing separator is the same path) keeps the result.
            vm.InputPath = first;
            vm.OutputPath = first;
            vm.TestMarkAnalyzeStarted();
            vm.TestSimulateTaskComplete("analyze", new WorkerEvent { Type = "complete", Id = "analyze-A2", Ok = true, Complete = true });
            AssertEqual(30, vm.AnalyzeResourceCount);
            vm.TestMarkTaskTerminal("analyze-A2");
            vm.InputPath = first + Path.DirectorySeparatorChar;
            AssertEqual(30, vm.AnalyzeResourceCount);
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void PumpUntilDone(Task task, Dispatcher dispatcher)
    {
        var frame = new DispatcherFrame();
        _ = task.ContinueWith(_ => dispatcher.BeginInvoke(DispatcherPriority.Send, new Action(() => frame.Continue = false)), TaskScheduler.Default);
        if (!task.IsCompleted)
            Dispatcher.PushFrame(frame);
        task.GetAwaiter().GetResult();
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

    private static void Copy_NoCsvChosenIsActionableAndSdkDownloadIsLabelled()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_copy_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
            vm.TestSetTranslationModelReady(true);
            vm.OutputPath = root;   // no translation.csv in it and none picked
            vm.NavigateTabCommand.Execute(WorkflowTabs.Translate);
            AssertTrue(SpinWait.SpinUntil(() => !vm.TranslateReadinessText.Contains("Đang kiểm tra", StringComparison.Ordinal), TimeSpan.FromSeconds(5)));
            AssertEqual(CsvPackageValidator.NoCsvChosenMessage, vm.TranslateReadinessText);
            AssertFalse(vm.TranslateReadinessText.Contains("File không tồn tại", StringComparison.Ordinal));

            AssertEqual("Tiến trình quét", vm.ExtractProgressHeading);
            vm.TestSetRenpySdkAction("download");
            vm.TestSetActiveTask("sdk-download", "extract");
            AssertEqual("Tiến trình tải SDK và lấy text", vm.ExtractProgressHeading);
            vm.TestMarkTaskTerminal("sdk-download");
            AssertEqual("Tiến trình quét", vm.ExtractProgressHeading);
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

    private static void OcrOnlyPackage_TranslateCardPointsToTheImageStep()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_ocr_only_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(root, "images"));
        try
        {
            // The package Extract leaves for a supported container whose only text is inside images.
            File.WriteAllText(Path.Combine(root, "translation.csv"), "key,source_text,translation,context,file_path,import_method\r\n", new UTF8Encoding(true));
            File.WriteAllText(Path.Combine(root, "manifest.json"), """{"entries":[]}""", Encoding.UTF8);
            File.WriteAllText(Path.Combine(root, "images", "report.json"), """
                {"schema":1,"status":"OCR_PARTIAL","items":[
                  {"source":"a.png","status":"OCR_READY"},{"source":"b.png","status":"OCR_READY"},
                  {"source":"c.png","status":"UNTRANSLATED","reason":"tilt gate"}]}
                """, Encoding.UTF8);
            var probe = ImagePackageProbe.Read(root);
            AssertEqual(3, probe.Total);
            AssertEqual(2, probe.OcrReady);
            using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
            vm.TestSetTranslationModelReady(true);
            vm.OutputPath = root;
            vm.NavigateTabCommand.Execute(WorkflowTabs.Translate);
            AssertTrue(SpinWait.SpinUntil(() => !vm.TranslateReadinessText.Contains("Đang kiểm tra", StringComparison.Ordinal), TimeSpan.FromSeconds(5)));
            AssertTrue(vm.TranslateReadinessText.Contains("2 ảnh đã OCR", StringComparison.Ordinal));
            AssertTrue(vm.TranslateReadinessText.Contains("Dịch ảnh…", StringComparison.Ordinal));
            AssertFalse(vm.RunTranslateCommand.CanExecute(null));   // there are no text rows to translate
            // No image report: the plain validator text stays (nothing invented).
            File.Delete(Path.Combine(root, "images", "report.json"));
            vm.OutputPath = root + Path.DirectorySeparatorChar;
            vm.OutputPath = root;
            AssertTrue(SpinWait.SpinUntil(() => vm.TranslateReadinessText == CsvPackageValidator.NoDataRowsMessage, TimeSpan.FromSeconds(5)));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void ImagePackageProbe_ToleratesMalformedReportsWithoutThrowing()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_probe_" + Guid.NewGuid().ToString("N"));
        var images = Path.Combine(root, "images");
        Directory.CreateDirectory(images);
        try
        {
            var report = Path.Combine(images, "report.json");
            void Put(string json) => File.WriteAllText(report, json, Encoding.UTF8);
            // Valid report.
            Put("""{"items":[{"status":"OCR_READY"},{"status":"OCR_READY"},{"status":"TRANSLATED_DRAFT"},{"status":"UNTRANSLATED"}]}""");
            AssertEqual(new ImagePackageProbe.Summary(4, 2, 1), ImagePackageProbe.Read(root));
            // Valid JSON of the wrong shape: none of these may throw, none counts as ready.
            foreach (var json in new[]
            {
                "[]", "null", "42", "\"text\"", "true", "{}", """{"items":null}""", """{"items":{}}""", """{"items":"x"}""", """{"items":7}""",
            })
            {
                Put(json);
                AssertEqual(default(ImagePackageProbe.Summary), ImagePackageProbe.Read(root));
            }
            // Malformed entries are counted as items but never as ready; well-formed neighbours still count.
            Put("""{"items":[1,null,"s",[],{"status":7},{"status":null},{"status":{}},{"status":["OCR_READY"]},{"status":"OCR_READY"}]}""");
            AssertEqual(new ImagePackageProbe.Summary(9, 1, 0), ImagePackageProbe.Read(root));
            // Invalid JSON and an empty file.
            Put("{not json");
            AssertEqual(default(ImagePackageProbe.Summary), ImagePackageProbe.Read(root));
            Put("");
            AssertEqual(default(ImagePackageProbe.Summary), ImagePackageProbe.Read(root));
            // Oversized report is ignored without being parsed.
            File.WriteAllText(report, "{\"items\":[],\"pad\":\"" + new string('x', (int)ImagePackageProbe.MaxReportBytes) + "\"}", Encoding.UTF8);
            AssertEqual(default(ImagePackageProbe.Summary), ImagePackageProbe.Read(root));
            // Unreadable report (exclusively locked): bounded failure, no exception.
            Put("""{"items":[{"status":"OCR_READY"}]}""");
            using (new FileStream(report, FileMode.Open, FileAccess.Read, FileShare.None))
                AssertEqual(default(ImagePackageProbe.Summary), ImagePackageProbe.Read(root));
            AssertEqual(new ImagePackageProbe.Summary(1, 1, 0), ImagePackageProbe.Read(root));
            // Missing / blank package directory.
            AssertEqual(default(ImagePackageProbe.Summary), ImagePackageProbe.Read(Path.Combine(root, "nope")));
            AssertEqual(default(ImagePackageProbe.Summary), ImagePackageProbe.Read(""));
            AssertEqual(default(ImagePackageProbe.Summary), ImagePackageProbe.Read(null));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void ImagePackageProbe_SelectionIsDeterministicAndBounded()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_probe_sel_" + Guid.NewGuid().ToString("N"));
        var images = Path.Combine(root, "images");
        Directory.CreateDirectory(images);
        try
        {
            void Put(string path, string json, DateTime utc)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(path)!);
                File.WriteAllText(path, json, Encoding.UTF8);
                File.SetLastWriteTimeUtc(path, utc);
            }
            var t0 = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
            Put(Path.Combine(images, "report.json"), """{"items":[{"status":"OCR_READY"}]}""", t0);
            // A newer retry report wins over the first report.
            Put(Path.Combine(images, "retry-a", "report.json"), """{"items":[{"status":"TRANSLATED_DRAFT"},{"status":"TRANSLATED_DRAFT"}]}""", t0.AddHours(1));
            AssertEqual(new ImagePackageProbe.Summary(2, 0, 2), ImagePackageProbe.Read(root));
            // Equal write times: the path order decides, so the answer never depends on enumeration order.
            Put(Path.Combine(images, "retry-b", "report.json"), """{"items":[{"status":"OCR_READY"},{"status":"OCR_READY"},{"status":"OCR_READY"}]}""", t0.AddHours(1));
            AssertEqual(new ImagePackageProbe.Summary(2, 0, 2), ImagePackageProbe.Read(root));
            // The retry scan is capped: a report that only exists beyond the cap is not found.
            Directory.Delete(Path.Combine(images, "retry-a"), true);
            Directory.Delete(Path.Combine(images, "retry-b"), true);
            File.Delete(Path.Combine(images, "report.json"));
            for (var i = 0; i < ImagePackageProbe.MaxRetryDirectories + 6; i++)
                Directory.CreateDirectory(Path.Combine(images, $"retry-{i:D3}"));
            Put(Path.Combine(images, $"retry-{ImagePackageProbe.MaxRetryDirectories + 5:D3}", "report.json"), """{"items":[{"status":"OCR_READY"}]}""", t0);
            AssertEqual(default(ImagePackageProbe.Summary), ImagePackageProbe.Read(root));
            // A report inside the cap is found.
            Put(Path.Combine(images, "retry-000", "report.json"), """{"items":[{"status":"OCR_READY"}]}""", t0);
            AssertEqual(new ImagePackageProbe.Summary(1, 1, 0), ImagePackageProbe.Read(root));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void OcrOnlyPackage_MalformedReportNeverReachesTheGetterAsAnException()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_ocr_bad_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(root, "images"));
        try
        {
            File.WriteAllText(Path.Combine(root, "translation.csv"), "key,source_text,translation,context,file_path,import_method\r\n", new UTF8Encoding(true));
            File.WriteAllText(Path.Combine(root, "manifest.json"), """{"entries":[]}""", Encoding.UTF8);
            using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
            vm.TestSetTranslationModelReady(true);
            foreach (var json in new[] { "[]", "null", """{"items":[1,null,{"status":3}]}""", "{oops" })
            {
                File.WriteAllText(Path.Combine(root, "images", "report.json"), json, Encoding.UTF8);
                vm.OutputPath = root + Path.DirectorySeparatorChar;
                vm.OutputPath = root;
                AssertTrue(SpinWait.SpinUntil(() => !vm.TranslateReadinessText.Contains("Đang kiểm tra", StringComparison.Ordinal), TimeSpan.FromSeconds(5)));
                // Reading the getter many times is cheap and never throws; no image claim without a valid report.
                for (var i = 0; i < 20; i++) AssertEqual(CsvPackageValidator.NoDataRowsMessage, vm.TranslateReadinessText);
            }
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void WindowGeometry_FitsNarrowShortAndHighDpiWorkAreas()
    {
        void Inside(WindowGeometry.Fit fit, Rect area)
        {
            AssertTrue(fit.Width <= area.Width + 0.001 && fit.Height <= area.Height + 0.001);
            AssertTrue(fit.Left >= area.Left - 0.001 && fit.Top >= area.Top - 0.001);
            AssertTrue(fit.Left + fit.Width <= area.Right + 0.001);      // right edge (close button) stays visible
            AssertTrue(fit.Top + fit.Height <= area.Bottom + 0.001);     // bottom edge stays above the taskbar
            AssertTrue(fit.MinWidth <= area.Width && fit.MinHeight <= area.Height);   // the minimum never forces overflow
            AssertTrue(fit.Width >= fit.MinWidth && fit.Height >= fit.MinHeight);
        }
        // Roomy 1080p work area: the design size is kept and centred.
        var roomy = new Rect(0, 0, 1920, 1040);
        var fit = WindowGeometry.Compute(1440, 920, null, null, roomy);
        AssertEqual(1440d, fit.Width); AssertEqual(920d, fit.Height); AssertEqual(1040d, fit.MinWidth); AssertEqual(720d, fit.MinHeight);
        AssertEqual(240d, fit.Left); AssertEqual(60d, fit.Top);
        Inside(fit, roomy);
        // Small laptop 1366x728 work area (design 920 is taller than the area).
        var laptop = new Rect(0, 0, 1366, 728);
        fit = WindowGeometry.Compute(1440, 920, null, null, laptop);
        AssertEqual(1366d, fit.Width); AssertEqual(728d, fit.Height); AssertEqual(1040d, fit.MinWidth); AssertEqual(720d, fit.MinHeight);
        Inside(fit, laptop);
        // 1920x1080 at 125% and 150% DPI: fewer logical pixels (1536x824 / 1280x680 after the taskbar).
        foreach (var dpi in new[] { new Rect(0, 0, 1536, 824), new Rect(0, 0, 1280, 680) })
        {
            fit = WindowGeometry.Compute(1440, 920, null, null, dpi);
            Inside(fit, dpi);
            AssertEqual(Math.Min(1440d, dpi.Width), fit.Width);
            AssertEqual(dpi.Height, fit.Height);
        }
        // Narrow/short area below the minimum (800x600): the minimum shrinks to the area, nothing overflows.
        var narrow = new Rect(0, 0, 800, 600);
        fit = WindowGeometry.Compute(1440, 920, null, null, narrow);
        AssertEqual(800d, fit.MinWidth); AssertEqual(600d, fit.MinHeight);
        Inside(fit, narrow);
        // Taskbar on the left/top: the work area does not start at 0,0.
        var offset = new Rect(60, 40, 1300, 700);
        fit = WindowGeometry.Compute(1440, 920, null, null, offset);
        Inside(fit, offset);
        // Saved geometry that is off-screen, huge, tiny, non-finite or negative is pulled back inside.
        foreach (var (w, h, l, t) in new (double, double, double?, double?)[]
        {
            (1440, 920, -3000, -3000), (1440, 920, 9000, 9000), (99999, 99999, 0, 0), (10, 10, 0, 0),
            (double.NaN, double.NaN, double.NaN, double.NaN), (-5, -5, 5, 5), (double.PositiveInfinity, 700, 1, 1),
        })
        {
            fit = WindowGeometry.Compute(w, h, l, t, laptop);
            Inside(fit, laptop);
        }
        // An unusable work area falls back to the design values instead of throwing.
        fit = WindowGeometry.Compute(1440, 920, null, null, new Rect(0, 0, 0, 0));
        AssertEqual(1440d, fit.Width); AssertEqual(720d, fit.MinHeight);
        // A real Window receives the fit, including the minimum (the XAML 1040x720 must not survive on a small area).
        Exception? failure = null;
        var thread = new Thread(() =>
        {
            try
            {
                var window = new Window { Width = 1440, Height = 920, MinWidth = 1040, MinHeight = 720 };
                WindowGeometry.Apply(window, WindowGeometry.Compute(1440, 920, null, null, narrow));
                AssertEqual(800d, window.Width); AssertEqual(600d, window.Height);
                AssertEqual(800d, window.MinWidth); AssertEqual(600d, window.MinHeight);
                AssertTrue(window.Left >= 0 && window.Left + window.Width <= 800 && window.Top + window.Height <= 600);
                AssertEqual(WindowStartupLocation.Manual, window.WindowStartupLocation);
            }
            catch (Exception ex) { failure = ex; }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        if (failure is not null) throw new InvalidOperationException(failure.Message, failure);
    }

    private static void ContentDisclosure_InitialIsQuietAndFailuresExpand()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_disclosure_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            using var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false)
            {
                OutputPath = root,
            };

            AssertEqual("", vm.ExtractProgressSubtitle);
            AssertEqual("", vm.ExtractStatusText);
            AssertEqual("Chưa bắt đầu", vm.ProgressSubtitle);
            AssertEqual("Sẵn sàng", vm.StatusText);
            var changed = new List<string?>();
            vm.PropertyChanged += (_, e) => changed.Add(e.PropertyName);
            vm.InputPath = @"C:\game";
            AssertEqual("Sẵn sàng lấy text", vm.ExtractStatusText);
            AssertTrue(changed.Contains(nameof(vm.ExtractStatusText)));
            vm.InputPath = "";
            foreach (var message in new[] { "Đang quét", "Hoàn tất", "Đã hủy", "Lỗi worker" })
            {
                changed.Clear();
                var taskId = "disclosure-" + message;
                vm.TestSetActiveTask(taskId, "extract");
                vm.TestHandleWorkerEvent(new WorkerEvent { Type = "progress", Id = taskId, Done = 1, Total = 2, Step = message });
                vm.StatusText = message;
                AssertTrue(vm.ExtractProgressSubtitle.Contains(message, StringComparison.Ordinal));
                AssertEqual(message, vm.ExtractStatusText);
                AssertTrue(changed.Contains(nameof(vm.ExtractProgressSubtitle)));
                AssertTrue(changed.Contains(nameof(vm.ExtractStatusText)));
                vm.TestMarkTaskTerminal(taskId);
            }
            vm.ProgressSubtitle = "Chưa bắt đầu";
            vm.StatusText = "Sẵn sàng";
            vm.SelectedTab = WorkflowTabs.Patch;
            AssertEqual("Chọn game và bản dịch để kiểm tra rồi đóng gói patch.", vm.HeroHint);
            vm.SelectedTab = WorkflowTabs.Extract;
            AssertEqual("Chưa phân tích game", vm.AnalyzeStatusText);
            AssertEqual("", vm.AnalyzeScanErrorText);
            AssertEqual("", vm.AnalyzeReportPath);
            AssertFalse(vm.AnalyzeResultsExpanded);
            AssertFalse(vm.AnalyzeHasReport);
            AssertEqual("", vm.CsvValidationMessage);
            AssertEqual("", vm.PatchPreflightMessage);
            AssertFalse(vm.PatchResultsAvailable);
            AssertFalse(vm.PatchResultsExpanded);
            AssertFalse(vm.PatchPreflightEvaluated);
            AssertFalse(vm.PatchDeliveryReady);
            AssertEqual("", vm.CloudRepairPackageDisplay);

            vm.ValidateTranslationCsvCommand.Execute(null);
            AssertTrue(vm.PatchResultsAvailable);
            AssertTrue(vm.PatchResultsExpanded);
            AssertFalse(vm.PatchPreflightEvaluated);
            AssertFalse(vm.CsvValidationOk);
            AssertTrue(!string.IsNullOrWhiteSpace(vm.CsvValidationMessage));
            AssertTrue(vm.PatchPreflightMessage.Contains("CSV hợp lệ", StringComparison.Ordinal));

            vm.TestSimulateTaskComplete("patch", new WorkerEvent
            {
                Type = "complete",
                Id = "patch-worker-exit",
                Ok = false,
                Complete = false,
                Error = "Worker process exited unexpectedly",
            });
            vm.TestHandleWorkerEvent(new WorkerEvent { Type = "error", Error = "Worker process exited" });
            AssertTrue(vm.PatchResultsAvailable);
            AssertTrue(vm.PatchResultsExpanded);
            AssertTrue(vm.LogLines.Any(line => line.Contains("Worker process exited unexpectedly", StringComparison.Ordinal)));

            vm.InputPath = @"C:\game";
            vm.TestSimulateTaskComplete("analyze", new WorkerEvent
            {
                Type = "complete",
                Ok = false,
                Complete = false,
                Error = "fixture scan failure",
            });
            AssertTrue(vm.AnalyzeResultsExpanded);
            AssertFalse(vm.AnalyzeHasReport);
            AssertEqual("", vm.AnalyzeReportPath);
            AssertEqual("Phân tích thất bại", vm.AnalyzeStatusText);
            AssertTrue(!string.IsNullOrWhiteSpace(vm.AnalyzeScanErrorText));

            var report = Path.Combine(root, "unity_analysis.json");
            File.WriteAllText(report, """
                {
                  "inventory_complete": false,
                  "unity": {"status": "DETECTED"},
                  "summary": {"resource_count": 1, "unknown_resources": 0, "scan_error_count": 1},
                  "coverage": {"text_candidates": 0, "patchable_text": 0, "extract_only_text": 0, "review_required": 0, "unsupported": 0},
                  "scan_errors": [{"path": "broken.asset", "error": "fixture scan warning"}]
                }
                """, Encoding.UTF8);
            vm.TestSimulateTaskComplete("analyze", new WorkerEvent
            {
                Type = "complete",
                Id = "analyze-with-scan-warning",
                Ok = false,
                Complete = false,
                Error = "fixture scan warning",
            });
            AssertTrue(vm.AnalyzeResultsExpanded);
            AssertTrue(vm.AnalyzeHasReport);
            AssertEqual(report, vm.AnalyzeReportPath);
            AssertTrue(vm.AnalyzeScanErrorText.Contains("1 lỗi quét", StringComparison.Ordinal));
        }
        finally
        {
            Directory.Delete(root, true);
        }
    }

    private static void CloudRepairPackage_IsShownOnlyAfterSuccessfulExport()
    {
        var root = Path.Combine(TestTempRoot(), "vntext_wpf_cloud_export_" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(root);
        try
        {
            var archive = Path.Combine(root, "fixture.zip");
            using (ZipFile.Open(archive, ZipArchiveMode.Create)) { }
            using var worker = new PythonWorkerHost();
            using var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false);
            vm.TestSetCloudRepairPackagePath(archive);

            AssertFalse(vm.CloudRepairPackageReady);
            AssertEqual("", vm.CloudRepairPackageDisplay);
            vm.TestSimulateTaskComplete("cloud_export", new WorkerEvent
            {
                Type = "complete",
                Ok = true,
                Complete = true,
                Summary = "fixture export complete",
            });
            AssertTrue(vm.CloudRepairPackageReady);
            AssertEqual(archive, vm.CloudRepairPackageDisplay);
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

            vm.RetranslateBlockedCsvRowsAsync().GetAwaiter().GetResult();

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
        AssertTrue(notifications[1].Message.Contains("chưa dịch 2"));
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
                GitHubReleaseWithDate("v1.0.1", false, false, "2026-10-24T08:43:24Z",
                    GitHubAsset(assetName, "sha256:" + digest, package.LongLength, downloadUrl),
                    GitHubAsset("Setup.exe", "sha256:" + digest, package.LongLength, setupUrl)),
            });
            var apiUrl = new Uri("https://api.github.com/repos/test-owner/test-repo/releases?per_page=100");
            var handler = new TestHttpMessageHandler((request, _) =>
            {
                if (request.RequestUri == apiUrl)
                {
                    AssertTrue(request.Headers.CacheControl?.NoCache == true);
                    AssertTrue(request.Headers.CacheControl?.NoStore == true);
                    AssertEqual(TimeSpan.Zero, request.Headers.CacheControl!.MaxAge!.Value);
                    AssertTrue(request.Headers.Pragma.Any(value => value.Name == "no-cache"));
                    return Task.FromResult(JsonResponse(releases));
                }
                if (request.RequestUri == new Uri(downloadUrl))
                    return Task.FromResult(BinaryResponse(package));
                throw new HttpRequestException("Unexpected HTTP target: " + request.RequestUri);
            });

            var offer = WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root, handler,
                metadataOnly: true).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.OfferAvailable, offer.State);
            AssertEqual("24/10/2026", offer.ReleaseDate);
            AssertEqual(1, handler.Requests.Count);
            AssertEqual("", offer.PackagePath);
            AssertEqual(digest, offer.PackageSha256);
            var changed = WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root, handler,
                expectedOffer: offer with { PackageSha256 = new string('0', 64) }).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.InvalidMetadata, changed.State);
            AssertEqual(2, handler.Requests.Count);
            handler.Requests.Clear();
            var result = WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root, handler,
                expectedOffer: offer).GetAwaiter().GetResult();
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
                AssertEqual(GitHubUpdateState.OfferAvailable, available.GitHubUpdateState);
                AssertFalse(available.GitHubApplyEnabled);
                available.DownloadOfferedUpdateAsync().GetAwaiter().GetResult();
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
            vm.DownloadOfferedUpdateAsync().GetAwaiter().GetResult();
            var packageDirectory = Path.Combine(fixture.Root, ".update", "work");
            var firstCandidate = Directory.GetFiles(packageDirectory, "github-update-*.zip").Single();

            var popupCount = 0;
            vm.UpdatePopupRequested += () => popupCount++;
            vm.DeferUpdate(false);
            vm.RecheckUpdateCommand.Execute(null);
            AssertEqual(1, popupCount);
            AssertTrue(File.Exists(firstCandidate));

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
            vm.DownloadOfferedUpdateAsync().GetAwaiter().GetResult();
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
            var updateLog = Path.Combine(fixture.Root, ".update", "update.log");
            if (result != 0 && File.Exists(updateLog))
            {
                var diagnostic = File.ReadAllText(updateLog);
                if (diagnostic.Length > 16000) diagnostic = diagnostic[^16000..];
                Console.Error.WriteLine("WPF_HANDOFF_UPDATE_LOG_BEGIN\n" + diagnostic + "\nWPF_HANDOFF_UPDATE_LOG_END");
            }
            AssertEqual(0, result);
            AssertFalse(File.Exists(check.PackagePath));
            AssertEqual(dataHash, HashFile(dataPath));
        }
        finally { DeleteUpdateFixture(fixture); }
    }

    private static void WpfUpdate_GitHubRetries1175AgainstExactPreState()
    {
        var fixture = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(fixture, "test-owner", "test-repo");
            var check = CheckGitHubPackage(fixture);
            AssertEqual(GitHubUpdateState.UpdateAvailable, check.State);
            var dataPath = Path.Combine(fixture.Root, "data", "keep.bin");
            var dataHash = HashFile(dataPath);
            var attempts = new Dictionary<string, int>(StringComparer.Ordinal);
            var injected = new HashSet<string>(StringComparer.Ordinal);
            void InjectOnce(string source, string destination, int attempt)
            {
                var relative = Path.GetRelativePath(fixture.Root, destination).Replace(Path.DirectorySeparatorChar, '/');
                if (relative != "VNText Studio.exe") return;
                attempts[relative] = attempt;
                if (!injected.Add(relative)) return;
                throw new IOException("injected 1175", unchecked((int)0x80070497));
            }

            var result = WpfUpdateService.RunGitHubUpdaterForTest(fixture.SourcePath, fixture.Root,
                check.PackagePath, check.PackageSha256, check.Version, replaceAttemptHook: InjectOnce);

            AssertEqual(0, result);
            AssertTrue(attempts["VNText Studio.exe"] is >= 2 and <= 4);
            AssertEqual(fixture.CandidateExeHash, HashFile(Path.Combine(fixture.Root, "VNText Studio.exe")));
            AssertEqual(dataHash, HashFile(dataPath));
            AssertTrue(File.ReadAllText(Path.Combine(fixture.Root, ".update", "update.log"))
                .Contains("replace failed path=VNText Studio.exe hresult=0x80070497 attempt=1", StringComparison.Ordinal));
        }
        finally { DeleteUpdateFixture(fixture); }
    }

    private static void WpfUpdate_GitHubRetryRefusesChangedInputsAndBoundsPersistent1175()
    {
        foreach (var mutate in new[] { "staged", "target" })
        {
            var fixture = CreateUpdateFixture("1.0.1");
            try
            {
                ConfigureGitHubSource(fixture, "test-owner", "test-repo");
                var check = CheckGitHubPackage(fixture);
                AssertEqual(GitHubUpdateState.UpdateAvailable, check.State);
                var dataPath = Path.Combine(fixture.Root, "data", "keep.bin");
                var dataHash = HashFile(dataPath);
                var targetPath = Path.Combine(fixture.Root, "VNText Studio.exe");
                var attempts = 0;
                void MutateThenInject(string source, string destination, int attempt)
                {
                    if (Path.GetRelativePath(fixture.Root, destination).Replace(Path.DirectorySeparatorChar, '/') != "VNText Studio.exe")
                        return;
                    attempts = attempt;
                    if (attempt != 1) return;
                    File.WriteAllText(mutate == "staged" ? source : destination,
                        "changed after the injected 1175 failure");
                    throw new IOException("injected 1175", unchecked((int)0x80070497));
                }

                var result = WpfUpdateService.RunGitHubUpdaterForTest(fixture.SourcePath, fixture.Root,
                    check.PackagePath, check.PackageSha256, check.Version, replaceAttemptHook: MutateThenInject);

                AssertEqual(5, result);
                AssertEqual(1, attempts);
                AssertEqual(dataHash, HashFile(dataPath));
                if (mutate == "staged")
                    AssertEqual(fixture.BaselineExeHash, HashFile(targetPath));
                else
                    AssertEqual("changed after the injected 1175 failure", File.ReadAllText(targetPath));
                AssertTrue(File.ReadAllText(Path.Combine(fixture.Root, ".update", "update.log"))
                    .Contains("Replacement " + mutate + " file changed", StringComparison.Ordinal));
            }
            finally { DeleteUpdateFixture(fixture); }
        }

        var persistent = CreateUpdateFixture("1.0.1");
        try
        {
            ConfigureGitHubSource(persistent, "test-owner", "test-repo");
            var check = CheckGitHubPackage(persistent);
            AssertEqual(GitHubUpdateState.UpdateAvailable, check.State);
            var dataPath = Path.Combine(persistent.Root, "data", "keep.bin");
            var dataHash = HashFile(dataPath);
            var attempts = 0;
            void InjectPersistent(string _source, string destination, int attempt)
            {
                if (Path.GetRelativePath(persistent.Root, destination).Replace(Path.DirectorySeparatorChar, '/') != "VNText Studio.exe")
                    return;
                attempts = attempt;
                throw new IOException("injected persistent 1175", unchecked((int)0x80070497));
            }

            var result = WpfUpdateService.RunGitHubUpdaterForTest(persistent.SourcePath, persistent.Root,
                check.PackagePath, check.PackageSha256, check.Version, replaceAttemptHook: InjectPersistent);

            AssertEqual(5, result);
            AssertEqual(4, attempts);
            AssertEqual(persistent.BaselineExeHash, HashFile(Path.Combine(persistent.Root, "VNText Studio.exe")));
            AssertEqual(dataHash, HashFile(dataPath));
            var log = File.ReadAllText(Path.Combine(persistent.Root, ".update", "update.log"));
            AssertEqual(4, log.Split("replace failed path=VNText Studio.exe hresult=0x80070497", StringSplitOptions.None).Length - 1);
        }
        finally { DeleteUpdateFixture(persistent); }
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

    private static object GitHubReleaseWithDate(string tag, bool draft, bool prerelease, string publishedAt, params object[] assets) =>
        new { tag_name = tag, draft, prerelease, published_at = publishedAt, assets };

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
            var version = RequiredExecutableProductVersion("VNTEXT_WPF_CANDIDATE_EXE");
            var transaction = FullAppUpdateService.ReadVerifiedSuccess(fixture.Root, version, "");
            AssertTrue(transaction is not null && transaction.StartsWith("txn-", StringComparison.Ordinal));
            AssertEqual<string?>(null, FullAppUpdateService.ReadVerifiedSuccess(fixture.Root, version, transaction!));
            AssertEqual<string?>(null, FullAppUpdateService.ReadVerifiedSuccess(fixture.Root, "0.0.0", ""));
            var pending = Path.Combine(fixture.Root, ".update", "pending-full-app-update.json");
            File.WriteAllText(pending, "{}");
            AssertEqual<string?>(null, FullAppUpdateService.ReadVerifiedSuccess(fixture.Root, version, ""));
            File.Delete(pending);
            File.AppendAllText(Path.Combine(fixture.Root, "VNText Studio.exe"), "tamper");
            AssertEqual<string?>(null, FullAppUpdateService.ReadVerifiedSuccess(fixture.Root, version, ""));
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
            AssertEqual<string?>(null, FullAppUpdateService.ReadVerifiedSuccess(fixture.Root, "1.0.0", ""));
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

    private static void FullAppUpdate_Retries1175AgainstExactPreState()
    {
        var fixture = CreateFullAppUpdateFixture();
        try
        {
            var injected = new HashSet<string>(StringComparer.Ordinal);
            var attempts = new Dictionary<string, int>(StringComparer.Ordinal);
            void InjectOnce(string source, string destination, int attempt)
            {
                var relative = Path.GetRelativePath(fixture.Root, destination).Replace(Path.DirectorySeparatorChar, '/');
                if (relative is not ("app/worker/replace.txt" or ".update/pending-full-app-update.json")) return;
                attempts[relative] = attempt;
                if (!injected.Add(relative)) return;
                throw new IOException("injected 1175", unchecked((int)0x80070497));
            }

            var exit = FullAppUpdateService.RunForTest(fixture.SourcePath, fixture.Root,
                healthCheck: (exe, root) => root == fixture.Root && HashFile(exe) == fixture.CandidateExeHash,
                replaceAttemptHook: InjectOnce);

            AssertEqual(0, exit);
            // The injected 1175 must cause a retry; Windows may also report a
            // native 1175 on the next Replace, so verify the bounded retry window.
            AssertTrue(attempts["app/worker/replace.txt"] is >= 2 and <= 4);
            AssertTrue(attempts[".update/pending-full-app-update.json"] is >= 2 and <= 4);
            AssertEqual(fixture.CandidateExeHash, HashFile(Path.Combine(fixture.Root, "VNText Studio.exe")));
            AssertEqual("candidate content", File.ReadAllText(Path.Combine(fixture.Root, "app", "worker", "replace.txt")));
            AssertTrue(ReadFullAppUpdateLog(fixture).Contains("replace failed path=app/worker/replace.txt hresult=0x80070497 attempt=1", StringComparison.Ordinal));
            AssertTrue(ReadFullAppUpdateLog(fixture).Contains("replace failed path=.update/pending-full-app-update.json hresult=0x80070497 attempt=1", StringComparison.Ordinal));
            AssertFalse(ReadFullAppUpdateLog(fixture).Contains(fixture.Root, StringComparison.OrdinalIgnoreCase));
        }
        finally { DeleteFullAppUpdateFixture(fixture); }
    }

    private static void FullAppUpdate_Persistent1175RollsBack()
    {
        var fixture = CreateFullAppUpdateFixture();
        try
        {
            var attempts = 0;
            void InjectPersistent(string source, string destination, int attempt)
            {
                var relative = Path.GetRelativePath(fixture.Root, destination).Replace(Path.DirectorySeparatorChar, '/');
                if (relative != "VNText Studio.exe") return;
                attempts++;
                throw new IOException("injected persistent 1175", unchecked((int)0x80070497));
            }

            var exit = FullAppUpdateService.RunForTest(fixture.SourcePath, fixture.Root,
                healthCheck: (exe, _) => HashFile(exe) == fixture.BaselineExeHash,
                replaceAttemptHook: InjectPersistent);

            AssertEqual(5, exit);
            AssertEqual(4, attempts);
            AssertEqual(fixture.BaselineExeHash, HashFile(Path.Combine(fixture.Root, "VNText Studio.exe")));
            AssertEqual("baseline content", File.ReadAllText(Path.Combine(fixture.Root, "app", "worker", "replace.txt")));
            AssertTrue(File.Exists(Path.Combine(fixture.Root, "app", "worker", "obsolete.txt")));
            AssertFalse(File.Exists(Path.Combine(fixture.Root, "app", "worker", "added.txt")));
            AssertFalse(File.Exists(Path.Combine(fixture.Root, ".update", "pending-full-app-update.json")));
            AssertEqual(4, ReadFullAppUpdateLog(fixture).Split("replace failed path=VNText Studio.exe", StringSplitOptions.None).Length - 1);
        }
        finally { DeleteFullAppUpdateFixture(fixture); }
    }

    private static void FullAppUpdate_1175RefusesChangedStagedAndTarget()
    {
        var stagedMutation = CreateFullAppUpdateFixture();
        try
        {
            var injected = false;
            void MutateStaged(string source, string destination, int attempt)
            {
                if (Path.GetRelativePath(stagedMutation.Root, destination) != "VNText Studio.exe" || injected) return;
                injected = true;
                File.WriteAllText(source, "changed staged bytes");
                throw new IOException("injected 1175 after staged mutation", unchecked((int)0x80070497));
            }
            var exit = FullAppUpdateService.RunForTest(stagedMutation.SourcePath, stagedMutation.Root,
                healthCheck: (exe, _) => HashFile(exe) == stagedMutation.BaselineExeHash,
                replaceAttemptHook: MutateStaged);
            AssertEqual(5, exit);
            AssertEqual(stagedMutation.BaselineExeHash, HashFile(Path.Combine(stagedMutation.Root, "VNText Studio.exe")));
            AssertEqual("baseline content", File.ReadAllText(Path.Combine(stagedMutation.Root, "app", "worker", "replace.txt")));
            AssertFalse(File.Exists(Path.Combine(stagedMutation.Root, ".update", "pending-full-app-update.json")));
            AssertTrue(ReadFullAppUpdateLog(stagedMutation).Contains("staged file changed from its planned hash or size: VNText Studio.exe", StringComparison.Ordinal));
        }
        finally { DeleteFullAppUpdateFixture(stagedMutation); }

        var targetMutation = CreateFullAppUpdateFixture();
        try
        {
            var injected = false;
            void MutateTarget(string source, string destination, int attempt)
            {
                if (Path.GetRelativePath(targetMutation.Root, destination) != "VNText Studio.exe" || injected) return;
                injected = true;
                File.WriteAllText(destination, "changed target bytes");
                throw new IOException("injected 1175 after target mutation", unchecked((int)0x80070497));
            }
            var exit = FullAppUpdateService.RunForTest(targetMutation.SourcePath, targetMutation.Root,
                replaceAttemptHook: MutateTarget);
            AssertEqual(6, exit);
            AssertEqual("changed target bytes", File.ReadAllText(Path.Combine(targetMutation.Root, "VNText Studio.exe")));
            AssertTrue(File.Exists(Path.Combine(targetMutation.Root, ".update", "pending-full-app-update.json")));
            AssertTrue(ReadFullAppUpdateLog(targetMutation).Contains("target changed from its expected pre-state: VNText Studio.exe", StringComparison.Ordinal));
        }
        finally { DeleteFullAppUpdateFixture(targetMutation); }
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
                $"full-app-update-from-{ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_BASELINE_EXE")!)}-to-{ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")!)}-{digest[..16]}.zip"));
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

    private static void FullAppUpdate_BaselineRoutesChooseVerifiedHop()
    {
        var fixture = CreateFullAppUpdateFixture();
        try
        {
            var bytes = File.ReadAllBytes(fixture.PackagePath); var digest = HashBytes(bytes);
            var current = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_BASELINE_EXE")!)!;
            var target = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")!)!;
            var targetCore = Version.Parse(target);
            var future = new Version(targetCore.Major, targetCore.Minor, targetCore.Build + 1).ToString();
            _ = CreateFullAppGitHubHandler(fixture, digest, bytes.LongLength, FullAppAssetUrl(fixture, digest), bytes);
            var name = $"full-app-update-from-{current}-to-{target}-{digest[..16]}.zip";
            var url = $"https://github.com/test-owner/test-repo/releases/download/v{target}/{name}";
            object Asset(string assetName, string version) => GitHubAsset(assetName, "sha256:" + digest, bytes.LongLength,
                $"https://github.com/test-owner/test-repo/releases/download/v{version}/{assetName}");
            var releases = JsonSerializer.Serialize(new[] {
                GitHubRelease("v" + future, false, false,
                    Asset($"full-app-update-{future}-{digest[..16]}.zip", future),
                    Asset($"full-app-update-from-{target}-to-{future}-{digest[..16]}.zip", future)),
                GitHubRelease("v" + target, false, false,
                    Asset($"full-app-update-{target}-{digest[..16]}.zip", target), Asset(name, target)) });
            var handler = new TestHttpMessageHandler((request, _) => {
                if (request.RequestUri?.Host == "api.github.com") return Task.FromResult(JsonResponse(releases));
                AssertEqual(new Uri(url), request.RequestUri!); return Task.FromResult(BinaryResponse(bytes));
            });
            var offer = WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root, handler, metadataOnly: true).GetAwaiter().GetResult();
            AssertEqual(GitHubUpdateState.OfferAvailable, offer.State); AssertEqual(future, offer.Version);
            AssertTrue(offer.FullAppRoute); AssertEqual(2, offer.Route?.Count);
            AssertEqual(current, offer.Route![0].FromVersion); AssertEqual(target, offer.Route[0].Version);
            AssertEqual(target, offer.Route[1].FromVersion); AssertEqual(future, offer.Route[1].Version);
            AssertEqual(url, offer.AssetUrl); AssertEqual(1, handler.Requests.Count);
            var invalid = releases.Replace(name, name.Replace(digest[..16], new string('0', 16)));
            var invalidHandler = new TestHttpMessageHandler((_, _) => Task.FromResult(JsonResponse(invalid)));
            AssertEqual(GitHubUpdateState.InvalidMetadata, WpfUpdateService.CheckGitHubUpdateAsync(fixture.Root, invalidHandler, metadataOnly:true).GetAwaiter().GetResult().State);
            AssertEqual(1, invalidHandler.Requests.Count);
        }
        finally { DeleteFullAppUpdateFixture(fixture); }
    }

    private static void FullAppUpdate_RouteUpdaterCleansEveryOwnedPackageOnHashFailure()
    {
        var fixture = CreateFullAppUpdateFixture();
        try
        {
            var current = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_BASELINE_EXE")!)!;
            var target = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")!)!;
            var futureCore = Version.Parse(target);
            var future = new Version(futureCore.Major, futureCore.Minor, futureCore.Build + 1).ToString();
            var fixtureBytes = File.ReadAllBytes(fixture.PackagePath);
            _ = CreateFullAppGitHubHandler(fixture, HashBytes(fixtureBytes), fixtureBytes.LongLength,
                FullAppAssetUrl(fixture, HashBytes(fixtureBytes)), fixtureBytes);
            var work = Path.Combine(fixture.Root, ".update", "work");
            Directory.CreateDirectory(work);
            var first = Path.Combine(work, "route-first.zip");
            var second = Path.Combine(work, "route-second.zip");
            File.WriteAllText(first, "tampered first package");
            File.WriteAllText(second, "valid downloaded second package");
            var descriptor = Path.Combine(work, "route.json");
            File.WriteAllText(descriptor, JsonSerializer.Serialize(new
            {
                schema = 1, target_version = future,
                hops = new[]
                {
                    new { from_version = current, version = target, package_path = first, package_sha256 = new string('0', 64) },
                    new { from_version = target, version = future, package_path = second, package_sha256 = HashFile(second) },
                },
            }));
            var starts = 0;
            var code = FullAppUpdateService.RunGitHubRouteUpdater(fixture.SourcePath, fixture.Root, int.MaxValue, null,
                descriptor, HashFile(descriptor), future, bindToRunningInstall: false, waitForProcesses: false,
                startAppOverride: _ => starts++);
            AssertEqual(5, code);
            AssertEqual(1, starts);
            AssertFalse(File.Exists(first));
            AssertFalse(File.Exists(second));
            AssertFalse(File.Exists(descriptor));
            AssertEqual(current, File.ReadAllText(Path.Combine(fixture.Root, "app", "VERSION.txt")).Trim());
            using var result = JsonDocument.Parse(File.ReadAllText(Path.Combine(fixture.Root, ".update", "github-route-result.json")));
            AssertEqual(current, result.RootElement.GetProperty("completed_version").GetString());
            AssertEqual(0, result.RootElement.GetProperty("completed_hops").GetInt32());
        }
        finally { DeleteFullAppUpdateFixture(fixture); }
    }

    private static string FullAppAssetUrl(FullAppUpdateFixture fixture, string digest)
    {
        var version = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")!);
        var baseline = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_BASELINE_EXE")!);
        var name = $"full-app-update-from-{baseline}-to-{version}-{digest[..16]}.zip";
        return $"https://github.com/test-owner/test-repo/releases/download/v{version}/{name}";
    }

    private static TestHttpMessageHandler CreateFullAppGitHubHandler(FullAppUpdateFixture fixture,
        string digest, long size, string downloadUrl, byte[] packageBytes, string notes = "", bool slowDownload = false)
    {
        var source = JsonSerializer.Deserialize<Dictionary<string, object>>(File.ReadAllText(fixture.SourcePath))!;
        source["github_owner"] = "test-owner";
        source["github_repository"] = "test-repo";
        File.WriteAllText(fixture.SourcePath, JsonSerializer.Serialize(source));
        var version = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")!);
        var baseline = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_BASELINE_EXE")!);
        var assetName = $"full-app-update-from-{baseline}-to-{version}-{digest[..16]}.zip";
        var releases = JsonSerializer.Serialize(new[]
        {
            GitHubRelease("v" + version, false, false,
                GitHubAsset(assetName, "sha256:" + digest, size, downloadUrl)),
        });
        var apiUrl = new Uri("https://api.github.com/repos/test-owner/test-repo/releases?per_page=100");
        var releaseNodes = System.Text.Json.Nodes.JsonNode.Parse(releases)!;
        releaseNodes[0]!["body"] = notes;
        releases = releaseNodes.ToJsonString();
        return new TestHttpMessageHandler((request, _) =>
        {
            if (request.RequestUri == apiUrl) return Task.FromResult(JsonResponse(releases));
            if (request.RequestUri == new Uri(downloadUrl))
            {
                if (!slowDownload) return Task.FromResult(BinaryResponse(packageBytes));
                var content = new StreamContent(new NativeUiDownloadStream(packageBytes));
                content.Headers.ContentLength = packageBytes.LongLength;
                return Task.FromResult(new HttpResponseMessage(HttpStatusCode.OK) { Content = content });
            }
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

    // Explicit TEST ONLY presentation source. No HTTP, settings, packages or process launch.
    private sealed class FixturePresentation : VNText.Studio.App.IUpdatePresentation
    {
        public string CurrentVersion { get; set; } = "TEST-0.1.5";
        public string Version { get; set; } = "TEST-0.1.6";
        public string ReleaseDate { get; set; } = "24/10/2026";
        public string Notes { get; set; } = "# Cải tiến giao diện\n- Cửa sổ cập nhật gọn hơn.\n- Ghi chú phát hành hiển thị trong ứng dụng.\n\n## Chi tiết thay đổi\n" + string.Join("\n", Enumerable.Range(1, 30).Select(i => "- Dòng ghi chú fixture " + i));
        public string Status { get; private set; } = "TEST ONLY";
        public bool Available { get; private set; }
        public bool Downloading { get; private set; }
        public bool Ready { get; private set; }
        public long Received { get; private set; }
        public long Total { get; private set; }
        public bool CanStart => !Downloading;
        public bool IsTestFixture => true;
        public int Starts, Cancels, Restarts, Checks;
        private TaskCompletionSource? _pending;
        public event System.ComponentModel.PropertyChangedEventHandler? PropertyChanged;
        public event Action? OfferRequested;
        private void Notify() => PropertyChanged?.Invoke(this, new(""));
        public Task CheckAsync() { Checks++; SetState("available"); OfferRequested?.Invoke(); return Task.CompletedTask; }
        public Task DownloadAsync()
        {
            if (Downloading) return _pending?.Task ?? Task.CompletedTask;
            Starts++; _pending = new(TaskCreationOptions.RunContinuationsAsynchronously); SetState("downloading"); return _pending.Task;
        }
        public void Cancel() { Cancels++; Downloading = false; Status = "TEST ONLY — đã hủy"; _pending?.TrySetResult(); Notify(); }
        public void Defer(bool skip) { Status = skip ? "TEST ONLY — skip không ghi settings" : "TEST ONLY — để sau"; Notify(); }
        public void Restart() { if (Ready) { Restarts++; Status = "TEST ONLY — restart được ghi nhận, không chạy process"; Notify(); } }
        public void SetState(string state)
        {
            Available = state is "available" or "downloading" or "ready" or "about-ready" or "notes";
            Downloading = state == "downloading"; Ready = state is "ready" or "about-ready";
            Total = Downloading ? 1000 : 0; Received = Downloading ? 420 : 0;
            Status = "TEST ONLY — " + state;
            if (Ready) _pending?.TrySetResult(); Notify();
        }
        public void Dispose() { _pending?.TrySetCanceled(); }
    }
    private static void UpdaterPresentation_DynamicStatesAndSafeActions()
    {
        using var source = new FixturePresentation { CurrentVersion = "fixture-current-17", Version = "fixture-next-29" };
        var offers = 0; source.OfferRequested += () => offers++;
        source.CheckAsync().GetAwaiter().GetResult(); AssertEqual(1, offers);
        var available = VNText.Studio.App.UpdateViewState.From(source);
        AssertEqual("fixture-next-29", available.Version); AssertEqual("fixture-current-17", available.Current);
        AssertEqual("Cập nhật ngay", available.PrimaryLabel);
        var first = source.DownloadAsync(); var second = source.DownloadAsync();
        AssertEqual(1, source.Starts); AssertTrue(ReferenceEquals(first, second));
        var downloading = VNText.Studio.App.UpdateViewState.From(source);
        AssertTrue(downloading.Downloading); AssertEqual(42d, downloading.Percent); AssertFalse(downloading.CanStart);
        source.Cancel(); AssertEqual(1, source.Cancels); AssertFalse(source.Downloading);
        source.SetState("ready"); var ready = VNText.Studio.App.UpdateViewState.From(source);
        AssertTrue(ready.Ready); AssertEqual("Khởi động lại", ready.PrimaryLabel);
        source.Restart(); AssertEqual(1, source.Restarts); source.Defer(true);
        AssertTrue(source.Status.Contains("không ghi settings", StringComparison.Ordinal));
    }
    private static int RunPresentationFixture(string[] args)
    {
        string Value(string flag, string fallback) { var i = Array.IndexOf(args, flag); return i >= 0 && i + 1 < args.Length ? args[i + 1] : fallback; }
        var state = Value("--presentation-state", "about");
        if (!new[] { "about", "available", "downloading", "ready", "notes", "about-ready", "success" }.Contains(state)) throw new ArgumentException("Unsupported TEST ONLY presentation state");
        var auto = args.Contains("--presentation-smoke", StringComparer.Ordinal);
        var app = new Application { ShutdownMode = auto ? ShutdownMode.OnExplicitShutdown : ShutdownMode.OnMainWindowClose };
        foreach (var dictionary in new[] { "DesignTokens", "IconGeometries", "ControlStyles" })
            app.Resources.MergedDictionaries.Add(new ResourceDictionary { Source = new Uri($"pack://application:,,,/VNText.Studio.App;component/Themes/{dictionary}.xaml") });
        var states = new Queue<string>(auto ? new[] { "about", "available", "downloading", "ready", "notes", "about-ready", "success" } : new[] { state });
        var checkedStates = new List<string>(); Exception? failed = null;
        void Next()
        {
            if (states.Count == 0) { Console.WriteLine(JsonSerializer.Serialize(new { test_only = true, smoke_states = checkedStates, ok = failed is null })); app.Shutdown(failed is null ? 0 : 1); return; }
            var current = states.Dequeue();
            var source = new FixturePresentation(); source.SetState(current == "success" ? "about" : current);
            var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false); vm.SelectedTab = WorkflowTabs.Settings;
            if (current == "notes") vm.ReleaseNotesHistory.Add(new ReleaseNotesCacheEntry
            {
                Version = source.Version, ReleaseDate = source.ReleaseDate, Notes = source.Notes
            });
            var window = new VNText.Studio.App.MainWindow(vm, source) { Title = "VNText Studio — TEST ONLY updater presentation" };
            var ticks = 0;
            var timer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(200) };
            timer.Tick += (_, _) =>
            {
                try
                {
                    ticks++;
                    if (ticks > 30) throw new TimeoutException("TEST ONLY fixture modal did not appear");
                    var modal = app.Windows.OfType<VNText.Studio.App.UpdateWindow>().SingleOrDefault();
                    if (current is "about" or "about-ready")
                    {
                        AssertTrue(modal is null);
                        AssertTrue(FindText(window, "Calanh")); AssertTrue(FindText(window, "Apache-2.0"));
                        AssertTrue(FindText(window, "Phản hồi"));
                        checkedStates.Add(current); timer.Stop(); window.Close(); return;
                    }
                    if (modal is null) return;
                    AssertTrue(modal.Owner == window); AssertTrue(modal.IsVisible);
                    if (current == "notes")
                    {
                        if (modal.SizeToContent != SizeToContent.Manual) throw new InvalidOperationException("fixture: release notes should use bounded manual sizing");
                        if (modal.ActualHeight > 720 || modal.ActualHeight >= window.ActualHeight * .9) throw new InvalidOperationException($"fixture: release-notes modal too tall {modal.ActualHeight}/{window.ActualHeight}");
                    }
                    else
                    {
                        if (modal.SizeToContent != SizeToContent.Height) throw new InvalidOperationException("fixture: status modal should size to content");
                        if (modal.ActualHeight >= window.ActualHeight * .9) throw new InvalidOperationException($"fixture: modal too tall {modal.ActualHeight}/{window.ActualHeight}");
                    }
                    AssertTrue(System.Windows.Input.KeyboardNavigation.GetTabNavigation(modal) == System.Windows.Input.KeyboardNavigationMode.Cycle);
                    for (var focusStep = 0; focusStep < 10; focusStep++)
                    {
                        var focused = System.Windows.Input.Keyboard.FocusedElement as DependencyObject;
                        if (focused is null || Window.GetWindow(focused) != modal) throw new InvalidOperationException($"fixture: keyboard focus left modal at step {focusStep}; focused={focused}");
                        if (focused is UIElement control) control.MoveFocus(new System.Windows.Input.TraversalRequest(System.Windows.Input.FocusNavigationDirection.Next));
                    }
                    AssertTrue(((UIElement)window.Content).Effect is System.Windows.Media.Effects.BlurEffect);
                    AssertEqual(1, window.OwnedWindows.Count);
                    AssertTrue(FindText(modal, current == "success" ? "0.1.13" : source.Version));
                    if (current == "downloading") AssertTrue(FindText(modal, "42%"));
                    if (current == "ready") AssertTrue(FindText(modal, "đã sẵn sàng"));
                    if (current == "notes") AssertTrue(FindText(modal, "Cải tiến giao diện"));
                    if (current == "success")
                    {
                        AssertTrue(FindText(modal, "Đã cập nhật thành công lên phiên bản v0.1.13."));
                        AssertTrue(FindText(modal, "đã cập nhật lên v0.1.13 và sẵn sàng sử dụng"));
                        AssertFalse(FindText(modal, "đã có phiên bản mới"));
                        AssertFalse(FindText(modal, "Hãy khởi động lại để áp dụng"));
                    }
                    checkedStates.Add(current); timer.Stop(); modal.Close();
                    AssertTrue(((UIElement)window.Content).Effect is null);
                    window.Dispatcher.BeginInvoke(new Action(window.Close));
                }
                catch (Exception ex)
                {
                    failed = ex; Console.Error.WriteLine(ex); timer.Stop();
                    foreach (var modal in app.Windows.OfType<VNText.Studio.App.UpdateWindow>().ToArray()) modal.Close();
                    window.Close(); app.Shutdown(1);
                }
            };
            window.Loaded += (_, _) =>
            {
                var tabs = FindVisual<TabControl>((ScrollViewer)window.FindName("SettingsScrollViewer")); if (tabs is not null) tabs.SelectedIndex = 2;
                Console.WriteLine(JsonSerializer.Serialize(new { test_only = true, state = current, no_network = true, no_settings_write = true, no_apply_restart = true, pid = Environment.ProcessId }));
                if (auto) timer.Start();
                window.Dispatcher.BeginInvoke(new Action(() =>
                {
                    if (current == "success") window.ShowUpdateDialog(false, "0.1.13");
                    else if (current is "available" or "downloading" or "ready" or "notes") window.ShowUpdateDialog(current == "notes");
                }));
            };
            window.Closed += (_, _) => { timer.Stop(); if (auto && failed is null) app.Dispatcher.BeginInvoke(new Action(Next)); };
            window.Show();
        }
        Next(); app.Run(); return failed is null ? 0 : 1;
    }
    private static bool FindText(DependencyObject parent, string text)
    {
        if (parent is TextBlock block && new System.Windows.Documents.TextRange(block.ContentStart, block.ContentEnd).Text.Contains(text, StringComparison.Ordinal)) return true;
        for (var i = 0; i < System.Windows.Media.VisualTreeHelper.GetChildrenCount(parent); i++)
            if (FindText(System.Windows.Media.VisualTreeHelper.GetChild(parent, i), text)) return true;
        return false;
    }
    private static T? FindVisual<T>(DependencyObject parent) where T : DependencyObject
    {
        for (var i = 0; i < System.Windows.Media.VisualTreeHelper.GetChildrenCount(parent); i++)
        { var child = System.Windows.Media.VisualTreeHelper.GetChild(parent, i); if (child is T found) return found; var nested = FindVisual<T>(child); if (nested is not null) return nested; }
        return null;
    }

    private static int RunNativeUpdateUi(bool layoutOnly)
    {
        var fixture = CreateFullAppUpdateFixture();
        try
        {
            var package = File.ReadAllBytes(fixture.PackagePath);
            var digest = HashBytes(package);
            var notes = string.Join("\n", Enumerable.Range(1, 120).Select(i => $"{i}. Ghi chú fixture: kiểm cuộn nội dung; không phải Release công khai."));
            var handler = CreateFullAppGitHubHandler(fixture, digest, package.LongLength, FullAppAssetUrl(fixture, digest), package, notes, slowDownload: true);
            var app = new Application { ShutdownMode = ShutdownMode.OnMainWindowClose };
            foreach (var dictionary in new[] { "DesignTokens", "IconGeometries", "ControlStyles" })
                app.Resources.MergedDictionaries.Add(new ResourceDictionary
                { Source = new Uri($"pack://application:,,,/VNText.Studio.App;component/Themes/{dictionary}.xaml") });
            var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false,
                githubHttpHandler: handler, updateInstallRoot: fixture.Root);
            vm.PropertyChanged += (_, e) =>
            {
                if (e.PropertyName == nameof(vm.GitHubUpdateState))
                    Console.WriteLine(JsonSerializer.Serialize(new { state = vm.GitHubUpdateState.ToString(), requests = handler.Requests.Count }));
                if (e.PropertyName == nameof(vm.DownloadReceived))
                    Console.WriteLine(JsonSerializer.Serialize(new { received = vm.DownloadReceived, total = vm.DownloadTotal }));
            };
            var window = new VNText.Studio.App.MainWindow(vm);
            window.Loaded += (_, _) => Console.WriteLine(JsonSerializer.Serialize(new { pid = Environment.ProcessId, root = fixture.Root,
                baseline_version = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_BASELINE_EXE")!),
                candidate_version = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")!),
                package_sha256 = digest, scope = "generated local UI fixture; mocked HTTP; no public release or native apply acceptance" }));
            app.Run(window);
            AssertEqual(layoutOnly ? GitHubUpdateState.OfferAvailable : GitHubUpdateState.UpdateAvailable, vm.GitHubUpdateState);
            var updateWork = Path.Combine(fixture.Root, ".update", "work");
            var stagedPackages = Directory.Exists(updateWork)
                ? Directory.GetFiles(updateWork, "github-update-*.zip")
                : [];
            AssertEqual(0, stagedPackages.Length);
            Console.WriteLine(layoutOnly ? "Native layout fixture closed at offer; no download/apply/restart acceptance."
                : "Native popup ready/defer/reopen and lease disposal: PASS; apply/restart not exercised.");
            return 0;
        }
        finally { DeleteFullAppUpdateFixture(fixture); }
    }

    private sealed class NativeUiDownloadStream(byte[] bytes) : MemoryStream(bytes, writable: false)
    {
        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default)
        {
            // Leave enough time for actual popup progress/cancel interaction without changing package bytes.
            await Task.Delay(150, cancellationToken);
            return await base.ReadAsync(buffer[..Math.Min(buffer.Length, 256)], cancellationToken);
        }
    }

    private sealed class FakePathPicker : IPathPickerService
    {
        public string? InputPath { get; set; }
        public string? OutputFolder { get; set; }
        public string? TranslationCsv { get; set; }
        public string? RenpySdkFolder { get; set; }
        public int InputPicks { get; private set; }
        public string? PickInputPath() { InputPicks++; return InputPath; }
        public string? PickOutputFolder() => OutputFolder;
        public string? LastCsvTitle { get; set; }
        public string? PickTranslationCsvFile(string? title = null) { LastCsvTitle = title; return TranslationCsv; }
        public string? PickRenpySdkFolder() => RenpySdkFolder;
        public string? ImageFile { get; set; }
        public string? PickImageFile(bool review = false) => ImageFile;
        public bool OpenPath(string path) => true;
    }
}
