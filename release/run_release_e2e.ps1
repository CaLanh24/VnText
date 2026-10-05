# End-to-end RELEASE verification (workflow + EXE-only update).
# The baseline and candidate are separate complete Release trees.  The update
# contract intentionally swaps only the EXE, so the baseline tree is never
# mixed with a partially published candidate before the updater starts.
param(
    [string]$ReleaseRoot = "",
    [string]$DevRoot = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($DevRoot)) {
    $DevRoot = Split-Path -Parent $PSScriptRoot
} else {
    $DevRoot = [System.IO.Path]::GetFullPath($DevRoot)
}
if ([string]::IsNullOrWhiteSpace($ReleaseRoot)) {
    $ReleaseRoot = Join-Path (Split-Path -Parent $DevRoot) "VNText_Studio_Release"
} else {
    $ReleaseRoot = [System.IO.Path]::GetFullPath($ReleaseRoot)
}
Set-Location $DevRoot

$versionFile = Join-Path $DevRoot "VERSION.txt"
$backendFile = Join-Path $DevRoot "vntext\app_backend.py"
$versionInfo = Join-Path $DevRoot "release\version_info.txt"
$baseVersion = (Get-Content -LiteralPath $versionFile -Raw).Trim()
$headVersion = (& git -C $DevRoot show HEAD:VERSION.txt).Trim()
if ($baseVersion -ne $headVersion) {
    throw "Source VERSION.txt does not match HEAD ($baseVersion != $headVersion); restore any interrupted temporary version edit before retrying"
}
$baseParts = ($baseVersion -replace '-.*$', '').Split('.')
if ($baseParts.Count -ne 3 -or ($baseParts | Where-Object { $_ -notmatch '^\d+$' })) {
    throw "VERSION.txt must contain a three-part version with an optional suffix: $baseVersion"
}
$nextVersion = "{0}.{1}.{2}-dev" -f $baseParts[0], $baseParts[1], ([int]$baseParts[2] + 1)
$nextUpdateParts = ($nextVersion -replace '-.*$', '').Split('.')
$nextWpfUpdateVersion = "{0}.{1}.{2}-dev" -f $nextUpdateParts[0], $nextUpdateParts[1], ([int]$nextUpdateParts[2] + 1)
$baseNumeric = "{0}, {1}, {2}, 0" -f $baseParts[0], $baseParts[1], $baseParts[2]
$nextParts = ($nextVersion -replace '-.*$', '').Split('.')
$nextNumeric = "{0}, {1}, {2}, 0" -f $nextParts[0], $nextParts[1], $nextParts[2]

$WorkRoot = Join-Path $DevRoot "RELEASE_RUN"
$Work = Join-Path $WorkRoot "release_verify"
$ReportDir = Join-Path $Work "reports"
$CandidateScopeRoot = Join-Path $WorkRoot "release_e2e"
$CandidateRoot = Join-Path $CandidateScopeRoot "candidate_release"
$RuntimeDataRoot = Join-Path $CandidateScopeRoot "localappdata"
$CandidateExe = Join-Path $CandidateRoot "VNText Studio.exe"
$ReleaseExe = Join-Path $ReleaseRoot "VNText Studio.exe"
$ReleaseJson = Join-Path $ReleaseRoot "RELEASE.json"
$CleanupScript = Join-Path $DevRoot "tests\tools\cleanup_work_artifacts.py"
$Python = Join-Path $DevRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    $Python = (Get-Command python.exe -ErrorAction Stop).Source
}

New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
if (-not (Test-Path -LiteralPath $CleanupScript -PathType Leaf)) {
    throw "Cleanup tool not found: $CleanupScript"
}
if (Test-Path -LiteralPath $CandidateRoot) {
    throw "Candidate Release root already exists; clean it through the artifact lifecycle before retrying: $CandidateRoot"
}
if (Test-Path -LiteralPath $CandidateScopeRoot) {
    throw "Release E2E scope already exists; clean it through the artifact lifecycle before retrying: $CandidateScopeRoot"
}
if (-not (Test-Path -LiteralPath $ReleaseExe -PathType Leaf)) {
    throw "Missing baseline RELEASE EXE: $ReleaseExe"
}

