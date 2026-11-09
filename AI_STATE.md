# Current checkpoint — 2026-11-09 local workflow candidate (native Setup accepted within scope)

## Authority and writer
Owner batch (one editable CSV, source/translation search, results-first image workspace, completion dialog + sound, one branded patch EXE, native-reviewed Setup) is local only: no push, release, version or tag. Public 0.1.17 is immutable. Game, saves and Owner AppData untouched. DEV is the sole writer (same agent/session); Root is sole UI owner. No owned process, UI, worker or build is running.

## Current candidates (retain until Owner QA)
- Setup: `C:/vnrg/candidate-terms-fix/VNTextStudio-DEV-0.1.17-1845cfe-Setup.exe`, sha256 `24399a11a7c9613fed6205f555de8ee240e8dee5a622189d15bb786c3a89921d`, 289,011,712 B. Code is `949d1fc`; `1845cfe` is the docs commit it is bound to. Payload = DFD bytes + new Uninstall.exe + RELEASE.json; 7,198 members verified.
- DEV app: `C:/v/DEV_RUN/final-workflow-0.1.17/Start-DEV.cmd`, app sha256 `78391c5a7a84d92e04d4f7078e2bc795259cb157071b6762e55787025458ea8b`.
- Receipts (in `C:/vnrg/evidence/batch5/`): `root-native-setup-20261109.json` (Root native), `terms-build-receipt.json`, `terms-build-dispose.json`, `terms-build-budget.json`, `native-setup-terms-prep.json`, `scope-recovery-receipt.json`.

## Verdicts (separate)
- Gates: focused canonical gate 22 tests PASS at `949d1fc` (setup package, resources, scope recovery); cleanup tool module 155 OK; earlier hA193/hB109 at `88d6a75` reused for unchanged Python; wrapper `REVIEW_REQUIRED` is protected epoch history only.
- Native (Root, exact Setup `24399a11…`): VI/EN terms footer full captions, original Intel agreement opens/Close, isolated install, resources step starts, UI Cancel/Skip truthfully show NOT ready, installed app launches, uninstall refuses while the app is active (no deletion) and succeeds after close and self-removes. Owner Desktop/Start Menu equal to the snapshot. Test root empty, all UI closed.
- NOT_PROVEN: real Ren'Py SDK download and resource success (needs the requested 6.25 -> 6.75 GiB budget; the async question is UNANSWERED and no cap was raised); forced-offline native branch (proxy launch was auto-policy rejected, not retried or bypassed; plain launch succeeded); all DPI/themes; audible playback; large games. No native PASS is claimed beyond the Root receipt.

## Budget and cleanup
Cap 6.25 GiB (+48 MiB guard), shared `.dev-env` 11 GiB, none changed. Combined about 6.02 GB; protected epoch history about 5.2 GB. Release-0.1.17 scope was recovered by an explicit CAS entry (`release-0.1.17:recovery:93cf155beb31`, old deletion proof unchanged). Consumed with receipts: old DFD Setup, generated baseline mirror, legacy `DEV_RUN` audit output (archived, hashed) and the empty native test container (`native-testroot-cleanup.json`, normal registry disposal OK). `runner-reports` remains REVIEW_REQUIRED (no force). Epoch `epoch-20261109-017-scope-recovery2`; ordinary same-scope transitions are standing.

## Next
Owner QA on the exact Setup/app. A real SDK-success test needs the budget decision first. History of earlier rounds: `docs/WORKFLOW_CANDIDATE_2026-11-09.md`.

## Temporary 6.75 GiB grant (2026-11-09, native full-resource run)
Owner: 'Cho phép 6,75 GiB, kiểm trọn Setup'. Recorded through the supported tooling path (`3008b52`, epoch `epoch-20261109-017-budget675b`): limit 6,912 MiB for release-0.1.17, 6.25 GiB epochs stay verifiable, scope generation reactivated, regressions in `test_cleanup_work_artifacts` (162 OK); guard 48 MiB and shared 11 GiB unchanged. Test root `DEV_RUN/native-setup-full` registered (absent); telemetry/cleanup scripts and checklist ready (`native-full-checklist.md`, `native-full-prep-receipt.json`). PREFLIGHT DOES NOT FIT yet: expected peak exceeds the abort line by ~39 MB; Root must pick one listed option before the download. Nothing started; Setup `24399a11…` untouched.
