using System.IO;

namespace VNText.Studio.App.Services;

internal static class GameFolderBoundary
{
    // Immediate runtime roots only; never auto-select a child of a collection.
    internal static bool IsRuntimeRoot(string root)
        => Directory.Exists(Path.Combine(root, "game"))
            && Directory.Exists(Path.Combine(root, "renpy"))
            && Directory.Exists(Path.Combine(root, "lib"))
            && Directory.EnumerateFiles(root, "*.exe").Any()
            || Directory.EnumerateDirectories(root, "*_Data").Any();

    internal static string? FindNestedRuntime(string input)
    {
        if (!Directory.Exists(input) || (File.GetAttributes(input) & FileAttributes.ReparsePoint) != 0 || IsRuntimeRoot(input)) return null;
        foreach (var child in Directory.EnumerateDirectories(input).Take(128))
            if ((File.GetAttributes(child) & FileAttributes.ReparsePoint) == 0 && IsRuntimeRoot(child))
                return child;
        return null;
    }
}
