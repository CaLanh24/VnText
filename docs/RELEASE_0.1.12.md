# VNText Studio 0.1.12 — final release acceptance

**Release status: PUBLISHED.** Stable GitHub release: [v0.1.12](https://github.com/CaLanh24/VnText/releases/tag/v0.1.12). The version-matched Setup and supported full-app updater assets are available. Release delivery and exact-source build gates passed; this does not claim full real-game or broad native visual acceptance.

## Scope and objective

This release completes the post-0.1.11 workflow and UI remediation: task-owned progress and cancellation, separate image OCR/extraction from image translation, local translation readiness/progress, CSV editor usability, app-themed feedback, engine visibility, release notes, and direct update routes. User-facing notes describe features and interface changes in Vietnamese. Test counts, hashes and developer instructions stay in technical evidence.

Starting source was `988780d3b6777599b91429417d43f3f8cd7b10ac` with the task-owned implementation changes inherited in the working tree. Public v0.1.11 remains unchanged.

## Git and source identity

- Branch at build/publication: `main`; release source commit: `7da2436014fa4b1d33185c997492b1a5dc9cf174`.
- Implementation: `cfd17a2 Complete 0.1.12 workflow UX remediation`.
- Follow-up fix: `fc95ef6 Fix release regression runtime selection`.
- Release policy and allocation records: `95d37ca`, `4d41c29`, `7da2436`.
- Annotated tag: `v0.1.12`; tag object `93d00e4cc083b7bcfcdfd9f59e5f791d79057a35`; peeled source is exactly `7da2436014fa4b1d33185c997492b1a5dc9cf174`.
- Before this acceptance-document update, source checkout was clean and remote `main` also pointed at `7da2436`. The docs-only closure is pushed separately; it does not change the release tag or tested binary source.

Main implementation areas include `wpf_app/VNText.Studio.App/MainWindow.xaml`, `MainWindow.xaml.cs`, the workflow/settings/update/CSV view models and services, `UpdateWindow.cs`, control theme resources, `vntext/app_tasks.py`, `vntext/image_batch.py`, CT2 readiness/pipeline modules, `vntext_worker/protocol.py`, task runners and worker main. Regression coverage was added or extended in worker protocol, image batch, model readiness, human review, traceability, Setup packaging and WPF workflow tests. `release/publish.ps1` now publishes the version-matched Setup and update routes together.

## Plan acceptance

| Plan phase | Result | Evidence and boundary |
|---|---|---|
| Plan and product contracts | PASS | Persisted in this plan, `CONTRACTS.md` and `AI_STATE.md`. Release-note policy requires concise Vietnamese user-facing changes and a Setup plus supported updater assets. |
| Focused regression | PASS | Ten focused test-file groups passed; two explicit environment-dependent skips. Receipt: `DEV_RUN/r012/tests/focused-final/20261025_134514_061/REGRESSION_COMPLETE.json`. |
| Affected and full regression | PASS | Exact source `7da2436`: 1,088 tests, 0 failures, 0 errors, 9 explained skips; runner cleanup PASS. Runtime OCR/model and external Unity-fixture cases account for skips. Log and receipt: `DEV_RUN/r012/tests/full-final/20261025_134748_826/`. |
| Integration | PARTIAL | Synthetic Ren'Py Analyze → Extract → local Translate → Patch passed before the last readiness-property fixes. The final fixes passed WPF workflow and affected regression; a second post-fix native full-flow run was not performed. Real-game E2E is `NOT TESTED`. |
| Native UX | PARTIAL | The native CSV layout probe handled 27,767 rows at three window sizes. The final derived Translate status fix is covered by regression, but its post-fix visual state and the full set of dialogs, DPI/focus/resize and image flows were not captured natively. |
| Exact-source commit and release build | PASS | Source/tag SHA `7da2436`; Setup payload verification, release verifier and worker smoke all PASS on that source. |
| Setup and updater acceptance | PASS for tested paths | Fresh isolated Setup install started the worker. Public GitHub update from 0.1.9 downloaded and applied the exact 0.1.9 route, restarted at 0.1.12 and preserved data/model sentinels. Other route packages were integrity-checked; their installed-app UI flows were not individually run. |
| Publication and readback | PASS | Stable release is public, tag peels to built source, all 15 uploaded assets match local size/SHA-256, including a direct Setup download. |
| Terminal cleanup | PASS | Exact registered candidate removed; checkout is back under 1 GiB and shared `.dev-env` under 6 GiB. Receipt: `DEV_RUN/r012/candidate-terminal-cleanup.json`. |

## Build, tests and installed evidence

- Exact-source regression: **1,088 PASS, 0 FAIL, 0 ERROR, 9 SKIP**. The skips are two explicit native OCR/model cases, two installer tests whose optional test executable was not built, one GUI-shutdown test without the standalone DEV executable, and four external Unity-fixture E2E cases. No real-game result is inferred from those skips.
- Release verifier: **PASS**. Packaged worker smoke: **PASS**. Setup payload: 7,193 files / 514,710,359 bytes.
- Setup asset: `VNTextStudio-Setup-0.1.12.exe`, 222,446,592 bytes, SHA-256 `626e98d51beae8009b3076107d6a0e7fd9f9196f8a628d2f9e826a34a54a9782`. A fresh isolated install had 7,191 app files, its executable SHA matched the release executable, and the app log recorded the Python worker ready. The generated install manifest has 7,194 entries: the 7,193 Setup payload entries plus the one Setup-generated `.vntext-update-source.json`. Receipt and retained startup log: `DEV_RUN/r012/setup-acceptance-public-0.1.12.json` and `setup-app-startup-0.1.12.log`.
- Public updater E2E from **0.1.9 → 0.1.12**: one hop; downloaded route ZIP 6,071,813 bytes, SHA-256 `da3bdc3f09665656575a5d894e737c6217c3b3ac940807763a80d54b1e154cf1`; updater health and restart PASS. Installed inventory matched Setup at 7,191/7,191 files with zero missing, extra or hash/size mismatches. Synthetic user-data and model sentinels survived. Durable records: `DEV_RUN/r012/public-update-acceptance-019.json`, `public-update-019-0.1.12.log` and `public-update-019-success.json`.
- GitHub readback: public stable release, not draft/prerelease; `main` and tag source matched `7da2436` at publication; **15/15** assets match local size and digest, and the directly downloaded Setup digest matches. Receipt: `DEV_RUN/r012/public-release-readback-final.json`.
- Five route packages/feeds are published: generic 0.1.7 baseline and named baselines 0.1.8, 0.1.9, 0.1.10 and 0.1.11. Package/manifest integrity was checked for all; only the 0.1.9 route received the full public installed-app offer/download/apply/restart test in this campaign.

## User-visible changes released

- Quét, dịch, OCR ảnh và patch report their own stage and active item; ETA is shown only when available and formatted as time.
- Image OCR/extraction no longer runs machine translation or renders output; image translation stays in Translate.
- Local translation has explicit CSV readiness and progress, with clearer reasons when Start is unavailable.
- Analysis surfaces the detected engine and exposes Ren'Py SDK recovery choices when needed.
- CSV editing has a clearer large-table layout and simpler translation search/replace controls.
- Completion and cancellation feedback uses the app's themed surface; update/release-note presentation and update routing were improved.
- Each supported older baseline receives a direct 0.1.12 package route. New users can download Setup directly from the release.

The public release body contains only the Vietnamese feature/interface summary; detailed verification and license notices remain in their separate assets/records.

## Remaining boundaries and follow-up

- **Real-game E2E: `NOT TESTED`.** No user game was used or copied in this release acceptance.
- **Broad native visual acceptance: `PARTIAL`.** Final-source regressions/build pass, but native post-fix full workflow, image OCR with real Windows OCR/model, all notification/dialogs, DPI/focus/resize and production release-note history were not comprehensively exercised.
- **Long synchronous CT2 cancellation completion: `PARTIAL`.** Cancellation checkpoints have fake-adapter regression coverage. A native pre-fix worker remained in a synchronous call without terminal completion; no native run proves post-fix recovery/exit.
- **Update success dialog wording: FOLLOW-UP.** The 0.1.9 → 0.1.12 update itself passed, and About reports 0.1.12/up-to-date, but the success dialog body still says a newer version is available. This copy defect is recorded for a later update; the immutable public v0.1.12 tag was not rewritten.
- Image translation, local translation and final readiness behavior have source/worker regression evidence; do not treat that as a real-game or universal workflow guarantee.

## Terminal storage

The registered `RELEASE_RUN/candidate-0.1.12` scope (4,217,712,570 bytes) was removed after preserving compact receipts in `DEV_RUN/r012`. The canonical finalizer measured non-exempt checkout usage at 1,065,083,684 / 1,073,741,824 bytes and `.dev-env` at 6,354,778,208 / 6,442,450,944 bytes. Both inventories were complete and within the normal terminal limits. Candidate registry entries retain MISSING status with deletion provenance; no history or user data was removed.
