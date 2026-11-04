using System.Security.Cryptography;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace VNText.PatchInstaller;

public sealed record PatchFile(
    [property: JsonPropertyName("path")] string Path,
    [property: JsonPropertyName("source_sha256")] string SourceSha256,
    [property: JsonPropertyName("original_sha256")] string OriginalSha256,
    [property: JsonPropertyName("original_exists")] bool OriginalExists);

public sealed record PatchManifest(
    [property: JsonPropertyName("format")] int Format,
    [property: JsonPropertyName("version")] string Version,
    [property: JsonPropertyName("generated_utc")] string GeneratedUtc,
    [property: JsonPropertyName("game_data_sha256")] string GameDataSha256,
    [property: JsonPropertyName("files")] List<PatchFile> Files,
    [property: JsonPropertyName("game_data_path")] string GameDataPath = "",
    [property: JsonPropertyName("game_executable")] string GameExecutable = "",
    [property: JsonPropertyName("engine")] string Engine = "unity",
    [property: JsonPropertyName("game_checks")] List<GameCheck>? GameChecks = null);

public sealed record GameCheck([property: JsonPropertyName("path")] string Path,
    [property: JsonPropertyName("sha256")] string Sha256);

public sealed record InstalledFile(
    [property: JsonPropertyName("path")] string Path,
    [property: JsonPropertyName("backup_path")] string BackupPath,
    [property: JsonPropertyName("original_exists")] bool OriginalExists,
    [property: JsonPropertyName("original_sha256")] string OriginalSha256,
    [property: JsonPropertyName("installed_sha256")] string InstalledSha256);

public sealed record InstallState(
    [property: JsonPropertyName("game_root")] string GameRoot,
    [property: JsonPropertyName("patch_version")] string PatchVersion,
    [property: JsonPropertyName("files")] List<InstalledFile> Files,
    [property: JsonPropertyName("compiled_caches")] List<CompiledCache>? CompiledCaches = null);

public sealed record CompiledCache(
    [property: JsonPropertyName("path")] string Path,
    [property: JsonPropertyName("original_exists")] bool OriginalExists,
    [property: JsonPropertyName("original_sha256")] string OriginalSha256,
    [property: JsonPropertyName("source_digests")] List<string> SourceDigests);

