# Release 0.1.32 — safe one-step patch upgrade, install journal and crash recovery

Owner (DEV session 2026-11-24, relayed design by Brain) asked for a safe one-step patch upgrade and confirmed its release once the gate passes. Task `release-0.1.32`, exact `RELEASE_RUN/candidate-0.1.32`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB; user data and evidence are preserved. The public 0.1.26 and 0.1.29 Setups (old-patch scenarios) and the 0.1.31 and 0.1.7 baselines are downloaded with the Owner's explicit permission in the DEV session.

## Scope
- Build a new patch from a game that already carries a VNText patch: files the ownership receipt proves are VNText's own, byte-identical to its top layer, are skipped as existing target state (`vntext/vntext_ownership.py`, `patch_renpy.py`, `renpy_extract.py`). The new patch records those bytes as its `original_sha256`, so the installer upgrades in one step (layer B over A). A patch file edited by hand or without a receipt still blocks the build with the 0.1.31 message.
- Installer transaction journal `install_journal.json` written before the first game write and removed after state and receipt are saved. The next install or uninstall recovers an interrupted install: complete installs are kept, partial ones are rolled back to the pre-install state (files, created files, temporaries, receipt).
- Uninstall and "Về bản gốc sạch" can be re-run after an interruption: already-restored files are accepted; first-original copies are deleted only after the receipt is saved.
- "Về bản gốc sạch" also works when the patch at hand is not the installed one (found by the UI smoke: after A → B → uninstall B the game holds A while the app's package is B, and the button was disabled although the message pointed to it). It restores from the ownership receipt alone: every VNText file must equal its newest layer (or already be at its first original after a cut-off run); an edited file is refused without writing.
- The old remove-then-install path is unchanged.
- Version/provenance 0.1.31 → 0.1.32 and the scoped ordinary transition `release-0.1.31` → `release-0.1.32`.

## Safe defaults chosen (no Owner question)
- Only receipt-proven, unedited VNText files are skipped; anything else still fails closed (avoid overwriting user edits).
- Recovery rolls an incomplete install back rather than forward (the pre-install state is fully proven by backups; a forward finish is not).
- Recovery runs automatically at the start of install/uninstall, never on its own in the background.

## Evidence
Receipts in `TEST_RUN/agent-evidence/release-0.1.32/`: installer harness 103 checks with a simulated crash at every step of install, upgrade A→B, uninstall and clean restore; E2E Ren'Py (real SDK) A → B built from the installed game → one-step upgrade → uninstall = A → clean original = original hashes; patches made and installed by the real 0.1.26 and 0.1.29 releases upgraded in one step, uninstalled back to the old patch, and restored byte-identical (`old-release-upgrade.json`).
