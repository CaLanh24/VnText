using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;

namespace VNText.Studio.App.Services;

/// <summary>
/// Wheel routing for a scrollable log nested in a scrolling page. The log consumes the wheel only while it can still move in that
/// direction; at its first/last line the same wheel step continues to the page, so the page (folder area, buttons) is always reachable.
/// A live log follows its newest line only until the user scrolls it away, and following never scrolls the page.
/// </summary>
public sealed class NestedScrollRouter
{
    private readonly FrameworkElement _host;
    private readonly Func<ScrollViewer?> _inner;
    private bool _follow = true;
    private bool _queued;

    private NestedScrollRouter(FrameworkElement host, Func<ScrollViewer?> inner)
    {
        _host = host;
        _inner = inner;
    }

    /// <summary>True while the log is pinned to its newest line.</summary>
    public bool Following => _follow;

    /// <summary>Chain the wheel of any scrollable host (list or scroll viewer) to its ancestors; returns the router for log following.</summary>
    public static NestedScrollRouter Attach(FrameworkElement host)
    {
        var router = new NestedScrollRouter(host, () => host as ScrollViewer ?? FindScrollViewer(host));
        host.PreviewMouseWheel += router.OnPreviewMouseWheel;
        // Items asking to be brought into view (selection, focus, programmatic reveal) must never drag the OUTER page along.
        host.RequestBringIntoView += (_, e) => { if (!ReferenceEquals(e.TargetObject, host)) e.Handled = true; };
        host.Loaded += (_, _) =>
        {
            var viewer = router._inner();
            if (viewer is not null) viewer.ScrollChanged += router.OnScrollChanged;
        };
        return router;
    }

    internal static ScrollViewer? FindScrollViewer(DependencyObject root)
    {
        if (root is ScrollViewer direct) return direct;
        var count = VisualTreeHelper.GetChildrenCount(root);
        for (var i = 0; i < count; i++)
        {
            var found = FindScrollViewer(VisualTreeHelper.GetChild(root, i));
            if (found is not null) return found;
        }
        return null;
    }

    private void OnPreviewMouseWheel(object sender, MouseWheelEventArgs e)
    {
        if (e.Handled) return;
        var viewer = _inner();
        if (viewer is null) return;
        var up = e.Delta > 0;
        var canMove = viewer.ScrollableHeight > 0.5 && (up ? viewer.VerticalOffset > 0.5 : viewer.VerticalOffset < viewer.ScrollableHeight - 0.5);
        if (canMove)
        {
            if (up) _follow = false;                      // the user reads history: stop following until they return to the end
            return;                                       // the log scrolls itself
        }
        // At the boundary (or nothing to scroll): hand the SAME wheel step to the page behind the log.
        e.Handled = true;
        var parent = VisualTreeHelper.GetParent(_host) as UIElement;
        if (parent is null) return;
        parent.RaiseEvent(new MouseWheelEventArgs(e.MouseDevice, e.Timestamp, e.Delta) { RoutedEvent = UIElement.MouseWheelEvent, Source = _host });
    }

    private void OnScrollChanged(object sender, ScrollChangedEventArgs e)
    {
        if (e.ExtentHeightChange != 0 || e.ViewportHeightChange != 0) return;     // growth is not a user action
        var viewer = (ScrollViewer)sender;
        if (viewer.ScrollableHeight <= 0.5) { _follow = true; return; }
        _follow = viewer.VerticalOffset >= viewer.ScrollableHeight - 0.5;         // user dragged/paged/wheeled back to the end
    }

    /// <summary>A line was appended: follow it only when pinned, scrolling the log itself and nothing else.</summary>
    public void NotifyAppended()
    {
        if (!_follow || _queued) return;
        _queued = true;
        _host.Dispatcher.BeginInvoke(new Action(() =>
        {
            _queued = false;
            if (_follow) _inner()?.ScrollToBottom();
        }), DispatcherPriority.Background);
    }

    /// <summary>The shown run changed: start at its newest line, again without touching the page.</summary>
    public void Reset()
    {
        _follow = true;
        NotifyAppended();
    }
}
