using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using TMPro;
using UnityEngine;

namespace VNTextTmpFonts
{
    /// <summary>
    /// Registers one verified dynamic TextMeshPro font as the first global fallback, so characters the game's own TMP fonts lack
    /// (Vietnamese) resolve to it.  It never edits game assets: it reads a hash-bound config + font from the data folder and changes
    /// only in-memory state of the running player.  Removing the files (uninstall) restores the exact original behaviour.
    /// </summary>
    public static class Startup
    {
        private const string Tag = "[VNTextTmpFonts] ";
        private const string ConfigName = "vntext_tmp_font.cfg";

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        public static void Initialize()
        {
            try
            {
                string directory = Application.dataPath;
                string[] lines = File.ReadAllLines(Path.Combine(directory, ConfigName), Encoding.UTF8);
                if (lines.Length != 3) throw new InvalidOperationException("config needs font name, sha256 and characters");
                string fontName = lines[0];
                string expected = lines[1].ToLowerInvariant();
                string characters = lines[2];
                if (fontName != Path.GetFileName(fontName) || !fontName.StartsWith("vntext_tmp_font_", StringComparison.Ordinal))
                    throw new InvalidOperationException("unexpected font file name");
                string fontPath = Path.Combine(directory, fontName);
                string actual;
                using (SHA256 sha = SHA256.Create())
                {
                    actual = BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(fontPath))).Replace("-", "").ToLowerInvariant();
                }
                if (actual != expected) throw new InvalidOperationException("font bytes differ from the installed hash; fallback not registered");

                Font source = new Font(fontPath);
                TMP_FontAsset asset = TMP_FontAsset.CreateFontAsset(source);
                if (asset == null) throw new InvalidOperationException("TMP font asset was not created");
                string missing;
                if (!asset.TryAddCharacters(characters, out missing))
                    throw new InvalidOperationException("font cannot supply " + (missing == null ? 0 : missing.Length) + " required characters; fallback not registered");

                var fallback = TMP_Settings.fallbackFontAssets;
                if (fallback == null) throw new InvalidOperationException("TMP global fallback list is unavailable");
                fallback.Insert(0, asset);
                Debug.Log(Tag + "registered " + fontName + " sha256=" + actual.Substring(0, 16) + " characters=" + characters.Length);
            }
            catch (Exception ex)
            {
                Debug.LogError(Tag + ex.GetType().Name + ": " + ex.Message);
            }
        }
    }
}
