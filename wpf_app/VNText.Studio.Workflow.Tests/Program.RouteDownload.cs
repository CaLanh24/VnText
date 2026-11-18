using System.IO;
using System.IO.Compression;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using VNText.Studio.App.Services;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private sealed class RouteProgress : IProgress<(long Received, long Total)>
    {
        internal readonly List<(long Received, long Total)> Values = [];
        public void Report((long Received, long Total) value) => Values.Add(value);
    }

    private static void FullAppUpdate_RouteDownloadChecks(string failure)
    {
        var first = CreateFullAppUpdateFixture();
        var second = CreateFullAppUpdateFixture(baselineExeOverride: Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE"),
            candidateExeOverride: Environment.GetEnvironmentVariable("VNTEXT_WPF_FUTURE_EXE")
                ?? throw new InvalidOperationException("Third versioned executable is required for a real two-hop download."));
        try
        {
            var current = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_BASELINE_EXE")!);
            var middle = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_CANDIDATE_EXE")!);
            var future = ReadExecutableProductVersion(Environment.GetEnvironmentVariable("VNTEXT_WPF_FUTURE_EXE")!);
            var firstBytes = File.ReadAllBytes(first.PackagePath);
            var secondBytes = MakeContinuousRoutePackage(first.PackagePath, second.PackagePath, failure == "discontinuous");
            var firstHash = HashBytes(firstBytes);
            var secondHash = HashBytes(secondBytes);
            string Name(string from, string to, string hash) => $"full-app-update-from-{from}-to-{to}-{hash[..16]}.zip";
            string Url(string to, string name) => $"https://github.com/test-owner/test-repo/releases/download/v{to}/{name}";
            var firstName = Name(current, middle, firstHash);
            var secondName = Name(middle, future, secondHash);
            var firstUrl = Url(middle, firstName);
            var secondUrl = Url(future, secondName);
            var releases = JsonSerializer.Serialize(new[] {
                GitHubRelease("v" + future, false, false, GitHubAsset(secondName, "sha256:" + secondHash, secondBytes.LongLength, secondUrl)),
                GitHubRelease("v" + middle, false, false, GitHubAsset(firstName, "sha256:" + firstHash, firstBytes.LongLength, firstUrl)) });
            _ = CreateFullAppGitHubHandler(first, firstHash, firstBytes.LongLength, firstUrl, firstBytes);
            var beforeExe = HashFile(Path.Combine(first.Root, "VNText Studio.exe"));
            var beforeData = File.ReadAllBytes(Path.Combine(first.Root, "data", "keep.bin"));
            var beforeModel = File.ReadAllBytes(Path.Combine(first.Root, "app", "worker", "models", "pinned.bin"));
            using var cancellation = new CancellationTokenSource();
            var progress = new RouteProgress();
            TestHttpMessageHandler Handler(bool inject) => new((request, _) =>
            {
                if (request.RequestUri?.Host == "api.github.com") return Task.FromResult(JsonResponse(releases));
                if (request.RequestUri?.AbsoluteUri == firstUrl) return Task.FromResult(BinaryResponse(firstBytes));
                AssertEqual(secondUrl, request.RequestUri!.AbsoluteUri);
                if (inject && failure == "cancel")
                {
                    cancellation.Cancel();
                    return Task.FromCanceled<HttpResponseMessage>(cancellation.Token);
                }
                if (inject && failure == "network") return Task.FromResult(new HttpResponseMessage(HttpStatusCode.ServiceUnavailable));
                var bytes = secondBytes.ToArray();
                if (inject && failure == "tamper") bytes[bytes.Length / 2] ^= 0x5a;
                return Task.FromResult(BinaryResponse(bytes));
            });
            var handler = Handler(failure != "success");
            var result = WpfUpdateService.CheckGitHubUpdateAsync(first.Root, handler, cancellation.Token, progress: progress).GetAwaiter().GetResult();
            AssertEqual(3, handler.Requests.Count);
            if (failure == "success")
            {
                AssertEqual(GitHubUpdateState.UpdateAvailable, result.State);
                AssertTrue(result.FullAppRoute);
                AssertEqual(2, result.Route?.Count);
                AssertEqual(firstHash, HashFile(result.Route![0].PackagePath));
                AssertEqual(secondHash, HashFile(result.Route[1].PackagePath));
                using var descriptor = JsonDocument.Parse(File.ReadAllText(result.PackagePath));
                AssertEqual(2, descriptor.RootElement.GetProperty("hops").GetArrayLength());
                var total = firstBytes.LongLength + secondBytes.LongLength;
                AssertTrue(progress.Values.Count > 1);
                AssertTrue(progress.Values.All(p => p.Total == total && p.Received >= 0 && p.Received <= total));
                AssertTrue(progress.Values.Zip(progress.Values.Skip(1), (a, b) => b.Received >= a.Received).All(p => p));
                AssertEqual(total, progress.Values[^1].Received);
            }
            else
            {
                AssertEqual(failure == "cancel" ? GitHubUpdateState.Timeout : failure == "network" ? GitHubUpdateState.Offline : GitHubUpdateState.InvalidPackage, result.State);
                AssertEqual(0, Directory.GetFiles(Path.Combine(first.Root, ".update", "work"), "github-update-route-*").Length);
                if (failure != "discontinuous")
                {
                    var retry = WpfUpdateService.CheckGitHubUpdateAsync(first.Root, Handler(false)).GetAwaiter().GetResult();
                    AssertEqual(GitHubUpdateState.UpdateAvailable, retry.State);
                    AssertEqual(2, retry.Route?.Count);
                }
            }
            AssertEqual(beforeExe, HashFile(Path.Combine(first.Root, "VNText Studio.exe")));
            AssertTrue(beforeData.SequenceEqual(File.ReadAllBytes(Path.Combine(first.Root, "data", "keep.bin"))));
            AssertTrue(beforeModel.SequenceEqual(File.ReadAllBytes(Path.Combine(first.Root, "app", "worker", "models", "pinned.bin"))));
        }
        finally { DeleteFullAppUpdateFixture(first); DeleteFullAppUpdateFixture(second); }
    }

    private static byte[] MakeContinuousRoutePackage(string firstPath, string secondPath, bool discontinuous)
    {
        using var first = ZipFile.OpenRead(firstPath);
        using var second = ZipFile.OpenRead(secondPath);
        using var firstManifest = JsonDocument.Parse(first.GetEntry(FullAppUpdateService.PackageManifestName)!.Open());
        using var secondManifest = JsonDocument.Parse(second.GetEntry(FullAppUpdateService.PackageManifestName)!.Open());
        var baseline = firstManifest.RootElement.GetProperty("files").EnumerateObject().ToDictionary(p => p.Name, p => p.Value.Clone());
        var target = secondManifest.RootElement.GetProperty("files").EnumerateObject().ToDictionary(p => p.Name, p => p.Value.Clone());
        if (discontinuous) baseline["app/keep.txt"] = JsonSerializer.SerializeToElement(new { sha256 = new string('0', 64), size = 9 });
        var additions = target.Where(p => !baseline.ContainsKey(p.Key)).ToDictionary(p => p.Key, p => p.Value);
        var replacements = target.Where(p => baseline.ContainsKey(p.Key) && p.Value.GetProperty("sha256").GetString() != baseline[p.Key].GetProperty("sha256").GetString()).ToDictionary(p => p.Key, p => p.Value);
        var manifest = secondManifest.RootElement.EnumerateObject().ToDictionary(p => p.Name, p => p.Value.Clone());
        manifest["base_files"] = JsonSerializer.SerializeToElement(baseline);
        manifest["add_files"] = JsonSerializer.SerializeToElement(additions);
        manifest["replace_files"] = JsonSerializer.SerializeToElement(replacements);
        manifest["delete_files"] = JsonSerializer.SerializeToElement(baseline.Keys.Except(target.Keys).ToArray());
        using var output = new MemoryStream();
        using (var archive = new ZipArchive(output, ZipArchiveMode.Create, leaveOpen: true))
        {
            WriteZipEntry(archive, FullAppUpdateService.PackageManifestName, JsonSerializer.SerializeToUtf8Bytes(manifest));
            foreach (var name in additions.Keys.Concat(replacements.Keys))
            {
                using var bytes = new MemoryStream();
                using var input = second.GetEntry(name)!.Open();
                input.CopyTo(bytes);
                WriteZipEntry(archive, name, bytes.ToArray());
            }
        }
        return output.ToArray();
    }
}
