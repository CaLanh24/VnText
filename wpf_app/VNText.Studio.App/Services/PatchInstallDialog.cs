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
    private enum Operation { Install, Restore, CleanOriginal }

    private const int FontLineCap = 9;
    private readonly AppDialogWindow _window;
    private readonly InstallerService _service;
    private readonly Func<bool> _revisionValid;
    private readonly TextBox _target;
    private readonly TextBlock _status;
    private readonly Button _install, _restore, _clean, _browse;
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
        _fontState = UiText.Translate(font is { } f && f.TryGetProperty("glyph_status", out var glyph) && glyph.GetString() is "PASS" or "PASS_WITH_FALLBACK"
            ? "Font đủ ký tự bản dịch. Chỉ áp dụng cho các kiểu chữ tĩnh đã nhận diện; chưa chứng minh hiển thị trong game."
            : "Chưa xác minh được font của game. Cài patch chưa bảo đảm chữ Việt hiển thị đúng.");
        var stack = new StackPanel();
        stack.Children.Add(new TextBlock { Text = UiText.TranslateDynamic(UiText.Msg("Số file sẽ cài: {0}. Bản gốc được sao lưu.", manifest.Files.Count)), Margin = new Thickness(0,12,0,8), TextWrapping = TextWrapping.Wrap });
        stack.Children.Add(new TextBlock { Text = _fontState, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0,0,0,12) });
        var fontLines = AssetInventoryPresentation.FromPatch(manifest.FontPreflight);
        if (fontLines.Count > 0)
        {
            var shown = fontLines.Count <= FontLineCap ? fontLines : fontLines.Take(FontLineCap - 1).Append(UiText.Format("… và {0} dòng nữa; xem font_preflight.json trong thư mục patch.", fontLines.Count - (FontLineCap - 1))).ToList();
            var fonts = new TextBlock { Text = string.Join("\n", shown), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0,0,0,12), FontSize = 12 };
            fonts.SetResourceReference(TextBlock.ForegroundProperty, "MutedBrush");
            System.Windows.Automation.AutomationProperties.SetName(fonts, UiText.Translate("Trạng thái font trong game"));
            stack.Children.Add(fonts);
        }
        _target = new TextBox { Text = game, IsReadOnly = true }; _target.SetResourceReference(FrameworkElement.StyleProperty, "FieldTextBoxStyle"); stack.Children.Add(_target);
        System.Windows.Automation.AutomationProperties.SetName(_target, UiText.Translate("Thư mục game"));
        _browse = new Button { Content = UiText.Translate("Chọn game…"), HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(0,8,0,12) };
        _browse.SetResourceReference(FrameworkElement.StyleProperty, "OutlineButton"); stack.Children.Add(_browse);
        _status = new TextBlock { TextWrapping = TextWrapping.Wrap, MaxHeight = 120, TextTrimming = TextTrimming.CharacterEllipsis }; stack.Children.Add(_status);
        _progress = new ProgressBar { Height = 4, IsIndeterminate = true, Visibility = Visibility.Collapsed, Margin = new Thickness(0,8,0,8) }; stack.Children.Add(_progress);
        _window = new AppDialogWindow(Application.Current.MainWindow, "Cài trong VNText", stack, width: 720);
        _clean = _window.AddButton("Về bản gốc sạch", () => _ = Run(Operation.CleanOriginal), closeOnClick: false);
        _restore = _window.AddButton("Gỡ và hoàn nguyên", () => _ = Run(Operation.Restore), closeOnClick: false);
        _install = _window.AddButton("Cài patch", () => _ = Run(Operation.Install), primary: true, closeOnClick: false);
        _browse.Click += (_, _) => { var picker = new Microsoft.Win32.OpenFolderDialog { Title = UiText.Translate("Chọn thư mục game") }; if (picker.ShowDialog(_window) == true) _target.Text = picker.FolderName; Refresh(); };
        _window.Closing += (_, e) => e.Cancel = _busy;
        Refresh();
    }

    internal bool? ShowDialog() => _window.ShowDialog();

    private void Refresh()
    {
        try
        {
            if (File.Exists(_service.StatePath)) { _service.ValidateInstalledState(_target.Text); _install.IsEnabled = false; _restore.IsEnabled = _clean.IsEnabled = true; _status.Text = UiText.Translate("Patch đã cài. Có thể gỡ (về trạng thái trước lần cài này) hoặc về bản gốc sạch."); }
            else
            {
                _service.ValidateGame(_target.Text); _install.IsEnabled = _revisionValid(); _restore.IsEnabled = false;
                // Another VNText patch (e.g. the previous one after stepping back from an upgrade) is still on the game: the receipt alone can bring back the clean original.
                _clean.IsEnabled = _revisionValid() && _service.HasReceiptLayers(_target.Text);
                var owned = _service.DescribeOwnership(_target.Text);
                _status.Text = UiText.Translate("Game hợp lệ. Chỉ ghi sau khi bạn xác nhận.") + (owned.Count == 0 ? "" : "\n" + string.Join("\n", owned));
            }
        }
        catch (Exception ex) { _install.IsEnabled = _restore.IsEnabled = _clean.IsEnabled = false; _status.Text = ex.Message; }
    }

    private async Task Run(Operation operation)
    {
        if (_busy || !_revisionValid()) { _status.Text = UiText.Translate("CSV hoặc patch đã thay đổi. Hãy tạo lại patch."); return; }
        var question = operation switch
        {
            Operation.Restore => "Gỡ patch và hoàn nguyên các file mà lần cài này đã thay?",
            Operation.CleanOriginal => "Đưa game về bản gốc đầu tiên được ghi nhận trước mọi patch VNText (gỡ cả các lớp patch cũ hơn)? File có sẵn không do VNText quản lý được trả lại nguyên trạng, không bị xóa.",
            _ => "Cài patch vào thư mục game này? Bản gốc sẽ được sao lưu.",
        };
        var ownership = "";
        try { if (operation == Operation.Install) ownership = string.Join("\n", _service.DescribeOwnership(_target.Text)); } catch (Exception) { /* the install itself re-validates and reports */ }
        if (AppDialogService.Show(UiText.Translate(question) + "\n\n" + _target.Text + "\n\n" + _fontState + (ownership.Length == 0 ? "" : "\n\n" + ownership), UiText.Translate("Cài trong VNText"), MessageBoxButton.YesNo, MessageBoxImage.Warning, _window) != MessageBoxResult.Yes) return;
        _busy = true; _install.IsEnabled = _restore.IsEnabled = _clean.IsEnabled = _browse.IsEnabled = false;
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
            await Task.Run(() =>
            {
                if (operation == Operation.Install) notes = _service.Install(game, Progress).Notes ?? new List<string>();
                else notes = _service.Uninstall(game, Progress, operation == Operation.CleanOriginal ? UninstallMode.CleanOriginal : UninstallMode.Previous).Notes;
            });
            _status.Text = UiText.Translate(operation switch { Operation.Restore => "Đã hoàn nguyên.", Operation.CleanOriginal => "Đã về bản gốc đầu tiên trước mọi patch VNText.", _ => "Đã cài patch và kiểm tra file." })
                + (notes.Count == 0 ? "" : "\n" + string.Join("\n", notes));
        }
        catch (Exception ex) { _status.Text = ex.Message; }
        finally { var terminal = _status.Text; _busy = false; _window.CloseButton.IsEnabled = true; _progress.Visibility = Visibility.Collapsed; _browse.IsEnabled = true; Refresh(); _status.Text = terminal; }
    }
}
