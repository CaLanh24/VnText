using System.Diagnostics;
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Net;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;

namespace VNText.Studio.App.Services;

public enum GitHubUpdateState
{
    Unconfigured,
    Current,
    UpdateAvailable,
    SetupRequired,
    InvalidMetadata,
    InvalidPackage,
    Offline,
    Timeout,
    RateLimited,
}

internal sealed record GitHubUpdateCheckResult(
    GitHubUpdateState State,
    string Version = "",
    string PackagePath = "",
    string PackageSha256 = "",
    string ReleasesUrl = "",
    string Message = "",
    bool FullAppPackage = false);

internal sealed class GitHubUpdatePackageLease : IDisposable
{
    private readonly string _installRoot;
    private int _state;

    internal GitHubUpdatePackageLease(string installRoot, GitHubUpdateCheckResult update)
    {
        if (update.State != GitHubUpdateState.UpdateAvailable || string.IsNullOrWhiteSpace(update.PackagePath))
            throw new InvalidDataException("A GitHub package lease requires a verified update candidate.");
        _installRoot = Path.GetFullPath(installRoot);
        Update = update;
    }

    internal GitHubUpdateCheckResult Update { get; }

    internal void TransferToUpdater()
    {
        if (Interlocked.CompareExchange(ref _state, 1, 0) != 0)
            throw new InvalidOperationException("The GitHub update package is no longer owned by the app.");
    }

    public void Dispose()
    {
        if (Interlocked.CompareExchange(ref _state, 2, 0) == 0)
            WpfUpdateService.DeleteGitHubUpdateCandidate(_installRoot, Update);
    }
}

public static class WpfUpdateService
{
    private const string SourceName = ".vntext-update-source.json";
    private const string FeedManifestName = "wpf-update-current.json";
    private const string PackageManifestName = "wpf-update-manifest.json";
    internal const long MaxGitHubUpdatePackageBytes = 536_870_912;
    private const long MaxGitHubReleaseMetadataBytes = 10_485_760;
    private static readonly TimeSpan GitHubRequestTimeout = TimeSpan.FromSeconds(20);
    private static readonly string[] AllowedFiles = ["VNText Studio.exe", "app/RELEASE.json", "app/VERSION.txt"];
    private static readonly HashSet<string> TrustedReleaseAssetHosts = new(StringComparer.OrdinalIgnoreCase)
    {
        "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"
    };

    internal static async Task<GitHubUpdateCheckResult> CheckGitHubUpdateAsync(
        string installRoot, HttpMessageHandler? httpHandler = null, CancellationToken cancellationToken = default)
    {
        string? downloadedPackage = null;
        UpdateSource? source = null;
        string root;
        try
        {
            root = Path.GetFullPath(installRoot);
            var sourcePath = Path.Combine(root, SourceName);
            EnsureNoReparsePath(root, sourcePath, "Update source configuration");
            if (!File.Exists(sourcePath))
                return new(GitHubUpdateState.Unconfigured, Message: "GitHub stable updates are not configured.");
            source = ReadSource(sourcePath);
            ValidateUpdatePaths(root, source);
            if (string.IsNullOrWhiteSpace(source.GitHubOwner) && string.IsNullOrWhiteSpace(source.GitHubRepository))
                return new(GitHubUpdateState.Unconfigured, Message: "GitHub stable updates are not configured.");
            if (!IsValidGitHubIdentity(source.GitHubOwner, source.GitHubRepository))
                return new(GitHubUpdateState.InvalidMetadata, Message: "GitHub update identity is invalid.");

            var releasesUrl = GetReleasesUrl(source);
            if (!TryReadInstalledVersion(root, out var installedVersion))
                return new(GitHubUpdateState.SetupRequired, ReleasesUrl: releasesUrl,
                    Message: "The installed WPF baseline does not match; install the current Setup release.");

            using var client = httpHandler is null
                ? new HttpClient(new HttpClientHandler { AllowAutoRedirect = false }, disposeHandler: true)
                : new HttpClient(httpHandler, disposeHandler: false);
            client.Timeout = GitHubRequestTimeout;
            using var request = new HttpRequestMessage(HttpMethod.Get,
                $"https://api.github.com/repos/{source.GitHubOwner}/{source.GitHubRepository}/releases?per_page=100");
            request.Headers.TryAddWithoutValidation("Accept", "application/vnd.github+json");
            request.Headers.TryAddWithoutValidation("User-Agent", "VNText-Studio");
            request.Headers.TryAddWithoutValidation("X-GitHub-Api-Version", "2022-11-28");

            using var response = await client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .ConfigureAwait(false);
            if (IsRateLimited(response))
                return new(GitHubUpdateState.RateLimited, ReleasesUrl: releasesUrl,
                    Message: "GitHub rate limit reached; try checking again later.");
            if (response.StatusCode == HttpStatusCode.NotFound)
                return new(GitHubUpdateState.InvalidMetadata, ReleasesUrl: releasesUrl,
                    Message: "The configured GitHub repository was not found.");
            if (!response.IsSuccessStatusCode)
                return new(GitHubUpdateState.Offline, ReleasesUrl: releasesUrl,
                    Message: $"GitHub releases are unavailable (HTTP {(int)response.StatusCode}).");
            string releaseJson;
            try
            {
                releaseJson = await ReadBoundedGitHubMetadataAsync(response.Content, cancellationToken).ConfigureAwait(false);
            }
            catch (InvalidDataException)
            {
                return new(GitHubUpdateState.InvalidMetadata, ReleasesUrl: releasesUrl,
                    Message: "GitHub release metadata is too large.");
            }

            List<GitHubReleaseInfo> releases;
            try { releases = ParseStableReleases(releaseJson); }
            catch (Exception ex) when (ex is JsonException or InvalidDataException or InvalidOperationException or FormatException)
            {
                return new(GitHubUpdateState.InvalidMetadata, ReleasesUrl: releasesUrl,
                    Message: "GitHub stable release metadata is invalid: " + ex.Message);
            }

            var newer = releases
                .Where(release => IsStrictlyNewerVersion(installedVersion, release.VersionText))
                .OrderByDescending(release => release.Version)
                .ToArray();
            foreach (var release in newer)
            {
                var updateAssets = release.Assets.Where(asset =>
                    (asset.Name.StartsWith("wpf-update-" + release.VersionText, StringComparison.Ordinal) ||
                     asset.Name.StartsWith("full-app-update-" + release.VersionText, StringComparison.Ordinal)) &&
                    asset.Name.EndsWith(".zip", StringComparison.Ordinal)).ToArray();
                if (updateAssets.Length > 1)
                    return new(GitHubUpdateState.InvalidMetadata, Version: release.VersionText, ReleasesUrl: releasesUrl,
                        Message: "The stable release contains ambiguous update assets.");

                if (updateAssets.Length == 0)
                    return new(GitHubUpdateState.SetupRequired, Version: release.VersionText, ReleasesUrl: releasesUrl,
                        Message: "This stable release has no applicable in-app update package; install Setup from the official Releases page.");

                var asset = updateAssets[0];
                var fullAppPackage = asset.Name.StartsWith("full-app-update-", StringComparison.Ordinal);
                if (!TryValidateUpdateAsset(source, release, asset, fullAppPackage, out var packageDigest, out var assetUri, out var metadataError))
                    return new(GitHubUpdateState.InvalidMetadata, Version: release.VersionText, ReleasesUrl: releasesUrl,
                        Message: metadataError);
                if (asset.Size <= 0 || asset.Size > MaxGitHubUpdatePackageBytes)
                    return new(GitHubUpdateState.InvalidPackage, Version: release.VersionText, ReleasesUrl: releasesUrl,
                        Message: "The GitHub WPF package has an invalid or oversized declared size.");

                    downloadedPackage = Path.Combine(source.WorkRoot,
                    $"github-update-{release.VersionText}-{Guid.NewGuid():N}.zip");
                try
                {
                    EnsureNoReparsePath(root, downloadedPackage, "GitHub update package");
                    Directory.CreateDirectory(source.WorkRoot);
                    using var assetResponse = await SendReleaseAssetAsync(client, assetUri, cancellationToken).ConfigureAwait(false);
                    if (!assetResponse.IsSuccessStatusCode)
                    {
                        if (IsRateLimited(assetResponse))
                            return new(GitHubUpdateState.RateLimited, Version: release.VersionText, ReleasesUrl: releasesUrl,
                                Message: "GitHub rate limit reached while downloading the WPF package.");
                        return new(GitHubUpdateState.Offline, Version: release.VersionText, ReleasesUrl: releasesUrl,
                            Message: $"GitHub WPF package is unavailable (HTTP {(int)assetResponse.StatusCode}).");
                    }

                    var downloadedDigest = await DownloadAndHashAssetAsync(
                        assetResponse.Content, downloadedPackage, asset.Size, cancellationToken).ConfigureAwait(false);
                    if (!FixedEquals(downloadedDigest, packageDigest))
                        throw new InvalidDataException("GitHub asset SHA-256 digest mismatch.");

                    if (fullAppPackage)
                        _ = FullAppUpdateService.ReadGitHubPackage(root, Path.Combine(root, SourceName), downloadedPackage,
                            packageDigest, release.VersionText);
                    else
                        _ = ReadAndValidateGitHubPackage(root, source, downloadedPackage, packageDigest, release.VersionText);
                    return new(GitHubUpdateState.UpdateAvailable, release.VersionText, downloadedPackage,
                        packageDigest, releasesUrl, $"Stable {(fullAppPackage ? "full-app" : "WPF")} update available: v{release.VersionText}.", fullAppPackage);
                }
                catch (FullAppBaselineMismatchException ex)
                {
                    TryDeleteGitHubPackage(downloadedPackage, source, root);
                    downloadedPackage = null;
                    return new(GitHubUpdateState.SetupRequired, Version: release.VersionText, ReleasesUrl: releasesUrl,
                        Message: "This full-app package does not apply to the installed baseline; install Setup. " + ex.Message);
                }
                catch (BaselineMismatchException ex)
                {
                    TryDeleteGitHubPackage(downloadedPackage, source, root);
                    downloadedPackage = null;
                    return new(GitHubUpdateState.SetupRequired, Version: release.VersionText, ReleasesUrl: releasesUrl,
                        Message: "This WPF package does not apply to the installed baseline; install Setup. " + ex.Message);
                }
                catch (TaskCanceledException)
                {
                    TryDeleteGitHubPackage(downloadedPackage, source, root);
                    downloadedPackage = null;
                    return new(GitHubUpdateState.Timeout, Version: release.VersionText, ReleasesUrl: releasesUrl,
                        Message: "GitHub update check timed out.");
                }
                catch (HttpRequestException ex)
                {
                    TryDeleteGitHubPackage(downloadedPackage, source, root);
                    downloadedPackage = null;
                    return new(GitHubUpdateState.Offline, Version: release.VersionText, ReleasesUrl: releasesUrl,
                        Message: "GitHub WPF package is unavailable: " + ex.Message);
                }
                catch (Exception ex) when (ex is InvalidDataException or IOException or JsonException or InvalidOperationException or UnauthorizedAccessException)
                {
                    TryDeleteGitHubPackage(downloadedPackage, source, root);
                    downloadedPackage = null;
                    return new(GitHubUpdateState.InvalidPackage, Version: release.VersionText, ReleasesUrl: releasesUrl,
                        Message: "GitHub WPF package is invalid: " + ex.Message);
                }
            }

            if (newer.Length > 0)
            {
                var latest = newer[0];
                return new(GitHubUpdateState.SetupRequired, Version: latest.VersionText, ReleasesUrl: releasesUrl,
                    Message: "A newer stable release requires Setup; open the official Releases page.");
            }
            return new(GitHubUpdateState.Current, ReleasesUrl: releasesUrl,
                Message: "VNText Studio is up to date with stable GitHub releases.");
        }
        catch (TaskCanceledException)
        {
            if (downloadedPackage is not null && source is not null)
                TryDeleteGitHubPackage(downloadedPackage, source, installRoot);
            return new(GitHubUpdateState.Timeout, Message: "GitHub update check timed out.");
        }
        catch (HttpRequestException ex)
        {
            if (downloadedPackage is not null && source is not null)
                TryDeleteGitHubPackage(downloadedPackage, source, installRoot);
            return new(GitHubUpdateState.Offline, Message: "GitHub releases are unavailable: " + ex.Message);
        }
        catch (Exception ex) when (ex is InvalidDataException or IOException or JsonException or InvalidOperationException or UnauthorizedAccessException or ArgumentException)
        {
            if (downloadedPackage is not null && source is not null)
                TryDeleteGitHubPackage(downloadedPackage, source, installRoot);
            return new(GitHubUpdateState.InvalidMetadata, Message: "GitHub update configuration is invalid: " + ex.Message);
        }
    }

