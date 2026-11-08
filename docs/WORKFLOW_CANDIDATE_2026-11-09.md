# Local workflow candidate — 2026-11-09

Local test candidate only; public 0.1.17 remains immutable. Code source `dfd15e2ed5087b94d2e35efdd2a1a270b92bacac`. No push, release, version or tag change.

Owner requested one editable CSV, source/translation search, image results only in Translate without repeated OCR, automatic image drafts, persistent completion dialogs with sound, and a single branded patch installer. Contract for document roles is in CONTRACTS §1. Human editing does not grant a missing engine writer proof.

Implemented: image translation consumes Extract's positive OCR report; results show counts/output/list/preview, with manual tools in an explicit edit view. Desktop extraction writes one editable CSV and keeps review roles in the manifest. Patch delivery bundles payload/manifest into one EXE, with per-payload internal state/backup and verified install/uninstall guards. Completion dialogs are queued after terminal state updates, including automatic analysis and tray restoration; superseded scans are suppressed.

## Evidence and acceptance

- Root receipt: `C:/vnrg/evidence/batch5/root-final-handoff-20261109.json`; package verification: `root-final-package-smoke.json` in the same directory.
- Final focused gate: 46 tests, zero failures/errors/skips, child exit0 at dfd15e2; wrapper protected epoch history remains REVIEW_REQUIRED. Earlier hA193 and hB109 tests at88d6a75 are reused only for unchanged Python/worker behavior; their skips remain recorded.
- Debug/Release app builds and worker smoke passed: cancel, extract, translate, single-EXE Patch, crash. All7198 Setup payload members and99 worker Python files verified.
- Native: exact final patch fixture install → inline uninstall confirmation → uninstall restored the inert fixture. Footer accessible at580×540 physical pixels/OS150%; default description wraps. Final app automatic-analysis completion dialog observed. Simplified empty image results observed on88d6a75; final delta only hides its stale manual hint.
- NOT_PROVEN: native Setup install/uninstall (earlier launch rejected by policy, not retried), actual audible playback, final positive-image E2E through native UI, all DPI/themes/large games. Automated evidence is not native PASS or release acceptance.

## Candidates and retention

- Setup: `C:/vnrg/candidate-workflow-final/VNTextStudio-DEV-0.1.17-dfd15e2-Setup.exe`, SHA256 `5b4e964b813a3cabd633f965fe1775964632ebb477535b2c5538efbe69b4768c`.
- DEV app: `C:/v/DEV_RUN/final-workflow-0.1.17/Start-DEV.cmd`; app SHA256 `78391c5a7a84d92e04d4f7078e2bc795259cb157071b6762e55787025458ea8b`.
- Private inert patch fixture: `C:/vnrg/candidate-single-exe/VNText-VietHoa.exe`, SHA256 `eef87e360762492581b519b55d21cad1d89dc2a7547a32b37a6f03fabf4b632a`.
- Build staging and superseded Setup candidates consumed; historical gatec audit compressed and byte-verified before disposal. User data, original game/saves and protected epoch history retained. Cleanup helper left debug/three small .NET fixture containers; no forced deletion or cleanup PASS claimed for those. Retain candidates until Owner QA, then consume superseded payloads with receipts.
