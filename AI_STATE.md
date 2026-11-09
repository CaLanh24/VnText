# Current checkpoint — 2026-11-10 Owner quality batch (candidate ready for Root native QA)

## Authority and writer
Local only: no push, release, version or tag. Public 0.1.17 immutable. Owner data (`Desktop/vntextapp/data/output`, game, saves) read-only and unchanged. Source writer is DEV again (Root's temporary quota commits `9b3493a`, `5f874f2`, `b3dd134` reviewed). Root is sole UI owner. No owned process, build or fixture is running.

## Source
HEAD `af36f6af9b80add3fcf33f3d9465da634c7d20ba`, tree clean, epoch `epoch-20261110-019-quality5`. DEV fixes on top of Root's `b3dd134`: `b41a00d` / `af36f6a` — the Ren'Py partial patch writer now OMITS ineligible rows (technical control, untranslated/blank) and counts them in `patch_verification.json["omitted_by_reason"]` / `import_report.txt` instead of aborting with "entry is not eligible"; omitted rows are no longer re-added to the verification records. Structural/identity/contract errors still abort. WPF code is unchanged since `b3dd134`.

## Candidate
- App: `C:/v/DEV_RUN/bootstrap-build/VNText.Studio.App.exe` sha256 `cf3a95f85a9b607007c3bade1ab204e02943c6a5a5af8fd70cc867fb27d479ce` (dll `fe14235a…4700`), Debug, built from clean `af36f6a` (`build-identity.json`, evidence `app-build.json`).
- Launcher: `C:/v/DEV_RUN/bootstrap-build/Start-DEV.cmd` (sha256 `5a370665…ad8b`) + `Start-DEV.ps1` (`fffa9beb…310b`); worker `C:/v/.dev-env/.venv`, worker cwd `C:/v`, model `.dev-env/cache/models/opus-mt-en-vi-int8`, data under `DEV_RUN/bootstrap-build/data`.
- Previous candidate app `DEV_RUN/final-workflow-0.1.17` and Setup `C:/vnrg/candidate-terms-fix/…-Setup.exe` (sha `24399a11…9921d`) are untouched; that Setup carries the old payload (no Setup rebuild for this batch).

## Gates (separate verdicts; none is native/UI PASS)
- WPF `Workflow.Tests --owner-quality-only` PASS at `b3dd134` (build exit 0, component unchanged since; reused, not rerun).
- Python focused: `test_renpy_patch` + `test_patch_input_safety` 48 OK at `af36f6a` (includes the new partial-omission regression); Root's 116-test gate at `9b3493a`.
- Real OCR (Owner photos WB025/WB113, source unchanged): both `NO_TEXT`; synthetic positives detected. "OK" is read as "0K" by Windows OCR, so positives are compared modulo O/0 and I/l/1 — NOT an exact-transcription PASS.
- Real patch (Owner CSV/manifest copied into a registered fixture, game read-only): preflight eligible 300 / blocked 19 (11 technical_control + 8 review_only); worker terminal ok; ONE EXE (sha256 `7a0b995d…80dd`); readback PASS 300 / FAIL 0 = exactly the eligible rows; 11 technical rows omitted and counted, 8 review rows unpatched; coverage scope `VERIFIED_MAIN_SUBSET`. Owner files unchanged. Evidence `C:/vnrg/evidence/quality-batch/` (`final-gates2.json`, `actual-patch.json`, `real-ocr.log`).
- Wrapper `REVIEW_REQUIRED` is only protected epoch history.

## Budget and cleanup
Base 6.25 GiB (6,710,886,400) + 48 MiB guard; the tooling still records the temporary 6,912 MiB (not used). Combined now 6,435,430,971 B, 225 MB to the abort line. Disposed through the registry: failed `DEV_RUN/quality-9b3493a`, both real-patch fixtures (`dispose-*.json`). Retained: `DEV_RUN/quality-b3dd134` (WPF test build, disposable after QA). The compiler server started by the build was stopped.

## Native checklist for Root (finite; not yet run)
1. Launch `Start-DEV.cmd`; scale 100% and 120%, Light and Dark.
2. Analyze: ONE progress bar/line only; engine status is a single concise NextAction line.
3. Journal/log: smaller font; success green, warning amber, error red in both themes; Translate/Patch history not truncated; warning card concise.
4. Extract/Translate on a folder with the Owner photos (WB025, WB113): no text rows, no MT, no rendered output. A real text image still gets rows.
5. CSV: Achievement/strftime/`[a.stat_progress]`/`[config.name!t]`/`<`/`>`/`{#quick_page}Q`/`{#auto_page}A`/`[page]` rows are technical (skipped); "Mute All" stays a translatable label.
6. Patch with 5 pending / 8 review: ONE confirmation naming included and omitted counts; icons/counts consistent; review is advisory; no-writeback/dynamic rows are not forced in; one patch EXE produced.

## Limits
Native UI, all DPI/theme combinations and audible behaviour unverified by DEV. OCR confusables (0/O, 1/l/I) are an engine limit. Debug configuration app.
