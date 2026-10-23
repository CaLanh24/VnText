using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;
using VNText.Studio.App.Services;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private static int RunAppDialogFixture()
    {
        var exitCode = 1;
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
                            MessageBoxButton.YesNo, MessageBoxResult.Yes);
                        AssertEqual(MessageBoxResult.Yes, confirmed);

                        app.Resources["SurfaceBrush"] = new SolidColorBrush(Color.FromRgb(250, 250, 252));
                        app.Resources["InkBrush"] = new SolidColorBrush(Color.FromRgb(22, 26, 34));
                        var cancelled = ShowDialogAndInspect(app, owner, "Light keyboard-cancel confirmation",
                            "Pressing Escape must cancel this confirmation.", MessageBoxButton.YesNoCancel, MessageBoxResult.Cancel);
                        AssertEqual(MessageBoxResult.Cancel, cancelled);
                        Console.WriteLine("WPF app dialog interaction fixture: PASS (dark/light resources, long text, owner modal, affirmative click, Escape cancel)");
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
        MessageBoxResult expected)
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

                if (expected == MessageBoxResult.Yes)
                {
                    var yes = FindButtons(dialog).Single(button => string.Equals(button.Content?.ToString(), "Có", StringComparison.Ordinal));
                    yes.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));
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
        var result = AppDialogService.Show(message, caption, buttons, MessageBoxImage.Question, owner);
        if (failure is not null)
            throw new InvalidOperationException($"Dialog fixture failed for {caption}", failure);
        return result;
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
}
