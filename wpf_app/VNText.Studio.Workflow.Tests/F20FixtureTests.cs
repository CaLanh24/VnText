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
    /// <summary>full20 F4/F5: bulk-replace counts pluralise independently (VI unchanged, EN time/times + row/rows) and the Translate/Patch log collapses to a hint only while empty and idle.</summary>
    private static int RunF20Fixture()
    {
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            try
            {
                var root = Environment.GetEnvironmentVariable("VNTEXT_LOCALAPPDATA") ?? throw new InvalidOperationException("isolated root required");
                Require(Path.GetFullPath(root).Contains(Path.DirectorySeparatorChar + "TEST_RUN" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "the fixture needs the TEST_RUN isolation");
                var app = new VNText.Studio.App.App();
                app.InitializeComponent();
                app.ShutdownMode = ShutdownMode.OnExplicitShutdown;
                try
                {
                    var cases = new (long m, long r, string en, string vi)[]
                    {
                        (1, 1, "Will replace once in 1 row (filtered rows).", "Sẽ thay 1 lần trong 1 dòng (filtered rows)."),
                        (2, 1, "Will replace 2 times in 1 row (filtered rows).", "Sẽ thay 2 lần trong 1 dòng (filtered rows)."),
                        (1, 2, "Will replace once in 2 rows (filtered rows).", "Sẽ thay 1 lần trong 2 dòng (filtered rows)."),
                        (2, 2, "Will replace 2 times in 2 rows (filtered rows).", "Sẽ thay 2 lần trong 2 dòng (filtered rows)."),
                    };
                    foreach (var language in new[] { "en", "vi" })
                    {
                        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        vm.Language = language; UiText.SetLanguage(language);
                        foreach (var c in cases)
                        {
                            var text = UiText.TranslateDynamic(MainViewModel.BulkReplaceMsg("Sẽ thay {M} lần trong {R} dòng ({T0}).", c.m, c.r, "filtered rows"));
                            Require(text == (language == "en" ? c.en : c.vi), $"F4 {language} {c.m}/{c.r}: '{text}'");
                            var confirm = UiText.TranslateDynamic(MainViewModel.BulkReplaceMsg("Thay thế {M} lần trong {R} dòng?", c.m, c.r));
                            var done = UiText.TranslateDynamic(MainViewModel.BulkReplaceMsg("Đã thay {M} lần trong {R} dòng. Có thể hoàn tác; đã tạo bản lưu khôi phục.", c.m, c.r));
                            if (language == "en")
                            {
                                Require(confirm == $"Replace {(c.m == 1 ? "once" : c.m + " times")} in {(c.r == 1 ? "1 row" : c.r + " rows")}?", "F4 en confirm " + confirm);
                                Require(done.StartsWith($"Replaced {(c.m == 1 ? "once" : c.m + " times")} in {(c.r == 1 ? "1 row" : c.r + " rows")}."), "F4 en success " + done);
                            }
                            else Require(confirm == $"Thay thế {c.m} lần trong {c.r} dòng?", "F4 vi confirm " + confirm);
                        }
                        vm.Language = "vi"; UiText.SetLanguage("vi"); vm.Dispose();
                    }

                    foreach (var (language, theme, scale) in new[] { ("vi", "light", 1.0), ("en", "dark", 1.2) })
                    {
                        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        vm.Language = language; vm.Theme = theme; vm.UiScale = scale;
                        vm.NavigateTabCommand.Execute("translate");
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal; window.Width = 1043; window.Height = 720;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1") { window.WindowStartupLocation = WindowStartupLocation.Manual; window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false; }
                        window.Show(); window.UpdateLayout(); PumpFixture(250);
                        FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                        var tag = $"{language}/{theme}/UI{scale * 100:0}";
                        Require(Named("TranslateLogEmptyHint").IsVisible && !Named("TranslateLogBody").IsVisible, tag + ": F5 empty + idle collapses the log body to a hint");
                        vm.TestSetBusy(true); window.UpdateLayout(); PumpFixture(120);
                        Require(!Named("TranslateLogEmptyHint").IsVisible && Named("TranslateLogBody").IsVisible && Math.Abs(Named("TranslateLogBody").ActualHeight - 220) < 0.5, tag + ": F5 busy keeps the 220 DIP log");
                        vm.TestSetBusy(false); vm.TranslateLogLines.Add("[00:00:00] hello"); window.UpdateLayout(); PumpFixture(120);
                        Require(!Named("TranslateLogEmptyHint").IsVisible && Named("TranslateLogBody").IsVisible && Math.Abs(Named("TranslateLogBody").ActualHeight - 220) < 0.5, tag + ": F5 with entries keeps the 220 DIP log");
                        vm.TranslateLogLines.Clear(); window.UpdateLayout(); PumpFixture(120);
                        Require(Named("TranslateLogEmptyHint").IsVisible && !Named("TranslateLogBody").IsVisible, tag + ": F5 cleared + idle returns to the hint");
                        window.Close(); vm.Language = "vi"; vm.Theme = "light"; vm.UiScale = 1; vm.Dispose();
                    }
                    Console.WriteLine("WPF F20 fixture: PASS (F4 counts VI/EN 1/1 2/1 1/2 2/2; F5 hint/body empty, busy, entries, cleared)");
                    exitCode = 0;
                }
                finally { app.Shutdown(); }
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); }
        });
        thread.SetApartmentState(ApartmentState.STA); thread.Start(); thread.Join();
        return exitCode;
    }
}
