using System.IO;
using System.Text;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    /// <summary>Q1: the resources task ends with a terminal status on the Extract page (success / not-ready / error / cancel), VI and EN, without touching another task's status or replaying the running text.</summary>
    private static int RunB18Fixture()
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
                app.ShutdownMode = System.Windows.ShutdownMode.OnExplicitShutdown;
                var work = Path.Combine(TestTempRoot(), "b18_" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(work);
                var game = Path.Combine(work, "game"); Directory.CreateDirectory(game);
                var statusFile = Path.Combine(WorkerPaths.AppDataRoot(), "resource-status.json");
                Directory.CreateDirectory(Path.GetDirectoryName(statusFile)!);
                var previousStatusFile = File.Exists(statusFile) ? File.ReadAllBytes(statusFile) : null;
                string Report(bool ready) => "{\"resources\":[{\"resource\":\"model\",\"ready\":" + (ready ? "true" : "false") + ",\"path\":\"x\",\"error\":\"missing\"},{\"resource\":\"renpy\",\"ready\":" + (ready ? "true" : "false") + ",\"path\":\"y\",\"error\":\"missing\"}]}";
                var report = new List<string>();
                try
                {
                                        foreach (var language in new[] { "vi", "en" })
                    {
                        string Shown(MainViewModel vm) => language == "en" ? UiText.TranslateDynamic(vm.ExtractStatusText) : vm.ExtractStatusText;
                        MainViewModel Fresh(string earlier)
                        {
                            var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false) { InputPath = game };
                            vm.Language = language; UiText.SetLanguage(language); vm.StatusText = earlier;
                            return vm;
                        }
                        void Finish(MainViewModel vm, bool ok, string? error = null)
                        {
                            vm.TestSimulateTaskComplete("resources", new WorkerEvent { Type = "complete", Id = vm.TestActiveTaskId, Ok = ok, Error = error, Summary = ok ? "checked" : null });
                        }

                        // ---- success: running text while it runs, then NOT the running text on the Extract page ----
                        File.WriteAllText(statusFile, Report(true), new UTF8Encoding(false));
                        var vmOk = Fresh("Sẵn sàng");
                        vmOk.TestClaimResourcesStatus(false);
                        var runningShown = vmOk.StatusText; Require(runningShown == vmOk.ResourceStatus && runningShown.Length > 0, $"{language} Q1: the task publishes its running status ({runningShown})");
                        Finish(vmOk, true);
                        Require(vmOk.StatusText != runningShown && !Shown(vmOk).Contains("kiểm tra tài nguyên", StringComparison.OrdinalIgnoreCase) && !Shown(vmOk).Contains("Checking resources", StringComparison.OrdinalIgnoreCase), $"{language} Q1: success leaves no running text on Extract ('{Shown(vmOk)}')");
                        Require(Shown(vmOk) == (language == "vi" ? "Sẵn sàng lấy text" : UiText.TranslateDynamic("Sẵn sàng lấy text")), $"{language} Q1: Extract shows the ready line ('{Shown(vmOk)}')");
                        Require(vmOk.ResourcesAllReady && !vmOk.ResourcesNeedRecovery, $"{language} Q1: the Settings resource state is unchanged (ready)");
                        // a late/duplicate completion never replays or rewrites the status
                        var settled = vmOk.StatusText;
                        Finish(vmOk, true);
                        Require(vmOk.StatusText == settled, $"{language} Q1: a late completion does not rewrite the status");

                        // ---- earlier status is restored (a finished extract result stays) ----
                        var vmKeep = Fresh("Đã lấy text xong: 120 dòng");
                        vmKeep.TestClaimResourcesStatus(false); Finish(vmKeep, true);
                        Require(vmKeep.StatusText == "Đã lấy text xong: 120 dòng", $"{language} Q1: the earlier extract result is restored, not replaced ({vmKeep.StatusText})");

                        // ---- another task's status written while resources run is never overwritten ----
                        var vmOther = Fresh("Sẵn sàng");
                        vmOther.TestClaimResourcesStatus(false);
                        vmOther.StatusText = "Cảnh báo: thiếu file bắt buộc";
                        Finish(vmOther, true);
                        Require(vmOther.StatusText == "Cảnh báo: thiếu file bắt buộc", $"{language} Q1: an unrelated status is preserved ({vmOther.StatusText})");

                        // ---- the Extract page's drawn status line (real window, UiTextDynamic converter) follows the language ----
                        {
                            var vmDraw = Fresh("Sẵn sàng"); vmDraw.TestClaimResourcesStatus(false); Finish(vmDraw, false, "boom");
                            var window = new VNText.Studio.App.MainWindow(vmDraw, new FixtureUpdatePresentation());
                            window.WindowState = System.Windows.WindowState.Normal; window.Width = 1055; window.Height = 720;
                            if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1") { window.WindowStartupLocation = System.Windows.WindowStartupLocation.Manual; window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false; }
                            vmDraw.NavigateTabCommand.Execute("extract"); window.Show(); window.UpdateLayout(); PumpFixture(250);
                            var line = (System.Windows.Controls.TextBlock)window.FindName("ExtractStatusLine");
                            Require(line.Text == (language == "vi" ? "Tài nguyên chưa sẵn sàng — xem Cài đặt › Dữ liệu." : "Resources are not ready — see Settings › Data."), $"{language} Q1: the drawn Extract status line is localized ('{line.Text}')");
                            vmDraw.Language = language == "vi" ? "en" : "vi"; UiText.SetLanguage(vmDraw.Language); PumpFixture(100); window.UpdateLayout();
                            Require(line.Text == (language == "vi" ? "Resources are not ready — see Settings › Data." : "Tài nguyên chưa sẵn sàng — xem Cài đặt › Dữ liệu."), $"{language} Q1: a language switch refreshes the Extract status line ('{line.Text}')");
                            window.Close(); vmDraw.Language = language; UiText.SetLanguage(language); vmDraw.Dispose();
                        }

                        // ---- not ready / error: a short blocked line, banner + Settings detail kept, never the running text ----
                        File.WriteAllText(statusFile, Report(false), new UTF8Encoding(false));
                        var vmBad = Fresh("Sẵn sàng");
                        vmBad.TestClaimResourcesStatus(false); Finish(vmBad, false, "boom");
                        Require(vmBad.StatusText == "Tài nguyên chưa sẵn sàng — xem Cài đặt › Dữ liệu." && Shown(vmBad).Length > 0 && (language == "vi" || !Shown(vmBad).Contains("Tài nguyên")), $"{language} Q1: error leaves a localized blocked line ('{Shown(vmBad)}')");
                        Require(vmBad.ResourcesNeedRecovery && vmBad.ResourceStatus.Contains("boom", StringComparison.Ordinal), $"{language} Q1: the error detail stays in the resource status");
                        var vmMissing = Fresh("Sẵn sàng");
                        vmMissing.TestClaimResourcesStatus(false); Finish(vmMissing, true);
                        Require(vmMissing.StatusText == "Tài nguyên chưa sẵn sàng — xem Cài đặt › Dữ liệu." && vmMissing.ResourcesNeedRecovery, $"{language} Q1: a completed check that finds missing resources says so (not 'ready', not running)");

                        // ---- cancel ----
                        var vmCancel = Fresh("Sẵn sàng");
                        vmCancel.TestClaimResourcesStatus(true);
                        Require(vmCancel.StatusText == vmCancel.ResourceStatus && vmCancel.StatusText != runningShown, $"{language} Q1: the prepare task publishes its own running text");
                        Finish(vmCancel, false, "cancelled");
                        Require(vmCancel.StatusText == "Đã hủy chuẩn bị tài nguyên; có thể tải lại. Tài nguyên đã cài vẫn được giữ.", $"{language} Q1: cancel ends the running status ('{Shown(vmCancel)}')");
                        report.Add(language);
                    }
                    UiText.SetLanguage("vi");
                    Console.WriteLine("WPF B18 Q1 fixture: PASS (" + string.Join(", ", report) + ")");
                    exitCode = 0;
                }
                finally
                {
                    using (var restore = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false)) { restore.Language = "vi"; restore.Theme = "light"; restore.UiScale = 1; }      // the isolated settings return to the defaults (later fixtures read them)
                    if (previousStatusFile is null) { try { File.Delete(statusFile); } catch (IOException) { } } else File.WriteAllBytes(statusFile, previousStatusFile);
                    try { Directory.Delete(work, true); } catch (IOException) { }
                    app.Shutdown();
                }
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); }
        });
        thread.SetApartmentState(ApartmentState.STA); thread.Start(); thread.Join();
        return exitCode;
    }
}
