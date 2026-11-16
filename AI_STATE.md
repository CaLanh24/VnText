# Current checkpoint — Settings header badge (qa-header19), 2026-11-17

## Authority / writer
Owner assigned ONE small P2 batch from `TEST_RUN/agent-evidence/qa008-independent-review.md`: the Settings header status badge is clipped at its left corners at outer 1583×1080 / UI120 / English (General, Data). Only `SettingsPageHeader` changes; B1 inputs/selects, R1 buttons, R2 card stretch, badge colours/radius/type/padding/copy, sidebar and all CSV/OCR/Patch guards stay frozen. No release/push/tag/version, no download/install/game/Owner CSV writes. Policy-blocked roots (u16-focused, r17b-focused, `wpf_app/VNText.Studio.App/obj`) are untouched.
Writer: the fixed Claude DEV (agent `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26`) resumed as sole source/UI writer after the Root takeover boundary (HEAD `6825199` over built baseline `008cd10`). DEV PASS is not independent QA.
Git: per-command `git -c user.name=Calanh -c user.email=316325487+CaLanh24@users.noreply.github.com commit`; Git config is never edited.

## Scope and map
docs/USABILITY_2026-11-13.md section "Settings header badge (qa-header19)"; regression `--h19-fixture`. Old candidate preserved at `DEV_RUN/candidate-008cd10/` (exe/dll/config/identity/launcher, shares isolated DEV data) for before/after comparison.

## Verification and limits
Evidence (ignored): `TEST_RUN/agent-evidence/qa-header19-*` and `DEV_RUN/bootstrap-build/build-identity.json`; read those receipts, not this text. Pressed/animation NOT PROVEN. Independent QA must re-open the built app.

## Result
Fix `ad3d7c3` (SettingsHeaderPanel). New candidate source `ad3d7c3b463be18da6294c5e16d7a8d47354e8b3` EXE `b7e9ad48250979c56de2bc0e317643df400158aac7db8ba6f1245208ea8166e0` DLL `e3d0778d51510848d009a2d6a2d7b8ef8b745eb1c0ccae9543ffd62b2b9ce488`; before 12/72 native cells clipped (EN/UI120 small+restore), after 0/72. Receipt `TEST_RUN/agent-evidence/qa-header19-final-receipt.json`. This AI_STATE-only commit does not rebuild the candidate. DEV native PASS is not independent QA.

## Candidate / retention
Candidate `DEV_RUN/bootstrap-build/Start-DEV.cmd` (Debug; isolated data under that folder). Owner CSV remains read-only (SHA `8e5d0e849a504b3e8354f676037e2c1ee55aaf5d2635cccb1e9a95a73a1bb0ef`).
