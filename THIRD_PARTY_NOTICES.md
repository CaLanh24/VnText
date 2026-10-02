# Third-party notices

The root [Apache-2.0 license](LICENSE) applies only to VNText-owned source
code. It does not grant rights to third-party software, fonts, models, game
data, or user-provided content.

## VNText-owned visual assets

Owner confirms that all project images, logos, and icons, including the Feather
artwork and SVG icons, were created by the Owner and may be distributed. This
is the Owner's rights declaration, not an independent provenance audit. It
covers project visual assets only, not third-party fonts, code, dependencies,
model weights, or game content.

## Source-code provenance decisions

Shared translation helpers transferred from the Owner's `~/.vnloc` utility
now live in `vntext/mt_translation_safety.py` and
`vntext/mt_translation_constants.py`. On 2026-10-01, the Owner confirmed
ownership of that utility and authorized distribution of those helper
portions under this project's Apache-2.0 license. This is the Owner's rights
declaration, not an independent legal audit; it resolves the rights question
for those portions unless specific contrary evidence is found. It does not
grant rights to third-party dependencies, models, game data, or other content.

The first-line comment in
`wpf_app/VNText.Studio.App/Themes/ControlStyles.xaml` identifies an older GUI
application as the source of the styles. The Owner confirms that application
is Owner-owned and authorizes distribution of these styles in VNText Studio
under the project's Apache-2.0 license. This records the Owner's declaration;
it is not an independent legal audit. Treat this as resolved for public
preparation unless specific contrary evidence is found.

`wpf_app/VNText.Studio.App/Themes/IconGeometries.xaml` also points to that
sibling project as the earlier location of the geometries. The Owner has
confirmed that all project icons were created by the Owner and may be
distributed, so this is recorded as Owner-created icon artwork rather than an
unresolved third-party asset. The comment alone does not establish third-party
authorship.

## Inter font

The WPF application embeds Inter font files under
`wpf_app/VNText.Studio.App/Assets/Fonts/`. Their included `LICENSE.txt`
identifies the Inter Project Authors and the SIL Open Font License, Version
1.1. The font files and their OFL notice remain subject to that license.

## Historical VinAI R&D model (not shipped)

Historical research used `vinai/vinai-translate-en2vi-v2`; it is not a
current VNText product route and its weights are not tracked or shipped.
Anyone who separately uses or distributes that model must review its upstream
license; the VNText code license does not cover third-party weights.

## Current CT2/OPUS model

