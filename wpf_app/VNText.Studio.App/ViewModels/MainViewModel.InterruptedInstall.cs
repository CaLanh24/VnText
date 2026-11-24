using System.IO;
using System.Windows;
using VNText.PatchInstaller;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    internal Func<string, string, MessageBoxButton, MessageBoxImage, MessageBoxResult> InterruptedInstallMessageBox { get; set; } =
        static (message, caption, buttons, image) => AppDialogService.Show(message, caption, buttons, image);

    /// <summary>
    /// Before reading or patching a game: if an install into it was cut off (power loss, app closed), its half-written files must not be read as the game's
    /// own.  Ask, then let the installer recover it (journal-proven, known states only).  Returns false when the person declines or recovery is refused.
    /// </summary>
    private bool EnsureNoInterruptedInstall(string input)
    {
        string game;
        try
        {
            if (string.IsNullOrWhiteSpace(input)) return true;
            game = Directory.Exists(input) ? input : Path.GetDirectoryName(input) ?? "";
            if (string.IsNullOrEmpty(game) || !InstallerService.HasPendingInstall(game)) return true;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or ArgumentException or NotSupportedException) { return true; }
        const string caption = "Phục hồi lần cài bị ngắt";
        if (InterruptedInstallMessageBox(UiText.Translate("Lần cài patch VNText trước vào game này bị ngắt giữa chừng (tắt máy hoặc ứng dụng bị đóng). Trước khi lấy text hay tạo patch, VNText cần đưa game về đúng trạng thái trước lần cài đó (kiểm hash từng tệp). Phục hồi ngay?"),
                UiText.Translate(caption), MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
        {
            StatusText = UiText.Translate("Chưa phục hồi lần cài bị ngắt");
            return false;
        }
        try
        {
            var note = InstallerService.RecoverPendingInstall(game) ?? UiText.Translate("Không còn gì cần phục hồi.");
            AppendLog(note);
            InterruptedInstallMessageBox(note, UiText.Translate(caption), MessageBoxButton.OK, MessageBoxImage.Information);
            return true;
        }
        catch (Exception ex) when (ex is InvalidOperationException or IOException or UnauthorizedAccessException)
        {
            AppendLog(ex.Message);
            InterruptedInstallMessageBox(ex.Message, UiText.Translate(caption), MessageBoxButton.OK, MessageBoxImage.Error);
            StatusText = UiText.Translate("Chưa phục hồi lần cài bị ngắt");
            return false;
        }
    }
}
