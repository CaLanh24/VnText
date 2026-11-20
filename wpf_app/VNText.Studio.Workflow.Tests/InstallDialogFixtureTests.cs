using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using VNText.PatchInstaller;
using VNText.Studio.App.Services;

namespace VNText.Studio.Workflow.Tests;

/// <summary>The in-app install modal: three actions through the one installer service, per-font status lines, ownership truth, and the clean-original confirmation.</summary>
internal static partial class Program
{
    private static int RunInstallDialogFixture(string[] args)
    {
        var index = Array.IndexOf(args, "--install-dialog-fixture");
        var outDir = index >= 0 && index + 1 < args.Length ? args[index + 1] : "";
        if (!string.IsNullOrWhiteSpace(outDir)) Directory.CreateDirectory(outDir);
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            var work = Path.Combine(Path.GetTempPath(), "vntext-install-dialog-" + Guid.NewGuid().ToString("N"));
            try
            {
                var app = new Application { ShutdownMode = ShutdownMode.OnExplicitShutdown };
                foreach (var dictionary in new[] { "DesignTokens", "IconGeometries", "ControlStyles" })
                    app.Resources.MergedDictionaries.Add(new ResourceDictionary { Source = new Uri($"pack://application:,,,/VNText.Studio.App;component/Themes/{dictionary}.xaml") });
                var game = Path.Combine(work, "game-root");
                foreach (var directory in new[] { "game", "renpy", "lib" }) Directory.CreateDirectory(Path.Combine(game, directory));
                File.WriteAllBytes(Path.Combine(game, "Game.exe"), new byte[] { 1 });
                File.WriteAllBytes(Path.Combine(game, "game/script.rpy"), Encoding.UTF8.GetBytes("label start:\n    return\n"));
                var patch = Path.Combine(work, "patch");
                const string overlay = "game/tl/vietnamese/vntext.rpy";
                var payloadBytes = Encoding.UTF8.GetBytes("# VNText language-scoped text font support v1\n");
                var payload = Path.Combine(patch, "COPY_TO_GAME_ROOT", overlay.Replace('/', Path.DirectorySeparatorChar));
                Directory.CreateDirectory(Path.GetDirectoryName(payload)!);
                File.WriteAllBytes(payload, payloadBytes);
                var evidence = JsonDocument.Parse("""
                    {"glyph_status":"PASS_WITH_FALLBACK","primary_missing":["U+266B"],"glyph_fallback":{"sha256":"x"},
                     "font_outcome_counts":{"REPLACED":1,"UNRESOLVED":1,"OK":1},
                     "font_outcomes":[{"source":"fonts/Gothic.ttf","outcome":"REPLACED","status":"NEEDS_VIETNAMESE_FONT"},
                                      {"source":"fonts/pack.ttc","outcome":"UNRESOLVED","status":"UNSUPPORTED_FORMAT"},
                                      {"source":"fonts/Full.ttf","outcome":"OK","status":"COVERS_TRANSLATION"}]}
                    """).RootElement.Clone();
                var manifest = new PatchManifest(1, "0.1.26", "2026-11-21T00:00:00Z", "",
                    new List<PatchFile> { new(overlay, Convert.ToHexString(SHA256.HashData(payloadBytes)).ToLowerInvariant(), "", false) }, "", "Game.exe", "renpy",
                    new List<GameCheck> { new("game/script.rpy", Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(Path.Combine(game, "game/script.rpy")))).ToLowerInvariant()) }, evidence);
                File.WriteAllText(Path.Combine(patch, "patch_manifest.json"), JsonSerializer.Serialize(manifest));

