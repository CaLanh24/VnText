# Current checkpoint - release 0.1.18 PUBLISHED (2026-11-12), post-publication client check pending

Owner 2026-11-12: fix remaining issues, then release. Brain ACCEPTed the exact candidate; v0.1.18 is PUBLIC (https://github.com/CaLanh24/VnText/releases/tag/v0.1.18, Latest, tag c543869 -> source 956a704, five assets verified by download/digest; v0.1.17 assets untouched). Root native: functional PASS fresh Setup/uninstall/upgrade+canaries, visual capture NOT_PROVEN. Details and exact hashes: docs/RELEASE_0.1.18.md; compact receipts: C:/vnrg/evidence/release-0.1.18/ (candidate-receipt.json).

## Writer
Fixed Claude DEV72329c3d-5883-4cc8-8d14-60c73886ebd3 / session76922e45-71b2-47a9-be97-cf18b927ae26 is the current sole source writer and owns release diagnostics/build/package/cleanup to terminal (this session after cursor 1641; cursor ~1700 at this handoff). The 1641 "Root temporary writer / no new task" text is HISTORICAL. Root is sole UI owner; no UI/native was run by DEV. No other writer, app or worker is running.

## Source / candidate
- Built source `956a7046e3f960f8a08c7338c4cbe50d44cd05cc` (clean worktree snapshot `RELEASE_RUN/candidate-0.1.18/source`); later commits are docs only (no rebuild). Epoch chain `release-0.1.18` hops 029..032 (+docs hop), ordinary 8-hop guard unchanged, no rebaseline.
- Setup `RELEASE_RUN/candidate-0.1.18/setup-018-956a704/ReleaseRoot/VNTextStudio-0.1.18-Setup.exe` 286,726,656 B sha256 `454ef46fa68d6211f22bef02981b8405fa28e4bbb300898a8d3e68e9bc5e930a`; payload 7,327 files; app exe sha256 `9d0d6f291da5d87bdb6274f04617f39af4b5a9e139e6c80acc25775a0b890156`. Updates: `full-app-update-0.1.18-f875f83f609f3aa2.zip` (+current.json, legacy 0.1.7 route) and `full-app-update-from-0.1.17-to-0.1.18-3e6a5d4897310aef.zip` (+current.json). Baseline public v0.1.17 (ed3f5b5, Setup sha `4e56da3e…`) and legacy v0.1.7 verified by digest.
- Changes since v0.1.17 include the new glossary masking fix (whole-word, non-cascading, collision-free, v1+v2, strategy `glossary-masking-3`), publisher installer-before-smoke fix, 0.1.18 task/epoch support, cold-registry epoch filter, regenerated icons, locked dependency inventory in THIRD_PARTY_NOTICES.

## Gates and limits
PASS: public Python groups (206 tests, 0 skip), setup package 13 (no PYTHONUTF8), release verify/publisher guards 11, locked-dependency check, `publish.ps1` exit 0 with DEV and Release worker smoke, updater backend on real packages for both routes (0.1.17 and legacy 0.1.7: version 0.1.18, 0 mismatch, canaries intact, health PASS). Updater rollback reused from 0.1.17 (code unchanged). NOT_PROVEN: Setup install/upgrade/uninstall native, in-app public update after publish, DPI/theme, whole-game translation quality. Offline translation remains a rough draft.

## Storage / authority
Standing 2026-10-24 temporary allocation under task `release-0.1.18` (3 GiB, measured to 4.5 GiB = 4,831,838,208 B; shared 11 GiB, 48 MiB guard unchanged); sampled peak 3,968,864,530 B. Dependency acquisition used the DEV network/command authority (LOCAL-WORKFLOW 2026-10-25), 52 locked wheels into the new isolated `.dev-env/release-venv-0.1.18`; existing `.venv`/`release-venv`/model/user data untouched. Scratch already disposed (0 refused). Remaining candidate/baseline/source worktree/venv stay until Brain ACCEPT + publish; then dispose and return to the default limit.

## Next boundary
Root runs the finite public in-app client check (0.1.17 app -> 0.1.18) and then sends the final cleanup instruction. Then (DEV): valid epoch hop for the docs HEAD, dispose `RELEASE_RUN/candidate-0.1.18/{source,setup-018-956a704,release-baselines}` and the venv decision, return project to <=1 GiB, keep receipts/hashes. Budget correction: real abort line 4,781,506,560 B (profile release-0.1.18, 4.5 GiB); earlier "free_to_abort" numbers used the wrong 6.25 GiB cap (`budget-correction.json`). Native-install/upgrade fixtures already disposed.
