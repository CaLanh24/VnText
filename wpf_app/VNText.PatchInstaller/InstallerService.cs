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
    [property: JsonPropertyName("game_executable")] string GameExecutable = "");

public sealed record InstalledFile(
    [property: JsonPropertyName("path")] string Path,
    [property: JsonPropertyName("backup_path")] string BackupPath,
    [property: JsonPropertyName("original_exists")] bool OriginalExists,
    [property: JsonPropertyName("original_sha256")] string OriginalSha256,
    [property: JsonPropertyName("installed_sha256")] string InstalledSha256);

public sealed record InstallState(
    [property: JsonPropertyName("game_root")] string GameRoot,
    [property: JsonPropertyName("patch_version")] string PatchVersion,
    [property: JsonPropertyName("files")] List<InstalledFile> Files);

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
        if (Directory.Exists(BackupDirectory)) Directory.Delete(BackupDirectory, true);
        Directory.CreateDirectory(BackupDirectory);
        var prepared = new List<InstalledFile>();
        try
        {
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
            }
            var state = new InstallState(root, manifest.Version, prepared);
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
                _ = ResolveSafe(BackupDirectory, file.BackupPath);
        }
        return state;
    }

    private string ValidateGameIdentity(string gameRoot)
    {
        var root = NormalizeGameRoot(gameRoot);
        if (!Directory.Exists(root)) throw new InvalidOperationException("Thư mục game không tồn tại.");
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
