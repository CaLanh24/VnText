# Current checkpoint — 2026-11-09 translation workflow + single-EXE patch (native-review fixes)

## Authority
Owner batch: image workspace only in Translate with automatic results; ONE editable `translation.csv`; completion dialog + sound once; ONE self-contained patch EXE (VNText icon, installer UI matching the app). Local only: no push, release, version or tag; public 0.1.17 immutable. Game original/saves/Owner AppData untouched. Same DEV agent72329c3d / session76922e45 / sole writer; Root is sole UI owner (DEV never launches native).

## Source
Code HEAD `88d6a7589e5d154773dd1dcf12439854a6f5e76e` (tree `56f294ef…` bound in the Setup RELEASE.json). Docs-only commits follow it. Epoch `epoch-20261109-017-single-exe8` (ordinary standing transitions, ordinal 23; each costs ~50 MB of protected history).

## Root native findings closed in this round
- (A) Patch installer: description is content-sized and wraps at the card width on every resize (no fixed height; auto-sized table rows); app brand tile (`brand-owner` artwork, rounded) replaces the tiny feather; rounded card/field/status/buttons with hover/pressed/focus-ring/disabled states in the app tokens. Rendered offscreen at 680x520 and 560x500 (in-process bitmap, no window shown) and checked; Root's native pass still needed. `InstallerForm.cs` is new, `Program.cs` keeps entry/CLI; source guard test in `test_patch_bundle`.
- (B) Image workspace is results-first: counts/path summary, result list, preview + read-only translations of the selected result, ONE clear action (`Dịch ảnh chưa xong`, or `Mở thư mục kết quả` when all are translated) and `Sửa ảnh`. Manual OCR/choose/open-review, region grid/details, render/package/install/recover exist only in the edit view (`ImageEditMode`; `Quay lại kết quả` returns); no Expander. Empty package shows only the summary + `Sửa ảnh`. Fixtures assert the default view hides the tools and edit view shows them.
- (C) Completion handler no longer returns silently when the window is hidden to the tray: it restores once (`_tray.Restore()`), then shows the persistent dialog with the sound; if the window cannot be shown the sound still plays. Superseded-scan guard unchanged (tested).
- (D) `test_worker_protocol_cancel_during_real_ct2_call_acknowledges_and_exits` is deterministic: the instrumented adapter boundary HOLDS the call until the parent has sent cancel and the worker acknowledged it from its command thread, then the REAL OPUS-MT/CT2 inference runs; the timing file proves the hold, the inference duration and that every string was really translated (changed). 3/3 direct passes and green in the wrapper.
- (E) Consumed with Root's authority: `DEV_RUN/batch5-candidate` (289 MB) and the preserved old DEV build; compact receipt with file hashes `C:/vnrg/evidence/batch5/consumed-old-candidates-receipt.json`, cleanup `consumed-old-candidates-cleanup.json`. Also disposed my own direct-run test workspaces (`dispose-direct-runs.json`).

## Gate verdicts (canonical wrapper, child exit 0; wrapper `REVIEW_REQUIRED` is protected epoch history only)
- hA at `88d6a75`: 193 tests OK (WPF 37, unified document, image batch, patch bundle + installer with the real self-contained stub, CSV API, packages, extract, resources...), 2 skips.
- hB at `88d6a75`: 109 tests OK (patch input safety, delivery, worker tasks/translate incl. the real-CT2 cancel test, QA), 3 skips. `gB` is green.
- Earlier runtime proof on the real stub (install, modified-file uninstall refusal, tampered cache/manifest restored, planted file removed, corrupt EXE refused, one file delivered) is part of hA.

## Candidates (new outputs, none overwrite batch5 evidence)
- Setup candidate (DEV, not a release): `C:/vnrg/candidate-single-exe-setup/VNTextStudio-DEV-0.1.17-88d6a75-Setup.exe` 289,010,176 B sha256 `15da5e3adca6fd2ba33203601ee8ec456e7900d8e6709095179b3ed7e4ccec85`. Payload = published 0.1.17 bytes + worker python synced from the clean tree (15 replaced, `patch_bundle.py` added) + new patch-installer stub (sha `2d72dc9a…35e` inside) + rebuilt app exe (sha `3dc346d2…867a`) + new Uninstall.exe + RELEASE.json bound to `88d6a75`. Smoke: embedded payload == verified zip, 7,198 members re-hashed, worker python equals the tree, terms/licenses present, PE version 0.1.17.0. Build ran under a size monitor: sampled peak 6,614,618,036 B vs abort line 6,660,554,752 B (`setup-build-budget.json`).
- App DEV build `C:/v/DEV_RUN/bootstrap-build/VNText.Studio.App.exe` sha256 `4309376905dba57dc7ec349ef770cf8a06b0852457f7274c0ff322301a0c7c08`, source `88d6a75` clean, smoke ok (cancel, extract, translate, patch to a single EXE, crash); it uses the repo worker and `release/patch_installer_publish/VNTextPatchInstaller.exe` (restored bit-exact from the Setup payload).
- Patch EXE on an INERT fixture: `C:/vnrg/candidate-single-exe/VNText-VietHoa.exe` 68,335,924 B sha256 `b9cbbefe126b8a55b5cbbad6832d36cc8c21b2b15d795a6bc80d89106f689520` + `inert-game` + `DEV_CANDIDATE.json`.
- Builder (reusable): `C:/vnrg/evidence/batch5/build_candidate2.py` (+ `run_setup_build.py`, `smoke_setup6.py`).

## Budget
Combined 6,456,959,119 B (cap 6,710,886,400; abort line 6,660,554,752): free 254 MB after all cleanup; 4.7+ GB is protected epoch history. Shared `.dev-env` unchanged.

## Open / limits
- Native review by Root: `C:/vnrg/evidence/batch5/native-checklist-single-exe.md` (installer layout at 150%/min size, tab/focus, image workspace default vs edit view, hidden-to-tray completion dialog+sound, Setup resource step/uninstall frame). DEV claims no native PASS.
- Installer font is Segoe UI; Setup's final-cleanup helper keeps a plain message box; the payload cache `%LOCALAPPDATA%/VNText/Patches/<sha>` holds install state/backups by design; old loose `Patch_Viet_Hoa` folders are not deleted.
- No owned process is running.
