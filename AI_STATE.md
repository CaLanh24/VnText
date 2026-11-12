# Current checkpoint — release 0.1.19 candidate built, awaiting Brain ACCEPT (2026-11-13)

## Authority and scope
Owner (2026-11-12) authorized publishing the updater hotfix 0.1.19 and cleanup; Brain exact-candidate ACCEPT is still required BEFORE any push/tag/upload. All project work stays in `C:/v` (no external roots). Do not touch the Owner's `Desktop/vntextapp`, data, games or saves. Root is the only UI owner. Standing measured release allocation (artifact-retention.md, 2026-10-24) applies: task `release-0.1.19`, 5 GiB, 48 MiB guard, shared 11 GiB unchanged, terminal return to 1 GiB. No rebaseline, no 8-hop relax, no guard weakening.

## Release candidate
Ledger: docs/RELEASE_0.1.19.md. Built source `28f62d348045f7ae2ffd42f47a2db363e44a91c1` (epoch 035; clean tree). Setup `RELEASE_RUN/candidate-0.1.19/setup-019-28f62d3/ReleaseRoot/VNTextStudio-0.1.19-Setup.exe` sha256 `32bc1924f1c821878a3c93bcb00575e978c6f5fb92e68b57583a78e664d05a8c`; five assets and hashes in `TEST_RUN/agent-evidence/release-0.1.19/assets-019.json`. Updater fix: typed bounded baseline-rejection identity (offer + installed metadata + failed file states) so a rejected pair is never re-offered/re-downloaded across manual/auto/restart checks and any real repair or new offer starts a fresh fully verified retry.
Gates/backend: public Python groups, setup package, release verify, cleanup/epoch and WPF updater regressions PASS; actual-package updater backend A (18->19), B (legacy 0.1.7), C (17->18->19) and negatives N1-N4 (tamper, drift, interrupt+recover, health-failure rollback) PASS. Known non-PASS (not from this diff, see ledger): `test_release_regression_runner` 1 failure (harness lacks budget_policy.json; fix on `main` 3679a5d, not in the built source) and `test_wpf_workflow` 3 failures in unchanged XAML/catalog/native-journal fixtures. Native Setup/in-app/visual acceptance is NOT_PROVEN and listed for Root in the ledger.

## Git state
`main` = docs on top of 3679a5d (test-only fix, post-release maintenance); the release is built from `28f62d3`, which is an ancestor. No push has been made. Epoch hop 035 is the last available (depth 8); any further source commit would need new authority, so tag the built SHA `28f62d3`.

## Writer
Fixed Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26`, cwd `C:/v`. Root edits nothing while DEV is active.

## Storage and cleanup
At handoff: project non-exempt 3,211,968,051 B (cap 5 GiB); candidate dir 2,245,838,428 B incl. baselines 1,779,684,385 B; shared `.dev-env` 3,308,896,406 B (release-venv re-provisioned to the 52 locked distributions; old pre-lock env disposed with inventory saved). Peak 4,701,415,615 B. Cleanup plan (after ACCEPT + publish): helper-dispose `RELEASE_RUN/candidate-0.1.19` and `TEST_RUN/updater-loop-check`, prune the source worktree, keep receipts/hashes, return to the default limit. No owned process is running.
