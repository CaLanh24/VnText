using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using System.IO;
using VNText.Studio.App.Services;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private static int RunAppDialogFixture(string[] args)
    {
        var exitCode = 1;
        var fixtureIndex = Array.IndexOf(args, "--app-dialog-fixture");
        var outDir = fixtureIndex >= 0 && fixtureIndex + 1 < args.Length
            ? args[fixtureIndex + 1]
            : "";
        if (!string.IsNullOrWhiteSpace(outDir))
            Directory.CreateDirectory(outDir);
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

                var owner = new Window { Title = "Dialog fixture owner", Width = 640, Height = 400 };
                owner.Loaded += (_, _) => owner.Dispatcher.BeginInvoke(new Action(() =>
                {
                    try
                    {
                        app.Resources["SurfaceBrush"] = new SolidColorBrush(Color.FromRgb(30, 35, 46));
                        app.Resources["InkBrush"] = new SolidColorBrush(Color.FromRgb(245, 246, 250));
                        var longMessage = string.Join("\n", Enumerable.Range(1, 48).Select(i => $"Fixture detail {i}: a long error message remains readable and scrollable."));
                        var confirmed = ShowDialogAndInspect(app, owner, "Dark long-message confirmation", longMessage,
                            MessageBoxButton.YesNo, MessageBoxResult.Yes,
                            string.IsNullOrWhiteSpace(outDir) ? null : Path.Combine(outDir, "dialog_dark_long_confirmation.png"), useDefaultOwner: true);
                        AssertEqual(MessageBoxResult.Yes, confirmed);

                        var safeDefault = ShowDialogAndInspect(app, owner, "Safe confirmation keyboard default",
                            "Enter should choose No for this confirmation.", MessageBoxButton.YesNo, MessageBoxResult.No,
                            null, useDefaultOwner: true);
                        AssertEqual(MessageBoxResult.No, safeDefault);

                        app.Resources["SurfaceBrush"] = new SolidColorBrush(Color.FromRgb(250, 250, 252));
                        app.Resources["InkBrush"] = new SolidColorBrush(Color.FromRgb(22, 26, 34));
                        var cancelled = ShowDialogAndInspect(app, owner, "Light keyboard-cancel confirmation",
                            "Pressing Escape must cancel this confirmation.", MessageBoxButton.YesNoCancel, MessageBoxResult.Cancel,
                            string.IsNullOrWhiteSpace(outDir) ? null : Path.Combine(outDir, "dialog_light_cancel_confirmation.png"));
                        AssertEqual(MessageBoxResult.Cancel, cancelled);
                        Console.WriteLine("WPF app dialog interaction fixture: PASS (dark/light resources, long text, default/explicit owner modal, affirmative click, safe No default, Escape cancel)");
                        exitCode = 0;
                    }
                    catch (Exception ex)
                    {
                        Console.Error.WriteLine(ex);
                        exitCode = 1;
                    }
                    finally
                    {
                        owner.Close();
                        app.Shutdown(exitCode);
                    }
                }));
                app.Run(owner);
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

    private static MessageBoxResult ShowDialogAndInspect(
        Application app,
        Window owner,
        string caption,
        string message,
        MessageBoxButton buttons,
        MessageBoxResult expected,
        string? screenshotPath,
        bool useDefaultOwner = false)
    {
        Exception? failure = null;
        var timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(40) };
        timer.Tick += (_, _) =>
        {
            var dialog = app.Windows.OfType<Window>().SingleOrDefault(window => !ReferenceEquals(window, owner) && window.Title == caption);
            if (dialog is null)
                return;
            timer.Stop();
            try
            {
                AssertTrue(ReferenceEquals(owner, dialog.Owner));
                AssertTrue(dialog.IsVisible);
                AssertTrue(ReferenceEquals(app.TryFindResource("SurfaceBrush"), dialog.Background));
                AssertTrue(ReferenceEquals(app.TryFindResource("InkBrush"), dialog.Foreground));
                var body = FindVisual<TextBox>(dialog) ?? throw new InvalidOperationException("Dialog body TextBox missing");
                AssertEqual(message, body.Text);
                AssertTrue(body.MaxHeight >= 300);
                AssertTrue(dialog.ActualHeight <= dialog.MaxHeight);
                if (!string.IsNullOrWhiteSpace(screenshotPath))
                    CaptureDialog(dialog, screenshotPath);

                if (expected == MessageBoxResult.Yes)
                {
                    var bodyScroll = FindVisualChildren<ScrollViewer>(body).FirstOrDefault();
                    if (message.Count(character => character == '\n') > 10)
                    {
                        AssertTrue(bodyScroll is not null && bodyScroll.ScrollableHeight > 0);
                        AssertEqual(Visibility.Visible, bodyScroll!.ComputedVerticalScrollBarVisibility);
                        if (!string.IsNullOrWhiteSpace(screenshotPath))
                        {
                            bodyScroll.ScrollToVerticalOffset(bodyScroll.ScrollableHeight);
                            dialog.UpdateLayout();
                            CaptureDialog(dialog, Path.Combine(Path.GetDirectoryName(screenshotPath)!,
                                Path.GetFileNameWithoutExtension(screenshotPath) + "_scrolled.png"));
                        }
                    }
                    var yes = FindButtons(dialog).Single(button => string.Equals(button.Content?.ToString(), "Có", StringComparison.Ordinal));
                    var no = FindButtons(dialog).Single(button => string.Equals(button.Content?.ToString(), "Không", StringComparison.Ordinal));
                    AssertFalse(yes.IsDefault);
                    AssertTrue(no.IsDefault);
                    yes.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
                }
                else if (expected == MessageBoxResult.No)
                {
                    var yes = FindButtons(dialog).Single(button => string.Equals(button.Content?.ToString(), "Có", StringComparison.Ordinal));
                    var no = FindButtons(dialog).Single(button => string.Equals(button.Content?.ToString(), "Không", StringComparison.Ordinal));
                    AssertFalse(yes.IsDefault);
                    AssertTrue(no.IsDefault);
                    no.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
                }
                else
                {
                    var source = PresentationSource.FromVisual(dialog) ?? PresentationSource.FromVisual(owner)
                        ?? throw new InvalidOperationException("Dialog has no presentation source");
                    var escape = new KeyEventArgs(Keyboard.PrimaryDevice, source, Environment.TickCount, Key.Escape)
                    {
                        RoutedEvent = Keyboard.KeyDownEvent,
                    };
                    dialog.RaiseEvent(escape);
                }
            }
            catch (Exception ex)
            {
                failure = ex;
                dialog.Close();
            }
        };
        timer.Start();
        var result = useDefaultOwner
            ? AppDialogService.Show(message, caption, buttons, MessageBoxImage.Question)
            : AppDialogService.Show(message, caption, buttons, MessageBoxImage.Question, owner);
        if (failure is not null)
            throw new InvalidOperationException($"Dialog fixture failed for {caption}", failure);
        return result;
    }

    private static void CaptureDialog(Window dialog, string path)
    {
        dialog.UpdateLayout();
        var bitmap = new RenderTargetBitmap(
            Math.Max(1, (int)Math.Ceiling(dialog.ActualWidth)),
            Math.Max(1, (int)Math.Ceiling(dialog.ActualHeight)),
            96,
            96,
            PixelFormats.Pbgra32);
        bitmap.Render(dialog);
        var encoder = new PngBitmapEncoder();
        encoder.Frames.Add(BitmapFrame.Create(bitmap));
        using var stream = File.Create(path);
        encoder.Save(stream);
    }

    private static IEnumerable<Button> FindButtons(DependencyObject parent)
    {
        for (var i = 0; i < VisualTreeHelper.GetChildrenCount(parent); i++)
        {
            var child = VisualTreeHelper.GetChild(parent, i);
            if (child is Button button)
                yield return button;
            foreach (var nested in FindButtons(child))
                yield return nested;
        }
    }

    private static IEnumerable<T> FindVisualChildren<T>(DependencyObject parent) where T : DependencyObject
    {
        for (var i = 0; i < VisualTreeHelper.GetChildrenCount(parent); i++)
        {
            var child = VisualTreeHelper.GetChild(parent, i);
            if (child is T match)
                yield return match;
            foreach (var nested in FindVisualChildren<T>(child))
                yield return nested;
        }
    }
}
