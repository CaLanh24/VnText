# Publish VNText Studio — Setup.exe plus the retained WPF Updates feed.
param(
    [string]$ReleaseRoot = "",
    [string]$DevRunRoot = "",
    [string]$ArtifactWorkRoot = "",
    [string]$ArtifactHelpersRoot = "",
    [string]$PythonPath = "",
    [string]$WorkerVenvRoot = "",
    [string]$ModelRoot = "",
    [string]$SourceRevision = "",
    [string]$WpfUpdateVersion = "",
    [string]$FullAppUpdateBaselineRoot = "",
    [string]$GitHubOwner = "",
    [string]$GitHubRepository = "",
    [string]$ArtifactScopeId = "",
    [switch]$SkipTests,
    [switch]$SkipWpfUpdatePackage,
    [switch]$SkipBuild,
    [switch]$BuildLegacy,
    [switch]$UsePreinstalledDependencies,
    [switch]$SkipIconGeneration,
    [switch]$RequireIsolatedArtifacts,
    [ValidateRange(1, 3600)]
    [int]$CleanupTimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"
function Assert-ReleaseRootLayout {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) { return }
    $releaseItem = Get-Item -LiteralPath $Path -Force
    if (-not $releaseItem.PSIsContainer) {
        throw "ReleaseRoot exists but is not a directory: $Path"
    }
    if (($releaseItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "ReleaseRoot cannot be a junction or symbolic link: $Path"
    }
    $allowedItems = @{
        "Setup.exe" = $false
        "Updates" = $true
    }
    $unexpectedItems = @()
    foreach ($item in @(Get-ChildItem -LiteralPath $Path -Force)) {
        if (-not $allowedItems.ContainsKey($item.Name)) {
            $unexpectedItems += $item.Name
            continue
        }
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or
            $item.PSIsContainer -ne [bool]$allowedItems[$item.Name]) {
            $unexpectedItems += $item.Name
        }
    }
    if ($unexpectedItems.Count -gt 0) {
        $names = @($unexpectedItems | Sort-Object -Unique) -join ", "
        throw "Refusing to publish; unexpected or invalid top-level ReleaseRoot item(s): $names"
    }
}
if ($RequireIsolatedArtifacts -and -not $UsePreinstalledDependencies) {
    throw "Isolated publish must use only preinstalled dependencies (-UsePreinstalledDependencies)."
}
if ($RequireIsolatedArtifacts -and (-not $SkipTests -or $SkipBuild -or $BuildLegacy)) {
    throw "Isolated publish requires the focused preflight/build path: -SkipTests, WPF build enabled, and Python preview build disabled."
}
if ($SkipBuild) {
    throw "Standard Setup publishing requires a fresh WPF app build; -SkipBuild is not supported."
}
function Get-WpfUpdateVersionNumeric([string]$Version, [bool]$SkipPackage) {
    if ($SkipPackage) {
        if (-not [string]::IsNullOrWhiteSpace($Version)) {
            throw "SkipWpfUpdatePackage cannot be combined with WpfUpdateVersion."
        }
        return $null
    }
    $match = [regex]::Match($Version, '^(\d+)\.(\d+)\.(\d+)(?:-[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*)?$')
    if (-not $match.Success) { throw "WpfUpdateVersion must be an explicit semantic version when requesting a WPF package." }
    return "{0}.{1}.{2}.0" -f $match.Groups[1].Value, $match.Groups[2].Value, $match.Groups[3].Value
}
$WpfUpdateVersionNumeric = Get-WpfUpdateVersionNumeric $WpfUpdateVersion ([bool]$SkipWpfUpdatePackage)
if ([string]::IsNullOrWhiteSpace($GitHubOwner) -ne [string]::IsNullOrWhiteSpace($GitHubRepository)) {
    throw "GitHubOwner and GitHubRepository must either both be supplied or both be blank."
}
if (-not [string]::IsNullOrWhiteSpace($GitHubOwner)) {
    $GitHubOwner = $GitHubOwner.Trim()
    $GitHubRepository = $GitHubRepository.Trim()
    if ($GitHubOwner -notmatch '^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$' -or
        $GitHubRepository -notmatch '^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?$') {
        throw "GitHubOwner or GitHubRepository contains unsupported characters."
    }
}
$DevRoot = Split-Path -Parent $PSScriptRoot
$DevRoot = [System.IO.Path]::GetFullPath($DevRoot)
$DevRunRoot = if ([string]::IsNullOrWhiteSpace($DevRunRoot)) { Join-Path $DevRoot "DEV_RUN" } else { $DevRunRoot }
$DevRunRoot = [System.IO.Path]::GetFullPath($DevRunRoot)
$ArtifactWorkRoot = if ([string]::IsNullOrWhiteSpace($ArtifactWorkRoot)) { Join-Path $DevRoot "RELEASE_RUN" } else { $ArtifactWorkRoot }
$ArtifactWorkRoot = [System.IO.Path]::GetFullPath($ArtifactWorkRoot)
$ArtifactHelpersRoot = if ([string]::IsNullOrWhiteSpace($ArtifactHelpersRoot)) { Join-Path $DevRoot "tests\lib" } else { [System.IO.Path]::GetFullPath($ArtifactHelpersRoot) }
$WorkerVenvRoot = if ([string]::IsNullOrWhiteSpace($WorkerVenvRoot)) { Join-Path $DevRoot ".dev-env\.venv" } else { [System.IO.Path]::GetFullPath($WorkerVenvRoot) }
if (-not (Test-Path -LiteralPath (Join-Path $WorkerVenvRoot "Scripts\python.exe"))) {
    throw "WorkerVenvRoot must contain Scripts\python.exe: $WorkerVenvRoot"
}
$ModelRoot = if ([string]::IsNullOrWhiteSpace($ModelRoot)) { Join-Path $ArtifactWorkRoot "models\opus-mt-en-vi-int8" } else { [System.IO.Path]::GetFullPath($ModelRoot) }
$canonicalRepoRoot = Split-Path -Parent $ArtifactHelpersRoot
$canonicalRepoRoot = Split-Path -Parent $canonicalRepoRoot
$expectedDevRunRoot = [System.IO.Path]::GetFullPath((Join-Path $canonicalRepoRoot "DEV_RUN"))
$expectedWorkRoot = [System.IO.Path]::GetFullPath((Join-Path $canonicalRepoRoot "RELEASE_RUN"))
if (-not $DevRunRoot.Equals($expectedDevRunRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "DevRunRoot must be the canonical project's DEV_RUN: $expectedDevRunRoot"
}
if (-not $ArtifactWorkRoot.Equals($expectedWorkRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "ArtifactWorkRoot must be the canonical project's RELEASE_RUN: $expectedWorkRoot"
}
$workPrefix = $ArtifactWorkRoot.TrimEnd('\') + '\'
if ($RequireIsolatedArtifacts -and -not $DevRoot.StartsWith($workPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Isolated publish source must be a registered working-tree snapshot under RELEASE_RUN."
}
if ([string]::IsNullOrWhiteSpace($ReleaseRoot)) {
    $ReleaseRoot = Join-Path (Split-Path -Parent $DevRoot) "VNText_Studio_Release"
} else {
    $ReleaseRoot = [System.IO.Path]::GetFullPath($ReleaseRoot)
}
$FullAppUpdateBaselineRoot = if ([string]::IsNullOrWhiteSpace($FullAppUpdateBaselineRoot)) { "" } else { [System.IO.Path]::GetFullPath($FullAppUpdateBaselineRoot) }
if ($FullAppUpdateBaselineRoot) {
    if (-not (Test-Path -LiteralPath $FullAppUpdateBaselineRoot -PathType Container)) {
        throw "FullAppUpdateBaselineRoot must be an existing install from the intended update baseline: $FullAppUpdateBaselineRoot"
    }
    $baselineItem = Get-Item -LiteralPath $FullAppUpdateBaselineRoot -Force
    if (($baselineItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "FullAppUpdateBaselineRoot cannot be a junction or symbolic link: $FullAppUpdateBaselineRoot"
    }
}
$ReleaseRoot = [System.IO.Path]::GetFullPath($ReleaseRoot)
$WorkRoot = $ArtifactWorkRoot
$publishScope = if ([string]::IsNullOrWhiteSpace($ArtifactScopeId)) { "setup-publish-" + [guid]::NewGuid().ToString("N") } else { $ArtifactScopeId.Trim() }
if ($publishScope -notmatch '^[A-Za-z0-9_-]{1,80}$') { throw "ArtifactScopeId must be a simple unique identifier" }
$publishArtifactRoot = Join-Path $WorkRoot $publishScope
$devPrefix = $DevRoot.TrimEnd('\') + '\'
$scopePrefix = $publishArtifactRoot.TrimEnd('\') + '\'
$releasePrefix = $ReleaseRoot.TrimEnd('\') + '\'
$insideWork = $ReleaseRoot.StartsWith($workPrefix, [System.StringComparison]::OrdinalIgnoreCase)
$insideRepo = $ReleaseRoot.StartsWith($devPrefix, [System.StringComparison]::OrdinalIgnoreCase)
$isRepoOrAncestor = $ReleaseRoot.Equals($DevRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $DevRoot.StartsWith($releasePrefix, [System.StringComparison]::OrdinalIgnoreCase)
$isUnsafeRepoPath = $isRepoOrAncestor -or ($insideRepo -and -not $insideWork) -or
    $ReleaseRoot.Equals($WorkRoot, [System.StringComparison]::OrdinalIgnoreCase)
if ($isUnsafeRepoPath) {
    throw "ReleaseRoot must be outside the repository, except for a dedicated child of RELEASE_RUN: $ReleaseRoot"
}
if ($RequireIsolatedArtifacts -and -not $ReleaseRoot.StartsWith($scopePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Isolated publish requires ReleaseRoot below its registered run scope: $publishArtifactRoot"
}
if ($RequireIsolatedArtifacts -and (Test-Path -LiteralPath $publishArtifactRoot)) {
    throw "Refusing to reuse an existing isolated publish scope: $publishArtifactRoot"
}
Assert-ReleaseRootLayout -Path $ReleaseRoot
Set-Location $DevRoot
$SourceSha = if (-not [string]::IsNullOrWhiteSpace($SourceRevision)) { $SourceRevision.Trim() } else { (& git -C $DevRoot rev-parse HEAD).Trim() }
if ($SourceSha -notmatch '^[0-9a-f]{40}$') {
    throw "Cannot resolve a valid source git SHA for Release provenance"
}
# Keep build/verify helpers from recreating Python bytecode in either the
# staging tree or the final portable runtime.
$env:PYTHONDONTWRITEBYTECODE = "1"
$safeTempRoot = Join-Path $DevRunRoot "_temp"
$devDataRoot = Join-Path $DevRunRoot "_data"
$devLocalAppData = Join-Path $DevRunRoot "_localappdata"
$devAppData = Join-Path $DevRunRoot "_appdata"
$devCliHome = Join-Path $DevRunRoot "_dotnet_cli"
$devNugetRoot = Join-Path $DevRunRoot "_nuget"
$devCacheRoot = Join-Path $DevRunRoot "_cache"
foreach ($path in @($safeTempRoot, $devDataRoot, $devLocalAppData, $devAppData, $devCliHome, $devNugetRoot, $devCacheRoot)) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
}
$env:TEMP = $safeTempRoot
$env:TMP = $safeTempRoot
$env:TMPDIR = $safeTempRoot
$env:LOCALAPPDATA = $devLocalAppData
$env:APPDATA = $devAppData
$env:DOTNET_CLI_HOME = $devCliHome
$env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
$env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"
$env:NUGET_PACKAGES = $devNugetRoot
$env:PIP_CACHE_DIR = Join-Path $DevRunRoot "_pip_cache"
$env:VNTEXT_DATA_ROOT = $devDataRoot
$env:VNTEXT_WORK_ARTIFACTS_ROOT = Join-Path $DevRunRoot "_work"
$env:VNTEXT_DEV_RUN_ROOT = $DevRunRoot
$env:HF_HOME = Join-Path $devCacheRoot "huggingface"
$env:HF_HUB_CACHE = Join-Path $devCacheRoot "huggingface\hub"
$env:TRANSFORMERS_CACHE = Join-Path $devCacheRoot "huggingface\transformers"
$env:TORCH_HOME = Join-Path $devCacheRoot "torch"
$env:VNTEXT_DIRECT_GPU_ROOT = Join-Path $devCacheRoot "gpu"
$systemTempCwd = $safeTempRoot

$Python = $null
$pythonCandidates = @()
if (-not [string]::IsNullOrWhiteSpace($PythonPath)) { $pythonCandidates += [System.IO.Path]::GetFullPath($PythonPath) }
$pythonCandidates += (Join-Path $DevRoot ".dev-env\.venv\Scripts\python.exe")
foreach ($candidate in $pythonCandidates) {
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    $probeExit = 1
    try {
        & $candidate -c "import sys" *> $null
        $probeExit = $LASTEXITCODE
    } catch {
        $probeExit = 1
    }
    if ($probeExit -eq 0) {
        $Python = $candidate
        break
    }
}
if (-not $Python) {
    Write-Error "No usable portable Python runtime. Checked .dev-env/.venv and RELEASE worker/.venv."
}
Write-Host "Python runtime: $Python" -ForegroundColor DarkGray

function Get-Sha256([string]$Path) {
    $stream = [System.IO.File]::OpenRead($Path)
    $digest = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($digest.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        $digest.Dispose()
        $stream.Dispose()
    }
}

function Switch-UpdateFeed([string]$Pending, [string]$Current, [string]$Previous, [bool]$HasStaged, [bool]$HadPrevious) {
    if ($HasStaged) {
        if ($HadPrevious) { [System.IO.File]::Replace($Pending, $Current, $Previous) }
        else { [System.IO.File]::Move($Pending, $Current) }
        return $true
    }
    if ($HadPrevious) {
        [System.IO.File]::Move($Current, $Previous)
        return $true
    }
    return $false
}

function Restore-UpdateFeed([string]$Current, [string]$Previous, [string]$Failed, [bool]$HadPrevious) {
    if ($HadPrevious -and (Test-Path -LiteralPath $Previous -PathType Leaf)) {
        if (Test-Path -LiteralPath $Current -PathType Leaf) {
            [System.IO.File]::Replace($Previous, $Current, $Failed)
            if (Test-Path -LiteralPath $Failed) { Remove-Item -LiteralPath $Failed -Force -ErrorAction Stop }
        } else { [System.IO.File]::Move($Previous, $Current) }
    } elseif (-not $HadPrevious -and (Test-Path -LiteralPath $Current)) {
        Remove-Item -LiteralPath $Current -Force -ErrorAction Stop
    }
}

function Assert-WpfBrandAssets([string]$GeneratedRoot, [string]$SourceRoot) {
    foreach ($relative in @(
        "release\assets\vntext_studio.ico",
        "wpf_app\VNText.Studio.App\Assets\vntext_studio.ico",
        "wpf_app\VNText.Studio.App\Assets\vntext_studio_logo_128.png",
        "wpf_app\VNText.Studio.App\Assets\vntext_studio_logo_256.png"
    )) {
        $generated = Join-Path $GeneratedRoot $relative
        $source = Join-Path $SourceRoot $relative
        if ((Get-Sha256 $generated) -ne (Get-Sha256 $source)) {
            throw "Generated icon differs from tracked source: $relative"
        }
    }
}

function Get-TextSha256([string]$Text) {
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $digest = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($digest.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    } finally {
        $digest.Dispose()
    }
}

$sourceTreeObject = (& git -C $DevRoot rev-parse --verify "$SourceSha^{tree}").Trim()
if ($LASTEXITCODE -ne 0 -or $sourceTreeObject -notmatch '^[0-9a-f]{40}$') {
    throw "Cannot resolve the Git tree for the Release source SHA"
}
$SourceTreeSha256 = Get-TextSha256 ("git-tree-sha1:" + $sourceTreeObject)

function Register-WorkPath([string]$Scope, [string]$Path, [string]$Purpose, [string]$Lifecycle = "DISPOSABLE", [string]$ScopeRoot = $publishArtifactRoot) {
    $register = "import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); from work_paths import register_artifact; register_artifact(artifact_id='publish:'+sys.argv[2]+':'+Path(sys.argv[3]).name,path=Path(sys.argv[3]),kind='release_staging',created_by='release/publish.ps1',owner='release/publish.ps1',purpose=sys.argv[4],lifecycle=sys.argv[5],scope_id=sys.argv[2],run_id=sys.argv[2],scope_root=Path(sys.argv[6]))"
    & $Python -B -c $register $ArtifactHelpersRoot $Scope $Path $Purpose $Lifecycle $ScopeRoot
    if ($LASTEXITCODE -ne 0) { throw "Cannot register write path before use: $Path" }
}

function Read-AppVersion {
    $line = (Get-Content -LiteralPath (Join-Path $DevRoot "VERSION.txt") -TotalCount 1).Trim()
    if (-not $line) { throw "VERSION.txt is empty" }
    return $line
}

function Format-Megabytes([long]$Bytes) {
    return [math]::Round($Bytes / 1MB, 1)
}

function Get-TreeSizeMb([string]$Path) {
    if (-not (Test-Path $Path)) { return 0 }
    $bytes = (Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    return [math]::Round($bytes / 1MB, 1)
}

function Get-TreeSha256([string]$Path) {
    $records = Get-ChildItem -LiteralPath $Path -Recurse -File -Force |
        Sort-Object FullName |
        ForEach-Object {
            $relative = $_.FullName.Substring($Path.Length).TrimStart('\').Replace('\', '/')
            "$relative $((Get-Sha256 $_.FullName))"
        }
    $payload = [System.Text.Encoding]::UTF8.GetBytes(($records -join "`n"))
    $digest = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($digest.ComputeHash($payload))).Replace('-', '').ToLowerInvariant()
    } finally {
        $digest.Dispose()
    }
}

function Invoke-ReleaseExe([string]$ExePath, [string[]]$Arguments, [string]$WorkingDirectory) {
    $proc = Start-Process -FilePath $ExePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -Wait -PassThru -NoNewWindow
    if ($null -eq $proc) { throw "Failed to start: $ExePath $($Arguments -join ' ')" }
    return $proc.ExitCode
}

function Invoke-ReleaseRegressionRunner {
    param(
        [Parameter(Mandatory = $true)] [string]$RunnerPath,
        [Parameter(Mandatory = $true)] [string]$PythonPath,
        [Parameter(Mandatory = $true)] [string]$WorkingDirectory,
        [Parameter(Mandatory = $true)] [string]$LogRoot,
        [Parameter(Mandatory = $true)] [string]$PatternFile,
        [Parameter(Mandatory = $true)] [string]$SourceSha,
        [Parameter(Mandatory = $true)] [string]$Stamp,
        [ValidateRange(1, 3600)] [int]$CleanupTimeoutSeconds = 120
    )
    $runnerStdout = Join-Path $LogRoot ("runner_{0}.stdout.log" -f $Stamp)
    $runnerStderr = Join-Path $LogRoot ("runner_{0}.stderr.log" -f $Stamp)
    $powershellExe = (Get-Command powershell.exe -ErrorAction Stop).Source
    $runnerArgs = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", $RunnerPath,
        "-PythonPath", $PythonPath,
        "-WorkingDirectory", $WorkingDirectory,
        "-LogRoot", $LogRoot,
        "-SourceSha", $SourceSha,
        "-TimeoutSeconds", "900",
        "-CleanupTimeoutSeconds", [string]$CleanupTimeoutSeconds,
        "-PatternFile", $PatternFile
    )
    $startedUtc = [DateTime]::UtcNow
    $runnerProcess = Start-Process `
        -FilePath $powershellExe `
        -ArgumentList $runnerArgs `
        -WorkingDirectory $WorkingDirectory `
        -RedirectStandardOutput $runnerStdout `
        -RedirectStandardError $runnerStderr `
        -WindowStyle Hidden `
        -PassThru
    $runnerFinished = $runnerProcess.WaitForExit(14400000)
    if (-not $runnerFinished) {
        try { $runnerProcess.Kill() } catch { }
        throw "Release regression runner exceeded outer 4-hour timeout"
    }
    $runnerProcess.Refresh()
    $runnerExit = $runnerProcess.ExitCode
    $runnerSummary = Get-ChildItem -LiteralPath $LogRoot -Filter "REGRESSION_COMPLETE.json" -Recurse -File |
        Where-Object { $_.LastWriteTimeUtc -ge $startedUtc.AddSeconds(-1) } |
        Sort-Object LastWriteTime | Select-Object -Last 1
    if (-not $runnerSummary) {
        throw "Release regression runner returned without a fresh REGRESSION_COMPLETE.json; see $runnerStdout and $runnerStderr"
    }
    $runnerSummaryData = Get-Content -LiteralPath $runnerSummary.FullName -Raw | ConvertFrom-Json
    if ($runnerSummaryData.status -ne "PASS" -or $runnerSummaryData.exit_code -ne 0) {
        throw "Release regression summary is not PASS: $($runnerSummary.FullName)"
    }
    # Windows PowerShell 5.1 can expose a null ExitCode for a hidden
    # PowerShell host even after WaitForExit. The runner's JSON contains the
    # authoritative per-Python exit codes; only reject a non-null host code.
    if ($null -ne $runnerExit -and $runnerExit -ne 0) {
        throw "Release regression runner host exit was $runnerExit; see $($runnerSummary.FullName), $runnerStdout and $runnerStderr"
    }
    return [ordered]@{
        summary = $runnerSummary.FullName
        host_exit_code = $runnerExit
        stdout = $runnerStdout
        stderr = $runnerStderr
    }
}

function Copy-RuntimeTree([string]$Src, [string]$Dest, [string[]]$ExtraXd = @()) {
    if (-not (Test-Path $Src)) { throw "Missing runtime path: $Src" }
    if (Test-Path $Dest) { Remove-Item -LiteralPath $Dest -Recurse -Force }
    $xd = @("__pycache__", ".pytest_cache", ".mypy_cache", ".git", "tests") + $ExtraXd
    $xdArg = ($xd | ForEach-Object { "/XD", $_ })
    $null = robocopy $Src $Dest /E /NFL /NDL /NJH /NJS /nc /ns /np /R:2 /W:2 @xdArg /XF *.pyc *.pyo *.log
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $Src" }
}

function Copy-PrivateDotnetRuntime([string]$RuntimeRoot, [string]$HostFxrVersion, [string]$FrameworkVersion, [string]$Destination) {
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $RuntimeRoot "dotnet.exe") -Destination $Destination -Force
    foreach ($name in @("LICENSE.txt", "ThirdPartyNotices.txt")) {
        Copy-Item -LiteralPath (Join-Path $RuntimeRoot $name) -Destination $Destination -Force
    }
    foreach ($relative in @(
        "host\fxr\$HostFxrVersion",
        "shared\Microsoft.NETCore.App\$FrameworkVersion",
        "shared\Microsoft.WindowsDesktop.App\$FrameworkVersion"
    )) {
        $source = Join-Path $RuntimeRoot $relative
        if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Private .NET runtime source missing: $source" }
        $target = Join-Path $Destination $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
    }
}

function Install-RequirementsIfAvailable([string]$PythonPath, [string[]]$RequirementFiles, [bool]$UseExistingOnly = $false) {
    if ($UseExistingOnly) {
        & $PythonPath -B -c "import PIL, UnityPy, ctranslate2, sentencepiece, transformers, huggingface_hub; print('preinstalled Python dependencies PASS')"
        if ($LASTEXITCODE -ne 0) { throw "Required preinstalled Python dependencies are missing; installation is disabled for this task" }
        return
    }
    & $PythonPath -c "import pip" *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Python runtime has no pip; using its pre-provisioned packages." -ForegroundColor DarkYellow
        return
    }
    foreach ($requirementFile in $RequirementFiles) {
        & $PythonPath -m pip install -q -r $requirementFile
        if ($LASTEXITCODE -ne 0) {
            throw "pip install failed: $requirementFile"
        }
    }
}

function Clean-ReleaseArtifacts([string]$Root) {
    Get-ChildItem -LiteralPath $Root -Directory -Filter "__pycache__" -Recurse -Force -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
    foreach ($name in @("app\_work", "_work", "app\worker\_work")) {
        $path = Join-Path $Root $name
        if (Test-Path $path) { Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue }
    }
    Get-ChildItem -LiteralPath $Root -Filter "*.log" -Recurse -File -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }
    foreach ($pattern in @("*.pyc", "*.pyo", "*.pdb")) {
        Get-ChildItem -LiteralPath $Root -Filter $pattern -Recurse -File -ErrorAction SilentlyContinue |
            ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force -ErrorAction SilentlyContinue }
    }
}

function Copy-ProjectNotices([string]$SourceRoot, [string]$AppRoot) {
    $licenseRoot = Join-Path $AppRoot "licenses"
    New-Item -ItemType Directory -Path $licenseRoot -Force | Out-Null
    foreach ($item in @(
        @{ Source = "LICENSE"; Destination = "APACHE-2.0.txt" },
        @{ Source = "NOTICE"; Destination = "NOTICE" },
        @{ Source = "THIRD_PARTY_NOTICES.md"; Destination = "THIRD_PARTY_NOTICES.md" },
        @{ Source = "release\licenses\ctranslate2-MIT.txt"; Destination = "python\ctranslate2-MIT.txt" },
        @{ Source = "release\licenses\sentencepiece-darts_clone.txt"; Destination = "python\sentencepiece-darts_clone.txt" },
        @{ Source = "release\licenses\sentencepiece-esaxx.txt"; Destination = "python\sentencepiece-esaxx.txt" },
        @{ Source = "release\licenses\sentencepiece-protobuf-lite.txt"; Destination = "python\sentencepiece-protobuf-lite.txt" },
        @{ Source = "release\licenses\cudnn-9.10.2-eula.html"; Destination = "native\cudnn-9.10.2-eula.html" },
        @{ Source = "release\licenses\cudnn-9.10.2-acknowledgements.html"; Destination = "native\cudnn-9.10.2-acknowledgements.html" },
        @{ Source = "release\licenses\intel-2025.3-cpp-eula.rtf"; Destination = "native\intel-2025.3-cpp-eula.rtf" },
        @{ Source = "release\licenses\intel-2025.3-customer-terms.txt"; Destination = "native\intel-2025.3-customer-terms.txt" },
        @{ Source = "release\licenses\intel-2025.3-credist.txt"; Destination = "native\intel-2025.3-credist.txt" },
        @{ Source = "release\licenses\intel-2025.3-compiler-third-party-programs.txt"; Destination = "native\intel-2025.3-compiler-third-party-programs.txt" },
        @{ Source = "release\licenses\intel-2025.3-openmp-third-party-programs.txt"; Destination = "native\intel-2025.3-openmp-third-party-programs.txt" },
        @{ Source = "release\licenses\intel-2025.3-tbb-license.txt"; Destination = "native\intel-2025.3-tbb-license.txt" },
        @{ Source = "release\licenses\intel-2025.3-tbb-third-party-programs.txt"; Destination = "native\intel-2025.3-tbb-third-party-programs.txt" }
    )) {
        $source = Join-Path $SourceRoot $item.Source
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Release license source missing: $($item.Source)" }
        $destination = Join-Path $licenseRoot $item.Destination
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination $destination -Force
    }
}

function Write-SetupVersionSource([string]$Path, [string]$Version, [string]$VersionNumeric) {
    if ($Version -notmatch '^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$' -or
        $VersionNumeric -cne (($Version -replace '-.*$', '') + '.0')) {
        throw "Invalid Setup version pair: $Version / $VersionNumeric"
    }
    $attributes = @"
using System.Reflection;
[assembly: AssemblyProduct("VNText Studio")]
[assembly: AssemblyInformationalVersion("$Version")]
[assembly: AssemblyFileVersion("$VersionNumeric")]
[assembly: AssemblyVersion("$VersionNumeric")]
"@
    [System.IO.File]::WriteAllText($Path, $attributes, [System.Text.UTF8Encoding]::new($false))
}

function Assert-SetupVersion([string]$Path, [string]$Version, [string]$VersionNumeric) {
    $info = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($Path)
    $assemblyVersion = [System.Reflection.AssemblyName]::GetAssemblyName($Path).Version.ToString()
    if ($info.ProductVersion -cne $Version -or $info.FileVersion -cne $VersionNumeric -or
        $assemblyVersion -cne $VersionNumeric) {
        throw "Installer version mismatch: $Path (Product=$($info.ProductVersion), File=$($info.FileVersion), Assembly=$assemblyVersion; expected $Version / $VersionNumeric)"
    }
}

function Assert-ReleaseLayout([string]$Root, [string]$RuntimeVersion, [string]$HostFxrVersion) {
    $fmodBinaries = @(Get-ChildItem -LiteralPath $Root -Recurse -File -Force -ErrorAction Stop |
        Where-Object { $_.Name -match '^(lib)?fmod.*\.(dll|dylib|so)(\.\d+)*$' })
    if ($fmodBinaries.Count -gt 0) { throw "RELEASE contains vendor FMOD binaries: $($fmodBinaries.FullName -join ', ')" }
    $names = Get-ChildItem -LiteralPath $Root -Force | Select-Object -ExpandProperty Name
    if ("app" -notin $names) { throw "RELEASE missing required app/ folder" }
    if ("VNText Studio.exe" -notin $names) { throw "RELEASE missing root VNText Studio.exe" }
    $unexpectedRoot = @($names | Where-Object { $_ -notin @("app", "VNText Studio.exe", "Uninstall.exe", "data") })
    if ($unexpectedRoot.Count -gt 0) {
        throw "RELEASE root contains unexpected items: $($unexpectedRoot -join ', ')"
    }
    $app = Join-Path $Root "app"
    foreach ($name in @("VERSION.txt", "RELEASE.json", "MODEL_MANIFEST.json", "worker", "dotnet", "licenses")) {
        if (-not (Test-Path (Join-Path $app $name))) { throw "RELEASE missing app/$name" }
    }
    foreach ($name in @("APACHE-2.0.txt", "NOTICE", "THIRD_PARTY_NOTICES.md", "python\ctranslate2-MIT.txt",
        "python\sentencepiece-darts_clone.txt", "python\sentencepiece-esaxx.txt", "python\sentencepiece-protobuf-lite.txt",
        "native\cudnn-9.10.2-eula.html", "native\cudnn-9.10.2-acknowledgements.html",
        "native\intel-2025.3-cpp-eula.rtf", "native\intel-2025.3-credist.txt",
        "native\intel-2025.3-customer-terms.txt",
        "native\intel-2025.3-compiler-third-party-programs.txt",
        "native\intel-2025.3-openmp-third-party-programs.txt", "native\intel-2025.3-tbb-license.txt",
        "native\intel-2025.3-tbb-third-party-programs.txt")) {
        if (-not (Test-Path (Join-Path $app "licenses\$name") -PathType Leaf)) { throw "RELEASE missing app/licenses/$name" }
    }
    if (Test-Path (Join-Path $app "VNText.Studio.App.dll")) { throw "RELEASE must ship the main WPF app as one root EXE" }
    $privateDotnet = Join-Path $app "dotnet"
    foreach ($path in @(
        "dotnet.exe",
        "host\fxr\$HostFxrVersion\hostfxr.dll",
        "shared\Microsoft.NETCore.App\$RuntimeVersion\coreclr.dll",
        "shared\Microsoft.WindowsDesktop.App\$RuntimeVersion\PresentationFramework.dll"
    )) {
        if (-not (Test-Path (Join-Path $privateDotnet $path))) { throw "RELEASE private .NET runtime missing: app/dotnet/$path" }
    }
    $workerRoot = Join-Path $app "worker"
    foreach ($item in @("vntext", "vntext_worker", "vntext_studio.py", "models", ".venv", "python")) {
        if (-not (Test-Path (Join-Path $workerRoot $item))) { throw "RELEASE worker missing: $item" }
    }
    if (
        (Test-Path (Join-Path $workerRoot "vntext\vinai_experimental.py")) -or
        (Test-Path (Join-Path $workerRoot "models\vinai-translate-en2vi-v2")) -or
        (Test-Path (Join-Path $app "VINAI_MODEL_NOTICE.txt"))
    ) {
        throw "RELEASE contains removed VinAI product files"
    }
    $sitePackages = Join-Path $workerRoot ".venv\Lib\site-packages"
    $torchPackages = @(Get-ChildItem -LiteralPath $sitePackages -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^(torch|torchgen|functorch)([-.]|$)' })
    if ($torchPackages.Count -gt 0) { throw "RELEASE still contains PyTorch packages: $($torchPackages.Name -join ', ')" }
    $modelManifest = Get-Content -LiteralPath (Join-Path $app "MODEL_MANIFEST.json") -Raw | ConvertFrom-Json
    if ($modelManifest.default_model.adapter_id -ne "ct2" -or $modelManifest.experimental_models) {
        throw "RELEASE model manifest must describe CT2 only"
    }
    if (-not (Test-Path (Join-Path $workerRoot "python\Lib\sitecustomize.py"))) {
        throw "RELEASE missing bytecode-suppression runtime hook: worker/python/Lib/sitecustomize.py"
    }
    if (-not (Test-Path (Join-Path $workerRoot "vntext\tools\VNTextPatchInstaller.exe"))) {
        throw "RELEASE missing worker/vntext/tools/VNTextPatchInstaller.exe"
    }
    $pyHome = Join-Path $workerRoot "python\python.exe"
    if (-not (Test-Path $pyHome)) { throw "RELEASE missing bundled worker/python/python.exe" }
    $pyvenv = Join-Path $workerRoot ".venv\pyvenv.cfg"
    if (-not (Test-Path $pyvenv)) { throw "RELEASE missing worker/.venv/pyvenv.cfg" }
    $cfgText = Get-Content -LiteralPath $pyvenv -Raw -ErrorAction Stop
    foreach ($bad in @("Programs\Python", "AppData\Local\Programs\Python", "portable_zip_update", "VNText_Studio_Core")) {
        if ($cfgText -match [regex]::Escape($bad)) {
            throw "RELEASE pyvenv.cfg still references build/system path: $bad"
        }
    }
    if ($cfgText -match "(?m)^\s*executable\s*=" -or $cfgText -match "(?m)^\s*command\s*=") {
        throw "RELEASE pyvenv.cfg must not keep executable/command build lines"
    }
    $expectedPyHome = Join-Path $Root "app\worker\python"
    $neutralPyHome = "__VNText_INSTALL_ROOT__\app\worker\python"
    if ($cfgText -notmatch [regex]::Escape($expectedPyHome) -and $cfgText -notmatch [regex]::Escape($neutralPyHome)) {
        throw "RELEASE pyvenv.cfg home must point at worker/python or use the portable install-root token"
    }
    $forbiddenRoot = @(
        "VNText.Studio.App.exe",
        "vntext",
        "vntext_worker",
        "vntext_studio.py",
        "models",
        ".venv",
        "app.py",
        "tests",
        "qml_ui",
        "mockup",
        "specs",
        "release",
        "wpf_app",
        "_work",
        "__pycache__"
    )
    foreach ($name in $forbiddenRoot) {
        if ($name -in $names) { throw "RELEASE root contains forbidden item: $name" }
    }
    $pdbs = Get-ChildItem -LiteralPath $Root -Filter "*.pdb" -Recurse -File -ErrorAction SilentlyContinue
    if ($pdbs) { throw "RELEASE contains PDB debug files" }
    foreach ($pattern in @("*.pyc", "*.pyo", "*.log")) {
        $leftovers = Get-ChildItem -LiteralPath $Root -Filter $pattern -Recurse -File -ErrorAction SilentlyContinue
        if ($leftovers) { throw "RELEASE contains forbidden runtime artifacts ($pattern)" }
    }
    $cacheDirs = Get-ChildItem -LiteralPath $Root -Directory -Filter "__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
    if ($cacheDirs) { throw "RELEASE contains forbidden __pycache__ directories" }
}

if ($RequireIsolatedArtifacts) {
    $modelTarget = Join-Path $devDataRoot "models\opus-mt-en-vi-int8"
    if (-not (Test-Path -LiteralPath (Join-Path $ModelRoot "model.bin"))) { throw "Offline preflight model missing: $ModelRoot" }
    if (-not (Test-Path -LiteralPath (Join-Path $modelTarget "model.bin"))) { Copy-RuntimeTree $ModelRoot $modelTarget }
}

Write-Host "`n[0/5] DEV release_verify (pre-build gate)..." -ForegroundColor Yellow
$preflightRunRoot = Join-Path $publishArtifactRoot "release_verify"
$preflightReport = Join-Path $WorkRoot ($publishScope + "-release_verify.json")
Register-WorkPath $publishScope $publishArtifactRoot "isolated Setup publish and preflight run scope" "DISPOSABLE" $publishArtifactRoot
Register-WorkPath ($publishScope + "-verify") $preflightRunRoot "isolated release_verify run scope" "DISPOSABLE" $publishArtifactRoot
Register-WorkPath ($publishScope + "-verify") $preflightReport "retained release_verify preflight evidence" "RETAINED" $WorkRoot
$verifyEnvNames = @("VNTEXT_RELEASE_VERIFY_RUN_ROOT", "VNTEXT_ARTIFACT_SCOPE_ROOT", "VNTEXT_DEV_RUN_ROOT", "VNTEXT_WORK_ARTIFACTS_ROOT")
$verifyEnvPrevious = @{}
foreach ($name in $verifyEnvNames) { $verifyEnvPrevious[$name] = [Environment]::GetEnvironmentVariable($name, "Process") }
$env:VNTEXT_RELEASE_VERIFY_RUN_ROOT = $preflightRunRoot
$env:VNTEXT_ARTIFACT_SCOPE_ROOT = $publishArtifactRoot
$env:VNTEXT_DEV_RUN_ROOT = $DevRunRoot
$env:VNTEXT_WORK_ARTIFACTS_ROOT = $preflightRunRoot
$preflightCode = 1
try {
    $savedUserProfile = $env:USERPROFILE
    try {
        $env:USERPROFILE = Join-Path $DevRunRoot "Profile"
        & $Python -B -c "from vntext.release_verify import run_release_verify; raise SystemExit(run_release_verify())" --report $preflightReport
        $preflightCode = $LASTEXITCODE
    } finally {
        $env:USERPROFILE = $savedUserProfile
    }
} finally {
    $cleanupScript = "import sys; from pathlib import Path; sys.path.insert(0,sys.argv[2]); sys.path.insert(0,sys.argv[1]); from cleanup_work_artifacts import cleanup_after_test; report=cleanup_after_test([Path(sys.argv[4])],reason='release/publish.ps1 preflight',outcome=sys.argv[5],scope_id=sys.argv[3],run_id=sys.argv[3]); print(report); raise SystemExit(0 if report.get('ok') else 1)"
    $preflightOutcome = if ($preflightCode -eq 0) { "PASS" } else { "FAIL" }
    & $Python -B -c $cleanupScript (Join-Path $ArtifactHelpersRoot "..\tools") $ArtifactHelpersRoot ($publishScope + "-verify") $preflightRunRoot $preflightOutcome
    if ($LASTEXITCODE -ne 0) { throw "Preflight artifact cleanup did not complete; preserve fail-closed status" }
    foreach ($name in $verifyEnvNames) { [Environment]::SetEnvironmentVariable($name, $verifyEnvPrevious[$name], "Process") }
}
if ($preflightCode -ne 0) { throw "DEV release_verify failed - abort publish (exit $preflightCode)" }
$env:VNTEXT_ARTIFACT_SCOPE_ID = $publishScope
$env:VNTEXT_ARTIFACT_RUN_ID = $publishScope
$env:VNTEXT_ARTIFACT_SCOPE_ROOT = $publishArtifactRoot
Write-Host "DEV release_verify PASS" -ForegroundColor Green

$setupReleasePath = Join-Path $ReleaseRoot "Setup.exe"

Write-Host "=== VNText Studio publish ===" -ForegroundColor Cyan
Write-Host "DEV:     $DevRoot"
Write-Host "RELEASE: $ReleaseRoot"

if (-not $SkipTests) {
    Write-Host "`n[1/5] Regression tests..." -ForegroundColor Yellow
    Install-RequirementsIfAvailable $Python @(
        (Join-Path $DevRoot "requirements.txt")
    ) ([bool]$UsePreinstalledDependencies)
    $regressionRunner = Join-Path $DevRoot "release\run_regression.ps1"
    if (-not (Test-Path -LiteralPath $regressionRunner -PathType Leaf)) {
        throw "Regression runner missing: $regressionRunner"
    }
    $regressionLogRoot = Join-Path $DevRoot "RELEASE_RUN\release_gate"
    New-Item -ItemType Directory -Path $regressionLogRoot -Force | Out-Null

    $traceabilityPatternFile = Join-Path $regressionLogRoot ("patterns_traceability_{0}.txt" -f $SourceSha)
    [System.IO.File]::WriteAllLines($traceabilityPatternFile, @("test_traceability.py"))
    $traceabilityStamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
    Write-Host "Starting traceability preflight runner: $traceabilityStamp"
    $traceabilityRun = Invoke-ReleaseRegressionRunner `
        -RunnerPath $regressionRunner `
        -PythonPath $Python `
        -WorkingDirectory $DevRoot `
        -LogRoot $regressionLogRoot `
        -PatternFile $traceabilityPatternFile `
        -SourceSha $SourceSha `
        -Stamp ("{0}_traceability" -f $traceabilityStamp) `
        -CleanupTimeoutSeconds $CleanupTimeoutSeconds
    Write-Host "Traceability preflight summary: $($traceabilityRun.summary)"

    $testPatterns = @(
        "test_ui_progress.py",
        "test_mt_structural.py", "test_freeze_hashes.py",
        "test_runtime_paths.py", "test_wpf_workflow.py",
        "test_patch_preflight.py",
        "test_mt_patch_gate_write.py", "test_csv_editor_api.py",
        "test_package_technical_filter.py", "test_user_glossary.py",
        "test_patch_installer.py",
        "test_patch_readback.py",
        "test_mt_classify.py", "test_translation_cache.py",
        "test_glossary_context_v2.py", "test_worker_protocol.py", "test_worker_translate.py",
        "test_setup_package.py", "test_release_regression_runner.py"
    )
    $patternFile = Join-Path $regressionLogRoot ("patterns_main_{0}.txt" -f $SourceSha)
    [System.IO.File]::WriteAllLines($patternFile, $testPatterns)
    $runnerStamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
    Write-Host "Starting main isolated regression runner: $runnerStamp"
    $mainRegressionRun = Invoke-ReleaseRegressionRunner `
        -RunnerPath $regressionRunner `
        -PythonPath $Python `
        -WorkingDirectory $DevRoot `
        -LogRoot $regressionLogRoot `
        -PatternFile $patternFile `
        -SourceSha $SourceSha `
        -Stamp ("{0}_main" -f $runnerStamp) `
        -CleanupTimeoutSeconds $CleanupTimeoutSeconds
    Write-Host "Main regression summary: $($mainRegressionRun.summary)"
    Write-Host "Regression PASS" -ForegroundColor Green
} else {
    Write-Host "`n[1/5] Regression skipped (-SkipTests)" -ForegroundColor DarkYellow
}

$wpfPublish = Join-Path $DevRunRoot "wpf_publish"
$wpfBuiltExe = Join-Path $wpfPublish "VNText.Studio.App.exe"
$wpfUpdatePublish = Join-Path $publishArtifactRoot "wpf_update_publish"
$dotnetRuntimeRoot = Join-Path $DevRunRoot "_dotnet"
$dotnetSdkRoot = Join-Path $DevRoot ".dev-env\dotnet-sdk-10"
$dotnet = Join-Path $dotnetSdkRoot "dotnet.exe"
$dotnetAppData = Join-Path $dotnetRuntimeRoot "appdata"
$dotnetLocalAppData = Join-Path $dotnetRuntimeRoot "localappdata"
$dotnetCliHome = Join-Path $dotnetRuntimeRoot "cli_home"
$nugetConfig = Join-Path $dotnetRuntimeRoot "NuGet.Config"
$nugetPackages = Join-Path $dotnetRuntimeRoot "packages"
$dotnetLayoutTargets = Join-Path $dotnetRuntimeRoot "layout-proof.targets"
$globalDotnetRoot = @(
    (Join-Path $env:ProgramFiles "dotnet"),
    (Join-Path ${env:ProgramFiles(x86)} "dotnet")
) | Where-Object { Test-Path (Join-Path $_ "shared\Microsoft.NETCore.App") } | Select-Object -First 1
if (-not $globalDotnetRoot) { throw "Installed .NET 8 runtime source was not found under Program Files" }
$frameworkCandidates = @(Get-ChildItem -LiteralPath (Join-Path $globalDotnetRoot "shared\Microsoft.NETCore.App") -Directory |
    Where-Object {
        $_.Name -match '^8\.' -and
        (Test-Path (Join-Path $globalDotnetRoot "shared\Microsoft.WindowsDesktop.App\$($_.Name)\PresentationFramework.dll")) -and
        (Test-Path (Join-Path $globalDotnetRoot "packs\Microsoft.NETCore.App.Ref\$($_.Name)")) -and
        (Test-Path (Join-Path $globalDotnetRoot "packs\Microsoft.WindowsDesktop.App.Ref\$($_.Name)"))
    } | Sort-Object { [version]$_.Name } -Descending)
if ($frameworkCandidates.Count -eq 0) { throw "Matching .NET 8 core/WPF runtimes and reference packs were not found" }
$frameworkRuntimeVersion = $frameworkCandidates[0].Name
$hostFxrCandidates = @(Get-ChildItem -LiteralPath (Join-Path $globalDotnetRoot "host\fxr") -Directory |
    Where-Object { $_.Name -match '^8\.' } | Sort-Object { [version]$_.Name } -Descending)
if ($hostFxrCandidates.Count -eq 0) { throw "Installed .NET 8 hostfxr was not found" }
$hostFxrVersion = $hostFxrCandidates[0].Name
$sdkVersions = @(Get-ChildItem -LiteralPath (Join-Path $dotnetSdkRoot "sdk") -Directory | Where-Object { $_.Name -match '^10\.' } | Sort-Object { [version]$_.Name } -Descending)
$appHostVersions = @(Get-ChildItem -LiteralPath (Join-Path $dotnetSdkRoot "packs\Microsoft.NETCore.App.Host.win-x64") -Directory | Where-Object { $_.Name -match '^10\.' } | Sort-Object { [version]$_.Name } -Descending)
if (-not (Test-Path -LiteralPath $dotnet) -or $sdkVersions.Count -eq 0 -or $appHostVersions.Count -eq 0) {
    throw "The approved local .NET 10 SDK is incomplete at $dotnetSdkRoot"
}
$appHostPackVersion = $appHostVersions[0].Name

if (-not $SkipBuild) {
    $buildTemp = Join-Path $dotnetRuntimeRoot "temp"
    $pipCache = Join-Path $DevRunRoot "_pip_cache"
    foreach ($path in @($buildTemp, $pipCache)) { New-Item -ItemType Directory -Path $path -Force | Out-Null }
    $env:TEMP = $buildTemp
    $env:TMP = $buildTemp
    $env:TMPDIR = $buildTemp
    $env:PIP_CACHE_DIR = $pipCache
    Write-Host "`n[2/5] Install build deps..." -ForegroundColor Yellow
    $buildRequirementFiles = @(
        (Join-Path $DevRoot "requirements.txt"),
        (Join-Path $DevRoot "release\requirements-build.txt")
    )
    Install-RequirementsIfAvailable $Python $buildRequirementFiles ([bool]$UsePreinstalledDependencies)
    & $Python -c "import UnityPy, ctranslate2; from transformers import MarianTokenizer; print('CT2 worker dependencies PASS')"
    if ($LASTEXITCODE -ne 0) { throw "CT2 worker dependencies missing (UnityPy/ctranslate2/Transformers)" }

    if ($BuildLegacy) {
        Write-Host "`n[2b] Legacy PyInstaller (DEV only)..." -ForegroundColor DarkYellow
        & $Python -B (Join-Path $DevRoot "release\make_icon.py") --output-root (Join-Path $DevRunRoot "_work\make_icon")
        $distDir = Join-Path $DevRunRoot "legacy_dist"
        $workDir = Join-Path $DevRunRoot "legacy_build"
        if (Test-Path $distDir) { Remove-Item -LiteralPath $distDir -Recurse -Force }
        & $Python -m PyInstaller (Join-Path $DevRoot "release\vntext_studio.spec") `
            --distpath $distDir --workpath $workDir --noconfirm
        if (-not (Test-Path (Join-Path $distDir "VNText Studio.exe"))) { throw "Legacy build failed" }
    }

    Write-Host "`n[3/5] Build WPF app..." -ForegroundColor Yellow
    # Keep SDK, NuGet and profile writes inside DEV_RUN; use existing offline
    # .NET 8 packs to build the framework-dependent .NET 8 WPF app.
    foreach ($path in @($dotnetAppData, $dotnetLocalAppData, $dotnetCliHome)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
    New-Item -ItemType Directory -Path $nugetPackages -Force | Out-Null
    foreach ($pack in @("Microsoft.NETCore.App.Ref", "Microsoft.WindowsDesktop.App.Ref", "Microsoft.AspNetCore.App.Ref")) {
        $source = Join-Path $globalDotnetRoot "packs\$pack\$frameworkRuntimeVersion"
        $target = Join-Path $dotnetSdkRoot "packs\$pack\$frameworkRuntimeVersion"
        if (-not (Test-Path -LiteralPath $target -PathType Container)) {
            if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Offline targeting pack missing: $source" }
            New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
            Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
        }
    }
    $globalNugetPackages = Join-Path $env:USERPROFILE ".nuget\packages"
    foreach ($package in @("microsoft.netcore.app.runtime.win-x64", "microsoft.windowsdesktop.app.runtime.win-x64", "microsoft.aspnetcore.app.runtime.win-x64")) {
        $source = Join-Path $globalNugetPackages "$package\$frameworkRuntimeVersion"
        $target = Join-Path $nugetPackages "$package\$frameworkRuntimeVersion"
        if (-not (Test-Path -LiteralPath $target -PathType Container)) {
            if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Offline NuGet runtime pack missing: $source" }
            New-Item -ItemType Directory -Path (Split-Path -Parent $target) -Force | Out-Null
            Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
        }
    }
    @"
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
  </packageSources>
</configuration>
"@ | Set-Content -LiteralPath $nugetConfig -Encoding utf8
    $env:APPDATA = $dotnetAppData
    $env:LOCALAPPDATA = $dotnetLocalAppData
    $env:DOTNET_CLI_HOME = $dotnetCliHome
    $env:DOTNET_ROOT = $dotnetSdkRoot
    $env:DOTNET_ROOT_X64 = $dotnetSdkRoot
    $env:DOTNET_SKIP_FIRST_TIME_EXPERIENCE = "1"
    $env:DOTNET_CLI_TELEMETRY_OPTOUT = "1"
    $env:NUGET_PACKAGES = $nugetPackages
    $targets = @"
<Project>
  <ItemGroup>
    <KnownFrameworkReference Update="Microsoft.NETCore.App" TargetingPackVersion="$frameworkRuntimeVersion" LatestRuntimeFrameworkVersion="$frameworkRuntimeVersion" />
    <KnownFrameworkReference Update="Microsoft.AspNetCore.App" TargetingPackVersion="$frameworkRuntimeVersion" LatestRuntimeFrameworkVersion="$frameworkRuntimeVersion" />
    <KnownFrameworkReference Update="Microsoft.WindowsDesktop.App" TargetingPackVersion="$frameworkRuntimeVersion" LatestRuntimeFrameworkVersion="$frameworkRuntimeVersion" />
    <KnownFrameworkReference Update="Microsoft.WindowsDesktop.App.WPF" TargetingPackVersion="$frameworkRuntimeVersion" LatestRuntimeFrameworkVersion="$frameworkRuntimeVersion" />
    <KnownFrameworkReference Update="Microsoft.WindowsDesktop.App.WindowsForms" TargetingPackVersion="$frameworkRuntimeVersion" LatestRuntimeFrameworkVersion="$frameworkRuntimeVersion" />
    <KnownAppHostPack Update="Microsoft.NETCore.App" AppHostPackVersion="$appHostPackVersion" />
  </ItemGroup>
</Project>
"@
    Set-Content -LiteralPath $dotnetLayoutTargets -Value $targets -Encoding utf8
    $targetsArg = "-p:DirectoryBuildTargetsPath=$dotnetLayoutTargets"
    if (-not $SkipIconGeneration) {
        $iconOutputRoot = Join-Path $DevRunRoot "_work\make_icon"
        & $Python -B (Join-Path $DevRoot "release\make_icon.py") --output-root $iconOutputRoot
        if ($LASTEXITCODE -ne 0) { throw "make_icon.py failed" }
        Assert-WpfBrandAssets $iconOutputRoot $DevRoot
    }
    $wpfProj = Join-Path $DevRoot "wpf_app\VNText.Studio.App\VNText.Studio.App.csproj"
    $wpfObj = Join-Path $DevRunRoot "obj\VNText.Studio.App"
    New-Item -ItemType Directory -Path $wpfObj -Force | Out-Null
    $wpfObjArg = "-p:BaseIntermediateOutputPath=$wpfObj\"
    $wpfExtensionsArg = "-p:MSBuildProjectExtensionsPath=$wpfObj\"
    $wpfOutputArg = "-p:OutputPath=$(Join-Path $DevRunRoot 'obj\VNText.Studio.App\bin\Release\net8.0-windows\win-x64')\"
    $version = Read-AppVersion
    $versionNumeric = "{0}.0" -f ($version -replace '-.*$', '')
    $devSmokeRoot = Join-Path $publishArtifactRoot "dev-smoke"
    $devSmokeOut = Join-Path $devSmokeRoot "out"
    $devAppExe = Join-Path $devSmokeOut "VNText.Studio.App.exe"
    $devTemp = Join-Path $devSmokeRoot "temp"
    $devData = Join-Path $devSmokeRoot "localappdata"
    $devWork = Join-Path $devSmokeRoot "work"
    Register-WorkPath $publishScope $devSmokeRoot "isolated WPF DEV build and worker smoke output" "DISPOSABLE" $publishArtifactRoot
    & $dotnet clean $wpfProj -c Release $targetsArg $wpfObjArg $wpfExtensionsArg $wpfOutputArg | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "WPF clean failed" }
    & $dotnet restore $wpfProj -r win-x64 --configfile $nugetConfig --ignore-failed-sources $targetsArg $wpfObjArg $wpfExtensionsArg $wpfOutputArg
    if ($LASTEXITCODE -ne 0) { throw "WPF offline restore failed" }
    if (Test-Path $wpfPublish) { Remove-Item -LiteralPath $wpfPublish -Recurse -Force }
    $devSmokeOutcome = "FAIL"
    $oldDevSmokeEnv = @{}
    try {
        & $dotnet build $wpfProj `
        -c Release -r win-x64 --no-restore `
        -p:SelfContained=false `
        -p:PublishSelfContained=false `
        $targetsArg `
        $wpfObjArg $wpfExtensionsArg $wpfOutputArg `
        -o $devSmokeOut
        if ($LASTEXITCODE -ne 0) { throw "WPF isolated DEV smoke build failed" }
        if (-not (Test-Path -LiteralPath $devAppExe)) { throw "Isolated WPF apphost missing: $devAppExe" }
        foreach ($path in @($devTemp, $devData, $devWork)) { New-Item -ItemType Directory -Path $path -Force | Out-Null }
        $devSmokeEnv = @{
            DOTNET_ROOT = $globalDotnetRoot; DOTNET_ROOT_X64 = $globalDotnetRoot
            VNTEXT_WORKER_CWD = $DevRoot; VNTEXT_WORKER_PYTHON = $Python
            VNTEXT_WORK_ARTIFACTS_ROOT = $devWork; VNTEXT_LOCALAPPDATA = $devData
            VNTEXT_ARTIFACT_SCOPE_ID = $publishScope; VNTEXT_ARTIFACT_RUN_ID = $publishScope
            VNTEXT_ARTIFACT_SCOPE_ROOT = $devSmokeRoot; VNTEXT_DEV_RUN_ROOT = $DevRunRoot
            APPDATA = $devData; LOCALAPPDATA = $devData
            TEMP = $devTemp; TMP = $devTemp; TMPDIR = $devTemp
        }
        foreach ($name in $devSmokeEnv.Keys) {
            $oldDevSmokeEnv[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
            [Environment]::SetEnvironmentVariable($name, $devSmokeEnv[$name], "Process")
        }
        $devSmoke = Invoke-ReleaseExe -ExePath $devAppExe -Arguments @("--smoke-worker") -WorkingDirectory $DevRoot
        if ($devSmoke -ne 0) { throw "DEV_RUN --smoke-worker failed (exit $devSmoke)" }
        $devSmokeOutcome = "PASS"
    } finally {
        foreach ($name in $oldDevSmokeEnv.Keys) {
            [Environment]::SetEnvironmentVariable($name, $oldDevSmokeEnv[$name], "Process")
        }
        $cleanupScript = "import sys; from pathlib import Path; sys.path.insert(0,sys.argv[2]); sys.path.insert(0,sys.argv[1]); from cleanup_work_artifacts import cleanup_after_test; report=cleanup_after_test([Path(sys.argv[4])],reason='release/publish.ps1 WPF DEV smoke',outcome=sys.argv[5],scope_id=sys.argv[3],run_id=sys.argv[3]); print(report); raise SystemExit(0 if report.get('ok') else 1)"
        & $Python -B -c $cleanupScript (Join-Path $ArtifactHelpersRoot "..\tools") $ArtifactHelpersRoot $publishScope $devSmokeRoot $devSmokeOutcome
        if ($LASTEXITCODE -ne 0) { throw "WPF DEV smoke artifact cleanup did not complete; preserve fail-closed status" }
    }
    Write-Host "Built and smoke-tested isolated DEV app: $devAppExe" -ForegroundColor Green
    & $dotnet publish $wpfProj `
        -c Release -r win-x64 --self-contained false --no-restore `
        -p:Version=$version `
        -p:InformationalVersion=$version `
        -p:IncludeSourceRevisionInInformationalVersion=false `
        -p:AssemblyVersion=$versionNumeric `
        -p:FileVersion=$versionNumeric `
        -p:PublishSingleFile=true `
        -p:AppHostRelativeDotNet=app/dotnet `
        -p:IncludeNativeLibrariesForSelfExtract=false `
        $targetsArg `
        $wpfObjArg $wpfExtensionsArg $wpfOutputArg `
        -o $wpfPublish
    if ($LASTEXITCODE -ne 0) { throw "WPF dotnet publish failed" }
    if (-not (Test-Path $wpfBuiltExe)) { throw "WPF build missing: $wpfBuiltExe" }
    Write-Host "Built WPF: $wpfBuiltExe" -ForegroundColor Green
    if (-not $SkipWpfUpdatePackage) {
        Write-Host "Build WPF Updates candidate $WpfUpdateVersion..." -ForegroundColor Yellow
        if (Test-Path -LiteralPath $wpfUpdatePublish) { Remove-Item -LiteralPath $wpfUpdatePublish -Recurse -Force }
        & $dotnet publish $wpfProj `
            -c Release -r win-x64 --self-contained false --no-restore `
            -p:Version=$WpfUpdateVersion `
            -p:InformationalVersion=$WpfUpdateVersion `
            -p:IncludeSourceRevisionInInformationalVersion=false `
            -p:AssemblyVersion=$WpfUpdateVersionNumeric `
            -p:FileVersion=$WpfUpdateVersionNumeric `
            -p:PublishSingleFile=true `
            -p:AppHostRelativeDotNet=app/dotnet `
            -p:IncludeNativeLibrariesForSelfExtract=false `
            $targetsArg `
            $wpfObjArg $wpfExtensionsArg $wpfOutputArg `
            -o $wpfUpdatePublish
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $wpfUpdatePublish "VNText.Studio.App.exe"))) {
            throw "WPF Updates candidate publish failed: $WpfUpdateVersion"
        }
        $wpfUpdateExe = Join-Path $wpfUpdatePublish "VNText.Studio.App.exe"
        $wpfUpdateProductVersion = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($wpfUpdateExe).ProductVersion
        if ($null -ne $wpfUpdateProductVersion) { $wpfUpdateProductVersion = $wpfUpdateProductVersion.Split('+', 2)[0].Trim() }
        if ($wpfUpdateProductVersion -ne $WpfUpdateVersion) {
            throw "WPF Updates candidate executable version mismatch: expected $WpfUpdateVersion, found '$wpfUpdateProductVersion'."
        }
        Write-Host "Built WPF Updates candidate: $wpfUpdatePublish" -ForegroundColor Green
    }
    Write-Host "`n[3b/5] Build patch installer..." -ForegroundColor Yellow
    $installerProj = Join-Path $DevRoot "wpf_app\VNText.PatchInstaller\VNText.PatchInstaller.csproj"
    $installerPublish = Join-Path $DevRunRoot "patch_installer_publish"
    $installerObj = Join-Path $DevRunRoot "obj\VNText.PatchInstaller"
    New-Item -ItemType Directory -Path $installerObj -Force | Out-Null
    $installerObjArg = "-p:BaseIntermediateOutputPath=$installerObj\"
    $installerExtensionsArg = "-p:MSBuildProjectExtensionsPath=$installerObj\"
    $installerOutputArg = "-p:OutputPath=$(Join-Path $DevRunRoot 'obj\VNText.PatchInstaller\bin\Release\net8.0-windows\win-x64')\"
    $installerBuiltExe = Join-Path $installerPublish "VNTextPatchInstaller.exe"
    if (Test-Path $installerPublish) { Remove-Item -LiteralPath $installerPublish -Recurse -Force }
    & $dotnet restore $installerProj -r win-x64 --configfile $nugetConfig --ignore-failed-sources $targetsArg $installerObjArg $installerExtensionsArg $installerOutputArg
    if ($LASTEXITCODE -ne 0) { throw "Patch installer restore failed" }
    & $dotnet publish $installerProj `
        -c Release -r win-x64 --self-contained false `
        -p:PublishSingleFile=true `
        -p:PublishTrimmed=false $targetsArg $installerObjArg $installerExtensionsArg $installerOutputArg --no-restore -o $installerPublish
    if ($LASTEXITCODE -ne 0) { throw "Patch installer publish failed" }
    if (-not (Test-Path $installerBuiltExe)) { throw "Patch installer missing: $installerBuiltExe" }
    Write-Host "Built installer: $installerBuiltExe" -ForegroundColor Green
} else {
    Write-Host "`n[2-3/5] Build skipped (-SkipBuild)" -ForegroundColor DarkYellow
    if (-not (Test-Path $wpfBuiltExe)) { throw "No WPF publish at $wpfBuiltExe" }
    $installerPublish = Join-Path $DevRunRoot "patch_installer_publish"
    $installerBuiltExe = Join-Path $installerPublish "VNTextPatchInstaller.exe"
    if (-not (Test-Path $installerBuiltExe)) { throw "No patch installer publish at $installerBuiltExe" }
}

Write-Host "`n[4/5] Clean deploy to RELEASE..." -ForegroundColor Yellow
$version = Read-AppVersion
$staging = Join-Path $publishArtifactRoot "stage"

$workRoot = $publishArtifactRoot
$updatesStaging = Join-Path $workRoot "Updates"
$payloadZip = Join-Path $workRoot ((Split-Path -Leaf $staging) + ".zip")
$setupExe = Join-Path $workRoot ((Split-Path -Leaf $staging) + "-Setup.exe")
$pendingSetup = Join-Path $ReleaseRoot "Setup.pending.exe"
$previousSetup = Join-Path $ReleaseRoot "Setup.previous.exe"
$failedSetup = Join-Path $ReleaseRoot "Setup.failed.exe"
$pendingPackage = $null
$pendingFullAppPackage = $null
$pendingUpdateFeed = $null
$pendingFullAppFeed = $null
$currentUpdateFeed = $null
$currentFullAppFeed = $null
$previousUpdateFeed = $null
$previousFullAppFeed = $null
$failedUpdateFeed = $null
$failedFullAppFeed = $null
$updateFeedCommitted = $false
$fullAppFeedCommitted = $false
$hadPreviousUpdateFeed = $false
$hadPreviousFullAppFeed = $false
$registerScript = "import sys; sys.path.insert(0,sys.argv[1]); from pathlib import Path; from work_paths import register_artifacts; scope=sys.argv[2]; base=Path(sys.argv[3]); paths=[Path(p) for p in sys.argv[4:]]; register_artifacts([dict(artifact_id='setup-publish:'+scope+':'+str(i),path=p,kind='release_staging',created_by='release/publish.ps1',owner='release/publish.ps1',purpose='staged Setup, package and install transaction paths',lifecycle='DISPOSABLE',scope_id=scope,run_id=scope,scope_root=base) for i,p in enumerate(paths)])"
& $Python -B -c $registerScript $ArtifactHelpersRoot $publishScope $workRoot $staging $payloadZip $setupExe $wpfUpdatePublish $updatesStaging
if ($LASTEXITCODE -ne 0) { throw "Cannot register portable Setup staging scope" }
$stagingApp = Join-Path $staging "app"
New-Item -ItemType Directory -Path (Join-Path $stagingApp "worker") -Force | Out-Null
Copy-ProjectNotices $DevRoot $stagingApp
Copy-PrivateDotnetRuntime $globalDotnetRoot $hostFxrVersion $frameworkRuntimeVersion (Join-Path $stagingApp "dotnet")

Get-ChildItem -LiteralPath $wpfPublish -Force | Where-Object { $_.Extension -ne ".pdb" } | ForEach-Object {
    $destination = if ($_.Name -eq "VNText.Studio.App.exe") {
        Join-Path $staging "VNText Studio.exe"
    } else {
        Join-Path $stagingApp $_.Name
    }
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force
}
$wpfStagingExe = Join-Path $staging "VNText Studio.exe"
if (-not (Test-Path $wpfStagingExe)) { throw "WPF staging exe missing" }

$stagingWorker = Join-Path $stagingApp "worker"
Copy-RuntimeTree (Join-Path $DevRoot "vntext") (Join-Path $stagingWorker "vntext") @("_legacy")
Copy-RuntimeTree (Join-Path $DevRoot "vntext_worker") (Join-Path $stagingWorker "vntext_worker")
$installerDest = Join-Path $stagingWorker "vntext\tools\VNTextPatchInstaller.exe"
New-Item -ItemType Directory -Path (Split-Path -Parent $installerDest) -Force | Out-Null
Copy-Item -LiteralPath $installerBuiltExe -Destination $installerDest -Force
$studioPy = Join-Path $DevRoot "vntext_studio.py"
Copy-Item -LiteralPath $studioPy -Destination (Join-Path $stagingWorker "vntext_studio.py") -Force
$stagingWorkerEscaped = $stagingWorker.Replace("'", "''")
& $Python -c "import sys; sys.path.insert(0, r'$stagingWorkerEscaped'); import vntext_studio; assert str(vntext_studio.VERSION) == r'$version'"
if ($LASTEXITCODE -ne 0) { throw "worker/vntext_studio.py VERSION mismatch (expected $version)" }
$modelRevision = (& $Python -c "import sys; sys.path.insert(0, r'$stagingWorkerEscaped'); from vntext.mt_ct2_constants import MODEL_REVISION; print(MODEL_REVISION)").Trim()
if ($LASTEXITCODE -ne 0 -or $modelRevision -notmatch '^[0-9a-f]{40}$') {
    throw "Could not resolve the pinned CT2 model revision from staged source."
}
$modelSrc = $ModelRoot
$modelDest = Join-Path $stagingWorker "models\opus-mt-en-vi-int8"
Copy-RuntimeTree $modelSrc $modelDest
if (-not (Test-Path (Join-Path $modelDest "model.bin"))) { throw "Release model.bin missing" }

Write-Host "Write model provenance manifest..." -ForegroundColor Yellow
$modelManifest = [ordered]@{
    schema_version = 1
    generated_from_source_sha = $SourceSha
    default_model = [ordered]@{
        adapter_id = "ct2"
        model_id = "opus-mt-en-vi-ct2-int8"
        repository = "dekthedev/opus-mt-en-vi-ct2-int8"
        revision = $modelRevision
        engine = "CTranslate2"
        quantization = "int8"
        source_model = "Helsinki-NLP/opus-mt-en-vi"
        license = "Apache-2.0"
        distribution = "bundled"
        path = "worker/models/opus-mt-en-vi-int8"
    }
}
[System.IO.File]::WriteAllText(
    (Join-Path $stagingApp "MODEL_MANIFEST.json"),
    ($modelManifest | ConvertTo-Json -Depth 6),
    (New-Object System.Text.UTF8Encoding $false)
)

Write-Host "Copy portable Python venv (worker runtime)..." -ForegroundColor Yellow
$venvSrc = $WorkerVenvRoot
$venvDest = Join-Path $stagingWorker ".venv"
$null = robocopy $venvSrc $venvDest /E /NFL /NDL /NJH /NJS /nc /ns /np /R:2 /W:2 `
    /XD __pycache__ .pytest_cache .mypy_cache torchaudio torchvision stanza spacy `
         PySide6 shiboken6 onnxruntime argostranslate pytest test tests `
    /XF *.pyc *.pyo *.log
if ($LASTEXITCODE -ge 8) { throw "robocopy .venv failed" }
if (-not (Test-Path (Join-Path $venvDest "Scripts\python.exe"))) { throw "Release .venv python.exe missing" }

# DEV .dev-env/.venv may be created with --system-site-packages.  Robocopy only sees
# the venv-local directory, so copy missing packages from the configured base
# site-packages before pruning; otherwise the portable Release silently loses
# UnityPy/CT2 imports while still passing the DEV interpreter probe.
$systemSite = (& $Python -c "import site; print(site.getsitepackages()[-1])").Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($systemSite)) {
    throw "Cannot resolve Python system site-packages for Release venv"
}
$releaseSite = Join-Path $venvDest "Lib\site-packages"
New-Item -ItemType Directory -Path $releaseSite -Force | Out-Null
$releaseSiteFull = [System.IO.Path]::GetFullPath($releaseSite)
$systemSiteFull = [System.IO.Path]::GetFullPath($systemSite)
if ($releaseSiteFull -ne $systemSiteFull) {
    Write-Host "Merge system site-packages: $systemSiteFull" -ForegroundColor DarkGray
    Get-ChildItem -LiteralPath $systemSiteFull -Force | ForEach-Object {
        $destination = Join-Path $releaseSite $_.Name
        if (-not (Test-Path -LiteralPath $destination)) {
            Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force
        }
    }
}
Get-ChildItem -LiteralPath $releaseSite -Recurse -Directory -Filter "__pycache__" -Force |
    Sort-Object FullName -Descending |
    Remove-Item -Recurse -Force -ErrorAction Stop
Get-ChildItem -LiteralPath $releaseSite -Recurse -File -Force |
    Where-Object { $_.Extension -in @(".pyc", ".pyo", ".log") } |
    Remove-Item -Force -ErrorAction Stop

Write-Host "Prune worker venv..." -ForegroundColor Yellow
& $Python (Join-Path $DevRoot "release\prune_worker_venv.py") $venvDest
if ($LASTEXITCODE -ne 0) { throw "prune_worker_venv failed" }
$venvMb = Get-TreeSizeMb $venvDest
Write-Host "worker/.venv size: $venvMb MB" -ForegroundColor DarkGray

Write-Host "Bundle portable base Python (no system Python)..." -ForegroundColor Yellow
& $Python (Join-Path $DevRoot "release\make_venv_portable.py") $venvDest (Join-Path $stagingWorker ".")
if ($LASTEXITCODE -ne 0) { throw "make_venv_portable failed" }
$pyRuntimeMb = Get-TreeSizeMb (Join-Path $stagingWorker "python")
Write-Host "worker/python size: $pyRuntimeMb MB" -ForegroundColor DarkGray

Copy-Item -LiteralPath (Join-Path $DevRoot "VERSION.txt") -Destination (Join-Path $stagingApp "VERSION.txt") -Force

$builtExe = Join-Path $staging "VNText Studio.exe"
$sha = Get-Sha256 $builtExe
$builtSize = (Get-Item -LiteralPath $builtExe).Length

$exeUrl = ""
$manifest = [ordered]@{
    version = $version
    source_sha = $SourceSha
    source_tree_sha256 = $SourceTreeSha256
    sha256  = $sha
    built   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    notes   = "VNText Studio $version (WPF)"
    url     = $exeUrl
}
[System.IO.File]::WriteAllText(
    (Join-Path $stagingApp "RELEASE.json"),
    ($manifest | ConvertTo-Json -Depth 4),
    (New-Object System.Text.UTF8Encoding $false)
)

New-Item -ItemType Directory -Path $updatesStaging -Force | Out-Null
if ($SkipWpfUpdatePackage) {
    # A disposable workspace, not an executable/package placeholder.
    New-Item -ItemType Directory -Path $wpfUpdatePublish -Force | Out-Null
} else {
Write-Host "Build immutable WPF package and Updates manifest..." -ForegroundColor Yellow
$updatePublisher = Join-Path $DevRoot "release\publish_owner_wpf_update.py"
& $Python -B $updatePublisher `
    --wpf-publish-root $wpfUpdatePublish `
    --install-root $staging `
    --updates-root $updatesStaging `
    --version $WpfUpdateVersion `
    --source-sha $SourceSha `
    --notes "VNText Studio $WpfUpdateVersion (WPF update)"
if ($LASTEXITCODE -ne 0) { throw "WPF Updates package generation failed" }

}

Write-Host "Rewrite portable pyvenv.cfg for final Release path..." -ForegroundColor Yellow
& $Python (Join-Path $DevRoot "release\make_venv_portable.py") `
    (Join-Path $stagingWorker ".venv") `
    $stagingWorker `
    --rewrite-only
if ($LASTEXITCODE -ne 0) { throw "make_venv_portable --rewrite-only failed" }

Assert-ReleaseLayout $staging $frameworkRuntimeVersion $hostFxrVersion

Write-Host "Build the in-place uninstaller..." -ForegroundColor Yellow
$frameworkDirs = @(
    (Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319"),
    (Join-Path $env:WINDIR "Microsoft.NET\Framework\v4.0.30319")
)
$csc = $null
foreach ($dir in $frameworkDirs) {
    $candidate = Join-Path $dir "csc.exe"
    if (Test-Path -LiteralPath $candidate) { $csc = $candidate; break }
}
if (-not $csc) { throw "Installed .NET Framework csc.exe was not found" }
$setupSource = Join-Path $DevRoot "release\Setup.cs"
$setupVersionSource = Join-Path $publishArtifactRoot "SetupVersion.cs"
$versionNumeric = ($version -replace '-.*$', '') + '.0'
Write-SetupVersionSource $setupVersionSource $version $versionNumeric
$uninstaller = Join-Path $staging "Uninstall.exe"
& $csc /nologo /target:winexe /define:UNINSTALLER /out:$uninstaller /reference:System.Windows.Forms.dll /reference:System.Web.Extensions.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll $setupSource $setupVersionSource
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $uninstaller)) { throw "Uninstall.exe compilation failed" }
Assert-SetupVersion $uninstaller $version $versionNumeric

Write-Host "`n[post] RELEASE verify..." -ForegroundColor Yellow
$savedRoot = $env:DOTNET_ROOT
$savedRootX64 = $env:DOTNET_ROOT_X64
$env:DOTNET_ROOT = Join-Path $dotnetRuntimeRoot "must-not-resolve-runtime"
$env:DOTNET_ROOT_X64 = $env:DOTNET_ROOT
try {
    $releaseExe = Join-Path $staging "VNText Studio.exe"
    $verifyCode = Invoke-ReleaseExe -ExePath $releaseExe -Arguments @("--release-verify") -WorkingDirectory $staging
    if ($verifyCode -ne 0) { throw "RELEASE --release-verify failed (exit $verifyCode)" }
    Write-Host "RELEASE verify PASS" -ForegroundColor Green

    Write-Host "`n[5/5] WPF smoke from RELEASE..." -ForegroundColor Yellow
    $smokeCode = 1
    foreach ($attempt in 1..3) {
        $smokeCode = Invoke-ReleaseExe -ExePath $releaseExe -Arguments @("--smoke-worker") -WorkingDirectory $staging
        if ($smokeCode -eq 0) { break }
        Write-Host "smoke-worker attempt $attempt failed (exit $smokeCode); retry..." -ForegroundColor DarkYellow
        Start-Sleep -Seconds 2
    }
    if ($smokeCode -ne 0) { throw "WPF --smoke-worker failed with exit $smokeCode" }
        $smokeOther = Invoke-ReleaseExe -ExePath $releaseExe -Arguments @("--smoke-worker") -WorkingDirectory $systemTempCwd
    if ($smokeOther -ne 0) { throw "WPF --smoke-worker from TEMP failed (exit $smokeOther)" }
    Write-Host "WPF smoke PASS (private app/dotnet runtime; Release cwd + TEMP cwd)" -ForegroundColor Green
} finally {
    $env:DOTNET_ROOT = $savedRoot
    $env:DOTNET_ROOT_X64 = $savedRootX64
}

# Verification creates app-owned state in the disposable staging root. Do not
# ship that state or any test output inside the user-selected install data tree.
$stagingData = Join-Path $staging "data"
if (Test-Path -LiteralPath $stagingData) { Remove-Item -LiteralPath $stagingData -Recurse -Force -ErrorAction Stop }

Clean-ReleaseArtifacts $staging
$portableCfg = Join-Path $stagingWorker ".venv\pyvenv.cfg"
$portableVersion = (& $Python -c "import sys; print('.'.join(map(str,sys.version_info[:3])))").Trim()
if ($LASTEXITCODE -ne 0 -or $portableVersion -notmatch '^3\.12\.') { throw "Cannot resolve bundled Python version for portable pyvenv.cfg" }
[System.IO.File]::WriteAllText($portableCfg, "home = __VNText_INSTALL_ROOT__\app\worker\python`ninclude-system-site-packages = false`nversion = $portableVersion`n", (New-Object System.Text.UTF8Encoding $false))
Assert-ReleaseLayout $staging $frameworkRuntimeVersion $hostFxrVersion

$stageRoots = @(Get-ChildItem -LiteralPath $staging -Force | Select-Object -ExpandProperty Name | Sort-Object)
$requiredStageRoots = @("app", "Uninstall.exe", "VNText Studio.exe")
if ($stageRoots.Count -ne $requiredStageRoots.Count -or @($requiredStageRoots | Where-Object { $_ -notin $stageRoots }).Count -gt 0) {
    throw "Setup staging root has an unexpected layout; found: $($stageRoots -join ', ')"
}

$finalForbidden = Get-ChildItem -LiteralPath $staging -Recurse -File -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @(".pyc", ".pyo", ".log", ".pdb") }
if ($finalForbidden) {
    throw "Final Release audit found forbidden files: $($finalForbidden.FullName -join ', ')"
}
$finalCaches = Get-ChildItem -LiteralPath $staging -Recurse -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq "__pycache__" }
if ($finalCaches) {
    throw "Final Release audit found forbidden __pycache__ directories: $($finalCaches.FullName -join ', ')"
}
Write-Host "Final Release audit: no pyc/pyo/log/PDB artifacts" -ForegroundColor Green

if ($FullAppUpdateBaselineRoot) {
    Write-Host "Build source-bound full-app update from baseline $FullAppUpdateBaselineRoot..." -ForegroundColor Yellow
    & $Python -B (Join-Path $DevRoot "release\publish_full_app_update.py") `
        --baseline-root $FullAppUpdateBaselineRoot `
        --candidate-root $staging `
        --updates-root $updatesStaging `
        --version $version `
        --source-sha $SourceSha `
        --source-tree-sha256 $SourceTreeSha256 `
        --notes "VNText Studio $version (full-app update)"
    if ($LASTEXITCODE -ne 0) { throw "Full-app Updates package generation failed" }
} else {
    Write-Host "Full-app Updates package not built: no installed baseline supplied; releases without this feed require Setup for full-app changes." -ForegroundColor DarkYellow
}

Write-Host "Build and hash-check the complete Setup payload..." -ForegroundColor Yellow
$payloadBytes = [long](Get-ChildItem -LiteralPath $staging -Recurse -File -Force | Measure-Object Length -Sum).Sum
$payloadCount = (Get-ChildItem -LiteralPath $staging -Recurse -File -Force).Count
& $Python (Join-Path $DevRoot "release\package_installer.py") $staging $payloadZip
if ($LASTEXITCODE -ne 0) { throw "Setup payload hash/package verification failed" }
$resourceArgument = [string]::Concat("/resource:", $payloadZip, ",Payload.zip")
$setupCompileArgs = @("/nologo", "/target:winexe", "/out:$setupExe", $resourceArgument,
    "/reference:System.Windows.Forms.dll", "/reference:System.Web.Extensions.dll",
    "/reference:System.IO.Compression.dll", "/reference:System.IO.Compression.FileSystem.dll")
if (-not [string]::IsNullOrWhiteSpace($GitHubOwner)) {
    $githubConfigResource = Join-Path $publishArtifactRoot "VNText.Studio.GitHubUpdateSource.json"
    $githubConfigJson = @{ owner = $GitHubOwner; repository = $GitHubRepository } | ConvertTo-Json -Compress
    [System.IO.File]::WriteAllText($githubConfigResource, $githubConfigJson, [System.Text.UTF8Encoding]::new($false))
    $setupCompileArgs += [string]::Concat("/resource:", $githubConfigResource, ",VNText.Studio.GitHubUpdateSource.json")
}
$setupCompileArgs += @($setupSource, $setupVersionSource)
& $csc @setupCompileArgs
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $setupExe)) { throw "Setup.exe compilation failed" }
Assert-SetupVersion $setupExe $version $versionNumeric
$setupSha = Get-Sha256 $setupExe
$setupBytes = (Get-Item -LiteralPath $setupExe).Length
if ($setupSha -notmatch '^[0-9a-f]{64}$' -or $setupBytes -le 0) { throw "Setup.exe hash/size validation failed" }

Write-Host ""
Write-Host "=== Publish package ready ===" -ForegroundColor Green
Write-Host "Version:  $version"
Write-Host "Source:   $SourceSha"
Write-Host "SHA256:   $setupSha"
if ([string]::IsNullOrWhiteSpace($GitHubOwner)) {
    Write-Host "GitHub stable updates: unconfigured"
} else {
    Write-Host "GitHub stable updates: $GitHubOwner/$GitHubRepository"
}
Write-Host "Size:     $setupBytes bytes"
Write-Host "Payload:  $payloadCount files, $payloadBytes bytes ($((Format-Megabytes $payloadBytes)) MB)"

Assert-ReleaseRootLayout -Path $ReleaseRoot
New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null
$pendingSetup = Join-Path $ReleaseRoot "Setup.pending.exe"
$previousSetup = Join-Path $ReleaseRoot "Setup.previous.exe"
if (Test-Path -LiteralPath $previousSetup -PathType Leaf) {
    if (Test-Path -LiteralPath $setupReleasePath -PathType Leaf) {
        Remove-Item -LiteralPath $previousSetup -Force -ErrorAction Stop
    } else {
        [System.IO.File]::Move($previousSetup, $setupReleasePath)
    }
}
$hadPreviousSetup = Test-Path -LiteralPath $setupReleasePath -PathType Leaf
$replacementStarted = $false
Copy-Item -LiteralPath $setupExe -Destination $pendingSetup -Force
try {
    if ((Get-Sha256 $pendingSetup) -ne $setupSha) { throw "Copied Setup.exe hash mismatch; old Release contents preserved" }
    $updatesRoot = Join-Path $ReleaseRoot "Updates"
    if (Test-Path -LiteralPath $updatesRoot) {
        $updatesItem = Get-Item -LiteralPath $updatesRoot -Force
        if (-not $updatesItem.PSIsContainer -or (($updatesItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw "ReleaseRoot Updates must be a regular directory: $updatesRoot"
        }
    } else {
        New-Item -ItemType Directory -Path $updatesRoot -ErrorAction Stop | Out-Null
    }
    $stagedFeedPath = Join-Path $updatesStaging "wpf-update-current.json"
    $hasStagedWpfFeed = Test-Path -LiteralPath $stagedFeedPath -PathType Leaf
    if ([bool]$hasStagedWpfFeed -eq [bool]$SkipWpfUpdatePackage) {
        throw "Staged WPF feed presence does not match the requested publisher mode"
    }
    if ($hasStagedWpfFeed) {
        $stagedFeed = Get-Content -LiteralPath $stagedFeedPath -Raw | ConvertFrom-Json
        $packageFile = [string]$stagedFeed.package_file
        $packageSha = [string]$stagedFeed.package_sha256
        if ([System.IO.Path]::GetFileName($packageFile) -ne $packageFile -or $packageFile -notmatch '^wpf-update-.+\.zip$' -or $packageSha -notmatch '^[0-9a-f]{64}$') {
            throw "Staged WPF Updates manifest has an unsafe package path or hash"
        }
        $stagedPackage = Join-Path $updatesStaging $packageFile
        $releasePackage = Join-Path $updatesRoot $packageFile
        $pendingPackage = Join-Path $updatesRoot ("." + $packageFile + ".pending")
        if (-not (Test-Path -LiteralPath $stagedPackage -PathType Leaf) -or (Get-Sha256 $stagedPackage) -ne $packageSha) {
            throw "Staged WPF Updates package is missing or has a SHA-256 mismatch"
        }
        if (Test-Path -LiteralPath $releasePackage) {
            $packageItem = Get-Item -LiteralPath $releasePackage -Force
            if ($packageItem.PSIsContainer -or (($packageItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) -or (Get-Sha256 $releasePackage) -ne $packageSha) {
                throw "Immutable WPF Updates package collision: $releasePackage"
            }
        } else {
            if (Test-Path -LiteralPath $pendingPackage) { throw "Stale WPF package transaction file exists: $pendingPackage" }
            Copy-Item -LiteralPath $stagedPackage -Destination $pendingPackage -ErrorAction Stop
            if ((Get-Sha256 $pendingPackage) -ne $packageSha) { throw "Copied WPF Updates package hash mismatch" }
            [System.IO.File]::Move($pendingPackage, $releasePackage)
        }
    }
    $currentUpdateFeed = Join-Path $updatesRoot "wpf-update-current.json"
    $pendingUpdateFeed = Join-Path $updatesRoot ".wpf-update-current.json.pending"
    $previousUpdateFeed = Join-Path $updatesRoot ".wpf-update-current.json.previous"
    $failedUpdateFeed = Join-Path $updatesRoot ".wpf-update-current.json.failed"
    if ((Test-Path -LiteralPath $pendingUpdateFeed) -or (Test-Path -LiteralPath $previousUpdateFeed) -or (Test-Path -LiteralPath $failedUpdateFeed)) {
        throw "Stale WPF Updates manifest transaction file exists under $updatesRoot"
    }
    if ($hasStagedWpfFeed) {
        $stagedFeedSha = Get-Sha256 $stagedFeedPath
        Copy-Item -LiteralPath $stagedFeedPath -Destination $pendingUpdateFeed -ErrorAction Stop
        if ((Get-Sha256 $pendingUpdateFeed) -ne $stagedFeedSha) { throw "Copied WPF Updates manifest hash mismatch" }
    }
    $hadPreviousUpdateFeed = Test-Path -LiteralPath $currentUpdateFeed -PathType Leaf
    if (Test-Path -LiteralPath $currentUpdateFeed) {
        $currentFeedItem = Get-Item -LiteralPath $currentUpdateFeed -Force
        if ($currentFeedItem.PSIsContainer -or (($currentFeedItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw "Current WPF Updates manifest must be a regular file: $currentUpdateFeed"
        }
    }
    $currentFullAppFeed = Join-Path $updatesRoot "full-app-update-current.json"
    $pendingFullAppFeed = Join-Path $updatesRoot ".full-app-update-current.json.pending"
    $previousFullAppFeed = Join-Path $updatesRoot ".full-app-update-current.json.previous"
    $failedFullAppFeed = Join-Path $updatesRoot ".full-app-update-current.json.failed"
    if ((Test-Path -LiteralPath $pendingFullAppFeed) -or (Test-Path -LiteralPath $previousFullAppFeed) -or (Test-Path -LiteralPath $failedFullAppFeed)) {
        throw "Stale full-app Updates manifest transaction file exists under $updatesRoot"
    }
    $hadPreviousFullAppFeed = Test-Path -LiteralPath $currentFullAppFeed -PathType Leaf
    if (Test-Path -LiteralPath $currentFullAppFeed) {
        $currentFullFeedItem = Get-Item -LiteralPath $currentFullAppFeed -Force
        if ($currentFullFeedItem.PSIsContainer -or (($currentFullFeedItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw "Current full-app Updates manifest must be a regular file: $currentFullAppFeed"
        }
    }
    $stagedFullAppFeedPath = Join-Path $updatesStaging "full-app-update-current.json"
    $hasStagedFullAppFeed = Test-Path -LiteralPath $stagedFullAppFeedPath -PathType Leaf
    if ($FullAppUpdateBaselineRoot -and -not $hasStagedFullAppFeed) {
        throw "Full-app Update baseline was supplied but the full-app Updates manifest was not generated."
    }
    if ($hasStagedFullAppFeed) {
        $stagedFullAppFeed = Get-Content -LiteralPath $stagedFullAppFeedPath -Raw | ConvertFrom-Json
        $fullAppPackageFile = [string]$stagedFullAppFeed.package_file
        $fullAppPackageSha = [string]$stagedFullAppFeed.package_sha256
        $fullManifest = $stagedFullAppFeed.manifest
        if ([int]$stagedFullAppFeed.schema -ne 1 -or
            [System.IO.Path]::GetFileName($fullAppPackageFile) -ne $fullAppPackageFile -or
            $fullAppPackageFile -notmatch '^full-app-update-.+\.zip$' -or
            $fullAppPackageSha -notmatch '^[0-9a-f]{64}$' -or
            $fullManifest.version -ne $version -or $fullManifest.source_sha -ne $SourceSha -or
            $fullManifest.source_tree_sha256 -ne $SourceTreeSha256) {
            throw "Staged full-app Updates manifest has invalid source identity, version, package path or hash"
        }
        $stagedFullAppPackage = Join-Path $updatesStaging $fullAppPackageFile
        $releaseFullAppPackage = Join-Path $updatesRoot $fullAppPackageFile
        $pendingFullAppPackage = Join-Path $updatesRoot ("." + $fullAppPackageFile + ".pending")
        if (-not (Test-Path -LiteralPath $stagedFullAppPackage -PathType Leaf) -or (Get-Sha256 $stagedFullAppPackage) -ne $fullAppPackageSha) {
            throw "Staged full-app Updates package is missing or has a SHA-256 mismatch"
        }
        if (Test-Path -LiteralPath $releaseFullAppPackage) {
            $fullPackageItem = Get-Item -LiteralPath $releaseFullAppPackage -Force
            if ($fullPackageItem.PSIsContainer -or (($fullPackageItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) -or
                (Get-Sha256 $releaseFullAppPackage) -ne $fullAppPackageSha) {
                throw "Immutable full-app Updates package collision: $releaseFullAppPackage"
            }
        } else {
            if (Test-Path -LiteralPath $pendingFullAppPackage) { throw "Stale full-app package transaction file exists: $pendingFullAppPackage" }
            Copy-Item -LiteralPath $stagedFullAppPackage -Destination $pendingFullAppPackage -ErrorAction Stop
            if ((Get-Sha256 $pendingFullAppPackage) -ne $fullAppPackageSha) { throw "Copied full-app Updates package hash mismatch" }
            [System.IO.File]::Move($pendingFullAppPackage, $releaseFullAppPackage)
        }
        $fullAppFeedSha = Get-Sha256 $stagedFullAppFeedPath
        Copy-Item -LiteralPath $stagedFullAppFeedPath -Destination $pendingFullAppFeed -ErrorAction Stop
        if ((Get-Sha256 $pendingFullAppFeed) -ne $fullAppFeedSha) { throw "Copied full-app Updates manifest hash mismatch" }
    }
    $updateFeedCommitted = $false
    $fullAppFeedCommitted = $false
    $cleanupScript = "import sys; sys.path.insert(0,sys.argv[2]); sys.path.insert(0,sys.argv[1]); from pathlib import Path; from cleanup_work_artifacts import cleanup_after_test; report=cleanup_after_test([Path(sys.argv[4]),Path(sys.argv[5]),Path(sys.argv[6]),Path(sys.argv[7]),Path(sys.argv[8])],reason='release/publish.ps1',outcome='PASS',scope_id=sys.argv[3],run_id=sys.argv[3]); print(report); raise SystemExit(0 if report.get('ok') else 1)"
    & $Python -B -c $cleanupScript (Join-Path $ArtifactHelpersRoot "..\tools") $ArtifactHelpersRoot $publishScope $staging $payloadZip $setupExe $wpfUpdatePublish $updatesStaging
    if ($LASTEXITCODE -ne 0) { throw "Portable Setup staging cleanup did not complete; old Release contents preserved" }
    if (-not (Test-Path -LiteralPath $pendingSetup -PathType Leaf)) { throw "Verified pending Setup disappeared during cleanup" }
    if (-not (Test-Path -LiteralPath $pendingSetup -PathType Leaf)) { throw "Verified pending Setup disappeared during Release cleanup" }
    $replacementStarted = $true
    if ($hadPreviousSetup) {
        [System.IO.File]::Move($setupReleasePath, $previousSetup)
    }
    [System.IO.File]::Move($pendingSetup, $setupReleasePath)
    $finalSha = if (Test-Path -LiteralPath $setupReleasePath -PathType Leaf) { Get-Sha256 $setupReleasePath } else { "missing" }
    if ($finalSha -ne $setupSha) { throw "Installed Setup hash mismatch before WPF Updates manifest publication" }
    $updateFeedCommitted = Switch-UpdateFeed $pendingUpdateFeed $currentUpdateFeed $previousUpdateFeed ([bool]$hasStagedWpfFeed) ([bool]$hadPreviousUpdateFeed)
    if ($hasStagedFullAppFeed) {
        if ($hadPreviousFullAppFeed) {
            [System.IO.File]::Replace($pendingFullAppFeed, $currentFullAppFeed, $previousFullAppFeed)
        } else {
            [System.IO.File]::Move($pendingFullAppFeed, $currentFullAppFeed)
        }
        $fullAppFeedCommitted = $true
    } elseif ($hadPreviousFullAppFeed) {
        [System.IO.File]::Move($currentFullAppFeed, $previousFullAppFeed)
        $fullAppFeedCommitted = $true
    }
    $transactionNames = @(Get-ChildItem -LiteralPath $ReleaseRoot -Force | Select-Object -ExpandProperty Name | Sort-Object)
    $expectedTransactionNames = if ($hadPreviousSetup) { @("Setup.exe", "Setup.previous.exe", "Updates") } else { @("Setup.exe", "Updates") }
    if ($finalSha -ne $setupSha -or ($transactionNames -join "|") -ne ($expectedTransactionNames -join "|")) {
        throw "Setup replacement mismatch: hash=$finalSha; entries=[$($transactionNames -join ', ')]"
    }
    if (Test-Path -LiteralPath $previousSetup) { Remove-Item -LiteralPath $previousSetup -Force -ErrorAction Stop }
    if (Test-Path -LiteralPath $previousUpdateFeed) { Remove-Item -LiteralPath $previousUpdateFeed -Force -ErrorAction Stop }
    if (Test-Path -LiteralPath $previousFullAppFeed) { Remove-Item -LiteralPath $previousFullAppFeed -Force -ErrorAction Stop }
    $finalFiles = @(Get-ChildItem -LiteralPath $ReleaseRoot -Force)
    if ($finalFiles.Count -ne 2 -or @($finalFiles | Where-Object { $_.Name -notin @("Setup.exe", "Updates") }).Count -gt 0 -or
        -not ($finalFiles | Where-Object { $_.Name -eq "Setup.exe" -and -not $_.PSIsContainer }) -or
        -not ($finalFiles | Where-Object { $_.Name -eq "Updates" -and $_.PSIsContainer }) -or
        (Get-Sha256 $setupReleasePath) -ne $setupSha) {
        $names = ($finalFiles | Select-Object -ExpandProperty Name) -join ", "
        throw "Final Release invariant failed: entries=[$names]; hash=$(if (Test-Path -LiteralPath $setupReleasePath -PathType Leaf) { Get-Sha256 $setupReleasePath } else { 'missing' })"
    }
} catch {
    if ($fullAppFeedCommitted) {
        try {
            Restore-UpdateFeed $currentFullAppFeed $previousFullAppFeed $failedFullAppFeed ([bool]$hadPreviousFullAppFeed)
        } catch {
            Write-Warning "Could not restore previous full-app Updates manifest; recovery file: $previousFullAppFeed"
        }
    }
    if ($updateFeedCommitted) {
        try {
            Restore-UpdateFeed $currentUpdateFeed $previousUpdateFeed $failedUpdateFeed ([bool]$hadPreviousUpdateFeed)
        } catch {
            Write-Warning "Could not restore previous WPF Updates manifest; recovery file: $previousUpdateFeed"
        }
    }
    if ($replacementStarted -and (Test-Path -LiteralPath $previousSetup -PathType Leaf)) {
        try {
            $failedSetup = Join-Path $ReleaseRoot "Setup.failed.exe"
            if (Test-Path -LiteralPath $setupReleasePath -PathType Leaf) {
                if (Test-Path -LiteralPath $failedSetup -PathType Leaf) {
                    Remove-Item -LiteralPath $failedSetup -Force -ErrorAction Stop
                }
                [System.IO.File]::Move($setupReleasePath, $failedSetup)
            }
            [System.IO.File]::Move($previousSetup, $setupReleasePath)
            if (Test-Path -LiteralPath $failedSetup -PathType Leaf) {
                Remove-Item -LiteralPath $failedSetup -Force -ErrorAction Stop
            }
        } catch {
            Write-Warning "Could not restore previous Setup automatically; recovery copy: $previousSetup"
        }
    } elseif ($replacementStarted -and -not $hadPreviousSetup -and (Test-Path -LiteralPath $setupReleasePath -PathType Leaf)) {
        Remove-Item -LiteralPath $setupReleasePath -Force -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $pendingSetup) { Remove-Item -LiteralPath $pendingSetup -Force -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $pendingUpdateFeed) { Remove-Item -LiteralPath $pendingUpdateFeed -Force -ErrorAction SilentlyContinue }
    if ($pendingFullAppFeed -and (Test-Path -LiteralPath $pendingFullAppFeed)) { Remove-Item -LiteralPath $pendingFullAppFeed -Force -ErrorAction SilentlyContinue }
    if ($pendingPackage -and (Test-Path -LiteralPath $pendingPackage)) { Remove-Item -LiteralPath $pendingPackage -Force -ErrorAction SilentlyContinue }
    if ($pendingFullAppPackage -and (Test-Path -LiteralPath $pendingFullAppPackage)) { Remove-Item -LiteralPath $pendingFullAppPackage -Force -ErrorAction SilentlyContinue }
    throw
}

Write-Host ""
Write-Host "Final ReleaseRoot contains Setup.exe and retained Updates: $ReleaseRoot"
$publishedPackages = @(Get-ChildItem -LiteralPath (Join-Path $ReleaseRoot "Updates") -File -Filter "wpf-update-*.zip" -Force)
$publishedPackageBytes = [long]($publishedPackages | Measure-Object Length -Sum).Sum
Write-Host "WPF Updates retention: $($publishedPackages.Count) immutable packages, $publishedPackageBytes bytes" -ForegroundColor DarkGray
$publishedFullAppPackages = @(Get-ChildItem -LiteralPath (Join-Path $ReleaseRoot "Updates") -File -Filter "full-app-update-*.zip" -Force)
$publishedFullAppPackageBytes = [long]($publishedFullAppPackages | Measure-Object Length -Sum).Sum
Write-Host "Full-app Updates retention: $($publishedFullAppPackages.Count) immutable packages, $publishedFullAppPackageBytes bytes" -ForegroundColor DarkGray
