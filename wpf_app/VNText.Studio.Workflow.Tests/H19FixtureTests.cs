using System.IO;
using System.Windows;
using System.Windows.Controls;
using VNText.Studio.App;
using VNText.Studio.App.Controls;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    /// <summary>qa-header19: the Settings header keeps the status badge whole (desired width) next to a non-overlapping tab strip in VI/EN, Light/Dark, UI100/120, small and wide windows, with and without the cancel button.</summary>
    private static int RunH19Fixture()
    {
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            try
            {
                var root = Environment.GetEnvironmentVariable("VNTEXT_LOCALAPPDATA") ?? throw new InvalidOperationException("isolated root required");
                Require(Path.GetFullPath(root).Contains(Path.DirectorySeparatorChar + "TEST_RUN" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "the fixture needs the TEST_RUN isolated settings root");
                var app = new VNText.Studio.App.App();
                app.InitializeComponent();
                app.ShutdownMode = ShutdownMode.OnExplicitShutdown;
                var report = new List<string>();
                try
                {
                    var stackedSeen = false; var inlineSeen = false;
                    foreach (var (language, theme, scale, width, height) in new[]
                    {
                        ("en", "light", 1.2, 1055.0, 720.0), ("en", "dark", 1.2, 1055.0, 720.0), ("vi", "light", 1.2, 1055.0, 720.0), ("en", "light", 1.0, 1055.0, 720.0),
                        ("en", "dark", 1.0, 1055.0, 720.0), ("vi", "dark", 1.0, 1055.0, 720.0), ("en", "light", 1.2, 1604.0, 900.0), ("vi", "light", 1.0, 1604.0, 900.0),
                    })
                    {
                        var tag = $"{language}/{theme}/UI{scale * 100:0}/{width:0}";
                        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        vm.Language = language; vm.Theme = theme; vm.UiScale = scale;
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal; window.Width = width; window.Height = height;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1") { window.WindowStartupLocation = WindowStartupLocation.Manual; window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false; }
                        window.Show(); window.UpdateLayout(); PumpFixture(250);
                        vm.NavigateTabCommand.Execute("settings"); window.UpdateLayout(); PumpFixture(250); window.UpdateLayout();
                        foreach (var settingsTab in new[] { 0, 1, 2 })
                        foreach (var busy in new[] { false, true })
                        {
                            FindVisualChildren<TabControl>(window).First(x => x.IsVisible).SelectedIndex = settingsTab; vm.TestSetBusy(busy); window.UpdateLayout(); PumpFixture(120); window.UpdateLayout();
                            var panel = FindVisualChildren<SettingsHeaderPanel>(window).First(p => p.IsVisible);
                            var title = (FrameworkElement)panel.Children[0]; var tabs = (FrameworkElement)panel.Children[1]; var status = (FrameworkElement)panel.Children[2];
                            Rect At(FrameworkElement e) { var p = e.TranslatePoint(new Point(0, 0), panel); return new Rect(p.X, p.Y, e.ActualWidth, e.ActualHeight); }
                            var t = At(title); var b = At(tabs); var s = At(status);
                            var label = $"{tag} tab{settingsTab} busy={busy}";
                            var statusFull = status.ActualWidth + status.Margin.Left + status.Margin.Right;
                            Require(Math.Abs(statusFull - status.DesiredSize.Width) < 0.5, $"{label}: the status cluster is arranged at its full desired width incl. margin ({statusFull:0.#} of {status.DesiredSize.Width:0.#})");
                            Require(s.Left >= -0.5 && s.Right <= panel.ActualWidth + 0.5, $"{label}: the status cluster is inside the header ({s.Left:0.#}..{s.Right:0.#} of {panel.ActualWidth:0.#})");
                            Require(!s.IntersectsWith(Shrink(b)) && !s.IntersectsWith(Shrink(t)), $"{label}: the status cluster overlaps neither the tab strip nor the title");
                            Require(!Shrink(t).IntersectsWith(Shrink(b)), $"{label}: the title and the tab strip do not overlap");
                            Require(b.Left >= -0.5 && b.Right <= panel.ActualWidth + 0.5, $"{label}: the tab strip is whole inside the header");
                            var stacked = b.Top > Math.Max(t.Bottom, s.Bottom) - 1;
                            if (stacked) { stackedSeen = true; Require(Math.Abs((b.Left + b.Right) / 2 - panel.ActualWidth / 2) < 1.0, $"{label}: stacked tab strip stays centred"); }
                            else { inlineSeen = true; Require(Math.Abs((b.Left + b.Right) / 2 - panel.ActualWidth / 2) < 1.0, $"{label}: inline tab strip stays exactly centred (layout preserved)"); Require(t.Right <= b.Left + 0.5, $"{label}: title left of tabs"); }
                            var scroller = (ScrollViewer)window.FindName("SettingsScrollViewer");
                            Require(scroller.ScrollableWidth < 0.5, $"{label}: no horizontal scroll ({scroller.ScrollableWidth:0.#})");
                            if (language == "vi" && scale < 1.1 && width < 1100 && !busy) Require(!stacked, $"{label}: where there is enough room the single-row layout is kept");
                        }
                        vm.TestSetBusy(false);
                        window.Close(); vm.Language = "vi"; vm.Theme = "light"; vm.UiScale = 1; vm.Dispose();
                        report.Add(tag);
                    }
                    Require(stackedSeen && inlineSeen, "both layouts were exercised (stacked fallback and the preserved single row)");
                    Console.WriteLine("WPF H19 header fixture: PASS (" + string.Join(", ", report) + ")");
                    exitCode = 0;
                }
                finally { app.Shutdown(); }
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); }
        });
        thread.SetApartmentState(ApartmentState.STA); thread.Start(); thread.Join();
        return exitCode;
    }

    private static Rect Shrink(Rect r) => new(r.X + 0.5, r.Y + 0.5, Math.Max(0, r.Width - 1), Math.Max(0, r.Height - 1));
}
