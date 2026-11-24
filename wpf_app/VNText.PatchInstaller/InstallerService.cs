using System.IO;
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
    [property: JsonPropertyName("game_checks")] List<GameCheck>? GameChecks = null,
    [property: JsonPropertyName("font_preflight")] JsonElement? FontPreflight = null);

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
    [property: JsonPropertyName("compiled_caches")] List<CompiledCache>? CompiledCaches = null,
    [property: JsonPropertyName("patch_id")] string? PatchId = null,
    [property: JsonPropertyName("notes")] List<string>? Notes = null);

public sealed record CompiledCache(
    [property: JsonPropertyName("path")] string Path,
    [property: JsonPropertyName("original_exists")] bool OriginalExists,
    [property: JsonPropertyName("original_sha256")] string OriginalSha256,
    [property: JsonPropertyName("source_digests")] List<string> SourceDigests);

public sealed partial class InstallerService
{
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true, WriteIndented = true };

    public InstallerService(string patchDirectory)
    {
        PatchDirectory = Path.GetFullPath(patchDirectory);
        ManifestPath = Path.Combine(PatchDirectory, "patch_manifest.json");
        PayloadDirectory = Path.Combine(PatchDirectory, "COPY_TO_GAME_ROOT");
        BackupDirectory = Path.Combine(PatchDirectory, "install_backup");
        StatePath = Path.Combine(PatchDirectory, "install_state.json");
        JournalPath = Path.Combine(PatchDirectory, "install_journal.json");
    }

    public string PatchDirectory { get; }
    public string ManifestPath { get; }
    public string PayloadDirectory { get; }
    public string BackupDirectory { get; }
    public string StatePath { get; }
    /// <summary>Written before the first byte of the game changes and removed only after the install state and the receipt are saved: its presence means
    /// an install was cut off (crash, power loss, kill) and the game must be brought back to the state before it.</summary>
    public string JournalPath { get; }

    /// <summary>Test seam only (the test CLI and harness set it; nothing in the product does): called at each step of a transaction so a test can stop there.</summary>
    internal static Action<string>? FaultPoint;
    private static void Fault(string point) => FaultPoint?.Invoke(point);

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
        if (manifest.FontPreflight is { } font && font.TryGetProperty("glyph_status", out var glyph)
            && glyph.GetString() == "MISSING")
            throw new InvalidOperationException("Font thiếu ký tự bản dịch; hãy chọn font phù hợp và tạo lại patch.");
        if (!Directory.Exists(root)) throw new InvalidOperationException("Thư mục game không tồn tại.");
        if (manifest.Engine == "renpy")
        {
            ValidateGameIdentity(root);
            if (manifest.GameChecks is null || manifest.GameChecks.Count == 0)
                throw new InvalidOperationException("Thiếu bằng chứng nhận dạng game Ren'Py.");
            foreach (var check in manifest.GameChecks)
                if (!File.Exists(ResolveSafe(root, check.Path)) || !string.Equals(HashFile(ResolveSafe(root, check.Path)), check.Sha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException(GameCheckMismatch(check.Path));
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
        // Unity patches that depend on exact player assemblies (TMP runtime adapter) bind them here, as Ren'Py binds its source files.
        foreach (var check in manifest.GameChecks ?? new List<GameCheck>())
            if (!File.Exists(ResolveSafe(root, check.Path)) || !string.Equals(HashFile(ResolveSafe(root, check.Path)), check.Sha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException(GameCheckMismatch(check.Path));
        foreach (var file in manifest.Files)
        {
            var payload = ResolveSafe(PayloadDirectory, file.Path);
            if (!File.Exists(payload)) throw new InvalidOperationException($"Patch thiếu payload: {file.Path}");
            if (!string.Equals(HashFile(payload), file.SourceSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException($"Payload bị thay đổi hoặc hỏng: {file.Path}");
        }
        return root;
    }

    /// <summary>A VNText-written path by name: the generated activation/font files, or anything under the Vietnamese translation folder named vntext*.</summary>
    private static bool LooksLikeVnTextPath(string path)
    {
        var normalized = path.Replace('\\', '/');
        var name = Path.GetFileName(normalized);
        return LegacyNamePrefixes.Any(prefix => name.StartsWith(prefix, StringComparison.OrdinalIgnoreCase))
            || (normalized.StartsWith("game/tl/", StringComparison.OrdinalIgnoreCase) && name.StartsWith("vntext", StringComparison.OrdinalIgnoreCase));
    }

    /// <summary>Why this patch does not fit the game now.  A patch built while another VNText patch was installed fits only that state: say so and how to continue.</summary>
    private static string GameCheckMismatch(string path) => LooksLikeVnTextPath(path)
        ? $"Sai bản game hoặc file nguồn đã thay đổi: {path}. Patch này được tạo khi game đang cài một patch VNText khác, nhưng game hiện không còn ở trạng thái đó "
          + "(đã gỡ, đã về bản gốc sạch hoặc đã cài patch khác). Hãy bấm 'Tạo patch' lại từ game hiện tại rồi cài. Game chưa bị thay đổi."
        : $"Sai bản game hoặc file nguồn đã thay đổi: {path}";

    public InstallState Install(string gameRoot, Action<string>? progress = null)
    {
        using var gameLock = LockGame(gameRoot);
        var recovered = JoinNotes(RecoverPendingInstall(gameRoot), RecoverInterruptedInstall());
        var root = ValidateGame(gameRoot);
        if (File.Exists(StatePath) && FinishCutUninstall() is { } finished) recovered = recovered is null ? finished : recovered + " " + finished;
        if (File.Exists(StatePath)) throw new InvalidOperationException("Patch này đã được cài. Hãy Gỡ cài đặt trước khi cài lại.");
        var manifest = LoadManifest();
        if (Directory.Exists(BackupDirectory) && !RemoveStaleBackups(root))
            throw new InvalidOperationException("Thư mục backup đã tồn tại; giữ nguyên để phục hồi giao dịch trước.");
        var receipt = LoadReceipt(root);
        var patchId = PatchId();
        var notes = new List<string>();
        if (recovered is not null) notes.Add(recovered);
        var createdOriginals = new List<string>();
        var createdTemps = new List<string>();
        var priorReceipt = File.Exists(ReceiptPath(root)) ? File.ReadAllBytes(ReceiptPath(root)) : null;
        // A different VNText patch that is verifiably active may be upgraded only when this patch was built from exactly its installed bytes;
        // otherwise (or when the owned file was edited) layering is refused and nothing is written.
        foreach (var file in manifest.Files)
        {
            var target = ResolveSafe(root, file.Path);
            var owner = NewerOwner(receipt, file.Path, patchId);
            if (owner is null && receipt.Paths.TryGetValue(file.Path, out var same) && same.Layers.Count > 0)
                throw new InvalidOperationException("Patch này đã được ghi nhận là đang cài ở game này.");
            if (owner is null) continue;
            if (!File.Exists(target) || !string.Equals(HashFile(target), owner.InstalledSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException($"{file.Path}: tệp do patch VNText {owner.Version} quản lý đã bị sửa ngoài VNText; không cài chồng. Gỡ hoặc khôi phục game trước.");
            if (!string.Equals(HashFile(target), file.OriginalSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException($"{file.Path}: đang cài patch VNText {owner.Version} nhưng patch này được tạo từ trạng thái khác (không nâng cấp chứng minh được). Gỡ patch hiện tại rồi cài lại, hoặc tạo patch mới từ game đang cài.");
            notes.Add($"{file.Path}: nâng cấp từ patch VNText {owner.Version}; bản gốc đầu tiên được giữ trong biên nhận.");
        }
        // The game itself records that an install is in flight (and which patch folder holds its journal) BEFORE the journal and any game write:
        // whichever VNText patch touches this game next - even one built later from a different package - recovers it first.
        Directory.CreateDirectory(ReceiptDirectory(root));
        WriteJsonAtomic(PendingPath(root), new PendingInstall(PatchDirectory, patchId));
        WriteJournal(new InstallJournal(root, patchId, priorReceipt is null ? null : Convert.ToBase64String(priorReceipt),
            manifest.Files.Select(f => new JournalFile(f.Path, f.Path.Replace('/', Path.DirectorySeparatorChar), f.OriginalExists, f.OriginalSha256, f.SourceSha256)).ToList()));
        Fault("journal-written");
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
                    var digests = new List<string> { Convert.ToHexString(MD5.HashData(source)),
                        Convert.ToHexString(MD5.HashData(source.Concat(System.Text.Encoding.ASCII.GetBytes("_2025-07-06")).ToArray())) };
                    caches.Add(new CompiledCache(relative, exists, exists ? HashFile(cache) : "", digests));
                    var cacheEntry = Claim(root, receipt, relative, "cache", patchId, manifest.Version, "", createdOriginals, notes);
                    foreach (var digest in digests) if (!cacheEntry.SourceDigests.Contains(digest, StringComparer.OrdinalIgnoreCase)) cacheEntry.SourceDigests.Add(digest);
                }
            foreach (var file in manifest.Files)
            {
                progress?.Invoke(file.Path);
                var target = ResolveSafe(root, file.Path);
                var exists = File.Exists(target);
                if (exists != file.OriginalExists)
                    throw new InvalidOperationException(LooksLikeVnTextPath(file.Path) ? GameCheckMismatch(file.Path) : $"Trạng thái file gốc không khớp manifest: {file.Path}");
                if (exists && !string.Equals(HashFile(target), file.OriginalSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException(LooksLikeVnTextPath(file.Path) ? GameCheckMismatch(file.Path) : $"File game đã bị thay đổi, không ghi đè: {file.Path}");

                Claim(root, receipt, file.Path, "file", patchId, manifest.Version, file.SourceSha256, createdOriginals, notes);
                var backupRel = file.Path.Replace('/', Path.DirectorySeparatorChar);
                var backup = ResolveSafe(BackupDirectory, backupRel);
                if (exists)
                {
                    Directory.CreateDirectory(Path.GetDirectoryName(backup)!);
                    File.Copy(target, backup, true);
                }
                Fault("backed-up:" + file.Path);
                var payload = ResolveSafe(PayloadDirectory, file.Path);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                var temp = target + $".vntext-install-{Environment.ProcessId}.tmp";
                createdTemps.Add(temp);
                File.Copy(payload, temp, true);
                try { File.Move(temp, target, true); }
                catch (Exception ex) when (ex is UnauthorizedAccessException or IOException)
                {
                    throw new InvalidOperationException($"Không ghi được {file.Path}: tệp đang chỉ-đọc hoặc bị chương trình khác khóa. Game được giữ nguyên; bỏ chỉ-đọc/đóng game rồi cài lại. ({ex.Message})");
                }
                prepared.Add(new InstalledFile(file.Path, backupRel, exists, file.OriginalSha256, file.SourceSha256));
                Fault("replaced:" + file.Path);
                if (!string.Equals(HashFile(target), file.SourceSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"Kiểm hash sau khi cài thất bại: {file.Path}");
            }
            var state = new InstallState(root, manifest.Version, prepared, caches, patchId, notes);
            WriteJsonAtomic(StatePath, state);
            Fault("state-written");
            SaveReceipt(root, receipt);
            Fault("receipt-saved");
            File.Delete(JournalPath);
            Fault("journal-deleted");
            ClearPending(root);
            return state;
        }
        catch (Exception ex) when (ex is not SimulatedCrashException)
        {
            // Every cleanup step is independent and tolerant: a read-only backup or a locked temp file must not stop the rest of the rollback.
            Attempt(() => Rollback(root, prepared));
            Attempt(() => ForceDeleteDirectory(BackupDirectory));
            Attempt(() => ForceDeleteFile(StatePath));
            foreach (var kept in createdOriginals) Attempt(() => ForceDeleteFile(kept));
            foreach (var temp in createdTemps) Attempt(() => ForceDeleteFile(temp));
            Attempt(() =>
            {
                if (priorReceipt is null) ForceDeleteFile(ReceiptPath(root));
                else { Directory.CreateDirectory(ReceiptDirectory(root)); File.WriteAllBytes(ReceiptPath(root), priorReceipt); }
            });
            Attempt(() => TryDeleteEmpty(OriginalsRoot(root))); Attempt(() => TryDeleteEmpty(ReceiptDirectory(root)));
            Attempt(() => ForceDeleteFile(JournalPath));
            Attempt(() => ClearPending(root));
            throw;
        }
    }

    private sealed record JournalFile(
        [property: JsonPropertyName("path")] string Path,
        [property: JsonPropertyName("backup_path")] string BackupPath,
        [property: JsonPropertyName("original_exists")] bool OriginalExists,
        [property: JsonPropertyName("original_sha256")] string OriginalSha256,
        [property: JsonPropertyName("installed_sha256")] string InstalledSha256);

    private sealed record InstallJournal(
        [property: JsonPropertyName("game_root")] string GameRoot,
        [property: JsonPropertyName("patch_id")] string PatchId,
        [property: JsonPropertyName("prior_receipt_base64")] string? PriorReceiptBase64,
        [property: JsonPropertyName("files")] List<JournalFile> Files);

    private sealed record JournalEnvelope(
        [property: JsonPropertyName("journal")] InstallJournal Journal,
        [property: JsonPropertyName("sha256")] string Sha256);

    private static string JournalDigest(InstallJournal journal) => Convert.ToHexString(SHA256.HashData(JsonSerializer.SerializeToUtf8Bytes(journal, JsonOptions))).ToLowerInvariant();

    private void WriteJournal(InstallJournal journal) => WriteJsonAtomic(JournalPath, new JournalEnvelope(journal, JournalDigest(journal)));

    private const string JournalUnreadable = "Nhật ký giao dịch cài đặt (install_journal.json trong thư mục patch) bị hỏng, cụt hoặc không thuộc patch này; VNText KHÔNG ghi hay xóa tệp game nào. "
        + "Giữ nguyên thư mục patch và game, bấm 'Tạo gói báo lỗi' để gửi cho nhà phát triển. Chi tiết: ";

    /// <summary>Reads the journal and proves it whole (checksum) and this patch's; anything else refuses before any game write.</summary>
    private InstallJournal ReadJournal()
    {
        InstallJournal? journal;
        try
        {
            var bytes = File.ReadAllBytes(JournalPath);
            using var document = JsonDocument.Parse(bytes);
            if (document.RootElement.ValueKind == JsonValueKind.Object && document.RootElement.TryGetProperty("journal", out _))
            {
                var envelope = JsonSerializer.Deserialize<JournalEnvelope>(bytes, JsonOptions) ?? throw new InvalidDataException("rỗng");
                journal = envelope.Journal ?? throw new InvalidDataException("thiếu nội dung");
                if (!string.Equals(JournalDigest(journal), envelope.Sha256, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("checksum không khớp");
            }
            else journal = JsonSerializer.Deserialize<InstallJournal>(bytes, JsonOptions);     // 0.1.32 journal (no checksum): accepted only if every field validates below
            if (journal is null || string.IsNullOrWhiteSpace(journal.GameRoot) || journal.Files is not { Count: > 0 }) throw new InvalidDataException("thiếu trường bắt buộc");
            if (!string.Equals(journal.PatchId, PatchId(), StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("nhật ký của patch khác");
            var root = NormalizeGameRoot(journal.GameRoot);
            foreach (var file in journal.Files)
            {
                if (file is null || string.IsNullOrWhiteSpace(file.Path) || file.InstalledSha256 is not { Length: 64 } || (file.OriginalExists && file.OriginalSha256 is not { Length: 64 }))
                    throw new InvalidDataException("mục tệp không hợp lệ");
                ResolveSafe(root, file.Path); ResolveSafe(BackupDirectory, file.BackupPath);
            }
            if (journal.PriorReceiptBase64 is not null) Convert.FromBase64String(journal.PriorReceiptBase64);
        }
        catch (Exception ex) when (ex is JsonException or InvalidDataException or IOException or FormatException or InvalidOperationException or ArgumentException or NotSupportedException)
        {
            throw new InvalidOperationException(JournalUnreadable + ex.Message);
        }
        return journal;
    }

    /// <summary>
    /// Brings the game back to exactly the state before an install that was cut off (its journal is still here).  An install whose state and receipt
    /// were both saved is complete and kept.  Otherwise every journal file is first classified against its two known states (before / after the install);
    /// if any is neither (edited by hand, or a backup that does not prove the original) nothing is written and the files are named.  Then each file is put
    /// back (from its proven backup, or removed when it did not exist before), the receipt is restored byte for byte, first-original copies it created are
    /// dropped, and the backup, state and journal are removed last.  Every step can be cut off and run again.  Returns a note, or null when there was nothing to recover.
    /// </summary>
    public string? RecoverInterruptedInstall()
    {
        if (!File.Exists(JournalPath)) return null;
        var journal = ReadJournal();
        var root = NormalizeGameRoot(journal.GameRoot);
        using var gameLock = LockGame(root);
        if (File.Exists(StatePath) && File.Exists(ReceiptPath(root)) && CompletedInstall(root, journal))
        {
            File.Delete(JournalPath);
            ClearPending(root);
            return "Lần cài trước đã hoàn tất trước khi bị ngắt; giữ nguyên kết quả.";
        }
        var actions = new List<(JournalFile File, string Target, bool Restore, bool Delete)>();
        var unknown = new List<string>();
        foreach (var file in journal.Files)
        {
            var target = ResolveSafe(root, file.Path);
            var current = File.Exists(target) ? HashFile(target) : null;
            var backup = ResolveSafe(BackupDirectory, file.BackupPath);
            if (file.OriginalExists)
            {
                if (string.Equals(current, file.OriginalSha256, StringComparison.OrdinalIgnoreCase)) actions.Add((file, target, false, false));   // never reached, or already put back
                else if (string.Equals(current, file.InstalledSha256, StringComparison.OrdinalIgnoreCase)
                         && File.Exists(backup) && string.Equals(HashFile(backup), file.OriginalSha256, StringComparison.OrdinalIgnoreCase))
                    actions.Add((file, target, true, false));
                else unknown.Add(file.Path);
            }
            else if (current is null) actions.Add((file, target, false, false));
            else if (string.Equals(current, file.InstalledSha256, StringComparison.OrdinalIgnoreCase)) actions.Add((file, target, false, true));
            else unknown.Add(file.Path);
        }
        if (unknown.Count > 0)
            throw new InvalidOperationException("Lần cài trước bị ngắt giữa chừng, nhưng các tệp sau không ở trạng thái trước hay sau lần cài đó (có thể đã bị sửa tay, hoặc bản sao lưu không chứng minh được bản gốc): "
                + string.Join(", ", unknown) + ". VNText giữ nguyên toàn bộ game, bản sao lưu và nhật ký, không ghi đè gì. Hãy trả các tệp này về như cũ rồi thử lại, hoặc bấm 'Tạo gói báo lỗi'.");
        foreach (var (file, target, restore, delete) in actions)
        {
            var folder = Path.GetDirectoryName(target)!;
            if (Directory.Exists(folder))
                foreach (var temp in Directory.EnumerateFiles(folder, Path.GetFileName(target) + ".vntext-install-*.tmp"))
                    ForceDeleteFile(temp);
            if (restore)
            {
                Directory.CreateDirectory(folder);
                var staged = target + $".vntext-recover-{Environment.ProcessId}.tmp";
                File.Copy(ResolveSafe(BackupDirectory, file.BackupPath), staged, true);
                File.Move(staged, target, true);
                if (!string.Equals(HashFile(target), file.OriginalSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"Không khôi phục được {file.Path} từ bản sao lưu; giữ nguyên để kiểm tra.");
            }
            else if (delete) File.Delete(target);
            if (Directory.Exists(folder))
                foreach (var temp in Directory.EnumerateFiles(folder, Path.GetFileName(target) + ".vntext-recover-*.tmp"))
                    ForceDeleteFile(temp);
            Fault("recover-file:" + file.Path);
        }
        var receiptPath = ReceiptPath(root);
        if (journal.PriorReceiptBase64 is null) ForceDeleteFile(receiptPath);
        else { Directory.CreateDirectory(ReceiptDirectory(root)); WriteBytesAtomic(receiptPath, Convert.FromBase64String(journal.PriorReceiptBase64)); }
        Fault("recover-receipt");
        // First-original copies are kept only for the paths the restored receipt still records.
        var kept = LoadReceipt(root);
        if (Directory.Exists(OriginalsRoot(root)))
            foreach (var copy in Directory.EnumerateFiles(OriginalsRoot(root), "*", SearchOption.AllDirectories).ToList())
            {
                var relative = Path.GetRelativePath(OriginalsRoot(root), copy).Replace(Path.DirectorySeparatorChar, '/');
                if (!(kept.Paths.TryGetValue(relative, out var entry) && entry.FirstOriginalExists)) ForceDeleteFile(copy);
            }
        TryDeleteEmpty(OriginalsRoot(root)); TryDeleteEmpty(ReceiptDirectory(root));
        ForceDeleteFile(StatePath);
        Fault("recover-state-deleted");
        ForceDeleteDirectory(BackupDirectory);
        Fault("recover-backup-deleted");
        File.Delete(JournalPath);
        Fault("recover-journal-deleted");
        ClearPending(root);
        return "Lần cài trước bị ngắt giữa chừng (tắt máy/đóng ứng dụng); VNText đã đưa game về đúng trạng thái trước lần cài đó (hash đã kiểm).";
    }

    private sealed record PendingInstall(
        [property: JsonPropertyName("patch_directory")] string PatchDirectory,
        [property: JsonPropertyName("patch_id")] string PatchId);

    private static string PendingPath(string root) => Path.Combine(ReceiptDirectory(root), "pending_install.json");

    private static string? JoinNotes(string? first, string? second) => first is null ? second : second is null ? first : first + " " + second;

    /// <summary>Removes the in-flight marker (only after the journal is gone) and an emptied receipt folder.</summary>
    private static void ClearPending(string root)
    {
        ForceDeleteFile(PendingPath(root));
        TryDeleteEmpty(OriginalsRoot(root)); TryDeleteEmpty(ReceiptDirectory(root));
    }

    /// <summary>True when an install into this game was cut off and has not been recovered yet (by any VNText patch).</summary>
    public static bool HasPendingInstall(string gameRoot)
    {
        var root = NormalizeGameRoot(gameRoot);
        return Directory.Exists(root) && File.Exists(PendingPath(root));
    }

    /// <summary>
    /// Recovers an install into this game that was cut off, whichever patch it was: the game's marker names the patch folder holding the journal and backups,
    /// and that patch's own recovery runs (same checks: journal checksum, known states only, nothing written otherwise).  A marker whose patch folder still
    /// exists but has no journal is a finished operation (the journal goes first) and is simply removed.  A marker whose patch folder is gone cannot be
    /// recovered safely: nothing is written and the person is told what to do.  Returns a note, or null when nothing was pending.
    /// </summary>
    public static string? RecoverPendingInstall(string gameRoot)
    {
        var root = NormalizeGameRoot(gameRoot);
        var marker = PendingPath(root);
        if (!File.Exists(marker)) return null;
        using var gameLock = LockGame(root);
        PendingInstall? pending;
        try { pending = JsonSerializer.Deserialize<PendingInstall>(File.ReadAllText(marker), JsonOptions); }
        catch (Exception ex) when (ex is JsonException or IOException) { pending = null; _ = ex; }
        if (pending is null || string.IsNullOrWhiteSpace(pending.PatchDirectory) || !Path.IsPathRooted(pending.PatchDirectory))
            throw new InvalidOperationException("Game có dấu hiệu một lần cài VNText bị ngắt (.vntext/pending_install.json) nhưng tệp đó hỏng; VNText KHÔNG ghi hay xóa tệp game nào. "
                + "Bấm 'Tạo gói báo lỗi' để gửi cho nhà phát triển.");
        var owner = new InstallerService(pending.PatchDirectory);
        if (!Directory.Exists(owner.PatchDirectory) || !File.Exists(owner.ManifestPath))
            throw new InvalidOperationException($"Lần cài patch VNText trước vào game này bị ngắt giữa chừng, nhưng thư mục patch giữ nhật ký và bản sao lưu ({owner.PatchDirectory}) không còn; "
                + "VNText KHÔNG ghi hay xóa tệp game nào vì không chứng minh được bản trước khi cài. Hãy trả lại thư mục đó (hoặc chạy lại đúng trình cài patch đó), hoặc bấm 'Tạo gói báo lỗi'.");
        if (!File.Exists(owner.JournalPath))
        {
            ClearPending(root);
            return null;
        }
        if (!string.Equals(owner.PatchId(), pending.PatchId, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException(JournalUnreadable + "dấu cài dở trong game không khớp patch giữ nhật ký");
        var note = owner.RecoverInterruptedInstall();
        if (File.Exists(marker) && !File.Exists(owner.JournalPath)) ClearPending(root);
        return note;
    }

    /// <summary>
    /// One VNText writer per game at a time, across processes (the app's dialog and any standalone patch installer): a named OS mutex keyed by the game
    /// folder, released by Windows if the holder dies.  A second writer is refused before it reads or writes anything.
    /// </summary>
    private static IDisposable LockGame(string root)
    {
        var key = Convert.ToHexString(SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(NormalizeGameRoot(root).TrimEnd(Path.DirectorySeparatorChar).ToUpperInvariant())))[..32];
        var mutex = new Mutex(false, "Local\\VNTextGame-" + key);
        bool owned;
        try { owned = mutex.WaitOne(0); }
        catch (AbandonedMutexException) { owned = true; }     // the previous writer died; its journal (if any) is recovered next
        if (!owned)
        {
            mutex.Dispose();
            throw new InvalidOperationException("Một trình cài/gỡ VNText khác đang ghi vào game này. Chờ nó xong (hoặc đóng nó) rồi thử lại. Game chưa bị thay đổi bởi lần bấm này.");
        }
        return new GameLock(mutex);
    }

    private sealed class GameLock(Mutex mutex) : IDisposable
    {
        private Mutex? _mutex = mutex;
        public void Dispose() { var m = Interlocked.Exchange(ref _mutex, null); if (m is null) return; try { m.ReleaseMutex(); } finally { m.Dispose(); } }
    }

    /// <summary>
    /// An uninstall cut off after it had put every file back and dropped this patch's receipt layer leaves only its state and backups behind.  When
    /// every file is provably back in its pre-install state and no receipt layer of this patch remains, those leftovers are removed (nothing in the game
    /// changes).  Returns a note, or null when this is not that case.
    /// </summary>
    private string? FinishCutUninstall()
    {
        if (!File.Exists(StatePath) || File.Exists(JournalPath)) return null;
        InstallState? state;
        try { state = JsonSerializer.Deserialize<InstallState>(File.ReadAllText(StatePath), JsonOptions); }
        catch (JsonException) { return null; }
        if (state?.Files is not { Count: > 0 } || string.IsNullOrEmpty(state.PatchId)) return null;
        var root = NormalizeGameRoot(state.GameRoot);
        if (!Directory.Exists(root)) return null;
        var receipt = LoadReceipt(root);
        foreach (var file in state.Files)
        {
            var target = ResolveSafe(root, file.Path);
            var restored = file.OriginalExists
                ? File.Exists(target) && string.Equals(HashFile(target), file.OriginalSha256, StringComparison.OrdinalIgnoreCase)
                : !File.Exists(target);
            var stillLayered = receipt.Paths.TryGetValue(file.Path, out var entry)
                && entry.Layers.Any(layer => string.Equals(layer.PatchId, state.PatchId, StringComparison.OrdinalIgnoreCase));
            if (!restored || stillLayered) return null;
        }
        File.Delete(StatePath);
        DeleteConsumedBackups(state);
        return "Lần gỡ trước đã đưa game về đúng trạng thái trước khi cài nhưng bị ngắt trước khi dọn tệp ghi nhận; đã dọn xong (game không bị thay đổi).";
    }

    private bool CompletedInstall(string root, InstallJournal journal)
    {
        var receipt = LoadReceipt(root);
        return journal.Files.All(file => receipt.Paths.TryGetValue(file.Path, out var entry) && entry.Layers.Count > 0
            && string.Equals(entry.Layers[^1].PatchId, journal.PatchId, StringComparison.OrdinalIgnoreCase)
            && File.Exists(ResolveSafe(root, file.Path))
            && string.Equals(HashFile(ResolveSafe(root, file.Path)), file.InstalledSha256, StringComparison.OrdinalIgnoreCase));
    }

    /// <summary>A backup folder left by an uninstall that restored everything but was cut off before removing it: every backup equals the game file again.</summary>
    private bool RemoveStaleBackups(string root)
    {
        if (File.Exists(StatePath) || File.Exists(JournalPath)) return false;
        foreach (var backup in Directory.EnumerateFiles(BackupDirectory, "*", SearchOption.AllDirectories))
        {
            var target = Path.Combine(root, Path.GetRelativePath(BackupDirectory, backup));
            if (!File.Exists(target) || !string.Equals(HashFile(target), HashFile(backup), StringComparison.OrdinalIgnoreCase)) return false;
        }
        ForceDeleteDirectory(BackupDirectory);
        return true;
    }

    public UninstallResult Uninstall(string gameRoot, Action<string>? progress = null, UninstallMode mode = UninstallMode.Previous)
    {
        using var gameLock = LockGame(gameRoot);
        var recovered = JoinNotes(RecoverPendingInstall(gameRoot), RecoverInterruptedInstall());
        if (recovered is not null && !File.Exists(StatePath)) return new UninstallResult(new List<string> { recovered });
        if (FinishCutUninstall() is { } finished) return new UninstallResult(new List<string> { finished });
        // This patch is not the installed one (for example the game was stepped back to the previous VNText patch): the receipt alone proves the clean original.
        if (mode == UninstallMode.CleanOriginal && !File.Exists(StatePath)) return RestoreCleanOriginalFromReceipt(gameRoot, progress);
        var state = ValidateInstalledState(gameRoot);
        var root = NormalizeGameRoot(state.GameRoot);
        var notes = new List<string>();
        if (mode == UninstallMode.CleanOriginal)
        {
            var clean = RestoreCleanOriginal(root, state, progress);
            File.Delete(StatePath);
            DeleteConsumedBackups(state);
            var cleanLeftovers = FindUnverifiedLeftovers(root, state.Files.Select(f => f.Path).Concat((state.CompiledCaches ?? new List<CompiledCache>()).Select(c => c.Path)));
            if (cleanLeftovers.Count > 0) clean.Notes.Add(LeftoverNote(cleanLeftovers));
            return clean;
        }
        var receipt = LoadReceipt(root);
        foreach (var entry in state.Files.Where(f => f.OriginalExists))
            if (receipt.Paths.TryGetValue(entry.Path, out var owned) && owned.Layers.Count == 1 && owned.Provenance == "legacy_vntext_unreceipted")
                notes.Add($"{entry.Path}: đã khôi phục bản Việt hóa VNText cũ không có biên nhận (không phải game gốc sạch); gỡ tiếp patch cũ nếu cần.");
            else if (owned is not null && owned.Layers.Count == 1 && owned.Provenance == "unmanaged_existing")
                notes.Add($"{entry.Path}: đã khôi phục tệp có sẵn không do VNText quản lý.");
        foreach (var cache in state.CompiledCaches ?? new List<CompiledCache>())
        {
            progress?.Invoke(cache.Path);
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
            Fault("restored:" + file.Path);
        }
        foreach (var path in state.Files.Select(f => f.Path).Concat((state.CompiledCaches ?? new List<CompiledCache>()).Select(c => c.Path)))
            RemoveLayer(receipt, root, path, state.PatchId ?? "");
        SaveReceipt(root, receipt);
        Fault("uninstall-receipt-saved");
        File.Delete(StatePath);
        Fault("uninstall-state-deleted");
        DeleteConsumedBackups(state);
        // Say plainly WHAT the game is now: the previous VNText layer (still translated) or no VNText layer at all, verified by hash above.
        var after = LoadReceipt(root);
        var stillOwned = state.Files.Count(f => after.Paths.TryGetValue(f.Path, out var left) && left.Layers.Count > 0);
        var legacyRestored = notes.Any(n => n.Contains("không có biên nhận"));
        notes.Add(stillOwned > 0
            ? $"Đã khôi phục bản VNText TRƯỚC ĐÓ cho {stillOwned} tệp (hash đã khớp); game vẫn là bản Việt hóa của patch trước, không phải game gốc sạch. Bấm «Về bản gốc sạch» để về game gốc (chứng minh bằng biên nhận)."
            : legacyRestored
                ? "Đã khôi phục tệp về bản Việt hóa VNText cũ không có biên nhận (hash đã khớp); đây KHÔNG phải game gốc sạch."
                : state.Files.Any(f => f.OriginalExists)
                    ? "Đã khôi phục các tệp về trạng thái trước khi cài patch này (hash đã khớp)."
                    : "Đã gỡ các tệp của patch này; trước đó chúng không tồn tại (hash đã kiểm).");
        var leftovers = FindUnverifiedLeftovers(root, state.Files.Select(f => f.Path).Concat((state.CompiledCaches ?? new List<CompiledCache>()).Select(c => c.Path)));
        if (leftovers.Count > 0) notes.Add(LeftoverNote(leftovers));
        return new UninstallResult(notes);
    }

    private void DeleteConsumedBackups(InstallState state)
    {
        // Remove only our consumed backups. Foreign additions are preserved.
        var consumed = state.Files.Where(f => f.OriginalExists).Select(f => f.BackupPath)
            .Concat((state.CompiledCaches ?? new List<CompiledCache>()).Where(c => c.OriginalExists).Select(c => c.Path));
        foreach (var relative in consumed)
        {
            var backup = ResolveSafe(BackupDirectory, relative);
            ForceDeleteFile(backup);
            for (var directory = Path.GetDirectoryName(backup); directory is not null
                && directory.StartsWith(BackupDirectory + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
                directory = Path.GetDirectoryName(directory))
                if (Directory.Exists(directory) && !Directory.EnumerateFileSystemEntries(directory).Any()) Directory.Delete(directory);
        }
        // A backup folder that is already gone (never needed for patch-only files, or removed by hand) is not an error after a successful restore.
        if (Directory.Exists(BackupDirectory) && !Directory.EnumerateFileSystemEntries(BackupDirectory).Any()) Directory.Delete(BackupDirectory);
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

        var receipt = LoadReceipt(root);
        foreach (var file in state.Files)
        {
            var target = ResolveSafe(root, file.Path);
            // An uninstall cut off part way has already put some files back: they are in their pre-install state, which the next run simply confirms.
            var alreadyRestored = file.OriginalExists
                ? File.Exists(target) && string.Equals(HashFile(target), file.OriginalSha256, StringComparison.OrdinalIgnoreCase)
                : !File.Exists(target);
            // The receipt drops this patch's layer only after every file is back, so a restored file under a receipt that still shows this patch on top
            // proves an uninstall in progress (and not a file changed by someone else).
            if (!string.IsNullOrEmpty(state.PatchId) && receipt.Paths.TryGetValue(file.Path, out var pending)
                && pending.Layers.Count > 0 && string.Equals(pending.Layers[^1].PatchId, state.PatchId, StringComparison.OrdinalIgnoreCase))
            {
                // A clean-original restore cut off part way has put some files back to the receipt's first original instead.
                var atFirstOriginal = pending.FirstOriginalExists
                    ? File.Exists(target) && string.Equals(HashFile(target), pending.FirstOriginalSha256, StringComparison.OrdinalIgnoreCase)
                    : !File.Exists(target);
                if (alreadyRestored || atFirstOriginal) continue;
            }
            if (!File.Exists(target) || !string.Equals(HashFile(target), file.InstalledSha256, StringComparison.OrdinalIgnoreCase))
            {
                if (!string.IsNullOrEmpty(state.PatchId) && NewerOwner(receipt, file.Path, state.PatchId) is { } newer)
                    throw new InvalidOperationException($"{file.Path}: patch VNText {newer.Version} mới hơn đang quản lý tệp này; gỡ patch đó trước (hoặc chọn Khôi phục bản gốc từ patch đó).");
                if (!string.IsNullOrEmpty(state.PatchId) && !(receipt.Paths.TryGetValue(file.Path, out var mine)
                    && mine.Layers.Any(layer => string.Equals(layer.PatchId, state.PatchId, StringComparison.OrdinalIgnoreCase))))
                    throw new InvalidOperationException($"{file.Path}: patch này đã bị thay thế hoặc gỡ qua Khôi phục bản gốc; không còn gì để gỡ.");
            }
            if (!File.Exists(target) || !string.Equals(HashFile(target), file.InstalledSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException($"File đã bị thay đổi sau khi cài, không tự động khôi phục: {file.Path}");
            // Resolve the backup path during validation too, so a malformed
            // state cannot later escape the patch backup directory.
            if (file.OriginalExists)
            {
                var backup = ResolveSafe(BackupDirectory, file.BackupPath);
                if (!File.Exists(backup) || !string.Equals(HashFile(backup), file.OriginalSha256, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException($"Backup thiếu hoặc đã thay đổi; không ghi vào game: {file.Path}. Game chưa bị thay đổi: các tệp patch vẫn ở nguyên vị trí và không có gì bị xóa.");
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
                || !(cache.SourceDigests.Contains(Convert.ToHexString(digest), StringComparer.OrdinalIgnoreCase)
                || (receipt.Paths.TryGetValue(cache.Path, out var known) && known.SourceDigests.Contains(Convert.ToHexString(digest), StringComparer.OrdinalIgnoreCase))))
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

    private static void Attempt(Action step) { try { step(); } catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { } }

    private static void ForceDeleteFile(string path)
    {
        if (!File.Exists(path)) return;
        File.SetAttributes(path, File.GetAttributes(path) & ~FileAttributes.ReadOnly);
        File.Delete(path);
    }

    private static void ForceDeleteDirectory(string directory)
    {
        if (!Directory.Exists(directory)) return;
        foreach (var file in Directory.EnumerateFiles(directory, "*", SearchOption.AllDirectories))
            File.SetAttributes(file, File.GetAttributes(file) & ~FileAttributes.ReadOnly);
        Directory.Delete(directory, true);
    }

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

    private static void WriteJsonAtomic<T>(string path, T value) => WriteBytesAtomic(path, JsonSerializer.SerializeToUtf8Bytes(value, JsonOptions));

    /// <summary>Temp file, flushed to disk, then renamed over the target: a crash leaves either the old or the new file, never a torn one.</summary>
    private static void WriteBytesAtomic(string path, byte[] bytes)
    {
        var temp = path + $".{Environment.ProcessId}.tmp";
        using (var stream = new FileStream(temp, FileMode.Create, FileAccess.Write, FileShare.None))
        {
            stream.Write(bytes);
            stream.Flush(true);
        }
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

/// <summary>Thrown only by a test fault point to stand in for the process dying there: it skips the in-process rollback on purpose.</summary>
public sealed class SimulatedCrashException(string point) : Exception("simulated crash at " + point);
