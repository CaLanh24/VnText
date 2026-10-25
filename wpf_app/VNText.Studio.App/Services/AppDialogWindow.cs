using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;

namespace VNText.Studio.App.Services;

/// <summary>
/// Shared shell for app-owned modal dialogs: transparent rounded card, header with a custom close X,
/// scrolling body, footer with rounded buttons, dim overlay over the owner, Esc / X / Alt+F4 routed
/// to one safe dismiss action, and focus restored to the previously focused owner element.
/// Native OS file/folder pickers are not built with this shell.
/// </summary>
internal sealed class AppDialogWindow : Window
{
    internal const double CardMargin = 18;
    /// <summary>Shared modal card radius; Update/Journal/Glossary shells use the same value.</summary>
    internal const double CardRadius = 18;
    private readonly StackPanel _buttons = new() { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right };
    private readonly Button _close;
    private readonly ScrollViewer _bodyScroll;
    private readonly Window? _shellOwner;
    private readonly IInputElement? _previousFocus;
    private Panel? _ownerPanel;
    private Border? _overlay;
    private Effect? _previousEffect;
    private bool _dismissRaised;
    private UIElement? _wrappedOriginal;
    private Panel? _wrappedHost;

    /// <summary>Invoked once when the dialog is closed without an explicit button (X, Esc, Alt+F4).</summary>
    internal Action? OnDismiss { get; set; }
    internal Button CloseButton => _close;
    internal ScrollViewer BodyScroll => _bodyScroll;
    internal Panel ButtonPanel => _buttons;

    internal AppDialogWindow(Window? owner, string title, UIElement body, double width = 480)
    {
        _shellOwner = owner;
        _previousFocus = owner is null ? null : Keyboard.FocusedElement;
        Title = title;
        Width = width + CardMargin * 2;
        SizeToContent = SizeToContent.Height;
        WindowStyle = WindowStyle.None;
        ResizeMode = ResizeMode.NoResize;
        AllowsTransparency = true;
        Background = Brushes.Transparent;
        ShowInTaskbar = false;
        WindowStartupLocation = owner is null ? WindowStartupLocation.CenterScreen : WindowStartupLocation.CenterOwner;
        if (owner is not null)
        {
            Owner = owner;
            FontFamily = owner.FontFamily;
        }
        FontSize = 14;
        var area = SystemParameters.WorkArea;
        var heightBound = owner is { ActualHeight: > 0 } ? owner.ActualHeight - 24 : area.Height - 48;
        MaxHeight = Math.Max(240, Math.Min(heightBound, area.Height - 24));
        MaxWidth = Math.Max(320, (owner is { ActualWidth: > 0 } ? owner.ActualWidth : area.Width) - 24);
        KeyboardNavigation.SetTabNavigation(this, KeyboardNavigationMode.Cycle);
        KeyboardNavigation.SetControlTabNavigation(this, KeyboardNavigationMode.Cycle);

        Brush Res(string key, Brush fallback) => Application.Current?.TryFindResource(key) as Brush ?? fallback;
        var ink = Res("InkBrush", Brushes.Black);
        Foreground = ink;
        var card = new Border
        {
            Margin = new Thickness(CardMargin),
            CornerRadius = new CornerRadius(CardRadius),
            Background = Res("SurfaceBrush", Brushes.White),
            Effect = new DropShadowEffect { BlurRadius = 32, ShadowDepth = 9, Opacity = .25 },
        };
        var grid = new Grid();
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        grid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
        grid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
        card.Child = grid;

        var header = new Grid { Margin = new Thickness(24, 14, 18, 14) };
        header.ColumnDefinitions.Add(new ColumnDefinition());
        header.ColumnDefinitions.Add(new ColumnDefinition { Width = GridLength.Auto });
        var heading = new TextBlock
        {
            Text = title, FontSize = 18, FontWeight = FontWeights.SemiBold, Foreground = ink,
            VerticalAlignment = VerticalAlignment.Center, TextWrapping = TextWrapping.Wrap,
        };
        header.Children.Add(heading);
        _close = new Button
        {
            Content = new TextBlock { Text = "×", FontSize = 20, VerticalAlignment = VerticalAlignment.Center },
            ToolTip = "Đóng (Esc)",
            Style = Application.Current?.TryFindResource("DialogCloseButton") as Style,
        };
        AutomationProperties.SetName(_close, "Đóng " + title);
        _close.Click += (_, _) => Dismiss();
        Grid.SetColumn(_close, 1);
        header.Children.Add(_close);
        grid.Children.Add(new Border
        {
            Child = header,
            BorderBrush = Res("LineBrush", Brushes.LightGray),
            BorderThickness = new Thickness(0, 0, 0, 1),
        });

        _bodyScroll = new ScrollViewer
        {
            Content = new Border { Padding = new Thickness(26, 18, 26, 18), Child = body },
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled,
            Style = Application.Current?.TryFindResource("ContentPanelScrollViewer") as Style,
        };
        Grid.SetRow(_bodyScroll, 1);
        grid.Children.Add(_bodyScroll);

        var footer = new Border
        {
            Background = Res("SubtlePanelBrush", Brushes.WhiteSmoke),
            BorderBrush = Res("LineBrush", Brushes.LightGray),
            BorderThickness = new Thickness(0, 1, 0, 0),
            CornerRadius = new CornerRadius(0, 0, CardRadius, CardRadius),
            Padding = new Thickness(22, 12, 22, 12),
            Child = _buttons,
        };
        Grid.SetRow(footer, 2);
        grid.Children.Add(footer);
        Content = card;

        PreviewKeyDown += (_, e) =>
        {
            if (e.Key == Key.Escape) { e.Handled = true; Dismiss(); }
        };
        Closing += (_, _) => RaiseDismissIfNeeded();
        Loaded += (_, _) => { AttachOverlay(); FocusDefault(); };
        Closed += (_, _) => DetachOverlay();
    }

