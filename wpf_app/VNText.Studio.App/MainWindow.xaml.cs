using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App;

public partial class MainWindow : Window
{
    private bool? _compactLayout;

    public MainWindow()
    {
        InitializeComponent();
        if (DataContext is MainViewModel vm)
            vm.CompletionRequested += OnCompletionRequested;

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

        var compact = ActualWidth < 1180;
        if (_compactLayout == compact)
            return;

        _compactLayout = compact;
        SetResponsiveLayout(ExtractPage, ExtractConfigCard, ExtractLogCard, compact);
        SetResponsiveLayout(TranslatePage, TranslateConfigCard, TranslateLogCard, compact);
        SetResponsiveLayout(PatchPage, PatchConfigCard, PatchCheckCard, compact);
    }

    private static void SetResponsiveLayout(Grid page, FrameworkElement primary, FrameworkElement secondary, bool compact)
    {
        page.ColumnDefinitions.Clear();
        page.RowDefinitions.Clear();

        if (compact)
        {
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
        else
        {
            page.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1.06, GridUnitType.Star) });
            page.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(0.94, GridUnitType.Star) });
            page.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            Grid.SetColumn(primary, 0);
            Grid.SetRow(primary, 0);
            Grid.SetColumn(secondary, 1);
            Grid.SetRow(secondary, 0);
            primary.Margin = new Thickness(0, 0, 10, 0);
            secondary.Margin = new Thickness(10, 0, 0, 0);
            page.VerticalAlignment = VerticalAlignment.Stretch;
        }
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
