using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Media;
using System.Windows.Threading;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    [DllImport("user32.dll")] private static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] private static extern IntPtr GetDC(IntPtr hWnd);
    [DllImport("user32.dll")] private static extern int ReleaseDC(IntPtr hWnd, IntPtr hDc);
    [DllImport("gdi32.dll")] private static extern uint GetPixel(IntPtr hDc, int x, int y);

    private static (byte R, byte G, byte B) ScreenPixel(int x, int y)
    {
        var dc = GetDC(IntPtr.Zero);
        try
        {
            var value = GetPixel(dc, x, y);
            return ((byte)(value & 0xFF), (byte)((value >> 8) & 0xFF), (byte)((value >> 16) & 0xFF));
        }
        finally { ReleaseDC(IntPtr.Zero, dc); }
    }

    /// <summary>
    /// Opens a real themed tooltip over a window painted in a known colour and samples the screen:
    /// the tooltip corner must show the window colour (rounded, transparent popup), the centre the
    /// tooltip surface, and the text must wrap within the style's maximum width.
    /// </summary>
    private static int RunTooltipFixture(string[] args)
    {
        var exitCode = 1;
        var index = Array.IndexOf(args, "--tooltip-fixture");
        var outPath = index >= 0 && index + 1 < args.Length ? args[index + 1] : "";
        var thread = new Thread(() =>
        {
            try
            {
                var app = new Application { ShutdownMode = ShutdownMode.OnExplicitShutdown };
                foreach (var dictionary in new[] { "DesignTokens", "IconGeometries", "ControlStyles" })
                    app.Resources.MergedDictionaries.Add(new ResourceDictionary
                    {
                        Source = new Uri($"pack://application:,,,/VNText.Studio.App;component/Themes/{dictionary}.xaml"),
                    });
                var button = new Button { Content = "target", Width = 120, Height = 36, HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center };
                var longText = string.Join(" ", Enumerable.Repeat("Mô hình OPUS-MT INT8 chạy trên máy, không gửi nội dung lên mạng.", 4));
                var tip = new ToolTip { Content = longText, Placement = PlacementMode.Bottom, PlacementTarget = button };
                button.ToolTip = tip;
                var window = new Window
                {
                    Width = 700, Height = 420, Left = 120, Top = 120, WindowStyle = WindowStyle.None, ResizeMode = ResizeMode.NoResize,
                    Background = new SolidColorBrush(Color.FromRgb(255, 0, 255)), // magenta: unmistakable "behind the tooltip"
                    Content = button, Topmost = true,
                };
                window.Loaded += (_, _) =>
                {
                    tip.IsOpen = true;
                    var phase2 = false;
                    var timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(500) };
                    timer.Tick += (_, _) =>
                    {
                        timer.Stop();
                        try
                        {
                            AssertTrue(tip.IsOpen);
                            var topLeft = tip.PointToScreen(new Point(0, 0));
                            var dpi = VisualTreeHelper.GetDpi(tip);
                            var x = (int)Math.Round(topLeft.X);
                            var y = (int)Math.Round(topLeft.Y);
                            var width = tip.ActualWidth * dpi.DpiScaleX;
                            var height = tip.ActualHeight * dpi.DpiScaleY;
                            // Wrapping: bounded by the style's MaxWidth (400 DIPs) and more than one line tall.
                            AssertTrue(tip.ActualWidth <= 400.5);
                            AssertTrue(tip.ActualHeight > 40);
                            var scale = dpi.DpiScaleX;
                            var inner = (int)Math.Round(6 * scale); // the style's shadow margin
                            var corner = ScreenPixel(x + inner + 1, y + inner + 1);
                            var centre = ScreenPixel(x + (int)(width / 2), y + (int)(height / 2));
                            var edge = ScreenPixel(x + (int)(width / 2), y + (int)Math.Round(6 * dpi.DpiScaleX) + 3);
                            Console.WriteLine($"tooltip rect={x},{y} {width:0}x{height:0} corner={corner} centre={centre} edge={edge}");
                            bool Magenta((byte R, byte G, byte B) c) => c.R > 200 && c.G < 80 && c.B > 200;
                            var farCorner = ScreenPixel(x + 1, y + 1);
                            AssertTrue(farCorner.R > 150 && farCorner.B > 150 && farCorner.G < 150); // transparent popup shows the window (shadow tint allowed)
                            AssertFalse(corner == (255, 255, 255)); // the rounded inner corner is not surface-coloured
                            AssertFalse(Magenta(centre)); // the surface is painted
                            AssertFalse(Magenta(edge));
                            tip.IsOpen = false;
                            phase2 = true;
                            // Phase 2: the production shape - a plain string ToolTip created by ToolTipService on hover.
                            button.ToolTip = longText;
                            ToolTipService.SetInitialShowDelay(button, 0);
                            var origin = button.PointToScreen(new Point(button.ActualWidth / 2, button.ActualHeight / 2));
                            SetCursorPos((int)origin.X, (int)origin.Y);
                            var probe = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(700) };
                            var attempts = 0;
                            probe.Tick += (_, _) =>
                            {
                                attempts++;
                                try
                                {
                                    var live = PresentationSource.CurrentSources.OfType<PresentationSource>()
                                        .Select(source => source.RootVisual).OfType<DependencyObject>()
                                        .SelectMany(root => FindVisualChildren<ToolTip>(root))
                                        .FirstOrDefault(t => !ReferenceEquals(t, tip) && t.IsOpen);
                                    if (live is null && attempts < 6) { SetCursorPos((int)origin.X + attempts, (int)origin.Y); return; }
                                    probe.Stop();
                                    AssertTrue(live is not null);
                                    AssertTrue(live!.Style is not null && ReferenceEquals(live.Style, app.FindResource(typeof(ToolTip))));
                                    var at = live.PointToScreen(new Point(0, 0));
                                    var d = VisualTreeHelper.GetDpi(live);
                                    var sx = (int)Math.Round(at.X); var sy = (int)Math.Round(at.Y);
                                    var inner2 = (int)Math.Round(6 * d.DpiScaleX);
                                    var c2 = ScreenPixel(sx + inner2 + 1, sy + inner2 + 1);
                                    var m2 = ScreenPixel(sx + (int)(live.ActualWidth * d.DpiScaleX / 2), sy + (int)(live.ActualHeight * d.DpiScaleY / 2));
                                    Console.WriteLine($"string tooltip rect={sx},{sy} {live.ActualWidth * d.DpiScaleX:0}x{live.ActualHeight * d.DpiScaleY:0} corner={c2} centre={m2}");
                                    AssertTrue(live.ActualWidth <= 400.5);
                                    // Rounded transparent popup: the corner shows whatever is behind the tooltip (sampled just outside it).
                                    AssertFalse(c2 == (255, 255, 255));
                                    AssertFalse(ScreenPixel(sx + inner2 + (int)(12 * d.DpiScaleX), sy + inner2 + (int)(6 * d.DpiScaleX)) != (255, 255, 255));
                                    AssertFalse(Magenta(m2));
                                    Console.WriteLine("WPF tooltip fixture: PASS (rounded transparent popup, themed surface, wrapped within max width; also via the real string ToolTipService path)");
                                    exitCode = 0;
                                }
                                catch (Exception ex2)
                                {
                                    probe.Stop();
                                    Console.Error.WriteLine(ex2);
                                    exitCode = 1;
                                }
                                if (!probe.IsEnabled) { window.Close(); app.Shutdown(exitCode); }
                            };
                            probe.Start();
                            return;
                        }
                        catch (Exception ex)
                        {
                            Console.Error.WriteLine(ex);
                            exitCode = 1;
                        }
                        finally
                        {
                            if (!phase2)
                            {
                                tip.IsOpen = false;
                                window.Close();
                                app.Shutdown(exitCode);
                            }
                        }
                    };
                    timer.Start();
                };
                app.Run(window);
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(ex);
                exitCode = 1;
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        return exitCode;
    }
}
