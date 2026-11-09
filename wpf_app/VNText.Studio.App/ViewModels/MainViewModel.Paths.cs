using System.Collections.Concurrent;
using System.Collections.ObjectModel;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Threading;
using Microsoft.Win32;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;


namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    private async Task<bool> ConfirmCsvBeforeSourceChangeAsync()
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return false;
        if (!CsvEditorDirty) return true;
        var choice = CsvEditorMessageBox("CSV có thay đổi chưa lưu. Lưu trước khi đổi nguồn hoặc thư mục xuất?", "Thay đổi CSV chưa lưu", MessageBoxButton.YesNoCancel, MessageBoxImage.Warning);
        if (choice == MessageBoxResult.Cancel) return false;
        if (choice == MessageBoxResult.Yes) return await SaveCsvEditorAsync();
        DiscardCsvEditorChanges();
        LoadCsvEditor(CsvEditorPath, reload: true);
        return true;
    }
    private async void ChooseInput()
    {
        if (Busy) return;
        var path = _pathPicker.PickInputPath();
        if (!string.IsNullOrWhiteSpace(path) && !string.Equals(path, InputPath, StringComparison.OrdinalIgnoreCase)
            && await ConfirmCsvBeforeSourceChangeAsync())
            InputPath = path;
    }

    private async void ChooseOutput()
    {
        if (Busy) return;
        var path = _pathPicker.PickOutputFolder();
        if (!string.IsNullOrWhiteSpace(path) && !string.Equals(path, OutputPath, StringComparison.OrdinalIgnoreCase)
            && await ConfirmCsvBeforeSourceChangeAsync())
            OutputPath = path;
    }

    // The same dialog serves different intents; a title that says "đã dịch" on the
    // translate input made a blank CSV look invalid.
    internal const string TranslateCsvPickerTitle = "Chọn CSV cần dịch";
    internal const string CsvEditorPickerTitle = "Chọn CSV để sửa";
    internal const string PatchCsvPickerTitle = "Chọn CSV để tạo patch";
    internal const string ImportTranslatedCsvPickerTitle = "Chọn translation.csv đã dịch để nhập";

    /// <summary>
    /// The Patch results (badge, counts, readiness, completion/delivery text) belong to ONE source. When the CSV/package source changes
    /// they are dropped and a fresh check is required; the old artifact on disk is never touched.
    /// </summary>
    private bool _patchSourceStale;

    /// <summary>One readiness state for the Patch badge: ready | review | csvok | stale. Text AND colour in the view both follow this value.</summary>
    public string PatchBadgeKind =>
        PatchPreflightOk ? (PatchBlockedCount > 0 ? "partial" : "ready")
        : PatchPreflightEvaluated ? "review"                 // judged and blocked
        : _patchSourceStale ? "stale"                          // source changed, no check yet
        : CsvValidationOk ? "csvok"                            // CSV valid, preflight not run
        : PatchResultsAvailable ? "review"                     // a check ran and failed (CSV invalid)
        : "idle";                                              // nothing has been checked at all

    public string PatchBadgeText => PatchBadgeKind switch
    {
        "ready" => "SẴN SÀNG",
        "partial" => "PATCH MỘT PHẦN",
        "csvok" => "CSV HỢP LỆ",
        "stale" => "CẦN KIỂM TRA LẠI",
        "idle" => "CHƯA KIỂM TRA",
        _ => "CẦN XEM LẠI",
    };

    /// <summary>The CSV this Patch page uses was saved after the last Build: an artifact on disk exists, but it is NOT proof that it matches the current CSV.
    /// Only a successful Build of the current revision clears this; Validate/preflight update counts and readiness only.</summary>
    private bool _patchArtifactBehindCsv;
    public bool PatchArtifactBehindCsv => _patchArtifactBehindCsv;
    /// <summary>A source change dropped the old results and no new check ran yet: the page shows a neutral "check again" cue instead of nothing.</summary>
    public bool PatchRecheckNeeded => _patchSourceStale && !PatchResultsAvailable;
    public bool PatchCheckCardVisible => PatchResultsAvailable || PatchRecheckNeeded;

    /// <summary>A partial patch (eligible subset, the rest omitted) is not "blocked": only a hard-blocked package keeps that word.</summary>
    public bool PatchPartialReady => PatchPreflightOk && PatchBlockedCount > 0;
    public string PatchBlockedLabel => PatchPartialReady ? "BỎ QUA" : "BỊ CHẶN";

    /// <summary>
    /// Patch-specific state of the CURRENT CSV revision (never the Translate step line): building, built from this revision,
    /// checked and ready (with the omitted count) or blocked.  "Built" comes only from the patch task's own completion (PatchDeliveryReady),
    /// which every source change/save/recheck clears; Validate and an artifact left on disk never imply it.
    /// </summary>
    public string PatchStatusText
    {
        get
        {
            if (Busy && _runningTask == "patch") return "Đang tạo patch…";
            if (!PatchPreflightEvaluated) return "Cần kiểm tra lại CSV hiện tại";
            if (!PatchPreflightOk) return "Chưa thể tạo patch — không có dòng nào đủ điều kiện";
            if (PatchDeliveryReady && !_patchArtifactBehindCsv)
                return PatchBlockedCount > 0
                    ? UiText.Msg("Đã tạo patch từ CSV hiện tại — ghi {0} dòng, bỏ qua {1}", PatchEligibleCount, PatchBlockedCount)
                    : UiText.Msg("Đã tạo patch từ CSV hiện tại — ghi {0} dòng", PatchEligibleCount);
            return PatchBlockedCount > 0
                ? UiText.Msg("Sẵn sàng tạo patch — ghi {0} dòng, bỏ qua {1}", PatchEligibleCount, PatchBlockedCount)
                : UiText.Msg("Sẵn sàng tạo patch — ghi {0} dòng", PatchEligibleCount);
        }
    }

    private void RaisePatchBadge()
    {
        Raise(nameof(PatchStatusText)); Raise(nameof(PatchBlockedLabel)); Raise(nameof(PatchPartialReady));
        Raise(nameof(PatchBadgeKind)); Raise(nameof(PatchBadgeText));
        Raise(nameof(PatchRecheckNeeded)); Raise(nameof(PatchCheckCardVisible)); Raise(nameof(PatchArtifactBehindCsv));
    }

    internal void TestSetTranslationCsvPath(string path) => TranslationCsvPath = path;

    private static bool SameCsvPath(string a, string b)
    {
        try { return string.Equals(Path.GetFullPath(a).TrimEnd('\\', '/'), Path.GetFullPath(b).TrimEnd('\\', '/'), StringComparison.OrdinalIgnoreCase); }
        catch (Exception) { return string.Equals(a, b, StringComparison.OrdinalIgnoreCase); }
    }

    private void InvalidatePatchSourceState(bool csvRevisionChanged = false)
    {
        var hadState = PatchResultsAvailable || PatchPreflightEvaluated || PatchDeliveryReady || CsvValidationOk;
        PatchDeliveryReady = false;
        PatchDeliveryLabel = "";
        PatchInstallInstructions = "";
        if (csvRevisionChanged) _patchArtifactBehindCsv = true;
        if (!hadState && !csvRevisionChanged) return;
        _patchSourceStale = true;
        CsvValidationOk = false;
        CsvValidationMessage = "";
        ReadyForPatch = false;
        PatchPreflightOk = false;
        PatchPreflightEvaluated = false;
        PatchEligibleCount = 0;
        PatchBlockedCount = 0;
        PatchPreflightMessage = csvRevisionChanged
            ? "CSV vừa được lưu — hãy kiểm tra lại. Patch cũ còn trên đĩa là của bản trước; cần đóng gói lại cho bản này."
            : "Nguồn bản dịch đã đổi — hãy kiểm tra lại trước khi tạo patch.";
        PatchResultsAvailable = false;
        PatchResultsExpanded = false;
        RaisePatchBadge();
    }

    internal void TestSetPatchDelivery(string label, string instructions)
    {
        PatchDeliveryLabel = label;
        PatchInstallInstructions = instructions;
        PatchDeliveryReady = true;
    }

    private async void ChooseTranslationCsv()
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return;
        if (CsvEditorDirty && !await SaveCsvEditorAsync()) return;
        var path = _pathPicker.PickTranslationCsvFile(SelectedTab == WorkflowTabs.Patch ? PatchCsvPickerTitle : TranslateCsvPickerTitle);
        if (string.IsNullOrWhiteSpace(path))
            return;

        if (SelectedTab == WorkflowTabs.Patch)
        {
            if (!string.IsNullOrWhiteSpace(CloudRepairPackagePath))
            {
                if (!File.Exists(CloudRepairPackagePath))
                {
                    const string message = "Không tìm thấy gói ZIP đã xuất. Hãy xuất lại gói ở tab Dịch rồi chọn CSV.";
                    AppendLog(message);
                    ShowToast(message, "warning");
                    return;
                }

                BeginCloudRepairImport(path);
                return;
            }
        }

        // Validate before mutating the current selection. Cancel or an invalid
        // candidate must never discard a previously valid external CSV.
        // Fresh Extract packages intentionally start with blank translations. They
        // are valid sources for Translate, while Patch still requires translated rows.
        var requireTranslations = SelectedTab != WorkflowTabs.Translate;
        var candidate = CsvPackageValidator.Validate(path, requireTranslations);
        if (!candidate.Ok)
        {
            AppendLog($"CSV: {candidate.Message}", "ERROR");
            ShowToast(candidate.Message, "warning");
            // The rejected pick is not adopted, but the Translate readiness line must give the same specific reason
            // instead of reporting the default output file as missing.
            _translateRejectedCsvPath = path;
            RefreshTranslateReadiness();
            return;
        }
        _translateRejectedCsvPath = "";

        var previousPath = TranslationCsvPath;
        var previousMessage = CsvValidationMessage;
        var previousOk = CsvValidationOk;
        var previousReady = ReadyForPatch;
        var previousPreflightOk = PatchPreflightOk;
        var previousEligible = PatchEligibleCount;
        var previousBlocked = PatchBlockedCount;
        var previousPreflightMessage = PatchPreflightMessage;
        var previousEvaluated = PatchPreflightEvaluated;
        var previousStale = _patchSourceStale;
        var previousResultsAvailable = PatchResultsAvailable;
        var previousResultsExpanded = PatchResultsExpanded;
        var previousDeliveryReady = PatchDeliveryReady;
        var previousDeliveryLabel = PatchDeliveryLabel;
        var previousInstructions = PatchInstallInstructions;

        TranslationCsvPath = path;
        if (!ValidateTranslationCsv(silent: false, requireTranslations: requireTranslations))
        {
            TranslationCsvPath = previousPath;
            CsvValidationMessage = previousMessage;
            CsvValidationOk = previousOk;
            ReadyForPatch = previousReady;
            PatchPreflightOk = previousPreflightOk;
            PatchEligibleCount = previousEligible;
            PatchBlockedCount = previousBlocked;
            PatchPreflightMessage = previousPreflightMessage;
            PatchPreflightEvaluated = previousEvaluated;
            _patchSourceStale = previousStale;
            RaisePatchBadge();
            PatchResultsAvailable = previousResultsAvailable;
            PatchResultsExpanded = previousResultsExpanded;
            PatchDeliveryLabel = previousDeliveryLabel;
            PatchInstallInstructions = previousInstructions;
            PatchDeliveryReady = previousDeliveryReady;
            return;
        }

        RefreshWorkflow();
    }

    private string? PickCloudRepairPackagePath()
    {
        var (zipTitle, zipFilter) = WpfPathPickerService.CloudRepairSaveDialogSpec();
        var dialog = new SaveFileDialog
        {
            Title = zipTitle,
            Filter = zipFilter,
            DefaultExt = ".zip",
            AddExtension = true,
            FileName = "cloud-repair-package.zip",
            OverwritePrompt = true,
        };
        return dialog.ShowDialog() == true ? dialog.FileName : null;
    }

    private void ChooseRenpySdk()
    {
        if (Busy) return;
        var path = _pathPicker.PickRenpySdkFolder();
        if (!string.IsNullOrWhiteSpace(path))
        {
            RenpySdkPath = path;
            RenpySdkAction = "existing";
            RenpySdkError = "";
            AppendLog("Đã chọn công cụ Ren'Py; ứng dụng sẽ kiểm tra khi lấy text.");
        }
    }

    private bool ValidateTranslationCsv(bool silent, bool requireTranslations = true)
    {
        var path = string.IsNullOrWhiteSpace(TranslationCsvPath)
            ? Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "translation.csv")
            : TranslationCsvPath;
        var result = CsvPackageValidator.Validate(path, requireTranslations);
        if (!silent)
        {
            PatchResultsAvailable = true;
            PatchResultsExpanded = true;
        }
        _patchSourceStale = false;
        CsvValidationOk = result.Ok;
        CsvValidationMessage = result.Message;
        ReadyForPatch = result.Ok;
        if (result.Ok)
        {
            // Heavy Python gate only when user explicitly validates or starts patch (silent=false).
            if (!silent)
                RunPatchPreflight(silent: false);
        }
        else
        {
            PatchPreflightOk = false;
            PatchPreflightEvaluated = false;
            PatchEligibleCount = 0;
            PatchBlockedCount = 0;
            PatchPreflightMessage = "Cần CSV hợp lệ trước khi kiểm tra chất lượng patch.";
        }
        if (!silent)
        {
            AppendLog(result.Ok ? $"CSV OK: {result.Message}" : $"CSV: {result.Message}", result.Ok ? null : "ERROR");
            if (result.Ok)
                AppendLog(PatchPreflightMessage.Replace("\r\n", " | ").Replace("\n", " | "), PatchBlockedCount > 0 ? "WARN" : null);   // an eligible subset still builds, but rows are omitted
            if (result.Ok && SelectedTab != WorkflowTabs.Patch)
                AppendLog("Có thể chuyển sang tab «Tạo patch».");
        }
        return result.Ok;
    }

    private async Task ValidateTranslationCsvAfterEditorSaveAsync(string path)
    {
        CsvValidationResult result;
        TranslateProgress progress;
        try
        {
            (result, progress) = await Task.Run(() =>
            {
                var validation = CsvPackageValidator.Validate(path);
                var state = validation.Ok
                    ? WorkflowStatus.EvaluateTranslateProgress(Path.GetDirectoryName(path)!)
                    : new TranslateProgress(false, false, 0, 0, 0, false);
                return (validation, state);
            });
        }
        catch (Exception ex)
        {
            CsvValidationOk = false;
            CsvValidationMessage = UiText.Msg("Không thể cập nhật trạng thái CSV: {0}", ex.Message);
            ReadyForPatch = false;
            return;
        }

        if (!string.Equals(path, TranslationCsvPath, StringComparison.OrdinalIgnoreCase))
            return;
        CsvValidationOk = result.Ok;
        CsvValidationMessage = result.Message;
        ReadyForPatch = result.Ok;
        if (!result.Ok)
        {
            PatchPreflightOk = false;
            PatchPreflightEvaluated = false;
            PatchEligibleCount = 0;
            PatchBlockedCount = 0;
            PatchPreflightMessage = "Cần CSV hợp lệ trước khi kiểm tra chất lượng patch.";
        }
    }

    private bool RunPatchPreflight(bool silent)
    {
        var csv = string.IsNullOrWhiteSpace(TranslationCsvPath)
            ? Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "translation.csv")
            : TranslationCsvPath;
        var manifest = Path.Combine(Path.GetDirectoryName(csv)!, "manifest.json");
        // Translation completion is advisory. The current CSV and manifest, not an
        // older MT run's pending/review counts, decide which rows can be patched.
        var result = PatchPreflightService.Run(csv, manifest);
        _patchSourceStale = false;
        PatchPreflightOk = result.Ok;
        ReadyForPatch = result.Ok;
        PatchPreflightEvaluated = true;
        PatchResultsAvailable = true;
        if (!silent)
            PatchResultsExpanded = true;
        PatchEligibleCount = result.Eligible;
        PatchBlockedCount = result.Blocked;
        PatchPreflightMessage = result.DetailMessage;
        if (!silent)
            AppendLog(result.Ok
                ? $"Kiểm tra patch: {result.Eligible} hợp lệ, {result.Blocked} bị chặn."
                : $"Kiểm tra patch: {result.Error ?? result.Summary}", result.Ok ? (result.Blocked > 0 ? "WARN" : null) : "ERROR");
        if (SelectedTab == WorkflowTabs.Patch)
            UpdateHeroForTab();
        return result.Ok;
    }

    private void OpenInput()
    {
        if (!_pathPicker.OpenPath(InputPath))
            AppendLog("Không mở được đường dẫn game — kiểm tra lại đường dẫn.");
    }

    private void OpenOutput()
    {
        if (!_pathPicker.OpenPath(OutputPath))
            AppendLog("Không mở được thư mục xuất — kiểm tra lại đường dẫn.");
    }

    private bool CanOpenInput() => !string.IsNullOrWhiteSpace(InputPath);
    private bool CanOpenOutput() => !string.IsNullOrWhiteSpace(OutputPath);

}
