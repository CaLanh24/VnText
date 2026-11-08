# Current checkpoint — 2026-11-09 translation workflow + single-EXE patch

## Authority
Owner batch: (1) image workspace only in Translate, reuse Extract OCR, automatic image translation, minimal UI; (2) ONE editable `translation.csv`; (3) themed completion dialog + sound once; (4) ONE self-contained patch EXE with the VNText icon and installer UI matching the app. Local only: no push, release, version or tag change; public 0.1.17 immutable. Game original/saves/Owner AppData untouched. Same DEV agent72329c3d / session76922e45 / sole writer (Root stopped mutating).

## Source
Local HEAD `13ade53fb3d08f5532086770b44d81d9c8f7bdea` (clean at gates) = Root WIP `d8c8a20`/`b0fb507`/`8a08764` + DEV hardening commits `3b200d5`, `8645dc0`, `7b3cfce`, `18f7d8b`, `7549c46`, `c8a67e3`, `13ade53`. Epoch `epoch-20261109-017-single-exe7` (ordinary standing transitions, ordinals 16-22; each costs ~50 MB of protected history).

## What DEV found and fixed in Root's WIP
- Patch bundle: the C# reader used a 56-byte footer and compared 16 chars of a 17-byte magic, so no bundle was ever recognised. `EmbeddedPatch.cs` rewritten: 57-byte footer, windowed read (archive never copied), SHA-256 of the whole payload before any entry, caps (100,000 entries, 64 GiB total, per-entry size must match the declared size exactly, path allow-list, reparse refusal under the storage root), free-space check, EVERY launch restores payload/manifest from the verified archive and deletes planted files, one installer per payload (mutex held for the process lifetime), scripted use never blocks on a dialog. `patch_bundle.py`: same caps, duplicate-name refusal, `verify_bundle`, `read_bundle_file`.
- Worker hand-off: failed bundling is an honest error, the `.patch-build` stage is always removed, engines without an installer manifest keep loose delivery.
- Image-only packages: the text translator failed on "no data rows" and never reached images; the worker now goes straight to the cached OCR images, and the Translate button is enabled for OCR-only packages.
- Completion dialog: the superseded-scan guard checked `_runningTask` after it was cleared; now a flag set during the terminal event suppresses dialog+sound for a stale automatic analysis (tested: exactly one notice per finished/failed analysis, none for a superseded one).
- Installer UI restyled to app tokens (canvas/surface/ink/blue, About-banner green, inline status banners, busy bar, hover/focus, in-form uninstall confirmation); SmokeWorker understands the single EXE. `report.json` write retries a transient Windows PermissionError.
- Stale tests updated (positive-only image list, new copy/catalog, single-EXE delivery); real-CT2 cancel test `test_worker_protocol_cancel_during_real_ct2_call_acknowledges_and_exits` is a timing race (20 ms window): same code passed 1 of 2 direct runs and failed in two wrapper runs; not touched by this batch.

## Gate verdicts (canonical wrapper, child exit 0 each; wrapper `REVIEW_REQUIRED` is protected epoch history only)
- WPF `test_wpf_workflow` 37/37 at `13ade53` (wrapper status PASS).
- gA at `c8a67e3`: 192 tests (WPF, unified document, image batch, patch bundle + installer with the real self-contained stub, CSV API, packages, extract, resources...) OK, 2 skips. Python after that commit unchanged.
- gB at `c8a67e3`: patch/worker family 109 tests, 1 failure = the timing-race test above; everything else OK (patch input safety, delivery, worker tasks/translate).
- Runtime on the REAL self-contained stub with a bundled payload on an inert Ren'Py-shaped fixture (`test_patch_bundle`): install, uninstall refusal of a modified file, tampered cache and manifest restored from the verified archive, planted file removed, corrupted EXE refused, ONE file delivered.
- Worker smoke (cancel, extract, translate, patch to a single EXE, crash) ok.

## Candidates (new outputs; batch5 candidate and its DEV exe untouched)
- App DEV build `C:/v/DEV_RUN/bootstrap-build/VNText.Studio.App.exe` sha256 `55ff11c23e78edf99d4f332398ee2f1b162d29952bcccdb6119905b15b60262c`, assembly `5699ea84…81cb`, source `13ade53` clean, smoke ok. Uses the repo worker (UPDATED python) and `release/patch_installer_publish/VNTextPatchInstaller.exe` (self-contained stub, sha256 `1135edaa3d3269f0986891cce46b627dd5b820859badd7a0a4c3a2f48b37cf0b`). The previous batch5 DEV build is preserved byte-identical at `DEV_RUN/bootstrap-build-168b655-preserved` (exe `ca37c3f3…`).
- Patch EXE fixture `C:/vnrg/candidate-single-exe/VNText-VietHoa.exe` (68,310,187 B, sha256 `3a63afe666c2875f3957df32f5e7c0c78db03e310ae8bec4a6289a1feb34a5ee`) + inert game folder `inert-game` + `DEV_CANDIDATE.json`.
- Setup candidate with the updated worker: NOT built (budget). Prepared and tested approach: `C:/vnrg/evidence/batch5/build_candidate2.py` (streams the published payload, syncs worker python from the clean tree, replaces the app exe, Uninstall.exe, RELEASE.json and the patch-installer stub). It needs ~650 MB transient + 289 MB retained; combined is 6.54 GB against the 6.71 GB cap (abort line 6.66 GB), mostly 4.7 GB of protected epoch history. Precondition to run: dispose Root's consumed `DEV_RUN/batch5-candidate` (289 MB) and the preserved old DEV build, or raise the cap for one run.

## Open
- Native Root/Brain review: checklist `C:/vnrg/evidence/batch5/native-checklist-single-exe.md`. NOT claimed by DEV: any native PASS, installer visual match, small-window layouts, sound.
- Limits: installer font is Segoe UI (no embedded Inter); the PowerShell final-cleanup helper of Setup's uninstall keeps a plain message box; Patch_Viet_Hoa folders from older builds are not deleted; the payload cache `%LOCALAPPDATA%/VNText/Patches/<sha>` holds install state/backups by design.
- No owned process is running; Rules in AGENTS.md/WORKFLOW unchanged.
