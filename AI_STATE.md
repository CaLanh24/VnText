# Current checkpoint — 2026-11-10 Owner quality batch, native round-1 corrections (R1–R4)

## Authority and writer
Local only: no push, release, version or tag. Public 0.1.17 immutable. Owner data (`Desktop/vntextapp/data/output`, game, saves) read-only and unchanged. DEV is the source writer; Root is sole UI owner (native round 1 at `af36f6a` PASSED the core flow; receipts `C:/vnrg/evidence/quality-batch/root-native-round1.json`, `native-*.png`, bound to `af36f6a`). No owned process, build or fixture is running.

## Source
App/code source `d517a43dfd57bb166c09128807544ae491d5eb36` (tree clean when built); a docs-only commit follows it. Epoch `epoch-20261110-020-quality6`. Earlier: `b41a00d`/`af36f6a` partial Ren'Py patch writer omits and counts ineligible rows (300 patched / 11 technical omitted, readback PASS 300).
Round-1 corrections in `d517a43` (WPF only; Python worker unchanged):
- R1 Patch summary card: own `PatchStatusText` (Building / ready — N rows written, M omitted / built from the CURRENT CSV / needs recheck / blocked) instead of the Translate step line; "BỎ QUA" (omitted) replaces "BỊ CHẶN" when `PatchPartialReady`. "Built" comes only from the patch task's own completion (`PatchDeliveryReady`), cleared by any source change/save; Validate or an old artifact never implies it.
- R2 severity by producer: `AppendLog(line, level)` + `LogSeverityConverter.Mark` (live display) and `AppJournalStore.Append(.., level)` (persisted ERROR/WARN). Explicit: CSV validation failure ERROR, preflight with omitted rows WARN, preflight failure ERROR. Worker lines `Patch read-back PASS` and `Patch tại …` are SUCCESS. Text, order, history unchanged.
- R3 delivery heading names the produced file (`VNText-VietHoa.exe`); a folder payload uses the installer named by the worker's own instructions; no fixed stub name otherwise.
- R4 busy Analyze no longer shows the amber duplicate "Đang kiểm tra…" line (real scan errors still appear on completion).

## Candidate
- App: `C:/v/DEV_RUN/bootstrap-build/VNText.Studio.App.exe` sha256 `13b61771c1a10904a2576e219e7668c611fd9716302ae69d297ec1fb5dfd3400` (dll `7cb408c5…ccf`), Debug, `build-identity.json`, evidence `app-build2.json`.
- Launcher: `Start-DEV.cmd` sha256 `5a370665…ad8b`, `Start-DEV.ps1` sha256 `fffa9beb…310b` (worker `C:/v/.dev-env/.venv`, cwd `C:/v`, model `opus-mt-en-vi-int8`).
- Candidate app data: `VNTEXT_LOCALAPPDATA=C:/v/DEV_RUN/bootstrap-build/localappdata`, so settings/journal live in `localappdata/VNTextStudio/` (NOT `data/`). Private prefs reset to Vietnamese / Light / 100% (`wpf_settings.json`) after Root's Dark 120% phase.
- Previous candidate app `DEV_RUN/final-workflow-0.1.17` and Setup `C:/vnrg/candidate-terms-fix/…-Setup.exe` (`24399a11…9921d`) untouched (old payload; no Setup rebuild).

## Gates (separate verdicts; none is a native/UI PASS of the new source)
- WPF `Workflow.Tests --owner-quality-only` PASS at `d517a43` content, including new `PatchStatus_ReflectsTheCurrentRevisionNotTheTranslateStep` (real VM/preflight: ready → build → source change), `LogSeverity_ProducerKnownLevelsReachTheDisplayAndTheJournal` (missing manifest ERROR live + persisted; partial preflight WARN; SUCCESS producers) and `AnalyzeBusy_…`.
- Full harness (no args): 24 failures, all updater tests that need versioned A/B executables not supplied here; everything else passes. Three tests were stale against Root's `9b3493a` partial-patch contract and were updated (AnalyzeComplete clean-scan text, scoped-review readiness is advisory, PartialPackage preflight decides).
- Backend/OCR/patch proof unchanged since `af36f6a` (real OCR NO_TEXT for WB025/WB113, 48 Python tests, real patch 300/0, one EXE `7a0b995d…`); not rerun.

## Budget and cleanup
Base 6.25 GiB (6,710,886,400) + 48 MiB guard; the tooling still records the old 6,912 MiB (not used). Combined 6,495,863,691 B, ~164 MB below the abort line. Disposed via registry: Root's `bootstrap-build/data/native-qa` (74 MB; hash proof archived in `native-qa-fixture-proof.json`), failed `quality-9b3493a`, real-patch fixtures. Retained: `DEV_RUN/quality-b3dd134` (WPF test build, disposable after QA). Compiler server stopped.

## Native checklist for Root (retest R1–R4 + colours only)
1. Patch tab after a successful build: card shows "Đã tạo patch từ CSV hiện tại — ghi 300 dòng, bỏ qua 19" (no "Bước 2/3 / pending / review"); second column titled BỎ QUA = 19. Before build: "Sẵn sàng tạo patch — …". After editing/saving the CSV: card asks for a recheck, never "Đã tạo".
2. Delivery heading names `VNText-VietHoa.exe` (Light and Dark).
3. Journal (sidebar and Patch log): missing-manifest CSV failure red; partial preflight amber; "Patch read-back PASS" and "Patch tại …" green; ordinary lines neutral; Light/Dark.
4. Analyze while running: one progress, one engine line, no amber "Đang kiểm tra…" line.
5. Journal window: the stored ERROR/WARN levels filter correctly.

## Limits
Native UI of the new source, other DPI/theme combinations and audible behaviour unverified by DEV. OCR 0/O, 1/l/I confusion is an engine limit. Debug configuration app.
