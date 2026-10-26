using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using VNText.Studio.App.ViewModels;
using VNText.Studio.App.Services;

namespace VNText.Studio.App;

public partial class MainWindow : Window
{
    private bool _layoutInitialized;
    private AppTray? _tray;
    private bool _explicitExit;
    private bool _allowDirtyExitOnce;
    private bool _closeDecisionPending;
    private bool _pendingUpdateOffer;

    public MainWindow() : this(null) { }

    public IUpdatePresentation UpdatePresentation { get; }
    private UpdateWindow? _updateDialog;
    private readonly bool _presentationFixture;

    internal MainWindow(MainViewModel? viewModel, IUpdatePresentation? presentation = null)
    {
        var currentVm = viewModel ?? new MainViewModel();
        DataContext = currentVm;
        UpdatePresentation = presentation ?? new ViewModelUpdatePresentation(currentVm);
        _presentationFixture = presentation?.IsTestFixture == true;
        UiText.Install(); UiText.SetLanguage(currentVm.Language);
        InitializeComponent();
        if (DataContext is MainViewModel vm)
        {
            vm.CompletionRequested += OnCompletionRequested;
            vm.ExitAfterTaskRequested += OnExitAfterTaskRequested;
            vm.JournalRequested += () => new JournalWindow(this,vm).ShowDialog();
            vm.RestoreWindow(this);
            WindowState = !_presentationFixture && vm.StartMinimized ? WindowState.Minimized : WindowState.Maximized;
            UpdatePresentation.OfferRequested += OpenUpdateDialog;
            vm.ReleaseNotesRequested += OpenReleaseNotes;
            vm.UpdateSuccessRequested += version => ShowUpdateDialog(false, version);
            if (!_presentationFixture) Loaded += async (_, _) => await vm.CheckUpdatesOnStartupAsync();
            void ApplyScale()
            {
                if (Content is FrameworkElement content)
                    content.LayoutTransform = new ScaleTransform(vm.UiScale, vm.UiScale);
            }
            var applyingPreferences = false;
            void ApplyPreferences()
            {
                if (applyingPreferences) return;
                applyingPreferences = true;
                try { UiText.SetLanguage(vm.Language); UiAppearance.Apply(vm.Theme, vm.BackgroundStrength); UiText.Apply(this); vm.RefreshLocalizedOptions(); }
                finally { applyingPreferences = false; }
            }
            ApplyScale(); ApplyPreferences();
            Activated += (_, _) =>
            {
                if (_pendingUpdateOffer && WindowState != WindowState.Minimized)
                { _pendingUpdateOffer=false; Dispatcher.BeginInvoke(new Action(OpenUpdateDialog)); }
            };
            Loaded += (_, _) =>
            {
                ApplyPreferences();
                Dispatcher.BeginInvoke(new Action(() => UiText.Apply(this)), System.Windows.Threading.DispatcherPriority.ContextIdle);
                if (!_presentationFixture && vm.StartMinimized && vm.CloseAction == "tray") HideToTray();
            };
            void HideToTray()
            {
                try { _tray ??= new AppTray(this, () => { _explicitExit=true; Close(); }); if (!_tray.Hide()) { Show(); WindowState=WindowState.Minimized; } }
                catch { Show(); WindowState=WindowState.Minimized; }
            }
            vm.PropertyChanged += (_, e) =>
            {
                if (e.PropertyName == nameof(vm.UiScale)) ApplyScale();
                if (e.PropertyName is nameof(vm.Language) or nameof(vm.Theme) or nameof(vm.BackgroundStrength)) ApplyPreferences();
                if (e.PropertyName == nameof(vm.SelectedTab)) { PageScrollViewer.ScrollToTop(); Dispatcher.BeginInvoke(new Action(() => UiText.Apply(this)), System.Windows.Threading.DispatcherPriority.ContextIdle); }
            };
            Closing += async (_, e) =>
            {
                if (_closeDecisionPending)
                {
                    e.Cancel = true;
                    return;
                }
                if (!_presentationFixture && !_explicitExit && vm.CloseAction == "tray")
                {
                    e.Cancel=true; HideToTray(); return;
                }
                if (vm.Busy)
                {
                    e.Cancel = true;
                    var cancelAndExit = AppDialogService.Show(
                        "Tác vụ đang chạy. Bạn có muốn yêu cầu hủy an toàn rồi thoát sau khi worker báo kết thúc không? Ứng dụng sẽ tiếp tục chờ nếu worker chưa dừng.",
                        "Tác vụ chưa hoàn tất", MessageBoxButton.YesNo, MessageBoxImage.Question, this);
                    if (cancelAndExit == MessageBoxResult.Yes)
                        vm.CancelAndExitCommand.Execute(null);
                    return;
                }
                if (vm.CsvEditorSaving)
                {
                    e.Cancel = true;
                    _closeDecisionPending = true;
                    try { await vm.WaitForCsvEditorSaveAsync(); }
                    finally { _closeDecisionPending = false; }
                    _ = Dispatcher.BeginInvoke(new Action(Close));
                    return;
                }
                if (vm.CsvEditorDirty && !_allowDirtyExitOnce)
                {
                    e.Cancel = true;
                    var decision = AppDialogService.Show(
                        "CSV có thay đổi chưa lưu. Chọn Lưu để kiểm tra và lưu trước khi thoát, Bỏ thay đổi để thoát và bỏ phần đang sửa, hoặc Hủy để tiếp tục làm việc.",
                        "CSV chưa lưu", MessageBoxButton.YesNoCancel, MessageBoxImage.Warning, this);
                    if (decision == MessageBoxResult.Yes)
                    {
                        _closeDecisionPending = true;
                        try
                        {
                            if (await vm.TrySaveCsvEditorForExitAsync()) CloseAfterCsvDecision();
                        }
                        finally { _closeDecisionPending = false; }
                    }
                    else if (decision == MessageBoxResult.No)
                    {
                        vm.DiscardCsvEditorChanges();
                        CloseAfterCsvDecision();
                    }
                    return;
                }
                _allowDirtyExitOnce = false;
                if (!_presentationFixture) vm.SaveWindow(this);
            };
        }

        Closed += (_, _) =>
        {
            UpdatePresentation.OfferRequested -= OpenUpdateDialog;
            currentVm.ReleaseNotesRequested -= OpenReleaseNotes;
            _tray?.Dispose();
            UpdatePresentation.Dispose();
            if (DataContext is MainViewModel closingVm)
            {
                closingVm.ExitAfterTaskRequested -= OnExitAfterTaskRequested;
                closingVm.CompletionRequested -= OnCompletionRequested;
            }
            if (DataContext is IDisposable disposable)
                disposable.Dispose();
        };
    }

