# Lifecycle gate for the Unity TMP adapter: builds tests/unity_adapter_lifecycle (the REAL Startup.cs against a fake Unity/TMP engine) and runs it.
# Optional -BaselineSource <Startup.cs> runs a previous adapter source the same way (expected to FAIL the re-apply checks).
param([Parameter(Mandatory)][string]$Dotnet, [Parameter(Mandatory)][string]$ArtifactsPath, [string]$RestoreConfig = "", [string]$BaselineSource = "")
$project = Join-Path $PSScriptRoot "..\unity_adapter_lifecycle\UnityAdapterLifecycle.csproj"
$extra = @(); if ($RestoreConfig) { $extra += "-p:RestoreConfigFile=$RestoreConfig" }
if ($BaselineSource) { $extra += "-p:StartupSource=$BaselineSource" }
& $Dotnet build $project -c Release --artifacts-path $ArtifactsPath @extra | Out-Null
if ($LASTEXITCODE -ne 0) { throw "lifecycle harness build failed" }
$dll = Get-ChildItem (Join-Path $ArtifactsPath "bin") -Recurse -Filter UnityAdapterLifecycle.dll | Select-Object -First 1
& $Dotnet $dll.FullName
exit $LASTEXITCODE
