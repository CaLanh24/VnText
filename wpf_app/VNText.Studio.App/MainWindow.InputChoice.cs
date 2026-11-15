using System.Windows;
using System.Windows.Controls;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App;

public partial class MainWindow
{
    /// <summary>N8: the source "Chọn..." button offers the two supported routes explicitly; each picker is a single step and Cancel/Escape ends it.</summary>
    private void ShowInputChoiceMenu(object? anchor)
    {
        if (DataContext is not MainViewModel vm || anchor is not FrameworkElement target) return;
        var menu = BuildInputChoiceMenu(vm, target);
        menu.IsOpen = true;
    }

    internal static ContextMenu BuildInputChoiceMenu(MainViewModel vm, FrameworkElement target)
    {
        var menu = new ContextMenu { PlacementTarget = target, Placement = System.Windows.Controls.Primitives.PlacementMode.Bottom };
        menu.Items.Add(new MenuItem { Header = UiText.Translate("Chọn thư mục game…"), Command = vm.ChooseInputCommand });
        menu.Items.Add(new MenuItem { Header = UiText.Translate("Chọn file asset / bundle…"), Command = vm.ChooseInputAssetCommand });
        return menu;
    }
}
