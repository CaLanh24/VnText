# Current checkpoint — 2026-11-05

Live cursor/receipts: `C:/vnrg/evidence/brain-current-checkpoint.json` (compact). This file replaces older checkpoints.

## Goal and authority

- Release 0.1.16 preparation under Owner “nghiệm thu đi, xử lý nốt các vấn đề tồn đọng rồi release”. Publication is BLOCKED: no push/tag/release until Brain/Owner ACCEPT; semantic game quality is NOT ACCEPTED.
- Budget unchanged: release-0.1.16 cap 6.25 GiB, shared `.dev-env` 11 GiB, no raise/waiver. The publisher exceeded the cap transiently (`publish016-run5.log`: 7,971,430,756 B before cleanup > 6,710,886,400 B; run3 8.89 GB); that incident stays on record. Now 4.94 GB.
- Owner authorised a bounded direct install/uninstall test of the product patch on the ORIGINAL game (not arbitrary edits, deletion or save changes) and the scoped cleanup of the test artifacts it produced.
- Epoch chain: one-use rebaseline `owner-20261105-af0d059` consumed → `epoch-20261105-rebase016-0550dc4` → ordinary hops host8-37640ef, docs-92d8723, homograph-6660290, cachefp-79c93fc, plus one docs hop for the commit that carries this file.

## Source and candidate

- Product source `79c93fcec9ac1962887eb2c51a24ac4da467544e`: `6660290` stops the post-translation repair from rewriting correct Vietnamese (keys do/so/in/me/men/man protected in both repair routes, Unicode- and combining-mark-aware boundaries, literal backslash-n branch no longer a bare substring replace, short dictionary keys pinned by a test); `79c93fc` adds `POSTPROCESS_VERSION` to the translation-cache strategy fingerprint so stale validated-only records miss (kept, never deleted). Gates: 347 translation/mt tests PASS at 6660290, 56 focused tests PASS at 79c93fc, 0 skips. Frozen/user-edited CSV rows are never rewritten; owner-approved memory is untouched; a corrupted existing CSV row is repaired only by an explicit retranslate.
- Brain paired review of the fix: 12 better / 1 tie / 0 worse (P1). P2 (name-cut retry) mixed and P3 (beam 4) no signal, so neither changed. P4 absolute review: semantic NOT ACCEPTED, and its 40 rows were not unseen (32 had appeared in the P3 holdout). The old OPUS “32 S2 / 5 F” was measured on the stale out11 build and is NOT the current rate; no fresh absolute rate exists.
- Candidate `37640ef` (nine assets, `C:/v/RELEASE_RUN/candidate-0.1.16/setup-exact-run5/ReleaseRoot`, Setup sha256 `ca407dba34e65d6dc665a920abc73f5da6a73a835236015d5d64f1b9d50a80c7`, hashes in `C:/vnrg/evidence/release-0116-final-hashes.json`) is OLD: it was built before 6660290/79c93fc and was not rebuilt or re-tested with the new source. Its Setup/updater/installer proofs stay valid only for components unchanged since 37640ef (the patch installer `e87ac3f6…689f` is unchanged: empty git diff of wpf_app/release).

## Original-game direct test (functional only)

- Product installer CLI on the original game: preflight, install of exactly 2 new files (`game/tl/vietnamese/vntext.rpy`, `game/zzz_vntext_vietnamese.rpy`, 0 overwrites), exact read-back, uninstall: PASS. Gameplay is NOT PROVEN: Brain's computer-use calls timed out while the game (PID 13464) held all CPUs at 100%; it was closed gracefully; no application-stability PASS.
- The run wrote outside the patch: 2 `.rpyb` cache files, 145 `renpy/**/*.pyc`, and `game/saves/persistent` (despite the APPDATA override). All were restored/removed from verified bytes (backup + the original archive `Desktop/game/Cucked_by_My_Wife.rar`, hash-matched against the pre-test manifest; persistent kept as a 1742-byte copy). Final: 1433 original files and 483 owner RenPy appdata files identical to the manifest.
- Future launch needs, not tested: `PYTHONDONTWRITEBYTECODE=1` set before Python starts, and per-file isolation/backup of `game/saves` and `game/cache`; no new game attempt is planned. The RAR, the original game and user data are preserved.
- Receipts: `C:/vnrg/evidence/direct-install-result.json`, `direct-cleanup-result.json`, `direct-restore-result.json`, `direct-patch-inventory.json`, `direct-original-fresh.json`; package kept at `C:/vnrg/outP` (installer + 2-file payload).

## Open blockers

- Semantic quality NOT ACCEPTED; most remaining errors are raw OPUS word-sense/syntax errors (identical to the raw CT2 output), name-guard false names, leading-ellipsis sentences.
- Cleanup `REVIEW_REQUIRED` (protected history, retained patch-installer containers), never waived. The managed game copy `TEST_RUN/realgame016/play` and `C:/vnrg/game-copy-v2` were disposed with compact evidence.
- Next only after Brain/Owner decide: rebuild a candidate from `79c93fc` or later and re-test Setup/updater before any release; docs/ledger: `docs/RELEASE_0.1.16.md`.

## Writer

- Persistent Claude DEV (sole writer); Brain Codex coordinates. No owned processes running.
