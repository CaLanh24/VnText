using System.IO;
using System.Text;
using System.Text.Json;
using System.Windows;
using VNText.Studio.App;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    /// <summary>
    /// Shows the REAL production update dialog (MainWindow.ShowUpdateDialog -> UpdateWindow, the same code path the app takes after a verified update) in the success or
    /// release-notes state, with the language chosen by VNTEXT_UPD_LANG (vi|en), so a person can read the visible secondary button and UI Automation can read its name.
    /// Nothing is simulated except that the dialog is opened directly instead of by a completed update.  A receipt records what the control reports one second after it opened.
    /// Env: VNTEXT_UPD_MODE (success|notes), VNTEXT_UPD_LANG, VNTEXT_UPD_RECEIPT, VNTEXT_UPD_HOLD_SECONDS, VNTEXT_LOCALAPPDATA (TEST_RUN isolation).
    /// </summary>
    private static int RunUpdateWindowSuccessFixture()
    {
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            try
            {
                string Env(string name, string fallback) => Environment.GetEnvironmentVariable(name) is { Length: > 0 } v ? v : fallback;
                var mode = Env("VNTEXT_UPD_MODE", "success");
                var lang = Env("VNTEXT_UPD_LANG", "vi") == "en" ? "en" : "vi";
                var receiptPath = Env("VNTEXT_UPD_RECEIPT", "");
                var hold = int.TryParse(Env("VNTEXT_UPD_HOLD_SECONDS", "600"), out var h) ? h : 600;
                Require(Path.GetFullPath(Env("VNTEXT_LOCALAPPDATA", "")).Contains(Path.DirectorySeparatorChar + "TEST_RUN" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "the fixture needs the TEST_RUN isolation");
                var app = new VNText.Studio.App.App();
                app.InitializeComponent();
                app.ShutdownMode = ShutdownMode.OnExplicitShutdown;
                try
                {
                    var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                    vm.Language = lang;
                    UiText.Install(); UiText.SetLanguage(lang);
                    var owner = new MainWindow(vm);
                    owner.WindowState = WindowState.Normal; owner.Width = 1043; owner.Height = 720; owner.Left = 60; owner.Top = 20;
                    if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1") { owner.WindowStartupLocation = WindowStartupLocation.Manual; owner.Left = -4000; owner.Top = 0; owner.ShowActivated = false; owner.ShowInTaskbar = false; }
                    owner.Show(); PumpFixture(300);
                    var start = DateTime.UtcNow; var recorded = false;
                    var timer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(500) };
                    timer.Tick += (_, _) =>
                    {
                        var dialog = Application.Current.Windows.OfType<UpdateWindow>().FirstOrDefault();
                        if (dialog is not null && !recorded && (DateTime.UtcNow - start).TotalSeconds > 1.5)
                        {
                            recorded = true;
                            if (receiptPath.Length > 0)
                                File.WriteAllText(receiptPath, JsonSerializer.Serialize(new
                                {
                                    kind = "REAL_PRODUCTION_UPDATE_WINDOW_SECONDARY_BUTTON", mode, language = lang, visible_label = dialog.LaterText, uia_name = dialog.LaterAutomationName,
                                    primary_uia_name = dialog.PrimaryAutomationName, status_text = dialog.StatusText, recorded_utc = DateTime.UtcNow.ToString("o"),
                                }, new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);
                            Console.WriteLine($"update window {mode}/{lang}: visible='{dialog.LaterText}' uia='{dialog.LaterAutomationName}'"); Console.Out.Flush();
                        }
                        if (recorded && dialog is null) { timer.Stop(); foreach (Window w in Application.Current.Windows.Cast<Window>().ToArray()) w.Close(); return; }   // the person closed the dialog: end the fixture
                        if ((DateTime.UtcNow - start).TotalSeconds > hold) { timer.Stop(); foreach (Window w in Application.Current.Windows.Cast<Window>().ToArray()) w.Close(); }
                    };
                    timer.Start();
                    owner.Dispatcher.BeginInvoke(new Action(() => owner.ShowUpdateDialog(mode == "notes", mode == "notes" ? null : "0.1.17")));   // modal: returns when the person closes it
                    var frame = new System.Windows.Threading.DispatcherFrame();
                    owner.Closed += (_, _) => frame.Continue = false;
                    System.Windows.Threading.Dispatcher.PushFrame(frame);
                    timer.Stop();
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
