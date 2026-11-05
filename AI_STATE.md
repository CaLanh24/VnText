# Current checkpoint — 2026-11-05

Live cursor/receipts: `C:/vnrg/evidence/brain-current-checkpoint.json` (compact). This file replaces older checkpoints.

## Goal and authority

- Release 0.1.16: Owner 2026-11-05 accepts usable raw Vietnamese output even with idiom/context/style errors; users may edit it or use another tool. Free/offline is mandatory. App-induced corruption, lost protected content and false completion remain blockers. Publish after technical/raw-output acceptance; perfect semantic fidelity is no longer a release prerequisite.
- Budget unchanged: release-0.1.16 cap 6.25 GiB, shared `.dev-env` 11 GiB, no raise/waiver. The publisher exceeded the cap transiently (`publish016-run5.log`: 7,971,430,756 B before cleanup > 6,710,886,400 B; run3 8.89 GB); that incident stays on record. Now 4.94 GB.
- Owner authorised a bounded direct install/uninstall test of the product patch on the ORIGINAL game (not arbitrary edits, deletion or save changes) and the scoped cleanup of the test artifacts it produced.
- Epoch chain: one-use rebaseline `owner-20261105-af0d059` consumed → `epoch-20261105-rebase016-0550dc4` → ordinary hops host8-37640ef, docs-92d8723, homograph-6660290, cachefp-79c93fc, plus one docs hop for the commit that carries this file.

## Source and candidate

- Product source `79c93fcec9ac1962887eb2c51a24ac4da467544e`: `6660290` stops the post-translation repair from rewriting correct Vietnamese (keys do/so/in/me/men/man protected in both repair routes, Unicode- and combining-mark-aware boundaries, literal backslash-n branch no longer a bare substring replace, short dictionary keys pinned by a test); `79c93fc` adds `POSTPROCESS_VERSION` to the translation-cache strategy fingerprint so stale validated-only records miss (kept, never deleted). Gates: 347 translation/mt tests PASS at 6660290, 56 focused tests PASS at 79c93fc, 0 skips. Frozen/user-edited CSV rows are never rewritten; owner-approved memory is untouched; a corrupted existing CSV row is repaired only by an explicit retranslate.
- Brain paired review of the fix: 12 better / 1 tie / 0 worse (P1). P2 (name-cut retry) mixed and P3 (beam 4) no signal, so neither changed. P4 absolute review: semantic NOT ACCEPTED, and its 40 rows were not unseen (32 had appeared in the P3 holdout). The old OPUS “32 S2 / 5 F” was measured on the stale out11 build and is NOT the current rate; no fresh absolute rate exists.
- Intermediate candidate `42f9d2d` at `RELEASE_RUN/candidate-0.1.16/setup-exact-run6/ReleaseRoot`: real packaged-model smoke and native CSV display PASS; installer4 PASS, translation350 PASS (wrapper cleanup separately REVIEW_REQUIRED). It is NOT final: a further confirmed bug removed Vietnamese words matching arbitrary placeholder names (`{an}` erased `an` in `bình an`). This commit bounds echo deletion to known English vocabulary/technical identifiers and protects structured output; cache repair identity is version3. Rebuild is required. Superseded candidate37640ef hashes are retained; its owned binary tree was disposed after replacement review. Live receipts/checkpoint own exact build paths/hashes.

## Original-game direct test (functional only)

- Product installer CLI on the original game: preflight, install of exactly 2 new files (`game/tl/vietnamese/vntext.rpy`, `game/zzz_vntext_vietnamese.rpy`, 0 overwrites), exact read-back, uninstall: PASS. Gameplay is NOT PROVEN: Brain's computer-use calls timed out while the game (PID 13464) held all CPUs at 100%; it was closed gracefully; no application-stability PASS.
- The run wrote outside the patch: 2 `.rpyb` cache files, 145 `renpy/**/*.pyc`, and `game/saves/persistent` (despite the APPDATA override). All were restored/removed from verified bytes (backup + the original archive `Desktop/game/Cucked_by_My_Wife.rar`, hash-matched against the pre-test manifest; persistent kept as a 1742-byte copy). Final: 1433 original files and 483 owner RenPy appdata files identical to the manifest.
- Future launch needs, not tested: `PYTHONDONTWRITEBYTECODE=1` set before Python starts, and per-file isolation/backup of `game/saves` and `game/cache`; no new game attempt is planned. The RAR, the original game and user data are preserved.
- Receipts: `C:/vnrg/evidence/direct-install-result.json`, `direct-cleanup-result.json`, `direct-restore-result.json`, `direct-patch-inventory.json`, `direct-original-fresh.json`; package kept at `C:/vnrg/outP` (installer + 2-file payload).

## Open blockers

- Raw OPUS word-sense/context/style errors remain documented; Owner accepts these for a rough draft. App must not introduce Vietnamese word corruption; focused regression and exact packaged-output checks remain mandatory.
- Cleanup `REVIEW_REQUIRED` (protected history, retained patch-installer containers), never waived. The managed game copy `TEST_RUN/realgame016/play` and `C:/vnrg/game-copy-v2` were disposed with compact evidence.
- Next: gate this fix, build an exact candidate, finish required direct updater routes, bounded native/raw-output acceptance and publication. No new model experiment, game launch or whole-game copy. See `docs/RELEASE_0.1.16.md`.

## Writer

- Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3` hit session quota (resets17:10JST, live tool failure cursor1326). Codex is temporary sole writer; return the same DEV at a safe boundary after recovery. No duplicate build/model children remained at takeover; owned processes and current receipts are tracked in the external checkpoint.
