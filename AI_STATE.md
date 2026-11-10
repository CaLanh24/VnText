# Current checkpoint — 2026-11-10 six-finding UX/environment batch (Owner-authorized; handoff to Owner test, not release, not native acceptance)

## Authority and writer
DEV cursor 1631+ (Claude DEV72329c3d / session76922e45). Local only: no push, release, version, tag, model download or game write. Owner data read-only and unchanged. DEV is the main writer again; Root is sole UI owner. The batch fixes exactly the six findings of Root's live review (`C:/vnrg/evidence/quality-batch/ux-full-review.json`): all six are done and gated below; none is native-verified yet.

## Source
Code/app source `a24d0f676cc92aa48f3e14ba763e0b6b21fd4930`; docs-only commits follow it (the candidate was built from `a24d0f6`; docs need no rebuild). Epoch: the registry's ACTIVE epoch (ordinary same-scope continuity hops, `epoch-20261110-024-quality10` and later; each docs commit needs one more hop; no rebaseline, no cap/guard change); the launcher budget check is bound to the final HEAD (verified at the end of this checkpoint).

## What changed (per finding)
1. **Budget/launcher (environment).** `release/dev_bootstrap.py` now carries the approved task budget (`VNTEXT_RELEASE_TASK_ID`, default `release-<VERSION>`) into the launcher and every owned child, and `Start-DEV.ps1` runs `dev_bootstrap.py --action budget-check` BEFORE the app starts: a fast read-only check (<1 s) that the registered ACTIVE epoch/budget/approval/scope belong to the exact clean HEAD; otherwise it stops with the exact cause (for a docs-only HEAD: epoch source != HEAD — run the ordinary same-scope epoch transition, then `--register-release-task-scope`). Cap 6.25 GiB base + 48 MiB guard and the baseline are untouched; the full epoch-history verification (minutes) stays with the quota tool.
2. **Analyze.** Success is a quiet non-blocking toast (no dialog, no sound); warnings/failures/pre-extract guard unchanged. Changing ONLY the output folder re-keys the valid analysis of the same source (no rerun, no second announcement); any source change still invalidates.
3. **CSV technical_control.** The status column shows the localized short label "Mã/định dạng game" / "Game code/format"; `IssueDisplay` (tooltip/help), disk CSV, reports and eligibility keep the raw `technical_control`.
4. **CSV find label.** "Tìm nguyên bản hoặc bản dịch" and "Thay bằng" wrap instead of clipping; layout fixture still holds 3 full rows at 1043x720 DIP / UI 120%.
5. **Language.** A switch re-reads readiness/workflow/analyze/patch/extract computed lines; app-generated completion titles/bodies (done/cancelled/error, Cloud Repair, import, patch, analyze, extract partial titles) have English entries and are localized at display; user text, paths, stderr, reports and release notes untouched.
6. **Import old translation.** The target is the package the person works on (the selected validated CSV that Translate/Export/Patch use; output folder only when none is selected); the target path is logged; manifest/identity/key/source/draft/same-file guards unchanged.

## Gates (separate verdicts)
- WPF `Workflow.Tests --owner-quality-only` PASS (new: Analyze toast + output-only reuse, technical label raw reason, language refresh/completion strings, import target; plus all earlier owner-quality tests). `--csv-editor-only` PASS (13). `--csv-layout-fixture` passes the CSV/label layout checks incl. the new wrap assertions; it then stops at an OLD journal-window probe that expects a TextBox where Root's `SeverityLogBox` is now used (pre-existing stale test, not part of these six). `--translate-readiness-only` has one stale expectation (`Thiếu model OPUS-MT INT8`, string removed in 0.1.12) — pre-existing. The full no-argument harness (24 updater tests needing A/B executables) was not rerun.
- Python `test_dev_bootstrap` 31 OK (launcher carries budget, check before app start, fail-closed diagnostics for docs HEAD/dirty/unregistered scope, owned env propagation).
- Real backend chain: `dev_bootstrap --action smoke` PASS at `a24d0f6`: cancel / extract (1 row) / MT translate (real CT2 model, 1/1) / patch (one installer, `Đã tạo installer Việt hóa … Patch_Viet_Hoa\VNText-VietHoa.exe`) / crash, all exit 0 (`smoke.json`). Earlier Ren'Py 300-row real patch proof (`7a0b995d…`) unchanged (worker code untouched).

