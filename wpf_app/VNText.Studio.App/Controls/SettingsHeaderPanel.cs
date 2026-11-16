using System.Windows;
using System.Windows.Controls;

namespace VNText.Studio.App.Controls;

/// <summary>
/// Settings page header: [title] [centred tab strip] [status cluster].  The cluster is allocated its DESIRED width (content + padding + margin) before the rest is
/// shared: while both outer slots are wide enough for their content the tab strip stays centred exactly as the former */Auto/* grid; when a slot would be too
/// small (long English badge at UI 120 % in a small window) the tab strip moves to its own centred row under the title/status row instead of overlapping or
/// clipping the badge.  Children, in order: title, tab strip, status cluster.
/// </summary>
public sealed class SettingsHeaderPanel : Panel
{
    /// <summary>Gap between the title/status row and the tab row in the fallback layout.</summary>
    private const double RowGap = 16;

    private bool _stacked;
    private Size _title, _tabs, _status;

    protected override Size MeasureOverride(Size constraint)
    {
        if (InternalChildren.Count != 3) return base.MeasureOverride(constraint);
        var infinite = new Size(double.PositiveInfinity, double.PositiveInfinity);
        foreach (UIElement child in InternalChildren) child.Measure(infinite);
        _title = InternalChildren[0].DesiredSize; _tabs = InternalChildren[1].DesiredSize; _status = InternalChildren[2].DesiredSize;
        var width = double.IsInfinity(constraint.Width) ? _title.Width + _tabs.Width + _status.Width : constraint.Width;
        _stacked = Stacked(width);
        var height = _stacked ? Math.Max(_title.Height, _status.Height) + RowGap + _tabs.Height : Math.Max(_title.Height, Math.Max(_tabs.Height, _status.Height));
        return new Size(width, height);
    }

    protected override Size ArrangeOverride(Size arrange)
    {
        if (InternalChildren.Count != 3) return base.ArrangeOverride(arrange);
        var width = arrange.Width; var stacked = Stacked(width);
        if (stacked)
        {
            var top = Math.Max(_title.Height, _status.Height);
            InternalChildren[0].Arrange(new Rect(0, (top - _title.Height) / 2, Math.Min(_title.Width, width), _title.Height));
            InternalChildren[2].Arrange(new Rect(Math.Max(0, width - _status.Width), (top - _status.Height) / 2, Math.Min(_status.Width, width), _status.Height));
            InternalChildren[1].Arrange(new Rect(Math.Max(0, (width - _tabs.Width) / 2), top + RowGap, Math.Min(_tabs.Width, width), _tabs.Height));
        }
        else
        {
            var row = Math.Max(_title.Height, Math.Max(_tabs.Height, _status.Height));
            InternalChildren[0].Arrange(new Rect(0, (row - _title.Height) / 2, _title.Width, _title.Height));
            InternalChildren[1].Arrange(new Rect((width - _tabs.Width) / 2, (row - _tabs.Height) / 2, _tabs.Width, _tabs.Height));
            InternalChildren[2].Arrange(new Rect(width - _status.Width, (row - _status.Height) / 2, _status.Width, _status.Height));
        }
        return arrange;
    }

    /// <summary>Enough room = each outer slot ((width - tabs) / 2) holds its desired content; otherwise stack.</summary>
    private bool Stacked(double width) => (width - _tabs.Width) / 2 < Math.Max(_title.Width, _status.Width);
}
