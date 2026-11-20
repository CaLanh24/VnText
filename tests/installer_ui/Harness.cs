using System.Drawing;
using System.Drawing.Imaging;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows.Forms;
using VNText.PatchInstaller;

internal static class Harness
{
    private static readonly List<string> Results = new();
    private static bool allPass = true;

    private static void Check(string name, bool ok, string detail = "")
    {
        Results.Add("{\"check\":" + JsonSerializer.Serialize(name) + ",\"pass\":" + (ok ? "true" : "false") + (ok ? "" : ",\"detail\":" + JsonSerializer.Serialize(detail)) + "}");
        allPass &= ok;
    }

    private static string Sha(byte[] data) => Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();
    private static byte[] Bytes(string text) => new UTF8Encoding(false).GetBytes(text);

    private static double Luminance(Color c)
    {
        static double L(double v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.Pow((v + 0.055) / 1.055, 2.4); }
        return 0.2126 * L(c.R) + 0.7152 * L(c.G) + 0.0722 * L(c.B);
    }

    private static double Contrast(Color a, Color b)
    {
        var (hi, lo) = (Math.Max(Luminance(a), Luminance(b)), Math.Min(Luminance(a), Luminance(b)));
        return (hi + 0.05) / (lo + 0.05);
    }

    private static T Field<T>(object target, string name) => (T)target.GetType().GetField(name, BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static)!.GetValue(target)!;
    private static T Static<T>(Type type, string name) => (T)type.GetField(name, BindingFlags.NonPublic | BindingFlags.Static)!.GetValue(null)!;

    private static void Pump() { for (var i = 0; i < 6; i++) { Application.DoEvents(); Thread.Sleep(30); } }

