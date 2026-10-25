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
| Cancellation, safe flush/rollback, cancel-and-exit, retry and worker terminal state | 0.1.12 checkpoints exist | Fake-adapter regressions exist | Post-fix synchronous CT2/native terminal completion not proven | PARTIAL |
| Generated fixture Extract (multiple images/OCR) → local Translate/render → CSV → Patch/read-back | Existing workflow fixes exist | Re-run exact-source integration and preservation assertions | Full final-source packaged flow not proven | PARTIAL |
| Large CSV editing, search/preview/apply/undo/save/reload, dirty-file/game changes, busy-state protection | Basic large-table layout and 27k-row operation have evidence | Re-run affected cases and add missing transitions | Small window, supported DPI, focus/tab and all dirty/busy transitions not complete | PARTIAL |
| App-wide pages, dialogs, notifications, tooltips, theme and empty/loading/ready/running/cancel/error/success states | 0.1.12 changes exist | Inventory source and regression coverage | Comprehensive installed-app visual sweep not complete | PARTIAL |
| Release history, Vietnamese notes, cache/offline/latest, network failure/retry, success wording | Synthetic history/cache exists; success wording defect recorded | Production parser/cache/update tests need review | Production feed and final installed UI not complete | PARTIAL |
| Missing SDK/model/resource discovery, download, interruption/cancel/retry and actionable failure state | Audit implementation and resource contracts | Add/fix tests where absent | Packaged user flow not verified | UNKNOWN |
| Direct updater routes from supported public 0.1.8–0.1.12 baselines, restart, data/model retention, rollback/recovery | 0.1.12 routes exist; verify 0.1.12→0.1.13 and supported older baselines | Re-run publisher/updater invariants and route tests | Installed-app matrix is incomplete | PARTIAL |
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

## Final acceptance record

Pending. This section will record source SHAs, implementation commits, exact test counts/skips, native and packaged evidence, Setup/updater matrix, release asset hashes/read-back, cleanup, and the Brain's acceptance before any public mutation.
