using System.IO;
using Microsoft.Win32;

namespace VNText.Studio.App.Services;

/// <summary>An installed font that resolves to a real .ttf/.otf file (display name as Windows registers it).</summary>
internal sealed record InstalledFont(string Display, string Path)
{
    /// <summary>What the list and assistive technology read: the registered name and the file name, never the full path.</summary>
    public override string ToString() => Display + " — " + System.IO.Path.GetFileName(Path);
}

/// <summary>
/// Lists the installed fonts that are real TrueType/OpenType FILES, read from Windows' own font registrations (never by browsing the shell Fonts namespace,
/// which the common file dialog may refuse).  Read-only: nothing is copied, installed or bundled; a font chosen from here still goes through the same preview,
/// rights acknowledgement and validation as any other custom font, and installed fonts are NOT presumed to be redistributable.
/// </summary>
internal static class InstalledFontCatalog
{
    private const string FontsKey = @"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts";

    internal static IReadOnlyList<InstalledFont> Enumerate() => Resolve(ReadRegistry(), Environment.GetFolderPath(Environment.SpecialFolder.Fonts));

    internal static IReadOnlyList<InstalledFont> Resolve(IEnumerable<(string Name, string Value)> entries, string fontsFolder)
    {
        var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var list = new List<InstalledFont>();
        foreach (var (name, value) in entries)
        {
            if (string.IsNullOrWhiteSpace(value)) continue;
            var extension = System.IO.Path.GetExtension(value.Trim()).ToLowerInvariant();
            if (extension is not (".ttf" or ".otf")) continue;                  // collections (.ttc), bitmap (.fon) and anything else are not offered
            string path;
            try { path = System.IO.Path.IsPathRooted(value) ? System.IO.Path.GetFullPath(value) : System.IO.Path.GetFullPath(System.IO.Path.Combine(fontsFolder, value)); }
            catch (Exception) { continue; }
            if (!File.Exists(path) || !seen.Add(path)) continue;
            var display = name.Trim();
            foreach (var suffix in new[] { " (TrueType)", " (OpenType)" })
                if (display.EndsWith(suffix, StringComparison.OrdinalIgnoreCase)) display = display[..^suffix.Length];
            list.Add(new InstalledFont(display.Length > 0 ? display : System.IO.Path.GetFileNameWithoutExtension(path), path));
        }
        return list.OrderBy(font => font.Display, StringComparer.CurrentCultureIgnoreCase).ToList();
    }

    private static IEnumerable<(string Name, string Value)> ReadRegistry()
    {
        foreach (var hive in new[] { RegistryHive.LocalMachine, RegistryHive.CurrentUser })
        {
            RegistryKey? key = null;
            try
            {
                using var root = RegistryKey.OpenBaseKey(hive, RegistryView.Default);
                key = root.OpenSubKey(FontsKey);
                if (key is null) continue;
                foreach (var name in key.GetValueNames())
                    if (key.GetValue(name) is string value) yield return (name, value);
            }
            finally { key?.Dispose(); }
        }
    }
}
