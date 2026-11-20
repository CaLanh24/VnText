using System.IO;
using System.Security.Cryptography;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using VNText.PatchInstaller;

namespace VNText.Studio.App.Services;

/// <summary>Same verified payload and transaction engine as the standalone installer.</summary>
internal sealed class PatchInstallDialog
{
    private readonly AppDialogWindow _window;
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
        _fontState = UiText.Translate(font is { } f && f.TryGetProperty("glyph_status", out var glyph) && glyph.GetString() == "PASS"
            ? "Font đủ ký tự bản dịch. Chỉ áp dụng cho các kiểu chữ tĩnh đã nhận diện; chưa chứng minh hiển thị trong game."
            : "Chưa xác minh được font của game. Cài patch chưa bảo đảm chữ Việt hiển thị đúng.");
        var stack = new StackPanel();
        stack.Children.Add(new TextBlock { Text = UiText.TranslateDynamic(UiText.Msg("Số file sẽ cài: {0}. Bản gốc được sao lưu.", manifest.Files.Count)), Margin = new Thickness(0,12,0,8), TextWrapping = TextWrapping.Wrap });
        stack.Children.Add(new TextBlock { Text = _fontState, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0,0,0,12) });
        _target = new TextBox { Text = game, IsReadOnly = true }; _target.SetResourceReference(FrameworkElement.StyleProperty, "FieldTextBoxStyle"); stack.Children.Add(_target);
        System.Windows.Automation.AutomationProperties.SetName(_target, UiText.Translate("Thư mục game"));
        _browse = new Button { Content = UiText.Translate("Chọn game…"), HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(0,8,0,12) };
        _browse.SetResourceReference(FrameworkElement.StyleProperty, "OutlineButton"); stack.Children.Add(_browse);
        _status = new TextBlock { TextWrapping = TextWrapping.Wrap, MaxHeight = 80, TextTrimming = TextTrimming.CharacterEllipsis }; stack.Children.Add(_status);
        _progress = new ProgressBar { Height = 4, IsIndeterminate = true, Visibility = Visibility.Collapsed, Margin = new Thickness(0,8,0,8) }; stack.Children.Add(_progress);
        _window = new AppDialogWindow(Application.Current.MainWindow, "Cài trong VNText", stack, width: 720);
        _restore = _window.AddButton("Gỡ và hoàn nguyên", () => _ = Run(true), closeOnClick: false);
        _install = _window.AddButton("Cài patch", () => _ = Run(false), primary: true, closeOnClick: false);
        _browse.Click += (_, _) => { var picker = new Microsoft.Win32.OpenFolderDialog { Title = UiText.Translate("Chọn thư mục game") }; if (picker.ShowDialog(_window) == true) _target.Text = picker.FolderName; Refresh(); };
        _window.Closing += (_, e) => e.Cancel = _busy;
        Refresh();
    }

    internal bool? ShowDialog() => _window.ShowDialog();

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
        var ownership = "";
        try { if (!restore) ownership = string.Join("\n", _service.DescribeOwnership(_target.Text)); } catch (Exception) { /* the install itself re-validates and reports */ }
        if (AppDialogService.Show(UiText.Translate(question) + "\n\n" + _target.Text + "\n\n" + _fontState + (ownership.Length == 0 ? "" : "\n\n" + ownership),UiText.Translate("Cài trong VNText"), MessageBoxButton.YesNo, MessageBoxImage.Warning, _window) != MessageBoxResult.Yes) return;
        _busy = true; _install.IsEnabled = _restore.IsEnabled = _browse.IsEnabled = false;
        _progress.Visibility = Visibility.Visible;
        _window.CloseButton.IsEnabled = false;
        var game = _target.Text; _status.Text = UiText.Translate("Đang xử lý…");
        void Progress(string line) => _window.Dispatcher.InvokeAsync(() => { if (!_busy) return; _log.Enqueue(line); while (_log.Count > 4) _log.Dequeue(); _status.Text = string.Join("\n", _log); });
        try
        {
            using var manifestLease = new FileStream(_service.ManifestPath, FileMode.Open, FileAccess.Read, FileShare.Read);
            if (!_revisionValid() || Convert.ToHexString(SHA256.HashData(manifestLease)) != _manifestHash)
                throw new InvalidDataException(UiText.Translate("CSV hoặc patch đã thay đổi. Hãy tạo lại patch."));
            List<string> notes = new();
            await Task.Run(() => { if (restore) notes = _service.Uninstall(game, Progress).Notes; else notes = _service.Install(game, Progress).Notes ?? new List<string>(); });
            _status.Text = UiText.Translate(restore ? "Đã hoàn nguyên." : "Đã cài patch và kiểm tra file.") + (notes.Count == 0 ? "" : "\n" + string.Join("\n", notes));
        }
        catch (Exception ex) { _status.Text = ex.Message; }
        finally { var terminal = _status.Text; _busy = false; _window.CloseButton.IsEnabled = true; _progress.Visibility = Visibility.Collapsed; _browse.IsEnabled = true; Refresh(); _status.Text = terminal; }
    }
}
