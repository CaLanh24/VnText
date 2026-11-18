using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Windows;
using Microsoft.Win32;
using VNText.Studio.App.Services;
using VNText.PatchInstaller;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    private string _deliveredPatch = "", _deliveredPatchHash = "", _deliveredCsv = "", _deliveredCsvHash = "", _deliveredGame = "";
    private string _replacementFont = "";
    public string ReplacementFontLabel => string.IsNullOrEmpty(_replacementFont) ? UiText.Translate("Font: tự kiểm tra font có sẵn") : Path.GetFileName(_replacementFont);
    public RelayCommand InstallDeliveredPatchCommand { get; private set; } = null!;
    public RelayCommand OpenDeliveredPatchCommand { get; private set; } = null!;
    public RelayCommand ChoosePatchFontCommand { get; private set; } = null!;
    public RelayCommand ResetPatchFontCommand { get; private set; } = null!;

    private void InitPatchInstallCommands()
    {
        InstallDeliveredPatchCommand = new RelayCommand(_ => OpenPatchInstaller(), _ => !Busy && PatchDeliveryReady && !_patchArtifactBehindCsv && File.Exists(_deliveredPatch));
        OpenDeliveredPatchCommand = new RelayCommand(_ => { if (File.Exists(_deliveredPatch)) Process.Start(new ProcessStartInfo(Path.GetDirectoryName(_deliveredPatch)!) { UseShellExecute = true }); }, _ => !Busy && File.Exists(_deliveredPatch));
        ResetPatchFontCommand = new RelayCommand(_ => { if (Busy) return; _replacementFont = ""; Raise(nameof(ReplacementFontLabel)); InvalidatePatchSourceState(); }, _ => !Busy);
        ChoosePatchFontCommand = new RelayCommand(_ =>
        {
            if (Busy) return;
            var picker = new OpenFileDialog { Filter = "Font (*.ttf;*.otf)|*.ttf;*.otf", Title = UiText.Translate("Chọn font Việt thay thế (Ren’Py)") };
            if (picker.ShowDialog() != true) return;
            try
            {
                // Desktop preview is separate from the worker's bounded glyph/mapping preflight.
                var face = new System.Windows.Media.GlyphTypeface(new Uri(picker.FileName));
                if (face.CharacterToGlyphMap.Count == 0) throw new InvalidDataException("Font has no glyph mapping.");
                if (!PreviewPatchFont(picker.FileName, face.FamilyNames.Values.First())) return;
                _replacementFont = picker.FileName; Raise(nameof(ReplacementFontLabel));
                InvalidatePatchSourceState();
            }
            catch (Exception ex) { ShowToast(ex.Message, "error"); }
        }, _ => !Busy);
        PropertyChanged += (_, e) =>
        {
            if (e.PropertyName is nameof(Busy) or nameof(PatchDeliveryReady) or nameof(CsvEditorDirty) or nameof(CsvEditorSaving))
            {
                InstallDeliveredPatchCommand.RaiseCanExecuteChanged(); OpenDeliveredPatchCommand.RaiseCanExecuteChanged();
                ChoosePatchFontCommand.RaiseCanExecuteChanged(); ResetPatchFontCommand.RaiseCanExecuteChanged();
            }
        };
    }

    private bool PreviewPatchFont(string path, string family)
    {
        var sample = string.Join("\n", _csvEditorRows.Where(row => !row.IsEmpty).Take(3).Select(row => row.Translation));
        if (sample.Length > 2000) sample = sample[..2000];
        var preview = new System.Windows.Controls.TextBlock
        {
            Text = "Đặng, Nguyễn — Ă Â Ê Ô Ơ Ư Đ · ă â ê ô ơ ư đ\nTiếng Việt có dấu: Xin chào!\n\n" + sample + "\n\n" + UiText.Translate("Đây là bản xem trước trên máy; mapping font trong game được kiểm riêng."),
            TextWrapping = TextWrapping.Wrap, FontSize = 21,
            FontFamily = new System.Windows.Media.FontFamily(new Uri(Path.GetDirectoryName(path)! + Path.DirectorySeparatorChar), "./" + Path.GetFileName(path) + "#" + family)
        };
        var accepted = false;
        var body = new System.Windows.Controls.StackPanel(); body.Children.Add(preview);
        var permission = new System.Windows.Controls.CheckBox { Content = UiText.Translate("Tôi có quyền đóng gói và phân phối font này."), Margin = new Thickness(0,16,0,0) };
        body.Children.Add(permission);
        var window = new AppDialogWindow(Application.Current.MainWindow, "Xem trước font Việt", body, width: 640);
        var use = window.AddButton("Dùng font này", () => accepted = true, primary: true, isDefault: true);
        use.IsEnabled = false;
        permission.Checked += (_, _) => use.IsEnabled = true;
        permission.Unchecked += (_, _) => use.IsEnabled = false;
        window.ShowDialog(); return accepted;
    }

    private static string HashFile(string path) { using var stream = File.OpenRead(path); return Convert.ToHexString(SHA256.HashData(stream)); }

    private void BindDeliveredPatch(string path)
    {
        _deliveredPatch = path;
        _deliveredPatchHash = File.Exists(path) ? HashFile(path) : "";
        _deliveredCsv = ResolveActiveCsvPath();
        _deliveredCsvHash = File.Exists(_deliveredCsv) ? HashFile(_deliveredCsv) : "";
        _deliveredGame = InputPath;
        InstallDeliveredPatchCommand.RaiseCanExecuteChanged(); OpenDeliveredPatchCommand.RaiseCanExecuteChanged();
    }

    private bool DeliveredRevisionValid()
    {
        try
        {
            return PatchDeliveryReady && !CsvEditorDirty && !CsvEditorSaving && !_patchArtifactBehindCsv
                && string.Equals(InputPath, _deliveredGame, StringComparison.OrdinalIgnoreCase)
                && string.Equals(ResolveActiveCsvPath(), _deliveredCsv, StringComparison.OrdinalIgnoreCase)
                && File.Exists(_deliveredCsv) && HashFile(_deliveredCsv) == _deliveredCsvHash
                && File.Exists(_deliveredPatch) && HashFile(_deliveredPatch) == _deliveredPatchHash;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { return false; }
    }

    private void OpenPatchInstaller()
    {
        if (Busy) return;
        try
        {
            if (!DeliveredRevisionValid()) throw new InvalidDataException(UiText.Translate("CSV hoặc patch đã thay đổi. Hãy tạo lại patch."));
            // Hold the verified EXE against replacement while its extracted transaction is open.
            using var lease = new FileStream(_deliveredPatch, FileMode.Open, FileAccess.Read, FileShare.Read);
            var root = EmbeddedPatch.Open(_deliveredPatch, WorkerPaths.AppDataRoot());
            if (root == AppContext.BaseDirectory) throw new InvalidDataException("Patch has no verified embedded payload.");
            new PatchInstallDialog(root, _deliveredGame, DeliveredRevisionValid).ShowDialog();
        }
        catch (Exception ex) { ShowToast(ex.Message, "error"); }
        finally { EmbeddedPatch.Release(); }
    }
}
