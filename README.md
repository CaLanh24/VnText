# VNText Studio

VNText Studio is a Windows desktop tool for extracting game text, translating
or importing CSV, and fail-closed patching. The supported product translation
route is local CT2/OPUS-MT only. The source has file-level tests for selected
Unity resources, Naninovel scripts, and Ren'Py loose source; these do not prove
compatibility with every game, version, or gameplay path.

Source version: `1.45.0` (stable release candidate; not yet published).

`README.md` is the canonical repository README. `README_VI.txt` is a
Vietnamese companion, while the fixture READMEs under `tests/` describe test
policy and are not product setup documents.

## Clone and setup

The tracked repository contains source, tests, contracts, and build scripts. It
does not include game data, user output, Python virtual environments, model
weights, Setup binaries, caches, logs, `DEV_RUN`, or `_work` artifacts.

Windows prerequisites:

- Git
- Python 3.11+ with `python` on `PATH`
- .NET 8 SDK for the WPF development build
- .NET 10 SDK under `DEV_RUN\dotnet-sdk-10` for the full WPF workflow test and
  Release publisher; it is not included in source. The WPF test can use an
  alternate DEV_RUN root via `VNTEXT_DEV_RUN_ROOT`.
- network access only when installing public Python/NuGet dependencies or
  downloading an explicitly approved build tool or the CT2 model on first
  translation when no local/bundled model is available

```powershell
git clone <repository-url> VNTextStudio
Set-Location VNTextStudio
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

These direct Python/PowerShell commands create a checkout-local `.venv` and
install the public Python dependencies. Do not copy `.venv`, models, Release
files, or game data from another clone.
The product and Python preview UI use the CT2/OPUS-MT route. The final Setup
payload still requires its own dependency audit.
The source repository does not include model weights. When the model is missing,
the app downloads the CT2/OPUS-MT model from Hugging Face on first translation;
set `VNTEXT_CT2_NO_DOWNLOAD=1` to disable that download and provide the model
locally. A bundled Setup may already contain the model.
The root `LICENSE` covers VNText-owned source only; see
`THIRD_PARTY_NOTICES.md` for third-party notices.

## Development and tests

Run focused Python tests through the scoped cleanup wrapper:

```powershell
.\.venv\Scripts\python.exe tests/tools/run_with_cleanup.py -- .\.venv\Scripts\python.exe -B -m unittest discover -s tests/unit -p "test_worker_protocol.py" -v
```

Build a development WPF executable into the ignored `DEV_RUN` directory and
run the required worker smoke:

```powershell
dotnet publish wpf_app\VNText.Studio.App\VNText.Studio.App.csproj `
  -c Release -r win-x64 --self-contained false -o DEV_RUN
.\DEV_RUN\VNText.Studio.App.exe --smoke-worker
```

The DEV executable is not a Release approval. Use `TEST_MATRIX.md` and
`CONTRACTS.md` to select the regression gates for a change.

## External fixtures and Release

Game and Release paths are supplied explicitly and are never inferred from a
developer's drive layout:

- `VNTEXT_GAME_FOLDER` — read-only source game for optional Unity E2E tests.
- `VNTEXT_RELEASE_ROOT` — external Release root for test helpers.
- `VNTEXT_RELEASE_PACKAGE` — external package used by parity helpers.
- `VNTEXT_MOCKUP_REFERENCE` — optional local image for the mockup measurement
  tool.

The final Release publisher uses the sibling `VNText_Studio_Release` by
default. `-ReleaseRoot` is only for isolated test/RC output:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\release\publish.ps1 `
  -WpfUpdateVersion <newer-version> `
  -GitHubOwner Calanh24 `
  -GitHubRepository VnText
```

Release publication requires the approved runtime/model prerequisites and
separate verification. Never place game data, model weights, user CSVs,
`VNText_Output`, or Release output in this repository.

The product supports only the CT2/OPUS-MT translation route. The specific
file-level engine paths listed above do not imply support for every game or a
complete gameplay path. VinAI is not included in the app or installer.

## Downloads and updates

The intended user download is `Setup.exe` from a verified GitHub Release; this
source-preparation snapshot does not claim a published release. The WPF source
can check stable public GitHub Releases and offer only verified WPF-only
packages, but Setup remains safely unconfigured until the publisher is given
both explicit `-GitHubOwner` and `-GitHubRepository` values. No account or
repository is guessed or embedded by default. The adjacent local `Updates`
feed remains a separate Owner/development preview, not the public channel.
Releases without an applicable WPF package or with a mismatched install
baseline route to the official Setup/Releases page. Code and mocked tests do
not establish real installed public-GitHub acceptance; that remains NOT
VERIFIED. The legacy Python one-EXE updater is separate and is not the
supported WPF update path.

## Product boundary and licensing

The workflow is:

1. Extract text into a package.
2. Translate/import the package CSV.
3. Validate and patch a copy of the game.
4. Reopen patched targets and verify the result.

Only entries with a proven locator, writer, and read-back route are promoted
to the main patch ledger. Other candidates remain explicitly review-only,
extract-only, or unsupported. A generic Unity capability is not a promise
that every game's custom binary or runtime behavior is supported.

Legacy game-specific profiles and corpora are not migrated or auto-applied.
Re-extract with the generic pipeline or import a user-owned CSV/glossary;
legacy profile or external-locator metadata is rejected fail-closed with an
explicit reason.

Apache-2.0 applies only to VNText-owned source in this repository. It does
not license game data, fonts, model weights, or dependencies. Optional model
and dependency distribution remains subject to the notices and upstream
licenses in `THIRD_PARTY_NOTICES.md`; obtain any required legal decision
before redistributing those materials.
