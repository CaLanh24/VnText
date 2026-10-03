using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using System.Threading;
using System.Threading.Tasks;

namespace VNText.Studio.App.Services;

internal sealed record FullAppUpdateSelection(string PackagePath, string PackageSha256, FullAppUpdateService.FullAppUpdateManifest Manifest);
internal sealed class FullAppBaselineMismatchException(string message) : Exception(message);

/// <summary>Validates and atomically applies SHA-256-verified full application deltas.</summary>
internal static class FullAppUpdateService
{
    internal const string FeedName = "full-app-update-current.json";
    internal const string PackageManifestName = "full-app-update-manifest.json";
    internal const string OwnershipName = ".update/owned-files.json";
    private const string PendingName = ".update/pending-full-app-update.json";
    private const long MaxPackageBytes = 536_870_912;
    private const long MaxExpandedBytes = 3L * 1024 * 1024 * 1024;
    private const long MaxManifestBytes = 8L * 1024 * 1024;
    private const int MaxFileCount = 20_000;
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true };

    internal static bool HasLocalFeed(string root)
    {
        var source = ReadSource(root);
        var path = Path.Combine(source.UpdatesRoot, FeedName);
        EnsureNoReparsePathOutsideRoot(path, "full-app Updates manifest");
        return File.Exists(path);
    }

    internal static FullAppUpdateSelection ReadLocalPackage(string root)
    {
        var source = ReadSource(root);
        var feedPath = Path.Combine(source.UpdatesRoot, FeedName);
        EnsureNoReparsePathOutsideRoot(feedPath, "full-app Updates manifest");
        if (new FileInfo(feedPath).Length <= 0 || new FileInfo(feedPath).Length > MaxManifestBytes)
            throw new InvalidDataException("Full-app Updates manifest size is invalid.");
        using var feed = JsonDocument.Parse(File.ReadAllText(feedPath));
        var element = feed.RootElement;
        if (element.ValueKind != JsonValueKind.Object || GetInt(element, "schema") != 1)
            throw new InvalidDataException("Full-app Updates manifest is invalid.");
        EnsureUniqueProperties(element);
        var packageName = GetString(element, "package_file");
        var digest = GetString(element, "package_sha256");
        if (Path.GetFileName(packageName) != packageName || !packageName.StartsWith("full-app-update-", StringComparison.Ordinal) ||
            !packageName.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) || !IsSha256(digest))
            throw new InvalidDataException("Full-app Updates package path or hash is invalid.");
        var packagePath = Path.Combine(source.UpdatesRoot, packageName);
        EnsureNoReparsePathOutsideRoot(packagePath, "full-app update package");
        var manifest = DeserializeManifest(element.GetProperty("manifest"));
        return ValidatePackage(root, source, packagePath, digest, manifest, expectedVersion: manifest.Version);
    }

    internal static FullAppUpdateSelection ReadGitHubPackage(string root, string sourcePath,
        string packagePath, string packageSha256, string version)
    {
        var source = ReadSource(root, sourcePath);
        packagePath = Path.GetFullPath(packagePath);
        RequireUnderRoot(source.WorkRoot, packagePath, "GitHub full-app package");
        RequireOutsideData(root, packagePath);
        EnsureNoReparsePath(root, packagePath, "GitHub full-app package");
        var packageInfo = new FileInfo(packagePath);
        if (!packageInfo.Exists || packageInfo.Length <= 0 || packageInfo.Length > MaxPackageBytes)
            throw new InvalidDataException("GitHub full-app package size is invalid.");
        if (!IsSha256(packageSha256) || !FixedEquals(HashFile(packagePath), packageSha256) || !TryParseVersion(version, out _))
            throw new InvalidDataException("GitHub full-app package hash or version is invalid.");
        using var archive = ZipFile.OpenRead(packagePath);
        var entry = archive.GetEntry(PackageManifestName) ?? throw new InvalidDataException("Full-app package manifest is missing.");
        if (entry.Length <= 0 || entry.Length > MaxManifestBytes)
            throw new InvalidDataException("Full-app package manifest size is invalid.");
        EnsureNoDuplicateJsonProperties(entry);
        var manifest = DeserializeManifest(entry);
        if (!string.Equals(manifest.Version, version, StringComparison.Ordinal))
            throw new InvalidDataException("Full-app package version does not match its GitHub release tag.");
        return ValidatePackage(root, source, packagePath, packageSha256, manifest, expectedVersion: version);
    }

    internal static bool TryGetAvailableVersion(string root, out string version, out string status)
    {
        version = "";
        status = "";
        try
        {
            var update = ReadLocalPackage(root);
            version = update.Manifest.Version;
            return true;
        }
        catch (Exception ex)
        {
            status = "Không thể kiểm tra gói cập nhật đầy đủ: " + ex.Message;
            return false;
        }
    }

    internal static int RunUpdater(string sourcePath, string root, int appPid, int? workerPid,
        bool fromGitHub, string packagePath = "", string packageSha256 = "", string version = "",
        bool bindToRunningInstall = true, bool waitForProcesses = true, bool restartApp = true,
        Func<string, string, bool>? healthCheck = null, Action<string>? startAppOverride = null)
    {
        root = Path.GetFullPath(root);
        sourcePath = Path.GetFullPath(sourcePath);
        if (!SamePath(sourcePath, Path.Combine(root, ".vntext-update-source.json"))) return 3;
        if (bindToRunningInstall && !SamePath(root, Path.GetDirectoryName(WorkerPaths.MainExePath())!)) return 3;
        UpdateSource source;
        try
        {
            EnsureNoReparsePath(root, sourcePath, "Update source configuration");
            source = ReadSource(root, sourcePath);
            ValidatePaths(root, source);
        }
        catch { return 5; }

        var appExited = false;
        var appRestarted = false;
        var preserveTransaction = false;
        string? backupRoot = null;
        string? stagingRoot = null;
        string? pendingPath = null;
        FullAppUpdateManifest? manifest = null;
        UpdateJournal? journal = null;
        void Restart()
        {
            if (!restartApp) return;
            if (startAppOverride is null) StartApp(root);
            else startAppOverride(root);
        }
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(source.LogPath)!);
            Log(source.LogPath, "waiting for app and worker to exit normally");
            if (waitForProcesses && !WaitForExit(appPid, TimeSpan.FromSeconds(90))) return 4;
            appExited = true;
            if (waitForProcesses && workerPid.HasValue && !WaitForExit(workerPid.Value, TimeSpan.FromSeconds(30)))
            {
                Restart();
                return 4;
            }
            RecoverInterruptedUpdate(root, source, throwOnFailure: true);
            var selection = fromGitHub
                ? ReadGitHubPackage(root, sourcePath, packagePath, packageSha256, version)
                : ReadLocalPackage(root);
            manifest = selection.Manifest;
            var transactionId = "txn-" + Guid.NewGuid().ToString("N");
            backupRoot = Path.Combine(source.BackupRoot, transactionId);
            stagingRoot = Path.Combine(source.StagingRoot, transactionId);
            pendingPath = SafeTemporaryTarget(root, PendingName);
            RequireOutsideData(root, pendingPath);
            EnsureNoReparsePath(root, backupRoot, "full-app backup directory");
            EnsureNoReparsePath(root, stagingRoot, "full-app staging directory");
            Directory.CreateDirectory(backupRoot);
            Directory.CreateDirectory(stagingRoot);

            using (var archive = ZipFile.OpenRead(selection.PackagePath))
            {
                foreach (var relative in manifest.AddFiles.Keys.Concat(manifest.ReplaceFiles.Keys).OrderBy(name => name, StringComparer.Ordinal))
                {
                    var entry = archive.GetEntry(relative) ?? throw new InvalidDataException("Full-app package file is missing: " + relative);
                    var staged = SafeTarget(stagingRoot, relative);
                    Directory.CreateDirectory(Path.GetDirectoryName(staged)!);
                    var record = manifest.Files[relative];
                    CopyEntryBounded(entry, staged, record.Size);
                    if (new FileInfo(staged).Length != record.Size || !FixedEquals(HashFile(staged), record.Sha256))
                        throw new InvalidDataException("Staged full-app file hash or size mismatch: " + relative);
                }
            }

            foreach (var relative in manifest.ReplaceFiles.Keys.Concat(manifest.DeleteFiles).OrderBy(name => name, StringComparer.Ordinal))
            {
                var sourceFile = SafeTarget(root, relative);
                var backupFile = SafeTarget(backupRoot, relative);
                Directory.CreateDirectory(Path.GetDirectoryName(backupFile)!);
                File.Copy(sourceFile, backupFile, overwrite: false);
                var expected = manifest.BaseFiles[relative];
                if (new FileInfo(backupFile).Length != expected.Size || !FixedEquals(HashFile(backupFile), expected.Sha256))
                    throw new IOException("Full-app backup verification failed: " + relative);
            }
            var ownershipPath = Path.Combine(root, OwnershipName.Replace('/', Path.DirectorySeparatorChar));
            EnsureNoReparsePath(root, ownershipPath, "full-app ownership manifest");
            var ownershipBackup = SafeTemporaryTarget(backupRoot, "ownership.previous.json");
            var ownershipExisted = File.Exists(ownershipPath);
            long ownershipPreviousSize = 0;
            string ownershipPreviousSha256 = "";
            if (ownershipExisted)
            {
                ValidateOwnershipFile(ownershipPath, manifest.BaseFiles.Keys);
                File.Copy(ownershipPath, ownershipBackup, overwrite: false);
                ownershipPreviousSize = new FileInfo(ownershipBackup).Length;
                ownershipPreviousSha256 = HashFile(ownershipBackup);
            }
            journal = new UpdateJournal
            {
                Schema = 1, TransactionId = transactionId,
                BaseFiles = manifest.BaseFiles, Files = manifest.Files,
                AddFiles = manifest.AddFiles, ReplaceFiles = manifest.ReplaceFiles,
                DeleteFiles = manifest.DeleteFiles, OwnershipExisted = ownershipExisted,
                OwnershipPreviousSize = ownershipPreviousSize, OwnershipPreviousSha256 = ownershipPreviousSha256,
            };
            WriteJsonAtomic(pendingPath, journal);

            foreach (var relative in manifest.AddFiles.Keys.Concat(manifest.ReplaceFiles.Keys).OrderBy(name => name, StringComparer.Ordinal))
            {
                var target = SafeTarget(root, relative);
                var staged = SafeTarget(stagingRoot, relative);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                if (manifest.AddFiles.ContainsKey(relative))
                {
                    if (File.Exists(target) || Directory.Exists(target)) throw new InvalidDataException("Full-app add target already exists: " + relative);
                    File.Move(staged, target);
                }
                else
                {
                    if (!FixedEquals(HashFile(target), manifest.BaseFiles[relative].Sha256))
                        throw new FullAppBaselineMismatchException("Installed file changed during update: " + relative);
                    ReplaceExistingFile(staged, target);
                }
                Log(source.LogPath, "installed " + relative);
                if (source.FaultInjectInterruptAfterFirstReplace && relative != "VNText Studio.exe")
                {
                    preserveTransaction = true;
                    return 7;
                }
            }
            foreach (var relative in manifest.DeleteFiles)
            {
                var target = SafeTarget(root, relative);
                if (!FixedEquals(HashFile(target), manifest.BaseFiles[relative].Sha256))
                    throw new FullAppBaselineMismatchException("Installed file changed before deletion: " + relative);
                File.Delete(target);
                Log(source.LogPath, "deleted " + relative);
            }
            RemoveEmptyAppDirectories(root);
            VerifyInventory(root, manifest.Files);
            ValidateInstalledMetadata(root, manifest);
            var health = healthCheck ?? RunHealthCheck;
            if (!health(Path.Combine(root, "VNText Studio.exe"), root))
                throw new InvalidOperationException("Updated application and worker health check failed.");
            Log(source.LogPath, "full-app health check passed");
            WriteJsonAtomic(ownershipPath, manifest.Files.Keys.OrderBy(name => name, StringComparer.Ordinal).ToArray());
            journal.CommitReady = true;
            WriteJsonAtomic(pendingPath, journal);
            Restart();
            appRestarted = restartApp;
            try { File.Delete(pendingPath); }
            catch (Exception ex)
            {
                preserveTransaction = true;
                Log(source.LogPath, "full-app update is healthy; startup will finalize its committed journal: " + ex.Message);
            }
            Log(source.LogPath, "full-app update completed");
            return 0;
        }
        catch (Exception ex)
        {
            try { Log(source.LogPath, $"full-app update failed ({ex.GetType().Name}, 0x{ex.HResult:X8}): {ex.Message}"); } catch { }
            if (appRestarted)
            {
                preserveTransaction = true;
                return 0;
            }
            if (pendingPath is not null && File.Exists(pendingPath))
            {
                try
                {
                    RecoverInterruptedUpdate(root, source, throwOnFailure: true, forceRollback: true);
                    if ((healthCheck ?? RunHealthCheck)(Path.Combine(root, "VNText Studio.exe"), root))
                    {
                        Restart();
                        return 5;
                    }
                }
                catch (Exception rollbackError)
                {
                    preserveTransaction = true;
                    try { Log(source.LogPath, "full-app rollback failed: " + rollbackError.Message); } catch { }
                    return 6;
                }
            }
            if (appExited) Restart();
            return 5;
        }
        finally
        {
            if (!preserveTransaction && backupRoot is not null && stagingRoot is not null)
            {
                TryDeleteTree(backupRoot, source.BackupRoot, root);
                TryDeleteTree(stagingRoot, source.StagingRoot, root);
            }
        }
    }

    internal static bool RecoverInterruptedUpdate(string root)
    {
        root = Path.GetFullPath(root);
        var pending = Path.Combine(root, PendingName.Replace('/', Path.DirectorySeparatorChar));
        EnsureNoReparsePath(root, pending, "pending full-app update journal");
        if (!File.Exists(pending)) return false;
        var sourcePath = Path.Combine(root, ".vntext-update-source.json");
        if (!File.Exists(sourcePath))
            throw new InvalidDataException("An interrupted full-app update needs its source configuration for recovery.");
        var source = ReadSource(root, sourcePath);
        ValidatePaths(root, source);
        return RecoverInterruptedUpdate(root, source, throwOnFailure: true);
    }

    internal static bool StartInterruptedRecovery(string root)
    {
        root = Path.GetFullPath(root);
        var pending = SafeTemporaryTarget(root, PendingName);
        if (!File.Exists(pending)) return false;
        if (new FileInfo(pending).Length <= 0 || new FileInfo(pending).Length > MaxManifestBytes)
            throw new InvalidDataException("Pending full-app update journal size is invalid.");
        var sourcePath = Path.Combine(root, ".vntext-update-source.json");
        var source = ReadSource(root, sourcePath);
        ValidatePaths(root, source);
        using var journalJson = JsonDocument.Parse(File.ReadAllText(pending));
        EnsureUniqueProperties(journalJson.RootElement);
        var journal = JsonSerializer.Deserialize<UpdateJournal>(journalJson.RootElement.GetRawText(), JsonOptions)
            ?? throw new InvalidDataException("Pending full-app update journal is invalid.");
        if (!journal.BaseFiles.TryGetValue("VNText Studio.exe", out var baselineExe) ||
            baselineExe is null || !IsSha256(baselineExe.Sha256) ||
            !FileMatches(source.UpdaterPath, baselineExe))
            throw new InvalidDataException("Isolated recovery updater does not match the installed baseline executable.");
        var start = new ProcessStartInfo(source.UpdaterPath)
        {
            WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true,
        };
        var runtime = Path.Combine(root, "app", "dotnet");
        start.Environment["DOTNET_ROOT"] = runtime;
        start.Environment["DOTNET_ROOT_X64"] = runtime;
        start.ArgumentList.Add("--recover-full-app-update");
        start.ArgumentList.Add(sourcePath);
        start.ArgumentList.Add(root);
        start.ArgumentList.Add(Environment.ProcessId.ToString());
        _ = Process.Start(start) ?? throw new IOException("Could not start the isolated full-app recovery updater.");
        return true;
    }

    internal static int RunRecoveryUpdater(string sourcePath, string root, int appPid)
    {
        try
        {
            root = Path.GetFullPath(root);
            sourcePath = Path.GetFullPath(sourcePath);
            if (!SamePath(sourcePath, Path.Combine(root, ".vntext-update-source.json")) ||
                !SamePath(root, Path.GetDirectoryName(WorkerPaths.MainExePath())!)) return 3;
            var source = ReadSource(root, sourcePath);
            ValidatePaths(root, source);
            if (!WaitForExit(appPid, TimeSpan.FromSeconds(90))) return 4;
            RecoverInterruptedUpdate(root, source, throwOnFailure: true);
            if (!RunHealthCheck(Path.Combine(root, "VNText Studio.exe"), root))
                throw new InvalidOperationException("Recovered baseline application and worker health check failed.");
            Log(source.LogPath, "isolated full-app recovery health check passed");
            StartApp(root);
            return 0;
        }
        catch (Exception ex)
        {
            try
            {
                var source = ReadSource(root, sourcePath);
                Log(source.LogPath, "isolated full-app recovery failed: " + ex);
            }
            catch { }
            return 6;
        }
    }

    internal static int RunForTest(string sourcePath, string root, bool restartApp = false,
        Func<string, string, bool>? healthCheck = null, Action<string>? startApp = null) =>
        RunUpdater(sourcePath, root, int.MaxValue, null, fromGitHub: false,
            bindToRunningInstall: false, waitForProcesses: false, restartApp: restartApp,
            healthCheck: healthCheck, startAppOverride: startApp);

    internal static bool IsExpectedFullAppAssetPath(string actualPath, string owner, string repository,
        string tag, string assetName) => WpfUpdateService.IsExpectedGitHubAssetPath(actualPath, owner, repository, tag, assetName);

    private static FullAppUpdateSelection ValidatePackage(string root, UpdateSource source, string packagePath,
        string packageSha256, FullAppUpdateManifest manifest, string expectedVersion)
    {
        ValidatePaths(root, source);
        packagePath = Path.GetFullPath(packagePath);
        if (!IsUnderOrEqual(source.UpdatesRoot, packagePath) && !IsUnderOrEqual(source.WorkRoot, packagePath))
            throw new InvalidDataException("Full-app package must stay under the configured update directories.");
        RequireOutsideData(root, packagePath);
        EnsureNoReparsePathOutsideRoot(packagePath, "full-app package");
        if (new FileInfo(packagePath).Length <= 0 || new FileInfo(packagePath).Length > MaxPackageBytes ||
            !IsSha256(packageSha256) || !FixedEquals(HashFile(packagePath), packageSha256))
            throw new InvalidDataException("Full-app package size or SHA-256 is invalid.");
        if (manifest.Schema != 2 || manifest.Kind != "full-app" || manifest.Version != expectedVersion ||
            !TryParseVersion(manifest.Version, out _) || !IsSha1(manifest.SourceSha) || !IsSha256(manifest.SourceTreeSha256))
            throw new InvalidDataException("Full-app manifest schema, version or source provenance is invalid.");
        ValidateRecords(manifest.Files, "target");
        ValidateRecords(manifest.BaseFiles, "baseline");
        ValidateRecords(manifest.AddFiles, "add");
        ValidateRecords(manifest.ReplaceFiles, "replace");
        if (manifest.Files.Count > MaxFileCount || manifest.BaseFiles.Count > MaxFileCount)
            throw new InvalidDataException("Full-app inventory exceeds the file limit.");
        if (manifest.Files.Values.Concat(manifest.BaseFiles.Values).Any(item => item.Size < 0) ||
            manifest.Files.Values.Sum(item => item.Size) > MaxExpandedBytes ||
            manifest.BaseFiles.Values.Sum(item => item.Size) > MaxExpandedBytes)
            throw new InvalidDataException("Full-app inventory exceeds the expanded size limit.");
        ValidateOperationManifest(manifest);
        VerifyInstalledBaseline(root, manifest.BaseFiles);
        if (!WpfUpdateService.IsStrictlyNewerVersion(File.ReadAllText(SafeTarget(root, "app/VERSION.txt")).Trim(), manifest.Version))
            throw new InvalidDataException("Full-app update version is not newer than the installed version.");
        if (!FixedEquals(HashFile(packagePath), packageSha256))
            throw new InvalidDataException("Full-app package SHA-256 mismatch.");

        using var archive = ZipFile.OpenRead(packagePath);
        var manifestEntry = archive.GetEntry(PackageManifestName)
            ?? throw new InvalidDataException("Full-app package manifest is missing.");
        if (manifestEntry.Length <= 0 || manifestEntry.Length > MaxManifestBytes)
            throw new InvalidDataException("Full-app package manifest size is invalid.");
        EnsureNoDuplicateJsonProperties(manifestEntry);
        var expectedEntries = new HashSet<string>(manifest.AddFiles.Keys.Concat(manifest.ReplaceFiles.Keys).Append(PackageManifestName), StringComparer.Ordinal);
        var names = archive.Entries.Select(entry => entry.FullName).ToArray();
        if (names.Length != names.Distinct(StringComparer.OrdinalIgnoreCase).Count() || names.Length != expectedEntries.Count ||
            names.Any(name => !expectedEntries.Contains(name)))
            throw new InvalidDataException("Full-app package entries do not match the explicit operations.");
        var embedded = DeserializeManifest(manifestEntry);
        if (!ManifestsEqual(manifest, embedded))
            throw new InvalidDataException("Full-app feed manifest does not match its package.");
        foreach (var pair in manifest.AddFiles.Concat(manifest.ReplaceFiles))
        {
            var entry = archive.GetEntry(pair.Key) ?? throw new InvalidDataException("Full-app file is missing: " + pair.Key);
            if (entry.Length != pair.Value.Size || !FixedEquals(HashEntry(entry, pair.Value.Size), pair.Value.Sha256))
                throw new InvalidDataException("Full-app file hash or size mismatch: " + pair.Key);
        }
        ValidateCandidateMetadata(root, source, archive, manifest);
        return new FullAppUpdateSelection(packagePath, packageSha256, manifest);
    }

    private static void ValidateOperationManifest(FullAppUpdateManifest manifest)
    {
        var expectedAdd = manifest.Files.Keys.Except(manifest.BaseFiles.Keys, StringComparer.Ordinal).ToHashSet(StringComparer.Ordinal);
        var expectedDelete = manifest.BaseFiles.Keys.Except(manifest.Files.Keys, StringComparer.Ordinal).ToHashSet(StringComparer.Ordinal);
        var expectedReplace = manifest.Files.Keys.Intersect(manifest.BaseFiles.Keys, StringComparer.Ordinal)
            .Where(name => !RecordsEqual(manifest.Files[name], manifest.BaseFiles[name])).ToHashSet(StringComparer.Ordinal);
        var expectedUnchanged = manifest.Files.Keys.Intersect(manifest.BaseFiles.Keys, StringComparer.Ordinal)
            .Where(name => RecordsEqual(manifest.Files[name], manifest.BaseFiles[name])).ToHashSet(StringComparer.Ordinal);
        var protectedModelFiles = manifest.Files.Keys.Union(manifest.BaseFiles.Keys, StringComparer.Ordinal)
            .Where(IsProtectedModelPath).ToArray();
        if (!expectedAdd.SetEquals(manifest.AddFiles.Keys) || !expectedReplace.SetEquals(manifest.ReplaceFiles.Keys) ||
            !expectedDelete.SetEquals(manifest.DeleteFiles) || manifest.AddFiles.Any(pair => !RecordsEqual(pair.Value, manifest.Files[pair.Key])) ||
            manifest.ReplaceFiles.Any(pair => !RecordsEqual(pair.Value, manifest.Files[pair.Key])) ||
            manifest.DeleteFiles.Count != expectedDelete.Count || expectedUnchanged.Any(name => manifest.AddFiles.ContainsKey(name) || manifest.ReplaceFiles.ContainsKey(name)))
            throw new InvalidDataException("Full-app add/replace/delete inventory is inconsistent.");
        foreach (var name in protectedModelFiles)
            if (!manifest.Files.TryGetValue(name, out var target) || !manifest.BaseFiles.TryGetValue(name, out var baseline) ||
                !RecordsEqual(target, baseline))
                throw new InvalidDataException("Full-app update cannot add, replace, or delete model files: " + name);
        foreach (var required in new[] { "VNText Studio.exe", "app/RELEASE.json", "app/VERSION.txt" })
            if (!manifest.Files.ContainsKey(required)) throw new InvalidDataException("Full-app target is missing: " + required);
    }

    private static void ValidateRecords(Dictionary<string, FileRecord> records, string label)
    {
        if (records is null) throw new InvalidDataException("Full-app " + label + " inventory is missing.");
        var folded = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var pair in records)
        {
            ValidateManagedName(pair.Key);
            if (pair.Key == "app") throw new InvalidDataException("Full-app inventory entries must be files, not the app directory.");
            if (!folded.Add(pair.Key)) throw new InvalidDataException("Case-insensitive duplicate in full-app " + label + " inventory: " + pair.Key);
            if (pair.Value is null || !IsSha256(pair.Value.Sha256) || pair.Value.Size < 0)
                throw new InvalidDataException("Invalid full-app " + label + " record: " + pair.Key);
            if ((pair.Key is "app/RELEASE.json" or "app/VERSION.txt") && pair.Value.Size > MaxManifestBytes)
                throw new InvalidDataException("Full-app metadata file exceeds the size limit: " + pair.Key);
        }
    }

    private static void VerifyInstalledBaseline(string root, Dictionary<string, FileRecord> expected)
    {
        var actualNames = EnumerateManagedFiles(root).ToHashSet(StringComparer.Ordinal);
        if (!actualNames.SetEquals(expected.Keys)) throw new FullAppBaselineMismatchException("Installed application file inventory does not match the package baseline.");
        foreach (var pair in expected)
        {
            var path = SafeTarget(root, pair.Key);
            var info = new FileInfo(path);
            if (info.Length != pair.Value.Size || !FixedEquals(HashFile(path), pair.Value.Sha256))
                throw new FullAppBaselineMismatchException("Installed baseline file differs: " + pair.Key);
        }
        ValidateInstalledMetadata(root, expected);
    }

    private static void ValidateInstalledMetadata(string root, FullAppUpdateManifest manifest) =>
        ValidateInstalledMetadata(root, manifest.Files);

    private static void ValidateInstalledMetadata(string root, Dictionary<string, FileRecord> files)
    {
        var versionPath = SafeTarget(root, "app/VERSION.txt");
        var releasePath = SafeTarget(root, "app/RELEASE.json");
        var exePath = SafeTarget(root, "VNText Studio.exe");
        var version = File.ReadAllText(versionPath).Trim();
        using var release = JsonDocument.Parse(File.ReadAllText(releasePath));
        var releaseVersion = GetString(release.RootElement, "version");
        var exeHash = HashFile(exePath);
        var productVersion = FileVersionInfo.GetVersionInfo(exePath).ProductVersion?.Split('+', 2)[0].Trim();
        if (version != releaseVersion || version != productVersion || !files.TryGetValue("VNText Studio.exe", out var record) ||
            !FixedEquals(exeHash, record.Sha256) || !FixedEquals(exeHash, GetString(release.RootElement, "sha256")))
            throw new InvalidDataException("Installed executable, VERSION.txt and RELEASE.json disagree.");
    }

    private static void ValidateCandidateMetadata(string root, UpdateSource source, ZipArchive archive, FullAppUpdateManifest manifest)
    {
        var validationRoot = Path.Combine(source.WorkRoot, "validate-full-app-" + Guid.NewGuid().ToString("N"));
        try
        {
            RequireUnderRoot(root, validationRoot, "full-app validation path");
            RequireOutsideData(root, validationRoot);
            EnsureNoReparsePath(root, validationRoot, "full-app validation path");
            Directory.CreateDirectory(validationRoot);
            var exePath = Path.Combine(validationRoot, "VNText Studio.exe");
            using (var input = archive.GetEntry("VNText Studio.exe")!.Open())
            using (var output = new FileStream(exePath, FileMode.CreateNew, FileAccess.Write, FileShare.None)) input.CopyTo(output);
            if (FileVersionInfo.GetVersionInfo(exePath).ProductVersion?.Split('+', 2)[0].Trim() != manifest.Version)
                throw new InvalidDataException("Full-app executable version does not match its manifest.");
            var versionBytes = ReadEntry(archive, "app/VERSION.txt");
            if (Encoding.UTF8.GetString(versionBytes).Trim() != manifest.Version)
                throw new InvalidDataException("Full-app VERSION.txt does not match its manifest.");
            using var release = JsonDocument.Parse(ReadEntry(archive, "app/RELEASE.json"));
            if (GetString(release.RootElement, "version") != manifest.Version ||
                !FixedEquals(GetString(release.RootElement, "sha256"), manifest.Files["VNText Studio.exe"].Sha256) ||
                GetString(release.RootElement, "source_sha") != manifest.SourceSha ||
                GetString(release.RootElement, "source_tree_sha256") != manifest.SourceTreeSha256)
                throw new InvalidDataException("Full-app RELEASE.json source, version or executable hash is invalid.");
        }
        finally { TryDeleteTree(validationRoot, source.WorkRoot, root); }
    }

    private static bool RecoverInterruptedUpdate(string root, UpdateSource source, bool throwOnFailure,
        bool forceRollback = false)
    {
        var pending = SafeTemporaryTarget(root, PendingName);
        RequireOutsideData(root, pending);
        EnsureNoReparsePath(root, pending, "pending full-app update journal");
        if (!File.Exists(pending)) return false;
        if (new FileInfo(pending).Length <= 0 || new FileInfo(pending).Length > MaxManifestBytes)
            throw new InvalidDataException("Pending full-app update journal size is invalid.");
        try
        {
            using var journalJson = JsonDocument.Parse(File.ReadAllText(pending));
            EnsureUniqueProperties(journalJson.RootElement);
            var journal = JsonSerializer.Deserialize<UpdateJournal>(journalJson.RootElement.GetRawText(), JsonOptions)
                ?? throw new InvalidDataException("Pending full-app update journal is invalid.");
            if (journal.Schema != 1 || !Regex.IsMatch(journal.TransactionId, "^txn-[0-9a-f]{32}$"))
                throw new InvalidDataException("Pending full-app update identity is invalid.");
            var backupRoot = Path.Combine(source.BackupRoot, journal.TransactionId);
            var stagingRoot = Path.Combine(source.StagingRoot, journal.TransactionId);
            RequireUnderRoot(root, backupRoot, "full-app recovery backup");
            RequireUnderRoot(root, stagingRoot, "full-app recovery staging");
            RequireOutsideData(root, backupRoot);
            RequireOutsideData(root, stagingRoot);
            EnsureNoReparsePath(root, backupRoot, "full-app recovery backup");
            EnsureNoReparsePath(root, stagingRoot, "full-app recovery staging");
            ValidateRecords(journal.BaseFiles, "recovery baseline");
            ValidateRecords(journal.Files, "recovery target");
            ValidateOperationManifest(new FullAppUpdateManifest
            {
                Schema = 2, Kind = "full-app", Version = "0.0.1", SourceSha = new string('0', 40),
                SourceTreeSha256 = new string('0', 64), Files = journal.Files, BaseFiles = journal.BaseFiles,
                AddFiles = journal.AddFiles, ReplaceFiles = journal.ReplaceFiles, DeleteFiles = journal.DeleteFiles,
            });
            var ownership = Path.Combine(root, OwnershipName.Replace('/', Path.DirectorySeparatorChar));
            EnsureNoReparsePath(root, ownership, "full-app ownership manifest");
            if (journal.CommitReady && !forceRollback)
            {
                try
                {
                    VerifyInventory(root, journal.Files);
                    ValidateInstalledMetadata(root, journal.Files);
                    ValidateOwnershipFile(ownership, journal.Files.Keys);
                    File.Delete(pending);
                    TryDeleteTree(backupRoot, source.BackupRoot, root);
                    TryDeleteTree(stagingRoot, source.StagingRoot, root);
                    Log(source.LogPath, "committed full-app update journal finalized");
                    return true;
                }
                catch
                {
                    // An incomplete committed target must restore from the verified baseline backups below.
                }
            }
            foreach (var relative in journal.ReplaceFiles.Keys.Concat(journal.DeleteFiles))
            {
                var backup = SafeTarget(backupRoot, relative);
                var baseRecord = journal.BaseFiles[relative];
                if (!File.Exists(backup) || new FileInfo(backup).Length != baseRecord.Size || !FixedEquals(HashFile(backup), baseRecord.Sha256))
                    throw new InvalidDataException("Recovery backup is missing or invalid: " + relative);
            }
            foreach (var relative in journal.ReplaceFiles.Keys.Concat(journal.DeleteFiles))
            {
                var backup = SafeTarget(backupRoot, relative);
                var target = SafeTarget(root, relative);
                Directory.CreateDirectory(Path.GetDirectoryName(target)!);
                if (File.Exists(target))
                {
                    var isBaseline = FileMatches(target, journal.BaseFiles[relative]);
                    var isTarget = journal.ReplaceFiles.TryGetValue(relative, out var targetRecord) && FileMatches(target, targetRecord);
                    if (!isBaseline && !isTarget)
                        throw new InvalidDataException("Recovery target changed after interruption: " + relative);
                    if (isBaseline) continue;
                    var restore = SafeTemporaryTarget(stagingRoot, "restore/" + relative);
                    Directory.CreateDirectory(Path.GetDirectoryName(restore)!);
                    File.Copy(backup, restore, overwrite: true);
                    ReplaceExistingFile(restore, target);
                }
                else File.Copy(backup, target, overwrite: false);
            }
            foreach (var relative in journal.AddFiles.Keys)
            {
                var added = SafeTarget(root, relative);
                if (Directory.Exists(added)) throw new InvalidDataException("Recovery add target became a directory: " + relative);
                if (File.Exists(added))
                {
                    if (!FileMatches(added, journal.Files[relative]))
                        throw new InvalidDataException("Recovery add target changed after interruption: " + relative);
                    File.Delete(added);
                }
            }
            var ownershipBackup = SafeTemporaryTarget(backupRoot, "ownership.previous.json");
            if (journal.OwnershipExisted)
            {
                EnsureNoReparsePath(backupRoot, ownershipBackup, "previous ownership manifest backup");
                if (!File.Exists(ownershipBackup) || new FileInfo(ownershipBackup).Length != journal.OwnershipPreviousSize ||
                    !IsSha256(journal.OwnershipPreviousSha256) || !FixedEquals(HashFile(ownershipBackup), journal.OwnershipPreviousSha256))
                    throw new InvalidDataException("Previous ownership manifest backup is missing or invalid.");
                WriteBytesAtomic(ownership, File.ReadAllBytes(ownershipBackup));
            }
            else
            {
                if (Directory.Exists(ownership)) throw new InvalidDataException("Ownership manifest path became a directory.");
                if (File.Exists(ownership)) File.Delete(ownership);
            }
            RemoveEmptyAppDirectories(root);
            VerifyInventory(root, journal.BaseFiles);
            ValidateInstalledMetadata(root, journal.BaseFiles);
            File.Delete(pending);
            TryDeleteTree(backupRoot, source.BackupRoot, root);
            TryDeleteTree(stagingRoot, source.StagingRoot, root);
            Log(source.LogPath, "interrupted full-app update rolled back and verified");
            return true;
        }
        catch
        {
            if (throwOnFailure) throw;
            return false;
        }
    }

    private static IEnumerable<string> EnumerateManagedFiles(string root)
    {
        var exe = SafeTarget(root, "VNText Studio.exe");
        if (!File.Exists(exe)) throw new FullAppBaselineMismatchException("Installed executable is missing.");
        yield return "VNText Studio.exe";
        var appRoot = SafeAppRoot(root);
        if (!Directory.Exists(appRoot)) throw new FullAppBaselineMismatchException("Installed app directory is missing.");
        var pending = new Stack<string>();
        pending.Push(appRoot);
        while (pending.Count > 0)
        {
            var directory = pending.Pop();
            if ((File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Application directory is a reparse point: " + directory);
            foreach (var child in Directory.EnumerateFileSystemEntries(directory))
            {
                var attributes = File.GetAttributes(child);
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidDataException("Application inventory contains a reparse point: " + child);
                if ((attributes & FileAttributes.Directory) != 0) pending.Push(child);
                else
                {
                    var relative = "app/" + Path.GetRelativePath(appRoot, child).Replace(Path.DirectorySeparatorChar, '/');
                    ValidateManagedName(relative);
                    yield return relative;
                }
            }
        }
    }

    private static void VerifyInventory(string root, Dictionary<string, FileRecord> expected)
    {
        var actual = EnumerateManagedFiles(root).ToHashSet(StringComparer.Ordinal);
        if (!actual.SetEquals(expected.Keys)) throw new InvalidDataException("Installed full-app inventory does not match the target manifest.");
        foreach (var pair in expected)
        {
            var path = SafeTarget(root, pair.Key);
            if (new FileInfo(path).Length != pair.Value.Size || !FixedEquals(HashFile(path), pair.Value.Sha256))
                throw new InvalidDataException("Installed full-app file failed target verification: " + pair.Key);
        }
    }

    private static void RemoveEmptyAppDirectories(string root)
    {
        var app = SafeAppRoot(root);
        var directories = new List<string>();
        var pending = new Stack<string>();
        pending.Push(app);
        while (pending.Count > 0)
        {
            var directory = pending.Pop();
            if ((File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Application directory is a reparse point: " + directory);
            directories.Add(directory);
            foreach (var child in Directory.EnumerateDirectories(directory))
            {
                if ((File.GetAttributes(child) & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidDataException("Application directory is a reparse point: " + child);
                pending.Push(child);
            }
        }
        foreach (var directory in directories.OrderByDescending(path => path.Length))
            if (!Directory.EnumerateFileSystemEntries(directory).Any()) Directory.Delete(directory, false);
    }

    private static string SafeAppRoot(string root)
    {
        var app = Path.Combine(Path.GetFullPath(root), "app");
        EnsureNoReparsePath(root, app, "application root");
        return app;
    }

    private static bool IsProtectedModelPath(string name) =>
        name.StartsWith("app/worker/models/", StringComparison.OrdinalIgnoreCase);

    private static bool FileMatches(string path, FileRecord record) =>
        File.Exists(path) && new FileInfo(path).Length == record.Size && FixedEquals(HashFile(path), record.Sha256);

    private static void ValidateOwnershipFile(string path, IEnumerable<string> expectedFiles)
    {
        EnsureNoReparsePathOutsideRoot(path, "full-app ownership manifest");
        var ownershipInfo = new FileInfo(path);
        if (!ownershipInfo.Exists || ownershipInfo.Length <= 0 || ownershipInfo.Length > MaxManifestBytes)
            throw new InvalidDataException("Full-app ownership manifest size is invalid.");
        using var document = JsonDocument.Parse(File.ReadAllText(path));
        if (document.RootElement.ValueKind != JsonValueKind.Array)
            throw new InvalidDataException("Full-app ownership manifest must be an array.");
        var actual = document.RootElement.EnumerateArray()
            .Select(item => item.ValueKind == JsonValueKind.String ? item.GetString() ?? "" : "\0")
            .ToArray();
        foreach (var name in actual) ValidateManagedName(name);
        if (actual.Distinct(StringComparer.Ordinal).Count() != actual.Length ||
            !actual.ToHashSet(StringComparer.Ordinal).SetEquals(expectedFiles))
            throw new InvalidDataException("Full-app ownership manifest does not match the managed file inventory.");
    }

    private static void ValidateManagedName(string name)
    {
        if (name != "VNText Studio.exe" && !name.StartsWith("app/", StringComparison.Ordinal))
            throw new InvalidDataException("Full-app update path is outside the managed application tree: " + name);
        if (Path.IsPathRooted(name) || name.Contains('\\') || name.Contains(':') ||
            name.Split('/').Any(part => part is "" or "." or ".."))
            throw new InvalidDataException("Unsafe full-app update path: " + name);
        if (name.Equals(OwnershipName, StringComparison.OrdinalIgnoreCase) || name.StartsWith("app/data/", StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Full-app update cannot target protected state: " + name);
    }

    private static UpdateSource ReadSource(string root) => ReadSource(root, Path.Combine(root, ".vntext-update-source.json"));

    private static UpdateSource ReadSource(string root, string sourcePath)
    {
        root = Path.GetFullPath(root);
        sourcePath = Path.GetFullPath(sourcePath);
        if (!SamePath(sourcePath, Path.Combine(root, ".vntext-update-source.json")))
            throw new InvalidDataException("Update source path is outside the install root.");
        EnsureNoReparsePath(root, sourcePath, "Update source configuration");
        return JsonSerializer.Deserialize<UpdateSource>(File.ReadAllText(sourcePath), JsonOptions)
            ?? throw new InvalidDataException("Update source configuration is invalid.");
    }

    private static void ValidatePaths(string root, UpdateSource source)
    {
        var updates = Path.GetFullPath(source.UpdatesRoot);
        if (IsUnderOrEqual(root, updates) || IsUnderOrEqual(updates, root)) throw new InvalidDataException("Updates folder must remain outside the install root.");
        foreach (var path in new[] { source.WorkRoot, source.BackupRoot, source.StagingRoot, source.UpdaterPath, source.LogPath })
        {
            RequireUnderRoot(root, path, "update working path");
            RequireOutsideData(root, path);
            EnsureNoReparsePath(root, path, "update working path");
        }
        EnsureNoReparsePathOutsideRoot(updates, "Updates folder");
    }

    private static UpdateSource DeserializeSource(string path) =>
        JsonSerializer.Deserialize<UpdateSource>(File.ReadAllText(path), JsonOptions) ?? throw new InvalidDataException("Update source configuration is invalid.");

    private static FullAppUpdateManifest DeserializeManifest(JsonElement element) =>
        JsonSerializer.Deserialize<FullAppUpdateManifest>(element.GetRawText(), JsonOptions)
        ?? throw new InvalidDataException("Full-app manifest is invalid.");

    private static FullAppUpdateManifest DeserializeManifest(ZipArchiveEntry entry)
    {
        return JsonSerializer.Deserialize<FullAppUpdateManifest>(ReadZipEntryBounded(entry, MaxManifestBytes), JsonOptions)
            ?? throw new InvalidDataException("Full-app manifest is invalid.");
    }

    private static void EnsureNoDuplicateJsonProperties(ZipArchiveEntry entry)
    {
        using var document = JsonDocument.Parse(ReadZipEntryBounded(entry, MaxManifestBytes));
        EnsureUniqueProperties(document.RootElement);
    }

    private static void EnsureUniqueProperties(JsonElement element)
    {
        if (element.ValueKind == JsonValueKind.Object)
        {
            var names = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var property in element.EnumerateObject())
            {
                if (!names.Add(property.Name)) throw new InvalidDataException("Full-app manifest contains duplicate properties.");
                EnsureUniqueProperties(property.Value);
            }
        }
        else if (element.ValueKind == JsonValueKind.Array)
            foreach (var item in element.EnumerateArray()) EnsureUniqueProperties(item);
    }

    private static bool ManifestsEqual(FullAppUpdateManifest left, FullAppUpdateManifest right) =>
        left.Schema == right.Schema && left.Kind == right.Kind && left.Version == right.Version && left.SourceSha == right.SourceSha &&
        left.SourceTreeSha256 == right.SourceTreeSha256 && left.Notes == right.Notes && RecordsEqual(left.Files, right.Files) &&
        RecordsEqual(left.BaseFiles, right.BaseFiles) && RecordsEqual(left.AddFiles, right.AddFiles) &&
        RecordsEqual(left.ReplaceFiles, right.ReplaceFiles) && left.DeleteFiles.SequenceEqual(right.DeleteFiles, StringComparer.Ordinal);

    private static bool RecordsEqual(Dictionary<string, FileRecord> left, Dictionary<string, FileRecord> right) =>
        left.Count == right.Count && left.All(pair => right.TryGetValue(pair.Key, out var value) && pair.Value.Size == value.Size &&
            string.Equals(pair.Value.Sha256, value.Sha256, StringComparison.OrdinalIgnoreCase));

    private static bool RecordsEqual(FileRecord left, FileRecord right) => left.Size == right.Size &&
        string.Equals(left.Sha256, right.Sha256, StringComparison.OrdinalIgnoreCase);

    private static string SafeTarget(string root, string relative)
    {
        ValidateManagedName(relative);
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var target = Path.GetFullPath(Path.Combine(fullRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
        if (!target.StartsWith(fullRoot + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Full-app update path escaped the install root.");
        EnsureNoReparsePath(root, target, "full-app update target");
        return target;
    }

    private static string SafeTemporaryTarget(string root, string relative)
    {
        if (Path.IsPathRooted(relative) || relative.Contains(':') || relative.Contains('\\') ||
            relative.Split('/').Any(part => part is "" or "." or ".."))
            throw new InvalidDataException("Unsafe updater temporary path: " + relative);
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var target = Path.GetFullPath(Path.Combine(fullRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
        if (!target.StartsWith(fullRoot + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Updater temporary path escaped its root.");
        EnsureNoReparsePath(fullRoot, target, "updater temporary path");
        return target;
    }

    private static void RequireUnderRoot(string root, string path, string label)
    {
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar) + Path.DirectorySeparatorChar;
        if (!Path.GetFullPath(path).StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException(label + " must stay under install root.");
    }

    private static void RequireOutsideData(string root, string path)
    {
        var data = Path.GetFullPath(Path.Combine(root, "data")).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var fullPath = Path.GetFullPath(path);
        if (SamePath(fullPath, data.TrimEnd(Path.DirectorySeparatorChar)) || fullPath.StartsWith(data, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Updater state and staging must stay outside data/.");
    }

    private static void EnsureNoReparsePath(string root, string path, string label)
    {
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var fullPath = Path.GetFullPath(path);
        RequireUnderRoot(fullRoot, fullPath, label);
        if ((Directory.Exists(fullRoot) || File.Exists(fullRoot)) && (File.GetAttributes(fullRoot) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException(label + " root is a reparse point.");
        var cursor = fullRoot;
        foreach (var part in Path.GetRelativePath(fullRoot, fullPath).Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar))
        {
            if (part.Length == 0 || part == ".") continue;
            cursor = Path.Combine(cursor, part);
            if ((Directory.Exists(cursor) || File.Exists(cursor)) && (File.GetAttributes(cursor) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException(label + " traverses a reparse point.");
        }
    }

    private static void EnsureNoReparsePathOutsideRoot(string path, string label)
    {
        var fullPath = Path.GetFullPath(path);
        var drive = Path.GetPathRoot(fullPath) ?? throw new InvalidDataException(label + " has no filesystem root.");
        var cursor = drive;
        foreach (var part in fullPath[drive.Length..].Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar, StringSplitOptions.RemoveEmptyEntries))
        {
            cursor = Path.Combine(cursor, part);
            if ((Directory.Exists(cursor) || File.Exists(cursor)) && (File.GetAttributes(cursor) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException(label + " traverses a reparse point.");
        }
    }

    private static bool IsUnderOrEqual(string root, string path)
    {
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var fullPath = Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        return SamePath(fullRoot, fullPath) || fullPath.StartsWith(fullRoot + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
    }

    private static void WriteJsonAtomic<T>(string path, T value)
    {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            var bytes = JsonSerializer.SerializeToUtf8Bytes(value);
            WriteBytesAtomic(temporary, bytes, moveToPath: false);
            if (File.Exists(path)) ReplaceExistingFile(temporary, path);
            else File.Move(temporary, path);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    private static void WriteBytesAtomic(string path, byte[] bytes, bool moveToPath = true)
    {
        var target = moveToPath ? path : path;
        var temporary = moveToPath ? path + "." + Guid.NewGuid().ToString("N") + ".tmp" : path;
        Directory.CreateDirectory(Path.GetDirectoryName(target)!);
        using (var stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
        {
            stream.Write(bytes);
            stream.Flush(true);
        }
        if (!moveToPath) return;
        try
        {
            if (File.Exists(target)) ReplaceExistingFile(temporary, target);
            else File.Move(temporary, target);
        }
        finally { if (File.Exists(temporary)) File.Delete(temporary); }
    }

    private static byte[] ReadEntry(ZipArchive archive, string name)
    {
        return ReadZipEntryBounded(archive.GetEntry(name)!, MaxManifestBytes);
    }

    private static byte[] ReadZipEntryBounded(ZipArchiveEntry entry, long maximumBytes)
    {
        if (entry.Length < 0 || entry.Length > maximumBytes)
            throw new InvalidDataException("Full-app ZIP metadata entry exceeds the size limit: " + entry.FullName);
        using var input = entry.Open();
        using var output = new MemoryStream((int)entry.Length);
        var buffer = new byte[64 * 1024];
        int read;
        while ((read = input.Read(buffer, 0, buffer.Length)) > 0)
        {
            if (output.Length + read > maximumBytes)
                throw new InvalidDataException("Full-app ZIP metadata entry expands beyond the size limit: " + entry.FullName);
            output.Write(buffer, 0, read);
        }
        return output.ToArray();
    }

    private static void CopyEntryBounded(ZipArchiveEntry entry, string destination, long expectedSize)
    {
        if (expectedSize < 0 || entry.Length != expectedSize)
            throw new InvalidDataException("Full-app ZIP entry size does not match the manifest: " + entry.FullName);
        using var input = entry.Open();
        using var output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write, FileShare.None);
        var buffer = new byte[1024 * 1024];
        long total = 0;
        int read;
        while ((read = input.Read(buffer, 0, buffer.Length)) > 0)
        {
            if (total > expectedSize - read)
                throw new InvalidDataException("Full-app ZIP entry expands beyond its declared size: " + entry.FullName);
            total += read;
            output.Write(buffer, 0, read);
        }
        if (total != expectedSize)
            throw new InvalidDataException("Full-app ZIP entry expanded size does not match the manifest: " + entry.FullName);
        output.Flush(true);
    }

    private static string HashEntry(ZipArchiveEntry entry, long expectedSize)
    {
        if (expectedSize < 0 || entry.Length != expectedSize)
            throw new InvalidDataException("Full-app ZIP entry size does not match the manifest: " + entry.FullName);
        using var input = entry.Open();
        using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        var buffer = new byte[1024 * 1024];
        long total = 0;
        int read;
        while ((read = input.Read(buffer, 0, buffer.Length)) > 0)
        {
            if (total > expectedSize - read)
                throw new InvalidDataException("Full-app ZIP entry expands beyond its declared size: " + entry.FullName);
            total += read;
            hash.AppendData(buffer, 0, read);
        }
        if (total != expectedSize)
            throw new InvalidDataException("Full-app ZIP entry expanded size does not match the manifest: " + entry.FullName);
        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }

    private static string HashFile(string path)
    {
        using var input = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(input)).ToLowerInvariant();
    }

    private static void ReplaceExistingFile(string source, string destination)
    {
        var delays = new[] { 50, 100, 200, 400, 800, 1_200, 1_600, 2_000 };
        for (var attempt = 0; ; attempt++)
        {
            try
            {
                File.Replace(source, destination, null, ignoreMetadataErrors: true);
                return;
            }
            catch (IOException ex) when (OperatingSystem.IsWindows() &&
                ((ex.HResult & 0xFFFF) == 32 || (ex.HResult & 0xFFFF) == 33) && attempt < delays.Length)
            {
                Thread.Sleep(delays[attempt]);
            }
        }
    }

    private static bool IsSha256(string? value) => value is { Length: 64 } && value.All(char.IsAsciiHexDigit);
    private static bool IsSha1(string? value) => value is { Length: 40 } && value.All(char.IsAsciiHexDigit);
    private static bool FixedEquals(string left, string right) => left.Length == right.Length &&
        CryptographicOperations.FixedTimeEquals(Convert.FromHexString(left), Convert.FromHexString(right));
    private static bool TryParseVersion(string value, out Version version)
    {
        version = new Version(0, 0, 0);
        if (!System.Text.RegularExpressions.Regex.IsMatch(value ?? "", "^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$")) return false;
        return Version.TryParse(value, out version!);
    }
    private static int GetInt(JsonElement element, string name) => element.TryGetProperty(name, out var property) && property.TryGetInt32(out var value) ? value : -1;
    private static string GetString(JsonElement element, string name) => element.TryGetProperty(name, out var property) && property.ValueKind == JsonValueKind.String ? property.GetString() ?? "" : "";
    private static bool SamePath(string left, string right) => string.Equals(Path.GetFullPath(left).TrimEnd(Path.DirectorySeparatorChar), Path.GetFullPath(right).TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase);
    private static bool WaitForExit(int pid, TimeSpan timeout) { try { using var p = Process.GetProcessById(pid); return p.WaitForExit((int)timeout.TotalMilliseconds); } catch (ArgumentException) { return true; } }
    private static void StartApp(string root)
    {
        using var process = Process.Start(new ProcessStartInfo(Path.Combine(root, "VNText Studio.exe"))
        { WorkingDirectory = root, UseShellExecute = true });
        if (process is null) throw new InvalidOperationException("Updated application could not be restarted.");
    }
    private static bool RunHealthCheck(string executable, string root)
    {
        try
        {
            using var app = Process.Start(new ProcessStartInfo(executable, "--update-health-check") { WorkingDirectory = root, UseShellExecute = false, CreateNoWindow = true });
            if (app is null || !app.WaitForExit(45_000) || app.ExitCode != 0) return false;
            var worker = WorkerPaths.PythonExecutable();
            var start = new ProcessStartInfo(worker)
            {
                WorkingDirectory = WorkerPaths.WorkerRoot(), UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            };
            start.ArgumentList.Add("-m"); start.ArgumentList.Add("vntext_worker.worker_main");
            start.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
            start.Environment["TEMP"] = start.Environment["TMP"] = Path.Combine(root, ".update", "health-temp");
            Directory.CreateDirectory(start.Environment["TEMP"]!);
            using var process = Process.Start(start);
            if (process is null) return false;
            _ = process.StandardError.ReadToEndAsync();
            var readyTask = process.StandardOutput.ReadLineAsync();
            if (!readyTask.Wait(TimeSpan.FromSeconds(20))) { TryStopWorker(process); return false; }
            var ready = readyTask.GetAwaiter().GetResult();
            process.StandardInput.Close();
            if (!process.WaitForExit(15_000)) { TryStopWorker(process); return false; }
            return ready is not null && JsonDocument.Parse(ready).RootElement.TryGetProperty("type", out var type) &&
                type.GetString() == "ready" && process.ExitCode == 0;
        }
        catch { return false; }
    }
    private static void TryStopWorker(Process process) { try { if (!process.HasExited) process.Kill(entireProcessTree: true); } catch { } }
    private static void Log(string path, string message) => File.AppendAllText(path, $"{DateTimeOffset.UtcNow:O} {message}{Environment.NewLine}");
    private static void TryDeleteTree(string path, string parent, string root)
    {
        try
        {
            RequireUnderRoot(root, path, "update cleanup path");
            RequireUnderRoot(parent, path, "update cleanup parent");
            RequireOutsideData(root, path);
            EnsureNoReparsePath(root, path, "update cleanup path");
            if (Directory.Exists(path))
            {
                EnsureNoReparseTree(path);
                Directory.Delete(path, true);
            }
        }
        catch { }
    }

    private static void EnsureNoReparseTree(string root)
    {
        if (!Directory.Exists(root)) return;
        var pending = new Stack<string>();
        pending.Push(root);
        while (pending.Count > 0)
        {
            var directory = pending.Pop();
            if ((File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Updater cleanup tree contains a reparse point: " + directory);
            foreach (var child in Directory.EnumerateFileSystemEntries(directory))
            {
                var attributes = File.GetAttributes(child);
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidDataException("Updater cleanup tree contains a reparse point: " + child);
                if ((attributes & FileAttributes.Directory) != 0) pending.Push(child);
            }
        }
    }
    private sealed class UpdateSource
    {
        [JsonPropertyName("updates_root")] public string UpdatesRoot { get; set; } = "";
        [JsonPropertyName("work_root")] public string WorkRoot { get; set; } = "";
        [JsonPropertyName("backup_root")] public string BackupRoot { get; set; } = "";
        [JsonPropertyName("staging_root")] public string StagingRoot { get; set; } = "";
        [JsonPropertyName("updater_path")] public string UpdaterPath { get; set; } = "";
        [JsonPropertyName("log_path")] public string LogPath { get; set; } = "";
        [JsonPropertyName("fault_inject_interrupt_after_first_replace")] public bool FaultInjectInterruptAfterFirstReplace { get; set; }
    }

    internal sealed class FullAppUpdateManifest
    {
        [JsonPropertyName("schema")] public int Schema { get; set; }
        [JsonPropertyName("kind")] public string Kind { get; set; } = "";
        [JsonPropertyName("version")] public string Version { get; set; } = "";
        [JsonPropertyName("source_sha")] public string SourceSha { get; set; } = "";
        [JsonPropertyName("source_tree_sha256")] public string SourceTreeSha256 { get; set; } = "";
        [JsonPropertyName("notes")] public string Notes { get; set; } = "";
        [JsonPropertyName("files")] public Dictionary<string, FileRecord> Files { get; set; } = new(StringComparer.Ordinal);
        [JsonPropertyName("base_files")] public Dictionary<string, FileRecord> BaseFiles { get; set; } = new(StringComparer.Ordinal);
        [JsonPropertyName("add_files")] public Dictionary<string, FileRecord> AddFiles { get; set; } = new(StringComparer.Ordinal);
        [JsonPropertyName("replace_files")] public Dictionary<string, FileRecord> ReplaceFiles { get; set; } = new(StringComparer.Ordinal);
        [JsonPropertyName("delete_files")] public List<string> DeleteFiles { get; set; } = [];
    }

    internal sealed class FileRecord
    {
        [JsonPropertyName("sha256")] public string Sha256 { get; set; } = "";
        [JsonPropertyName("size")] public long Size { get; set; }
    }

    private sealed class UpdateJournal
    {
        [JsonPropertyName("schema")] public int Schema { get; set; }
        [JsonPropertyName("transaction_id")] public string TransactionId { get; set; } = "";
        [JsonPropertyName("files")] public Dictionary<string, FileRecord> Files { get; set; } = new(StringComparer.Ordinal);
        [JsonPropertyName("base_files")] public Dictionary<string, FileRecord> BaseFiles { get; set; } = new(StringComparer.Ordinal);
        [JsonPropertyName("add_files")] public Dictionary<string, FileRecord> AddFiles { get; set; } = new(StringComparer.Ordinal);
        [JsonPropertyName("replace_files")] public Dictionary<string, FileRecord> ReplaceFiles { get; set; } = new(StringComparer.Ordinal);
        [JsonPropertyName("delete_files")] public List<string> DeleteFiles { get; set; } = [];
        [JsonPropertyName("ownership_existed")] public bool OwnershipExisted { get; set; }
        [JsonPropertyName("ownership_previous_size")] public long OwnershipPreviousSize { get; set; }
        [JsonPropertyName("ownership_previous_sha256")] public string OwnershipPreviousSha256 { get; set; } = "";
        [JsonPropertyName("commit_ready")] public bool CommitReady { get; set; }
    }

}