    private void OpenUpdateDialog() { if (IsVisible && WindowState != WindowState.Minimized) ShowUpdateDialog(false); else _pendingUpdateOffer=true; }
    private void OpenReleaseNotes() => ShowUpdateDialog(true);

    private void CloseAfterCsvDecision()
    {
        _allowDirtyExitOnce = true;
        Dispatcher.BeginInvoke(new Action(Close));
    }

    private void OnExitAfterTaskRequested(object? sender, EventArgs e)
    {
        _explicitExit = true;
        Close();
    }
    internal void ShowUpdateDialog(bool notes, string? successVersion = null)
    {
        if (_updateDialog is not null) { _updateDialog.Activate(); return; }
        _updateDialog = new UpdateWindow(this, UpdatePresentation, notes, successVersion);
        try { _updateDialog.ShowDialog(); }
        finally { _updateDialog = null; }
    }
    private async void CheckUpdates_Click(object sender, RoutedEventArgs e) => await UpdatePresentation.CheckAsync();
    private void SidebarUpdate_Click(object sender, RoutedEventArgs e)
    {
        if (UpdatePresentation.Available) ShowUpdateDialog(false);
    }

    private void OnCompletionRequested(object? sender, CompletionNotification notification)
    {
        void Show()
        {
            if (DataContext is MainViewModel vm)
                vm.ShowCompletionToast(notification);
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
        SetResponsiveLayout(PatchPage, PatchConfigCard, PatchCheckCard, PatchLogCard);
    }

    private static void SetResponsiveLayout(Grid page, FrameworkElement primary, FrameworkElement secondary, FrameworkElement? third = null)
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
            primary.Margin = new Thickness(0, 0, 0, 24);
            secondary.Margin = new Thickness(0,0,0,third is null ? 0 : 24);
            if (third is not null)
            {
                page.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
                Grid.SetColumn(third,0); Grid.SetRow(third,2); third.Margin = new Thickness(0);
            }
            page.VerticalAlignment = VerticalAlignment.Top;
    }

    private void CsvEditorGrid_CellEditEnding(object sender, DataGridCellEditEndingEventArgs e)
    {
        if (DataContext is MainViewModel vm)
            vm.OnCsvEditorTranslationChanged(e.Row.Item as VNText.Studio.App.Models.CsvEditorRow);
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