$ScopeId = "release-e2e-" + [Guid]::NewGuid().ToString("N")
$RunId = "release-e2e-run-" + [Guid]::NewGuid().ToString("N")
$BeforeSnapshot = Join-Path $ReportDir "candidate_scope_before.json"
$CleanupReport = Join-Path $ReportDir "candidate_cleanup.json"
$CandidateRegistered = $false
$SourceChanged = $false
$SourceRestored = $false
$ScriptPassed = $false

function Get-Sha256([string]$Path) {
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-TreeBytes([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return [long]0 }
    $sum = (Get-ChildItem -LiteralPath $Path -Recurse -File -Force |
        Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sum) { return [long]0 }
    return [long]$sum
}

function Read-Report([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Register-Artifact([string]$Path, [string]$Purpose, [string]$Lifecycle) {
    & $Python -B $CleanupScript `
        --register-path $Path `
        --scope-id $ScopeId `
        --run-id $RunId `
        --scope-root $CandidateScopeRoot `
        --owner "release/run_release_e2e.ps1" `
        --purpose $Purpose `
        --lifecycle $Lifecycle
    if ($LASTEXITCODE -ne 0) {
        throw "Artifact registration failed for $Path (exit $LASTEXITCODE)"
    }
}

function Wait-ExeVersion([string]$Exe, [string]$Expected, [string]$Label, [int]$TimeoutSec = 90) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $reportPath = Join-Path $ReportDir ("version_{0}.json" -f $Label)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path -LiteralPath $reportPath) { Remove-Item -LiteralPath $reportPath -Force }
        $workingDirectory = Split-Path -Parent $Exe
        $p = Start-Process -FilePath $Exe `
            -ArgumentList @("--release-version", "--report", $reportPath) `
            -WorkingDirectory $workingDirectory -PassThru -Wait
        if ($p.ExitCode -eq 0 -and (Test-Path -LiteralPath $reportPath -PathType Leaf)) {
            $rep = Read-Report $reportPath
            if ($null -ne $rep -and [string]$rep.version -eq $Expected -and $rep.ok -eq $true) {
                return [string]$rep.version
            }
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out waiting for EXE version $Expected ($Label): $Exe"
}

function Assert-TopLayout([string]$Root, [string[]]$ExpectedNames, [string]$Label) {
    $actual = @(Get-ChildItem -LiteralPath $Root -Force | Select-Object -ExpandProperty Name | Sort-Object)
    $expected = @($ExpectedNames | Sort-Object)
    $delta = @(Compare-Object -ReferenceObject $expected -DifferenceObject $actual)
    if ($delta.Count -gt 0) {
        $diff = ($delta | ForEach-Object { "$($_.SideIndicator)$($_.InputObject)" }) -join ', '
        throw "$Label top-level Release layout changed: $diff"
    }
}

function Assert-ReleaseTreeClean([string]$Root, [string]$Label) {
    $badFiles = @(Get-ChildItem -LiteralPath $Root -Recurse -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @(".pyc", ".pyo", ".log", ".pdb") })
    $badCaches = @(Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq "__pycache__" })
    if ($badFiles.Count -gt 0 -or $badCaches.Count -gt 0) {
        $paths = @($badFiles.FullName) + @($badCaches.FullName)
        throw "$Label contains forbidden Release artifacts: $($paths -join ', ')"
    }
}

function Assert-ReleaseIdentity(
    [string]$Root,
    [string]$ExpectedVersion,
    [string[]]$ExpectedNames,
    [string]$Label,
    [switch]$RequireSelfManifest
) {
    $exe = Join-Path $Root "VNText Studio.exe"
    $versionPath = Join-Path $Root "VERSION.txt"
    $releasePath = Join-Path $Root "RELEASE.json"
    $backendPath = Join-Path $Root "worker\vntext\app_backend.py"
    $modelManifestPath = Join-Path $Root "MODEL_MANIFEST.json"
    foreach ($required in @($exe, $versionPath, $releasePath, $backendPath, $modelManifestPath, (Join-Path $Root "worker"))) {
        if (-not (Test-Path -LiteralPath $required)) { throw "$Label missing required path: $required" }
    }

    Assert-TopLayout $Root $ExpectedNames $Label
    Assert-ReleaseTreeClean $Root $Label
    $rootVersion = (Get-Content -LiteralPath $versionPath -Raw).Trim()
    if ($rootVersion -ne $ExpectedVersion) { throw "$Label VERSION.txt mismatch: $rootVersion != $ExpectedVersion" }
    $workerText = Get-Content -LiteralPath $backendPath -Raw
    $workerMatch = [regex]::Match($workerText, 'VERSION\s*=\s*"([^"]+)"')
    if (-not $workerMatch.Success -or $workerMatch.Groups[1].Value -ne $ExpectedVersion) {
        throw "$Label bundled worker version mismatch"
    }

    $metadata = Read-Report $releasePath
    if ($null -eq $metadata -or [string]$metadata.version -ne $ExpectedVersion) {
        throw "$Label RELEASE.json version mismatch"
    }
    $sha = Get-Sha256 $exe
    if ([string]$metadata.sha256 -ne $sha) { throw "$Label RELEASE.json SHA256 mismatch" }
    if ([string]::IsNullOrWhiteSpace([string]$metadata.source_sha)) {
        throw "$Label RELEASE.json missing source_sha"
    }
    if ($RequireSelfManifest) {
        $expectedUrl = "file:///$($exe.Replace('\','/'))"
        $publishedUrl = ([string]$metadata.url).Replace('%20', ' ')
        if ($publishedUrl -ne $expectedUrl) { throw "$Label RELEASE.json URL mismatch: $($metadata.url)" }
    }

    $numeric = "{0}.0" -f ($ExpectedVersion -replace '-.*$', '')
    $versionInfo = (Get-Item -LiteralPath $exe).VersionInfo
    if ([string]$versionInfo.FileVersion -ne $numeric) {
        throw "$Label EXE FileVersion mismatch: $($versionInfo.FileVersion) != $numeric"
    }
    $productVersion = ([string]$versionInfo.ProductVersion).Split('+')[0]
    if ($productVersion -ne $ExpectedVersion) {
        throw "$Label EXE ProductVersion mismatch: $($versionInfo.ProductVersion) != $ExpectedVersion"
    }
    $reported = Wait-ExeVersion -Exe $exe -Expected $ExpectedVersion -Label $Label
    return [ordered]@{
        label = $Label
        version = $ExpectedVersion
        exe = $exe
        sha256 = $sha
        file_version = [string]$versionInfo.FileVersion
        product_version = [string]$versionInfo.ProductVersion
        worker_version = $workerMatch.Groups[1].Value
        reported_version = $reported
        bytes = (Get-Item -LiteralPath $exe).Length
        tree_bytes = Get-TreeBytes $Root
        top_level = @($ExpectedNames | Sort-Object)
    }
}

function Assert-UpdatedExeIdentity(
    [string]$Root,
    [string]$ExpectedVersion,
    [string[]]$ExpectedNames,
    [string]$ExpectedSha,
    [string]$Label
) {
    $exe = Join-Path $Root "VNText Studio.exe"
    Assert-TopLayout $Root $ExpectedNames $Label
    Assert-ReleaseTreeClean $Root $Label
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw "$Label EXE missing: $exe" }
    $sha = Get-Sha256 $exe
    if ($sha -ne $ExpectedSha) { throw "$Label EXE SHA256 mismatch: $sha != $ExpectedSha" }
    $numeric = "{0}.0" -f ($ExpectedVersion -replace '-.*$', '')
    $versionInfo = (Get-Item -LiteralPath $exe).VersionInfo
    if ([string]$versionInfo.FileVersion -ne $numeric) {
        throw "$Label EXE FileVersion mismatch: $($versionInfo.FileVersion) != $numeric"
    }
    $productVersion = ([string]$versionInfo.ProductVersion).Split('+')[0]
    if ($productVersion -ne $ExpectedVersion) {
        throw "$Label EXE ProductVersion mismatch: $($versionInfo.ProductVersion) != $ExpectedVersion"
    }
    $reported = Wait-ExeVersion -Exe $exe -Expected $ExpectedVersion -Label $Label
    return [ordered]@{
        label = $Label
        version = $ExpectedVersion
        exe = $exe
        sha256 = $sha
        file_version = [string]$versionInfo.FileVersion
        product_version = [string]$versionInfo.ProductVersion
        reported_version = $reported
        release_tree_version = (Get-Content -LiteralPath (Join-Path $Root "VERSION.txt") -Raw).Trim()
        bytes = (Get-Item -LiteralPath $exe).Length
    }
}

function Stop-ReleaseProcesses([string]$Exe) {
    $target = [System.IO.Path]::GetFullPath($Exe)
    $root = [System.IO.Path]::GetDirectoryName($target)
    $rootPrefix = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    try {
        Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object { $_.ExecutablePath -and [System.IO.Path]::GetFullPath([string]$_.ExecutablePath) -ieq $target } |
            ForEach-Object { & taskkill.exe /PID $_.ProcessId /T /F *> $null }
    } catch {
        # The verification process itself is short-lived; a normal GUI child
        # is harmless here and will be reported by the final Release audit.
    }
    # The Release worker can outlive the GUI process after a verification
    # command.  Stop only processes whose executable is inside this exact
    # Release root so a source/dev worker is never touched.
    Get-Process -ErrorAction SilentlyContinue | ForEach-Object {
        try {
            $path = [System.IO.Path]::GetFullPath([string]$_.Path)
            if ($path.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
            }
        } catch {
            # Access to an unrelated process path can be denied; ignore it.
        }
    }
}

function Invoke-ScopedCleanup([string]$Outcome) {
    & $Python -B $CleanupScript `
        --scope-id $ScopeId `
        --run-id $RunId `
        --scope-root $CandidateScopeRoot `
        --before $BeforeSnapshot `
        --outcome $Outcome `
        --output $CleanupReport `
        --inventory-timeout-seconds 180 `
        --inventory-max-items 500000 | Out-Host
    $exitCode = $LASTEXITCODE
    if (-not (Test-Path -LiteralPath $CleanupReport -PathType Leaf)) {
        throw "Scoped cleanup did not write a terminal report (exit $exitCode)"
    }
    $cleanup = Read-Report $CleanupReport
    if ($Outcome -eq "PASS" -and ($exitCode -ne 0 -or $null -eq $cleanup -or $cleanup.ok -ne $true)) {
        throw "Candidate cleanup failed: exit=$exitCode report=$CleanupReport"
    }
    return [ordered]@{
        report = $CleanupReport
        status = [string]$cleanup.status
        ok = [bool]$cleanup.ok
        terminal_status = [string]$cleanup.terminal_status
        freed_gb = $cleanup.freed_gb
        deleted_count = @($cleanup.deleted | Where-Object { $_.deleted -eq $true }).Count
        unknown_count = @($cleanup.unknown).Count
        locked_count = @($cleanup.locked).Count
        errors_count = @($cleanup.errors).Count
        inventory_complete = [bool]$cleanup.inventory_complete
    }
}

Write-Host "=== RELEASE E2E verify ===" -ForegroundColor Cyan
$oldVersionBytes = [System.IO.File]::ReadAllBytes($versionFile)
$oldBackendBytes = [System.IO.File]::ReadAllBytes($backendFile)
$oldVersionInfoBytes = [System.IO.File]::ReadAllBytes($versionInfo)
$baselineIdentity = $null
$candidateIdentity = $null
$updateIdentity = $null
$cleanup = $null

try {
    $env:LOCALAPPDATA = $RuntimeDataRoot
    $env:VNTEXT_LOCALAPPDATA = $RuntimeDataRoot
    # Register existing empty roots so scoped reconciliation can cover every
    # descendant created by publish/update.  A missing parent is reconciled as
    # MISSING before its children exist and cannot authorize those children.
    New-Item -ItemType Directory -Path $CandidateScopeRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $CandidateRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $RuntimeDataRoot -Force | Out-Null
    Register-Artifact $ReportDir "retained Release E2E reports" "RETAINED"
    Register-Artifact $CandidateScopeRoot "disposable Release E2E scope" "DISPOSABLE"
    Register-Artifact $CandidateRoot "disposable next-version Release tree" "DISPOSABLE"
    Register-Artifact $RuntimeDataRoot "disposable Release updater/runtime data" "DISPOSABLE"
    $CandidateRegistered = $true
    & $Python -B $CleanupScript `
        --snapshot `
        --scope-id $ScopeId `
        --run-id $RunId `
        --scope-root $CandidateScopeRoot `
        --output $BeforeSnapshot `
        --owner "release/run_release_e2e.ps1" `
        --purpose "candidate Release scope before publish" `
        --lifecycle RETAINED
    if ($LASTEXITCODE -ne 0) { throw "Candidate scope snapshot failed" }

    Write-Host "`n[1] Rebuild baseline RELEASE $baseVersion..." -ForegroundColor Yellow
    Stop-ReleaseProcesses $ReleaseExe
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $DevRoot "release\publish.ps1") -WpfUpdateVersion $nextVersion -ReleaseRoot $ReleaseRoot | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "baseline publish failed" }
    $baselineNames = @(Get-ChildItem -LiteralPath $ReleaseRoot -Force | Select-Object -ExpandProperty Name)
    $baselineIdentity = Assert-ReleaseIdentity $ReleaseRoot $baseVersion $baselineNames "baseline" -RequireSelfManifest
    Write-Host "Baseline consistency PASS: $($baselineIdentity.sha256)" -ForegroundColor Green

    Write-Host "`n[2] RELEASE workflow verify (extract/CT2/OPUS-MT/patch/progress/sound)..." -ForegroundColor Yellow
    $verifyReport = Join-Path $ReportDir "release_verify.json"
    if (Test-Path -LiteralPath $verifyReport) { Remove-Item -LiteralPath $verifyReport -Force }
    $p = Start-Process -FilePath $ReleaseExe `
        -ArgumentList @("--release-verify", "--report", $verifyReport) `
        -WorkingDirectory $ReleaseRoot -PassThru -Wait
    $rep = Read-Report $verifyReport
    if ($p.ExitCode -ne 0 -or $null -eq $rep -or $rep.ok -ne $true) {
        throw "RELEASE verify failed: exit=$($p.ExitCode) report=$verifyReport"
    }
    Write-Host "Workflow PASS" -ForegroundColor Green

    Write-Host "`n[3] Build complete next Release tree $nextVersion..." -ForegroundColor Yellow
    $oldBackend = [System.Text.Encoding]::UTF8.GetString($oldBackendBytes)
    $oldVersionInfo = [System.Text.Encoding]::UTF8.GetString($oldVersionInfoBytes)
    [System.IO.File]::WriteAllText($versionFile, $nextVersion, (New-Object System.Text.UTF8Encoding($false)))
    [System.IO.File]::WriteAllText(
        $backendFile,
        ($oldBackend -replace 'VERSION = "[^"]+"', ('VERSION = "{0}"' -f $nextVersion)),
        (New-Object System.Text.UTF8Encoding($false)))
    $nextVersionInfo = $oldVersionInfo `
        -replace [regex]::Escape($baseNumeric), $nextNumeric `
        -replace [regex]::Escape("u'$baseVersion'"), "u'$nextVersion'"
    [System.IO.File]::WriteAllText($versionInfo, $nextVersionInfo, (New-Object System.Text.UTF8Encoding($false)))
    $SourceChanged = $true
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $DevRoot "release\publish.ps1") -SkipTests -WpfUpdateVersion $nextWpfUpdateVersion -ReleaseRoot $CandidateRoot | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "candidate publish $nextVersion failed" }
    $candidateIdentity = Assert-ReleaseIdentity $CandidateRoot $nextVersion $baselineNames "candidate" -RequireSelfManifest
    Write-Host "Candidate consistency PASS: $($candidateIdentity.sha256)" -ForegroundColor Green

    Write-Host "`n[4] Auto-update E2E ($baseVersion -> $nextVersion)..." -ForegroundColor Yellow
    $manifest = [ordered]@{
        version = $nextVersion
        source_sha = (& git -C $DevRoot rev-parse HEAD).Trim()
        sha256 = $candidateIdentity.sha256
        built = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        notes = "VNText Studio $nextVersion update test"
        url = "file:///$($CandidateExe.Replace('\','/'))"
    }
    [System.IO.File]::WriteAllText(
        $ReleaseJson,
        ($manifest | ConvertTo-Json -Depth 4),
        (New-Object System.Text.UTF8Encoding($false)))
    $manifestCheck = Read-Report $ReleaseJson
    if ([string]$manifestCheck.url -ne [string]$manifest.url -or [string]$manifestCheck.sha256 -ne $candidateIdentity.sha256) {
        throw "Update manifest does not point only to the candidate EXE"
    }

    $updateReport = Join-Path $ReportDir "release_update.json"
    if (Test-Path -LiteralPath $updateReport) { Remove-Item -LiteralPath $updateReport -Force }
    $pUpdate = Start-Process -FilePath $ReleaseExe `
        -ArgumentList @("--release-verify-update", "--report", $updateReport) `
        -WorkingDirectory $ReleaseRoot -PassThru
    Start-Sleep -Seconds 8
    $newVersion = Wait-ExeVersion -Exe $ReleaseExe -Expected $nextVersion -Label "updated" -TimeoutSec 120
    $updateRep = Read-Report $updateReport
    if ($null -eq $updateRep -or $updateRep.ok -ne $true) { throw "Update download stage failed" }
    if ($newVersion -ne $nextVersion) { throw "Update did not apply version $nextVersion" }
    $updateIdentity = Assert-UpdatedExeIdentity $ReleaseRoot $nextVersion $baselineNames $candidateIdentity.sha256 "updated-exe"
    if ($updateIdentity.sha256 -ne $candidateIdentity.sha256) { throw "Updated EXE hash is not the candidate hash" }
    Stop-ReleaseProcesses $ReleaseExe
    Write-Host "Auto-update PASS -> $newVersion; SHA256 $($updateIdentity.sha256)" -ForegroundColor Green

    Write-Host "`n[5] Final Release audit..." -ForegroundColor Yellow
    $finalManifest = Read-Report $ReleaseJson
    if ([string]$finalManifest.version -ne $nextVersion -or [string]$finalManifest.sha256 -ne $candidateIdentity.sha256) {
        throw "Final RELEASE.json does not describe the updated EXE"
    }
    Assert-TopLayout $ReleaseRoot $baselineNames "updated-exe"
    Assert-ReleaseTreeClean $ReleaseRoot "updated-exe"
    $ScriptPassed = $true
}
finally {
    if ($SourceChanged) {
        [System.IO.File]::WriteAllBytes($versionFile, $oldVersionBytes)
        [System.IO.File]::WriteAllBytes($backendFile, $oldBackendBytes)
        [System.IO.File]::WriteAllBytes($versionInfo, $oldVersionInfoBytes)
        $SourceRestored = $true
    }
    Stop-ReleaseProcesses $ReleaseExe
    if ($CandidateRegistered) {
        $cleanup = Invoke-ScopedCleanup $(if ($ScriptPassed) { "PASS" } else { "FAIL" })
    }
}

