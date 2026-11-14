namespace VNText.Studio.App.Services;

/// <summary>
/// The CSV table's height budget (V1).  Pure arithmetic over MEASURED layout values (already in the content's own units, i.e. after the interface scale),
/// so the decisions are testable without a window: the table must always be able to show its header plus three single-line rows; when the real toolbars
/// (which may have wrapped) leave less, the find/replace group folds, and an opened group is capped so the table keeps its rows.
/// </summary>
internal static class CsvEditorLayoutBudget
{
    /// <summary>Fallback height of a single-line CSV row (cell padding + one text line) used before any row is realised; the live value is measured from the grid.</summary>
    internal const double SingleLineRow = 42;
    /// <summary>Rows that must be fully visible in the viewport.</summary>
    internal const int GuaranteedRows = 3;
    /// <summary>Slack under the last guaranteed row so it is never flush with the footer.</summary>
    internal const double Slack = 4;
    /// <summary>Grow-back margin: unfold only when the folded tools would still leave this much beyond the floor (prevents flip-flopping).</summary>
    internal const double Hysteresis = 16;
    internal const double MinToolsViewport = 72;

    /// <summary>Header + three single-line rows (+ slack): the least viewport that satisfies the floor.</summary>
    internal static double Required(double headerHeight, double rowHeight) => Math.Max(headerHeight, 24) + GuaranteedRows * Math.Max(rowHeight, 24) + Slack;

    internal static bool NeedsFold(double viewportHeight, double required) => viewportHeight + 0.5 < required;

    /// <summary>True when unfolding the tools (which costs <paramref name="toolsExtra"/>) still leaves the floor plus the hysteresis margin.</summary>
    internal static bool CanUnfold(double viewportHeight, double required, double toolsExtra) => viewportHeight >= required + Math.Max(0, toolsExtra) + Hysteresis;

    /// <summary>Largest height the opened tools may take: everything the card has, minus every other chrome row, minus the table floor.  Never below a usable minimum.</summary>
    internal static double ToolsCap(double cardContentHeight, double viewportHeight, double toolsHeight, double required)
    {
        var otherChrome = cardContentHeight - viewportHeight - toolsHeight;
        return Math.Max(MinToolsViewport, cardContentHeight - otherChrome - required);
    }
}
