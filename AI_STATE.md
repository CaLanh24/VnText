# Current checkpoint — 2026-11-08

Live cursor/receipts: `C:/vnrg/evidence/brain-current-checkpoint.json` (compact). This file replaces older checkpoints.

## Goal and authority
- Release 0.1.17 is PUBLISHED: https://github.com/CaLanh24/VnText/releases/tag/v0.1.17 (Latest), annotated tag `v0.1.17` → artifact source `ed3f5b58f1b0540e913785705080a1b3327d0455` (immutable; later commits are tests/docs only). Exactly five assets; public 0.1.16 and its nine assets are unchanged. Ledger `docs/RELEASE_0.1.17.md`.
- Authority: Owner explicitly authorized the release after Root ACCEPT (`C:/vnrg/evidence/release-readiness/root-accept-0.1.17.json`, aggregate sha `7ad9485a…`, Setup sha `4e56da3e…`). Standing same-scope epoch policy (CONTRACTS.md) continues; budget cap 6.25 GiB + 48 MiB abort line, shared `.dev-env` 11 GiB, no raise/waiver. No model change, free/offline only.

## Verdicts (separate; none substitutes for another)
- Tests: 61 (WPF/aggregate/guard) on `ed3f5b5`, installer 4/4, updater backend 7196/7196, 189 tool tests on `775ef19`; wrapper status `REVIEW_REQUIRED` from protected history, child exits 0.
- Build: Setup `VNTextStudio-0.1.17-Setup.exe` 285,221,888 B sha256 `4e56da3e960c2030ce6c709bda2475b7c695a4dd680f1a1217817c7b836ccf7f`; sampled peak 6,648,569,803 B < 6,660,554,752 B.
- Native: CSV small window PASS; update window dynamic footer + primary name PASS (fixture UI, later-button label NOT claimed); original-game linear 227-line route to the ending + two History looks + title/tabs PASS (attestation `brain-native017-final-20261108.json`). PUBLIC in-app update offer: NOT yet checked (checklist `release-readiness/native-checklist-public-offer.md`).
- Cleanup: scoped PASS; protected epoch history `REVIEW_REQUIRED` separately. Owner AppData 497→2 historical gap cause UNKNOWN (Owner reply is not approval); backups of the 497 retained; current-task protection exact (`tests/tools/original_game_guard.py`).
- Publication: tag and release read back anonymously (`public-readback-0.1.17.json`), sizes and sha256 equal the local inventory.

## Rules in force
- Testing/UI rule: aggregate acceptance `tests/tools/whole_game_acceptance.py` (fail-closed, hash-bound reuse), UI only where required, agent-desktop first (docs/WORKFLOW.md).
- Original game: never launched by DEV; use the guard (`verify`, dry-run `restore`, then `--execute`) around any run; Owner AppData is never written.
- Cleanup of epoch verification is memory-bounded (projection of previous registries).

## Next
- Root: public in-app offer check with `run017/native-upd016`, then DEV runs the read-only verifier and removes that fixture.
- No further publication work is open. DEV is the sole writer; no owned process is running.
