using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;

namespace VNText.PatchInstaller;

internal static class EmbeddedPatch
{
    // Persistent per-payload storage keeps install state/backups when the EXE is moved.
    public static string Open(string executable)
    {
        using var source = File.OpenRead(executable);
        if (source.Length < 56) return AppContext.BaseDirectory;
        source.Position = source.Length - 56;
        var footer = new byte[56]; source.ReadExactly(footer);
        if (Encoding.ASCII.GetString(footer, 40, 16) != "VNTEXT-PATCH-001!") return AppContext.BaseDirectory;
        long length = BitConverter.ToInt64(footer, 32);
        if (length <= 0 || length > source.Length - 56) throw new InvalidDataException("Payload patch không hợp lệ.");
        var expected = footer.AsSpan(0, 32).ToArray();
        var id = Convert.ToHexString(expected).ToLowerInvariant();
        var root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "VNText", "Patches", id);
        CheckPath(root);
        using var mutex = new Mutex(false, "Local\\VNTextPatch-" + id);
        bool owned = false;
        try
        {
            try { owned = mutex.WaitOne(TimeSpan.FromSeconds(30)); } catch (AbandonedMutexException) { owned = true; }
            if (!owned) throw new IOException("Installer khác đang xử lý patch này.");
            Directory.CreateDirectory(root);
            var archive = Path.Combine(root, "payload-" + Guid.NewGuid().ToString("N") + ".zip");
            try
            {
                source.Position = source.Length - 56 - length;
                using (var output = new FileStream(archive, FileMode.CreateNew))
                using (var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256))
                {
                    var buffer = new byte[1024 * 1024]; long remaining = length;
                    while (remaining > 0)
                    {
                        int read = source.Read(buffer, 0, (int)Math.Min(buffer.Length, remaining));
                        if (read == 0) throw new EndOfStreamException();
                        hash.AppendData(buffer, 0, read); output.Write(buffer, 0, read); remaining -= read;
                    }
                    if (!hash.GetHashAndReset().SequenceEqual(expected)) throw new InvalidDataException("Hash payload patch không khớp.");
                }
                using var zip = ZipFile.OpenRead(archive);
                if (zip.Entries.Count > 100000) throw new InvalidDataException("Quá nhiều file patch.");
                var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                foreach (var entry in zip.Entries)
                {
                    var name = entry.FullName.Replace('\\', '/');
                    if (name.EndsWith('/')) continue;
                    if (!(name.StartsWith("COPY_TO_GAME_ROOT/", StringComparison.Ordinal) || name is "patch_manifest.json" or "patch_coverage.json" or "patch_verification.json")
                        || name.Split('/').Any(p => p is "" or "." or ".." || p.Contains(':')) || !names.Add(name))
                        throw new InvalidDataException("Đường dẫn payload patch không hợp lệ.");
                    var target = Path.GetFullPath(Path.Combine(root, name));
                    if (!target.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Payload ngoài thư mục patch.");
                    CheckPath(target);
                    // Never overwrite cached payload or transaction data; InstallerService verifies its manifest hashes.
                    if (File.Exists(target)) continue;
                    Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                    var temp = target + "." + Guid.NewGuid().ToString("N") + ".tmp";
                    try { entry.ExtractToFile(temp); File.Move(temp, target); }
                    finally { if (File.Exists(temp)) File.Delete(temp); }
                }
                if (!File.Exists(Path.Combine(root, "patch_manifest.json"))) throw new InvalidDataException("Thiếu manifest patch.");
            }
            finally { if (File.Exists(archive)) File.Delete(archive); }
            return root;
        }
        finally { if (owned) mutex.ReleaseMutex(); }
    }

    private static void CheckPath(string path)
    {
        for (FileSystemInfo? part = new FileInfo(path); part is not null; part = part is FileInfo f ? f.Directory : ((DirectoryInfo)part).Parent)
            if (part.Exists && (part.Attributes & FileAttributes.ReparsePoint) != 0) throw new IOException("Không dùng đường dẫn liên kết cho dữ liệu patch.");
    }
}
