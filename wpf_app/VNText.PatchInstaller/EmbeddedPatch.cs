using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;

namespace VNText.PatchInstaller;

/// <summary>
/// One self-contained EXE: the patch payload is a ZIP appended to this executable, followed by SHA-256(32) + length(8) + magic(16).
/// The payload is verified against that digest, then materialised into a per-payload folder under LocalAppData.  Every launch re-verifies and
/// restores the cached payload/manifest from the verified archive, so a tampered cache is never trusted; install state/backups stay in the same
/// folder (they are not part of the payload) and survive moving the EXE.
/// </summary>
internal static class EmbeddedPatch
{
    internal const int FooterSize = 32 + 8 + 17;      // sha256, little-endian length, 17-byte magic
    internal const string Magic = "VNTEXT-PATCH-001!";
    internal const long MaxTotalBytes = 64L * 1024 * 1024 * 1024;     // 64 GiB of extracted payload
    internal const int MaxEntries = 100000;
    private static readonly string[] AllowedRootFiles = { "patch_manifest.json", "patch_coverage.json", "patch_verification.json" };
    private static Mutex? _instanceLock;                                // held until the process exits: one installer per payload at a time

    /// <summary>Returns the folder InstallerService should use.  An EXE without a payload footer (a loose patch folder) uses its own directory.</summary>
    public static string Open(string executable, string? storageRoot = null)
    {
        using var source = new FileStream(executable, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (source.Length < FooterSize) return AppContext.BaseDirectory;
        source.Position = source.Length - FooterSize;
        var footer = new byte[FooterSize]; source.ReadExactly(footer);
        if (Encoding.ASCII.GetString(footer, 40, 17) != Magic) return AppContext.BaseDirectory;
        long length = BitConverter.ToInt64(footer, 32);
        if (length < 22 || length > source.Length - FooterSize) throw new InvalidDataException("Payload patch không hợp lệ.");
        var expected = footer.AsSpan(0, 32).ToArray();
        var id = Convert.ToHexString(expected).ToLowerInvariant();
        var local = !string.IsNullOrWhiteSpace(storageRoot) ? storageRoot : Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        var root = Path.GetFullPath(Path.Combine(local, "VNText", "Patches", id));
        CheckPath(root, local);

        var window = new SubStream(source, source.Length - FooterSize - length, length);
        // 1. The whole appended payload must match the digest in the footer before any entry is read.
        using (var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256))
        {
            var buffer = new byte[1024 * 1024]; int read;
            while ((read = window.Read(buffer, 0, buffer.Length)) > 0) hash.AppendData(buffer, 0, read);
            if (!hash.GetHashAndReset().AsSpan().SequenceEqual(expected)) throw new InvalidDataException("Hash payload patch không khớp.");
        }
        window.Position = 0;

        // 2. One installer per payload (install/uninstall state is a single transaction); held for the lifetime of the process.
        var mutex = new Mutex(false, "Local\\VNTextPatch-" + id);
        try
        {
            if (!mutex.WaitOne(TimeSpan.FromSeconds(3))) { mutex.Dispose(); throw new IOException("Một installer khác đang mở patch này. Hãy đóng nó trước."); }
        }
        catch (AbandonedMutexException) { }
        _instanceLock = mutex;

        Directory.CreateDirectory(root);
        using var zip = new ZipArchive(window, ZipArchiveMode.Read, leaveOpen: true);
        if (zip.Entries.Count == 0 || zip.Entries.Count > MaxEntries) throw new InvalidDataException("Số file patch không hợp lệ.");
        var names = new Dictionary<string, ZipArchiveEntry>(StringComparer.OrdinalIgnoreCase);
        long total = 0;
        foreach (var entry in zip.Entries)
        {
            var name = entry.FullName.Replace('\\', '/');
            if (name.EndsWith('/')) continue;
            if (!(name.StartsWith("COPY_TO_GAME_ROOT/", StringComparison.Ordinal) || AllowedRootFiles.Contains(name, StringComparer.Ordinal))
                || name.Split('/').Any(p => p is "" or "." or ".." || p.Contains(':') || p.EndsWith('.') || p.EndsWith(' ')) || !names.TryAdd(name, entry))
                throw new InvalidDataException("Đường dẫn payload patch không hợp lệ.");
            if (entry.Length < 0 || entry.Length > MaxTotalBytes) throw new InvalidDataException("Kích thước file patch không hợp lệ.");
            total = checked(total + entry.Length);
            if (total > MaxTotalBytes) throw new InvalidDataException("Payload patch vượt giới hạn 64 GiB.");
        }
        if (!names.ContainsKey("patch_manifest.json")) throw new InvalidDataException("Thiếu manifest patch.");
        var free = new DriveInfo(Path.GetPathRoot(root)!).AvailableFreeSpace;
        if (free < total + 256L * 1024 * 1024) throw new IOException("Không đủ dung lượng trống để chuẩn bị patch.");

        // 3. Restore every payload file from the verified archive when it differs; remove anything unexpected from the payload tree.
        foreach (var (name, entry) in names)
        {
            var target = Path.GetFullPath(Path.Combine(root, name));
            if (!target.StartsWith(root + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Payload ngoài thư mục patch.");
            CheckPath(target, local);
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            var temp = target + "." + Guid.NewGuid().ToString("N") + ".tmp";
            try
            {
                string digest;
                using (var input = entry.Open())
                using (var output = new FileStream(temp, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                using (var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256))
                {
                    var buffer = new byte[1024 * 1024]; long copied = 0; int read;
                    while ((read = input.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        copied += read;
                        if (copied > entry.Length) throw new InvalidDataException("File patch lớn hơn kích thước khai báo.");
                        hash.AppendData(buffer, 0, read); output.Write(buffer, 0, read);
                    }
                    if (copied != entry.Length) throw new InvalidDataException("File patch ngắn hơn kích thước khai báo.");
                    digest = Convert.ToHexString(hash.GetHashAndReset());
                }
                if (File.Exists(target) && HashFile(target) == digest) { File.Delete(temp); continue; }
                File.Move(temp, target, true);
            }
            finally { if (File.Exists(temp)) File.Delete(temp); }
        }
        RemoveUnexpected(Path.Combine(root, "COPY_TO_GAME_ROOT"), root, names.Keys);
        foreach (var file in Directory.EnumerateFiles(root, "*", SearchOption.TopDirectoryOnly))
        {
            var leaf = Path.GetFileName(file);
            if (leaf.EndsWith(".tmp", StringComparison.OrdinalIgnoreCase) || (leaf.StartsWith("payload-") && leaf.EndsWith(".zip", StringComparison.OrdinalIgnoreCase))) File.Delete(file);
        }
        return root;
    }

    private static string HashFile(string path)
    {
        using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        return Convert.ToHexString(SHA256.HashData(stream));
    }

    private static void RemoveUnexpected(string directory, string root, IEnumerable<string> expectedNames)
    {
        if (!Directory.Exists(directory)) return;
        var expected = new HashSet<string>(expectedNames.Select(n => Path.GetFullPath(Path.Combine(root, n))), StringComparer.OrdinalIgnoreCase);
        foreach (var file in Directory.EnumerateFiles(directory, "*", SearchOption.AllDirectories))
        {
            if ((File.GetAttributes(file) & FileAttributes.ReparsePoint) != 0) throw new IOException("Không dùng đường dẫn liên kết cho dữ liệu patch.");
            if (!expected.Contains(Path.GetFullPath(file))) File.Delete(file);
        }
    }

    /// <summary>Refuses a link/reparse point anywhere between <paramref name="path"/> and the storage root (links above the root are the user's own layout).</summary>
    private static void CheckPath(string path, string stopAt)
    {
        var stop = Path.GetFullPath(stopAt).TrimEnd(Path.DirectorySeparatorChar);
        for (FileSystemInfo? part = new FileInfo(path); part is not null; part = part is FileInfo f ? f.Directory : ((DirectoryInfo)part).Parent)
        {
            if (string.Equals(part.FullName.TrimEnd(Path.DirectorySeparatorChar), stop, StringComparison.OrdinalIgnoreCase)) break;
            if (part.Exists && (part.Attributes & FileAttributes.ReparsePoint) != 0) throw new IOException("Không dùng đường dẫn liên kết cho dữ liệu patch.");
        }
    }

    /// <summary>A read-only seekable window over the appended payload, so the archive is never copied to disk a second time.</summary>
    private sealed class SubStream(Stream inner, long start, long length) : Stream
    {
        private long _position;
        public override bool CanRead => true;
        public override bool CanSeek => true;
        public override bool CanWrite => false;
        public override long Length => length;
        public override long Position { get => _position; set => _position = Math.Clamp(value, 0, length); }
        public override void Flush() { }
        public override int Read(byte[] buffer, int offset, int count)
        {
            var take = (int)Math.Min(count, length - _position);
            if (take <= 0) return 0;
            inner.Position = start + _position;
            var read = inner.Read(buffer, offset, take);
            _position += read;
            return read;
        }
        public override long Seek(long offset, SeekOrigin origin)
        {
            Position = origin switch { SeekOrigin.Begin => offset, SeekOrigin.Current => _position + offset, _ => length + offset };
            return _position;
        }
        public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
    }
}
