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
| Cancellation, safe flush/rollback, cancel-and-exit, retry and worker terminal state | 0.1.12 checkpoints plus 0.1.13 post-call cancellation propagation | Added a real-model test that signals cancel 21 ms into a 6.256 s CT2 call; it checks the worker terminal error, cache close, unchanged 256-row CSV and no temporary CSV | Test child passed; exact clean-commit rerun and installed cancel/exit acceptance remain pending | PARTIAL |
| Generated fixture Extract (multiple images/OCR) → local Translate/render → CSV → Patch/read-back | Existing workflow fixes exist | Re-run exact-source integration and preservation assertions | Full final-source packaged flow not proven | PARTIAL |
| Large CSV editing, search/preview/apply/undo/save/reload, dirty-file/game changes, busy-state protection | Basic large-table layout and 27k-row operation have evidence | Re-run affected cases and add missing transitions | Small window, supported DPI, focus/tab and all dirty/busy transitions not complete | PARTIAL |
| App-wide pages, dialogs, notifications, tooltips, theme and empty/loading/ready/running/cancel/error/success states | 0.1.12 changes exist | Inventory source and regression coverage | Comprehensive installed-app visual sweep not complete | PARTIAL |
| Release history, Vietnamese notes, cache/offline/latest, network failure/retry, success wording | Success wording fix and notes-history presentation fixture included | Seven-state updater presentation smoke passed on `e52ca6447966282f6d42990b50138c866bbae138`; Debug build 0 warnings/errors | Production feed/cache and installed UI not complete | PARTIAL |
| Missing SDK/model/resource discovery, download, interruption/cancel/retry and actionable failure state | Bounded, cancellable, hash-checked Ren'Py SDK download with partial cleanup and retry UX | Four SDK downloader tests passed as child process on `8d3e93c55b1db1cf48c0b5041b564c81054f3ed7`; wrapper disposition `REVIEW_REQUIRED` | Packaged user flow not verified | PARTIAL |
| Direct updater routes from supported public 0.1.8–0.1.12 baselines, restart, data/model retention, rollback/recovery | .13 epoch transition guard now explicitly supports authorized .12→.13 lineage | New no-delete transition regression child PASS (1 test) on dirty working tree; wrapper disposition `REVIEW_REQUIRED` | Exact release-scope epoch transition and installed-app matrix remain pending | PARTIAL |
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
| 2026-10-25 | Native cancellation probe on the provisioned INT8 model through `run_translate_ct2_task` | `cfe72e3d6361b58d1e5a7227eb52ee867c9fd887` plus an uncommitted test | Child PASS (1/1): cancel signalled 21 ms after native call entry; call returned at 6,256 ms; worker emitted `cancelled`, closed cache, left 0/256 translations and no CSV `.tmp`. Scope cleanup PASS. Wrapper disposition remains `REVIEW_REQUIRED` for `preexisting_test_run_content / terminal_retained_path_outside_evidence_allowlist`; the test code itself was uncommitted, so an exact-clean-commit rerun is still required. |

## Final acceptance record

Pending. This section will record source SHAs, implementation commits, exact test counts/skips, native and packaged evidence, Setup/updater matrix, release asset hashes/read-back, cleanup, and the Brain's acceptance before any public mutation.
