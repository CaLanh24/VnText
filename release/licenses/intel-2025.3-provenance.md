# Intel oneAPI 2025.3 runtime notice provenance

Checked 2026-10-02 for the `libiomp5md.dll` already present in the inspected
1.45.0 Setup inventory. This records package identity, redistribution
designation, and notice-copy provenance. It is not EULA acceptance or blanket
legal clearance.

The downloaded package and extracted evidence were held in the task-owned
temporary scope. Its machine-specific path is not recorded in this tracked
report.

## Official package and DLL identity

- Source: [Intel oneAPI Base Toolkit 2025.3.0.372 offline package](https://registrationcenter-download.intel.com/akdlm/IRC_NAS/1f18901e-877d-469d-a41a-a10f11b39336/intel-oneapi-base-toolkit-2025.3.0.372_offline.exe)
- Downloaded file: `intel-oneapi-base-toolkit-2025.3.0.372_offline.exe`, 2,691,346,600 bytes, SHA-256 `f4dde6e5ea732b1624f0a50df546401712bccdf45766c9a23b0865f95863f541`.
- Extracted DLL: `openmp\_installdir\compiler\2025.3\bin\libiomp5md.dll`, 1,614,192 bytes, SHA-256 `982233366b0afcda1e0f55a0b134097e35b779613f54ddb69e685e6cd06b755f`. PE metadata: Intel Corporation; copyright 1997-2025; FileVersion `20250910`.
- Existing Setup inventory `../VNText_Public_1.45.0_Vendor/Updates/evidence/setup-payload-inventory.json` parses to `app/worker/.venv/Lib/site-packages/ctranslate2/libiomp5md.dll`, with the same size and SHA-256. The JSON was parsed with `ConvertFrom-Json`; it was not searched as minified text.

Intel's compiler `credist.txt`, line 41, names the exact component:

```text
<installdir>/bin/libiomp5md.dll
```

This is a PASS for the package's redistributable designation of this file. The
DLL is an Intel component under Intel's terms, not Apache-2.0 or CTranslate2
MIT.

## Bundle archives and documents

All four CUP archives are from the same downloaded toolkit bundle. Hashes below
are SHA-256 of the extracted `cupPayload.cup` files.

- `intel.oneapi.win.compilers-common-runtime,v=2025.3.0+640\cupPayload.cup`: 80,311,476 bytes; SHA-256 `94cfa4b3a3447e515224b58c24def129a7156ac4a64f5969dadb38b390f94382`.
- `intel.oneapi.win.cpp-dpcpp-common,v=2025.3.0+640\cupPayload.cup`: 184,409,443 bytes; SHA-256 `2df178f3e5a12d0a4c55d526a0bc55a094829fbf9e1223a7a9117fcd8f4239aa`.
- `intel.oneapi.win.openmp,v=2025.3.0+640\cupPayload.cup`: 56,179,144 bytes; SHA-256 `9605885e79f82d668c239871894ab42603ba698f85776da1a7d04922f6a325ad`.
- `intel.oneapi.win.tbb.runtime,v=2022.3.0+380\cupPayload.cup`: 5,515,661 bytes; SHA-256 `bcfb40a888c0326d99afdd52930e423685fbb848acfb399ab3a8226931e4bc35`.

The exact vendor text files were copied byte-for-byte into `release/licenses/`;
source and retained hashes match:

- `intel-2025.3-cpp-eula.rtf`: 262,117 bytes; SHA-256 `4e96f3006c9d51b38561f9802da896480dc48e7703a76c206292bf6d6d11a781`.
- `intel-2025.3-credist.txt`: 18,655 bytes; SHA-256 `396a881181eceee56bbc2468d52d2ffd5fa313aa0b4b9ec509d5dd35872ab554`.
- `intel-2025.3-compiler-third-party-programs.txt`: 36,937 bytes; SHA-256 `a81491a0243fa1d072aa636c890a6dd082ca403aca4681672cf6f69d3d516f79`.
- `intel-2025.3-openmp-third-party-programs.txt`: 31,578 bytes; SHA-256 `f8ce918fe7311ce279e68380a2e233f8a42b1cd3dda8f4c48d6de97a0255c1d7`.
- `intel-2025.3-tbb-license.txt`: 4,180 bytes; SHA-256 `4229ebf297195a64279a99566431731c411f744a34e1213a5b1e69a8fa286ea1`.
- `intel-2025.3-tbb-third-party-programs.txt`: 19,503 bytes; SHA-256 `1f6de0bd498c04c9283c6306379e2db2492e1c4e7d2b248c8de0e8fe9124cd03`.

The compiler EULA source is `compiler-docs\_installdir\compiler\2025.3\share\doc\compiler\licensing\c\LICENSE.rtf`; its complete original RTF bytes are retained. The toolkit-level `selected\license.txt` is a separate 25,086-byte file with SHA-256 `361b0c0120863fc90141eb85e737047261d683545426a51a00a87021df554fca`; both it and the compiler RTF identify the August 2024 Developer Tools Agreement.

## Conditional terms and version note

The `credist.txt` preamble calls its associated Developer Tools Agreement
Version April 2023. The exact compiler `LICENSE.rtf` and toolkit-level license
identify Version August 2024. Intel's [official EULA page](https://www.intel.com/content/www/us/en/developer/articles/license/end-user-license-agreement.html)
states that the controlling agreement is the one included with the software
package. The older `credist.txt` version reference is retained as a package
document discrepancy; the compiler RTF is preserved and used as the compiler
license source rather than replacing it with the toolkit-level text.

Under the bundled Agreement §2.1(D), redistribution is limited to the listed
Redistributables and only as part of the distributor's product. Intel-provided
executable code must remain in executable form and, under §2.1(D)(2), must be
distributed subject to a license agreement prohibiting reverse engineering,
decompilation, and disassembly. Section 2.1(D)(4)(i) assigns product support
and other customer obligations to the distributor; (iv) requires compliance
with restrictions in the associated text files and §3; and (v) allocates
specified indemnity obligations. Section 7.3 requires the Agreement's Section
7 liability limitations to be conveyed to and made binding on customers
acquiring the Redistributables.

Copying these notices does not implement those customer-license conditions.
Historical status as of 2026-10-02: this task added no product EULA, executed
no EULA, and recorded no Owner assent or blanket legal clearance. On
2026-10-03, the Owner accepted the Intel oneAPI terms for the identified
Redistributables, including distributor obligations. That decision does not
implement customer-facing license conditions or constitute blanket legal
clearance. No Intel binary, dependency, or runtime behavior was changed.

## Extraction and verification record

- Acquisition result supplied in the task packet: `curl` exit 0. Its exact
  command line was not retained; the official URL, resulting file size, and
  package SHA-256 are recorded above.
- Extraction tool: existing 7-Zip only. The outer PE reported
  `Checksum error`; extraction of the relevant nested CUP/ZIP payloads returned
  exit 0 / `Everything is Ok`. The prior exact extraction command lines were
  not retained. This warning is preserved; it is not a signature or package
  authenticity PASS.
- Hash command used on the package, CUP archives, DLL, and source documents:
  `Get-FileHash -Algorithm SHA256 -LiteralPath <exact path>`.
- Setup inventory comparison: parse `setup-payload-inventory.json` with
  `Get-Content -Raw -LiteralPath <path> | ConvertFrom-Json`, then select the
  `files` property ending in `libiomp5md.dll`.
- Focused command: `.\.venv\Scripts\python.exe tests/tools/run_with_cleanup.py -- .\.venv\Scripts\python.exe -B -m unittest discover -s tests/unit -p "test_setup_package.py" -k test_project_notices_copy_hash_and_missing_source -v`.
- Test result: child exit 0; 1 test, 0 failures/errors/skips/warnings. Output:
  `NOTICE_COPY: 15 exact copy/hash matches; 15 missing-input rejections`.
- The wrapper recorded Git HEAD `fc956146a159d66f14408ae1817c0178f676024b`;
  the focused test ran against the current modified working tree.
- Wrapper exit 1; cleanup is `REVIEW_REQUIRED` because non-exempt project size
  remained 1,074,091,668 bytes against the 1,073,741,824-byte limit (349,844
  bytes over). The four registered test-scope artifacts were deleted; the
  cleanup report records zero blocked roots, locked roots, or errors. No
  unrelated files were changed to reduce the project size.
- Retained focused-run and cleanup evidence: `tests/golden/_work/canonical-run-675c361f185b4770af6783d97be1705b.md`.
- No Setup compile/build, publish, install, or EULA acceptance was run.
