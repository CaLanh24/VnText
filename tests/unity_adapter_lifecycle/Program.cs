using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;
using VNTextTmpFonts;

public static class Program
{
    private static readonly List<string> Results = new List<string>();
    private static bool allPass = true;

    private static void Check(string name, bool ok)
    {
        Results.Add("{\"check\":\"" + name + "\",\"pass\":" + (ok ? "true" : "false") + "}");
        allPass &= ok;
    }

    private static int Count(List<TMP_FontAsset> list, TMP_FontAsset item)
    {
        int n = 0;
        foreach (TMP_FontAsset entry in list) if (ReferenceEquals(entry, item)) n++;
        return n;
    }

    private static bool Ours(TMP_FontAsset item) { return !ReferenceEquals(item, null) && item.name != null && item.name.StartsWith("dyn"); }

    public static int Main(string[] args)
    {
        string dir = Path.Combine(Path.GetTempPath(), "vntext-lifecycle-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(dir);
        byte[] font = Encoding.UTF8.GetBytes("not a real font; the fake engine does not parse it");
        string hash;
        using (SHA256 sha = SHA256.Create()) hash = BitConverter.ToString(sha.ComputeHash(font)).Replace("-", "").ToLowerInvariant();
        string fontFile = "vntext_tmp_font_" + hash.Substring(0, 16) + ".ttf";
        File.WriteAllBytes(Path.Combine(dir, fontFile), font);
        File.WriteAllText(Path.Combine(dir, "vntext_tmp_font.cfg"), fontFile + "\n" + hash + "\nDang Nguyen\n", new UTF8Encoding(false));
        Application.dataPath = dir;

        var original = new TMP_FontAsset { name = "game fallback" };
        TMP_Settings.Replace(new List<TMP_FontAsset> { original });

        Startup.Initialize();
        Startup.Initialize();                                                   // a double start-up must neither double-subscribe nor double-register
        TMP_FontAsset first = TMP_Settings.fallbackFontAssets.Count > 0 ? TMP_Settings.fallbackFontAssets[0] : null;
        Check("registered first at start", Ours(first) && TMP_Settings.fallbackFontAssets.Count == 2 && Count(TMP_Settings.fallbackFontAssets, first) == 1);
        Check("original fallback kept after ours", TMP_Settings.fallbackFontAssets.Count == 2 && ReferenceEquals(TMP_Settings.fallbackFontAssets[1], original));

        SceneManager.Raise("gameplay");
        SceneManager.Raise("gameplay again");
        Check("scene loads do not duplicate", TMP_Settings.fallbackFontAssets.Count == 2 && Count(TMP_Settings.fallbackFontAssets, first) == 1);

        var replaced = new List<TMP_FontAsset> { new TMP_FontAsset { name = "game fallback 2" } };
        TMP_Settings.Replace(replaced);                                         // a later scene / the game rebuilds the TMP settings list
        SceneManager.Raise("in-game menu");
        Check("re-applied after the global list was replaced", TMP_Settings.fallbackFontAssets.Count == 2 && ReferenceEquals(TMP_Settings.fallbackFontAssets[0], first));
        Check("game's own entries preserved", TMP_Settings.fallbackFontAssets.Count == 2 && TMP_Settings.fallbackFontAssets[1].name == "game fallback 2");

        first.Destroyed = true;                                                 // Unity unloaded our runtime asset
        SceneManager.Raise("after unload");
        TMP_FontAsset recreated = TMP_Settings.fallbackFontAssets.Count > 0 ? TMP_Settings.fallbackFontAssets[0] : null;
        Check("re-created after destroy, exactly once", Ours(recreated) && !ReferenceEquals(recreated, first) && TMP_Settings.fallbackFontAssets.Count == 2 && Count(TMP_Settings.fallbackFontAssets, recreated) == 1);
        Check("marked DontUnloadUnusedAsset", !ReferenceEquals(recreated, null) && (recreated.hideFlags & HideFlags.DontUnloadUnusedAsset) != 0);

        File.WriteAllBytes(Path.Combine(dir, fontFile), Encoding.UTF8.GetBytes("tampered"));
        recreated.Destroyed = true;
        var thirdList = new List<TMP_FontAsset> { new TMP_FontAsset { name = "game fallback 3" } };
        TMP_Settings.Replace(thirdList);
        SceneManager.Raise("tampered");
        Check("a font file changed after start is never registered again", thirdList.Count == 1 && thirdList[0].name == "game fallback 3");

        Console.WriteLine("{\"pass\":" + (allPass ? "true" : "false") + ",\"checks\":[" + string.Join(",", Results) + "]}");
        try { Directory.Delete(dir, true); } catch { }
        return allPass ? 0 : 1;
    }
}
