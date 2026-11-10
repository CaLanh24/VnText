# Current checkpoint — 2026-11-10 six-finding UX/environment batch (Owner-authorized)

## Authority and writer
Local only: no push, release, version, tag, model download or game write. Owner data read-only and unchanged. DEV is the main writer again; Root is sole UI owner. The batch fixes exactly the six findings of Root's live review (`C:/vnrg/evidence/quality-batch/ux-full-review.json`): all six are done and gated below; none is native-verified yet.

## Source
Code/app source `a24d0f676cc92aa48f3e14ba763e0b6b21fd4930` (parents: `8b0b9f8`, `bf9b878`); a docs-only commit follows it. Epoch `epoch-20261110-023-quality9` (ordinary same-scope continuity hops; no rebaseline, no cap/guard change).

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

## Root native fixture
`C:/v/DEV_RUN/bootstrap-build/data/native-qa3/package` (`translation.csv`, `manifest.json`, `extract_status.json`; 1.4 MB, Owner source hashes unchanged, proof `native-qa3-fixture-proof.json`) and `.../native-qa3/old-translation/translation.csv` (copy for Import). Registered DISPOSABLE `root-quality-native-qa3` (scope `release-0.1.17`).

## Native checklist for Root (finite)
1. `Start-DEV.cmd` starts (budget check silent). Choose a Ren'Py game folder + output: Extract is NOT blocked by the 1 GiB default; Analyze shows a toast only (no dialog); change only the output folder: no second analysis/announcement; change the source: re-analysis.
2. Choose `native-qa3/package/translation.csv`: rows with `technical_control` show "Mã/định dạng game", tooltip keeps `technical_control`.
3. CSV tab at 1565x1071 px, OS 150%, UI 120%: the find label wraps, 3 full rows + preview/Apply/Undo remain.
4. Switch Vietnamese ↔ English: readiness line and an Export completion dialog (title, body, button) are fully English, then back.
5. With that CSV selected (output folder unrelated), Import existing translation → picks `old-translation/translation.csv`: the log shows the target package; same-file import is refused.

## Budget and cleanup
Base 6.25 GiB (6,710,886,400) + 48 MiB guard; no raise/waiver. Combined recorded in the handoff. Retained: current/previous candidates, evidence. No owned process running.

## Limits
Native UI of the six fixes, other DPI/themes, audible behaviour and the stale probes above are unverified by DEV. Debug builds.
