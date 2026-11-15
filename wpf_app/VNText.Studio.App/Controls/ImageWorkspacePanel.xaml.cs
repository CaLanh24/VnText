using System.Windows;
using System.Windows.Controls;
using VNText.Studio.App.Models;

namespace VNText.Studio.App.Controls;

/// <summary>Text-in-image workspace (OCR, review/approve, render, delivery, install); bound to MainViewModel.</summary>
public partial class ImageWorkspacePanel : UserControl
{
    public ImageWorkspacePanel() => InitializeComponent();

    private static readonly string[] NumericFields = ["RegionXBox", "RegionYBox", "RegionWidthBox", "RegionHeightBox", "RegionFontBox", "DonorXBox", "DonorYBox"];

    /// <summary>U3: a numeric box whose text the rule rejected shows an INVALID DRAFT while the review model keeps its last valid number.  Nothing may save, render, package, install
    /// or approve on that stale value, so the VM is told whether any field of the form currently has an error; the state is read from the live controls (never from
    /// remembered events), so a corrected value, another region, a reload or an unload clears it without a stale global block.</summary>
    private void OnRegionDraftValidationError(object sender, System.Windows.Controls.ValidationErrorEventArgs e) => UpdateDraftState();
    private void OnRegionFormDataContextChanged(object sender, DependencyPropertyChangedEventArgs e)
    {
        UpdateDraftState();
        Dispatcher.BeginInvoke(new Action(UpdateDraftState), System.Windows.Threading.DispatcherPriority.DataBind);   // after the rebinding has cleared the old errors
    }
    private void UpdateDraftState()
    {
        if (DataContext is not ViewModels.MainViewModel vm) return;
        vm.ImageDraftInvalid = NumericFields.Any(name => FindName(name) is TextBox box && System.Windows.Controls.Validation.GetHasError(box));
    }

    /// <summary>The background mode is one explicit human choice: the radio only reports the click, the region applies it (and drops its approval).
    /// IsChecked is one-way, so loading or selecting a region never lets the group uncheck, pick or normalise the stored flags.</summary>
    private void OnBackgroundModeClick(object sender, RoutedEventArgs e)
    {
        if (sender is not FrameworkElement { DataContext: ImageTextRegion region } box) return;
        region.ChooseBackgroundMode(box.Name switch
        {
            "FlatModeBox" => RegionBackgroundMode.Flat,
            "TransparentModeBox" => RegionBackgroundMode.Transparent,
            "SolidModeBox" => RegionBackgroundMode.Solid,
            _ => RegionBackgroundMode.Clone,
        });
    }
}
