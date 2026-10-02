# Run Release regression patterns in isolated, non-interactive Python processes.
# The caller owns the final Release decision; this runner only reports exact
# subprocess outcomes and fails closed on timeout/start/exit errors.
param(
    [Parameter(Mandatory = $true)]
    [string]$PythonPath,
    [Parameter(Mandatory = $true)]
    [string]$WorkingDirectory,
    [Parameter(Mandatory = $true)]
    [string]$LogRoot,
    [string[]]$Patterns = @(),
    [string]$PatternFile = "",
    [string]$SourceSha = "",
    [ValidateRange(1, 3600)]
    [int]$TimeoutSeconds = 900,
    [ValidateRange(1, 3600)]
    [int]$CleanupTimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"

function Write-JsonFile([string]$Path, [object]$Value) {
    $json = $Value | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText(
        $Path,
        $json,
        (New-Object System.Text.UTF8Encoding $false)
    )
}

function Register-ScopedArtifact(
    [string]$Python,
    [string]$Cwd,
    [string]$Path,
    [string]$ScopeId,
    [string]$RunId,
    [string]$ScopeRoot,
    [string]$Purpose,
    [string]$Lifecycle = "RETAINED"
) {
    $cleanupScript = Join-Path $Cwd "tests\tools\cleanup_work_artifacts.py"
    if (-not (Test-Path -LiteralPath $cleanupScript -PathType Leaf)) {
        throw "Cleanup tool not found: $cleanupScript"
    }
    & $Python -B $cleanupScript `
        --register-path $Path `
        --scope-id $ScopeId `
        --run-id $RunId `
        --scope-root $ScopeRoot `
        --owner "release/run_regression.ps1" `
        --purpose $Purpose `
        --lifecycle $Lifecycle | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Artifact registration failed for $Path (exit $LASTEXITCODE)"
    }
}

function Stop-ProcessTree([System.Diagnostics.Process]$Process) {
    if ($null -eq $Process) { return }
    try {
        if ($Process.HasExited) { return }
    } catch {
        # A Process object that failed before Start has no usable process tree.
        return
    }
    try {
        $Process.Kill($true)
    } catch {
        # Windows PowerShell 5.1 does not expose Process.Kill(bool).  Use the
        # OS process-tree terminator there so a timed-out cleanup cannot leave
        # a child Python process holding the report pipe or filesystem open.
        try {
            & taskkill.exe /PID $Process.Id /T /F *> $null
        } catch {
            try { $Process.Kill() } catch { }
        }
    }
    try { $null = $Process.WaitForExit(5000) } catch { }
}

function Invoke-IsolatedPattern(
    [string]$Pattern,
    [string]$PatternLog,
    [string]$Python,
    [string]$Cwd,
    [int]$Timeout,
    [string]$ScopeId,
    [string]$RunId,
    [string]$ScopeRoot
) {
    $started = [DateTime]::UtcNow
    $arguments = @(
        "-B",
        "-m", "unittest",
        "discover",
        "-s", "tests/unit",
        "-p", $Pattern,
        "-v"
    )
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Python
    $psi.WorkingDirectory = $Cwd
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.Environment["VNTEXT_ARTIFACT_SCOPE_ID"] = $ScopeId
    $psi.Environment["VNTEXT_ARTIFACT_RUN_ID"] = $RunId
    $psi.Environment["VNTEXT_ARTIFACT_SCOPE_ROOT"] = $ScopeRoot
    if ($psi.PSObject.Properties.Name -contains "ArgumentList") {
        foreach ($argument in $arguments) {
            $null = $psi.ArgumentList.Add($argument)
        }
    } else {
        # Windows PowerShell 5.1 lacks ProcessStartInfo.ArgumentList. These
        # arguments are controlled switches/patterns; quote only values that
        # need it so the same runner works under Windows PowerShell and pwsh.
        $psi.Arguments = ($arguments | ForEach-Object {
            if ($_ -match '[\s"]') { '"' + $_.Replace('"', '\\"') + '"' } else { $_ }
        }) -join ' '
    }

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    $stdoutTask = $null
    $stderrTask = $null
    $status = "START_ERROR"
    $exitCode = $null
    $errorText = $null
    try {
        if (-not $process.Start()) {
            throw "Process.Start returned false"
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $waitMilliseconds = [int]($Timeout * 1000)
        if (-not $process.WaitForExit($waitMilliseconds)) {
            $status = "TIMEOUT"
            $errorText = "Regression pattern exceeded ${Timeout}s timeout"
            Stop-ProcessTree $process
        } else {
            # Windows PowerShell 5.1 may leave the Start-Process object with
            # a stale null ExitCode until it is refreshed.
            $process.Refresh()
            $exitCode = $process.ExitCode
            $status = if ($exitCode -eq 0) { "PASS" } else { "FAIL" }
        }
    } catch {
        $status = "START_ERROR"
        $errorText = $_.Exception.Message
        Stop-ProcessTree $process
    } finally {
        $stdout = ""
        $stderr = ""
        if ($null -ne $stdoutTask) {
            try { $stdout = $stdoutTask.GetAwaiter().GetResult() } catch { $stdout = "<stdout read failed: $($_.Exception.Message)>" }
        }
        if ($null -ne $stderrTask) {
            try { $stderr = $stderrTask.GetAwaiter().GetResult() } catch { $stderr = "<stderr read failed: $($_.Exception.Message)>" }
        }
        $header = @(
            "pattern=$Pattern",
            "status=$status",
            "exit_code=$exitCode",
            "started_utc=$($started.ToString('o'))",
            "finished_utc=$([DateTime]::UtcNow.ToString('o'))",
            "timeout_seconds=$Timeout",
            ""
        ) -join [Environment]::NewLine
        $body = $header + "[stdout]" + [Environment]::NewLine + $stdout + [Environment]::NewLine + "[stderr]" + [Environment]::NewLine + $stderr
        [System.IO.File]::WriteAllText($PatternLog, $body, (New-Object System.Text.UTF8Encoding $false))
        if ($null -ne $process) { $process.Dispose() }
    }
    return [ordered]@{
        pattern = $Pattern
        status = $status
        exit_code = $exitCode
        timeout_seconds = $Timeout
        started_utc = $started.ToString("o")
        finished_utc = [DateTime]::UtcNow.ToString("o")
        log = $PatternLog
        error = $errorText
    }
}

function Invoke-RegisteredArtifactCleanup(
    [string]$Python,
    [string]$Cwd,
    [string]$RunDirectory,
    [string]$Outcome = "UNKNOWN",
    [string]$ScopeId,
    [string]$RunId,
    [string]$ScopeRoot,
    [string]$BeforeSnapshot,
    [int]$CleanupTimeoutSeconds = 120
) {
    $cleanupScript = Join-Path $Cwd "tests\tools\cleanup_work_artifacts.py"
    $cleanupOutput = Join-Path $RunDirectory "CLEANUP_COMPLETE.json"

    function Write-TerminalCleanupReport(
        [string]$Status,
        [string]$Reason,
        [Nullable[int]]$ExitCode = $null
    ) {
        $payload = [ordered]@{
            schema_version = 3
            utc = [DateTime]::UtcNow.ToString("o")
            scope_id = $ScopeId
            run_id = $RunId
            scope_root = $ScopeRoot
            outcome = $Outcome
            status = "REVIEW_REQUIRED"
            terminal_status = $Status
            ok = $false
            before = @{ path = $ScopeRoot; complete = $false }
            after = $null
            before_metrics = $null
            after_metrics = $null
            lifecycle_metrics = @{ before = $null; after = $null }
            before_inventory = $null
            run_inventory = $null
            after_inventory = $null
            created = @()
            modified = @()
            deleted = @()
            retained = @()
            protected = @()
            unknown = @()
            missing = @()
            locked = @()
            errors = @(@{
                status = $Status
                reason = $Reason
                phase = "cleanup_finalization"
            })
            metadata_issues = @()
            inventory_complete = $false
            inventory = @{
                budget = @{
                    complete = $false
                    status = $Status
                    reason = $Reason
                    timeout_seconds = $CleanupTimeoutSeconds
                }
            }
            freed_gb = 0.0
        }
        if ($null -ne $ExitCode) {
            $payload.errors[0].exit_code = $ExitCode
        }
        Write-JsonFile $cleanupOutput $payload
    }

    if (-not (Test-Path -LiteralPath $cleanupScript -PathType Leaf)) {
        Write-TerminalCleanupReport "START_ERROR" "cleanup_script_missing"
        return [ordered]@{
            status = "START_ERROR"
            exit_code = $null
            report = $cleanupOutput
            error = "Cleanup tool not found: $cleanupScript"
        }
    }

    $arguments = @(
        "-B", $cleanupScript,
        "--scope-id", $ScopeId,
        "--run-id", $RunId,
        "--scope-root", $ScopeRoot,
        "--before", $BeforeSnapshot,
        "--outcome", $Outcome,
        "--output", $cleanupOutput,
        "--inventory-timeout-seconds", [string]$CleanupTimeoutSeconds
    )
    $process = New-Object System.Diagnostics.Process
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Python
    $psi.WorkingDirectory = $Cwd
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    if ($psi.PSObject.Properties.Name -contains "ArgumentList") {
        foreach ($argument in $arguments) {
            $null = $psi.ArgumentList.Add($argument)
        }
    } else {
        $psi.Arguments = ($arguments | ForEach-Object {
            if ($_ -match '[\s"]') { '"' + $_.Replace('"', '\\"') + '"' } else { $_ }
        }) -join ' '
    }
    $process.StartInfo = $psi
    $stdoutTask = $null
    $stderrTask = $null
    $status = "START_ERROR"
    $exitCode = $null
    $errorText = $null
    try {
        if (-not $process.Start()) {
            throw "Process.Start returned false"
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit([int]($CleanupTimeoutSeconds * 1000))) {
            $status = "TIMEOUT"
            $exitCode = 124
            $errorText = "Cleanup finalization exceeded ${CleanupTimeoutSeconds}s timeout"
            Stop-ProcessTree $process
        } else {
            $process.Refresh()
            $exitCode = $process.ExitCode
            $status = if ($exitCode -eq 0) { "PASS" } else { "FAIL" }
        }
    } catch {
        $status = "START_ERROR"
        $errorText = $_.Exception.Message
        Stop-ProcessTree $process
    } finally {
        $stdout = ""
        $stderr = ""
        if ($null -ne $stdoutTask) {
            try {
                if ($stdoutTask.Wait(5000)) { $stdout = $stdoutTask.Result }
                else { $stdout = "<stdout not drained after cleanup termination>" }
            } catch { $stdout = "<stdout read failed: $($_.Exception.Message)>" }
        }
        if ($null -ne $stderrTask) {
            try {
                if ($stderrTask.Wait(5000)) { $stderr = $stderrTask.Result }
                else { $stderr = "<stderr not drained after cleanup termination>" }
            } catch { $stderr = "<stderr read failed: $($_.Exception.Message)>" }
        }
        if ($stdout -or $stderr) {
            $streamPath = Join-Path $RunDirectory "CLEANUP_PROCESS.log"
            $streamText = "[stdout]`r`n$stdout`r`n[stderr]`r`n$stderr"
            [System.IO.File]::WriteAllText($streamPath, $streamText, (New-Object System.Text.UTF8Encoding $false))
        }
        if ($null -ne $process) { $process.Dispose() }
    }

    $payload = $null
    $payloadValid = $false
    if (Test-Path -LiteralPath $cleanupOutput -PathType Leaf) {
        try {
            $payload = Get-Content -Raw -LiteralPath $cleanupOutput | ConvertFrom-Json
            $payloadValid = $null -ne $payload -and
                $payload.PSObject.Properties.Name -contains "status" -and
                $payload.PSObject.Properties.Name -contains "ok" -and
                $payload.PSObject.Properties.Name -contains "inventory_complete"
        } catch {
            $payload = $null
            $payloadValid = $false
        }
    }
    if ($status -eq "TIMEOUT" -or $status -eq "START_ERROR" -or -not $payloadValid) {
        if ($status -eq "PASS" -and -not $payloadValid) {
            $status = "FAIL"
            $exitCode = if ($null -eq $exitCode) { 1 } else { $exitCode }
            $errorText = "Cleanup process exited without a valid terminal report"
        }
        if (-not (Test-Path -LiteralPath $cleanupOutput -PathType Leaf) -or -not $payloadValid -or $status -in @("TIMEOUT", "START_ERROR")) {
            $fallbackReason = if ($errorText) { $errorText } else { "cleanup_terminal_report_invalid" }
            Write-TerminalCleanupReport $status $fallbackReason $exitCode
            $payload = $null
        }
    }
    if ($payloadValid -and $status -eq "PASS") {
        $terminal = [string]($payload.terminal_status)
        $ok = $exitCode -eq 0 -and [bool]$payload.ok -and [bool]$payload.inventory_complete -and
            [string]$payload.status -eq "PASS" -and $terminal -eq "PASS"
        if (-not $ok) {
            $status = if ($terminal -in @("TIMEOUT", "START_ERROR", "FAIL")) { $terminal } else { "FAIL" }
            $errorText = "Cleanup status: $($payload.status), terminal_status: $terminal"
        }
    }
    if ($status -eq "PASS" -and $null -eq $payload) {
        $status = "FAIL"
        $exitCode = if ($null -eq $exitCode) { 1 } else { $exitCode }
        $errorText = "Cleanup process failed without a report"
        Write-TerminalCleanupReport $status "cleanup_report_missing" $exitCode
    }
    return [ordered]@{
        status = $status
        exit_code = $exitCode
        report = $cleanupOutput
        error = $errorText
    }
}

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Regression Python runtime not found: $PythonPath"
}
if (-not (Test-Path -LiteralPath $WorkingDirectory -PathType Container)) {
    throw "Regression working directory not found: $WorkingDirectory"
}
if ($PatternFile) {
    if (-not (Test-Path -LiteralPath $PatternFile -PathType Leaf)) {
        throw "Regression pattern file not found: $PatternFile"
    }
    $Patterns = @(Get-Content -LiteralPath $PatternFile | Where-Object { $_.Trim() })
}
if (-not $Patterns -or $Patterns.Count -eq 0) {
    throw "At least one regression pattern is required"
}

$runDirectory = Join-Path $LogRoot (Get-Date -Format "yyyyMMdd_HHmmss_fff")
New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
$summaryPath = Join-Path $runDirectory "REGRESSION_COMPLETE.json"
$cleanupScript = Join-Path $WorkingDirectory "tests\tools\cleanup_work_artifacts.py"
$scopeRoot = Join-Path $WorkingDirectory "tests\golden\_work"
$scopeId = "release-regression-$([guid]::NewGuid().ToString('N'))"
$runId = "release-run-$([guid]::NewGuid().ToString('N'))"
$beforeSnapshot = Join-Path $runDirectory "SCOPE_BEFORE.json"
$cleanupOutput = Join-Path $runDirectory "CLEANUP_COMPLETE.json"
$results = [System.Collections.Generic.List[object]]::new()
$overallStatus = "PASS"
$overallExitCode = 0
$failedPattern = $null
$runStarted = [DateTime]::UtcNow
$cleanupResult = $null
$progressMessages = [System.Collections.Generic.List[string]]::new()

# These retained reports are registered before the cleanup child runs.  Give
# each path a real lifecycle immediately so registry reconciliation cannot
# mistake a future output for an unexplained historical deletion.
[System.IO.File]::WriteAllText($summaryPath, "", (New-Object System.Text.UTF8Encoding $false))
[System.IO.File]::WriteAllText($cleanupOutput, "", (New-Object System.Text.UTF8Encoding $false))

try {
    $scopeRootResolved = (Resolve-Path -LiteralPath $scopeRoot).Path
    $logRootResolved = (Resolve-Path -LiteralPath $LogRoot).Path
    if ($logRootResolved -ne $scopeRootResolved -and $logRootResolved.StartsWith($scopeRootResolved + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        Register-ScopedArtifact $PythonPath $WorkingDirectory $logRootResolved $scopeId $runId $scopeRoot "Release regression evidence root" "RETAINED"
    }
    Register-ScopedArtifact $PythonPath $WorkingDirectory $runDirectory $scopeId $runId $scopeRoot "Release regression evidence directory" "RETAINED"
    Register-ScopedArtifact $PythonPath $WorkingDirectory $summaryPath $scopeId $runId $scopeRoot "Release regression summary"
    Register-ScopedArtifact $PythonPath $WorkingDirectory $beforeSnapshot $scopeId $runId $scopeRoot "Release regression before-snapshot"
    Register-ScopedArtifact $PythonPath $WorkingDirectory $cleanupOutput $scopeId $runId $scopeRoot "Release regression cleanup report"
    foreach ($parentLog in @($env:VNTEXT_PARENT_STDOUT_LOG, $env:VNTEXT_PARENT_STDERR_LOG)) {
        if ($parentLog -and (Test-Path -LiteralPath $parentLog -PathType Leaf)) {
            Register-ScopedArtifact $PythonPath $WorkingDirectory $parentLog $scopeId $runId $scopeRoot "Canonical parent runner log" "RETAINED"
        }
    }
    & $PythonPath -B $cleanupScript --snapshot --scope-id $scopeId --run-id $runId --scope-root $scopeRoot --output $beforeSnapshot | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to capture Release regression before-snapshot (exit $LASTEXITCODE)"
    }
    for ($index = 0; $index -lt $Patterns.Count; $index++) {
        $pattern = $Patterns[$index]
        $safeName = ($pattern -replace "[^A-Za-z0-9_.-]", "_")
        $patternLog = Join-Path $runDirectory ("{0:D2}_{1}.log" -f ($index + 1), $safeName)
        $progressMessages.Add("  -> $pattern (isolated, timeout ${TimeoutSeconds}s)")
        $result = Invoke-IsolatedPattern $pattern $patternLog $PythonPath $WorkingDirectory $TimeoutSeconds $scopeId $runId $scopeRoot
        Register-ScopedArtifact $PythonPath $WorkingDirectory $patternLog $scopeId $runId $scopeRoot "Release regression pattern log: $pattern"
        $results.Add($result)
        $progressMessages.Add(("     {0} exit={1} log={2}" -f $result.status, $result.exit_code, $patternLog))
        if ($result.status -ne "PASS") {
            $overallStatus = $result.status
            $overallExitCode = 1
            $failedPattern = $pattern
            break
        }
    }
} catch {
    $overallStatus = "RUNNER_ERROR"
    $overallExitCode = 1
    $failedPattern = $null
    $results.Add([ordered]@{
        pattern = $null
        status = "RUNNER_ERROR"
        exit_code = $null
        timeout_seconds = $TimeoutSeconds
        started_utc = $runStarted.ToString("o")
        finished_utc = [DateTime]::UtcNow.ToString("o")
        log = $null
        error = $_.Exception.Message
    })
} finally {
    if ($overallStatus -eq "PASS") {
        $cleanupOutcome = "PASS"
    } elseif ($overallStatus -eq "TIMEOUT") {
        $cleanupOutcome = "TIMEOUT"
    } elseif ($overallStatus -eq "START_ERROR") {
        $cleanupOutcome = "START_ERROR"
    } elseif ($overallStatus -eq "UNKNOWN" -or $overallStatus -eq "RUNNER_ERROR") {
        $cleanupOutcome = "UNKNOWN"
    } else {
        $cleanupOutcome = "FAIL"
    }
    try {
        $cleanupResult = Invoke-RegisteredArtifactCleanup $PythonPath $WorkingDirectory $runDirectory $cleanupOutcome $scopeId $runId $scopeRoot $beforeSnapshot $CleanupTimeoutSeconds
    } catch {
        $cleanupResult = [ordered]@{
            status = "FAIL"
            exit_code = $null
            report = $cleanupOutput
            error = "Cleanup caller exception: $($_.Exception.Message)"
        }
    }
    if ($cleanupResult.status -ne "PASS" -and $overallStatus -eq "PASS") {
        $overallStatus = "CLEANUP_FAILED"
        $overallExitCode = 1
    }
    $summary = [ordered]@{
        schema_version = 1
        status = $overallStatus
        exit_code = $overallExitCode
        source_sha = $SourceSha
        python = $PythonPath
        working_directory = $WorkingDirectory
        timeout_seconds = $TimeoutSeconds
        cleanup_timeout_seconds = $CleanupTimeoutSeconds
        scope_id = $scopeId
        run_id = $runId
        scope_root = $scopeRoot
        before_snapshot = $beforeSnapshot
        started_utc = $runStarted.ToString("o")
        finished_utc = [DateTime]::UtcNow.ToString("o")
        failed_pattern = $failedPattern
        cleanup = $cleanupResult
        results = $results.ToArray()
    }
    Write-JsonFile $summaryPath $summary
    Register-ScopedArtifact $PythonPath $WorkingDirectory $summaryPath $scopeId $runId $scopeRoot "Release regression summary"
    foreach ($message in $progressMessages) {
        Write-Host $message
    }
    Write-Host "Regression summary: $summaryPath"
}

if ($overallExitCode -ne 0) {
    throw "Regression gate $overallStatus at pattern '$failedPattern'; see $summaryPath"
}
exit 0
