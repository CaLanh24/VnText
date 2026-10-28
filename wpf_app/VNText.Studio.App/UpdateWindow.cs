using System.ComponentModel;
using System.Collections.Specialized;
using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Automation;
using VNText.Studio.App.ViewModels;
using VNText.Studio.App.Controls;
using VNText.Studio.App.Services;

namespace VNText.Studio.App;

internal sealed record UpdateViewState(string Version, string Current, string Notes, string Status,
    bool Downloading, bool Ready, bool Available, bool CanStart, bool Indeterminate, double Percent)
{
    internal static UpdateViewState From(IUpdatePresentation source) => new(source.Version, source.CurrentVersion,
        source.Notes, source.Status, source.Downloading, source.Ready, source.Available, source.CanStart,
        source.Total <= 0, source.Total <= 0 ? 0 : Math.Clamp(100d * source.Received / source.Total, 0, 100));
    internal string PrimaryLabel => Downloading ? "Đang tải xuống..." : Ready ? "Khởi động lại" : "Cập nhật ngay";
}

internal sealed class UpdateWindow : Window
{
    private readonly IUpdatePresentation _source;
    private readonly bool _notesOnly;
    private readonly string? _successVersion;
    private readonly Button _primary, _skip, _later, _cancel;
    private readonly TextBlock _version, _date, _current, _status, _banner, _progressText;
    private readonly ProgressBar _progress;
    private readonly Border _success, _versionBadge, _dateBadge, _notesHeading;
    private readonly Grid _progressArea;
    private readonly ScrollViewer _notes;
    private bool _starting;
    private Effect? _previousEffect;
    private string? _renderedNotes;
    private Panel? _ownerPanel;
    private Border? _overlay;
    internal UpdateWindow(MainWindow owner, MainViewModel vm, string? successVersion = null)
        : this(owner, owner.UpdatePresentation, false, successVersion) { }
    internal UpdateWindow(MainWindow owner, IUpdatePresentation source, bool notesOnly = false, string? successVersion = null)
    {
        _source = source; _notesOnly = notesOnly; _successVersion = successVersion;
        Owner = owner; Title = notesOnly ? "Ghi chú phát hành" : "Cập nhật VNText Studio";
        Width = notesOnly ? 880 : 620; SizeToContent = SizeToContent.Height;
        if (notesOnly) { Height = Math.Max(280, Math.Min(720, owner.ActualHeight - 24)); SizeToContent = SizeToContent.Manual; }
        MaxWidth = Math.Max(320, owner.ActualWidth - 24); MaxHeight = Math.Max(300, owner.ActualHeight - 24);
        WindowStartupLocation = WindowStartupLocation.CenterOwner; WindowStyle = WindowStyle.None;
        ResizeMode = ResizeMode.NoResize; AllowsTransparency = true; Background = Brushes.Transparent;
        ShowInTaskbar = false; FontFamily = owner.FontFamily; FontSize = 13;
        KeyboardNavigation.SetTabNavigation(this, KeyboardNavigationMode.Cycle);
        KeyboardNavigation.SetControlTabNavigation(this, KeyboardNavigationMode.Cycle);
        Brush Brush(string key) => (Brush)owner.FindResource(key);
        var surface = new Border { Margin = new Thickness(AppDialogWindow.CardMargin), CornerRadius = new CornerRadius(AppDialogWindow.CardRadius),
            Background = Brush("SurfaceBrush"), Effect = new DropShadowEffect { BlurRadius = 32, ShadowDepth = 9, Opacity = .25 } };
        var grid = new Grid(); surface.Child = grid; Content = surface;
        if (UiAppearance.Scaled)
        {
            surface.LayoutTransform = new ScaleTransform(UiAppearance.Scale, UiAppearance.Scale);
            Width *= UiAppearance.Scale;
            if (notesOnly) Height *= UiAppearance.Scale;
        }
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto }); grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        if (notesOnly) grid.RowDefinitions[1].Height = new GridLength(1, GridUnitType.Star);
        var header = new Grid { Margin = new Thickness(24, 17, 24, 17) };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.ColumnDefinitions.Add(new ColumnDefinition()); header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var icon = new Border { Width = 28, Height = 28, CornerRadius = new CornerRadius(8), Background = Gradient(false), Margin = new Thickness(0, 0, 12, 0) };
        icon.Child = new TextBlock { Text = notesOnly ? "≡" : "↻", Foreground = Brushes.White, FontSize = 19, HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center };
        if (!notesOnly) header.Children.Add(icon);
        var heading = new TextBlock { Text = notesOnly ? "Ghi chú phát hành" : successVersion is null ? "Có bản cập nhật mới" : "Cập nhật thành công",
            FontSize = 18, FontWeight = FontWeights.SemiBold, Foreground = Brush("InkBrush"), VerticalAlignment = VerticalAlignment.Center, TextWrapping = TextWrapping.Wrap };
        Grid.SetColumn(heading, 1); header.Children.Add(heading);
        var close = new Button { Content = new TextBlock { Text = "×", FontSize = 20, VerticalAlignment = VerticalAlignment.Center }, Style = (Style)owner.FindResource("DialogCloseButton") };
        AutomationProperties.SetName(close, "Đóng " + Title); close.ToolTip = "Đóng (Esc)";
        close.Click += (_, _) => Close(); Grid.SetColumn(close, 2); header.Children.Add(close);
        grid.Children.Add(new Border { Child = header, BorderBrush = Brush("LineBrush"), BorderThickness = new Thickness(0, 0, 0, 1) });
        var body = new Grid { Margin = new Thickness(26, 18, 26, 18) }; Grid.SetRow(body, 1); grid.Children.Add(body);
        for (var n = 0; n < 4; n++) body.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        if (notesOnly) body.RowDefinitions[3].Height = new GridLength(1, GridUnitType.Star);
        _version = new TextBlock { Foreground = notesOnly ? Brush("MutedBrush") : Brush("BlueBrush"), FontSize = 13, FontWeight = FontWeights.SemiBold, TextWrapping = TextWrapping.Wrap };
        var releaseBadges = new StackPanel { Orientation = Orientation.Horizontal };
        body.Children.Add(releaseBadges);
        releaseBadges.Children.Add(_versionBadge = new Border { Child = _version, Background = notesOnly ? new SolidColorBrush(Color.FromRgb(241, 243, 246)) : Brushes.Transparent, CornerRadius = new CornerRadius(8), Padding = new Thickness(8, 4, 8, 4), HorizontalAlignment = HorizontalAlignment.Left, Margin = new Thickness(0, 0, 8, 0) });
        _date = new TextBlock { Foreground = Brush("MutedBrush"), FontSize = 12, FontWeight = FontWeights.SemiBold, TextWrapping = TextWrapping.Wrap };
        releaseBadges.Children.Add(_dateBadge = new Border { Child = _date, Background = notesOnly ? new SolidColorBrush(Color.FromRgb(241, 243, 246)) : Brushes.Transparent, CornerRadius = new CornerRadius(8), Padding = new Thickness(8, 4, 8, 4), HorizontalAlignment = HorizontalAlignment.Left });
        _current = new TextBlock { Foreground = Brush("MutedBrush"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 8, 0, 12) };
        Grid.SetRow(_current, 1); body.Children.Add(_current);
        var stateArea = new StackPanel(); Grid.SetRow(stateArea, 2); body.Children.Add(stateArea);
        _progressArea = new Grid { Margin = new Thickness(0, 0, 0, 12) };
        _progressArea.ColumnDefinitions.Add(new ColumnDefinition()); _progressArea.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        _progressArea.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto }); _progressArea.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        _progress = new ProgressBar { Style = (Style)owner.FindResource("BlueProgressBarStyle"), Foreground = Gradient(false), Height = 3, VerticalAlignment = VerticalAlignment.Center };
        _progressArea.Children.Add(_progress); _cancel = MakeIconButton(owner, "⊗", 20); _cancel.Margin = new Thickness(8, 0, 0, 0);
        AutomationProperties.SetName(_cancel, "Hủy tải cập nhật"); _cancel.Click += (_, _) => source.Cancel(); Grid.SetColumn(_cancel, 1); _progressArea.Children.Add(_cancel);
        _progressText = new TextBlock { HorizontalAlignment = HorizontalAlignment.Center, FontSize = 10, Foreground = Brush("MutedBrush"), Margin = new Thickness(0, 4, 0, 0) };
        Grid.SetRow(_progressText, 1); Grid.SetColumnSpan(_progressText, 2); _progressArea.Children.Add(_progressText); stateArea.Children.Add(_progressArea);
        _banner = new TextBlock { TextWrapping = TextWrapping.Wrap, Foreground = Brush("GreenDarkBrush") };
        _success = new Border { Background = Brush("GreenSoftBrush"), CornerRadius = new CornerRadius(9), Padding = new Thickness(10, 7, 10, 7), Margin = new Thickness(0, 0, 0, 12), Child = _banner };
        stateArea.Children.Add(_success);
        var notesArea = new Grid(); Grid.SetRow(notesArea, 3); body.Children.Add(notesArea);
        notesArea.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto }); notesArea.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        if (notesOnly) notesArea.RowDefinitions[1].Height = new GridLength(1, GridUnitType.Star);
        _notesHeading = new Border { BorderBrush = Brush("LineBrush"), BorderThickness = new Thickness(0, 1, 0, 0), Padding = new Thickness(0, 12, 0, 8),
            Child = new TextBlock { Text = notesOnly ? "Có gì mới" : "Tính năng mới", FontWeight = FontWeights.SemiBold, TextWrapping = TextWrapping.Wrap, Foreground = Brush("InkBrush") } };
        notesArea.Children.Add(_notesHeading);
        _notes = new ScrollViewer { Style = (Style)owner.FindResource("ContentPanelScrollViewer"), VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled };
        Grid.SetRow(_notes, 1); notesArea.Children.Add(_notes);
        var footer = new StackPanel();
        _status = new TextBlock { Foreground = Brush("MutedBrush"), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 10) }; footer.Children.Add(_status);
        var buttons = new WrapPanel { HorizontalAlignment = HorizontalAlignment.Right }; footer.Children.Add(buttons);
        _later = MakeButton(owner, notesOnly ? "Đóng" : "Hủy", false); _skip = MakeButton(owner, "Bỏ qua phiên bản này", false); _primary = MakeButton(owner, "Cập nhật ngay", true);
        _later.Margin = _skip.Margin = _primary.Margin = new Thickness(4);
        buttons.Children.Add(_later); buttons.Children.Add(_skip); buttons.Children.Add(_primary);
        var footerSurface = new Border { Background = Brush("SubtlePanelBrush"), CornerRadius = new CornerRadius(0, 0, AppDialogWindow.CardRadius, AppDialogWindow.CardRadius), BorderBrush = Brush("LineBrush"), BorderThickness = new Thickness(0, 1, 0, 0), Padding = new Thickness(22, 10, 22, 10), Child = footer };
        Grid.SetRow(footerSurface, 2); grid.Children.Add(footerSurface);
        _later.Click += (_, _) => Close(); _skip.Click += (_, _) => { source.Defer(true); Close(); };
        _primary.Click += async (_, _) =>
        {
            if (_starting || source.Downloading || !source.CanStart) return;
            if (source.Ready) { try { source.Restart(); } catch (Exception ex) { _status.Text = ex.Message; } return; }
            _starting = true; _primary.IsEnabled = false;
            try { await source.DownloadAsync(); } catch (Exception ex) { _status.Text = "Không tải được cập nhật: " + ex.Message; }
            finally { _starting = false; if (IsVisible) Refresh(); }
        };
        PreviewKeyDown += (_, e) => { if (e.Key == Key.Escape) { e.Handled = true; Close(); } };
        Loaded += (_, _) =>
        {
            if (owner.Content is UIElement element)
            {
                _previousEffect = element.Effect; element.Effect = new BlurEffect { Radius = AppDialogWindow.BackdropBlur };
                _ownerPanel = element as Panel ?? throw new InvalidOperationException("Modal owner must expose the app root panel for dim coverage.");
                _overlay = new Border { Background = new SolidColorBrush(AppDialogWindow.BackdropColor), IsHitTestVisible = false };
                Grid.SetColumnSpan(_overlay, 2); Grid.SetRowSpan(_overlay, Math.Max(1, (_ownerPanel as Grid)?.RowDefinitions.Count ?? 1));
                Panel.SetZIndex(_overlay, int.MaxValue); _ownerPanel.Children.Add(_overlay);
            }
            close.Focus();
        };
        Closing += (_, _) => { if (!notesOnly && successVersion is null) { source.Defer(false); if (source.Downloading) source.Cancel(); } };
        if (notesOnly && owner.DataContext is MainViewModel historyVm)
        {
            historyVm.ReleaseNotesHistory.CollectionChanged += HistoryChanged;
            historyVm.PropertyChanged += Changed;
        }
        Closed += (_, _) => { source.PropertyChanged -= Changed; if (owner.DataContext is MainViewModel closingHistoryVm) { closingHistoryVm.ReleaseNotesHistory.CollectionChanged -= HistoryChanged; closingHistoryVm.PropertyChanged -= Changed; } if (_overlay is not null) _ownerPanel?.Children.Remove(_overlay); if (owner.Content is UIElement element) element.Effect = _previousEffect; };
        // Content-driven state rows change height after opening; keep the dialog centered.
        SizeChanged += (_, _) =>
        {
            if (!IsVisible) return;
            Left = owner.Left + (owner.ActualWidth - ActualWidth) / 2;
            Top = owner.Top + (owner.ActualHeight - ActualHeight) / 2;
        };
        source.PropertyChanged += Changed; Refresh();
    }
    private void Changed(object? sender, PropertyChangedEventArgs e)
    {
        if (!Dispatcher.CheckAccess()) { Dispatcher.BeginInvoke(new Action(Refresh)); return; } Refresh();
    }
    private void HistoryChanged(object? sender, NotifyCollectionChangedEventArgs e) { _renderedNotes = null; Changed(sender, new PropertyChangedEventArgs("ReleaseNotesHistory")); }
    private void Refresh()
    {
        var state = UpdateViewState.From(_source);
        var releaseVersion = _successVersion ?? state.Version;
        _version.Text = string.IsNullOrWhiteSpace(releaseVersion) ? "" : "v" + releaseVersion;
        _versionBadge.Visibility = _notesOnly && string.IsNullOrWhiteSpace(releaseVersion) ? Visibility.Collapsed : Visibility.Visible;
        _date.Text = string.IsNullOrWhiteSpace(_source.ReleaseDate) ? "" : "Phát hành " + _source.ReleaseDate;
        _dateBadge.Visibility = string.IsNullOrWhiteSpace(_source.ReleaseDate) ? Visibility.Collapsed : Visibility.Visible;
        _current.Visibility = _notesOnly ? Visibility.Collapsed : Visibility.Visible;
        _notesHeading.Visibility = _notesOnly && string.IsNullOrWhiteSpace(releaseVersion) ? Visibility.Collapsed : Visibility.Visible;
        var updateCompleted = !string.IsNullOrWhiteSpace(_successVersion);
        _current.Text = _notesOnly ? "Ghi chú phiên bản"
            : updateCompleted ? $"Đã cập nhật thành công lên phiên bản v{_successVersion}."
            : $"Phiên bản hiện tại {state.Current}, " + (state.Ready ? "gói mới đã được kiểm tra." : "đã có phiên bản mới.");
        var notesText = _successVersion is not null && Owner.DataContext is MainViewModel vm ? vm.VerifiedSuccessNotes : state.Notes;
        if (string.IsNullOrWhiteSpace(notesText)) notesText = "Chưa có ghi chú phát hành. Kiểm tra cập nhật để xem thông tin mới nhất.";
        if (_notesOnly && Owner.DataContext is MainViewModel historyVm)
        {
            var signature = string.Join("\u001f", historyVm.ReleaseNotesHistory.Select(entry => entry.Version + "\u001e" + entry.ReleaseDate + "\u001e" + entry.Notes));
            if (_renderedNotes != signature) { _renderedNotes = signature; _notes.Content = RenderHistory(Owner, historyVm.ReleaseNotesHistory); }
            _versionBadge.Visibility = _dateBadge.Visibility = _notesHeading.Visibility = Visibility.Collapsed;
        }
        else if (_renderedNotes != notesText) { _renderedNotes = notesText; _notes.Content = RenderNotes(notesText); }
        _progressArea.Visibility = state.Downloading && !_notesOnly ? Visibility.Visible : Visibility.Collapsed;
        _progress.IsIndeterminate = state.Indeterminate; _progress.Maximum = 100; _progress.Value = state.Percent;
        _progressText.Text = state.Indeterminate ? "Đang tải xuống..." : $"Đang tải xuống... {state.Percent:0}%";
        _success.Visibility = (state.Ready || updateCompleted) && !_notesOnly ? Visibility.Visible : Visibility.Collapsed;
        _banner.Text = updateCompleted
            ? $"✓  VNText Studio đã cập nhật lên v{_successVersion} và sẵn sàng sử dụng."
            : $"✓  Phiên bản v{state.Version} đã sẵn sàng. Hãy khởi động lại để áp dụng.";
        _status.Text = _notesOnly && Owner.DataContext is MainViewModel statusVm ? statusVm.ReleaseNotesStatus : _source.IsTestFixture ? "" : state.Status;
        _status.Visibility = string.IsNullOrWhiteSpace(_status.Text) ? Visibility.Collapsed : Visibility.Visible;
        // Measure actual short content; cap only long release bodies. State rows add their own height.
        _notes.MaxHeight = _notesOnly ? double.PositiveInfinity : Math.Min(145, Math.Max(90, Owner.ActualHeight * .22));
        MaxHeight = _notesOnly ? Math.Max(280, Owner.ActualHeight - 24) : Math.Max(300, Owner.ActualHeight * .80);
        var primaryContents = new StackPanel { Orientation = Orientation.Horizontal };
        var glyph = new TextBlock { Text = state.Downloading ? "◌" : state.Ready ? "↻" : "↓", Margin = new Thickness(0, 0, 8, 0), RenderTransformOrigin = new Point(.5, .5) };
        if (state.Downloading) { var rotation = new RotateTransform(); glyph.RenderTransform = rotation; rotation.BeginAnimation(RotateTransform.AngleProperty, new System.Windows.Media.Animation.DoubleAnimation(0, 360, TimeSpan.FromSeconds(1.2)) { RepeatBehavior = System.Windows.Media.Animation.RepeatBehavior.Forever }); }
        primaryContents.Children.Add(glyph); primaryContents.Children.Add(new TextBlock { Text = state.PrimaryLabel }); _primary.Content = primaryContents; AutomationProperties.SetName(_primary, state.PrimaryLabel);
        _primary.IsEnabled = state.CanStart && !state.Downloading && !_starting;
        _primary.Opacity = state.Downloading ? .65 : 1;
        _skip.Visibility = !state.Downloading && state.Available && !_notesOnly && _successVersion is null ? Visibility.Visible : Visibility.Collapsed;
        _primary.Visibility = !_notesOnly && _successVersion is null ? Visibility.Visible : Visibility.Collapsed;
        _later.Content = _notesOnly || _successVersion is not null ? "Đóng" : state.Downloading || state.Ready ? "Để sau" : "Hủy";
    }
    internal static LinearGradientBrush Gradient(bool ready) => new(Color.FromRgb(37, 99, 235), Color.FromRgb(0, 181, 205), 0);
    private static Button MakeButton(FrameworkElement owner, string text, bool primary)
    {
        // Same rounded PrimaryButton/OutlineButton styles as AppDialogWindow (hover, pressed, keyboard focus).
        var b = new Button { Content = text, Style = (Style)owner.FindResource(primary ? "PrimaryButton" : "OutlineButton"), Padding = new Thickness(14, 7, 14, 7), FontSize = 13 };
        AutomationProperties.SetName(b, text); return b;
    }
    private static Button MakeIconButton(MainWindow owner, string text, double size)
    {
        var border = new FrameworkElementFactory(typeof(Border));
        border.SetValue(Border.BackgroundProperty, Brushes.Transparent);
        border.SetValue(Border.CornerRadiusProperty, new CornerRadius(15));
        var content = new FrameworkElementFactory(typeof(ContentPresenter));
        content.SetValue(FrameworkElement.HorizontalAlignmentProperty, HorizontalAlignment.Center);
        content.SetValue(FrameworkElement.VerticalAlignmentProperty, VerticalAlignment.Center);
        content.SetBinding(ContentPresenter.ContentProperty, new System.Windows.Data.Binding("Content") { RelativeSource = System.Windows.Data.RelativeSource.TemplatedParent });
        border.AppendChild(content);
        var button = new Button { Content = new TextBlock { Text = text, FontSize = size == 20 ? 13 : 20 },
            Template = new ControlTemplate(typeof(Button)) { VisualTree = border },
            Background = Brushes.Transparent, BorderThickness = new Thickness(0), Width = size, Height = size,
            MinWidth = 0, MinHeight = 0, Padding = new Thickness(0), Foreground = (Brush)owner.FindResource("MutedBrush"),
            FocusVisualStyle = (Style)owner.FindResource("KeyboardFocusStyle"), Cursor = Cursors.Hand };
        button.MouseEnter += (_, _) => button.Foreground = (Brush)owner.FindResource("InkBrush");
        button.MouseLeave += (_, _) => button.Foreground = (Brush)owner.FindResource("MutedBrush");
        return button;
    }
    internal static StackPanel RenderHistory(FrameworkElement owner, IEnumerable<ReleaseNotesCacheEntry> history)
    {
        var panel = new StackPanel();
        foreach (var entry in history)
        {
            var content = new StackPanel();
            var header = new Grid { Margin = new Thickness(0, 0, 0, 12) };
            header.ColumnDefinitions.Add(new ColumnDefinition());
            header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
            var label = new StackPanel();
            label.Children.Add(new TextBlock { Text = "v" + entry.Version, FontWeight = FontWeights.SemiBold,
                Foreground = (Brush)owner.FindResource("InkBrush"), FontSize = 14 });
            if (!string.IsNullOrWhiteSpace(entry.ReleaseDate))
                label.Children.Add(new TextBlock { Text = entry.ReleaseDate, Foreground = (Brush)owner.FindResource("MutedBrush"), Margin = new Thickness(0, 4, 0, 0) });
            header.Children.Add(label);
            if (!string.IsNullOrWhiteSpace(entry.DownloadUrl))
            {
                var download = MakeButton(owner, "Tải xuống", false);
                download.VerticalAlignment = VerticalAlignment.Top;
                AutomationProperties.SetName(download, "Tải phiên bản " + entry.Version);
                download.Click += (_, _) =>
                {
                    try { Process.Start(new ProcessStartInfo(entry.DownloadUrl) { UseShellExecute = true }); }
                    catch { AppDialogService.Show("Không mở được trang tải. Hãy thử lại khi trình duyệt sẵn sàng.", "Mở trang tải", MessageBoxButton.OK, MessageBoxImage.Information); }
                };
                Grid.SetColumn(download, 1); header.Children.Add(download);
            }
            content.Children.Add(header); content.Children.Add(RenderNotes(entry.Notes));
            panel.Children.Add(new Border { Child = content, Background = (Brush)owner.FindResource("SurfaceBrush"),
                BorderBrush = (Brush)owner.FindResource("LineBrush"), BorderThickness = new Thickness(1),
                CornerRadius = new CornerRadius(14), Padding = new Thickness(18), Margin = new Thickness(0, 0, 0, 12) });
        }
        if (panel.Children.Count == 0)
            panel.Children.Add(new TextBlock { Text = "Chưa có ghi chú được lưu. Kết nối mạng và kiểm tra cập nhật để tải lịch sử; sau đó bạn có thể xem lại khi ngoại tuyến.",
                TextWrapping = TextWrapping.Wrap, Foreground = (Brush)owner.FindResource("MutedBrush"), Margin = new Thickness(0, 8, 0, 8) });
        return panel;
    }

    private static StackPanel RenderNotes(string text)
    {
        var panel = new StackPanel();
        foreach (var raw in text.Replace("\r", "").Split('\n'))
        {
            var line = raw.Trim(); if (line.Length == 0) continue;
            var heading = line.StartsWith('#'); var bullet = line.StartsWith("- ") || line.StartsWith("* ");
            var visible = heading ? line.TrimStart('#', ' ') : bullet ? "• " + line[2..] : line;
            var block = new TextBlock { TextWrapping = TextWrapping.Wrap,
                FontWeight = heading ? FontWeights.SemiBold : FontWeights.Normal, FontSize = 13, Margin = new Thickness(bullet ? 7 : 0, heading ? 8 : 2, 0, 3), LineHeight = 20 };
            block.SetResourceReference(TextBlock.ForegroundProperty, "InkBrush");
            var chunks = visible.Split("**", StringSplitOptions.None);
            for (var i = 0; i < chunks.Length; i++)
                block.Inlines.Add(new Run(chunks[i]) { FontWeight = i % 2 == 1 ? FontWeights.SemiBold : heading ? FontWeights.SemiBold : FontWeights.Normal });
            panel.Children.Add(block);
        }
        return panel;
    }
}