    internal static void StartGitHubUpdate(int? workerPid, GitHubUpdatePackageLease packageLease)
    {
        var update = packageLease.Update;
        if (update.State != GitHubUpdateState.UpdateAvailable || string.IsNullOrWhiteSpace(update.PackagePath) ||
            !IsSha256(update.PackageSha256) || !TryParseStableVersion(update.Version, out _))
            throw new InvalidDataException("There is no verified GitHub WPF update to apply.");
        var root = InstallRoot();
        StartUpdaterProcess(root, Path.Combine(root, SourceName), workerPid,
            update.PackagePath, update.PackageSha256, update.Version, packageLease.TransferToUpdater,
            fullAppPackage: update.FullAppPackage);
    }

    internal static bool TryGetAvailableUpdateVersion(string installRoot, out string version) =>
        TryGetAvailableUpdateVersion(installRoot, out version, out _);

    internal static bool TryGetAvailableUpdateVersion(string installRoot, out string version, out string status)
    {
        version = "";
        status = "";
        try
        {
            var root = Path.GetFullPath(installRoot);
            if (FullAppUpdateService.HasLocalFeed(root))
                return FullAppUpdateService.TryGetAvailableVersion(root, out version, out status);
            var marker = Path.Combine(root, SourceName);
            EnsureNoReparsePath(root, marker, "Update source configuration");
            var source = ReadSource(marker);
            var selection = ReadAndValidatePackage(root, source);
            version = selection.Manifest.Version;
            return true;
        }
        catch (NoNewerUpdateException ex)
        {
            status = ex.Message;
            return false;
        }
        catch (Exception ex)
        {
            version = "";
            status = "Không thể kiểm tra nguồn cập nhật: " + ex.Message;
            return false;
        }
    }

    internal static bool IsStrictlyNewerVersion(string current, string candidate)
    {
        if (!TryParseAppVersion(current, out var currentCore, out var currentSuffix) ||
            !TryParseAppVersion(candidate, out var candidateCore, out var candidateSuffix))
            return false;
        var comparison = candidateCore.CompareTo(currentCore);
        if (comparison != 0)
            return comparison > 0;
        return currentSuffix.Length > 0 && candidateSuffix.Length == 0;
    }

    public static void StartUpdate(int? workerPid)
    {
        var root = InstallRoot();
        var sourcePath = Path.Combine(root, SourceName);
        if (!TryGetAvailableUpdateVersion(root, out _))
            throw new InvalidDataException("Không có bản cập nhật hợp lệ, mới hơn cho bản cài này.");
        StartUpdaterProcess(root, sourcePath, workerPid, null, "", "", fullAppPackage: FullAppUpdateService.HasLocalFeed(root));
    }