The current model repository is `dekthedev/opus-mt-en-vi-ct2-int8`; its model
card declares Apache-2.0, and the base `Helsinki-NLP/opus-mt-en-vi` card also
declares Apache-2.0. See the [converted model card](https://huggingface.co/dekthedev/opus-mt-en-vi-ct2-int8)
and [base model card](https://huggingface.co/Helsinki-NLP/opus-mt-en-vi). The
converted repository's immutable revision is
`c22547827b876e8ee939d6a9363965e5c9f769e1`. The local CT2 cache's 10-file tree
matched its recorded LFS SHA-256 values or Git blob IDs in a read-only check;
this establishes provenance for that local cache only, not a packaged Setup.
The app downloader pins that revision, and the publisher derives the model
manifest's revision from the staged source. This identifies the intended
upstream snapshot; it does not by itself prove that a particular Setup's model
files match that snapshot. Audit the final bundled files and applicable license
notices before distribution. Model weights are not tracked in this repository.

The currently inspected local model tree had ten files and no standalone
`LICENSE` or `NOTICE` file. The publisher copies that tree into
`app/worker/models` and records the identifier `Apache-2.0` in
`MODEL_MANIFEST.json`; that identifier is not itself the license text. The
publisher source now copies the root `LICENSE`, `NOTICE`, this file, and the
CTranslate2 MIT license into `app/licenses/`, and its layout check requires
those files. The focused Setup package test verifies that these entries survive
packaging. The immutable Hugging Face model revision `c22547827b876e8ee939d6a9363965e5c9f769e1` above is the model-file provenance; it is not a claim about Setup contents or model redistribution rights. No private review root or historical payload inventory is required by this public clone. Every future Setup needs its own exact payload inventory and redistribution review; no release or legal PASS is inferred here.

## Dependencies

### Bundled CPython

The portable worker includes CPython and preserves its original `LICENSE.txt`
under `app/worker/python/`. Packaging refuses a base interpreter whose license
file is missing before replacing a staged runtime. The portable layout removes
development/test directories, adds `sitecustomize.py`, and changes the bundled
`encodings/__init__.py` and `site.py` bootstrap modules to disable bytecode
writes; guarded bootstrap modules are also copied into the standard-library
ZIP. These are packaging changes, not a replacement license for Python or its
third-party components. Verify the exact runtime and notices in the final Setup.

### Python packages

#### FMOD vendor binary exclusion (Owner decision, 2026-10-02)

The p1451 review payload includes
`app/worker/.venv/Lib/site-packages/fmod_toolkit/libfmod/Windows/x64/fmod.dll`.
The `fmod_toolkit` 0.1.3 helper's MIT metadata/license does not establish
redistribution permission for the separate FMOD vendor binary; that permission
remains UNKNOWN. Owner requires excluding the vendor `fmod_toolkit/libfmod`
subtree from the staged public worker environment, while preserving the Python
helper and its MIT notice. The pruner and pre-Setup layout guard enforce this
boundary without modifying developer dependencies. VNText's Unity text route
does not use audio samples/export; audio export is outside the product scope.
Private review-Setup inventories and payload reports are intentionally omitted;
they are not needed to clone, build or test this source and establish no current
payload or general redistribution right. Review each future Setup from its own
exact payload while preserving the vendor exclusion and license obligations
above.

Python requirements use minimum-version constraints, not locked versions. A
read-only walk of installed `Requires-Dist` metadata in `.venv` on 2026-10-01
(Python 3.12.10) followed the six default requirements with current-platform
markers and `extra` unset. It found 6 direct packages and 41 transitives (47
total), all installed. This is a point-in-time developer-environment graph,
not a lockfile or promise of what a later install resolves. It excludes build
requirements and optional extras, and does not inventory the Setup payload.
Six transitives lack both `License-Expression` and a non-unknown `License`
field: colorama, lz4, markdown-it-py, mdurl, safetensors, and tokenizers. All
six have license classifiers; five have candidate license files in the local
distribution metadata. Their currently installed versions were checked against
versioned upstream license files:

- colorama 0.4.6 — BSD-3-Clause ([upstream license](https://github.com/tartley/colorama/blob/0.4.6/LICENSE.txt)).
- lz4 4.4.5 — BSD-3-Clause ([upstream license](https://github.com/python-lz4/python-lz4/blob/v4.4.5/LICENSE)).
- markdown-it-py 4.2.0 — MIT; its distribution also includes the separate
  MIT notice for markdown-it ([project license](https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/LICENSE),
  [markdown-it notice](https://github.com/executablebooks/markdown-it-py/blob/v4.2.0/LICENSE.markdown-it)).
- mdurl 0.1.2 — MIT, including the separate Joyent Node.js `url` notice in its
  license file ([upstream license](https://github.com/executablebooks/mdurl/blob/0.1.2/LICENSE)).
- safetensors 0.8.0 and tokenizers 0.23.2 — Apache-2.0 ([safetensors license](https://github.com/safetensors/safetensors/blob/v0.8.0/LICENSE),
  [tokenizers license](https://github.com/huggingface/tokenizers/blob/v0.23.2/LICENSE)).

#### Four pinned dependencies — upstream license sources

The upstream tags and license-source hashes below identify the pinned versions;
they do not describe or prove any installed Setup payload. The exact-tag root
listings have LICENSE but no root NOTICE. The shared `app/licenses/APACHE-2.0.txt` supplies the Apache terms
for FlatBuffers, SentencePiece and Tokenizers; do not duplicate that text merely
for adjacency. The existing `app/licenses/python/ctranslate2-MIT.txt` preserves
the SYSTRAN/OpenNMT copyright and permission text of the exact CT2 license
(whitespace differences only), and is not replaced or duplicated.

| Component | Exact primary tag / commit | Root LICENSE SHA-256 (upstream UTF-8 bytes) |
| --- | --- | --- |
| CTranslate2 4.8.1 | [v4.8.1](https://github.com/OpenNMT/CTranslate2/blob/v4.8.1/LICENSE) / `0d8bcd362ac75ef860ef161d6f0efad0ae439ff0` | `54aa79d9fe3c09e67a16dcd95b9e88676405a6ec174efda31036983cf7672ecb` |
| FlatBuffers 25.12.19 | [v25.12.19](https://github.com/google/flatbuffers/blob/v25.12.19/LICENSE) / `7e163021e59cca4f8e1e35a7c828b5c6b7915953` | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| SentencePiece 0.2.2 | [v0.2.2](https://github.com/google/sentencepiece/blob/v0.2.2/LICENSE) / `e0cce7d37b065b5140349dbe12c6bcf6192fdd78` | `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30` |
| Tokenizers 0.23.2 | [v0.23.2](https://github.com/huggingface/tokenizers/blob/v0.23.2/LICENSE) / `88a4498ad4ea1a9487b0a9b0ff881383fd5a06a3` | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |

SentencePiece's explicit vendored components require separate copyright texts:
[darts_clone](https://github.com/google/sentencepiece/blob/v0.2.2/third_party/darts_clone/LICENSE)
(Susumu Yata, BSD), [esaxx](https://github.com/google/sentencepiece/blob/v0.2.2/third_party/esaxx/LICENSE)
(Daisuke Okanohara, MIT), and [protobuf-lite](https://github.com/google/sentencepiece/blob/v0.2.2/third_party/protobuf-lite/LICENSE)
(Google, BSD). Their notice texts are now retained under `release/licenses/`
and copied/required as `app/licenses/python/sentencepiece-darts_clone.txt`,
`sentencepiece-esaxx.txt`, and `sentencepiece-protobuf-lite.txt`. They were NOT
in the existing NoFMOD Setup; only a later verified rebuild can establish their
presence in a new Setup. Darts_clone drops two trailing line spaces only for
Git whitespace checks; all copyright/terms remain verbatim. Upstream and local
text hashes and commands are in
`tests/golden/_work/notices-stage1/upstream-evidence.json` and the stage-1 report.

Specific unresolved CT2 binary notice gap: the actual wheel/NoFMOD payload also
contains `ctranslate2/cudnn64_9.dll` and `ctranslate2/libiomp5md.dll`. The
[exact Windows wheel build script](https://github.com/OpenNMT/CTranslate2/blob/v4.8.1/python/tools/prepare_build_environment_windows.sh)
copies these from NVIDIA cuDNN and Intel oneAPI installations; neither the
CT2 wheel's license contents nor the exact-tag root supplies their vendor
license/notice text. A subsequent bounded check on 2026-10-02 identified the
actual NVIDIA DLL as cuDNN 9.10.2.21, matching the script's cuDNN 9.10.2 input.
The [version-matched NVIDIA agreement](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.10.2/reference/eula.html)
designates runtime .dll files as distributable, subject to the Agreement's
license grant and distribution requirements and the cuDNN supplement's NVIDIA
GPU application scope. This is conditional permission, not Owner assent or
unconditional redistribution clearance. The official agreement article and
[acknowledgements](https://docs.nvidia.com/deeplearning/cudnn/backend/v9.10.2/reference/acknowledgements.html)
are preserved under release/licenses/cudnn-9.10.2-*.html and copied/required in
app/licenses/native/. Copyright, binary redistribution conditions, disclaimers
and the Facebook patent grant are preserved, including upstream article text.

The exact Intel input is the official [oneAPI Base Toolkit 2025.3.0.372
offline package](https://registrationcenter-download.intel.com/akdlm/IRC_NAS/1f18901e-877d-469d-a41a-a10f11b39336/intel-oneapi-base-toolkit-2025.3.0.372_offline.exe)
(2,691,346,600 bytes; SHA-256
`f4dde6e5ea732b1624f0a50df546401712bccdf45766c9a23b0865f95863f541`). Its
compiler `credist.txt`, line 41, explicitly lists
`<installdir>/bin/libiomp5md.dll`. The DLL's exact 1,614,192-byte SHA-256
`982233366b0afcda1e0f55a0b134097e35b779613f54ddb69e685e6cd06b755f` matches
`app/worker/.venv/Lib/site-packages/ctranslate2/libiomp5md.dll` in the inspected
Setup payload inventory. Intel file metadata reports copyright 1997-2025 and
FileVersion 20250910. This establishes the package's redistributable
designation for that exact file; the DLL is governed by Intel's terms, not the
project's Apache-2.0 or CTranslate2's MIT license.

The bundled compiler `LICENSE.rtf` is retained verbatim. `credist.txt` says its
associated Developer Tools Agreement is Version April 2023, while that exact
RTF and the toolkit-level `license.txt` identify Version August 2024. Intel's
[official EULA page](https://www.intel.com/content/www/us/en/developer/articles/license/end-user-license-agreement.html)
states that the controlling agreement is the one included with the software
package. The older `credist.txt` reference is preserved as a package-document
discrepancy; it is not replaced with the toolkit-level license or silently
rewritten. Source and retained-text hashes are recorded in
`release/licenses/intel-2025.3-provenance.md`.

This designation is conditional redistribution, not blanket legal clearance or
Owner assent. Under the bundled Developer Tools Agreement §2.1(D), the
redistributable may only be distributed as part of Your Product; Intel-provided
executable code must remain executable code and must be distributed subject to
a license agreement prohibiting reverse engineering, decompilation and
disassembly (§2.1(D)(2)). Section 2.1(D)(4)(i) assigns product support and
other customer obligations to the distributor; (iv) requires compliance with
restrictions in the accompanying text files and §3; and (v) allocates specified
indemnity obligations. Section 7.3 requires the Agreement's Section 7 liability
limitations to be conveyed to and made binding on customers acquiring the
redistributable. Copying vendor notices does not implement or prove those
customer-license terms.

Historical statement, recorded before 2026-10-03: This task does not add,
execute or accept an Intel EULA or change the product's customer license.

### Owner decision — Intel Setup acceptance, 2026-10-03

The Owner accepts the applicable Intel oneAPI terms, including the distributor
obligations recorded above, for the identified Intel Redistributables. Setup
now requires a separate explicit acceptance of customer terms before writing
to the selected install folder. Those terms convey Intel's §7.1 and §7.2
liability limitations as binding on customers under §7.3 and prohibit reverse
engineering, decompilation, and disassembly only for the Intel Redistributables.
They do not restrict VNText Studio source code, which remains under Apache-2.0.
The original bundled Intel EULA is viewable in Setup before acceptance and is
retained in the installed notices.

Owner authorization for the eventual Calanh24/VnText public target applies only
after all mandatory release gates pass. A prior Worker-phase restriction was
limited to that handoff and does not narrow the Owner's task-wide authorization.
This notice does not establish blanket clearance for other dependencies, model
weights, data, or legal issues.

The exact compiler, OpenMP Runtime, and oneTBB license/third-party texts from
the same 2025.3 bundle are retained under `release/licenses/intel-2025.3-*` and
copied into `app/licenses/native/`; the publisher and layout guard require all
six files. Their source hashes, the four CUP archive hashes, package warning,
and exact extraction/hash commands are in the provenance report. No Intel
binary, dependency, or runtime behavior was changed. This notice update does
not close license acceptance, customer-license implementation, or other
third-party/model-rights questions.

Requirements remain unlocked, and every final Setup needs its own exact
payload inventory. Dependencies remain under their respective upstream terms;
this repository does not relicense them.

| Declared in | Distribution (observed version; location) | License evidence |
| --- | --- | --- |
| `requirements.txt` | UnityPy 1.25.3 (inherited base Python) | `License` metadata contains MIT text; MIT classifier; `LICENSE` file. |
| `requirements.txt`, `release/requirements-build.txt` | PySide6 6.8.3 (inherited base Python) | `License` metadata: `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`; license classifiers include LGPLv3, GPLv2, GPLv3 and other/proprietary. |
| `requirements.txt` | ctranslate2 4.8.1 (inherited base Python) | `License=MIT`; bundled text is `app/licenses/python/ctranslate2-MIT.txt` ([upstream v4.8.1 license](https://github.com/OpenNMT/CTranslate2/blob/v4.8.1/LICENSE)). |
| `requirements.txt` | flatbuffers 25.12.19 (inherited base Python) | `License=Apache 2.0`; standard Apache-2.0 text is bundled as `app/licenses/APACHE-2.0.txt` ([upstream license](https://github.com/google/flatbuffers/blob/v25.12.19/LICENSE)). |
| `requirements.txt` | sentencepiece 0.2.2 (inherited base Python) | `license_expression=Apache-2.0`. |
| `requirements.txt` | transformers 5.17.0 (`.venv`) | `License=Apache 2.0 License`; `LICENSE` file. |
| `requirements.txt` | huggingface_hub 1.31.0 (`.venv`) | `License=Apache-2.0`; `LICENSE` file; Apache classifier. |
| `release/requirements-build.txt` | PyInstaller 6.22.0 (inherited base Python) | `License` metadata says GPLv2-or-later with a special exception for building and distributing non-free programs; GPLv2 classifier; `COPYING.txt`. |
| `release/requirements-build.txt` | Pillow 12.3.0 (inherited base Python) | `license_expression=MIT-CMU`; `LICENSE` file. |

For the 41 resolved default transitives, license metadata fields and local
license-file leads were checked as above; these are not a legal determination
or a bundled-payload inventory. Argos and MiniSBD are no longer declared
dependencies or runtime features. The release pruner continues to exclude
stale copies from an inherited development environment; the exact Setup
NoFMOD review payload has a separate retained inventory; the notice/installer
metadata changes described above still require a new build and separate audit.

Legal applicability and redistribution approval remain separate from the
p1451 exact payload/license inventory. WPF project files contain
no NuGet `PackageReference`; this does not inventory the .NET runtime or SDK.
