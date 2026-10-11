using System.Windows;
using System.Windows.Controls;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;
using System.Windows.Automation;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App;

internal sealed class UpdateWindow : Window
{
    internal UpdateWindow(MainWindow owner, MainViewModel vm, string? successVersion = null)
    {
        Owner = owner; Title = "Cập nhật VNText Studio";
        Width = 700; Height = 560; MaxWidth = Math.Max(400, owner.ActualWidth - 40);
        MaxHeight = Math.Max(360, owner.ActualHeight - 40); WindowStartupLocation = WindowStartupLocation.CenterOwner;
        WindowStyle = WindowStyle.None; ResizeMode = ResizeMode.NoResize;
        AllowsTransparency = true; Background = Brushes.Transparent; ShowInTaskbar = false;
        FontFamily = owner.FontFamily; FontSize = 14;
        Brush Brush(string key) => (Brush)owner.FindResource(key);
        Foreground = Brush("InkBrush");
        var surface = new Border { Margin = new Thickness(14), CornerRadius = new CornerRadius(16),
            Background = Brush("SurfaceBrush"), Effect = new DropShadowEffect { BlurRadius = 24, ShadowDepth = 6, Opacity = .22 } };
        var grid = new Grid(); surface.Child = grid; Content = surface;
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var header = new Grid { Margin = new Thickness(26, 24, 26, 20) };
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        header.ColumnDefinitions.Add(new ColumnDefinition());
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var logo = new Image { Width = 32, Height = 32, VerticalAlignment = VerticalAlignment.Top,
            Source = new BitmapImage(new Uri("pack://application:,,,/VNText.Studio.App;component/Assets/vntext_studio_logo_128.png")), Margin = new Thickness(0, 3, 14, 0) };
        header.Children.Add(logo);
        var heading = new StackPanel(); Grid.SetColumn(heading, 1); header.Children.Add(heading);
        heading.Children.Add(new TextBlock { Text = successVersion is null ? "Có bản cập nhật mới" : "Cập nhật thành công", FontSize = 22, FontWeight = FontWeights.Bold, TextWrapping = TextWrapping.Wrap });
        var versions = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 10, 0, 0) };
        var versionLabel = new TextBlock { Text = successVersion ?? vm.OfferedVersion, FontSize = 17, FontWeight = FontWeights.SemiBold, Foreground = Brush("GreenDarkBrush") };
        versions.Children.Add(versionLabel);
        versions.Children.Add(new TextBlock { Text = successVersion is null ? $"  ·  Hiện tại {vm.CurrentVersionDisplay}" : "  ·  Đã cập nhật", Foreground = Brush("MutedBrush"), VerticalAlignment = VerticalAlignment.Center });
        heading.Children.Add(versions);
        var close = new Button { Style = (Style)owner.FindResource("OutlineButton"), Width = 34, Height = 34, Padding = new Thickness(8), VerticalAlignment = VerticalAlignment.Top,
            Content = new System.Windows.Shapes.Path { Data = Geometry.Parse("M2,2 L12,12 M12,2 L2,12"), Stroke = Brush("MutedBrush"), StrokeThickness = 1.7, Stretch = Stretch.Uniform } };
        AutomationProperties.SetName(close, "Đóng thông báo cập nhật"); close.ToolTip = "Đóng (Esc)";
        close.Click += (_, _) => Close(); Grid.SetColumn(close, 2); header.Children.Add(close);
        header.MouseLeftButtonDown += (_, e) => { if (e.OriginalSource is TextBlock or Image) DragMove(); };
        var headerBorder = new Border { BorderBrush = Brush("LineBrush"), BorderThickness = new Thickness(0, 0, 0, 1), Child = header };
        grid.Children.Add(headerBorder);
        var body = new Grid { Margin = new Thickness(26, 20, 26, 20) }; Grid.SetRow(body, 1); grid.Children.Add(body);
        body.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto }); body.RowDefinitions.Add(new RowDefinition());
        body.Children.Add(new TextBlock { Text = "Có gì mới", FontSize = 16, FontWeight = FontWeights.SemiBold, Margin = new Thickness(0, 0, 0, 12) });
        TextBlock NotesText(string text) => new() { Text = text, TextWrapping = TextWrapping.Wrap, LineHeight = 23, Foreground = Brush("InkBrush") };
        var notes = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            Style = (Style)owner.FindResource("ContentPanelScrollViewer"), Content = NotesText(vm.UpdateNotes) };
        Grid.SetRow(notes, 1); body.Children.Add(notes);
        var footer = new StackPanel();
        var footerBorder = new Border { Background = Brush("CanvasBrush"), CornerRadius = new CornerRadius(0, 0, 16, 16), Padding = new Thickness(26, 18, 26, 20), Child = footer,
            BorderBrush = Brush("LineBrush"), BorderThickness = new Thickness(0, 1, 0, 0) };
        Grid.SetRow(footerBorder, 2); grid.Children.Add(footerBorder);
        var status = new TextBlock { TextWrapping = TextWrapping.Wrap, Foreground = Brush("MutedBrush"), Margin = new Thickness(0, 0, 0, 10),
            Text = successVersion is null ? "Chỉ tải khi bạn chọn cập nhật." : "Phiên bản và kết quả cập nhật đã được xác nhận." };
        var progress = new ProgressBar { Style = (Style)owner.FindResource("ExtractionProgressBarStyle"), Height = 6, Visibility = Visibility.Collapsed, Margin = new Thickness(0, 0, 0, 16) };
        footer.Children.Add(status); footer.Children.Add(progress);
        var buttons = new WrapPanel { HorizontalAlignment = HorizontalAlignment.Right };
        footer.Children.Add(buttons);
        PreviewKeyDown += (_, e) => { if (e.Key == Key.Escape) { e.Handled = true; Close(); } };
        DimAdorner? dim = null; AdornerLayer? layer = null;
        Loaded += (_, _) =>
        {
            layer = AdornerLayer.GetAdornerLayer((UIElement)owner.Content);
            if (layer is not null) { dim = new DimAdorner((UIElement)owner.Content); layer.Add(dim); }
            close.Focus();
        };
        Closed += (_, _) => { if (dim is not null) layer?.Remove(dim); };
        void SetAction(Button button, string text, bool restart = false)
        {
            var content = new StackPanel { Orientation = Orientation.Horizontal };
            var icon = new System.Windows.Shapes.Path { Width = 16, Height = 16, Margin = new Thickness(0, 0, 8, 0), Stretch = Stretch.Uniform,
                StrokeThickness = 1.7, Stroke = button.Foreground, Data = Geometry.Parse(restart ? "M19,9 A8,8 0 1 0 19,15 M19,3 V9 H13" : "M12,3 V15 M7,10 L12,15 L17,10 M4,17 V21 H20 V17") };
            content.Children.Add(icon); content.Children.Add(new TextBlock { Text = text }); button.Content = content;
            AutomationProperties.SetName(button, text);
        }
        if (successVersion is not null)
        {
            notes.Content = NotesText(string.IsNullOrWhiteSpace(vm.VerifiedSuccessNotes) ? "Phiên bản này chưa cung cấp ghi chú phát hành." : vm.VerifiedSuccessNotes);
            var done = new Button { Content = "Hoàn tất", IsDefault = true, IsCancel = true, Style = (Style)owner.FindResource("PrimaryButton") };
            done.Click += (_, _) => Close();
            buttons.Children.Add(done);
            return;
        }
        var defer = new Button { Content = "Để sau", Margin = new Thickness(4), Style = (Style)owner.FindResource("OutlineButton") };
        var skip = new Button { Content = "Bỏ qua phiên bản này", Margin = new Thickness(4), Style = (Style)owner.FindResource("OutlineButton") };
        var action = new Button { Content = vm.GitHubApplyEnabled ? "Khởi động lại để cập nhật" : "Cập nhật", Margin = new Thickness(4), Style = (Style)owner.FindResource("PrimaryButton") };
        SetAction(action, vm.GitHubApplyEnabled ? "Khởi động lại để cập nhật" : "Cập nhật", vm.GitHubApplyEnabled);
        buttons.Children.Add(defer); buttons.Children.Add(skip); buttons.Children.Add(action);
        defer.Click += (_, _) => { vm.DeferUpdate(false); Close(); };
        skip.Click += (_, _) => { vm.DeferUpdate(true); Close(); };
        vm.PropertyChanged += OnProgress;
        void OnProgress(object? sender, System.ComponentModel.PropertyChangedEventArgs e)
        {
            if (e.PropertyName == nameof(vm.OfferedVersion) && !string.IsNullOrWhiteSpace(vm.OfferedVersion))
                versionLabel.Text = vm.OfferedVersion;
            if (e.PropertyName == nameof(vm.UpdateNotes))
                notes.Content = NotesText(vm.UpdateNotes);
            if (e.PropertyName is nameof(vm.DownloadReceived) or nameof(vm.DownloadTotal))
            {
                progress.IsIndeterminate = vm.DownloadTotal <= 0;
                progress.Maximum = Math.Max(1, vm.DownloadTotal); progress.Value = vm.DownloadReceived;
                status.Text = $"Đang tải: {vm.DownloadReceived:N0} / {vm.DownloadTotal:N0} byte";
            }
        }
        action.Click += async (_, _) =>
        {
            if (vm.Busy || vm.CsvEditorDirty)
            {
                status.Text = "Hãy hoàn tất tác vụ và lưu CSV trước khi cập nhật.";
                return;
            }
            if (vm.GitHubApplyEnabled)
            {
                try { vm.RestartForUpdate(); }
                catch (Exception ex) { status.Text = "Không khởi chạy được cập nhật: " + ex.Message; }
                return;
            }
            action.IsEnabled = false; skip.IsEnabled = false; defer.Content = "Hủy tải";
            progress.Visibility = Visibility.Visible; progress.IsIndeterminate = true;
            try { await vm.DownloadOfferedUpdateAsync(); }
            catch (Exception ex) { status.Text = "Không tải được cập nhật: " + ex.Message; }
            if (!IsVisible) return;
            status.Text = vm.GitHubApplyEnabled ? "Đã kiểm tra gói. Sẵn sàng cập nhật." : vm.GitHubUpdateStatus;
            SetAction(action, vm.GitHubApplyEnabled ? "Khởi động lại để cập nhật" : "Thử lại", vm.GitHubApplyEnabled);
            action.IsEnabled = true; skip.IsEnabled = true; defer.Content = "Để sau";
        };
        Closing += (_, _) => { vm.DeferUpdate(false); if (vm.DownloadingUpdate) vm.CancelUpdateDownload(); };
        Closed += (_, _) => vm.PropertyChanged -= OnProgress;
    }

    private sealed class DimAdorner(UIElement element) : Adorner(element)
    {
        protected override void OnRender(DrawingContext drawingContext) => drawingContext.DrawRectangle(
            new SolidColorBrush(Color.FromArgb(64, 32, 36, 45)), null, new Rect(AdornedElement.RenderSize));
    }
}
