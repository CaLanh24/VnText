# Local workflow candidate — 2026-11-09

Local test candidate only; public 0.1.17 remains immutable. Current code source `949d1fc` (workflow code `dfd15e2` plus the Setup terms-dialog fix and the scope-recovery tooling). No push, release, version or tag change.

Owner requested one editable CSV, source/translation search, image results only in Translate without repeated OCR, automatic image drafts, persistent completion dialogs with sound, and a single branded patch installer. Contract for document roles is in CONTRACTS §1. Human editing does not grant a missing engine writer proof.

Implemented: image translation consumes Extract's positive OCR report; results show counts/output/list/preview, with manual tools in an explicit edit view. Desktop extraction writes one editable CSV and keeps review roles in the manifest. Patch delivery bundles payload/manifest into one EXE, with per-payload internal state/backup and verified install/uninstall guards. Completion dialogs are queued after terminal state updates, including automatic analysis and tray restoration; superseded scans are suppressed.

## Evidence and acceptance

- Root receipt: `C:/vnrg/evidence/batch5/root-final-handoff-20261109.json`; package verification: `root-final-package-smoke.json` in the same directory.
- Final focused gate: 46 tests, zero failures/errors/skips, child exit0 at dfd15e2; wrapper protected epoch history remains REVIEW_REQUIRED. Earlier hA193 and hB109 tests at88d6a75 are reused only for unchanged Python/worker behavior; their skips remain recorded.
- Debug/Release app builds and worker smoke passed: cancel, extract, translate, single-EXE Patch, crash. All7198 Setup payload members and99 worker Python files verified.
- Native: exact final patch fixture install → inline uninstall confirmation → uninstall restored the inert fixture. Footer accessible at580×540 physical pixels/OS150%; default description wraps. Final app automatic-analysis completion dialog observed. Simplified empty image results observed on88d6a75; final delta only hides its stale manual hint.
- NOT_PROVEN: native Setup install/uninstall (earlier launch rejected by policy, not retried), actual audible playback, final positive-image E2E through native UI, all DPI/themes/large games. Automated evidence is not native PASS or release acceptance.

## Current candidate and native result

- Setup: `C:/vnrg/candidate-terms-fix/VNTextStudio-DEV-0.1.17-1845cfe-Setup.exe`, SHA256 `24399a11a7c9613fed6205f555de8ee240e8dee5a622189d15bb786c3a89921d` (289,011,712 B); payload 7,198 members verified, embedded stream hash equals the verified ZIP `c48edc57...`.
- DEV app (unchanged): `C:/v/DEV_RUN/final-workflow-0.1.17/Start-DEV.cmd`, app SHA256 `78391c5a7a84d92e04d4f7078e2bc795259cb157071b6762e55787025458ea8b`.
- Root native receipt: `C:/vnrg/evidence/batch5/root-native-setup-20261109.json`. PASS: VI/EN terms footer, original Intel agreement + Close, isolated install, resources start then Cancel/Skip truthfully NOT ready, installed app launch, uninstall blocked while the app is active (no deletion) then success after close and self-removal; Owner Desktop/Start Menu unchanged; test root empty, UI closed.
- Full native resource path PASS (Root `root-native-full-setup-20261109.json`: real 155.5 MB SDK download/verify/extract -> Setup Ready, app launched, Check Resources all Ready, uninstall removed 11,680 items; cleanup `native-full-cleanup-linked-receipt.json`). NOT_PROVEN: forced-offline native branch (proxy launch auto-policy rejected, not retried); all DPI/themes; audible playback.
- Build evidence: `terms-build-receipt.json`, `terms-build-dispose.json`, `terms-build-budget.json`, `native-setup-terms-prep.json`; scope recovery `scope-recovery-receipt.json`; legacy DEV_RUN archive `legacy-dev-run-archive-receipt.json`.

## History (superseded pointers, kept for the ledger)

- `dfd15e2` Setup `5b4e964b...4768c` was the first native-ready candidate; Root found the terms footer clipped and `/lang=vi` ignored for that dialog. It was consumed (approved exact move into DEV_RUN + registry disposal) when the terms-fix Setup was built.
- Earlier DEV candidates: `88d6a75` (results-first image workspace, installer layout) and `3f6976b` (five-finding batch). Their Setup builds are consumed; hashes are in the batch5 receipts.
- Private inert patch fixture: Root's `eef87e36...b632a` is no longer at `C:/vnrg/candidate-single-exe`; DEV's superseded fixture at that path was consumed with a hash receipt (`consumed-r3-receipt.json`) during budget cleanup. Rebuild a fixture from `build_fixture_exe.py` if one is needed again.
- Consumed with receipts: generated 0.1.17 baseline mirror, old batch5 Setup, legacy DEV_RUN audit output (text archived, binaries hash-indexed), empty native test container. `runner-reports` stays REVIEW_REQUIRED. User data, original game/saves and protected epoch history retained.

- Temporary 6.75 GiB grant (Owner 2026-11-09) funded the full-resource run; stub relocated for the preflight and restored byte-exact afterwards; test container disposed through the registry route.

- 2026-11-10 six-finding batch (Owner-authorized): launcher budget prerequisite, quiet Analyze success + output-only reuse, `technical_control` user label, wrapping find label, language refresh + localized completion, import target consistency. Code `a24d0f6`; candidate `DEV_RUN/resources-dev15` (app sha256 `ff7e6c9f…4cc7`); real smoke chain PASS; native visual NOT PROVEN (Root desktop lock, UIA-only note for Analyze). Details: AI_STATE and `C:/vnrg/evidence/quality-batch/` (`root-native-observation-sixfinding.json`, `app-smoke.json`, `sixfinding-final-cleanup.json`).
