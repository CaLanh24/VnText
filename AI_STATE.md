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

## Round-2 correction (last): worker task-log severity
Root native round 2 passed R1/R3/R4, journal colours and the real Build (one EXE, readback 300 PASS / 0 FAIL, Owner files unchanged). Only left: the worker's preflight block in the Patch tab log stayed neutral. Fix `bf9b878` (end-to-end, no wording guesses): `emit_log(task_id, text, severity=None)` adds optional `severity` ("warning"/"error"/"ok", parsed by the existing `WorkerEvent.Severity`); `run_patch_worker` marks the preflight log "warning" only when `blocked > 0` (otherwise the old one-argument call, so existing callers/mocks are unchanged); the VM maps it (`KnownLogLevel`) and routes it through `AppendLog` AND `AddTaskProgress` (marked `PatchLogLines`/`TranslateLogLines` line + persisted journal level). Text, order and history are unchanged; unmarked lines stay text-derived/neutral.
Tests: Python `test_worker_preflight_log_carries_producer_known_warning_only_when_rows_are_omitted` (real worker emit; `test_patch_input_safety` 15 OK); WPF `WorkerPreflightLog_SeverityReachesThePatchTaskLogAndTheJournal` (real protocol JSON → `PatchLogLines`, `LogLines`, persisted WARN) inside `--owner-quality-only` PASS. Full updater harness, engine/OCR/MT and Setup not rerun (unchanged components reuse the `d517a43` native proof).

## Candidate
- App: `C:/v/DEV_RUN/bootstrap-build/VNText.Studio.App.exe` sha256 `cb9587f553c87b89307a3e7eeb023de3c47d1732e76c8b9cb239df543c25cd85` (dll `d269c0d9…bdd4`), Debug, from clean source `bf9b878697040b0ed112096128156b0d69761ce5` (`build-identity.json`, evidence `app-build3.json`). Epoch `epoch-20261110-021-quality7`.
- Launcher (unchanged, works; run `Start-DEV.cmd`, raw `powershell -File` hits the OS script policy): `Start-DEV.cmd` `5a370665…ad8b`, `Start-DEV.ps1` `fffa9beb…310b`; app data `DEV_RUN/bootstrap-build/localappdata/VNTextStudio/`. Prefs Light / 100%.
- Previous candidate app `DEV_RUN/final-workflow-0.1.17` and Setup `C:/vnrg/candidate-terms-fix/…-Setup.exe` (`24399a11…9921d`) untouched (old payload; no Setup rebuild).

## Budget and cleanup
Base 6.25 GiB (6,710,886,400) + 48 MiB guard; no 6.75 reuse. Combined 6,527,458,597 B, ~133 MB below the abort line. Disposed via registry: Root's `native-qa2` fixture (hash proof `native-qa2-fixture-proof.json`) and the WPF test build `DEV_RUN/quality-b3dd134`. No owned process or build is running.

## Native check for Root (new worker warning only + colours)
Build a patch from the Owner CSV copy: the Patch tab log line "Kiểm tra patch — hợp lệ 300, bị chặn 19 …" is amber (Light and Dark); the read-back/created-installer lines stay green; ordinary lines neutral; Journal window shows the persisted WARN.

## Limits
Native UI of the new source, other DPI/theme combinations and audible behaviour unverified by DEV. OCR 0/O, 1/l/I confusion is an engine limit. Debug configuration app.
