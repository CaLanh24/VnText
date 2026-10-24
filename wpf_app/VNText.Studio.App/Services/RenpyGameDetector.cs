using System;
using System.IO;
using System.Linq;
using System.Threading;

namespace VNText.Studio.App.Services;

internal static class RenpyGameDetector
{
    public static bool IsLooseSourceGame(string inputPath, CancellationToken cancellationToken)
        => HasSdkRecoveryEvidence(inputPath, cancellationToken);

    public static bool HasSdkRecoveryEvidence(string inputPath, CancellationToken cancellationToken)
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

        if (HasLooseSourceFiles(root, cancellationToken))
            return true;

        var gameRoot = Path.Combine(root, "game");
        if (!Directory.Exists(gameRoot)
            || !Directory.Exists(Path.Combine(root, "renpy"))
            || !Directory.Exists(Path.Combine(root, "lib"))
            || !Directory.EnumerateFiles(root, "*.exe", SearchOption.TopDirectoryOnly).Any())
            return false;

        var options = new EnumerationOptions
        {
            RecurseSubdirectories = true,
            IgnoreInaccessible = true,
            AttributesToSkip = FileAttributes.ReparsePoint,
        };
        var header = new byte[64];
        foreach (var path in Directory.EnumerateFiles(gameRoot, "*.rpa", options))
        {
            cancellationToken.ThrowIfCancellationRequested();
            using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
            var read = 0;
            while (read < header.Length)
            {
                var count = stream.Read(header, read, header.Length - read);
                if (count == 0 || header[read + count - 1] == (byte)'\n')
                {
                    read += count;
                    break;
                }
                read += count;
            }
            if (HasSupportedRpaHeader(header, read))
                return true;
        }

        return false;
    }

    private static bool HasSupportedRpaHeader(byte[] bytes, int length)
    {
        if (length is < 1 or > 64 || bytes[length - 1] != (byte)'\n')
            return false;
        var line = System.Text.Encoding.ASCII.GetString(bytes, 0, length - 1).TrimEnd('\r');
        var parts = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
        return parts.Length == 3
            && parts[0] == "RPA-3.0"
            && parts[1].Length == 16
            && parts[2].Length == 8
            && parts[1].All(Uri.IsHexDigit)
            && parts[2].All(Uri.IsHexDigit)
            || parts.Length == 2
            && parts[0] == "RPA-2.0"
            && parts[1].Length == 16
            && parts[1].All(Uri.IsHexDigit);
    }

    public static bool HasLooseSourceFiles(string inputPath, CancellationToken cancellationToken)
    {
        if (string.IsNullOrWhiteSpace(inputPath)) return false;
        var root = File.Exists(inputPath) ? Path.GetDirectoryName(Path.GetFullPath(inputPath)) : Path.GetFullPath(inputPath);
        if (string.IsNullOrWhiteSpace(root) || !Directory.Exists(root)) return false;
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
