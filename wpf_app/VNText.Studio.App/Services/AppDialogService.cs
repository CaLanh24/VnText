using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace VNText.Studio.App.Services;

internal static class AppDialogService
{
    public static MessageBoxResult Show(
        string message,
        string caption,
        MessageBoxButton buttons = MessageBoxButton.OK,
        MessageBoxImage image = MessageBoxImage.None,
        Window? owner = null)
    {
        var app = Application.Current;
        var ink = app?.TryFindResource("InkBrush") as Brush ?? Brushes.Black;
        var muted = app?.TryFindResource("MutedBrush") as Brush ?? Brushes.DimGray;
        var surface = app?.TryFindResource("SurfaceBrush") as Brush ?? Brushes.White;
        var line = app?.TryFindResource("LineBrush") as Brush ?? Brushes.LightGray;
        var accentKey = image == MessageBoxImage.Error ? "ErrorBrush"
            : image == MessageBoxImage.Warning ? "WarningBrush"
            : "BlueBrush";
        var accent = app?.TryFindResource(accentKey) as Brush ?? Brushes.SteelBlue;
        var result = MessageBoxResult.None;
        Action<MessageBoxResult> setResult = value => result = value;
        var content = BuildContent(message, caption, buttons, ink, muted, line, accent, setResult);
        var dialog = new Window
        {
            Title = caption,
            Width = 480,
            MinWidth = 360,
            SizeToContent = SizeToContent.Height,
            MaxHeight = 640,
            WindowStartupLocation = owner is null ? WindowStartupLocation.CenterScreen : WindowStartupLocation.CenterOwner,
            ResizeMode = ResizeMode.NoResize,
            ShowInTaskbar = false,
            Background = surface,
            Foreground = ink,
            Content = content,
        };
        if (owner is not null)
            dialog.Owner = owner;
        dialog.Closing += (_, _) =>
        {
            if (result != MessageBoxResult.None)
                return;
            result = buttons switch
            {
                MessageBoxButton.YesNo => MessageBoxResult.No,
                MessageBoxButton.YesNoCancel or MessageBoxButton.OKCancel => MessageBoxResult.Cancel,
                _ => MessageBoxResult.OK,
            };
        };
        dialog.KeyDown += (_, e) =>
        {
            if (e.Key == System.Windows.Input.Key.Escape)
            {
                setResult(MessageBoxResult.Cancel);
                dialog.Close();
            }
        };
        dialog.ShowDialog();
        return result;
    }

    private static UIElement BuildContent(
        string message,
        string caption,
        MessageBoxButton buttons,
        Brush ink,
        Brush muted,
        Brush line,
        Brush accent,
        Action<MessageBoxResult> setResult)
    {
        var root = new StackPanel { Margin = new Thickness(22) };
        root.Children.Add(new Border { Height = 3, Background = accent, Margin = new Thickness(0, 0, 0, 16) });
        var title = new TextBlock
        {
            Text = caption,
            FontSize = 17,
            FontWeight = FontWeights.SemiBold,
            Foreground = ink,
            Margin = new Thickness(0, 0, 0, 12),
        };
        root.Children.Add(title);
        var body = new TextBox
        {
            Text = message,
            IsReadOnly = true,
            TextWrapping = TextWrapping.Wrap,
            AcceptsReturn = true,
            BorderThickness = new Thickness(0),
            Background = Brushes.Transparent,
            Foreground = ink,
            FontSize = 14,
            BorderBrush = Brushes.Transparent,
            CaretBrush = muted,
            MaxHeight = 420,
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            IsTabStop = true,
        };
        root.Children.Add(body);
        root.Children.Add(new Border { Height = 1, Background = line, Margin = new Thickness(0, 18, 0, 12) });
        var actions = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
        root.Children.Add(actions);

        void Add(string label, MessageBoxResult result, bool primary = false)
        {
            var button = new Button
            {
                Content = label,
                MinWidth = 84,
                Margin = new Thickness(8, 0, 0, 0),
                Padding = new Thickness(14, 7, 14, 7),
                Style = Application.Current?.TryFindResource(primary ? "PrimaryButton" : "OutlineButton") as Style,
            };
            button.Click += (_, _) =>
            {
                setResult(result);
                Window.GetWindow(button)?.Close();
            };
            actions.Children.Add(button);
        }

        if (buttons == MessageBoxButton.YesNo)
        {
            Add("Không", MessageBoxResult.No);
            Add("Có", MessageBoxResult.Yes, true);
        }
        else if (buttons == MessageBoxButton.YesNoCancel)
        {
            Add("Hủy", MessageBoxResult.Cancel);
            Add("Bỏ thay đổi", MessageBoxResult.No);
            Add("Lưu", MessageBoxResult.Yes, true);
        }
        else if (buttons == MessageBoxButton.OKCancel)
        {
            Add("Hủy", MessageBoxResult.Cancel);
            Add("OK", MessageBoxResult.OK, true);
        }
        else
        {
            Add("Đóng", MessageBoxResult.OK, true);
        }
        return root;
    }
}
