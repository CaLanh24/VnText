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
    private string _imageOverlaySpec = "";
    // Optional: a user-authored rendered-image spec (known imagemap/imagebutton assets, declared regions). The product validates it when the patch is built; nothing is recognised automatically.
    public bool ImageSpecIsSet => !string.IsNullOrEmpty(_imageOverlaySpec);
    public string ImageSpecLabel => ImageSpecIsSet ? UiText.Msg("Ảnh đã chọn: {0}", Path.GetFileName(_imageOverlaySpec)) : "Không dùng ảnh (tùy chọn)";
    public string ImageSpecHelpText => "Bỏ qua nếu game không có ảnh chứa chữ. Nếu có, chọn tệp mô tả ảnh đã chỉnh sửa sẵn; ứng dụng kiểm tệp này khi tạo patch và không tự sửa chữ trong ảnh.";
    private void RaiseImageSpec() { Raise(nameof(ImageSpecIsSet)); Raise(nameof(ImageSpecLabel)); }
    public RelayCommand ChooseImageSpecCommand { get; private set; } = null!;
    public RelayCommand ResetImageSpecCommand { get; private set; } = null!;
    public string ReplacementFontLabel => string.IsNullOrEmpty(_replacementFont) ? UiText.Translate("Font Việt tự động cho Ren’Py") : Path.GetFileName(_replacementFont);
    // f-design: the font choice is shown where it is made - the mode/name, what still has to be true before it can be checked, and the confirmation of the last action.
    private string _patchFontNotice = "";
    public bool PatchFontIsCustom => !string.IsNullOrEmpty(_replacementFont);
    public string PatchFontModeText => PatchFontIsCustom ? UiText.Msg("Font tùy chọn: {0}", Path.GetFileName(_replacementFont)) : "Font Việt đi kèm (mặc định)";
    public string PatchFontStateText =>
        !HasPatchSource ? "Chưa kiểm — chọn game/asset ở bước Lấy text; glyph và mapping font được kiểm khi đóng gói."
        : !CsvValidationOk ? "Chưa kiểm — chọn CSV hợp lệ; glyph và mapping font được kiểm khi đóng gói."
        : PatchDeliveryReady && !_patchArtifactBehindCsv ? "Patch gần nhất được đóng gói với lựa chọn này; mapping trong game được kiểm riêng khi cài."
        : "Sẽ kiểm glyph và mapping font khi đóng gói patch.";
    public string PatchFontNotice => _patchFontNotice;
    public bool PatchFontNoticeVisible => _patchFontNotice.Length > 0;
    private void SetPatchFontNotice(string text) { _patchFontNotice = text; RaisePatchFont(); }
    private void RaisePatchFont()
    {
        Raise(nameof(ReplacementFontLabel)); Raise(nameof(PatchFontIsCustom)); Raise(nameof(PatchFontModeText)); Raise(nameof(PatchFontStateText));
        Raise(nameof(PatchFontNotice)); Raise(nameof(PatchFontNoticeVisible));
    }
    public RelayCommand InstallDeliveredPatchCommand { get; private set; } = null!;
    public RelayCommand OpenDeliveredPatchCommand { get; private set; } = null!;
    public RelayCommand ChoosePatchFontCommand { get; private set; } = null!;
    public RelayCommand ResetPatchFontCommand { get; private set; } = null!;
    public RelayCommand ChooseInstalledPatchFontCommand { get; private set; } = null!;

    private void InitPatchInstallCommands()
    {
        InstallDeliveredPatchCommand = new RelayCommand(_ => OpenPatchInstaller(), _ => !Busy && PatchDeliveryReady && !_patchArtifactBehindCsv && File.Exists(_deliveredPatch));
        OpenDeliveredPatchCommand = new RelayCommand(_ => { if (File.Exists(_deliveredPatch)) Process.Start(new ProcessStartInfo(Path.GetDirectoryName(_deliveredPatch)!) { UseShellExecute = true }); }, _ => !Busy && File.Exists(_deliveredPatch));
        ChooseImageSpecCommand = new RelayCommand(_ =>
        {
            if (Busy) return;
            var picker = new OpenFileDialog { Filter = "Tệp mô tả ảnh (*.json)|*.json", Title = UiText.Translate("Chọn tệp mô tả ảnh đã chỉnh sửa") };
            var opener = System.Windows.Input.Keyboard.FocusedElement;
            if (picker.ShowDialog() != true) { RestoreFocus(opener); return; }
            _imageOverlaySpec = picker.FileName; RaiseImageSpec(); InvalidatePatchSourceState(); RestoreFocus(opener);
        }, _ => !Busy);
        ResetImageSpecCommand = new RelayCommand(_ => { if (Busy) return; _imageOverlaySpec = ""; RaiseImageSpec(); InvalidatePatchSourceState(); }, _ => !Busy && ImageSpecIsSet);
        ResetPatchFontCommand = new RelayCommand(_ => { if (Busy) return; _replacementFont = ""; SetPatchFontNotice("Đã chọn: Font Việt đi kèm."); InvalidatePatchSourceState(); }, _ => !Busy);
        ChoosePatchFontCommand = new RelayCommand(_ =>
        {
            if (Busy) return;
            var picker = new OpenFileDialog { Filter = "Font (*.ttf;*.otf)|*.ttf;*.otf", Title = UiText.Translate("Chọn font Việt thay thế (Ren’Py)") };
            var opener = System.Windows.Input.Keyboard.FocusedElement;
            if (picker.ShowDialog() != true) { SetPatchFontNotice("Đã hủy chọn font; lựa chọn hiện tại được giữ nguyên."); RestoreFocus(opener); return; }
            ApplyPatchFontFile(picker.FileName);
            RestoreFocus(opener);
        }, _ => !Busy);
        ChooseInstalledPatchFontCommand = new RelayCommand(_ =>
        {
            if (Busy) return;
            var opener = System.Windows.Input.Keyboard.FocusedElement;
            var chosen = PickInstalledFont();
            if (chosen is null) { SetPatchFontNotice("Đã hủy chọn font; lựa chọn hiện tại được giữ nguyên."); RestoreFocus(opener); return; }
            ApplyPatchFontFile(chosen);
            RestoreFocus(opener);
        }, _ => !Busy);
        PropertyChanged += (_, e) =>
        {
            if (e.PropertyName is nameof(Busy) or nameof(PatchDeliveryReady) or nameof(CsvEditorDirty) or nameof(CsvEditorSaving))
            {
                InstallDeliveredPatchCommand.RaiseCanExecuteChanged(); OpenDeliveredPatchCommand.RaiseCanExecuteChanged();
                ChoosePatchFontCommand.RaiseCanExecuteChanged(); ResetPatchFontCommand.RaiseCanExecuteChanged(); ChooseInstalledPatchFontCommand.RaiseCanExecuteChanged();
                ChooseImageSpecCommand.RaiseCanExecuteChanged(); ResetImageSpecCommand.RaiseCanExecuteChanged();
            }
        };
    }

    /// <summary>After the modal(s) are gone the focus goes back to the control that opened the flow (never into the page behind it).</summary>
    private static void RestoreFocus(System.Windows.IInputElement? opener)
    {
        if (opener is not System.Windows.UIElement element) return;
        element.Dispatcher.BeginInvoke(new Action(() => { if (element.IsEnabled && element.IsVisible) { element.Focus(); System.Windows.Input.Keyboard.Focus(element); } }), System.Windows.Threading.DispatcherPriority.ApplicationIdle);
    }

    /// <summary>The one path every custom font takes (file dialog or the installed-font list): real glyph map, preview, rights acknowledgement, then the choice.</summary>
    private void ApplyPatchFontFile(string path)
    {
        try
        {
            // Desktop preview is separate from the worker's bounded glyph/mapping preflight.
            var face = new System.Windows.Media.GlyphTypeface(new Uri(path));
            if (face.CharacterToGlyphMap.Count == 0) throw new InvalidDataException("Font has no glyph mapping.");
            if (!PreviewPatchFont(path, face.FamilyNames.Values.First())) { SetPatchFontNotice("Chưa dùng font vừa xem; lựa chọn hiện tại được giữ nguyên."); return; }
            _replacementFont = path; SetPatchFontNotice(UiText.Msg("Đã chọn font: {0}.", Path.GetFileName(_replacementFont)));
            InvalidatePatchSourceState();
        }
        catch (Exception ex) { ShowToast(ex.Message, "error"); }
    }

    /// <summary>Fallback for the case the OS file dialog cannot browse the Windows Fonts folder: pick an installed font by name; it resolves to its real file and nothing is copied.</summary>
    internal Func<IReadOnlyList<InstalledFont>, string?>? InstalledFontPickerOverride { get; set; }
    internal string? PickInstalledFont()
    {
        var fonts = InstalledFontCatalog.Enumerate();
        if (InstalledFontPickerOverride is { } over) return over(fonts);
        var info = new System.Windows.Controls.TextBlock
        {
            Text = UiText.Translate("Chọn font đã cài trên máy. VNText chỉ đọc tệp font để xem trước và không sao chép nó. Font hệ thống thường có giấy phép riêng: chỉ dùng khi bạn có quyền đóng gói và phân phối."),
            TextWrapping = TextWrapping.Wrap, Foreground = (System.Windows.Media.Brush)Application.Current.FindResource("MutedBrush")
        };
        var searchLabel = new System.Windows.Controls.TextBlock { Text = UiText.Translate("Tìm font"), FontWeight = FontWeights.SemiBold, Margin = new Thickness(0, 14, 0, 4), Foreground = (System.Windows.Media.Brush)Application.Current.FindResource("InkBrush") };
        UiText.SetAppText(searchLabel, System.Windows.Controls.TextBlock.TextProperty, "Tìm font");
        var search = new System.Windows.Controls.TextBox { Margin = new Thickness(0, 0, 0, 8), ToolTip = UiText.Translate("Tìm font") };
        System.Windows.Automation.AutomationProperties.SetLabeledBy(search, searchLabel);
        if (Application.Current.TryFindResource("FieldTextBoxStyle") is Style field) search.Style = field;
        System.Windows.Automation.AutomationProperties.SetAutomationId(search, "InstalledFontSearchBox");
        System.Windows.Automation.AutomationProperties.SetName(search, UiText.Translate("Tìm font"));
        var list = new System.Windows.Controls.ListBox { MinHeight = 200, MaxHeight = 280 };
        if (Application.Current.TryFindResource("ThemedListBoxStyle") is Style listStyle) list.Style = listStyle;
        if (Application.Current.TryFindResource("ThemedListBoxItemStyle") is Style itemStyle) list.ItemContainerStyle = itemStyle;
        System.Windows.Input.KeyboardNavigation.SetTabIndex(search, 0); System.Windows.Input.KeyboardNavigation.SetTabIndex(list, 1);
        System.Windows.Automation.AutomationProperties.SetAutomationId(list, "InstalledFontList");
        System.Windows.Automation.AutomationProperties.SetName(list, UiText.Translate("Font đã cài"));
        var empty = new System.Windows.Controls.TextBlock { Text = UiText.Translate("Không tìm thấy font .ttf/.otf đã cài."), Foreground = info.Foreground, Margin = new Thickness(0, 8, 0, 0), Visibility = Visibility.Collapsed };
        void Refresh()
        {
            var q = search.Text.Trim();
            var shown = fonts.Where(f => q.Length == 0 || f.Display.Contains(q, StringComparison.CurrentCultureIgnoreCase) || Path.GetFileName(f.Path).Contains(q, StringComparison.OrdinalIgnoreCase)).ToList();
            list.ItemsSource = shown; empty.Visibility = shown.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
        }
        search.TextChanged += (_, _) => Refresh(); Refresh();
        var body = new System.Windows.Controls.StackPanel();
        body.Children.Add(info); body.Children.Add(searchLabel); body.Children.Add(search); body.Children.Add(list); body.Children.Add(empty);
        string? chosen = null;
        var window = new AppDialogWindow(Application.Current.MainWindow, "Chọn font đã cài", body, width: 560);
        var use = window.AddButton("Chọn font này", () => chosen = (list.SelectedItem as InstalledFont)?.Path, primary: true, isDefault: true);
        use.IsEnabled = false;
        System.Windows.Automation.AutomationProperties.SetAutomationId(use, "InstalledFontChooseButton");
        list.SelectionChanged += (_, _) => use.IsEnabled = list.SelectedItem is InstalledFont;
        // Keyboard: the search box owns the first focus; Tab goes search > list > Choose (when enabled) > close, Shift+Tab the other way (the dialog cycles).
        System.Windows.Input.KeyboardNavigation.SetTabIndex(window.CloseButton, 100);
        System.Windows.Input.KeyboardNavigation.SetTabIndex(use, 50);
        window.Loaded += (_, _) => search.Dispatcher.BeginInvoke(new Action(() => { search.Focus(); System.Windows.Input.Keyboard.Focus(search); }), System.Windows.Threading.DispatcherPriority.Input);
        list.MouseDoubleClick += (_, _) => { if (list.SelectedItem is InstalledFont) use.RaiseEvent(new RoutedEventArgs(System.Windows.Controls.Primitives.ButtonBase.ClickEvent)); };
        window.ShowDialog();
        return chosen;
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
        if (Application.Current.TryFindResource("ThemedCheckBoxStyle") is Style checkStyle) permission.Style = checkStyle;
        body.Children.Add(permission);
        var window = new AppDialogWindow(Application.Current.MainWindow, "Xem trước font Việt", body, width: 640);
        var use = window.AddButton("Dùng font này", () => accepted = true, primary: true, isDefault: true);
        use.IsEnabled = false;
        System.Windows.Input.KeyboardNavigation.SetTabIndex(window.CloseButton, 100);
        System.Windows.Input.KeyboardNavigation.SetTabIndex(use, 50);
        window.Loaded += (_, _) => permission.Dispatcher.BeginInvoke(
            new Action(() => System.Windows.Input.Keyboard.Focus(permission)),
            System.Windows.Threading.DispatcherPriority.Input);
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
