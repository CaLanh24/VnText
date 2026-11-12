# Current checkpoint — release 0.1.19 candidate built, awaiting Brain ACCEPT (2026-11-13)

## Authority and scope
Owner (2026-11-12) authorized publishing the updater hotfix 0.1.19 and cleanup; Brain exact-candidate ACCEPT is still required BEFORE any push/tag/upload. All project work stays in `C:/v` (no external roots). Do not touch the Owner's `Desktop/vntextapp`, data, games or saves. Root is the only UI owner. Standing measured release allocation (artifact-retention.md, 2026-10-24) applies: task `release-0.1.19`, 5 GiB, 48 MiB guard, shared 11 GiB unchanged, terminal return to 1 GiB. No rebaseline, no 8-hop relax, no guard weakening.

## Release candidate
Ledger: docs/RELEASE_0.1.19.md. Built source `28f62d348045f7ae2ffd42f47a2db363e44a91c1` (epoch 035; clean tree). Setup `RELEASE_RUN/candidate-0.1.19/setup-019-28f62d3/ReleaseRoot/VNTextStudio-0.1.19-Setup.exe` sha256 `32bc1924f1c821878a3c93bcb00575e978c6f5fb92e68b57583a78e664d05a8c`; five assets and hashes in `TEST_RUN/agent-evidence/release-0.1.19/assets-019.json`. Updater fix: typed bounded baseline-rejection identity (offer + installed metadata + failed file states) so a rejected pair is never re-offered/re-downloaded across manual/auto/restart checks and any real repair or new offer starts a fresh fully verified retry.
Gates/backend (built source 28f62d3): public Python groups, setup package, release verify, cleanup/epoch, WPF updater regressions and actual-package updater backend A/B/C + N1-N4 PASS. Four gate failures were investigated (see ledger): 3 stale/real test findings (2 stale assertions, 1 real missing English catalog entry present since 0.1.18) and the runner harness; fixes are on `main` @ 0b38d5b (maintenance/harness source, NOT in the built product, not an exact-SHA gate). On 0b38d5b 36/37 WPF workflow tests and the runner contract pass; two tests stop only at the final cleanup report because the project (3.24 GB, candidate retained for Root native) exceeds the default 1 GiB; re-run after Root native + cleanup. Native Setup/in-app/visual acceptance is NOT_PROVEN (Root).

## Git state
`main` = docs on top of 3679a5d (test-only fix, post-release maintenance); the release is built from `28f62d3`, which is an ancestor. No push has been made. Epoch hop 035 is the last available (depth 8); any further source commit would need new authority, so tag the built SHA `28f62d3`.

## Writer
Fixed Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26`, cwd `C:/v`. Root edits nothing while DEV is active.

## Storage and cleanup
At handoff: project non-exempt 3,211,968,051 B (cap 5 GiB); candidate dir 2,245,838,428 B incl. baselines 1,779,684,385 B; shared `.dev-env` 3,308,896,406 B (release-venv re-provisioned to the 52 locked distributions; old pre-lock env disposed with inventory saved). Peak 4,701,415,615 B. Cleanup plan (after ACCEPT + publish): helper-dispose `RELEASE_RUN/candidate-0.1.19` and `TEST_RUN/updater-loop-check`, prune the source worktree, keep receipts/hashes, return to the default limit. No owned process is running.

## Native boundary and pending decision (2026-11-13)
Root native: fresh Setup `32bc1924…` interactively installed to `RELEASE_RUN/candidate-0.1.19/native019` (no shortcuts; EXE `06c64dd2…` matches; About shows 0.1.19; closed cleanly; registered `release019-native-install`, RETAINED under the candidate scope). This is fresh Setup/app native PASS only; upgrade, uninstall, Setup-required native, public in-app update and full visual acceptance are NOT_PROVEN. Open decision for Brain/Owner: publish `28f62d3` as built, or request ONE no-delete rebaseline for prepared source `cba2a80` (catalog fix + harness fixes) — draft plan `docs/RELEASE_0.1.19_REBASELINE_PLAN.md`, NOT applied (no Owner authority yet). Same scope/5 GiB/shared 11 GiB/48 MiB guard/CAS/rollback/8-hop if granted. No push/tag/upload.
