# VNText Studio 0.1.13 — implementation and acceptance ledger

**Status: IN PROGRESS.** This ledger carries forward the remaining acceptance gaps recorded for public 0.1.12 and the Owner's approved remediation plan. Public 0.1.12 remains immutable. Target release: 0.1.13.

## Starting point and publication boundary

- Starting source: `a223aab86a151e72e57f5a95c319021a751ee4a3` on clean `main`.
- Public baseline at task start: 0.1.12. Recheck GitHub latest and exact tag/source before release mutation.
- Source commits may be created locally for review. Do not push, create/update a tag or release, upload assets, or change the public latest feed until Brain records `ACCEPT` for the completed implementation, tests, packaged native integration, Setup and updater matrix.
- Real-game E2E remains a separate `NOT TESTED` item under the existing Owner deferral. That does not waive generated-fixture integration or installed-app acceptance.

## Acceptance ledger

`PASS` requires evidence for the named scope and exact SHA. Unit/fake coverage does not establish native behavior. `PARTIAL`, `UNKNOWN`, `RUNTIME_ONLY`, `UNSUPPORTED`, `BLOCKED`, and `NOT TESTED` remain explicit until their own criteria pass.

| Scope | Implementation | Focused/affected tests | Packaged/native evidence | Status at start |
|---|---|---|---|---|
| Task-owned progress, late-event isolation, ETA, stage-specific Extract/Translate/Patch progress | 0.1.12 fixes exist; audit remaining cross-page/stale-event cases | Existing regression evidence is tied to 0.1.12 | Final packaged multi-stage interaction not complete | PARTIAL |
| Cancellation, safe flush/rollback, cancel-and-exit, retry and worker terminal state | 0.1.12 checkpoints plus 0.1.13 post-call cancellation propagation | Exact-source in-process pipeline probe: real CT2 adapter, 256-row CSV unchanged, cache closed, no temp CSV; worker-process stdin cancel/ack/complete/exit with real CT2 PASS 1/1 on `64fd0a0` | Packaged WPF cancel-and-exit and retry-after-cancel not proven; worker-process evidence does not establish UI behavior | PARTIAL |
| Generated fixture Extract (multiple images/OCR) → local Translate/render → CSV → Patch/read-back | Existing workflow fixes exist | Re-run exact-source integration and preservation assertions | Full final-source packaged flow not proven | PARTIAL |
| Large CSV editing, search/preview/apply/undo/save/reload, dirty-file/game changes, busy-state protection | Basic large-table layout and 27k-row operation have evidence | Re-run affected cases and add missing transitions | Small window, supported DPI, focus/tab and all dirty/busy transitions not complete | PARTIAL |
| App-wide pages, dialogs, notifications, tooltips, theme and empty/loading/ready/running/cancel/error/success states | 0.1.12 changes exist | Inventory source and regression coverage | Comprehensive installed-app visual sweep not complete | PARTIAL |
| Release history, Vietnamese notes, cache/offline/latest, network failure/retry, success wording | Success wording and bounded release-history presentation included | Seven-state updater presentation smoke passed on `e52ca6447966282f6d42990b50138c866bbae138`; exact-source WPF workflow suite also passes (see progress log) | Production feed/cache and installed UI not complete | PARTIAL |
| Missing SDK/model/resource discovery, download, interruption/cancel/retry and actionable failure state | Bounded, cancellable, hash-checked Ren'Py SDK download with partial cleanup and retry UX | Exact-source SDK downloader suite passed 4/4 on `b31d3514672dae40414174f797a0d93e69a908a9` | Packaged user flow not verified | PARTIAL |
| Direct updater routes from supported public 0.1.8–0.1.12 baselines, restart, data/model retention, rollback/recovery | .13 epoch transition guard explicitly supports authorized .12→.13 lineage | Exact .13 no-delete epoch transition and scope reactivation regression passed; wrapper disposition `REVIEW_REQUIRED` for inherited terminal-root content | Public baseline package matrix and installed-app apply/restart/rollback remain pending | PARTIAL |
| Exact-source regression, Setup, updater packages/feed, release verifier and independent worker smoke | Not started for 0.1.13 | Full release gate pending | Fresh Setup and update installs pending | NOT STARTED |
| Public GitHub release and exact asset read-back | Hard-held for Brain acceptance | N/A | No 0.1.13 publication yet | NOT STARTED |
| Real-game E2E | Separate Owner-deferred campaign | N/A | No real game used | NOT TESTED |

