# Release 0.1.27 — font size option, Unity v22+ growth, cancel and uninstall fixes

Owner 2026-11-22 authorized the release (including the download of the public 0.1.26 and 0.1.7 baselines) after trying the trial build. Task `release-0.1.27`, exact `RELEASE_RUN/candidate-0.1.27`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB; user data and evidence are not deleted. Public baseline is 0.1.26.

## Scope
- Ren'Py font size option: `config.ftfont_scale` on the generated Vietnamese font only (0.70–1.50); other engines refuse it (CONTRACTS §8 owner `vntext/renpy_font_support.py`).
- Unity SerializedFile v22+ object growth with read-back as the safety gate.
- Cancelled extraction restores the previous package status; game files are released deterministically after a failed Unity load.
- Uninstall of patch-only files works when the backup folder is gone; scan/extract/patch/uninstall layout matrices.
- Version/provenance 0.1.26 → 0.1.27 and the scoped ordinary transition `release-0.1.26` → `release-0.1.27` in `tests/tools/cleanup_work_artifacts.py`.

## Evidence
`TEST_RUN/agent-evidence/release-0.1.27/`. Known limits stay out of the release body: font/image picker dialogs and image translation through the UI, a real patch-to-patch upgrade on an installed game, the font size slider in a running game.
