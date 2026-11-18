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

    private void InitPatchInstallCommands()
    {
        InstallDeliveredPatchCommand = new RelayCommand(_ => OpenPatchInstaller(), _ => !Busy && PatchDeliveryReady && !_patchArtifactBehindCsv && File.Exists(_deliveredPatch));
        OpenDeliveredPatchCommand = new RelayCommand(_ => { if (File.Exists(_deliveredPatch)) Process.Start(new ProcessStartInfo("explorer.exe", Path.GetDirectoryName(_deliveredPatch)!) { UseShellExecute = true }); }, _ => !Busy && File.Exists(_deliveredPatch));
        ChoosePatchFontCommand = new RelayCommand(_ =>
        {
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
    }

    private bool PreviewPatchFont(string path, string family)
    {
        var window = new Window { Owner = Application.Current.MainWindow, Title = UiText.Translate("Xem trước font Việt"), Width = 640, Height = 360, WindowStartupLocation = WindowStartupLocation.CenterOwner };
        window.SetResourceReference(Window.BackgroundProperty, "WindowBrush");
        window.SetResourceReference(Window.ForegroundProperty, "InkBrush");
        var body = new System.Windows.Controls.DockPanel { Margin = new Thickness(24) };
        var accept = new System.Windows.Controls.Button { Content = UiText.Translate("Dùng font này"), HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0,12,0,0) };
        accept.SetResourceReference(System.Windows.Controls.Button.StyleProperty, "PrimaryButton");
        accept.Click += (_, _) => window.DialogResult = true;
        System.Windows.Controls.DockPanel.SetDock(accept, System.Windows.Controls.Dock.Bottom); body.Children.Add(accept);
        var preview = new System.Windows.Controls.TextBlock { Text = "Đặng, Nguyễn — Ă Â Ê Ô Ơ Ư Đ · ă â ê ô ơ ư đ\nTiếng Việt có dấu: Xin chào!\n\n" + UiText.Translate("Đây là bản xem trước trên máy; mapping font trong game được kiểm riêng."), TextWrapping = TextWrapping.Wrap, FontSize = 21,
            FontFamily = new System.Windows.Media.FontFamily(new Uri(Path.GetDirectoryName(path)! + Path.DirectorySeparatorChar), "./" + Path.GetFileName(path) + "#" + family) };
        body.Children.Add(new System.Windows.Controls.ScrollViewer { Content = preview, VerticalScrollBarVisibility = System.Windows.Controls.ScrollBarVisibility.Auto });
        window.Content = body; return window.ShowDialog() == true;
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

    private bool DeliveredRevisionValid() => !CsvEditorDirty && !CsvEditorSaving && !_patchArtifactBehindCsv
        && string.Equals(InputPath, _deliveredGame, StringComparison.OrdinalIgnoreCase)
        && string.Equals(ResolveActiveCsvPath(), _deliveredCsv, StringComparison.OrdinalIgnoreCase)
        && File.Exists(_deliveredCsv) && HashFile(_deliveredCsv) == _deliveredCsvHash
        && File.Exists(_deliveredPatch) && HashFile(_deliveredPatch) == _deliveredPatchHash;

    private void OpenPatchInstaller()
    {
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