    /// <summary>Adds a footer button; clicking it is an explicit choice (no dismiss callback).</summary>
    internal Button AddButton(string label, Action onClick, bool primary = false, bool isDefault = false)
    {
        var button = new Button
        {
            Content = label,
            MinWidth = 84,
            Margin = new Thickness(_buttons.Children.Count == 0 ? 0 : 8, 0, 0, 0),
            Padding = new Thickness(14, 7, 14, 7),
            Style = Application.Current?.TryFindResource(primary ? "PrimaryButton" : "OutlineButton") as Style,
            IsDefault = isDefault,
        };
        AutomationProperties.SetName(button, label);
        button.Click += (_, _) => { _dismissRaised = true; onClick(); Close(); };
        _buttons.Children.Add(button);
        return button;
    }

    /// <summary>Close without an explicit choice: runs the safe default exactly once.</summary>
    internal void Dismiss()
    {
        RaiseDismissIfNeeded();
        Close();
    }

    private void RaiseDismissIfNeeded()
    {
        if (_dismissRaised) return;
        _dismissRaised = true;
        OnDismiss?.Invoke();
    }

    private void FocusDefault()
    {
        var target = _buttons.Children.OfType<Button>().FirstOrDefault(b => b.IsDefault)
            ?? _buttons.Children.OfType<Button>().LastOrDefault();
        (target ?? _close).Focus();
    }

    private void AttachOverlay()
    {
        if (_shellOwner is null) return;
        var panel = _shellOwner.Content as Panel;
        if (panel is null && _shellOwner.Content is UIElement original)
        {
            // Owner is itself a shell (Update/Journal/another dialog) whose root is a card Border:
            // host the card and the dim layer in a Grid so nested popups dim their owner too.
            _wrappedOriginal = original;
            _shellOwner.Content = null;
            panel = new Grid();
            panel.Children.Add(original);
            _wrappedHost = panel;
            _shellOwner.Content = panel;
        }
        if (panel is null) return;
        _ownerPanel = panel;
        _previousEffect = panel.Effect;
        _overlay = new Border { Background = new SolidColorBrush(Color.FromArgb(140, 24, 31, 45)), IsHitTestVisible = false };
        if (_wrappedOriginal is Border ownerCard)
        {
            // Transparent shell owner: dim only the visible rounded card, not the whole transparent window.
            _overlay.Margin = ownerCard.Margin;
            _overlay.CornerRadius = ownerCard.CornerRadius;
        }
        else
        {
            panel.Effect = new BlurEffect { Radius = 8 };
        }
        Grid.SetColumnSpan(_overlay, 2);
        Grid.SetRowSpan(_overlay, Math.Max(1, (panel as Grid)?.RowDefinitions.Count ?? 1));
        Panel.SetZIndex(_overlay, int.MaxValue);
        panel.Children.Add(_overlay);
    }

    private void DetachOverlay()
    {
        if (_ownerPanel is not null)
        {
            if (_overlay is not null) _ownerPanel.Children.Remove(_overlay);
            _ownerPanel.Effect = _previousEffect;
            if (_wrappedOriginal is not null && ReferenceEquals(_ownerPanel, _wrappedHost) && _shellOwner is not null)
            {
                _wrappedHost.Children.Remove(_wrappedOriginal);
                _shellOwner.Content = _wrappedOriginal;
            }
        }
        _overlay = null;
        if (_shellOwner is { IsVisible: true })
        {
            _shellOwner.Activate();
            if (_previousFocus is not null) Keyboard.Focus(_previousFocus);
        }
    }
}
