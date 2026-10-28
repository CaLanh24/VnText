using System.Windows;
using System.Windows.Controls;
using System.Windows.Media.Effects;

namespace VNText.Studio.App.Services;

/// <summary>
/// Shared backdrop for an in-window modal overlay: the content behind it blurs by <see cref="AppDialogWindow.BackdropBlur"/>,
/// while the overlay and every layer at or above its z-order (toasts, dialog dim layers) stay sharp so feedback remains readable.
/// </summary>
internal static class ModalBackdrop
{
    internal static void BlurBackground(Panel root, UIElement overlay, IDictionary<UIElement, Effect?> saved)
    {
        var overlayZ = Panel.GetZIndex(overlay);
        foreach (UIElement child in root.Children)
        {
            if (ReferenceEquals(child, overlay) || Panel.GetZIndex(child) >= overlayZ || saved.ContainsKey(child)) continue;
            saved[child] = child.Effect;
            child.Effect = new BlurEffect { Radius = AppDialogWindow.BackdropBlur };
        }
    }

    internal static void Restore(IDictionary<UIElement, Effect?> saved)
    {
        foreach (var (element, effect) in saved) element.Effect = effect;
        saved.Clear();
    }
}
