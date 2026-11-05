# Current checkpoint — 2026-11-05

Live cursor/receipts: `C:/vnrg/evidence/brain-current-checkpoint.json` (compact; `release_technical_acceptance` holds the table and asset hashes). This file replaces older checkpoints.

## Goal and authority

- Release 0.1.16 preparation under Owner “nghiệm thu đi, xử lý nốt các vấn đề tồn đọng rồi release”. Publication is BLOCKED: no push/tag/release until Brain/Owner ACCEPT.
- Budget unchanged: release-0.1.16 cap 6.25 GiB, shared `.dev-env` 11 GiB, no raise/waiver. The publisher exceeded the cap transiently (`publish016-run5.log`: cleanup.before non-exempt 7,971,430,756 B > 6,710,886,400 B; after 6,588,710,482 B; run3 peaked 8.89 GB). That incident stays on record; now 5.19 GB.
- One-use rebaseline `owner-20261105-af0d059` is consumed. Chain: `epoch-20261105-rebase016-0550dc4` → ordinary hop `epoch-20261105-host8-37640ef` → one docs-only hop for this commit (six ordinary hops remain after it).

## Source and candidate

- Candidate built from source `37640ef0d081435800501bc97ba8e143db7833e6` (clean main). `37640ef` fixes `release/publish.ps1`: the self-contained patch installer uses the cached .NET 8 singlefilehost pack (SDK 10 host could not start the .NET 8 runtime, 0x80131522); fail-closed if the pack is absent. The docs-only commit after it is NOT the artifact source; artifact manifests keep `37640ef` and are not relabelled.
- Candidate (nine assets, hashes re-checked): `C:/v/RELEASE_RUN/candidate-0.1.16/setup-exact-run5/ReleaseRoot` — Setup 284,375,040 B sha256 `ca407dba34e65d6dc665a920abc73f5da6a73a835236015d5d64f1b9d50a80c7`; Updates: full-app current + from-0.1.13/0.1.14/0.1.15 routes (zip + current.json each). Legacy 0.1.7 uses the full-app current feed. Per-file sha256 in `C:/vnrg/evidence/release-0116-final-hashes.json`. Packaged installer `VNTextPatchInstaller.exe` sha256 `e87ac3f6f67885b0fb82eb7362e70eaad48932f3dda8c4e2fcf8eb4cd83a689f`. Model tree unchanged from public 0.1.15 (guard not loosened).

## Technical evidence (no re-run needed)

- PASS: clean-source build/publish; installer 4/4 under a private no-framework .NET root plus GUI probe; Setup/updater/release-verify/cleanup unit 168 PASS, 0 skip; reused WPF 26/74/34/worker5 and Setup VI/EN wizard + installer5 (inputs unchanged).
- Native (Brain, `C:/vnrg/evidence/native*`): Setup 016 VI6/EN6 PASS, installed worker5 smoke PASS; updater 0.1.15/0.1.14/0.1.13 → 0.1.16 PASS via product `--apply-full-app-update` CLI (exit 0, 7196/7196 files, canaries unchanged) with success dialog and About 0.1.16 observed (`native016/014/013-updater-receipt.json`).
- Boundaries: baseline apps 014/013 were not launched (appPid = exited Setup PID); the 015 app was launched and closed. UI offer from the baseline with a local-only source is NOT PROVEN for all three (not PASS); published baselines unchanged. The 0.1.7 route has no native run. No real-game native run on this candidate.

## Open blockers

- Semantic game quality NOT ACCEPTED (OPUS64: 32 S2 / 5 F); Owner scope question pending. Product route stays OPUS; no model switch.
- Cleanup `REVIEW_REQUIRED` (protected immutable history, retained patch-installer containers); never waived. All native/baseline/proof fixtures are disposed with helper receipts.
- Next after ACCEPT: tag/push/release per `docs/RELEASE_0.1.16.md`. Real game original `C:/Users/VNTextDev/Desktop/game/Cucked by My Wife` stays read-only.

## Writer

- Persistent Claude DEV (sole writer); Brain Codex coordinates. No owned processes running.
