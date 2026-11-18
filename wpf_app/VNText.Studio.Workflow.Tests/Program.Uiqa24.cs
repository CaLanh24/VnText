using System.IO;
using System.Security.Cryptography;
using System.Text.Json;
using VNText.PatchInstaller;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private static int RunUiqa24()
    {
        var result = 1;
        var thread = new Thread(() =>
        {
            var app = new VNText.Studio.App.App(); app.InitializeComponent();
            app.ShutdownMode = System.Windows.ShutdownMode.OnExplicitShutdown;
            try
            {
                using var vm = new MainViewModel(new FakePathPicker(), new PythonWorkerHost(), startWorker: false);
                vm.InputPath = Path.Combine(TestTempRoot(), "status-game");
                vm.TestSetActiveTask("owned-extract", "extract"); vm.StatusText = "Đã lấy text xong: 120 dòng";
                vm.TestMarkTaskTerminal("owned-extract");
                foreach (var task in new[] { "translate", "resources", "patch", "image_batch" })
                    foreach (var status in new[] { "Lỗi", "Hoàn tất", "Đã hủy" })
                    {
                        vm.TestSetActiveTask(task + status, task); vm.StatusText = status;
                        vm.TestMarkTaskTerminal(task + status);
                        Require(vm.ExtractStatusText == "Đã lấy text xong: 120 dòng", "Extract keeps its owned status after " + task + status);
                    }
                vm.TestSetActiveTask("owned-error", "extract"); vm.StatusText = "Lỗi worker"; vm.TestMarkTaskTerminal("owned-error");
                Require(vm.ExtractStatusText == "Lỗi worker", "Extract does retain its own failure");
                vm.InputPath = Path.Combine(TestTempRoot(), "different-game");
                Require(vm.ExtractStatusText != "Lỗi worker", "A new source never inherits another source's status");
                Console.WriteLine("PASS task-owned Extract status");

                var root = Path.Combine(TestTempRoot(), "uiqa24-core-" + Guid.NewGuid().ToString("N"));
                Directory.CreateDirectory(root);
                try
                {
                    var game = Path.Combine(root, "game"); var patch = Path.Combine(root, "patch");
                    Directory.CreateDirectory(Path.Combine(game, "game")); Directory.CreateDirectory(Path.Combine(game, "renpy")); Directory.CreateDirectory(Path.Combine(game, "lib"));
                    File.WriteAllText(Path.Combine(game, "Game.exe"), "synthetic executable");
                    var source = Path.Combine(game, "game", "script.rpy"); File.WriteAllText(source, "label start:\n    \"Hello\"\n");
                    var relative = "game/tl/vietnamese/vntext_font_fixture.ttf";
                    var payload = Path.Combine(patch, "COPY_TO_GAME_ROOT", relative);
                    Directory.CreateDirectory(Path.GetDirectoryName(payload)!); File.WriteAllBytes(payload, new byte[] { 1,2,3,4 });
                    var target = Path.Combine(game, relative); Directory.CreateDirectory(Path.GetDirectoryName(target)!); File.WriteAllBytes(target, new byte[] { 9,8,7 });
                    string Hash(string p) => Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(p)));
                    var original = File.ReadAllBytes(target);
                    var manifest = new PatchManifest(1, "fixture", "", "", new() { new PatchFile(relative, Hash(payload), Hash(target), true) }, Engine: "renpy", GameChecks: new() { new GameCheck("game/script.rpy", Hash(source)) });
                    var manifestPath = Path.Combine(patch, "patch_manifest.json");
                    File.WriteAllText(manifestPath, JsonSerializer.Serialize(manifest));
                    var service = new InstallerService(patch); var progress = new List<string>();
                    service.Install(game, progress.Add); Require(File.ReadAllBytes(target).SequenceEqual(File.ReadAllBytes(payload)), "Install copies verified font payload");
                    service.Uninstall(game, progress.Add); Require(File.ReadAllBytes(target).SequenceEqual(original), "Uninstall restores original font bytes");
                    Require(progress.Count > 0, "Shared core reports bounded progress to caller");
                    using var badFont = JsonDocument.Parse("{\"glyph_status\":\"MISSING\"}");
                    manifest = manifest with { FontPreflight = badFont.RootElement.Clone() };
                    File.WriteAllText(manifestPath, JsonSerializer.Serialize(manifest));
                    var refused = false; try { service.Install(game); } catch (InvalidOperationException) { refused = true; }
                    Require(refused && File.ReadAllBytes(target).SequenceEqual(original), "Missing glyph report refuses without game mutation");
                    Console.WriteLine("PASS shared install/font restoration and glyph guard (synthetic bytes, not font rendering)");
                }
                finally { Directory.Delete(root, true); }
                result = 0;
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); }
            finally { app.Shutdown(); }
        });
        thread.SetApartmentState(ApartmentState.STA); thread.Start(); thread.Join(); return result;
    }
}