$summary = [ordered]@{
    ok = $true
    workflow = $true
    auto_update = $true
    source_restored = $SourceRestored
    version_before = $baseVersion
    version_after = $nextVersion
    baseline = $baselineIdentity
    candidate = $candidateIdentity
    updated_exe = $updateIdentity
    baseline_tree_bytes = if ($null -ne $baselineIdentity) { $baselineIdentity.tree_bytes } else { 0 }
    candidate_tree_bytes_before_cleanup = if ($null -ne $candidateIdentity) { $candidateIdentity.tree_bytes } else { 0 }
    candidate_tree_exists_after_cleanup = Test-Path -LiteralPath $CandidateRoot
    runtime_data_exists_after_cleanup = Test-Path -LiteralPath $RuntimeDataRoot
    release_files = @(Get-ChildItem -LiteralPath $ReleaseRoot -Force | Select-Object -ExpandProperty Name | Sort-Object)
    cleanup = $cleanup
}
($summary | ConvertTo-Json -Depth 10) | Set-Content -LiteralPath (Join-Path $ReportDir "e2e_summary.json") -Encoding UTF8

Write-Host ""
Write-Host "=== RELEASE E2E PASS ===" -ForegroundColor Green
Write-Host ($summary | ConvertTo-Json -Compress -Depth 10)
