using System.Collections.ObjectModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using VNText.Studio.App.Services;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    /// <summary>Real WPF routed-wheel boundary: a virtualized log inside a scrolling page (the Extract journal layout).</summary>
    private static int RunScrollRoutingFixture()
    {
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            try
            {
                var items = new ObservableCollection<string>(Enumerable.Range(0, 500).Select(i => "line " + i));
                var list = new ListBox { Height = 200, ItemsSource = items };
                var stack = new StackPanel();
                stack.Children.Add(new Border { Height = 700 });                       // the folder/options area above the log
                stack.Children.Add(list);
                stack.Children.Add(new Border { Height = 300 });
                var outer = new ScrollViewer { Height = 300, Content = stack, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
                var router = NestedScrollRouter.Attach(list);
                var window = new Window { Width = 500, Height = 400, Content = outer, ShowInTaskbar = false, Opacity = 0 };
                window.Show();
                window.UpdateLayout();
                PumpFixture(150);
                var inner = NestedScrollRouter.FindScrollViewer(list) ?? throw new InvalidOperationException("the list has no scroll viewer");

                void Wheel(int delta)
                {
                    var preview = new MouseWheelEventArgs(Mouse.PrimaryDevice, Environment.TickCount, delta) { RoutedEvent = UIElement.PreviewMouseWheelEvent, Source = inner };
                    inner.RaiseEvent(preview);   // a real wheel starts at the deepest element under the pointer, inside the log
                    if (!preview.Handled)
                        inner.RaiseEvent(new MouseWheelEventArgs(Mouse.PrimaryDevice, Environment.TickCount, delta) { RoutedEvent = UIElement.MouseWheelEvent, Source = inner });
                    PumpFixture(60);
                }
                bool InnerAtBottom() => inner.VerticalOffset >= inner.ScrollableHeight - 0.5;

                outer.ScrollToVerticalOffset(outer.ScrollableHeight);
                inner.ScrollToBottom();
                PumpFixture(100);
                Require(InnerAtBottom() && inner.ScrollableHeight > 100, "the log starts pinned at its newest line");
                var pageOffset = outer.VerticalOffset;
                Require(pageOffset > 300, "the page is scrolled down to the log");

                // 1) wheel up while the log can still scroll up: the LOG scrolls, the page stays, following stops.
                var innerBefore = inner.VerticalOffset;
                Wheel(120);
                Require(inner.VerticalOffset < innerBefore, "wheel up scrolls the log back through its history");
                Require(Math.Abs(outer.VerticalOffset - pageOffset) < 0.5, "the page did not move while the log could scroll");
                Require(!router.Following, "the user scrolled away, so the log stops following");

                // 2) at the log's FIRST line the same wheel step reaches the page: the folder area is reachable by wheel.
                inner.ScrollToTop();
                PumpFixture(80);
                Wheel(120);
                Require(outer.VerticalOffset < pageOffset - 1, "at the log's top the wheel continues to the page (up toward the folder area)");
                Require(inner.VerticalOffset < 0.5, "the log stayed at its top");

                // 3) at the log's LAST line wheel down reaches the page as well.
                outer.ScrollToVerticalOffset(200);
                PumpFixture(60);
                inner.ScrollToBottom();
                PumpFixture(80);
                var midPage = outer.VerticalOffset;
                Wheel(-120);
                Require(outer.VerticalOffset > midPage + 1, "at the log's end wheel down continues to the page");
                Require(InnerAtBottom(), "the log stayed at its end");

                // 4) following: appended lines are followed ONLY inside the log and NEVER move the page.
                outer.ScrollToVerticalOffset(pageOffset);
                PumpFixture(60);
                router.Reset();
                PumpFixture(120);
                var pinnedPage = outer.VerticalOffset;
                for (var i = 0; i < 50; i++) items.Add("live " + i);
                router.NotifyAppended();
                PumpFixture(200);
                Require(InnerAtBottom(), "a pinned log follows the newest appended line");
                Require(Math.Abs(outer.VerticalOffset - pinnedPage) < 0.5, "following never pulls the outer page");

                // 5) the user scrolls away mid-run: appends no longer steal the scroll position.
                Wheel(120);
                var reading = inner.VerticalOffset;
                for (var i = 0; i < 50; i++) items.Add("more " + i);
                router.NotifyAppended();
                PumpFixture(200);
                Require(!InnerAtBottom() && Math.Abs(inner.VerticalOffset - reading) < 0.5, "an appended burst does not scroll away from what the user is reading");
                Require(Math.Abs(outer.VerticalOffset - pinnedPage) < 0.5, "the page stays where the user left it");

                // 6) returning to the end resumes following.
                inner.ScrollToBottom();
                PumpFixture(120);
                for (var i = 0; i < 10; i++) items.Add("resumed " + i);
                router.NotifyAppended();
                PumpFixture(200);
                Require(router.Following && InnerAtBottom(), "back at the end the log follows again");

                // 7) every line stays reachable (virtualized, nothing evicted)
                Require(items.Count == 610 && (string)items[0] == "line 0", "the full history is still in the list");
                inner.ScrollToTop();
                PumpFixture(100);
                Require(inner.VerticalOffset < 0.5, "the very first line is reachable by scrolling back");
                window.Close();
                Console.WriteLine("WPF scroll routing fixture: PASS");
                exitCode = 0;
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        return exitCode;
    }
}
