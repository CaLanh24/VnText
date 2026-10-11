using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App;

public partial class MainWindow : Window
{
    private bool _layoutInitialized;

    public MainWindow() : this(null) { }

    internal MainWindow(MainViewModel? viewModel)
    {
        DataContext = viewModel ?? new MainViewModel();
        InitializeComponent();
        if (DataContext is MainViewModel vm)
        {
            vm.CompletionRequested += OnCompletionRequested;
            vm.RestoreWindow(this);
            UpdateWindow? updateWindow = null;
            vm.UpdatePopupRequested += () =>
            {
                if (updateWindow is not null) { updateWindow.Activate(); return; }
                updateWindow = new UpdateWindow(this, vm);
                updateWindow.Closed += (_, _) => updateWindow = null;
                updateWindow.Show();
            };
            vm.UpdateSuccessRequested += version => new UpdateWindow(this, vm, version).Show();
            Loaded += async (_, _) => await vm.CheckUpdatesOnStartupAsync();
            void ApplyScale()
            {
                if (Content is FrameworkElement content)
                    content.LayoutTransform = new ScaleTransform(vm.UiScale, vm.UiScale);
            }
            ApplyScale();
            vm.PropertyChanged += (_, e) =>
            {
                if (e.PropertyName == nameof(vm.UiScale)) ApplyScale();
                if (e.PropertyName == nameof(vm.SelectedTab)) PageScrollViewer.ScrollToTop();
            };
            Closing += (_, e) =>
            {
                if (vm.CsvEditorDirty || vm.Busy)
                {
                    MessageBox.Show(this, "Hãy hoàn tất hoặc hủy tác vụ và lưu CSV trước khi đóng ứng dụng.", "Công việc chưa hoàn tất");
                    e.Cancel = true;
                    return;
                }
                vm.SaveWindow(this);
            };
        }

        Closed += (_, _) =>
        {
            if (DataContext is MainViewModel currentVm)
                currentVm.CompletionRequested -= OnCompletionRequested;
            if (DataContext is IDisposable disposable)
                disposable.Dispose();
        };
    }

    private void OnCompletionRequested(object? sender, CompletionNotification notification)
    {
        void Show()
        {
            MessageBox.Show(
                this,
                notification.Message,
                notification.Title,
                MessageBoxButton.OK,
                notification.Kind switch
                {
                    "error" => MessageBoxImage.Error,
                    "warning" => MessageBoxImage.Warning,
                    "info" => MessageBoxImage.Information,
                    _ => MessageBoxImage.Information,
                });
        }

        if (Dispatcher.CheckAccess())
            Show();
        else
            Dispatcher.BeginInvoke(Show);
    }

    private void MainWindow_SizeChanged(object sender, SizeChangedEventArgs e)
    {
        if (ActualWidth <= 0)
            return;

        if (_layoutInitialized)
            return;
        _layoutInitialized = true;
        SetResponsiveLayout(TranslatePage, TranslateConfigCard, TranslateLogCard);
        SetResponsiveLayout(PatchPage, PatchConfigCard, PatchCheckCard);
    }

    private static void SetResponsiveLayout(Grid page, FrameworkElement primary, FrameworkElement secondary)
    {
        page.ColumnDefinitions.Clear();
        page.RowDefinitions.Clear();

            page.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            page.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            page.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            Grid.SetColumn(primary, 0);
            Grid.SetRow(primary, 0);
            Grid.SetColumn(secondary, 0);
            Grid.SetRow(secondary, 1);
            primary.Margin = new Thickness(0, 0, 0, 14);
            secondary.Margin = new Thickness(0);
            page.VerticalAlignment = VerticalAlignment.Top;
    }

    private void CsvEditorGrid_CellEditEnding(object sender, DataGridCellEditEndingEventArgs e)
    {
        if (DataContext is MainViewModel vm)
            vm.OnCsvEditorTranslationChanged();
    }

    private void CsvEditorGrid_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (sender is DataGrid grid && DataContext is MainViewModel vm)
            vm.UpdateCsvEditorSelection(grid.SelectedItems);
    }

    private void GlossaryEditButton_Click(object sender, RoutedEventArgs e)
    {
        GlossaryOverlay.Visibility = Visibility.Visible;
        Dispatcher.BeginInvoke(new Action(() => GlossaryTermTextBox.Focus()));
    }

    private void GlossaryCloseButton_Click(object sender, RoutedEventArgs e) => CloseGlossaryOverlay();

    private void GlossaryOverlay_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key != Key.Escape)
            return;
        CloseGlossaryOverlay();
        e.Handled = true;
    }

    private void GlossaryOverlay_PreviewMouseDown(object sender, MouseButtonEventArgs e)
    {
        if (ReferenceEquals(e.OriginalSource, GlossaryOverlay))
            CloseGlossaryOverlay();
    }

    private void CloseGlossaryOverlay()
    {
        GlossaryOverlay.Visibility = Visibility.Collapsed;
        GlossaryEditButton.Focus();
    }

    private void InputPathDrop(object sender, DragEventArgs e)
    {
        if (DataContext is not MainViewModel vm)
            return;
        if (!e.Data.GetDataPresent(DataFormats.FileDrop))
            return;
        var files = e.Data.GetData(DataFormats.FileDrop) as string[];
        if (files is { Length: > 0 })
            vm.SetInputPathFromDrop(files[0]);
        e.Handled = true;
    }
}
