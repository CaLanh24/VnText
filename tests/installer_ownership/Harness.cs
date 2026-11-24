using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using VNText.PatchInstaller;

internal static class Harness
{
    private static readonly List<string> Results = new();
    private static bool allPass = true;
    private const string Overlay = "game/tl/vietnamese/vntext.rpy";
    private const string Activation = "game/zzz_vntext_vietnamese.rpy";

    private static void Check(string name, bool ok, string detail = "")
    {
        Results.Add("{\"check\":" + JsonSerializer.Serialize(name) + ",\"pass\":" + (ok ? "true" : "false") + (ok ? "" : ",\"detail\":" + JsonSerializer.Serialize(detail)) + "}");
        allPass &= ok;
    }

    private static string Sha(byte[] data) => Convert.ToHexString(SHA256.HashData(data)).ToLowerInvariant();
    private static string Sha(string path) => Sha(File.ReadAllBytes(path));
    private static byte[] Bytes(string text) => new UTF8Encoding(false).GetBytes(text);

    private static string NewGame(string work, string name)
    {
        var root = Path.Combine(work, name);
        foreach (var directory in new[] { "game", "renpy", "lib" }) Directory.CreateDirectory(Path.Combine(root, directory));
        File.WriteAllBytes(Path.Combine(root, "Game.exe"), Bytes("exe"));
        File.WriteAllBytes(Path.Combine(root, "game/script.rpy"), Bytes("label start:\n    return\n"));
        return root;
    }

    private sealed record Spec(string Path, string Content, bool OriginalExists, string? OriginalContent);

    /// <summary>A patch folder exactly as the generator writes it: payload + manifest bound to the game's current files.</summary>
    private static InstallerService MakePatch(string work, string name, string version, string gameRoot, params Spec[] files)
    {
        var dir = Path.Combine(work, name);
        Directory.CreateDirectory(dir);
        var entries = new List<PatchFile>();
        foreach (var file in files)
        {
            var payload = Path.Combine(dir, "COPY_TO_GAME_ROOT", file.Path.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(payload)!);
            File.WriteAllBytes(payload, Bytes(file.Content));
            entries.Add(new PatchFile(file.Path, Sha(Bytes(file.Content)), file.OriginalExists ? Sha(Bytes(file.OriginalContent ?? "")) : "", file.OriginalExists));
        }
        var manifest = new PatchManifest(1, version, "2026-11-21T00:00:00Z", "", entries, "", "Game.exe", "renpy",
            new List<GameCheck> { new("game/script.rpy", Sha(Path.Combine(gameRoot, "game/script.rpy"))) });
        File.WriteAllText(Path.Combine(dir, "patch_manifest.json"), JsonSerializer.Serialize(manifest));
        return new InstallerService(dir);
    }