    private static void StartUpdaterProcess(string root, string sourcePath, int? workerPid,
        string? packagePath, string packageSha256, string version, Action? packageHandedOff = null,
        bool fullAppPackage = false)
    {
        EnsureNoReparsePath(root, sourcePath, "Update source configuration");
        var source = ReadSource(sourcePath);
        ValidateUpdatePaths(root, source);
        if (packagePath is not null)
        {
            packagePath = Path.GetFullPath(packagePath);
            RequireUnderRoot(source.WorkRoot, packagePath, "GitHub update package");
            RequireOutsideData(root, packagePath);
            EnsureNoReparsePath(root, packagePath, "GitHub update package");
            if (!IsSha256(packageSha256) || !FixedEquals(HashFile(packagePath), packageSha256) ||
                !TryParseStableVersion(version, out _))
                throw new InvalidDataException("GitHub update package hash or version changed before apply.");
        }
        Directory.CreateDirectory(Path.GetDirectoryName(source.UpdaterPath)!);
        File.Copy(WorkerPaths.MainExePath(), source.UpdaterPath, overwrite: true);
        var start = new ProcessStartInfo(source.UpdaterPath)
        {
            WorkingDirectory = root,
            UseShellExecute = false,
        };
        var runtime = Path.Combine(root, "app", "dotnet");
        start.Environment["DOTNET_ROOT"] = runtime;
        start.Environment["DOTNET_ROOT_X64"] = runtime;
        start.ArgumentList.Add(packagePath is null
            ? (fullAppPackage ? "--apply-full-app-update" : "--apply-wpf-update")
            : (fullAppPackage ? "--apply-github-full-app-update" : "--apply-github-wpf-update"));
        start.ArgumentList.Add(sourcePath);
        start.ArgumentList.Add(root);
        start.ArgumentList.Add(Environment.ProcessId.ToString());
        start.ArgumentList.Add(workerPid?.ToString() ?? "");
        if (packagePath is not null)
        {
            start.ArgumentList.Add(packagePath);
            start.ArgumentList.Add(packageSha256);
            start.ArgumentList.Add(version);
        }
        _ = Process.Start(start) ?? throw new InvalidOperationException("Could not start the isolated updater process.");
        packageHandedOff?.Invoke();
        System.Windows.Application.Current.Shutdown();
    }

    public static int RunUpdater(string[] args)
    {
        if (args.Length == 4 && string.Equals(args[0], "--recover-full-app-update", StringComparison.Ordinal) &&
            int.TryParse(args[3], out var recoveryAppPid))
            return FullAppUpdateService.RunRecoveryUpdater(args[1], args[2], recoveryAppPid);
        if (args.Length < 5 || !int.TryParse(args[3], out var appPid))
            return 2;
        int? workerPid = int.TryParse(args[4], out var parsedWorkerPid) ? parsedWorkerPid : null;
        if (string.Equals(args[0], "--apply-github-full-app-update", StringComparison.Ordinal))
        {
            if (args.Length != 8 || !IsSha256(args[6]) || !TryParseStableVersion(args[7], out _)) return 2;
            return FullAppUpdateService.RunUpdater(args[1], args[2], appPid, workerPid, fromGitHub: true,
                packagePath: args[5], packageSha256: args[6], version: args[7]);
        }
        if (string.Equals(args[0], "--apply-full-app-update", StringComparison.Ordinal))
        {
            if (args.Length != 5) return 2;
            return FullAppUpdateService.RunUpdater(args[1], args[2], appPid, workerPid, fromGitHub: false);
        }
        if (string.Equals(args[0], "--apply-github-wpf-update", StringComparison.Ordinal))
        {
            if (args.Length != 8 || !IsSha256(args[6]) || !TryParseStableVersion(args[7], out _))
                return 2;
            return RunUpdaterCore(args[1], args[2], appPid, workerPid, bindToRunningInstall: true,
                waitForProcesses: true, restartApp: true, healthCheck: RunHealthCheck,
                githubPackagePath: args[5], githubPackageSha256: args[6], githubVersion: args[7]);
        }
        if (!string.Equals(args[0], "--apply-wpf-update", StringComparison.Ordinal) || args.Length != 5)
            return 2;
        return RunUpdaterCore(args[1], args[2], appPid, workerPid, bindToRunningInstall: true,
            waitForProcesses: true, restartApp: true, healthCheck: RunHealthCheck);
    }

    internal static int RunUpdaterForTest(string sourcePath, string root, bool restartApp = false,
        Func<string, string, bool>? healthCheck = null)
    {
        return RunUpdaterCore(sourcePath, root, int.MaxValue, null, bindToRunningInstall: false,
            waitForProcesses: false, restartApp: restartApp, healthCheck: healthCheck ?? ((_, _) => true));
    }

    internal static int RunGitHubUpdaterForTest(string sourcePath, string root, string packagePath,
        string packageSha256, string version, bool restartApp = false,
        Func<string, string, bool>? healthCheck = null, Action<string>? startApp = null)
    {
        return RunUpdaterCore(sourcePath, root, int.MaxValue, null, bindToRunningInstall: false,
            waitForProcesses: false, restartApp: restartApp, healthCheck: healthCheck ?? ((_, _) => true),
            githubPackagePath: packagePath, githubPackageSha256: packageSha256, githubVersion: version,
            startAppOverride: startApp);
    }

    private static int RunUpdaterCore(string sourcePath, string root, int appPid, int? workerPid,
        bool bindToRunningInstall, bool waitForProcesses, bool restartApp,
        Func<string, string, bool> healthCheck, string? githubPackagePath = null,
        string githubPackageSha256 = "", string githubVersion = "", Action<string>? startAppOverride = null)
    {
        sourcePath = Path.GetFullPath(sourcePath);
        root = Path.GetFullPath(root);
        if (bindToRunningInstall && !SamePath(root, InstallRoot()))
            return 3;
        if (!SamePath(sourcePath, Path.Combine(root, SourceName)))
            return 3;

        UpdateSource source;
        try
        {
            EnsureNoReparsePath(root, sourcePath, "Update source configuration");
            source = ReadSource(sourcePath);
            ValidateUpdatePaths(root, source);
        }
        catch { return 5; }

        var targets = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var previousHashes = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var replaced = new List<string>();
        var appExited = false;
        var transactionId = "txn-" + Guid.NewGuid().ToString("N");
        var backupParent = source.BackupRoot;
        var stagingParent = source.StagingRoot;
        source.BackupRoot = Path.Combine(backupParent, transactionId);
        source.StagingRoot = Path.Combine(stagingParent, transactionId);
        var preserveTransaction = false;
        void RestartApp()
        {
            if (!restartApp) return;
            if (startAppOverride is null) StartApp(root);
            else startAppOverride(root);
        }
        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(source.LogPath)!);
            Log(source.LogPath, "waiting for app and worker to exit normally");
            if (waitForProcesses && !WaitForExit(appPid, TimeSpan.FromSeconds(90)))
            {
                Log(source.LogPath, "app shutdown wait timed out; update not applied");
                return 4;
            }
            appExited = true;
            if (waitForProcesses && workerPid.HasValue && !WaitForExit(workerPid.Value, TimeSpan.FromSeconds(30)))
            {
                Log(source.LogPath, "worker shutdown wait timed out; update not applied");
                RestartApp();
                return 4;
            }

            var update = githubPackagePath is null
                ? ReadAndValidatePackage(root, source)
                : ReadAndValidateGitHubPackage(root, source, githubPackagePath, githubPackageSha256, githubVersion);
            var manifest = update.Manifest;
            var staged = ExtractPackage(source, update);
            ValidateMetadata(root, manifest, staged);
            Directory.CreateDirectory(source.BackupRoot);
            foreach (var relative in AllowedFiles)
            {
                var target = SafeTarget(root, relative);
                var expected = manifest.BaseFiles[relative].Sha256;
                var actual = HashFile(target);
                if (!FixedEquals(actual, expected))
                    throw new InvalidDataException($"Installed baseline mismatch: {relative}");
                previousHashes[relative] = actual;
                var backup = SafeTarget(source.BackupRoot, relative);
                Directory.CreateDirectory(Path.GetDirectoryName(backup)!);
                File.Copy(target, backup, overwrite: false);
                if (!FixedEquals(HashFile(backup), actual))
                    throw new IOException($"Backup verification failed: {relative}");
                targets[relative] = target;
            }