    [STAThread]
    public static int Main(string[] args)
    {
        var shots = args.Length > 0 ? Path.GetFullPath(args[0]) : Path.Combine(Path.GetTempPath(), "vntext-installer-ui");
        Directory.CreateDirectory(shots);
        var theme = InstallerTheme.Dark ? "dark" : "light";
        var work = Path.Combine(Path.GetTempPath(), "vntext-ui-" + Guid.NewGuid().ToString("N"));
        var game = Path.Combine(work, "game-root");
        foreach (var directory in new[] { "game", "renpy", "lib" }) Directory.CreateDirectory(Path.Combine(game, directory));
        File.WriteAllBytes(Path.Combine(game, "Game.exe"), Bytes("exe"));
        File.WriteAllBytes(Path.Combine(game, "game/script.rpy"), Bytes("label start:\n    return\n"));

        // A patch with real per-font evidence so the summary lines are exercised.
        var patch = Path.Combine(work, "patch");
        const string overlay = "game/tl/vietnamese/vntext.rpy";
        var payload = Path.Combine(patch, "COPY_TO_GAME_ROOT", overlay.Replace('/', Path.DirectorySeparatorChar));
        Directory.CreateDirectory(Path.GetDirectoryName(payload)!);
        File.WriteAllBytes(payload, Bytes("# VNText language-scoped text font support v1\n"));
        var fontEvidence = JsonDocument.Parse("""
            {"glyph_status":"PASS_WITH_FALLBACK","primary_missing":["U+266B"],"glyph_fallback":{"sha256":"x"},
             "font_outcome_counts":{"REPLACED":1,"UNRESOLVED":2,"OK":1},
             "font_outcomes":[{"source":"fonts/Gothic.ttf","outcome":"REPLACED","status":"NEEDS_VIETNAMESE_FONT","why":""},
                              {"source":"fonts/pack.ttc","outcome":"UNRESOLVED","status":"UNSUPPORTED_FORMAT","why":""},
                              {"source":"fonts/web.woff2","outcome":"UNRESOLVED","status":"UNSUPPORTED_FORMAT","why":""},
                              {"source":"fonts/Full.ttf","outcome":"OK","status":"COVERS_TRANSLATION","why":""}],
             "image_candidates":{"candidates":[{"asset":"gui/menu.png"}]}}
            """).RootElement.Clone();
        var manifest = new PatchManifest(1, "0.1.26", "2026-11-21T00:00:00Z", "",
            new List<PatchFile> { new(overlay, Sha(Bytes("# VNText language-scoped text font support v1\n")), "", false) }, "", "Game.exe", "renpy",
            new List<GameCheck> { new("game/script.rpy", Sha(File.ReadAllBytes(Path.Combine(game, "game/script.rpy")))) }, fontEvidence);
        File.WriteAllText(Path.Combine(patch, "patch_manifest.json"), JsonSerializer.Serialize(manifest));

        ApplicationConfiguration.Initialize();
        using var form = new InstallerForm(patch);
        form.Show();
        Pump();

        var card = Field<Control>(form, "_card");
        var flow = Field<Control>(form, "_flow");
        var install = Field<Button>(form, "_install");
        var uninstall = Field<Button>(form, "_uninstall");
        var clean = Field<Button>(form, "_restoreClean");
        var confirm = Field<Button>(form, "_confirm");
        var cancel = Field<Button>(form, "_cancelConfirm");
        var path = Field<TextBox>(form, "_gamePath");
        var status = Field<Label>(form, "_status");
        var summary = Field<Label>(form, "_summary");
        var type = typeof(InstallerForm);
        var showConfirm = type.GetMethod("ShowConfirm", BindingFlags.NonPublic | BindingFlags.Instance)!;
        var ink = Static<Color>(type, "Ink"); var muted = Static<Color>(type, "Muted"); var surface = Static<Color>(type, "Surface"); var canvas = Static<Color>(type, "Canvas");

        void Shot(string name) { Pump(); using var bitmap = new Bitmap(form.Width, form.Height); form.DrawToBitmap(bitmap, new Rectangle(Point.Empty, form.Size)); bitmap.Save(Path.Combine(shots, $"{theme}-{name}.png"), ImageFormat.Png); }

        void Compact(string state)
        {
            Pump();
            var contentBottom = flow.Controls.Cast<Control>().Max(c => c.Bottom) + flow.Top + card.Top + card.Padding.Bottom + 16;     // last row + card padding + frame padding
            var slack = form.ClientSize.Height - contentBottom;
            Check($"{theme}/{state}: window height follows its content (no blank surface)", Math.Abs(slack) <= 8, $"client={form.ClientSize.Height} content={contentBottom}");
            var work = Screen.FromControl(form).WorkingArea;
            Check($"{theme}/{state}: window fits the screen and is not oversized", form.Height <= work.Height && form.ClientSize.Width <= 720, $"{form.Size}");
            var visible = flow.Controls.Cast<Control>().Where(c => c is FlowLayoutPanel).Cast<FlowLayoutPanel>().First().Controls.Cast<Control>().Where(c => c.Visible).ToList();
            if (visible.Count > 0)
            {
                var footer = flow.Controls.Cast<Control>().OfType<FlowLayoutPanel>().First();
                var rightMost = visible.Max(c => c.Right);
                Check($"{theme}/{state}: footer buttons sit at the right edge like the in-app modal", footer.ClientSize.Width - rightMost <= 4, $"gap={footer.ClientSize.Width - rightMost}");
                Check($"{theme}/{state}: footer fits one row at the in-app width", visible.Select(c => c.Top).Distinct().Count() == 1, string.Join(",", visible.Select(c => c.Top)));
                Check($"{theme}/{state}: footer buttons do not overlap", visible.GroupBy(c => c.Top).All(row => row.OrderBy(c => c.Left).Zip(row.OrderBy(c => c.Left).Skip(1)).All(p => p.First.Right <= p.Second.Left)), "overlap");
            }
        }

        Check($"{theme}: dialog is fixed, not maximisable, content-sized", form.FormBorderStyle == FormBorderStyle.FixedDialog && !form.MaximizeBox, form.FormBorderStyle.ToString());
        Check($"{theme}: ink and muted text meet contrast on the card", Contrast(ink, surface) >= 4.5 && Contrast(muted, surface) >= 4.5, $"{Contrast(ink, surface):F1}/{Contrast(muted, surface):F1}");
        Check($"{theme}: card is distinct from the canvas", surface != canvas);
        Check($"{theme}: summary carries the file count and the per-font truth", summary.Text.Contains("Số file sẽ cài: 1") && summary.Text.Contains("fonts/pack.ttc") && summary.Text.Contains("Chưa xử lý được") && summary.Text.Contains("DejaVu") && summary.Text.Split((char)10).Length <= 8, summary.Text);
        Check($"{theme}: summary says there is no automatic image text recognition", summary.Text.Contains("không được nhận diện tự động"), summary.Text);
        Compact("empty");
        Shot("1-empty");

        path.Text = game;
        Pump();
        Check($"{theme}: a valid game enables Install and makes it the default button", install.Enabled && form.AcceptButton == install && !uninstall.Enabled && !clean.Enabled, status.Text);
        Compact("ready");
        Shot("2-ready");

        var tabbed = new List<Control> { path, Field<Button>(form, "_browse"), clean, uninstall, install };
        Check($"{theme}: tab order follows reading order and every control is a tab stop", tabbed.Zip(tabbed.Skip(1)).All(p => p.First.TabIndex < p.Second.TabIndex) && tabbed.All(c => c.TabStop), "tab order");

        install.PerformClick();
        Pump();
        Check($"{theme}: confirmation shows Confirm/Back, focus starts on the safe choice, Enter is not hijacked", confirm.Visible && cancel.Visible && !install.Visible && cancel.Focused && form.AcceptButton == null, $"focus={form.ActiveControl?.Text}");
        Compact("confirm-install");
        Shot("3-confirm");
        var keyDown = typeof(Form).GetMethod("OnKeyDown", BindingFlags.NonPublic | BindingFlags.Instance)!;
        keyDown.Invoke(form, new object[] { new KeyEventArgs(Keys.Escape) });
        Pump();
        Check($"{theme}: Escape backs out of the confirmation without closing", !confirm.Visible && install.Visible && !form.IsDisposed, "escape");

        // Install for real through the same service, then exercise the installed state and the clean-original confirmation.
        var state = new InstallerService(patch).Install(game);
        path.Text = ""; path.Text = game;
        Pump();
        Check($"{theme}: installed state enables Uninstall and Clean original, not Install", uninstall.Enabled && clean.Enabled && !install.Enabled, status.Text);
        Compact("installed");
        Shot("4-installed");
        clean.PerformClick();
        Pump();
        Check($"{theme}: clean-original confirmation names the first original and unmanaged files", confirm.Text == "Xác nhận về gốc" && status.Text.Contains("bản gốc đầu tiên") && status.Text.Contains("không bị xóa"), status.Text);
        Compact("confirm-clean");
        Shot("5-confirm-clean");
        keyDown.Invoke(form, new object[] { new KeyEventArgs(Keys.Escape) });
        Pump();
        new InstallerService(patch).Uninstall(game, null, UninstallMode.CleanOriginal);

        keyDown.Invoke(form, new object[] { new KeyEventArgs(Keys.Escape) });
        Pump();
        Check($"{theme}: Escape closes an idle dialog", form.IsDisposed || !form.Visible, "closed");

        Console.WriteLine("{\"pass\":" + (allPass ? "true" : "false") + ",\"theme\":\"" + theme + "\",\"checks\":[" + string.Join(",", Results) + "]}");
        try { Directory.Delete(work, true); } catch { }
        return allPass ? 0 : 1;
    }
}