## Execution order

1. Reconcile the 0.1.12 evidence and source implementation against this ledger; inspect the release and artifact contracts before allocating candidate data.
2. Fix the confirmed final-source gaps first: cancellation/terminal behavior, remaining progress ownership, update-success wording, SDK/resource recovery UX, and any uncovered CSV/theme defects.
3. Run focused and affected regression sequentially. Persist exact-source receipts before moving to the next dependent gate.
4. Run generated-fixture packaged Extract → Translate → CSV → Patch/read-back and cancellation/dirty-state scenarios.
5. Run installed UI review across the named pages/dialogs and supported window/DPI/focus states. Record screenshots and exact executable hash.
6. Build and verify Setup plus all supported direct updater routes. Exercise offer/download/apply/restart and rollback/recovery with data/model preservation on installed baselines.
7. Run exact-source full regression, release verifier, independent working-directory worker smokes and fresh Setup acceptance; resolve unexplained failures/skips.
8. Produce Vietnamese user-facing release notes focused on changes to features and interface. Keep technical evidence in this ledger/receipts, not the GitHub body.
9. Persist a review packet; wait for Brain `ACCEPT`, then publish source/tag/release/assets/latest-feed and verify public read-back. Clean registered temporary scope to the terminal storage limits.

## Progress and evidence

