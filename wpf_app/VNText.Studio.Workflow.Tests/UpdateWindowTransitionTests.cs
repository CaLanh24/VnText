using System.IO;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Windows;
using VNText.Studio.App;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    /// <summary>
    /// Transition regression for the REAL update popup (production UpdateWindow + MainViewModel + WpfUpdateService + the HTTP fixture with a real package ZIP):
    /// offer -> downloading -> ready -> language flip -> recheck.  At every step the visible footer, the banner, the "later" button and the UI Automation name of the
    /// primary button must follow the CURRENT state (native finding: the footer kept the offer text and the primary name stayed "Cap nhat ngay" at READY).
    /// </summary>
    private static int RunUpdateWindowTransitionFixture()
    {
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            UpdateFixture? fixture = null;
            try
            {
                Require(Path.GetFullPath(Environment.GetEnvironmentVariable("VNTEXT_LOCALAPPDATA") ?? "").Contains(Path.DirectorySeparatorChar + "TEST_RUN" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "the fixture needs the TEST_RUN isolation");
                fixture = CreateUpdateFixture("1.0.1");
                ConfigureGitHubSource(fixture, "test-owner", "test-repo");
                var package = File.ReadAllBytes(fixture.PackagePath);
                var digest = HashBytes(package);
                var name = $"wpf-update-1.0.1-{digest[..16]}.zip";
                var apiUrl = new Uri("https://api.github.com/repos/test-owner/test-repo/releases?per_page=100");
                var downloadUrl = new Uri($"https://github.com/test-owner/test-repo/releases/download/v1.0.1/{name}");
                var metadata = GitHubReleaseListWithAsset("v1.0.1", name, "sha256:" + digest, package.LongLength, downloadUrl.AbsoluteUri);
                var gate = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
                var handler = new TestHttpMessageHandler((request, _) =>
                {
                    if (request.RequestUri == apiUrl) return Task.FromResult(JsonResponse(metadata));
                    if (request.RequestUri == downloadUrl)
                    {
                        var response = new HttpResponseMessage(HttpStatusCode.OK) { Content = new StreamContent(new GatedStream(package, gate.Task)) };
                        response.Content.Headers.ContentLength = package.LongLength;
                        return Task.FromResult(response);
                    }
                    throw new HttpRequestException("Unexpected HTTP target: " + request.RequestUri);
                });

                var app = new VNText.Studio.App.App();
                app.InitializeComponent();
                app.ShutdownMode = ShutdownMode.OnExplicitShutdown;
                try
                {
                    UiText.Install(); UiText.SetLanguage("vi");
                    var ownerVm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                    var owner = new MainWindow(ownerVm, null);
                    owner.WindowState = WindowState.Normal; owner.Width = 1043; owner.Height = 720;
                    owner.WindowStartupLocation = WindowStartupLocation.Manual; owner.Left = -4000; owner.Top = 0; owner.ShowActivated = false; owner.ShowInTaskbar = false;
                    owner.Show();
                    var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false, githubHttpHandler: handler, updateInstallRoot: fixture.Root);
                    var source = new ViewModelUpdatePresentation(vm);
                    var window = new UpdateWindow(owner, source);
                    window.WindowStartupLocation = WindowStartupLocation.Manual; window.Left = -4000; window.Top = 0; window.ShowActivated = false;
                    window.Show();
                    PumpFixture(200);

                    void Settle(Func<bool> done, string what)
                    {
                        for (var i = 0; i < 100 && !done(); i++) PumpFixture(100);
                        Require(done(), what + " [status: " + source.Status + "; avail=" + source.Available + " dl=" + source.Downloading + " ready=" + source.Ready + " vm=" + vm.GitHubUpdateState + "]");
                        PumpFixture(150);
                    }
                    string Tr(string vi) => UiText.TranslateDynamic(vi);
                    // The window must always agree with the presentation state: footer text, primary accessible name, "later" label.
                    void Agrees(string step)
                    {
                        var state = UpdateViewState.From(source);
                        Require(window.PrimaryAutomationName == Tr(state.PrimaryLabel), $"{step}: UIA name '{window.PrimaryAutomationName}' follows the state ('{Tr(state.PrimaryLabel)}')");
                        Require(window.StatusText == Tr(state.Status), $"{step}: footer '{window.StatusText}' follows the state status '{Tr(state.Status)}'");
                        var later = state.Downloading || state.Ready ? "Để sau" : "Hủy";
                        Require(window.LaterText == Tr(later), $"{step}: later button '{window.LaterText}' is '{Tr(later)}'");
                    }

                    // offer
                    source.CheckAsync().GetAwaiter().GetResult();
                    Settle(() => source.Available && !source.Downloading && !source.Ready, "offer state reached");
                    Agrees("offer");
                    var offerFooter = window.StatusText;
                    var offerName = window.PrimaryAutomationName;
                    Require(offerName == "Cập nhật ngay", "offer: the primary action is the update action");

                    // downloading (the HTTP body is gated, so this state is observable)
                    var download = source.DownloadAsync();
                    Settle(() => source.Downloading, "downloading state reached");
                    Agrees("downloading");
                    Require(window.PrimaryAutomationName == "Đang tải xuống...", "downloading: UIA name shows the download state");
                    gate.SetResult();
                    download.GetAwaiter().GetResult();

                    // ready
                    Settle(() => source.Ready && !source.Downloading, "ready state reached");
                    Agrees("ready");
                    Require(window.PrimaryAutomationName == "Khởi động lại", "ready: UIA name is the restart action");
                    Require(window.StatusText != offerFooter && !window.StatusText.Contains("chưa tải gói", StringComparison.Ordinal), "ready: the footer must not claim that the package was not downloaded");
                    Require(window.BannerShown && window.BannerText.Contains("sẵn sàng", StringComparison.Ordinal), "ready: the green ready banner is shown");
                    Require(window.LaterText == "Để sau", "ready: the later button defers");

                    // hot language switch at READY and back
                    UiText.SetLanguage("en"); PumpFixture(200);
                    Agrees("ready/en");
                    Require(window.PrimaryAutomationName != "Khởi động lại" && window.PrimaryAutomationName.Length > 0, "ready/en: UIA name is localized");
                    Require(!window.StatusText.Contains("chưa tải gói", StringComparison.Ordinal), "ready/en: footer is not the offer text");
                    UiText.SetLanguage("vi"); PumpFixture(200);
                    Agrees("ready/vi");
                    Require(window.PrimaryAutomationName == "Khởi động lại", "ready/vi: UIA name returns to Vietnamese");

                    // defer keeps the downloaded package ready; a recheck must not regress the window to the offer text
                    source.Defer(false); PumpFixture(200);
                    Agrees("defer");
                    source.CheckAsync().GetAwaiter().GetResult(); PumpFixture(300);
                    Agrees("recheck");
                    Require(!(source.Ready && window.StatusText == offerFooter), "recheck: a ready package never shows the offer footer");

                    window.Close(); owner.Close();
                    Console.WriteLine("WPF update window transition fixture: PASS (offer -> downloading -> ready -> EN/VI -> defer -> recheck; footer, banner, later button and UIA name follow the state)");
                    exitCode = 0;
                }
                finally { app.Shutdown(); }
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); }
            finally { if (fixture is not null) DeleteUpdateFixture(fixture); }
        });
        thread.SetApartmentState(ApartmentState.STA); thread.Start(); thread.Join();
        return exitCode;
    }

    /// <summary>Returns half of the body, then waits for the gate: the DOWNLOADING state stays observable until the test releases it.</summary>
    private sealed class GatedStream(byte[] data, Task gate) : Stream
    {
        private int _position;
        public override bool CanRead => true;
        public override bool CanSeek => false;
        public override bool CanWrite => false;
        public override long Length => data.Length;
        public override long Position { get => _position; set => throw new NotSupportedException(); }
        public override void Flush() { }
        public override int Read(byte[] buffer, int offset, int count) => ReadAsync(buffer, offset, count, CancellationToken.None).GetAwaiter().GetResult();
        public override async Task<int> ReadAsync(byte[] buffer, int offset, int count, CancellationToken cancellationToken)
        {
            if (_position >= data.Length / 2 && !gate.IsCompleted) await gate.WaitAsync(cancellationToken);
            var take = Math.Min(Math.Min(count, _position < data.Length / 2 ? data.Length / 2 - _position : data.Length - _position), data.Length - _position);
            if (take <= 0) return 0;
            Buffer.BlockCopy(data, _position, buffer, offset, take);
            _position += take;
            return take;
        }
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException();
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }
}