    /// <summary>What Ren'Py writes after running the game: a compiled cache bound to the source's MD5.</summary>
    private static void CompileCache(string root, string relative, string source)
    {
        var path = Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar) + "c");
        var bytes = new List<byte>(Encoding.ASCII.GetBytes("RENPY RPC2"));
        bytes.AddRange(new byte[40]);
        bytes.AddRange(MD5.HashData(Bytes(source)));
        File.WriteAllBytes(path, bytes.ToArray());
    }

    private static string? Read(string root, string relative)
    {
        var path = Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar));
        return File.Exists(path) ? File.ReadAllText(path) : null;
    }

    private static bool Throws(Action action, string contains, out string message)
    {
        try { action(); message = "no exception"; return false; }
        catch (Exception ex) { message = ex.Message; return ex.Message.Contains(contains, StringComparison.OrdinalIgnoreCase); }
    }

    private static string Receipt(string root) => Path.Combine(root, ".vntext", "ownership.json");

    private static string Snapshot(string root)
    {
        var lines = Directory.EnumerateFiles(root, "*", SearchOption.AllDirectories).OrderBy(p => p, StringComparer.Ordinal)
            .Select(p => Path.GetRelativePath(root, p) + "=" + Sha(p));
        return string.Join("\n", lines);
    }

    public static int Main()
    {
        var work = Path.Combine(Path.GetTempPath(), "vntext-ownership-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(work);
        const string v24 = "# VNText language-scoped text font support v1\ntranslate vietnamese style default:\n    font \"old.ttf\"\n";
        const string v25 = "# VNText language-scoped text font support v1\ntranslate vietnamese style default:\n    font \"new.ttf\"\n";
        const string act = "# activation\ntranslate None python:\n    pass\n";

        // 1. install old (clean game), upgrade to new, game runs (compiled cache), then step back: previous, then the clean original.
        {
            var game = NewGame(work, "g1");
            var old = MakePatch(work, "p24", "0.1.24", game, new Spec(Overlay, v24, false, null), new Spec(Activation, act, false, null));
            var state24 = old.Install(game);
            Check("old install writes both files and a receipt", Read(game, Overlay) == v24 && File.Exists(Receipt(game)) && state24.PatchId is { Length: 64 });
            CompileCache(game, Overlay, v24);
            var next = MakePatch(work, "p25", "0.1.25", game, new Spec(Overlay, v25, true, v24), new Spec(Activation, act, true, act));
            Check("preflight describes a proven upgrade", string.Join("|", next.DescribeOwnership(game)).Contains("nâng cấp") );
            var state25 = next.Install(game);
            Check("upgrade installs the new overlay and says it is an upgrade", Read(game, Overlay) == v25 && string.Join("|", state25.Notes ?? new()).Contains("nâng cấp"));
            Check("receipt keeps the first original as 'did not exist' with two layers", JsonDocument.Parse(File.ReadAllText(Receipt(game))).RootElement.GetProperty("paths").GetProperty(Overlay).GetProperty("layers").GetArrayLength() == 2
                && !JsonDocument.Parse(File.ReadAllText(Receipt(game))).RootElement.GetProperty("paths").GetProperty(Overlay).GetProperty("first_original_exists").GetBoolean());
            Check("the older patch refuses to uninstall under a newer layer", Throws(() => old.Uninstall(game), "mới hơn", out var m1), "");
            CompileCache(game, Overlay, v25);
            next.Uninstall(game);
            Check("uninstalling the new patch restores the previous payload and the previous cache", Read(game, Overlay) == v24 && File.Exists(Path.Combine(game, "game/tl/vietnamese/vntext.rpyc")));
            Check("receipt still holds the first original after the step back", File.Exists(Receipt(game)));
            old.Uninstall(game);
            Check("uninstalling the old patch leaves the game clean", !File.Exists(Path.Combine(game, Overlay.Replace('/', '\\'))) && !File.Exists(Path.Combine(game, Activation)) && !File.Exists(Path.Combine(game, "game/tl/vietnamese/vntext.rpyc")));
            Check("no receipt or backup debris remains", !Directory.Exists(Path.Combine(game, ".vntext")) && !Directory.Exists(old.BackupDirectory) && !Directory.Exists(next.BackupDirectory) && !File.Exists(old.StatePath) && !File.Exists(next.StatePath));
        }

        // 2. clean-original restore from the newest layer removes every VNText layer and its compiled caches; older state says so.
        {
            var game = NewGame(work, "g2");
            var original = Snapshot(game);
            var old = MakePatch(work, "q24", "0.1.24", game, new Spec(Overlay, v24, false, null), new Spec(Activation, act, false, null));
            old.Install(game);
            CompileCache(game, Overlay, v24);
            var next = MakePatch(work, "q25", "0.1.25", game, new Spec(Overlay, v25, true, v24), new Spec(Activation, act, true, act));
            next.Install(game);
            CompileCache(game, Overlay, v25);
            var result = next.Uninstall(game, null, UninstallMode.CleanOriginal);
            Check("clean-original restore returns the game byte-identical to before any VNText patch", Snapshot(game) == original, Snapshot(game));
            Check("clean-original restore reports the removed older layer", string.Join("|", result.Notes).Contains("lớp patch cũ hơn"));
            var cleaned = Snapshot(game);
            var leftover = Throws(() => old.Uninstall(game), "đã bị thay thế", out var m2)
                || (m2 == "no exception" && !File.Exists(old.StatePath));
            Check("the superseded older patch has nothing left to undo: it says so, or tidies its own stale record without touching the game", leftover && Snapshot(game) == cleaned, m2);
        }

        // 3. refuse layering when the new patch was not built from the active install; tamper of an owned file; both leave the game untouched.
        {
            var game = NewGame(work, "g3");
            var old = MakePatch(work, "r24", "0.1.24", game, new Spec(Overlay, v24, false, null), new Spec(Activation, act, false, null));
            old.Install(game);
            var before = Snapshot(game);
            var fromClean = MakePatch(work, "r25", "0.1.25", game, new Spec(Overlay, v25, false, null), new Spec(Activation, act, false, null));
            Check("a patch built from a different state is refused as layering", Throws(() => fromClean.Install(game), "không nâng cấp chứng minh được", out var m3), m3);
            Check("the refused layering wrote nothing", Snapshot(game) == before && !Directory.Exists(fromClean.BackupDirectory) && !File.Exists(fromClean.StatePath));
            File.WriteAllText(Path.Combine(game, Overlay.Replace('/', '\\')), v24 + "# user edit\n");
            var proven = MakePatch(work, "r25b", "0.1.25", game, new Spec(Overlay, v25, true, v24 + "# user edit\n"), new Spec(Activation, act, true, act));
            var edited = Snapshot(game);
            Check("an owned file edited outside VNText is never layered over", Throws(() => proven.Install(game), "đã bị sửa ngoài VNText", out var m4), m4);
            Check("the tampered game is left byte-identical", Snapshot(game) == edited);
        }

        // 4. torn upgrade: the second file does not match its manifest, so the first (already written) file must roll back and the receipt stay as it was.
        {
            var game = NewGame(work, "g4");
            var old = MakePatch(work, "s24", "0.1.24", game, new Spec(Overlay, v24, false, null), new Spec(Activation, act, false, null));
            old.Install(game);
            var before = Snapshot(game);
            var mismatch = MakePatch(work, "s25a", "0.1.25", game, new Spec(Overlay, v25, true, v24), new Spec(Activation, act, true, "something else"));
            Check("an upgrade whose files do not match the active install is refused before any write", Throws(() => mismatch.Install(game), "không nâng cấp chứng minh được", out var m5a), m5a);
            Check("the refused upgrade left everything as it was", Snapshot(game) == before && !Directory.Exists(mismatch.BackupDirectory) && !File.Exists(mismatch.StatePath));
            File.WriteAllText(Path.Combine(game, "game", "blocked"), "a file where a folder is needed");
            before = Snapshot(game);
            var torn = MakePatch(work, "s25", "0.1.25", game, new Spec(Overlay, v25, true, v24), new Spec("game/blocked/extra.rpy", "label x:" + (char)10 + "    return", false, null));
            Check("a torn upgrade fails after the first file was already written", Throws(() => torn.Install(game), "", out var m5), m5);
            Check("a torn upgrade rolls back every file, the receipt, and leaves no backup or state", Snapshot(game) == before && Read(game, Overlay) == v24 && !Directory.Exists(torn.BackupDirectory) && !File.Exists(torn.StatePath));
            File.Delete(Path.Combine(game, "game", "blocked"));
            old.Uninstall(game);
            Check("the previous patch can still be uninstalled cleanly after the torn upgrade", !File.Exists(Path.Combine(game, Activation)) && !Directory.Exists(Path.Combine(game, ".vntext")));
        }

        // 5. an install from before receipts existed: truthfully a previous VNText overlay, never presented as a clean original.
        {
            var game = NewGame(work, "g5");
            Directory.CreateDirectory(Path.GetDirectoryName(Path.Combine(game, Overlay.Replace('/', '\\')))!);
            File.WriteAllText(Path.Combine(game, Overlay.Replace('/', '\\')), v24);
            File.WriteAllText(Path.Combine(game, Activation), act);
            var next = MakePatch(work, "t25", "0.1.25", game, new Spec(Overlay, v25, true, v24), new Spec(Activation, act, true, act));
            var preflight = string.Join("|", next.DescribeOwnership(game));
            Check("preflight says the old overlay has no receipt and is not a clean original", preflight.Contains("không có biên nhận") && preflight.Contains("không chứng minh được game gốc sạch"));
            var state = next.Install(game);
            Check("install notes carry the same truth", string.Join("|", state.Notes ?? new()).Contains("không có biên nhận"));
            var before = Snapshot(game);
            Check("clean-original restore is refused when the first original is an unreceipted VNText overlay", Throws(() => next.Uninstall(game, null, UninstallMode.CleanOriginal), "không phải game gốc sạch", out var m6), m6);
            Check("the refused clean restore changed nothing", Snapshot(game) == before);
            var undone = next.Uninstall(game);
            Check("uninstall puts back the previous overlay and says so", Read(game, Overlay) == v24 && string.Join("|", undone.Notes).Contains("không phải game gốc sạch"));
        }

        // 6. a Vietnamese overlay the user (or another tool) made: kept byte-for-byte, restored on either uninstall mode, never deleted.
        foreach (var mode in new[] { UninstallMode.Previous, UninstallMode.CleanOriginal })
        {
            var game = NewGame(work, "g6" + mode);
            Directory.CreateDirectory(Path.GetDirectoryName(Path.Combine(game, Overlay.Replace('/', '\\')))!);
            const string foreign = "translate vietnamese strings:\n    old \"Hi\"\n    new \"Chào\"\n";
            File.WriteAllText(Path.Combine(game, Overlay.Replace('/', '\\')), foreign);
            var patch = MakePatch(work, "u" + mode, "0.1.25", game, new Spec(Overlay, v25, true, foreign), new Spec(Activation, act, false, null));
            Check($"preflight names the unmanaged file ({mode})", string.Join("|", patch.DescribeOwnership(game)).Contains("không do VNText quản lý"));
            patch.Install(game);
            patch.Uninstall(game, null, mode);
            Check($"the unmanaged Vietnamese file is restored byte-for-byte ({mode})", Read(game, Overlay) == foreign && !File.Exists(Path.Combine(game, Activation)) && !Directory.Exists(Path.Combine(game, ".vntext")));
        }

        // 7. damaged receipt or damaged first-original copy: fail closed, touch nothing.
        {
            var game = NewGame(work, "g7");
            var old = MakePatch(work, "v24", "0.1.24", game, new Spec(Overlay, v24, false, null), new Spec(Activation, act, false, null));
            old.Install(game);
            var next = MakePatch(work, "v25", "0.1.25", game, new Spec(Overlay, v25, true, v24), new Spec(Activation, act, true, act));
            next.Install(game);
            var before = Snapshot(game);
            var keep = Path.Combine(game, ".vntext", "originals");
            Check("no first-original copy is stored when the original did not exist", !Directory.Exists(keep) || !Directory.EnumerateFiles(keep, "*", SearchOption.AllDirectories).Any());
            File.WriteAllText(Receipt(game), "{ not json");
            var broken = Snapshot(game);
            Check("an unreadable receipt blocks uninstall without touching the game", Throws(() => next.Uninstall(game), "không đọc được", out var m7), m7);
            Check("an unreadable receipt blocks a new install", Throws(() => MakePatch(work, "v26", "0.1.26", game, new Spec(Overlay, v25 + "#", true, v25), new Spec(Activation, act, true, act)).Install(game), "không đọc được", out var m8), m8);
            Check("the blocked operations left everything as it was", Snapshot(game) == broken);
        }
        {
            var game = NewGame(work, "g8");
            Directory.CreateDirectory(Path.GetDirectoryName(Path.Combine(game, Overlay.Replace('/', '\\')))!);
            File.WriteAllText(Path.Combine(game, Overlay.Replace('/', '\\')), "translate vietnamese strings:\n    old \"a\"\n    new \"b\"\n");
            var foreign = File.ReadAllText(Path.Combine(game, Overlay.Replace('/', '\\')));
            var patch = MakePatch(work, "w25", "0.1.25", game, new Spec(Overlay, v25, true, foreign), new Spec(Activation, act, false, null));
            patch.Install(game);
            var originalCopy = Path.Combine(game, ".vntext", "originals", Overlay.Replace('/', '\\'));
            File.WriteAllText(originalCopy, "tampered original copy");
            var before = Snapshot(game);
            Check("a tampered first-original copy blocks the clean restore", Throws(() => patch.Uninstall(game, null, UninstallMode.CleanOriginal), "thiếu hoặc đã bị thay đổi", out var m9), m9);
            Check("the blocked clean restore changed nothing", Snapshot(game) == before);
        }

        // 9. field chain: an older release (no receipt, its own generated font) -> upgrade by a patch with a DIFFERENT font name -> uninstall.
        //    The old font is not in the new patch, so nothing may touch it; the result must name it, and every restored file is hash-proven.
        {
            var game = NewGame(work, "g9");
            const string oldFont = "game/tl/vietnamese/vntext_font_aaaaaaaaaaaaaaaa.ttf";
            const string newFont = "game/tl/vietnamese/vntext_font_bbbbbbbbbbbbbbbb.ttf";
            Directory.CreateDirectory(Path.Combine(game, "game", "tl", "vietnamese"));
            File.WriteAllText(Path.Combine(game, Overlay.Replace('/', '\\')), v24);
            File.WriteAllText(Path.Combine(game, Activation), act);
            File.WriteAllBytes(Path.Combine(game, oldFont.Replace('/', '\\')), Bytes("OLD BROKEN FONT"));
            var oldFontHash = Sha(Path.Combine(game, oldFont.Replace('/', '\\')));
            var next = MakePatch(work, "x26", "0.1.26", game, new Spec(Overlay, v25, true, v24), new Spec(Activation, act, true, act), new Spec(newFont, "NEW FONT", false, null));
            Check("preflight names the older unreceipted font that this patch does not replace", string.Join("|", next.DescribeOwnership(game)).Contains("vntext_font_aaaaaaaaaaaaaaaa.ttf"));
            next.Install(game);
            Check("the old font is untouched by the upgrade", Sha(Path.Combine(game, oldFont.Replace('/', '\\'))) == oldFontHash);
            var removed = next.Uninstall(game);
            var allNotes = string.Join("|", removed.Notes);
            Check("uninstall restores overlay and activation to the previous bytes", Read(game, Overlay) == v24 && Read(game, Activation) == act && !File.Exists(Path.Combine(game, newFont.Replace('/', '\\'))));
            Check("uninstall says the previous (not clean) version is what is back", allNotes.Contains("không phải game gốc sạch"));
            Check("uninstall reports the leftover old font by name and hash, and leaves it byte-identical", allNotes.Contains("CÒN LẠI") && allNotes.Contains("vntext_font_aaaaaaaaaaaaaaaa.ttf") && allNotes.Contains(oldFontHash[..12])
                && Sha(Path.Combine(game, oldFont.Replace('/', '\\'))) == oldFontHash);
        }

        // 10. missing backup: refuse before writing anything and say what is left in place.
        {
            var game = NewGame(work, "g10");
            Directory.CreateDirectory(Path.Combine(game, "game", "tl", "vietnamese"));
            File.WriteAllText(Path.Combine(game, Overlay.Replace('/', '\\')), v24);
            var patch = MakePatch(work, "y26", "0.1.26", game, new Spec(Overlay, v25, true, v24));
            patch.Install(game);
            File.Delete(Path.Combine(patch.BackupDirectory, Overlay.Replace('/', '\\')));
            var before = Snapshot(game);
            Check("a missing backup blocks the uninstall and says the game was not changed", Throws(() => patch.Uninstall(game), "Game chưa bị thay đổi", out var m10), m10);
            Check("the blocked uninstall left the game byte-identical", Snapshot(game) == before && Read(game, Overlay) == v25);
        }

        // 11. unusual game folder names (spaces, non-ASCII): install then uninstall must restore the folder byte for byte.
        {
            var game = NewGame(work, "g11 tập lệnh đặc biệt");
            var before = Snapshot(game);
            var patch = MakePatch(work, "z26", "0.1.26", game, new Spec(Overlay, v25, false, null), new Spec(Activation, act, false, null));
            patch.Install(game);
            patch.Uninstall(game);
            Check("a folder with spaces and non-ASCII letters round-trips install and uninstall byte for byte", Snapshot(game) == before);
        }

        // 12. a read-only target: either the install succeeds and uninstall restores it exactly, or it fails closed leaving the game untouched.
        {
            var game = NewGame(work, "g12");
            Directory.CreateDirectory(Path.Combine(game, "game", "tl", "vietnamese"));
            var target = Path.Combine(game, Overlay.Replace('/', Path.DirectorySeparatorChar));
            File.WriteAllText(target, v24);
            File.SetAttributes(target, FileAttributes.ReadOnly);
            var before = Snapshot(game);
            var patch = MakePatch(work, "r26", "0.1.26", game, new Spec(Overlay, v25, true, v24), new Spec(Activation, act, false, null));
            bool installed;
            try { patch.Install(game); installed = true; } catch (Exception) { installed = false; }
            if (!installed)
                Check("a read-only target makes the install fail closed with the game untouched", Snapshot(game) == before && !File.Exists(patch.StatePath) && !Directory.Exists(patch.BackupDirectory), "same=" + (Snapshot(game) == before) + " state=" + File.Exists(patch.StatePath) + " backup=" + Directory.Exists(patch.BackupDirectory) + " now=" + Snapshot(game).Replace("\n", " | "));
            else
            {
                File.SetAttributes(target, FileAttributes.Normal);
                try { patch.Uninstall(game); } catch (Exception) { }
                Check("a read-only target that was replaced is restored exactly by uninstall", Read(game, Overlay) == v24 && !File.Exists(Path.Combine(game, Activation)));
            }
            try { File.SetAttributes(target, FileAttributes.Normal); } catch { }
        }

        // 13. patch-only files (nothing to restore): the whole backup folder may be gone and the uninstall must still finish cleanly.
        {
            var game = NewGame(work, "g13");
            var before = Snapshot(game);
            var patch = MakePatch(work, "w26", "0.1.26", game, new Spec(Overlay, v25, false, null), new Spec(Activation, act, false, null));
            patch.Install(game);
            try { Directory.Delete(patch.BackupDirectory, true); } catch { }
            var finished = !Throws(() => patch.Uninstall(game), "", out var m13);
            Check("uninstall of patch-only files succeeds even when the backup folder is already gone", finished && Snapshot(game) == before, m13);
        }


        // 14. power loss / kill at EVERY step of an install, an upgrade (A -> B in one step), an uninstall and a clean-original restore: the next run must
        //     find the game in a valid state (before or after the step, never half), and the full chain must still end byte-identical to the original game.
        {
            static string Game(string snapshot) => string.Join("\n", snapshot.Split('\n').Where(line => !line.StartsWith(".vntext", StringComparison.Ordinal)));
            int Crash(Action action, int at)
            {
                var count = 0;
                InstallerService.FaultPoint = point => { if (++count == at) throw new SimulatedCrashException(point); };
                try { action(); return 0; }
                catch (SimulatedCrashException) { return 1; }
                finally { InstallerService.FaultPoint = null; }
            }
            var crashes = 0;
            for (var at = 1; at < 40; at++)
            {
                var game = NewGame(work, $"g14i{at}");
                var original = Snapshot(game);
                var a = MakePatch(work, $"x24_{at}", "0.1.24", game, new Spec(Overlay, v24, false, null), new Spec(Activation, act, false, null));
                if (Crash(() => a.Install(game), at) == 0) break;
                crashes++;
                var recovered = a.RecoverInterruptedInstall();
                var installed = File.Exists(a.StatePath);
                Check($"install cut at step {at}: the next run finds the game either untouched or fully installed", installed ? Read(game, Overlay) == v24 && Read(game, Activation) == act : Snapshot(game) == original,
                    $"recovered={recovered} installed={installed}");
                if (!installed) a.Install(game);
                a.Uninstall(game);
                Check($"install cut at step {at}: install + uninstall still end byte-identical to the original", Snapshot(game) == original, Snapshot(game));
            }
            Check("every install step was exercised", crashes >= 7, crashes.ToString());

            crashes = 0;
            for (var at = 1; at < 40; at++)
            {
                var game = NewGame(work, $"g14u{at}");
                var original = Snapshot(game);
                var a = MakePatch(work, $"y24_{at}", "0.1.24", game, new Spec(Overlay, v24, false, null), new Spec(Activation, act, false, null));
                a.Install(game);
                var withA = Game(Snapshot(game));
                var b = MakePatch(work, $"y25_{at}", "0.1.25", game, new Spec(Overlay, v25, true, v24), new Spec(Activation, act, true, act));
                if (Crash(() => b.Install(game), at) == 0) break;
                crashes++;
                b.RecoverInterruptedInstall();
                var upgraded = File.Exists(b.StatePath);
                Check($"upgrade cut at step {at}: the game is still exactly patch A, or exactly patch B", upgraded ? Read(game, Overlay) == v25 : Game(Snapshot(game)) == withA, Snapshot(game));
                if (!upgraded) b.Install(game);
                b.Uninstall(game);
                Check($"upgrade cut at step {at}: uninstalling B after recovery gives back patch A byte for byte", Game(Snapshot(game)) == withA, Snapshot(game));
                a.Uninstall(game);
                Check($"upgrade cut at step {at}: the chain ends byte-identical to the original game", Snapshot(game) == original, Snapshot(game));
            }
            Check("every upgrade step was exercised", crashes >= 7, crashes.ToString());

            crashes = 0;
            for (var at = 1; at < 40; at++)
            {
                var game = NewGame(work, $"g14r{at}");
                var original = Snapshot(game);
                var a = MakePatch(work, $"z24_{at}", "0.1.24", game, new Spec(Overlay, v24, false, null), new Spec(Activation, act, false, null));
                a.Install(game);
                var b = MakePatch(work, $"z25_{at}", "0.1.25", game, new Spec(Overlay, v25, true, v24), new Spec(Activation, act, true, act));
                b.Install(game);
                var withB = Game(Snapshot(game));
                if (Crash(() => b.Uninstall(game, null, UninstallMode.CleanOriginal), at) == 0) break;
                crashes++;
                var again = !Throws(() => b.Uninstall(game, null, UninstallMode.CleanOriginal), "", out var mr);
                Check($"clean restore cut at step {at}: running it again reaches the original game, or says plainly the patch is already gone",
                    Snapshot(game) == original || (!again && mr.Contains("không còn gì để gỡ") && Game(Snapshot(game)) == Game(original)), mr + "\n" + Snapshot(game));
                Check($"clean restore cut at step {at}: never a mix of patch and original files", Game(Snapshot(game)) == Game(original) || Game(Snapshot(game)) == withB, Snapshot(game));
            }
            Check("every clean-restore step was exercised", crashes >= 3, crashes.ToString());

            crashes = 0;
            for (var at = 1; at < 40; at++)
            {
                var game = NewGame(work, $"g14p{at}");
                var original = Snapshot(game);
                var a = MakePatch(work, $"v24_{at}", "0.1.24", game, new Spec(Overlay, v24, false, null), new Spec(Activation, act, false, null));
                a.Install(game);
                if (Crash(() => a.Uninstall(game), at) == 0) break;
                crashes++;
                var again = !Throws(() => a.Uninstall(game), "", out var mu);
                Check($"uninstall cut at step {at}: running it again ends byte-identical to the original game", Snapshot(game) == original || (!again && Game(Snapshot(game)) == Game(original)), mu + "\n" + Snapshot(game));
                var reinstall = !Throws(() => a.Install(game), "", out var mi);
                Check($"uninstall cut at step {at}: the same patch can be installed again afterwards", reinstall && Read(game, Overlay) == v24, mi);
                a.Uninstall(game);
            }
            Check("every uninstall step was exercised", crashes >= 3, crashes.ToString());
        }

        Console.WriteLine("{\"pass\":" + (allPass ? "true" : "false") + ",\"checks\":[" + string.Join(",", Results) + "]}");
        try { Directory.Delete(work, true); } catch { }
        return allPass ? 0 : 1;
    }
}
