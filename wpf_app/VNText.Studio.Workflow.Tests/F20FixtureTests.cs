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
                    {
                        // F5 (Root correction): a stale no-match overlay must never cover a read failure or the no-file state (owned fixture log only).
                        var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                        var window = new MainWindow(vm, new FixtureUpdatePresentation());
                        window.WindowState = WindowState.Normal; window.Width = 1043; window.Height = 720;
                        if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1") { window.WindowStartupLocation = WindowStartupLocation.Manual; window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false; }
                        window.Show(); window.UpdateLayout(); PumpFixture(200);
                        Directory.CreateDirectory(vm.JournalStore.Root);
                        var logPath = Path.Combine(vm.JournalStore.Root, "app.log." + DateTime.Now.ToString("yyyy-MM-dd"));
                        Require(Path.GetFullPath(logPath).Contains(Path.DirectorySeparatorChar + "TEST_RUN" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "the Journal fixture log lives in the TEST_RUN isolation");
                        File.WriteAllText(logPath, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff zzz") + " INFO alpha line one" + Environment.NewLine);
                        var journal = new JournalWindow(window, vm);
                        journal.Show(); journal.UpdateLayout(); PumpFixture(250);
                        var queryBox = FindVisualChildren<TextBox>(journal).First(b => b.ToolTip as string == "Tìm trong nhật ký");
                        bool NoMatchShown() => FindVisualChildren<TextBlock>(journal).Any(t => t.IsVisible && t.Text.StartsWith("Không có bản ghi khớp", StringComparison.Ordinal));
                        bool EmptyShown() => FindVisualChildren<TextBlock>(journal).Any(t => t.IsVisible && t.Text.StartsWith("Chưa có bản ghi nào", StringComparison.Ordinal));
                        queryBox.Text = "zzz-none"; PumpFixture(150);
                        Require(NoMatchShown(), "F5: the filter with no match says so");
                        using (var locked = new FileStream(logPath, FileMode.Open, FileAccess.ReadWrite, FileShare.None))
                        {
                            queryBox.Text = "zzz-none-2"; PumpFixture(150);
                            Require(!NoMatchShown() && !EmptyShown(), "F5: a read failure is not covered by a stale no-match overlay");
                            var logBox = FindVisualChildren<VNText.Studio.App.Controls.SeverityLogBox>(journal).First(b => b.IsReadOnly);
                            Require(logBox.Text.Contains("Không đọc được nhật ký", StringComparison.Ordinal), "F5: the read failure message is visible");
                        }
                        queryBox.Text = "alpha"; PumpFixture(150);
                        Require(!NoMatchShown() && !EmptyShown(), "F5: after the lock is released the log reads again");
                        queryBox.Text = "zzz-none"; PumpFixture(150);
                        Require(NoMatchShown(), "F5: no-match again");
                        File.Delete(logPath);
                        FindVisualChildren<Button>(journal).First(b => b.Content as string == "Làm mới").Command?.Execute(null);
                        var refresh = FindVisualChildren<Button>(journal).First(b => b.Content as string == "Làm mới");
                        refresh.RaiseEvent(new RoutedEventArgs(Button.ClickEvent)); PumpFixture(250);
                        Require(!NoMatchShown(), "F5: the no-file state is not covered by a stale no-match overlay");
                        journal.Close(); window.Close(); vm.Dispose();
                    }
                    {
                        // F2 (Root correction): the in-grid translation editor of a very long text is bounded and scrolls its own text (keyboard reaches the end), the data is untouched.
                        var host = new Window { Width = 400, Height = 300, ShowActivated = false, ShowInTaskbar = false, WindowStartupLocation = WindowStartupLocation.Manual, Left = -4000, Top = 0 };
                        var panel = new ImageWorkspacePanel();
                        var longText = string.Join(" ", Enumerable.Repeat("Bảng thông báo ghi rõ từng quy định của ngôi làng rất chi tiết, hãy đọc kỹ từng dòng trước khi rời đi.", 8));
                        var editor = new TextBox { Style = (Style)panel.FindResource("RegionTranslationEditor"), Text = longText, Width = 170 };
                        host.Content = editor; host.Show(); host.UpdateLayout(); PumpFixture(150);
                        var scroller = (ScrollViewer)editor.Template.FindName("PART_ContentHost", editor);
                        Require(editor.ActualHeight <= 112.5, "F2: the long-translation editor is bounded (" + editor.ActualHeight + ")");
                        Require(scroller.VerticalScrollBarVisibility == ScrollBarVisibility.Auto && scroller.ScrollableHeight > 0, "F2: the bounded editor scrolls its own text (" + scroller.ScrollableHeight + ")");
                        editor.Focus(); editor.CaretIndex = editor.Text.Length; editor.ScrollToEnd(); host.UpdateLayout(); PumpFixture(100);
                        Require(scroller.VerticalOffset >= scroller.ScrollableHeight - 1 && editor.Text == longText, "F2: the end of the full text is reachable and the data is unchanged");
                        host.Close();
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