## Candidate (new, isolated; previous candidate untouched)
- App `C:/v/DEV_RUN/resources-dev15/VNText.Studio.App.exe` sha256 `ff7e6c9f2af59098c954dadb1238fa2ccbd9dd3f61fd932df257f74eef1a4cc7`, dll `48be7a4c492552b8202a3db41330f353b97f3e797ef493daa594ea6a1dde2686`, Debug, clean `a24d0f6` (`build-identity.json`, evidence `app-smoke.json`). (`resources-dev15` is just the second owned output slot of `dev_bootstrap`; it is the new candidate.)
- Launcher `Start-DEV.cmd` `5a370665…ad8b`, `Start-DEV.ps1` `9be946e2…8774` (includes the budget check; run with `Start-DEV.cmd`, raw `powershell -File` hits the OS script policy). App data `DEV_RUN/resources-dev15/localappdata/VNTextStudio/`; defaults Vietnamese/Light/100%.
- Preserved: `DEV_RUN/bootstrap-build` (cb9587f5… previous app) and `DEV_RUN/final-workflow-0.1.17`.
- Launcher/budget note for any docs-only commit: after it, the launcher stops by design until `trans2`-style ordinary epoch transition + scope registration bind the new HEAD (done for the final HEAD below).

## Root native observation (receipt `root-native-observation-sixfinding.json`)
Root opened the new launcher (`resources-dev15`), exact-app UIA valid; picked the declared output before the real game (read-only); Analyze completed (Ren'Py / "Sẵn sàng lấy text") with toast text "Phân tích game hoàn tất" and NO completion modal — UIA-only, limited evidence for finding 2. The desktop then locked (all windows is_focused=false, app capture TIMEOUT with WGC, display capture BitBlt 0x80070006, LogonUI sessions 1/2); Root stopped native, no fallback across the lock, app closed (PID 14212 exited). **Native visual verdict: all six NOT PROVEN.**

## Root native fixture (disposed)
`C:/v/DEV_RUN/bootstrap-build/data/native-qa3/package` (`translation.csv`, `manifest.json`, `extract_status.json`; 1.4 MB, Owner source hashes unchanged, proof `native-qa3-fixture-proof.json`) and `.../native-qa3/old-translation/translation.csv` (copy for Import). Disposed through the registry helper after Root closed the app (hash proof kept in `native-qa3-fixture-proof.json`, cleanup receipt `sixfinding-final-cleanup.json`). Two stale MISSING records of an earlier same-named fixture had to be reclassified DISPOSABLE first (the helper skips a re-created path that still has a MISSING record).

## Native checklist for Root (finite; repeat when the desktop is unlocked)
1. `Start-DEV.cmd` starts (budget check silent). With a Ren'Py game + output: Extract is NOT blocked by the 1 GiB default; Analyze toast only (visual); output-only change: no second analysis; source change: re-analysis.
2. A CSV with `technical_control` rows shows "Mã/định dạng game", tooltip keeps `technical_control`.
3. CSV tab at 1565x1071 px, OS 150%, UI 120%: find label wraps, 3 full rows + preview/Apply/Undo remain.
4. Vietnamese <-> English: readiness line and an Export completion dialog fully English, then back.
5. Import existing translation with a selected valid CSV and an unrelated output folder: the log names the target package; same-file import is refused.
(No native fixture is left; build one from the Owner output copy if needed.)

## Budget and cleanup
Base 6.25 GiB (6,710,886,400) + 48 MiB guard (abort line 6,660,554,752) is the manual limit; the tooling record still says the old temporary 6,912 MiB (cap 7,247,757,312) and was NOT used or raised. Combined 6,422,025,806 B, ~238 MB below the abort line. Disposed: `native-qa3` fixture and the rebuilt `DEV_RUN/quality-b3dd134` WPF test build. Retained until Owner QA: new candidate `DEV_RUN/resources-dev15` (prefs VI/Light/100%), previous `DEV_RUN/bootstrap-build` and `final-workflow-0.1.17`, all evidence. No owned process running.

## Limits
Native UI of the six fixes, other DPI/themes, audible behaviour and the stale probes above are unverified by DEV. Debug builds.