| Date | Change/evidence | SHA | Outcome / remaining work |
|---|---|---|---|
| 2026-10-25 | Ledger opened from the accepted 0.1.12 release record and Owner plan | `a223aab` | Release 0.1.12 remains public and immutable. No 0.1.13 candidate has been built. |
| 2026-10-25 | Added bounded Ren'Py SDK download/cancel/retry handling, updater success wording, and initial release gates | `8d3e93c55b1db1cf48c0b5041b564c81054f3ed7` | SDK child tests 4/4 PASS; canonical wrapper is `REVIEW_REQUIRED` because the existing `TEST_RUN` terminal root contains pre-existing out-of-scope content. No cleanup of historical roots was attempted. |
| 2026-10-25 | Fixed updater presentation fixture to check the bounded release-history layout with an actual history entry | `e52ca6447966282f6d42990b50138c866bbae138` | Debug build 0 warnings/errors; all 7 updater presentation states PASS. |
| 2026-10-25 | Prospective epoch preflight initially rejected the .12→.13 transition with `transition_active_epoch_release_task_mismatch` and `transition_source_version_mismatch`; added a narrow .12→.13-only path using the recorded .13 authorization and preserving rollback/registry history | `e52ca6447966282f6d42990b50138c866bbae138` plus uncommitted transition guard/test | Focused child regression PASS (1/1); canonical wrapper is `REVIEW_REQUIRED` because of the same pre-existing terminal-root condition. The actual epoch plan/apply has not yet been rerun on a clean commit. |
| 2026-10-25 | Real-model cancellation probe through `run_translate_ct2_task` in-process; this is pipeline evidence, not a worker-process protocol test | `cfe72e3d6361b58d1e5a7227eb52ee867c9fd887` plus the committed test at `594f307` and exact-source rerun at `b31d351` | Child PASS (1/1): instrumented real CT2 adapter call returned after 8,451 ms; cancellation was signalled 21 ms after adapter-call entry; cache closed; CSV retained 256 blank rows and no `.tmp`. The callback's terminal payload was `cancelled`; it did not prove worker stdin/ack/process exit or WPF cancel-and-exit. Wrapper disposition `REVIEW_REQUIRED` is separate from child PASS because of inherited terminal-root content. |
| 2026-10-25 | Committed the native CT2 cancellation regression and transitioned/verified the .13 epoch at exact clean source | `594f3079ef6309d74391f7549572065298d605d4` | No-delete transition PASS, full inventory 743 entries; updater and SDK focused gates still pending exact-source reruns. |
| 2026-10-25 | Release wrapper preflight found the registered empty .13 candidate reconciled to `MISSING`; the 1,077,398,628-byte checkout exceeded the default 1 GiB, so no test child started | `594f3079ef6309d74391f7549572065298d605d4` | Added a fail-closed reactivation path for only the exact zero-byte .13 candidate record with no deletion provenance, plus refusal coverage when deletion evidence exists. This changes no historical .12 record and performs no deletion. On `b31d351`, the exact .13 epoch was transitioned and verified, the scope reactivated, and the scope reactivation regression passed 1/1. |
| 2026-10-25 | Exact-source focused regression on clean `b31d3514672dae40414174f797a0d93e69a908a9` | `b31d3514672dae40414174f797a0d93e69a908a9` | SDK downloader 4/4 PASS; real CT2 pipeline cancellation 1/1 PASS; generated worker Extract→Translate→Patch 1/1 PASS; WPF workflow suite 15/15 PASS. Each child exited 0 with 0 failures/errors/skips. Canonical wrapper disposition is `REVIEW_REQUIRED` due pre-existing `TEST_RUN` terminal-root content; cleanup reported zero blocked roots, locked roots or errors. No historical data was removed. Test receipts: `canonical-run-fef04da1a25b4438b96b38e002dc6efd.md`, `canonical-run-cf4f887abe5f4edba6fb48d92ea1e98a.md`, `canonical-run-5561def6018e40aeab11f5ce2a2799a6.md`, `canonical-run-e0760a1ee74e4443ba843735dcada32e.md`. |
| 2026-10-25 | Added process-level real-model cancellation acceptance coverage | `33412e97089cf37f20888c488bee4b1ac9c9afe3` | First child run (`canonical-run-3eb8994898b9478082ee6f08006582c4.md`) failed 1/1 before model inference because the observer launcher passed a string where the model API requires `Path`; this was test-harness setup only, not a product failure. The harness correction was committed as `64fd0a0`. The acceptance checks actual JSON worker stdin `cancel`, accepted `cancel_ack`, terminal `complete(error=cancelled)`, post-cancel ping, normal exit, unchanged 256-row CSV and no temp file. |
| 2026-10-25 | Exact-source rerun of the process-level real-model cancellation acceptance | `64fd0a059e1cd792b970c5865453699ad174fb53` | Child PASS 1/1, 0 failures/errors/skips/warnings (`canonical-run-e1c3bbfada874068bc426065dc700be9.md`): `cancel_ack=accepted`, terminal `cancelled`, cancel sent 15 ms after adapter entry and before the 6,455 ms call returned, ping after cancel, worker exit 0, 256 source rows with 0 persisted translations, no temporary CSV. Wrapper cleanup disposition `REVIEW_REQUIRED` (0 blocked/locked roots, 0 errors) is separate from child PASS; non-exempt bytes after run 1,094,764,763 within the temporary release ceiling. Packaged WPF cancel-and-exit and retry remain `PARTIAL`. The failed `33412e9` run's non-cancel error carried the cancelled/interrupted `diagnostic_action`; classification is unaudited (`UNKNOWN`). |

## Final acceptance record

Pending. This section will record source SHAs, implementation commits, exact test counts/skips, native and packaged evidence, Setup/updater matrix, release asset hashes/read-back, cleanup, and the Brain's acceptance before any public mutation.
