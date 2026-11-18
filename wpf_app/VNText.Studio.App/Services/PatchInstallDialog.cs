using System.IO;
using System.Security.Cryptography;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using VNText.PatchInstaller;

namespace VNText.Studio.App.Services;

/// <summary>Same verified payload and transaction engine as the standalone installer.</summary>
internal sealed class PatchInstallDialog : Window
{
    private readonly InstallerService _service;
    private readonly Func<bool> _revisionValid;
    private readonly TextBox _target;
    private readonly TextBlock _status;
    private readonly Button _install, _restore, _browse;
    private readonly ProgressBar _progress;
    private readonly Queue<string> _log = new();
    private bool _busy;
    private readonly string _fontState;
    private readonly string _manifestHash;

    internal PatchInstallDialog(string payloadRoot, string game, Func<bool> revisionValid)
    {
        _service = new InstallerService(payloadRoot);
        _revisionValid = revisionValid;
        var manifest = _service.LoadManifest();
        _manifestHash = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(_service.ManifestPath)));
        var font = manifest.FontPreflight;
        _fontState = font is { } f && f.TryGetProperty("glyph_status", out var glyph)
            ? $"Glyph: {glyph.GetString()}; mapping: {(f.TryGetProperty("mapping_status", out var mapping) ? mapping.GetString() : "UNKNOWN")}. " + UiText.Translate("Chưa chứng minh hiển thị font trong game.")
            : UiText.Translate("Chưa kiểm chứng font của patch này.");
        Title = UiText.Translate("Cài trong VNText");
        Width = 720; Height = 480; MinWidth = 540; MinHeight = 390;
        Owner = Application.Current.MainWindow; WindowStartupLocation = WindowStartupLocation.CenterOwner;
        SetResourceReference(BackgroundProperty, "WindowBrush");
        SetResourceReference(ForegroundProperty, "InkBrush");
        var body = new DockPanel { Margin = new Thickness(24) };
        var footer = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right, Margin = new Thickness(0,16,0,0) };
        DockPanel.SetDock(footer, Dock.Bottom); body.Children.Add(footer);
        Button Button(string text, string style) { var b = new Button { Content = UiText.Translate(text), Margin = new Thickness(6,0,0,0) }; b.SetResourceReference(StyleProperty, style); return b; }
        _restore = Button("Gỡ và hoàn nguyên", "OutlineButton");
        _install = Button("Cài patch", "PrimaryButton");
        footer.Children.Add(_restore); footer.Children.Add(_install);
        var stack = new StackPanel(); body.Children.Add(stack);
        stack.Children.Add(new TextBlock { Text = Title, FontSize = 22, FontWeight = FontWeights.SemiBold });
        stack.Children.Add(new TextBlock { Text = $"{manifest.Files.Count} " + UiText.Translate("file sẽ được cài; bản gốc được sao lưu."), Margin = new Thickness(0,12,0,8), TextWrapping = TextWrapping.Wrap });
        stack.Children.Add(new TextBlock { Text = _fontState, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0,0,0,12) });
        _target = new TextBox { Text = game, IsReadOnly = true }; _target.SetResourceReference(StyleProperty, "FieldTextBoxStyle"); stack.Children.Add(_target);
        _browse = Button("Chọn game…", "OutlineButton"); _browse.HorizontalAlignment = HorizontalAlignment.Left; _browse.Margin = new Thickness(0,8,0,12); stack.Children.Add(_browse);
        _status = new TextBlock { TextWrapping = TextWrapping.Wrap, MaxHeight = 80, TextTrimming = TextTrimming.CharacterEllipsis }; stack.Children.Add(_status);
        _progress = new ProgressBar { Height = 4, IsIndeterminate = true, Visibility = Visibility.Collapsed, Margin = new Thickness(0,8,0,8) }; stack.Children.Add(_progress);
        _browse.Click += (_, _) => { var picker = new Microsoft.Win32.OpenFolderDialog { Title = UiText.Translate("Chọn thư mục game") }; if (picker.ShowDialog(this) == true) _target.Text = picker.FolderName; Refresh(); };
        _install.Click += async (_, _) => await Run(false);
        _restore.Click += async (_, _) => await Run(true);
        Closing += (_, e) => e.Cancel = _busy;
        Content = body; Refresh();
    }

    private void Refresh()
    {
        try
        {
            if (File.Exists(_service.StatePath)) { _service.ValidateInstalledState(_target.Text); _install.IsEnabled = false; _restore.IsEnabled = true; _status.Text = UiText.Translate("Patch đã cài. Có thể gỡ và hoàn nguyên."); }
            else { _service.ValidateGame(_target.Text); _install.IsEnabled = _revisionValid(); _restore.IsEnabled = false; _status.Text = UiText.Translate("Game hợp lệ. Chỉ ghi sau khi bạn xác nhận."); }
        }
        catch (Exception ex) { _install.IsEnabled = _restore.IsEnabled = false; _status.Text = ex.Message; }
    }

    private async Task Run(bool restore)
    {
        if (_busy || !_revisionValid()) { _status.Text = UiText.Translate("CSV hoặc patch đã thay đổi. Hãy tạo lại patch."); return; }
        var question = restore ? "Gỡ patch và hoàn nguyên các file gốc đã sao lưu?" : "Cài patch vào thư mục game này? Bản gốc sẽ được sao lưu.";
        if (AppDialogService.Show(UiText.Translate(question) + "\n\n" + _target.Text + "\n\n" + _fontState, Title, MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes) return;
        _busy = true; _install.IsEnabled = _restore.IsEnabled = _browse.IsEnabled = false;
        _progress.Visibility = Visibility.Visible;
        var game = _target.Text; _status.Text = UiText.Translate("Đang xử lý…");
        void Progress(string line) => Dispatcher.InvokeAsync(() => { if (!_busy) return; _log.Enqueue(line); while (_log.Count > 4) _log.Dequeue(); _status.Text = string.Join("\n", _log); });
        try
        {
            using var manifestLease = new FileStream(_service.ManifestPath, FileMode.Open, FileAccess.Read, FileShare.Read);
            if (!_revisionValid() || Convert.ToHexString(SHA256.HashData(manifestLease)) != _manifestHash)
                throw new InvalidDataException(UiText.Translate("CSV hoặc patch đã thay đổi. Hãy tạo lại patch."));
            await Task.Run(() => { if (restore) _service.Uninstall(game, Progress); else _service.Install(game, Progress); });
            _status.Text = UiText.Translate(restore ? "Đã hoàn nguyên." : "Đã cài patch và kiểm tra file.");
        }
        catch (Exception ex) { _status.Text = ex.Message; }
        finally { _busy = false; _progress.Visibility = Visibility.Collapsed; _browse.IsEnabled = true; Refresh(); }
    }
}
