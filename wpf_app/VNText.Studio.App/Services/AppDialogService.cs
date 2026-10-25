using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace VNText.Studio.App.Services;

internal static class AppDialogService
{
    /// <summary>Result when a dialog is dismissed without an explicit button (X, Esc, Alt+F4).</summary>
    internal static MessageBoxResult SafeDismissResult(MessageBoxButton buttons) => buttons switch
    {
        MessageBoxButton.YesNo => MessageBoxResult.No,
        MessageBoxButton.YesNoCancel or MessageBoxButton.OKCancel => MessageBoxResult.Cancel,
        _ => MessageBoxResult.OK,
    };

    /// <summary>Button labels with (label, result, primary, default), in footer order.</summary>
    internal static IReadOnlyList<(string Label, MessageBoxResult Result, bool Primary, bool Default)> ButtonSpecs(MessageBoxButton buttons) => buttons switch
    {
        MessageBoxButton.YesNo => new[]
        {
            ("Không", MessageBoxResult.No, false, true),
            ("Có", MessageBoxResult.Yes, true, false),
        },
        MessageBoxButton.YesNoCancel => new[]
        {
            ("Hủy", MessageBoxResult.Cancel, false, true),
            ("Bỏ thay đổi", MessageBoxResult.No, false, false),
            ("Lưu", MessageBoxResult.Yes, true, false),
        },
        MessageBoxButton.OKCancel => new[]
        {
            ("Hủy", MessageBoxResult.Cancel, false, false),
            ("OK", MessageBoxResult.OK, true, true),
        },
        _ => new[] { ("Đóng", MessageBoxResult.OK, true, true) },
    };

    internal static AppDialogWindow Build(
        string message,
        string caption,
        MessageBoxButton buttons,
        MessageBoxImage image,
        Window? owner,
        Action<MessageBoxResult> setResult)
    {
        var app = Application.Current;
        var ink = app?.TryFindResource("InkBrush") as Brush ?? Brushes.Black;
        var muted = app?.TryFindResource("MutedBrush") as Brush ?? Brushes.DimGray;
        var accentKey = image == MessageBoxImage.Error ? "ErrorBrush"
            : image == MessageBoxImage.Warning ? "WarningBrush"
            : "BlueBrush";
        var accent = app?.TryFindResource(accentKey) as Brush ?? Brushes.SteelBlue;
        var body = new StackPanel();
        body.Children.Add(new Border { Height = 3, Width = 40, HorizontalAlignment = HorizontalAlignment.Left, CornerRadius = new CornerRadius(2), Background = accent, Margin = new Thickness(0, 0, 0, 12) });
        body.Children.Add(new TextBox
        {
            Text = message,
            IsReadOnly = true,
            TextWrapping = TextWrapping.Wrap,
            BorderThickness = new Thickness(0),
            Background = Brushes.Transparent,
            Foreground = ink,
            FontSize = 14,
            BorderBrush = Brushes.Transparent,
            CaretBrush = muted,
            IsTabStop = true,
        });
        var dialog = new AppDialogWindow(owner, caption, body);
        dialog.OnDismiss = () => setResult(SafeDismissResult(buttons));
        foreach (var (label, result, primary, isDefault) in ButtonSpecs(buttons))
        {
            var captured = result;
            dialog.AddButton(label, () => setResult(captured), primary, isDefault);
        }
        return dialog;
    }

    public static MessageBoxResult Show(
        string message,
        string caption,
        MessageBoxButton buttons = MessageBoxButton.OK,
        MessageBoxImage image = MessageBoxImage.None,
        Window? owner = null)
    {
        var app = Application.Current;
        owner ??= app?.Windows.OfType<Window>().FirstOrDefault(window => window.IsVisible && window.IsActive)
            ?? (app?.MainWindow is { IsVisible: true } mainWindow ? mainWindow : null);
        var result = MessageBoxResult.None;
        var dialog = Build(message, caption, buttons, image, owner, value => result = value);
        dialog.ShowDialog();
        return result == MessageBoxResult.None ? SafeDismissResult(buttons) : result;
    }
}
