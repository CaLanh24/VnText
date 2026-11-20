using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using TMPro;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace VNTextTmpFonts
{
    /// <summary>
    /// Keeps one verified dynamic TextMeshPro font registered as the first global TMP fallback, so characters the game's own TMP fonts lack
    /// (Vietnamese) resolve to it.  It never edits game assets: it reads a hash-bound config + font from the data folder and changes only in-memory
    /// state of the running player.  Removing the files (uninstall) restores the exact original behaviour.
    ///
    /// Lifecycle: the registration is verified at start-up and again after every scene load, and re-applied idempotently when the global fallback list
    /// was replaced or our font asset was destroyed (a one-shot registration is lost as soon as a later scene or the game re-creates TMP settings).
    /// </summary>
    public static class Startup
    {
        private const string Tag = "[VNTextTmpFonts] ";
        private const string ConfigName = "vntext_tmp_font.cfg";

        private static TMP_FontAsset asset;
        private static string fontName;
        private static string actualHash;
        private static string expectedHash;
        private static string characters;
        private static string fontPath;
        private static bool configured;
        private static bool subscribed;
        private static int registrations;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        public static void Initialize()
        {
            try
            {
                if (!configured) Configure();
                if (!subscribed)
                {
                    SceneManager.sceneLoaded += OnSceneLoaded;
                    subscribed = true;
                }
                Ensure("start");
            }
            catch (Exception ex)
            {
                Debug.LogError(Tag + ex.GetType().Name + ": " + ex.Message);
            }
        }

        private static void OnSceneLoaded(Scene scene, LoadSceneMode mode)
        {
            try
            {
                Ensure("scene " + scene.name);
            }
            catch (Exception ex)
            {
                Debug.LogError(Tag + ex.GetType().Name + ": " + ex.Message);
            }
        }

        private static void Configure()
        {
            string directory = Application.dataPath;
            string[] lines = File.ReadAllLines(Path.Combine(directory, ConfigName), Encoding.UTF8);
            if (lines.Length != 3) throw new InvalidOperationException("config needs font name, sha256 and characters");
            fontName = lines[0];
            expectedHash = lines[1].ToLowerInvariant();
            characters = lines[2];
            if (fontName != Path.GetFileName(fontName) || !fontName.StartsWith("vntext_tmp_font_", StringComparison.Ordinal))
                throw new InvalidOperationException("unexpected font file name");
            fontPath = Path.Combine(directory, fontName);
            VerifyFont();
            configured = true;
        }

        private static void VerifyFont()
        {
            using (SHA256 sha = SHA256.Create())
            {
                actualHash = BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(fontPath))).Replace("-", "").ToLowerInvariant();
            }
            if (actualHash != expectedHash) throw new InvalidOperationException("font bytes differ from the installed hash; fallback not registered");
        }

        /// <summary>Idempotent: creates the asset once (again only if Unity destroyed it) and inserts it at the front of the CURRENT global list once.</summary>
        private static void Ensure(string reason)
        {
            if (!configured) return;
            TMP_FontAsset retired = null;
            if (asset == null)
            {
                retired = asset;
                VerifyFont();                                   // a re-created asset is built from re-verified bytes only
                Font source = new Font(fontPath);
                TMP_FontAsset created = TMP_FontAsset.CreateFontAsset(source);
                if (created == null) throw new InvalidOperationException("TMP font asset was not created");
                string missing;
                if (!created.TryAddCharacters(characters, out missing))
                    throw new InvalidOperationException("font cannot supply " + (missing == null ? 0 : missing.Length) + " required characters; fallback not registered");
                created.hideFlags = HideFlags.DontUnloadUnusedAsset;
                asset = created;
            }

            var fallback = TMP_Settings.fallbackFontAssets;
            if (fallback == null) throw new InvalidOperationException("TMP global fallback list is unavailable");
            if (!ReferenceEquals(retired, null)) fallback.Remove(retired);      // our own destroyed asset must not linger as a dead entry
            if (fallback.Contains(asset)) return;
            fallback.Insert(0, asset);
            registrations++;
            Debug.Log(Tag + "registered " + fontName + " sha256=" + actualHash.Substring(0, 16) + " characters=" + characters.Length + " (" + reason + ", #" + registrations + ")");
        }
    }
}
