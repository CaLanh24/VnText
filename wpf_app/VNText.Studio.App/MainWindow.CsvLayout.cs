using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App;

public partial class MainWindow
{
    // V1: the CSV table's three-row floor, measured from the REAL layout (UI scale applied, wrapped toolbars included) instead of a fixed height threshold.
    private (double w, double h, bool tight, bool open, double tools, double selection, string lang) _csvBudgetSignature;
    private double _csvToolsExtra = 150;     // what the tools cost beyond their folded bar; refreshed from a real measurement before every fold
    private bool _csvBudgetHooked;
    private (double w, double h) _csvBudgetFlipSize;
    private int _csvBudgetFlips;

    private void HookCsvLayoutBudget()
    {
        if (_csvBudgetHooked) return;
        _csvBudgetHooked = true;
        LayoutUpdated += (_, _) => UpdateCsvLayoutBudget();
    }

    private static double HeaderHeightOf(DataGrid grid)
    {
        var presenter = FindDescendant<System.Windows.Controls.Primitives.DataGridColumnHeadersPresenter>(grid);
        return presenter is { ActualHeight: > 0 } ? presenter.ActualHeight : CsvEditorLayoutBudget.SingleLineRow;
    }

    /// <summary>Height of the shortest realised row (a single-line row), so the floor follows the real cell padding, font and scale; a fallback before any row exists.</summary>
    private static double RowHeightOf(DataGrid grid)
    {
        var shortest = double.MaxValue;
        for (var i = 0; i < Math.Min(grid.Items.Count, 12); i++)
            if (grid.ItemContainerGenerator.ContainerFromIndex(i) is DataGridRow { ActualHeight: > 0 } row && row.ActualHeight < shortest) shortest = row.ActualHeight;
        // Only a row that is plausibly ONE line counts: a page of long, wrapped rows must not inflate the floor (they scroll instead).
        return shortest <= CsvEditorLayoutBudget.SingleLineRow * 1.3 ? shortest : CsvEditorLayoutBudget.SingleLineRow;
    }

    /// <summary>Tallest of the first three realised rows: the table must also be able to show ONE whole row of what it really holds (a page of long wrapped rows is never reduced to a sliver by the tools).</summary>
    private static double LeadingRowHeightOf(DataGrid grid)
    {
        var tallest = 0.0;
        for (var i = 0; i < Math.Min(grid.Items.Count, 3); i++)
            if (grid.ItemContainerGenerator.ContainerFromIndex(i) is DataGridRow { ActualHeight: > 0 } row && row.ActualHeight > tallest) tallest = row.ActualHeight;
        return tallest;
    }

    private static T? FindDescendant<T>(DependencyObject root) where T : DependencyObject
    {
        for (var i = 0; i < VisualTreeHelper.GetChildrenCount(root); i++)
        {
            var child = VisualTreeHelper.GetChild(root, i);
            if (child is T match) return match;
            if (FindDescendant<T>(child) is { } nested) return nested;
        }
        return null;
    }

    internal void UpdateCsvLayoutBudget()
    {
        if (DataContext is not MainViewModel vm || CsvEditorGrid is not { IsVisible: true } grid || !vm.CsvEditorHasDocument) return;
        var card = CsvEditorCardGrid;
        if (card.ActualHeight <= 0 || grid.ActualHeight <= 0) return;
        var signature = (Math.Round(card.ActualWidth), Math.Round(card.ActualHeight), vm.CsvToolsTight, vm.CsvToolsOpen, Math.Round(CsvToolsScroll.ActualHeight), Math.Round(CsvSelectionBar.ActualHeight) + Math.Round(RowHeightOf(grid)) * 1000, UiText.Language);
        if (signature == _csvBudgetSignature) return;
        _csvBudgetSignature = signature;

        var required = Math.Max(CsvEditorLayoutBudget.Required(HeaderHeightOf(grid), RowHeightOf(grid)), HeaderHeightOf(grid) + LeadingRowHeightOf(grid) + CsvEditorLayoutBudget.Slack);
        var viewport = grid.ActualHeight;
        // Safety net against any layout feedback: at most two fold/unfold flips for one card size; a new size starts again.
        var size = (Math.Round(card.ActualWidth), Math.Round(card.ActualHeight));
        if (size != _csvBudgetFlipSize) { _csvBudgetFlipSize = size; _csvBudgetFlips = 0; }
        var canFlip = _csvBudgetFlips < 2;
        if (!vm.CsvToolsTight)
        {
            CsvToolsScroll.MaxHeight = double.PositiveInfinity;
            if (canFlip && CsvEditorLayoutBudget.NeedsFold(viewport, required))
            {
                _csvToolsExtra = Math.Max(60, CsvToolsScroll.ActualHeight - 40);
                _csvBudgetFlips++;
                vm.SetCsvToolsTight(true);
            }
            return;
        }
        if (!vm.CsvToolsOpen)
        {
            CsvToolsScroll.MaxHeight = double.PositiveInfinity;
            if (canFlip && CsvEditorLayoutBudget.CanUnfold(viewport, required, _csvToolsExtra)) { _csvBudgetFlips++; vm.SetCsvToolsTight(false); }
            return;
        }
        // Opened by the user while tight: the tools scroll inside a cap that always leaves the table its floor.
        CsvToolsScroll.MaxHeight = CsvEditorLayoutBudget.ToolsCap(card.ActualHeight, viewport, CsvToolsScroll.ActualHeight, required);
    }
}
