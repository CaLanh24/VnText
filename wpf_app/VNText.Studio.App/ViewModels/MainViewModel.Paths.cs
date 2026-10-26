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
    internal const string ImportTranslatedCsvPickerTitle = "Chọn translation.csv đã dịch để nhập";

    private async void ChooseTranslationCsv()
    {
        if (CsvEditorSaving && !await WaitForCsvEditorSaveAsync()) return;
        if (CsvEditorDirty && !await SaveCsvEditorAsync()) return;
        var path = _pathPicker.PickTranslationCsvFile(TranslateCsvPickerTitle);
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
            AppendLog($"CSV: {candidate.Message}");
            ShowToast(candidate.Message, "warning");
            return;
        }

        var previousPath = TranslationCsvPath;
        var previousMessage = CsvValidationMessage;
        var previousOk = CsvValidationOk;
        var previousReady = ReadyForPatch;
        var previousPreflightOk = PatchPreflightOk;
        var previousEligible = PatchEligibleCount;
        var previousBlocked = PatchBlockedCount;
        var previousPreflightMessage = PatchPreflightMessage;

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
            return;
        }

        RefreshWorkflow();
    }

    private string? PickCloudRepairPackagePath()
    {
        var dialog = new SaveFileDialog
        {
            Title = "Lưu gói Cloud Repair",
            Filter = "Cloud Repair ZIP (*.zip)|*.zip|Tất cả (*.*)|*.*",
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
        CsvValidationOk = result.Ok;
        CsvValidationMessage = result.Message;
        ReadyForPatch = result.Ok && WorkflowStatus.EvaluateTranslateProgress(Path.GetDirectoryName(path)!).IsComplete;
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
            AppendLog(result.Ok ? $"CSV OK: {result.Message}" : $"CSV: {result.Message}");
            if (result.Ok)
                AppendLog(PatchPreflightMessage.Replace("\r\n", " | ").Replace("\n", " | "));
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
            CsvValidationMessage = $"Không thể cập nhật trạng thái CSV: {ex.Message}";
            ReadyForPatch = false;
            return;
        }

        if (!string.Equals(path, TranslationCsvPath, StringComparison.OrdinalIgnoreCase))
            return;
        CsvValidationOk = result.Ok;
        CsvValidationMessage = result.Message;
        ReadyForPatch = result.Ok && progress.IsComplete;
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
        var progress = WorkflowStatus.EvaluateTranslateProgress(Path.GetDirectoryName(csv)!);
        var result = !progress.IsComplete
            ? PatchPreflightResult.Fail(csv, $"Dịch chưa hoàn tất — pending {progress.Pending}, review {progress.ReviewOnly}, blocked {progress.Blocked}. Chưa thể tạo Patch.")
            : PatchPreflightService.Run(csv, manifest);
        PatchPreflightOk = result.Ok;
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
                : $"Kiểm tra patch: {result.Error ?? result.Summary}");
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
