using System.Diagnostics;
using System.IO;
using Microsoft.Win32;

namespace VNText.Studio.App.Services;

public sealed class WpfPathPickerService : IPathPickerService
{
    public string? PickImageFile(bool review = false)
    {
        var dialog = new OpenFileDialog { CheckFileExists = true,
            Title = UiText.Translate(review ? "Mở review text ảnh" : "Chọn ảnh có chữ"),
            Filter = review ? "Image review (*.json)|*.json" : UiText.Translate("Ảnh tĩnh") + "|*.png;*.jpg;*.jpeg;*.webp" };
        return dialog.ShowDialog() == true ? dialog.FileName : null;
    }

    public string? PickInputPath()
    {
        var folderDlg = new OpenFolderDialog
        {
            Title = UiText.Translate("Chọn thư mục game"),
            Multiselect = false,
        };
        if (folderDlg.ShowDialog() == true && !string.IsNullOrWhiteSpace(folderDlg.FolderName))
            return folderDlg.FolderName;

        var fileDlg = new OpenFileDialog
        {
            Title = UiText.Translate("Hoặc chọn file asset / bundle"),
            CheckFileExists = true,
        };
        return fileDlg.ShowDialog() == true ? fileDlg.FileName : null;
    }

    public string? PickOutputFolder()
    {
        var dlg = new OpenFolderDialog
        {
            Title = UiText.Translate("Chọn thư mục xuất gói dịch"),
            Multiselect = false,
        };
        return dlg.ShowDialog() == true ? dlg.FolderName : null;
    }

    public string? PickTranslationCsvFile(string? title = null)
    {
        var (dialogTitle, filter) = TranslationCsvDialogSpec(title);
        var dlg = new OpenFileDialog
        {
            Title = dialogTitle,
            Filter = filter,
            CheckFileExists = true,
        };
        return dlg.ShowDialog() == true ? dlg.FileName : null;
    }

    /// <summary>Title and filter of the CSV picker in the current language (catalog keys; the file pattern itself is not text).</summary>
    internal static (string Title, string Filter) TranslationCsvDialogSpec(string? title) =>
        (UiText.Translate(string.IsNullOrWhiteSpace(title) ? "Chọn tệp CSV" : title), "CSV (*.csv)|*.csv|" + UiText.Translate("Tất cả") + " (*.*)|*.*");

    /// <summary>Title and filter of the Cloud Repair package save dialog in the current language.</summary>
    internal static (string Title, string Filter) CloudRepairSaveDialogSpec() =>
        (UiText.Translate("Lưu gói Cloud Repair"), "Cloud Repair ZIP (*.zip)|*.zip|" + UiText.Translate("Tất cả") + " (*.*)|*.*");

    public string? PickRenpySdkFolder()
    {
        var dlg = new OpenFolderDialog { Title = UiText.Translate("Chọn thư mục Ren'Py 8.5.3 đã cài"), Multiselect = false };
        return dlg.ShowDialog() == true ? dlg.FolderName : null;
    }

    public bool OpenPath(string path)
    {
        var text = (path ?? "").Trim().Trim('"');
        if (string.IsNullOrEmpty(text))
            return false;

        string target;
        if (File.Exists(text))
            target = Path.GetDirectoryName(text) ?? text;
        else if (Directory.Exists(text))
            target = text;
        else
            return false;

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = target,
                UseShellExecute = true,
            });
            return true;
        }
        catch
        {
            return false;
        }
    }
}
