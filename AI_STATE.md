# Current checkpoint — 2026-11-09 local workflow candidate (native full PASS)

## Authority and writer
Owner batch (one editable CSV, source/translation search, results-first image workspace, completion dialog + sound, one branded patch EXE, native-reviewed Setup) is local only: no push, release, version or tag. Public 0.1.17 is immutable. Game, saves and Owner AppData untouched. DEV is the sole writer (same agent/session); Root is sole UI owner. No owned process, UI, worker or build is running.

## Current candidates (retain until Owner QA)
- Setup: `C:/vnrg/candidate-terms-fix/VNTextStudio-DEV-0.1.17-1845cfe-Setup.exe`, sha256 `24399a11a7c9613fed6205f555de8ee240e8dee5a622189d15bb786c3a89921d`, 289,011,712 B. Code `949d1fc` (+docs). 7,198 payload members verified.
- DEV app: `C:/v/DEV_RUN/final-workflow-0.1.17/Start-DEV.cmd`, app sha256 `78391c5a7a84d92e04d4f7078e2bc795259cb157071b6762e55787025458ea8b`.
- Patch-installer stub `release/patch_installer_publish/VNTextPatchInstaller.exe` restored byte-exact (sha256 `cbd6e72d…8be24`).

## Verdicts (separate)
- Gates: focused canonical gate 22 tests PASS at `949d1fc`; cleanup tool module 162 OK after the budget/reactivation tooling; earlier hA193/hB109 reused for unchanged Python; wrapper `REVIEW_REQUIRED` is protected epoch history only.
- Native (Root): terms footer VI/EN, Intel agreement, isolated install, Cancel/Skip truthfully NOT ready, installed app launch, uninstall refusal with the app active and success after close — and the FULL resource path: real 155.5 MB Ren'Py SDK download -> verify/extract -> Setup Ready; Finish launched the app; physical Check Resources showed model/renpy/ocr all Ready; uninstall removed all 11,680 items including the downloaded SDK and self-removed. Test root empty, UI closed, Owner Desktop/Start Menu equal. Receipts: `root-native-full-setup-20261109.json`, `native-full-cleanup-linked-receipt.json`, telemetry `native-full-telemetry.jsonl` (sampled peak 7,168,785,045 B < abort 7,197,425,664; 1 s samples, not continuous).
- Limits kept: forced-offline native branch (proxy launch auto-policy rejected, not retried or bypassed), all DPI/themes, audible playback, large games. No release acceptance.

## Budget and cleanup
Owner granted a TEMPORARY 6.75 GiB for the full-resource run; recorded in the tooling (limit 6,912 MiB, epoch `epoch-20261109-017-budget675b`); guard 48 MiB and shared 11 GiB unchanged. Combined after cleanup 6,134,550,799 B (below the old 6.25 GiB cap too); the tooling record itself has not been returned to 6.25 GiB (needs a tooling change plus epoch). Consumed with receipts: old Setups, baseline mirror, legacy `DEV_RUN` output (archived), stub (restored), native test containers (normal registry disposal, 0 refused). `runner-reports` and 113 unknown `TEST_RUN/tmp` dirs remain REVIEW_REQUIRED/unforced.

## Next
Owner QA on the exact Setup/app. History of earlier rounds: `docs/WORKFLOW_CANDIDATE_2026-11-09.md`.
