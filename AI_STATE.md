# Current checkpoint — usability DEV batch, 2026-11-14, NOT COMPLETE

## Authority and sole writer
Owner wants all reported CSV/Images/Patch usability fixes, app checks, CSV quality inspection and patch read-back. NO game run/test, Owner CSV/game/save writes, release/push/tag/version change. All artifacts in C:/v. Owner approved temporary2.5GiB (call_5fb9fd2206dc4f9c8b1eeeaebfcded09), but candidate fits default1GiB; grant is not registered/activated/consumed.
Fixed DEV72329c3d-5883-4cc8-8d14-60c73886ebd3/session76922e45-71b2-47a9-be97-cf18b927ae26 is idle/failed, last turn49ab5f5f-40a1-4805-8909-3f0c49420187, last read cursor1791 (waiter1795). Reported quota resets05:40 Asia/Tokyo. Root temporarily owns source under AGENTS quota exception; return to same DEV after recovery at safe boundary. No parallel writer or owned child beyond the focused Root gate described below.

## Source and metadata
Baseline usable clean commit f0265eae7e81c554bbf35d084243a98068c1d376. DEV committed and rebuilt before hitting quota; its final quota-only answer omitted that work. Root confirmed Git/receipts. Git global/local name/email are absent, but the prior five commits consistently use Calanh <316325487+CaLanh24@users.noreply.github.com>. Reuse that established identity per-command git -c only; no config-file edit or new/private email needed. Root's earlier identity question was unnecessary and corrected. No reset/stash/drop or guard bypass.
Root has a small native-discovered correction pending after f0265ea: command-state notifications in MainViewModel.CsvSelection.cs and a behavior test in Program.CsvEditor.cs. Docs checkpoint included in that correction. Exact final source is git HEAD and latest candidate build-identity receipt; verify they match before launch. Do not use old dirty-build identities from historical receipts.

## Implemented batch
- Automatic RenPy technical/version/engine-metadata filtering and verified human screen text; persisted user exclusions.
- Checked CSV rows translate with existing offline OPUS and save same CSV; conflict-protected delete. Manual multiline/unselected rows preserved; status/count updates retain structural diagnostics.
- Compact checkbox toolbar; finite small-window CSV viewport, no horizontal overflow, short readable placeholder status; VI/EN updates.
- First-class Images sidebar/results page; OCR-only extract, cached image translation without rescan, image errors isolated from text and routed to Images.
- Per-page durable notices; selected-row job completion separate from package-wide counts.
- One Patch action with explicit valid-subset policy and unchanged per-row identity/hash/schema/placeholder/locator/writeback guards. Selected translate/Delete invalidate old patch claims while keeping picked CSV valid for retry; Save revalidates.
- Real resource readiness hides redundant download and repairs only missing resources. No model change.

## Gates and quality evidence
- usability-20261114-wpf21.log:37/37 PASS, includes source/build, app/image/scroll, CSV layout/real-CSV repro, update transition, region and English fixtures. Cancel/readiness and selected-translate old-artifact regression pass. Not packaged/native acceptance.
- Public Python groups PASS:CSV34,MT91,Patch37,maintenance44. Related97 PASS with2 explicit native OCR skips. Text-integrity31 PASS retained. No reason to rerun unchanged Python/model/content gates for the new notification-only correction.
- Fresh source fixture -> actual OPUS -> CSV -> per-key patch readback:9 nonempty human/intentional-keep rows,9 readbacks; technical/version chrome excluded. Small quality evidence TEST_RUN/agent-evidence/usability-csv-quality. Rough wording/name-like Prologue retention does not prove perfect semantics or every sentence Vietnamese.
- Owner CSV read-only319rows/311nonempty/8legacyempty; final SHA8e5d0e849a504b3e8354f676037e2c1ee55aaf5d2635cccb1e9a95a73a1bb0ef unchanged. Other-machine1464-row CSV absent. No whole-game claim.

## Candidate and native status
C:/v/DEV_RUN/bootstrap-build, Start-DEV.cmd/ps1, Debug depending on installed .NET/.dev-env worker (not portable). f0265ea build EXE bf6d28c87b5dda0ead910487ac37112d9a727ef8600518524f0714cdd01bc5c5; DLL bdef98089720dd7ce375beab7ad3e2440c1590e62f14380cc654f4c52d3317e4. Final-candidate.json/final-launcher.json receipts confirm clean identity and actual launcher smoke exit0. It must be rebuilt after pending native correction before final handoff.
Root launched actual Start-DEV.ps1, used agent-desktop, opened ONLY synthetic TEST_RUN/native-fixture-usability/package/translation.csv (8rows,2manual+6empty), checked warm-bed row, ran OPUS via confirmation, observed completion dialog/save. No real game. Screenshot usability-native-csv.png. Candidate app closed after completion; no pending input/capture/kernel.
Native finding: select-all remained disabled after CSV load because selection commands lacked CanExecuteChanged notifications. Checking a row enabled Translate/Delete but not select-all. Correction refreshes recount/commands on Busy/loading/saving/path/document changes, including select-all; test checks event delivery after load and reset on document replacement. Focused WPF gate37/37 PASS at TEST_RUN/agent-evidence/usability-20261114-selection-native-regression.log; owned run terminal exit0.
Remaining native checklist on corrected candidate: select-all/clear/translate/delete confirmation and persistence, cancel/retry, manual status+Patch stale/current state, Images/resources, VI/EN and small UI. Prior fixtures do not prove these on new binary. No installer/updater/release/gameplay acceptance.

## Cleanup and next action
DEV disposed127 owned scratch roots,0refused;852 own stale MISSING records reconciled (usability-20261114-scratch-cleanup.json). Measured project695199317B/default1073741824B. Candidate retained; TEST_RUN/updater-loop-check29MB retained for consumer/guard; synthetic native fixture~1.1MB registered retained for Root and disposable after QA. Owner app/data untouched.
Finish focused gate -> commit intended correction using established per-command identity -> rebuild clean candidate -> actual launcher smoke -> Root native. Keep tracked tree clean after final commit; subsequent native state goes in ignored evidence receipt and this checkpoint's linked receipt, not an uncommitted docs mutation that blocks the launcher. See docs/USABILITY_2026-11-13.md for scope/history.

