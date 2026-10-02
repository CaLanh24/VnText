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
    private void ChooseInput()
    {
        var path = _pathPicker.PickInputPath();
        if (!string.IsNullOrWhiteSpace(path))
            InputPath = path;
    }

    private void ChooseOutput()
    {
        var path = _pathPicker.PickOutputFolder();
        if (!string.IsNullOrWhiteSpace(path))
            OutputPath = path;
    }

    private void ChooseTranslationCsv()
    {
        var path = _pathPicker.PickTranslationCsvFile();
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
        var candidate = CsvPackageValidator.Validate(path);
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
        if (!ValidateTranslationCsv(silent: false))
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
        var path = _pathPicker.PickRenpySdkFolder();
        if (!string.IsNullOrWhiteSpace(path))
        {
            RenpySdkPath = path;
            RenpySdkAction = "existing";
            AppendLog("Đã chọn Ren'Py SDK; sẽ kiểm tra khi extract.");
        }
    }

    private bool ValidateTranslationCsv(bool silent)
    {
        var path = string.IsNullOrWhiteSpace(TranslationCsvPath)
            ? Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "translation.csv")
            : TranslationCsvPath;
        var result = CsvPackageValidator.Validate(path);
        CsvValidationOk = result.Ok;
        CsvValidationMessage = result.Message;
        ReadyForPatch = result.Ok || WorkflowStatus.Evaluate(InputPath, OutputPath).ReadyForPatch;
        if (result.Ok)
        {
            // Heavy Python gate only when user explicitly validates or starts patch (silent=false).
            if (!silent)
                RunPatchPreflight(silent: false);
        }
        else
        {
            PatchPreflightOk = false;
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

    private bool RunPatchPreflight(bool silent)
    {
        var csv = string.IsNullOrWhiteSpace(TranslationCsvPath)
            ? Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "translation.csv")
            : TranslationCsvPath;
        var manifest = Path.Combine(Path.GetDirectoryName(csv)!, "manifest.json");
        var result = PatchPreflightService.Run(csv, manifest);
        PatchPreflightOk = result.Ok;
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
