# Gate: every MemberRef (parent type, name, signature blob) the stub-built adapter emits must equal what the SAME source emits when compiled
# against the real Unity assemblies.  Source-level success is not enough (optional parameters change the emitted signature).
param([Parameter(Mandatory)][string]$StubBuilt, [Parameter(Mandatory)][string]$RealBuilt)
Add-Type -AssemblyName System.Reflection.Metadata
function Rows($path) {
  $s = [IO.File]::OpenRead($path); $pe = [System.Reflection.PortableExecutable.PEReader]::new($s)
  $md = [System.Reflection.Metadata.PEReaderExtensions]::GetMetadataReader($pe)
  $rows = foreach ($h in $md.MemberReferences) {
    $m = $md.GetMemberReference($h); $parent = ''
    if ($m.Parent.Kind -eq 'TypeReference') { $t = $md.GetTypeReference([System.Reflection.Metadata.TypeReferenceHandle]$m.Parent); $parent = $md.GetString($t.Namespace) + '.' + $md.GetString($t.Name) }
    "{0}::{1}::{2}" -f $parent, $md.GetString($m.Name), [BitConverter]::ToString($md.GetBlobBytes($m.Signature))
  }
  $pe.Dispose(); $s.Dispose(); $rows | Where-Object { $_ -match "^(UnityEngine|TMPro)." } | Sort-Object
}
$a = Rows $StubBuilt; $b = Rows $RealBuilt
$diff = Compare-Object $a $b
if ($diff) { $diff | ForEach-Object { "MISMATCH $($_.SideIndicator) $($_.InputObject)" }; exit 1 }
"PASS $($a.Count) MemberRefs identical"
