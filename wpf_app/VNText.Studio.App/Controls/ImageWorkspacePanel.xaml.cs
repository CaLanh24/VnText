using System.Windows;
using System.Windows.Controls;
using VNText.Studio.App.Models;

namespace VNText.Studio.App.Controls;

/// <summary>Text-in-image workspace (OCR, review/approve, render, delivery, install); bound to MainViewModel.</summary>
public partial class ImageWorkspacePanel : UserControl
{
    public ImageWorkspacePanel() => InitializeComponent();

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
