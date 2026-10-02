param([Parameter(Mandatory=$true)][string]$FullPythonRoot)
$ErrorActionPreference = 'Stop'
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$qaRoot = Join-Path $repo 'tests/golden/_work/qa_gui_runtime'
$runtime = Join-Path $qaRoot 'python'
foreach ($relative in @('python.exe', 'tcl/tcl8.6/init.tcl', 'tcl/tk8.6/tk.tcl', 'DLLs/_tkinter.pyd')) {
    if (!(Test-Path -LiteralPath (Join-Path $FullPythonRoot $relative))) { throw "Incomplete Python: $relative" }
}
if (Test-Path -LiteralPath $runtime) { throw "Preserve existing runtime: $runtime; use it or explicitly archive it first." }
New-Item -ItemType Directory -Path $qaRoot -Force | Out-Null
Copy-Item -LiteralPath $FullPythonRoot -Destination $runtime -Recurse
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:TEMP = Join-Path $qaRoot 'tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
& "$runtime/python.exe" -B -m pip install --disable-pip-version-check --no-cache-dir PySide6==6.8.3
if ($LASTEXITCODE -ne 0) { throw "Qt installation failed: $LASTEXITCODE" }
& "$runtime/python.exe" -B "$PSScriptRoot/run_qa_gui_workflows.py"
exit $LASTEXITCODE