            foreach (var relative in AllowedFiles)
            {
                var target = targets[relative];
                var stagedFile = staged[relative];
                File.Replace(stagedFile, target, null, ignoreMetadataErrors: true);
                replaced.Add(relative);
                Log(source.LogPath, "replaced " + relative);
                if (source.FaultInjectAfterFirstReplace && replaced.Count == 1)
                    throw new IOException("Injected post-replacement failure.");
            }

            if (!healthCheck(targets["VNText Studio.exe"], root))
                throw new InvalidOperationException("Updated application health check failed.");
            Log(source.LogPath, "health check passed");
            RestartApp();
            return 0;
        }
        catch (Exception ex)
        {
            Log(source.LogPath, "update failed: " + ex.Message);
            if (replaced.Count > 0)
            {
                try
                {
                    foreach (var relative in replaced.AsEnumerable().Reverse())
                    {
                        var backup = SafeTarget(source.BackupRoot, relative);
                        var target = targets[relative];
                        var restore = Path.Combine(source.StagingRoot, "restore", relative.Replace('/', Path.DirectorySeparatorChar));
                        Directory.CreateDirectory(Path.GetDirectoryName(restore)!);
                        File.Copy(backup, restore, overwrite: true);
                        File.Replace(restore, target, null, ignoreMetadataErrors: true);
                    }
                    foreach (var relative in AllowedFiles)
                        if (!FixedEquals(HashFile(SafeTarget(root, relative)), previousHashes[relative]))
                            throw new IOException("Rollback hash mismatch: " + relative);
                    if (!healthCheck(targets["VNText Studio.exe"], root))
                        throw new IOException("Restored baseline health check failed.");
                    Log(source.LogPath, "rollback verified; baseline hashes restored");
                    RestartApp();
                    return 5;
                }
                catch (Exception rollbackError)
                {
                    Log(source.LogPath, "rollback failed: " + rollbackError.Message);
                    preserveTransaction = true;
                    return 6;
                }
            }

            if (appExited)
                RestartApp();
            return 5;
        }
        finally
        {
            if (githubPackagePath is not null)
                TryDeleteGitHubPackage(githubPackagePath, source, root);
            if (!preserveTransaction)
            {
                TryDeleteTransaction(source.BackupRoot, backupParent, root);
                TryDeleteTransaction(source.StagingRoot, stagingParent, root);
            }
        }
    }

    public static int RunHealthCheck()
    {
        try
        {
            var root = InstallRoot();
            var versionPath = Path.Combine(root, "app", "VERSION.txt");
            var releasePath = Path.Combine(root, "app", "RELEASE.json");
            var exe = Path.Combine(root, "VNText Studio.exe");
            using var release = JsonDocument.Parse(File.ReadAllText(releasePath));
            var version = File.ReadAllText(versionPath).Trim();
            var productVersion = FileVersionInfo.GetVersionInfo(exe).ProductVersion?.Split('+', 2)[0].Trim();
            return version.Length > 0
                && release.RootElement.GetProperty("version").GetString() == version
                && productVersion == version
                && FixedEquals(HashFile(exe), release.RootElement.GetProperty("sha256").GetString() ?? "")
                ? 0 : 1;
        }
        catch { return 1; }
    }

    private static List<GitHubReleaseInfo> ParseStableReleases(string json)
    {
        using var document = JsonDocument.Parse(json);
        if (document.RootElement.ValueKind != JsonValueKind.Array)
            throw new InvalidDataException("Release response must be an array.");
        var releases = new List<GitHubReleaseInfo>();
        foreach (var element in document.RootElement.EnumerateArray())
        {
            if (element.ValueKind != JsonValueKind.Object ||
                !element.TryGetProperty("draft", out var draft) || draft.ValueKind is not (JsonValueKind.True or JsonValueKind.False) ||
                !element.TryGetProperty("prerelease", out var prerelease) || prerelease.ValueKind is not (JsonValueKind.True or JsonValueKind.False))
                throw new InvalidDataException("Release stable/draft metadata is missing.");
            if (draft.GetBoolean() || prerelease.GetBoolean())
                continue;
            if (!element.TryGetProperty("tag_name", out var tagElement) || tagElement.ValueKind != JsonValueKind.String)
                throw new InvalidDataException("Stable release tag is missing.");
            var tag = tagElement.GetString() ?? "";
            if (!TryParseStableTag(tag, out var versionText, out var version))
                throw new InvalidDataException("Stable release tag is not semantic version: " + tag);
            if (!element.TryGetProperty("assets", out var assetsElement) || assetsElement.ValueKind != JsonValueKind.Array)
                throw new InvalidDataException("Stable release assets are missing.");

            var assets = new List<GitHubAssetInfo>();
            foreach (var asset in assetsElement.EnumerateArray())
            {
                if (asset.ValueKind != JsonValueKind.Object ||
                    !asset.TryGetProperty("name", out var nameElement) || nameElement.ValueKind != JsonValueKind.String)
                    throw new InvalidDataException("Release asset name is missing.");
                var name = nameElement.GetString() ?? "";
                var digest = asset.TryGetProperty("digest", out var digestElement) && digestElement.ValueKind == JsonValueKind.String
                    ? digestElement.GetString() ?? "" : "";
                var size = asset.TryGetProperty("size", out var sizeElement) && sizeElement.TryGetInt64(out var parsedSize)
                    ? parsedSize : -1;
                var downloadUrl = asset.TryGetProperty("browser_download_url", out var urlElement) && urlElement.ValueKind == JsonValueKind.String
                    ? urlElement.GetString() ?? "" : "";
                assets.Add(new GitHubAssetInfo(name, digest, size, downloadUrl));
            }
            releases.Add(new GitHubReleaseInfo(tag, versionText, version, assets));
        }

        if (releases.GroupBy(release => release.VersionText, StringComparer.Ordinal).Any(group => group.Count() > 1))
            throw new InvalidDataException("Stable release versions are duplicated.");
        return releases;
    }

    internal static bool TryParseStableTag(string tag, out string versionText, out Version version)
    {
        versionText = tag.StartsWith('v') ? tag[1..] : tag;
        version = new Version(0, 0, 0);
        if (versionText.Split('.', StringSplitOptions.None).Length == 2)
            versionText += ".0";
        return TryParseStableVersion(versionText, out version);
    }

    private static bool TryParseStableVersion(string value, out Version version)
    {
        version = new Version(0, 0, 0);
        if (!Regex.IsMatch(value ?? "", "^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$"))
            return false;
        if (!Version.TryParse(value, out var parsed) || parsed is null)
            return false;
        version = parsed;
        return true;
    }

    private static bool TryReadInstalledVersion(string root, out string version)
    {
        version = "";
        try
        {
            var versionPath = SafeTarget(root, "app/VERSION.txt");
            var releasePath = SafeTarget(root, "app/RELEASE.json");
            var exePath = SafeTarget(root, "VNText Studio.exe");
            version = File.ReadAllText(versionPath).Trim();
            if (!TryParseAppVersion(version, out _, out _)) return false;
            using var release = JsonDocument.Parse(File.ReadAllText(releasePath));
            var productVersion = FileVersionInfo.GetVersionInfo(exePath).ProductVersion?.Split('+', 2)[0].Trim();
            return release.RootElement.GetProperty("version").GetString() == version && productVersion == version &&
                FixedEquals(HashFile(exePath), release.RootElement.GetProperty("sha256").GetString() ?? "");
        }
        catch
        {
            version = "";
            return false;
        }
    }

    private static bool IsValidGitHubIdentity(string owner, string repository) =>
        Regex.IsMatch(owner ?? "", "^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$") &&
        Regex.IsMatch(repository ?? "", "^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?$") &&
        repository is not "." and not "..";

    private static string GetReleasesUrl(UpdateSource source) =>
        $"https://github.com/{source.GitHubOwner}/{source.GitHubRepository}/releases/latest";

    private static bool TryValidateUpdateAsset(UpdateSource source, GitHubReleaseInfo release, GitHubAssetInfo asset,
        bool fullAppPackage, out string digest, out Uri downloadUri, out string error)
    {
        digest = "";
        downloadUri = new Uri("https://github.com/");
        var packageLabel = fullAppPackage ? "full-app" : "WPF";
        var packagePrefix = fullAppPackage ? "full-app-update-" : "wpf-update-";
        error = $"GitHub {packageLabel} asset metadata is invalid.";
        if (!asset.Digest.StartsWith("sha256:", StringComparison.OrdinalIgnoreCase) ||
            !IsSha256(asset.Digest[7..]))
        {
            error = $"GitHub {packageLabel} asset is missing its SHA-256 digest.";
            return false;
        }
        digest = asset.Digest[7..].ToLowerInvariant();
        var expectedName = $"{packagePrefix}{release.VersionText}-{digest[..16]}.zip";
        if (!string.Equals(asset.Name, expectedName, StringComparison.Ordinal))
        {
            error = $"GitHub {packageLabel} asset name does not match its version and SHA-256 digest.";
            return false;
        }
        if (!Uri.TryCreate(asset.DownloadUrl, UriKind.Absolute, out var uri) ||
            !IsTrustedHttpsUri(uri) || !string.Equals(uri.Host, "github.com", StringComparison.OrdinalIgnoreCase))
        {
            error = $"GitHub {packageLabel} asset URL must use the trusted GitHub HTTPS host.";
            return false;
        }
        if (!IsExpectedGitHubAssetPath(uri.AbsolutePath, source.GitHubOwner, source.GitHubRepository, release.Tag, expectedName) || uri.Query.Length != 0)
        {
            error = $"GitHub {packageLabel} asset URL does not match the configured repository, release tag and expected asset.";
            return false;
        }
        downloadUri = uri;
        return true;
    }

    internal static bool IsExpectedGitHubAssetPath(
        string actualPath, string owner, string repository, string tag, string assetName)
    {
        var identityPrefix = $"/{owner}/{repository}/";
        var expectedRouteAndAsset = $"releases/download/{tag}/{assetName}";
        return actualPath.StartsWith(identityPrefix, StringComparison.OrdinalIgnoreCase) &&
               string.Equals(actualPath[identityPrefix.Length..], expectedRouteAndAsset, StringComparison.Ordinal);
    }

    private static bool IsTrustedHttpsUri(Uri uri) =>
        uri.Scheme == Uri.UriSchemeHttps && uri.IsDefaultPort && string.IsNullOrEmpty(uri.UserInfo) &&
        string.IsNullOrEmpty(uri.Fragment);

    private static async Task<HttpResponseMessage> SendReleaseAssetAsync(HttpClient client, Uri uri,
        CancellationToken cancellationToken)
    {
        for (var redirectCount = 0; redirectCount <= 5; redirectCount++)
        {
            if (!IsTrustedHttpsUri(uri) || !TrustedReleaseAssetHosts.Contains(uri.Host))
                throw new InvalidDataException("GitHub asset redirect used an untrusted HTTPS host.");
            using var request = new HttpRequestMessage(HttpMethod.Get, uri);
            var response = await client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken)
                .ConfigureAwait(false);
            if ((int)response.StatusCode is < 300 or > 399)
                return response;
            var location = response.Headers.Location;
            if (location is null || redirectCount == 5)
            {
                response.Dispose();
                throw new InvalidDataException("GitHub asset redirect is missing or excessive.");
            }
            var next = location.IsAbsoluteUri ? location : new Uri(uri, location);
            response.Dispose();
            if (!IsTrustedHttpsUri(next) || !TrustedReleaseAssetHosts.Contains(next.Host))
                throw new InvalidDataException("GitHub asset redirect used an untrusted HTTPS host.");
            uri = next;
        }
        throw new InvalidDataException("GitHub asset redirect limit exceeded.");
    }

    private static async Task<string> DownloadAndHashAssetAsync(HttpContent content, string path, long expectedSize,
        CancellationToken cancellationToken)
    {
        if (content.Headers.ContentLength.HasValue && content.Headers.ContentLength.Value != expectedSize)
            throw new InvalidDataException("GitHub WPF asset content length does not match release metadata.");
        using var input = await content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        using var output = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.None,
            64 * 1024, FileOptions.Asynchronous | FileOptions.SequentialScan);
        using var hash = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);
        var buffer = new byte[64 * 1024];
        long total = 0;
        while (true)
        {
            var read = await input.ReadAsync(buffer.AsMemory(), cancellationToken).ConfigureAwait(false);
            if (read == 0) break;
            total += read;
            if (total > MaxGitHubUpdatePackageBytes || total > expectedSize)
                throw new InvalidDataException("GitHub WPF package exceeds its declared size limit.");
            hash.AppendData(buffer, 0, read);
            await output.WriteAsync(buffer.AsMemory(0, read), cancellationToken).ConfigureAwait(false);
        }
        await output.FlushAsync(cancellationToken).ConfigureAwait(false);
        if (total != expectedSize)
            throw new InvalidDataException("GitHub WPF package size does not match release metadata.");
        return Convert.ToHexString(hash.GetHashAndReset()).ToLowerInvariant();
    }

    private static async Task<string> ReadBoundedGitHubMetadataAsync(HttpContent content,
        CancellationToken cancellationToken)
    {
        if (content.Headers.ContentLength is > MaxGitHubReleaseMetadataBytes)
            throw new InvalidDataException("GitHub release metadata is too large.");

        using var input = await content.ReadAsStreamAsync(cancellationToken).ConfigureAwait(false);
        using var output = new MemoryStream();
        var buffer = new byte[64 * 1024];
        long total = 0;
        while (true)
        {
            var read = await input.ReadAsync(buffer.AsMemory(), cancellationToken).ConfigureAwait(false);
            if (read == 0) break;
            total += read;
            if (total > MaxGitHubReleaseMetadataBytes)
                throw new InvalidDataException("GitHub release metadata is too large.");
            output.Write(buffer, 0, read);
        }

        return new UTF8Encoding(encoderShouldEmitUTF8Identifier: false, throwOnInvalidBytes: true)
            .GetString(output.GetBuffer(), 0, (int)output.Length);
    }

    private static bool IsRateLimited(HttpResponseMessage response) =>
        response.StatusCode == HttpStatusCode.TooManyRequests ||
        (response.StatusCode == HttpStatusCode.Forbidden &&
            response.Headers.TryGetValues("X-RateLimit-Remaining", out var values) && values.Contains("0"));

    private static void TryDeleteGitHubPackage(string path, UpdateSource source, string root)
    {
        try
        {
            var fullPath = Path.GetFullPath(path);
            RequireUnderRoot(source.WorkRoot, fullPath, "GitHub package cleanup path");
            RequireOutsideData(root, fullPath);
            EnsureNoReparsePath(root, fullPath, "GitHub package cleanup path");
            if (File.Exists(fullPath)) File.Delete(fullPath);
        }
        catch { }
    }

    internal static void DeleteGitHubUpdateCandidate(string installRoot, GitHubUpdateCheckResult candidate)
    {
        if (candidate.State != GitHubUpdateState.UpdateAvailable || string.IsNullOrWhiteSpace(candidate.PackagePath))
            return;
        try
        {
            var root = Path.GetFullPath(installRoot);
            var sourcePath = Path.Combine(root, SourceName);
            EnsureNoReparsePath(root, sourcePath, "Update source configuration");
            if (!File.Exists(sourcePath)) return;
            var source = ReadSource(sourcePath);
            ValidateUpdatePaths(root, source);
            TryDeleteGitHubPackage(candidate.PackagePath, source, root);
        }
        catch { }
    }

    private static UpdateSelection ReadAndValidatePackage(string root, UpdateSource source)
    {
        ValidateUpdatePaths(root, source);
        var feedPath = Path.Combine(source.UpdatesRoot, FeedManifestName);
        EnsureNoReparsePathOutsideRoot(feedPath, "Updates manifest");
        var published = JsonSerializer.Deserialize<PublishedUpdate>(File.ReadAllText(feedPath), JsonOptions)
            ?? throw new InvalidDataException("Updates manifest is invalid.");
        if (published.Schema != 1 || published.Manifest is null || string.IsNullOrWhiteSpace(published.PackageFile) ||
            published.PackageFile is "." or ".." || published.PackageFile.IndexOfAny(['/', '\\', ':']) >= 0 ||
            !published.PackageFile.EndsWith(".zip", StringComparison.OrdinalIgnoreCase) || !IsSha256(published.PackageSha256))
            throw new InvalidDataException("Updates manifest package path or hash is invalid.");

        var packagePath = Path.Combine(source.UpdatesRoot, published.PackageFile);
        EnsureNoReparsePathOutsideRoot(packagePath, "Update package");
        return ValidateUpdatePackage(root, source, packagePath, published.PackageSha256, published.Manifest,
            requireNewerVersion: true, setupRequiredOnBaselineMismatch: false);
    }

    private static UpdateSelection ReadAndValidateGitHubPackage(string root, UpdateSource source,
        string packagePath, string packageSha256, string version)
    {
        ValidateUpdatePaths(root, source);
        packagePath = Path.GetFullPath(packagePath);
        RequireUnderRoot(source.WorkRoot, packagePath, "GitHub update package");
        RequireOutsideData(root, packagePath);
        EnsureNoReparsePath(root, packagePath, "GitHub update package");
        if (!IsSha256(packageSha256) || !FixedEquals(HashFile(packagePath), packageSha256) ||
            !TryParseStableVersion(version, out _))
            throw new InvalidDataException("GitHub package hash or version is invalid.");

        using var archive = ZipFile.OpenRead(packagePath);
        var manifestEntry = archive.GetEntry(PackageManifestName)
            ?? throw new InvalidDataException("Embedded update manifest is missing.");
        UpdateManifest manifest;
        using (var input = manifestEntry.Open())
            manifest = JsonSerializer.Deserialize<UpdateManifest>(input)
                ?? throw new InvalidDataException("Embedded update manifest is invalid.");
        if (!string.Equals(manifest.Version, version, StringComparison.Ordinal))
            throw new InvalidDataException("WPF package version does not match its GitHub release tag.");
        return ValidateUpdatePackage(root, source, packagePath, packageSha256, manifest,
            requireNewerVersion: true, setupRequiredOnBaselineMismatch: true);
    }

    private static UpdateSelection ValidateUpdatePackage(string root, UpdateSource source,
        string packagePath, string packageSha256, UpdateManifest manifest,
        bool requireNewerVersion, bool setupRequiredOnBaselineMismatch)
    {
        ValidateUpdatePaths(root, source);
        if (!IsSha256(packageSha256))
            throw new InvalidDataException("Update package SHA-256 is invalid.");
        if (manifest.Schema != 1 || !AllowedFiles.SequenceEqual(manifest.Files.Keys.OrderBy(name => Array.IndexOf(AllowedFiles, name)), StringComparer.Ordinal))
            throw new InvalidDataException("Update allowlist or inventory is invalid.");
        if (!AllowedFiles.SequenceEqual(manifest.BaseFiles.Keys.OrderBy(name => Array.IndexOf(AllowedFiles, name)), StringComparer.Ordinal))
            throw new InvalidDataException("Baseline inventory is invalid.");
        if (!TryParseAppVersion(manifest.Version, out _, out _))
            throw new InvalidDataException("Update version is invalid.");

        var baselineVersionPath = SafeTarget(root, "app/VERSION.txt");
        var baselineVersion = File.ReadAllText(baselineVersionPath).Trim();
        var baselineReleasePath = SafeTarget(root, "app/RELEASE.json");
        using var baselineRelease = JsonDocument.Parse(File.ReadAllText(baselineReleasePath));
        var baselineExePath = SafeTarget(root, "VNText Studio.exe");
        var baselineProductVersion = FileVersionInfo.GetVersionInfo(baselineExePath).ProductVersion?.Split('+', 2)[0].Trim();
        if (baselineRelease.RootElement.GetProperty("version").GetString() != baselineVersion ||
            baselineProductVersion != baselineVersion ||
            !FixedEquals(HashFile(baselineExePath), baselineRelease.RootElement.GetProperty("sha256").GetString() ?? ""))
        {
            if (setupRequiredOnBaselineMismatch)
                throw new BaselineMismatchException("Installed baseline metadata is inconsistent.");
            throw new InvalidDataException("Installed baseline metadata is inconsistent.");
        }
        if (requireNewerVersion && !IsStrictlyNewerVersion(baselineVersion, manifest.Version))
            throw new NoNewerUpdateException("Không có bản cập nhật mới hơn cho phiên bản hiện tại.");

        foreach (var relative in AllowedFiles)
        {
            var installedPath = SafeTarget(root, relative);
            var baseline = manifest.BaseFiles[relative];
            if (baseline.Size < 0 || !IsSha256(baseline.Sha256))
                throw new InvalidDataException("Baseline inventory record is invalid: " + relative);
            if (baseline.Size != new FileInfo(installedPath).Length || !FixedEquals(HashFile(installedPath), baseline.Sha256))
            {
                if (setupRequiredOnBaselineMismatch)
                    throw new BaselineMismatchException("The WPF package baseline differs from the installed files.");
                throw new NoNewerUpdateException("Không có gói cập nhật dành cho baseline của bản cài này.");
            }
        }

        if (!FixedEquals(HashFile(packagePath), packageSha256))
            throw new InvalidDataException("Update package SHA-256 mismatch.");

        using var archive = ZipFile.OpenRead(packagePath);
        var names = archive.Entries.Select(entry => entry.FullName).ToArray();
        if (names.Length != names.Distinct(StringComparer.OrdinalIgnoreCase).Count() || names.Count(name => name == PackageManifestName) != 1)
            throw new InvalidDataException("Update package has duplicate or missing manifest entries.");
        if (names.Length != AllowedFiles.Length + 1 || names.Any(name => name != PackageManifestName && !AllowedFiles.Contains(name, StringComparer.Ordinal)))
            throw new InvalidDataException("Update package contains files outside the exact WPF allowlist.");
        UpdateManifest embedded;
        using (var input = archive.GetEntry(PackageManifestName)!.Open())
            embedded = JsonSerializer.Deserialize<UpdateManifest>(input) ?? throw new InvalidDataException("Embedded update manifest is invalid.");
        if (!ManifestsEqual(manifest, embedded))
            throw new InvalidDataException("Updates manifest does not match the package manifest.");

        foreach (var relative in AllowedFiles)
        {
            var entry = archive.GetEntry(relative) ?? throw new InvalidDataException("Update file missing: " + relative);
            var item = manifest.Files[relative];
            if (item.Size < 0 || !IsSha256(item.Sha256) || entry.Length != item.Size || !FixedEquals(HashEntry(entry), item.Sha256))
                throw new InvalidDataException("Update file hash/size mismatch: " + relative);
        }

        using var candidateVersionStream = archive.GetEntry("app/VERSION.txt")!.Open();
        using var versionReader = new StreamReader(candidateVersionStream);
        if (versionReader.ReadToEnd().Trim() != manifest.Version)
            throw new InvalidDataException("Update VERSION.txt does not match its manifest.");
        using var candidateReleaseStream = archive.GetEntry("app/RELEASE.json")!.Open();
        using var candidateRelease = JsonDocument.Parse(candidateReleaseStream);
        if (candidateRelease.RootElement.GetProperty("version").GetString() != manifest.Version ||
            !FixedEquals(candidateRelease.RootElement.GetProperty("sha256").GetString() ?? "", manifest.Files["VNText Studio.exe"].Sha256))
            throw new InvalidDataException("Candidate RELEASE.json does not match its executable and version.");
        ValidateCandidateExecutableVersion(root, source, archive, manifest);
        return new UpdateSelection(packagePath, manifest);
    }

    private static void ValidateCandidateExecutableVersion(string root, UpdateSource source, ZipArchive archive, UpdateManifest manifest)
    {
        var validationRoot = Path.Combine(source.WorkRoot, "validate-" + Guid.NewGuid().ToString("N"));
        var validationExe = Path.Combine(validationRoot, "VNText Studio.exe");
        try
        {
            RequireUnderRoot(root, validationRoot, "package validation path");
            RequireOutsideData(root, validationRoot);
            Directory.CreateDirectory(validationRoot);
            using (var input = archive.GetEntry("VNText Studio.exe")!.Open())
            using (var output = new FileStream(validationExe, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                input.CopyTo(output);
            if (new FileInfo(validationExe).Length != manifest.Files["VNText Studio.exe"].Size ||
                !FixedEquals(HashFile(validationExe), manifest.Files["VNText Studio.exe"].Sha256))
                throw new InvalidDataException("Candidate executable changed while it was validated.");
            var productVersion = FileVersionInfo.GetVersionInfo(validationExe).ProductVersion?.Split('+', 2)[0].Trim();
            if (productVersion != manifest.Version)
                throw new InvalidDataException("Candidate executable version does not match its manifest.");
        }
        finally
        {
            TryDeleteTransaction(validationRoot, source.WorkRoot, root);
        }
    }

    private static Dictionary<string, string> ExtractPackage(UpdateSource source, UpdateSelection update)
    {
        Directory.CreateDirectory(source.StagingRoot);
        var staged = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        using var archive = ZipFile.OpenRead(update.PackagePath);
        foreach (var relative in AllowedFiles)
        {
            var entry = archive.GetEntry(relative) ?? throw new InvalidDataException("Update file missing: " + relative);
            var target = SafeTarget(source.StagingRoot, relative);
            Directory.CreateDirectory(Path.GetDirectoryName(target)!);
            using (var input = entry.Open())
            using (var output = new FileStream(target, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                input.CopyTo(output);
            var item = update.Manifest.Files[relative];
            if (new FileInfo(target).Length != item.Size || !FixedEquals(HashFile(target), item.Sha256))
                throw new InvalidDataException("Update file hash/size mismatch: " + relative);
            staged[relative] = target;
        }
        return staged;
    }

    private static void ValidateMetadata(string root, UpdateManifest manifest, Dictionary<string, string> staged)
    {
        using var release = JsonDocument.Parse(File.ReadAllText(staged["app/RELEASE.json"]));
        var stagedVersion = File.ReadAllText(staged["app/VERSION.txt"]).Trim();
        var productVersion = FileVersionInfo.GetVersionInfo(staged["VNText Studio.exe"]).ProductVersion?.Split('+', 2)[0].Trim();
        if (stagedVersion != manifest.Version || productVersion != manifest.Version ||
            release.RootElement.GetProperty("version").GetString() != manifest.Version ||
            !FixedEquals(release.RootElement.GetProperty("sha256").GetString() ?? "", manifest.Files["VNText Studio.exe"].Sha256))
            throw new InvalidDataException("Candidate executable, VERSION.txt and RELEASE.json versions/hashes disagree.");
        foreach (var relative in AllowedFiles)
            _ = SafeTarget(root, relative);
    }

    private static UpdateSource ReadSource(string path) =>
        JsonSerializer.Deserialize<UpdateSource>(File.ReadAllText(path), JsonOptions)
        ?? throw new InvalidDataException("Update source configuration is invalid.");

    private static string SourcePath() => Path.Combine(InstallRoot(), SourceName);
    private static string InstallRoot() => Path.GetDirectoryName(WorkerPaths.MainExePath())!;
    private static readonly JsonSerializerOptions JsonOptions = new() { PropertyNameCaseInsensitive = true };

    private static string SafeTarget(string root, string relative)
    {
        if (Path.IsPathRooted(relative) || relative.Contains(':') || relative.Contains('\\') ||
            relative.Split('/').Any(part => part is "" or "." or ".."))
            throw new InvalidDataException("Unsafe update path: " + relative);
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var target = Path.GetFullPath(Path.Combine(root, relative.Replace('/', Path.DirectorySeparatorChar)));
        if (!target.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Update path escaped its root.");
        if ((File.Exists(target) || Directory.Exists(target)) &&
            (File.GetAttributes(target) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException("Update path is a reparse point.");
        var cursor = Path.GetDirectoryName(target);
        while (!string.IsNullOrEmpty(cursor) && cursor.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase))
        {
            if (Directory.Exists(cursor) && (File.GetAttributes(cursor) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Update path traverses a reparse point.");
            cursor = Path.GetDirectoryName(cursor);
        }
        return target;
    }

    private static void RequireUnderRoot(string root, string path, string label)
    {
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var fullPath = Path.GetFullPath(path);
        if (!fullPath.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException(label + " must stay under the install test scope.");
    }

    private static void RequireOutsideData(string root, string path)
    {
        var data = Path.GetFullPath(Path.Combine(root, "data")).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var fullPath = Path.GetFullPath(path);
        if (SamePath(fullPath, data.TrimEnd(Path.DirectorySeparatorChar)) || fullPath.StartsWith(data, StringComparison.OrdinalIgnoreCase))
            throw new InvalidDataException("Updater temporary paths must stay outside data/.");
    }

    private static void ValidateUpdatePaths(string root, UpdateSource source)
    {
        if (string.IsNullOrWhiteSpace(source.UpdatesRoot))
            throw new InvalidDataException("Updates source path is missing.");
        var updatesRoot = Path.GetFullPath(source.UpdatesRoot);
        if (IsUnderOrEqual(root, updatesRoot) || IsUnderOrEqual(updatesRoot, root))
            throw new InvalidDataException("Updates folder must remain outside the install root.");
        RequireUnderRoot(root, source.WorkRoot, "update working directory");
        RequireUnderRoot(root, source.BackupRoot, "update backup directory");
        RequireUnderRoot(root, source.StagingRoot, "update staging directory");
        RequireUnderRoot(root, source.UpdaterPath, "updater executable");
        RequireUnderRoot(root, source.LogPath, "update log");
        RequireOutsideData(root, source.WorkRoot);
        RequireOutsideData(root, source.BackupRoot);
        RequireOutsideData(root, source.StagingRoot);
        RequireOutsideData(root, source.UpdaterPath);
        RequireOutsideData(root, source.LogPath);
        EnsureNoReparsePathOutsideRoot(updatesRoot, "Updates folder");
        foreach (var (path, label) in new[]
        {
            (source.WorkRoot, "update working directory"),
            (source.BackupRoot, "update backup directory"),
            (source.StagingRoot, "update staging directory"),
            (source.UpdaterPath, "updater executable"),
            (source.LogPath, "update log"),
        })
            EnsureNoReparsePath(root, path, label);
    }

    private static bool IsUnderOrEqual(string root, string path)
    {
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var fullPath = Path.GetFullPath(path).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        return SamePath(fullRoot, fullPath) || fullPath.StartsWith(fullRoot + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
    }

    private static void EnsureNoReparsePathOutsideRoot(string path, string label)
    {
        var fullPath = Path.GetFullPath(path);
        var driveRoot = Path.GetPathRoot(fullPath) ?? throw new InvalidDataException(label + " has no filesystem root.");
        var cursor = driveRoot;
        foreach (var part in fullPath[driveRoot.Length..].Split([Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar], StringSplitOptions.RemoveEmptyEntries))
        {
            cursor = Path.Combine(cursor, part);
            if ((File.Exists(cursor) || Directory.Exists(cursor)) && (File.GetAttributes(cursor) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException(label + " traverses a reparse point: " + cursor);
        }
    }

    private static bool ManifestsEqual(UpdateManifest left, UpdateManifest right) =>
        left.Schema == right.Schema && left.Version == right.Version && left.SourceSha == right.SourceSha &&
        left.SourceTreeSha256 == right.SourceTreeSha256 && left.Notes == right.Notes &&
        RecordsEqual(left.Files, right.Files) && RecordsEqual(left.BaseFiles, right.BaseFiles);

    private static bool RecordsEqual(Dictionary<string, FileRecord> left, Dictionary<string, FileRecord> right) =>
        left.Count == right.Count && left.All(pair => right.TryGetValue(pair.Key, out var value) &&
            pair.Value.Size == value.Size && string.Equals(pair.Value.Sha256, value.Sha256, StringComparison.OrdinalIgnoreCase));

    private static void EnsureNoReparsePath(string root, string path, string label)
    {
        var fullRoot = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
        var fullPath = Path.GetFullPath(path);
        RequireUnderRoot(fullRoot, fullPath, label);
        if ((Directory.Exists(fullRoot) || File.Exists(fullRoot)) &&
            (File.GetAttributes(fullRoot) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException(label + " root is a reparse point.");
        var relative = Path.GetRelativePath(fullRoot, fullPath);
        var cursor = fullRoot;
        foreach (var part in relative.Split(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar))
        {
            if (part.Length == 0 || part == ".") continue;
            cursor = Path.Combine(cursor, part);
            if ((Directory.Exists(cursor) || File.Exists(cursor)) &&
                (File.GetAttributes(cursor) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException(label + " traverses a reparse point.");
        }
    }

    private static void TryDeleteTransaction(string transactionPath, string parent, string installRoot)
    {
        try
        {
            RequireUnderRoot(installRoot, transactionPath, "transaction cleanup path");
            RequireOutsideData(installRoot, transactionPath);
            RequireUnderRoot(parent, transactionPath, "transaction cleanup parent");
            if (Directory.Exists(transactionPath) && (File.GetAttributes(transactionPath) & FileAttributes.ReparsePoint) == 0)
                Directory.Delete(transactionPath, recursive: true);
        }
        catch { }
    }

    private static string HashEntry(ZipArchiveEntry entry)
    {
        using var input = entry.Open();
        return Convert.ToHexString(SHA256.HashData(input)).ToLowerInvariant();
    }

    private static bool IsSha256(string value) =>
        value.Length == 64 && value.All(ch => char.IsAsciiHexDigit(ch));

    private static bool TryParseAppVersion(string value, out Version core, out string suffix)
    {
        core = new Version(0, 0, 0);
        suffix = "";
        var match = Regex.Match(value ?? "", "^(?<core>[0-9]+\\.[0-9]+\\.[0-9]+)(?:-(?<suffix>[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*))?$");
        if (!match.Success || !Version.TryParse(match.Groups["core"].Value, out var parsedCore) || parsedCore is null)
            return false;
        core = parsedCore;
        suffix = match.Groups["suffix"].Value;
        return true;
    }

    private static bool SamePath(string left, string right) =>
        string.Equals(Path.GetFullPath(left).TrimEnd(Path.DirectorySeparatorChar), Path.GetFullPath(right).TrimEnd(Path.DirectorySeparatorChar), StringComparison.OrdinalIgnoreCase);

    private static bool WaitForExit(int pid, TimeSpan timeout)
    {
        try { using var process = Process.GetProcessById(pid); return process.WaitForExit((int)timeout.TotalMilliseconds); }
        catch (ArgumentException) { return true; }
    }

    private static bool RunHealthCheck(string executable, string root)
    {
        using var process = Process.Start(new ProcessStartInfo(executable, "--update-health-check")
        {
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true,
        });
        return process is not null && process.WaitForExit(45000) && process.ExitCode == 0;
    }

    private static void StartApp(string root)
    {
        var exe = Path.Combine(root, "VNText Studio.exe");
        Process.Start(new ProcessStartInfo(exe) { WorkingDirectory = root, UseShellExecute = false });
    }

    private static string HashFile(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();
    }

    private static bool FixedEquals(string left, string right) =>
        left.Length == right.Length && CryptographicOperations.FixedTimeEquals(Convert.FromHexString(left), Convert.FromHexString(right));

    private static void Log(string path, string message) =>
        File.AppendAllText(path, $"{DateTimeOffset.UtcNow:O} {message}{Environment.NewLine}");

    private sealed class UpdateSource
    {
        [JsonPropertyName("updates_root")] public string UpdatesRoot { get; set; } = "";
        [JsonPropertyName("github_owner")] public string GitHubOwner { get; set; } = "";
        [JsonPropertyName("github_repository")] public string GitHubRepository { get; set; } = "";
        [JsonPropertyName("work_root")] public string WorkRoot { get; set; } = "";
        [JsonPropertyName("backup_root")] public string BackupRoot { get; set; } = "";
        [JsonPropertyName("staging_root")] public string StagingRoot { get; set; } = "";
        [JsonPropertyName("updater_path")] public string UpdaterPath { get; set; } = "";
        [JsonPropertyName("log_path")] public string LogPath { get; set; } = "";
        [JsonPropertyName("fault_inject_after_first_replace")] public bool FaultInjectAfterFirstReplace { get; set; }
    }

    private sealed class PublishedUpdate
    {
        [JsonPropertyName("schema")] public int Schema { get; set; }
        [JsonPropertyName("package_file")] public string PackageFile { get; set; } = "";
        [JsonPropertyName("package_sha256")] public string PackageSha256 { get; set; } = "";
        [JsonPropertyName("manifest")] public UpdateManifest Manifest { get; set; } = new();
    }

    private sealed record UpdateSelection(string PackagePath, UpdateManifest Manifest);

    private sealed record GitHubReleaseInfo(string Tag, string VersionText, Version Version, List<GitHubAssetInfo> Assets);

    private sealed record GitHubAssetInfo(string Name, string Digest, long Size, string DownloadUrl);

    private sealed class NoNewerUpdateException(string message) : Exception(message);

    private sealed class BaselineMismatchException(string message) : Exception(message);

    private sealed class UpdateManifest
    {
        [JsonPropertyName("schema")] public int Schema { get; set; }
        [JsonPropertyName("version")] public string Version { get; set; } = "";
        [JsonPropertyName("source_sha")] public string SourceSha { get; set; } = "";
        [JsonPropertyName("source_tree_sha256")] public string? SourceTreeSha256 { get; set; }
        [JsonPropertyName("notes")] public string Notes { get; set; } = "";
        [JsonPropertyName("files")] public Dictionary<string, FileRecord> Files { get; set; } = new(StringComparer.Ordinal);
        [JsonPropertyName("base_files")] public Dictionary<string, FileRecord> BaseFiles { get; set; } = new(StringComparer.Ordinal);
    }

    private sealed class FileRecord
    {
        [JsonPropertyName("sha256")] public string Sha256 { get; set; } = "";
        [JsonPropertyName("size")] public long Size { get; set; }
    }
}
