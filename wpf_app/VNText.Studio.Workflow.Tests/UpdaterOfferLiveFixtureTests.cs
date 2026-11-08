using System.IO;
using System.Net;
using System.Net.Http;
using System.Security.Cryptography;
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
    /// Fixture UI for the updater offer/download popup BEFORE any public release exists.  The production MainWindow, MainViewModel and
    /// WpfUpdateService run unchanged; only the network is replaced by an HttpMessageHandler that answers the GitHub releases API with metadata
    /// built from the REAL candidate route feed and streams the REAL candidate route ZIP (throttled so progress is visible).  It is NOT the
    /// packaged 0.1.16 app and NOT a public offer; the exact 7196-file apply/readback is proven separately by the backend gate.
    /// Env: VNTEXT_UPD_ROOT (extracted 0.1.16 payload), VNTEXT_UPD_ZIP, VNTEXT_UPD_FEED, VNTEXT_UPD_RECEIPT, VNTEXT_UPD_HOLD_SECONDS, VNTEXT_UPD_KBPS.
    /// </summary>
    private static int RunUpdaterOfferLiveFixture()
    {
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            try
            {
                string Env(string name) => Environment.GetEnvironmentVariable(name) ?? throw new InvalidOperationException(name + " is required");
                var root = Path.GetFullPath(Env("VNTEXT_UPD_ROOT"));
                var zipPath = Path.GetFullPath(Env("VNTEXT_UPD_ZIP"));
                var feedPath = Path.GetFullPath(Env("VNTEXT_UPD_FEED"));
                var receiptPath = Env("VNTEXT_UPD_RECEIPT");
                var hold = int.TryParse(Environment.GetEnvironmentVariable("VNTEXT_UPD_HOLD_SECONDS"), out var h) ? h : 900;
                var kbps = int.TryParse(Environment.GetEnvironmentVariable("VNTEXT_UPD_KBPS"), out var k) ? k : 3000;
                Require(Path.GetFullPath(Env("VNTEXT_LOCALAPPDATA")).Contains(Path.DirectorySeparatorChar + "TEST_RUN" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "the fixture needs the TEST_RUN isolation");
                Require(File.Exists(Path.Combine(root, "VNText Studio.exe")) && File.Exists(Path.Combine(root, "app", "VERSION.txt")), "the install root must be an extracted payload");
                var feed = JsonDocument.Parse(File.ReadAllText(feedPath, Encoding.UTF8)).RootElement;
                var packageFile = feed.GetProperty("package_file").GetString()!;
                var packageSha = feed.GetProperty("package_sha256").GetString()!;
                var zipBytes = File.ReadAllBytes(zipPath);
                Require(Path.GetFileName(zipPath) == packageFile && HashBytes(zipBytes) == packageSha, "route ZIP matches its feed (name and sha256)");
                var installed = File.ReadAllText(Path.Combine(root, "app", "VERSION.txt")).Trim();

                // Same source file the packaged app reads; the updates folder must be OUTSIDE the install root (WpfUpdateService.ValidateUpdatePaths), the rest stays inside it.
                var updatesRoot = root.TrimEnd(Path.DirectorySeparatorChar) + "-updates";
                Directory.CreateDirectory(updatesRoot);
                var update = Path.Combine(root, ".update");
                File.WriteAllText(Path.Combine(root, ".vntext-update-source.json"), JsonSerializer.Serialize(new Dictionary<string, object>
                {
                    ["updates_root"] = updatesRoot, ["github_owner"] = "CaLanh24", ["github_repository"] = "VnText",
                    ["work_root"] = Path.Combine(update, "work"), ["backup_root"] = Path.Combine(update, "backup"), ["staging_root"] = Path.Combine(update, "staging"),
                    ["updater_path"] = Path.Combine(update, "updater.exe"), ["log_path"] = Path.Combine(update, "update.log"), ["fault_inject_after_first_replace"] = false,
                }));
                Directory.CreateDirectory(update);
                File.Copy(Path.Combine(root, "VNText Studio.exe"), Path.Combine(update, "updater.exe"), true);

                var version = feed.GetProperty("manifest").ValueKind == JsonValueKind.Object ? feed.GetProperty("manifest").GetProperty("version").GetString()! : JsonDocument.Parse(feed.GetProperty("manifest").GetString()!).RootElement.GetProperty("version").GetString()!;
                var tag = "v" + version;
                var apiUrl = new Uri("https://api.github.com/repos/CaLanh24/VnText/releases?per_page=100");
                var downloadUrl = new Uri($"https://github.com/CaLanh24/VnText/releases/download/{tag}/{packageFile}");
                var release = new
                {
                    tag_name = tag, draft = false, prerelease = false, published_at = DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'"),
                    body = "Bản thử nghiệm giao diện (fixture): nội dung ghi chú phát hành mẫu để kiểm tra hộp thoại cập nhật.",
                    assets = new[] { GitHubAsset(packageFile, "sha256:" + packageSha, zipBytes.LongLength, downloadUrl.AbsoluteUri) },
                };
                var log = new List<string>();
                var handler = new TestHttpMessageHandler((request, _) =>
                {
                    log.Add($"{DateTime.UtcNow:HH:mm:ss.fff} {request.RequestUri}");
                    if (request.RequestUri == apiUrl) return Task.FromResult(JsonResponse(JsonSerializer.Serialize(new[] { release })));
                    if (request.RequestUri == downloadUrl)
                    {
                        var response = new HttpResponseMessage(HttpStatusCode.OK) { Content = new StreamContent(new ThrottledStream(zipBytes, kbps)) };
                        response.Content.Headers.ContentLength = zipBytes.LongLength;
                        return Task.FromResult(response);
                    }
                    throw new HttpRequestException("Unexpected HTTP target: " + request.RequestUri);
                });

                var app = new VNText.Studio.App.App();
                app.InitializeComponent();
                app.ShutdownMode = ShutdownMode.OnExplicitShutdown;
                try
                {
                    var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false, githubHttpHandler: handler, updateInstallRoot: root);
                    vm.UiScale = 1.2; vm.Theme = "dark";
                    var window = new MainWindow(vm);                   // production IUpdatePresentation, no fixture presentation
                    window.WindowState = WindowState.Normal; window.Width = 1043; window.Height = 720;
                    if (Environment.GetEnvironmentVariable("VNTEXT_WPF_FIXTURE_OFFSCREEN") == "1")
                    {
                        window.WindowStartupLocation = WindowStartupLocation.Manual;
                        window.Left = -4000; window.Top = 0; window.ShowActivated = false; window.ShowInTaskbar = false;
                    }
                    var samples = new List<string>();
                    var start = DateTime.UtcNow;
                    var closed = false; window.Closed += (_, _) => closed = true;
                    var lastState = ""; var autoDownload = Environment.GetEnvironmentVariable("VNTEXT_UPD_AUTODOWNLOAD") == "1"; var autoStarted = false;
                    // The offer popup is modal (nested message loop), so state sampling and the hold timeout run from a dispatcher timer, not from this method's loop.
                    var frame = new System.Windows.Threading.DispatcherFrame();
                    var timer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(250) };
                    timer.Tick += (_, _) =>
                    {
                        var state = $"{vm.GitHubUpdateState} downloading={vm.DownloadingUpdate} {vm.DownloadReceived}/{vm.DownloadTotal} applyEnabled={vm.GitHubApplyEnabled}";
                        if (state != lastState) { Console.WriteLine("trace: " + state); Console.Out.Flush(); samples.Add($"{(DateTime.UtcNow - start).TotalSeconds:F1}s {state}"); lastState = state; }
                        if (autoDownload && !autoStarted && vm.GitHubUpdateState == GitHubUpdateState.OfferAvailable) { autoStarted = true; _ = vm.DownloadOfferedUpdateAsync(); }
                        if (closed || (DateTime.UtcNow - start).TotalSeconds >= hold || (autoDownload && vm.GitHubUpdateState == GitHubUpdateState.UpdateAvailable && !vm.DownloadingUpdate))
                        {
                            timer.Stop();
                            foreach (Window w in Application.Current.Windows.Cast<Window>().ToArray()) { if (!ReferenceEquals(w, window)) w.Close(); }
                            frame.Continue = false;
                        }
                    };
                    var recheckDone = false;
                    timer.Tick += (_, _) => { if (!recheckDone && (DateTime.UtcNow - start).TotalSeconds > 6 && log.Count == 0) { recheckDone = true; vm.RecheckUpdateCommand.Execute(null); } };
                    timer.Start();
                    window.Show(); window.UpdateLayout();          // the startup check may raise the modal offer popup from here on
                    System.Windows.Threading.Dispatcher.PushFrame(frame);
                    File.WriteAllText(receiptPath, JsonSerializer.Serialize(new
                    {
                        kind = "UPDATER_OFFER_FIXTURE_UI_NOT_PUBLIC_OFFER", installed_version = installed, offered_version = version,
                        zip_sha256 = packageSha, zip_bytes = zipBytes.LongLength, feed_sha256 = HashBytes(File.ReadAllBytes(feedPath)), root,
                        final_state = lastState, state_samples = samples, http_requests = log, window_closed_by_user = closed,
                    }, new JsonSerializerOptions { WriteIndented = true }), Encoding.UTF8);
                    if (!closed) window.Close();
                    Console.WriteLine("WPF updater-offer live fixture: DONE (" + lastState + ")");
                    exitCode = 0;
                }
                finally { app.Shutdown(); }
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); }
        });
        thread.SetApartmentState(ApartmentState.STA); thread.Start(); thread.Join();
        return exitCode;
    }

    /// <summary>Serves the ZIP at a fixed rate so the download progress is visible to the person looking at it.</summary>
    private sealed class ThrottledStream(byte[] data, int kilobytesPerSecond) : Stream
    {
        private int _position;
        public override bool CanRead => true;
        public override bool CanSeek => false;
        public override bool CanWrite => false;
        public override long Length => data.Length;
        public override long Position { get => _position; set => throw new NotSupportedException(); }
        public override void Flush() { }
        public override int Read(byte[] buffer, int offset, int count)
        {
            var take = Math.Min(Math.Min(count, 64 * 1024), data.Length - _position);
            if (take <= 0) return 0;
            Buffer.BlockCopy(data, _position, buffer, offset, take);
            _position += take;
            Thread.Sleep(Math.Max(1, take * 1000 / (Math.Max(1, kilobytesPerSecond) * 1024)));
            return take;
        }
        public override async Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken)
        {
            var take = Math.Min(Math.Min(count, 64 * 1024), data.Length - _position);
            if (take <= 0) return 0;
            Buffer.BlockCopy(data, _position, buffer, offset, take);
            _position += take;
            await Task.Delay(Math.Max(1, take * 1000 / (Math.Max(1, kilobytesPerSecond) * 1024)), cancellationToken);
            return take;
        }
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }
}
