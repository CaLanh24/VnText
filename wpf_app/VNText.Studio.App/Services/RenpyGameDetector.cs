using System;
using System.IO;
using System.Linq;
using System.Threading;

namespace VNText.Studio.App.Services;

internal static class RenpyGameDetector
{
    public static bool IsLooseSourceGame(string inputPath, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(inputPath))
            return false;

        var root = File.Exists(inputPath)
            ? Path.GetDirectoryName(Path.GetFullPath(inputPath))
            : Path.GetFullPath(inputPath);
        if (string.IsNullOrWhiteSpace(root) || !Directory.Exists(root))
            return false;

        var hasUnityEvidence = Directory.EnumerateFileSystemEntries(root).Any(path =>
        {
            var name = Path.GetFileName(path);
            return name.EndsWith("_Data", StringComparison.OrdinalIgnoreCase)
                || Path.GetExtension(name).Equals(".unity", StringComparison.OrdinalIgnoreCase);
        });
        if (hasUnityEvidence)
            return false;

        var gameRoot = Path.Combine(root, "game");
        if (!Directory.Exists(gameRoot))
            return false;

        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            IgnoreInaccessible = true,
            AttributesToSkip = FileAttributes.ReparsePoint,
        };
        foreach (var path in Directory.EnumerateFiles(gameRoot, "*", options))
        {
            cancellationToken.ThrowIfCancellationRequested();
            var extension = Path.GetExtension(path);
            if (extension.Equals(".rpy", StringComparison.OrdinalIgnoreCase)
                || extension.Equals(".rpym", StringComparison.OrdinalIgnoreCase))
                return true;
        }

        return false;
    }
}
