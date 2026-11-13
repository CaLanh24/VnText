# Current checkpoint — usability DEV batch, 2026-11-14, NOT COMPLETE

## Authority / coordination
Owner wants all reported CSV/Images/Patch usability fixes, repeated app checks, CSV quality inspection and patch read-back. NO game run/test; no Owner CSV/game/save writes; no release/push/tag/version change. All artifacts in C:/v. Owner approved temporary2.5GiB for this batch (call_5fb9fd2206dc4f9c8b1eeeaebfcded09), but DEV candidate fits default1GiB and the grant has NOT been activated/registered or consumed.
Fixed Claude DEV72329c3d-5883-4cc8-8d14-60c73886ebd3, session76922e45-71b2-47a9-be97-cf18b927ae26 is sole source writer, quota recovered. Root's temporary quota takeover ended. Last handoff turn c47bf42d-71bd-4c11-bf21-267c8494e441; agent idle, last read cursor1787, followup waiter returned1790. No owned child running. Do not create writer/session/model or replay history.

## Source / candidate
HEAD723f9293d9ef414d3d2eab12eef768e0acf7797d plus intentional dirty batch; nothing pushed or committed. Git user.name/email absent; Owner identity question pending. Do not invent author, edit git config, reset/stash/drop changes or bypass source guard.
Candidate C:/v/DEV_RUN/bootstrap-build/VNText.Studio.App.exe, Debug using installed .NET and .dev-env worker (NOT portable/packaged). EXE SHA256 a36ac0b5e799ff2fb8194b3dfa40dfdf9f274d1245140456f9875957a7fd8f51; DLL e936b4315dff8311d314110267259c2dbd4d37eabb168fdd621e629496e68e82. Build-time tracked diff319dc1aa9f8b5e1b4b4624613b2fdc83bafb6c1b03402fcc786971b07d66d730; per-file/untracked hashes in TEST_RUN/agent-evidence/usability-20261114-candidate-source-identity.json. This checkpoint/report reconciliation is docs-only after build; no product code changed after handoff.

## Implemented
- Automatic technical/version/engine-metadata filtering and proved human screen text; persisted user exclusions. Checked CSV rows translate with existing OPUS and save same CSV; delete protected by source hash. Unselected manual multiline drafts preserved.
- Manual translation status/count updates while preserving real structural diagnostics; compact checkbox toolbar, finite CSV table viewport at1043x720/UI120, no horizontal overflow, readable placeholder label.
- First-class Images sidebar page and cached results; OCR-only extract, cached image translation without rescan; no redundant modal entry on Translate.
- Per-page durable notices; image partial/failure does not fail text completion or appear on Extract. Selected-row job completion separated from measured package-wide counts.
- One visible Patch action with explicit valid-subset policy; per-row identity/hash/schema/placeholder/locator/writeback guards remain. Selected translate/Delete invalidate old patch artifact/presentation, with keepCsvValidation preserving valid picked CSV and retry after cancel. Save still revalidates.
- Resource readiness hides redundant download when ready, repairs only missing resources. VI/EN checked-row text updates on language change. No model change.

## Gates / evidence
- WPF21:37/37 PASS, including app/image/scroll, CSV layout + real-CSV repro, update transition, region and English fixtures. Regression SelectedTranslate_KeepsTheCurrentCsvValidButMarksTheOldPatchBehind added; cancel-picked-CSV regression fixed. TEST_RUN/agent-evidence/usability-20261114-wpf21.log.
- Public Python groups PASS:CSV34, MT91, Patch37, maintenance44. Related97 PASS with2 explicit native OCR skips; includes real-OPUS owner-flow, extraction/compiled/UI/dynamic, operation protocol, images/exclusions/safe subset. Text integrity31 PASS retained; no unnecessary updater/release rerun.
- Build and smoke exit0; usability-20261114-dev-candidate-build.json / dev-smoke.json. Smoke is NOT launcher/native acceptance.
- Fresh source fixture CSV:9 nonempty human/intentional-keep rows,9 per-key patch readbacks; version chrome/technical syntax excluded. Evidence in TEST_RUN/agent-evidence/usability-csv-quality. Rough model wording and name-like Prologue retention are not perfect semantics claims.
- Owner CSV read-only319rows/311nonempty/8legacyempty; final SHA8e5d0e849a504b3e8354f676037e2c1ee55aaf5d2635cccb1e9a95a73a1bb0ef unchanged. Other-machine1464-row CSV absent. No whole-game claim.

## ROOT verification / actual blocker
Root reviewed keepCsvValidation delta and candidate receipts. Agent-desktop status/list-windows worked (desktop appeared interactive, only ChatGPT listed); no app interaction or capture/input session started. Root ran the ACTUAL delivered Start-DEV.ps1: exit1, 'BLOCKED: DEV source tree is dirty; commit the intended source before launching.' Thus the candidate launcher is NOT ready for Owner testing; do not bypass by launching EXE with hand-built environment. Native/package acceptance remains NOT_PROVEN. Identity RESOLVED: the established repository identity (author = committer of all prior commits) is used per-command (`git -c user.name/-c user.email`, config untouched); the intended tree is committed by DEV, the candidate identity is rebuilt at that clean commit and the real Start-DEV.ps1 smoke is run by DEV (ignored receipts `TEST_RUN/agent-evidence/usability-20261114-final-*.json`; no tracked file is edited for them, so the tree stays clean). No new release authority.

## Cleanup / next step
DEV disposed127 owned TEST_RUN/tmp roots,0refused;852 own stale MISSING records reconciled. Receipt usability-20261114-scratch-cleanup.json. Project measured695199317B/default1073741824B; candidate retained, 29MB TEST_RUN/updater-loop-check retained because guard/consumer; small DEV_RUN/scratch retained. No Owner data/game/app touched. No app/worker child or pending input/capture from Root.
Next: Root native checks (candidate/launcher/fixture evidence in the ignored final receipts) of CSV select/translate/delete/dirty/conflict, cancel+retry, Patch stale/current state, Images/resources and VI/EN/small UI. Preserve accepted behavior, no game run or publication. See docs/USABILITY_2026-11-13.md.

## DEV final boundary (2026-11-14)
Regression fixed: patch invalidation after a selected translate/Delete separates OLD patch/artifact claims from the validity of the CURRENT picked CSV (`InvalidatePatchSourceState(keepCsvValidation)`); cancelled translate keeps CSV/retry; successful translate/delete marks the old artifact behind and not done (`SelectedTranslate_KeepsTheCurrentCsvValidButMarksTheOldPatchBehind`). Gates: `test_wpf_workflow` 37/37, public Python 34/91/37/44, 97 related Python tests OK (2 explicit native OCR skips). The 2.5 GiB temporary budget was not needed; none registered. Native/live acceptance is NOT_PROVEN (Root).