                var owner = new Window { Title = "Install dialog fixture owner", Width = 900, Height = 600 };
                Application.Current.MainWindow = owner;
                owner.Loaded += (_, _) => owner.Dispatcher.BeginInvoke(new Action(() =>
                {
                    try
                    {
                        var dialog = new PatchInstallDialog(patch, game, () => true);
                        var window = (AppDialogWindow)typeof(PatchInstallDialog).GetField("_window", BindingFlags.NonPublic | BindingFlags.Instance)!.GetValue(dialog)!;
                        var refresh = typeof(PatchInstallDialog).GetMethod("Refresh", BindingFlags.NonPublic | BindingFlags.Instance)!;
                        var timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(60) };
                        var step = 0;
                        Exception? failure = null;
                        timer.Tick += (_, _) =>
                        {
                            try
                            {
                                if (!window.IsVisible) return;
                                step++;
                                Console.Error.WriteLine($"install-dialog step {step}; windows={string.Join("|", app.Windows.OfType<Window>().Select(w => w.GetType().Name + ":" + w.IsVisible))}");
                                var buttons = Descendants<Button>(window).ToList();
                                Button Named(string label) => buttons.Single(button => (button.Content as string) == label);
                                if (step == 1)
                                {
                                    Require(Named("Cài patch").IsEnabled, "install is available for a valid, uninstalled game");
                                    Require(!Named("Gỡ và hoàn nguyên").IsEnabled && !Named("Về bản gốc sạch").IsEnabled, "uninstall actions are disabled before install");
                                    var text = string.Join("\n", Descendants<TextBlock>(window).Select(block => block.Text));
                                    Require(text.Contains("Font trong game:"), "per-font counts are shown in the dialog");
                                    Require(text.Contains("Chưa xử lý được · fonts/pack.ttc"), "an unresolved font is named with its outcome");
                                    Require(text.Contains("Đã thay trong patch · fonts/Gothic.ttf"), "a replaced font is named with its outcome");
                                    Require(text.Contains("Font đủ ký tự bản dịch"), "PASS_WITH_FALLBACK counts as covered text");
                                    Shot(window, outDir, "install-dialog-ready.png");
                                    new InstallerService(patch).Install(game);                        // same service the dialog drives
                                    refresh.Invoke(dialog, null);
                                }
                                else if (step == 2)
                                {
                                    Require(!Named("Cài patch").IsEnabled && Named("Gỡ và hoàn nguyên").IsEnabled && Named("Về bản gốc sạch").IsEnabled, "installed state offers both uninstall modes");
                                    Shot(window, outDir, "install-dialog-installed.png");
                                    var clean = Named("Về bản gốc sạch");
                                    window.Dispatcher.BeginInvoke(new Action(() => clean.RaiseEvent(new RoutedEventArgs(Button.ClickEvent))));   // the confirmation is modal: open it after this tick returns
                                }
                                else
                                {
                                    var confirm = app.Windows.OfType<AppDialogWindow>().FirstOrDefault(candidate => !ReferenceEquals(candidate, window) && candidate.IsVisible);
                                    if (confirm is null) { if (step > 60) throw new InvalidOperationException("clean-original confirmation never appeared"); return; }
                                    timer.Stop();
                                    var confirmText = string.Join("\n", Descendants<TextBox>(confirm).Select(box => box.Text));
                                    Require(confirmText.Contains("bản gốc đầu tiên") && confirmText.Contains("không bị xóa"), "the confirmation names the first original and unmanaged files");
                                    Shot(confirm, outDir, "install-dialog-confirm-clean.png");
                                    var no = Descendants<Button>(confirm).Single(button => (button.Content as string) == "Không");
                                    confirm.Dispatcher.BeginInvoke(new Action(() =>
                                    {
                                        no.RaiseEvent(new RoutedEventArgs(Button.ClickEvent));    // safe default: nothing changes
                                        Require(File.Exists(Path.Combine(game, overlay.Replace('/', '\\'))), "declining the confirmation leaves the installed patch untouched");
                                        exitCode = 0;
                                        window.Close();
                                        owner.Close();
                                        Dispatcher.CurrentDispatcher.InvokeShutdown();
                                    }));
                                }
                            }
                            catch (Exception ex) { failure = ex; timer.Stop(); try { window.Close(); } catch { } owner.Close(); Dispatcher.CurrentDispatcher.BeginInvokeShutdown(DispatcherPriority.Background); }
                        };
                        timer.Start();
                        dialog.ShowDialog();
                        if (failure is not null) throw failure;
                    }
                    catch (Exception ex) { Console.Error.WriteLine("install-dialog fixture failed: " + ex); exitCode = 1; owner.Close(); }
                }));
                owner.Show();
                Dispatcher.Run();
            }
            catch (Exception ex) { Console.Error.WriteLine("install-dialog fixture failed: " + ex); exitCode = 1; }
            finally { try { Directory.Delete(work, true); } catch { } }
        });
        thread.IsBackground = true;
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join(TimeSpan.FromMinutes(2));
        Console.WriteLine("{\"fixture\":\"install-dialog\",\"pass\":" + (exitCode == 0 ? "true" : "false") + "}");
        return exitCode;
    }

    private static IEnumerable<T> Descendants<T>(DependencyObject root) where T : DependencyObject
    {
        for (var i = 0; i < VisualTreeHelper.GetChildrenCount(root); i++)
        {
            var child = VisualTreeHelper.GetChild(root, i);
            if (child is T match) yield return match;
            foreach (var nested in Descendants<T>(child)) yield return nested;
        }
    }

    private static void Shot(Window window, string outDir, string name)
    {
        if (string.IsNullOrWhiteSpace(outDir)) return;
        var width = Math.Max(1, (int)Math.Ceiling(window.ActualWidth)); var height = Math.Max(1, (int)Math.Ceiling(window.ActualHeight));
        var bitmap = new RenderTargetBitmap(width, height, 96, 96, PixelFormats.Pbgra32);
        bitmap.Render(window);
        var encoder = new PngBitmapEncoder(); encoder.Frames.Add(BitmapFrame.Create(bitmap));
        using var stream = File.Create(Path.Combine(outDir, name)); encoder.Save(stream);
    }
}
