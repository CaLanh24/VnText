using System.Windows;
using System.Windows.Controls;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App;

internal sealed class UpdateWindow : Window
{
    internal UpdateWindow(MainWindow owner, MainViewModel vm, string? successVersion = null)
    {
        Owner = owner; Title = "Cập nhật VNText Studio";
        Width = 620; Height = 500; MaxWidth = Math.Max(400, owner.ActualWidth - 40);
        MaxHeight = Math.Max(360, owner.ActualHeight - 40); WindowStartupLocation = WindowStartupLocation.CenterOwner;
        Background = (System.Windows.Media.Brush)owner.FindResource("SurfaceBrush");
        FontFamily = owner.FontFamily; FontSize = 14;
        var grid = new Grid { Margin = new Thickness(24) };
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        var heading = new StackPanel();
        heading.Children.Add(new TextBlock { Text = successVersion is null ? "Có bản cập nhật mới" : "Cập nhật thành công", FontSize = 22, FontWeight = FontWeights.Bold });
        var versionLabel = new TextBlock { Text = successVersion is null ? $"Phiên bản mới {vm.OfferedVersion} • Hiện tại {vm.CurrentVersionDisplay}" : $"Bạn đang dùng phiên bản {successVersion}.", Margin = new Thickness(0, 10, 0, 16), TextWrapping = TextWrapping.Wrap };
        heading.Children.Add(versionLabel);
        grid.Children.Add(heading);
        var notes = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto, Content = new TextBlock { Text = vm.UpdateNotes, TextWrapping = TextWrapping.Wrap }, Margin = new Thickness(0, 0, 0, 16) };
        Grid.SetRow(notes, 1); grid.Children.Add(notes);
        var footer = new StackPanel(); Grid.SetRow(footer, 2); grid.Children.Add(footer);
        var status = new TextBlock { TextWrapping = TextWrapping.Wrap };
        var progress = new ProgressBar { Height = 6, Visibility = Visibility.Collapsed, Margin = new Thickness(0, 8, 0, 12) };
        footer.Children.Add(status); footer.Children.Add(progress);
        var buttons = new WrapPanel { HorizontalAlignment = HorizontalAlignment.Right };
        footer.Children.Add(buttons);
        if (successVersion is not null)
        {
            notes.Content = new TextBlock { Text = vm.VerifiedSuccessNotes, TextWrapping = TextWrapping.Wrap };
            var done = new Button { Content = "Hoàn tất", IsDefault = true, IsCancel = true, Style = (Style)owner.FindResource("PrimaryButton") };
            done.Click += (_, _) => Close();
            buttons.Children.Add(done);
            Content = grid;
            return;
        }
        var defer = new Button { Content = "Để sau", Margin = new Thickness(4), Padding = new Thickness(12, 8, 12, 8) };
        var skip = new Button { Content = "Bỏ qua phiên bản này", Margin = new Thickness(4), Padding = new Thickness(12, 8, 12, 8) };
        var action = new Button { Content = vm.GitHubApplyEnabled ? "Khởi động lại để cập nhật" : "Cập nhật", Margin = new Thickness(4), Style = (Style)owner.FindResource("PrimaryButton") };
        buttons.Children.Add(defer); buttons.Children.Add(skip); buttons.Children.Add(action);
        defer.Click += (_, _) => { vm.DeferUpdate(false); Close(); };
        skip.Click += (_, _) => { vm.DeferUpdate(true); Close(); };
        vm.PropertyChanged += OnProgress;
        void OnProgress(object? sender, System.ComponentModel.PropertyChangedEventArgs e)
        {
            if (e.PropertyName == nameof(vm.OfferedVersion) && !string.IsNullOrWhiteSpace(vm.OfferedVersion))
                versionLabel.Text = $"Phiên bản mới {vm.OfferedVersion} • Hiện tại {vm.CurrentVersionDisplay}";
            if (e.PropertyName == nameof(vm.UpdateNotes))
                notes.Content = new TextBlock { Text = vm.UpdateNotes, TextWrapping = TextWrapping.Wrap };
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
            action.Content = vm.GitHubApplyEnabled ? "Khởi động lại để cập nhật" : "Thử lại";
            action.IsEnabled = true; skip.IsEnabled = true; defer.Content = "Để sau";
        };
        Closing += (_, _) => { vm.DeferUpdate(false); if (vm.DownloadingUpdate) vm.CancelUpdateDownload(); };
        Closed += (_, _) => vm.PropertyChanged -= OnProgress;
        Content = grid;
    }
}