public sealed class InstallerService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true, WriteIndented = true };

    public InstallerService(string patchDirectory)
    {
        PatchDirectory = Path.GetFullPath(patchDirectory);
        ManifestPath = Path.Combine(PatchDirectory, "patch_manifest.json");
        PayloadDirectory = Path.Combine(PatchDirectory, "COPY_TO_GAME_ROOT");
        BackupDirectory = Path.Combine(PatchDirectory, "install_backup");
        StatePath = Path.Combine(PatchDirectory, "install_state.json");
    }

    public string PatchDirectory { get; }
    public string ManifestPath { get; }
    public string PayloadDirectory { get; }
    public string BackupDirectory { get; }
    public string StatePath { get; }

    public PatchManifest LoadManifest()
    {
        if (!File.Exists(ManifestPath)) throw new InvalidOperationException("Thiếu patch_manifest.json.");
        var manifest = JsonSerializer.Deserialize<PatchManifest>(File.ReadAllText(ManifestPath), JsonOptions);
        if (manifest is null || manifest.Files is null || manifest.Files.Count == 0)
            throw new InvalidOperationException("patch_manifest.json không hợp lệ hoặc không có file patch.");
        return manifest;
    }

    public string ValidateGame(string gameRoot)
    {
        var root = NormalizeGameRoot(gameRoot);
        var manifest = LoadManifest();
        if (!Directory.Exists(root)) throw new InvalidOperationException("Thư mục game không tồn tại.");
        if (manifest.Engine == "renpy")
        {
            ValidateGameIdentity(root);
            if (manifest.GameChecks is null || manifest.GameChecks.Count == 0)
                throw new InvalidOperationException("Thiếu bằng chứng nhận dạng game Ren'Py.");
            foreach (var check in manifest.GameChecks)
                if (!File.Exists(ResolveSafe(root, check.Path)) || !string.Equals(HashFile(ResolveSafe(root, check.Path)), check.Sha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"Sai bản game hoặc file nguồn đã thay đổi: {check.Path}");
            foreach (var file in manifest.Files)
                if (!File.Exists(ResolveSafe(PayloadDirectory, file.Path)) || !string.Equals(HashFile(ResolveSafe(PayloadDirectory, file.Path)), file.SourceSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"Payload bị thay đổi hoặc hỏng: {file.Path}");
            return root;
        }
        if (manifest.Engine != "unity") throw new InvalidOperationException("Engine không được hỗ trợ.");
        var layout = DetectUnityLayout(root, manifest.GameExecutable);
        if (layout.DataDirectory is null)
            throw new InvalidOperationException("Sai thư mục game: thiếu thư mục Unity *_Data.");
        if (layout.Executable is null)
            throw new InvalidOperationException("Sai thư mục game: không có file .exe ở thư mục gốc.");
        var dataPath = ResolveManifestDataPath(root, layout.DataDirectory, manifest.GameDataPath);
        if (!File.Exists(dataPath)) throw new InvalidOperationException("Sai game/data: không tìm thấy resource data theo manifest hoặc *_Data.");
        if (!string.IsNullOrWhiteSpace(manifest.GameDataSha256) &&
            !string.Equals(HashFile(dataPath), manifest.GameDataSha256, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Sai game/data: resource data không khớp bản game đã dùng để tạo patch.");
        foreach (var file in manifest.Files)
        {
            var payload = ResolveSafe(PayloadDirectory, file.Path);
            if (!File.Exists(payload)) throw new InvalidOperationException($"Patch thiếu payload: {file.Path}");
            if (!string.Equals(HashFile(payload), file.SourceSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException($"Payload bị thay đổi hoặc hỏng: {file.Path}");
        }
        return root;
    }

    public InstallState Install(string gameRoot)
    {
        var root = ValidateGame(gameRoot);
        if (File.Exists(StatePath)) throw new InvalidOperationException("Patch này đã được cài. Hãy Gỡ cài đặt trước khi cài lại.");
        var manifest = LoadManifest();
        if (Directory.Exists(BackupDirectory)) throw new InvalidOperationException("Thư mục backup đã tồn tại; giữ nguyên để phục hồi giao dịch trước.");
        Directory.CreateDirectory(BackupDirectory);
        var prepared = new List<InstalledFile>();
        var caches = new List<CompiledCache>();
        try
        {
            if (manifest.Engine == "renpy")
                foreach (var file in manifest.Files.Where(f => f.Path.EndsWith(".rpy", StringComparison.OrdinalIgnoreCase)))
                {
                    var relative = file.Path + "c";
                    var cache = ResolveSafe(root, relative);
                    var exists = File.Exists(cache);
                    if (exists)
                    {
                        var backup = ResolveSafe(BackupDirectory, relative);
                        Directory.CreateDirectory(Path.GetDirectoryName(backup)!);
                        File.Copy(cache, backup, false);
                    }
                    var source = File.ReadAllBytes(ResolveSafe(PayloadDirectory, file.Path));
                    // Ren'Py 8.3 hashes raw source; 8.5 adds RPYC_MAGIC. Never
                    // deserialize a cache: only the compiler's header/trailer.
                    caches.Add(new CompiledCache(relative, exists, exists ? HashFile(cache) : "",
                        new List<string> { Convert.ToHexString(MD5.HashData(source)),
                            Convert.ToHexString(MD5.HashData(source.Concat(System.Text.Encoding.ASCII.GetBytes("_2025-07-06")).ToArray())) }));
                }
            foreach (var file in manifest.Files)
            {
                var target = ResolveSafe(root, file.Path);
                var exists = File.Exists(target);
                if (exists != file.OriginalExists)
                    throw new InvalidOperationException($"Trạng thái file gốc không khớp manifest: {file.Path}");
                if (exists && !string.Equals(HashFile(target), file.OriginalSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"File game đã bị thay đổi, không ghi đè: {file.Path}");

                var backupRel = file.Path.Replace('/', Path.DirectorySeparatorChar);
                var backup = ResolveSafe(BackupDirectory, backupRel);
                if (exists)
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(backup)!);
                    File.Copy(target, backup, true);
                }
                var payload = ResolveSafe(PayloadDirectory, file.Path);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                var temp = target + $".vntext-install-{Environment.ProcessId}.tmp";
                File.Copy(payload, temp, true);
                File.Move(temp, target, true);
                prepared.Add(new InstalledFile(file.Path, backupRel, exists, file.OriginalSha256, file.SourceSha256));
                if (!string.Equals(HashFile(target), file.SourceSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"Kiểm hash sau khi cài thất bại: {file.Path}");
            }
            var state = new InstallState(root, manifest.Version, prepared, caches);
            WriteJsonAtomic(StatePath, state);
            return state;
        }
        catch
        {
            Rollback(root, prepared);
            if (Directory.Exists(BackupDirectory)) Directory.Delete(BackupDirectory, true);
            throw;
        }
    }

    public void Uninstall(string gameRoot)
    {
        var state = ValidateInstalledState(gameRoot);
        var root = NormalizeGameRoot(state.GameRoot);
        foreach (var cache in state.CompiledCaches ?? new List<CompiledCache>())
        {
            var target = ResolveSafe(root, cache.Path);
            if (cache.OriginalExists)
            {
                File.Copy(ResolveSafe(BackupDirectory, cache.Path), target, true);
                if (!string.Equals(HashFile(target), cache.OriginalSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"Khôi phục cache thất bại: {cache.Path}");
            }
            else if (File.Exists(target)) File.Delete(target);
        }
        foreach (var file in state.Files)
        {
            var target = ResolveSafe(root, file.Path);
            if (file.OriginalExists)
            {
                var backup = ResolveSafe(BackupDirectory, file.BackupPath);
                if (!File.Exists(backup)) throw new InvalidOperationException($"Thiếu backup: {file.Path}");
                File.Copy(backup, target, true);
                if (!string.Equals(HashFile(target), file.OriginalSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"Khôi phục hash thất bại: {file.Path}");
            }
            else if (File.Exists(target))
            {
                File.Delete(target);
            }
        }
        File.Delete(StatePath);
        // Remove only our consumed backups. Foreign additions are preserved.
        var consumed = state.Files.Where(f => f.OriginalExists).Select(f => f.BackupPath)
            .Concat((state.CompiledCaches ?? new List<CompiledCache>()).Where(c => c.OriginalExists).Select(c => c.Path));
        foreach (var relative in consumed)
        {
            var backup = ResolveSafe(BackupDirectory, relative);
            File.Delete(backup);
            for (var directory = Path.GetDirectoryName(backup); directory is not null
                && directory.StartsWith(BackupDirectory + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
                directory = Path.GetDirectoryName(directory))
                if (!Directory.EnumerateFileSystemEntries(directory).Any()) Directory.Delete(directory);
        }
        if (!Directory.EnumerateFileSystemEntries(BackupDirectory).Any()) Directory.Delete(BackupDirectory);
    }

    /// <summary>
    /// Validates an already-installed patch without applying the pre-install
    /// manifest check.  The manifest's game_data_sha256 is the original
    /// data.unity3d hash, so calling ValidateGame after installation would
    /// necessarily reject the patched game and hide the uninstall action.
    /// </summary>
    public InstallState ValidateInstalledState(string gameRoot)
    {
        var root = ValidateGameIdentity(gameRoot);
        if (!File.Exists(StatePath))
            throw new InvalidOperationException("Không tìm thấy install_state.json của patch này.");

        var state = JsonSerializer.Deserialize<InstallState>(File.ReadAllText(StatePath), JsonOptions)
            ?? throw new InvalidOperationException("install_state.json không hợp lệ.");
        if (state.Files is null || state.Files.Count == 0)
            throw new InvalidOperationException("install_state.json không có file đã cài.");
        if (!string.Equals(NormalizeGameRoot(state.GameRoot), root, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("Bạn đang chọn khác thư mục game đã cài patch.");

        foreach (var file in state.Files)
        {
            var target = ResolveSafe(root, file.Path);
            if (!File.Exists(target) || !string.Equals(HashFile(target), file.InstalledSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException($"File đã bị thay đổi sau khi cài, không tự động khôi phục: {file.Path}");
            // Resolve the backup path during validation too, so a malformed
            // state cannot later escape the patch backup directory.
            if (file.OriginalExists)
            {
                var backup = ResolveSafe(BackupDirectory, file.BackupPath);
                if (!File.Exists(backup) || !string.Equals(HashFile(backup), file.OriginalSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"Backup thiếu hoặc đã thay đổi; không ghi vào game: {file.Path}");
            }
        }
        foreach (var cache in state.CompiledCaches ?? new List<CompiledCache>())
        {
            if (!state.Files.Any(f => string.Equals(f.Path + "c", cache.Path, StringComparison.OrdinalIgnoreCase)
                && f.Path.EndsWith(".rpy", StringComparison.OrdinalIgnoreCase)))
                throw new InvalidOperationException("Cache không thuộc file patch đã cài.");
            var target = ResolveSafe(root, cache.Path);
            if (cache.OriginalExists)
            {
                var backup = ResolveSafe(BackupDirectory, cache.Path);
                if (!File.Exists(backup) || !string.Equals(HashFile(backup), cache.OriginalSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"Backup cache thiếu hoặc đã thay đổi: {cache.Path}");
            }
            if (!File.Exists(target)) continue;
            if (cache.OriginalExists && string.Equals(HashFile(target), cache.OriginalSha256, StringComparison.OrdinalIgnoreCase)) continue;
            using var stream = File.OpenRead(target);
            var header = new byte[10];
            var digest = new byte[16];
            if (stream.Length < 62 || stream.Read(header) != 10 || System.Text.Encoding.ASCII.GetString(header) != "RENPY RPC2")
                throw new InvalidOperationException($"Cache đã thay đổi ngoài patch, không tự xóa: {cache.Path}");
            stream.Seek(-16, SeekOrigin.End);
            if (stream.Read(digest) != 16 || cache.SourceDigests is null
                || !cache.SourceDigests.Contains(Convert.ToHexString(digest), StringComparer.OrdinalIgnoreCase))
                throw new InvalidOperationException($"Cache không khớp nguồn patch, không tự xóa: {cache.Path}");
        }
        return state;
    }

    private string ValidateGameIdentity(string gameRoot)
    {
        var root = NormalizeGameRoot(gameRoot);
        if (!Directory.Exists(root)) throw new InvalidOperationException("Thư mục game không tồn tại.");
        if (LoadManifest().Engine == "renpy")
        {
            if (!Directory.Exists(Path.Combine(root, "game")) || !Directory.Exists(Path.Combine(root, "renpy")) || !Directory.Exists(Path.Combine(root, "lib"))
                || !Directory.EnumerateFiles(root, "*.exe").Any())
                throw new InvalidOperationException("Sai thư mục game Ren'Py.");
            return root;
        }
        if (!Directory.EnumerateDirectories(root, "*_Data", SearchOption.TopDirectoryOnly).Any())
            throw new InvalidOperationException("Sai thư mục game: thiếu thư mục Unity *_Data.");
        if (!Directory.EnumerateFiles(root, "*.exe", SearchOption.TopDirectoryOnly).Any())
            throw new InvalidOperationException("Sai thư mục game: không có file .exe ở thư mục gốc.");
        return root;
    }

    private static string ResolveManifestDataPath(string root, string dataDirectory, string? manifestPath)
    {
        if (!string.IsNullOrWhiteSpace(manifestPath))
        {
            var resolved = ResolveSafe(root, manifestPath);
            if (File.Exists(resolved)) return resolved;
            throw new InvalidOperationException($"Sai game/data: không tìm thấy resource theo manifest: {manifestPath}");
        }

        var fallback = Path.Combine(dataDirectory, "data.unity3d");
        return File.Exists(fallback) ? fallback : Path.Combine(dataDirectory, "globalgamemanagers");
    }

    private static UnityLayout DetectUnityLayout(string root, string? preferredExecutable)
    {
        var executables = Directory.EnumerateFiles(root, "*.exe", SearchOption.TopDirectoryOnly)
            .OrderBy(path => Path.GetFileName(path), StringComparer.OrdinalIgnoreCase)
            .ToList();
        if (!string.IsNullOrWhiteSpace(preferredExecutable))
        {
            var preferredName = Path.GetFileName(preferredExecutable);
            executables = executables
                .OrderBy(path => !string.Equals(Path.GetFileName(path), preferredName, StringComparison.OrdinalIgnoreCase))
                .ThenBy(path => Path.GetFileName(path), StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        var executable = executables.FirstOrDefault();
        var dataDirectories = Directory.EnumerateDirectories(root, "*_Data", SearchOption.TopDirectoryOnly)
            .OrderBy(path => Path.GetFileName(path), StringComparer.OrdinalIgnoreCase)
            .ToList();
        if (executable is not null)
        {
            var expectedName = Path.GetFileNameWithoutExtension(executable) + "_Data";
            dataDirectories = dataDirectories
                .OrderBy(path => !string.Equals(Path.GetFileName(path), expectedName, StringComparison.OrdinalIgnoreCase))
                .ThenBy(path => Path.GetFileName(path), StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        return new UnityLayout(executable, dataDirectories.FirstOrDefault());
    }

    private sealed record UnityLayout(string? Executable, string? DataDirectory);

    private static string NormalizeGameRoot(string root) => Path.GetFullPath(root.Trim().Trim('"'));

    private static string ResolveSafe(string baseDirectory, string relative)
    {
        var normalized = relative.Replace('/', Path.DirectorySeparatorChar).Replace('\\', Path.DirectorySeparatorChar);
        if (Path.IsPathRooted(normalized)) throw new InvalidOperationException($"Manifest chứa đường dẫn tuyệt đối: {relative}");
        var baseFull = Path.GetFullPath(baseDirectory) + Path.DirectorySeparatorChar;
        var full = Path.GetFullPath(Path.Combine(baseFull, normalized));
        if (!full.StartsWith(baseFull, StringComparison.OrdinalIgnoreCase)) throw new InvalidOperationException($"Manifest chứa đường dẫn ngoài thư mục: {relative}");
        for (var part = full; !string.IsNullOrEmpty(part); part = Path.GetDirectoryName(part))
            if ((File.Exists(part) || Directory.Exists(part)) && (File.GetAttributes(part) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidOperationException($"Không cài qua link/junction: {part}");
        return full;
    }

    private static string HashFile(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static void WriteJsonAtomic<T>(string path, T value)
    {
        var temp = path + $".{Environment.ProcessId}.tmp";
        File.WriteAllText(temp, JsonSerializer.Serialize(value, JsonOptions));
        File.Move(temp, path, true);
    }

    private void Rollback(string root, IReadOnlyList<InstalledFile> files)
    {
        foreach (var file in files.Reverse())
        {
            var target = ResolveSafe(root, file.Path);
            if (file.OriginalExists)
            {
                var backup = ResolveSafe(BackupDirectory, file.BackupPath);
                if (File.Exists(backup)) File.Copy(backup, target, true);
            }
            else if (File.Exists(target)) File.Delete(target);
        }
    }
}
