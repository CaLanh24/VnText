# Current checkpoint — 2026-10-27 (native 10/11 and SDK recovery boundary)

## Successor update (supersedes stale process and next-action statements below)

- #10 PASS bounded on s13n: CT2 cancel-and-exit; app/worker present before and during wait, cancellation terminal after 13.4 s, both absent afterward, CSV hash unchanged. Exit code and in-flight inference boundary not captured. `DEV_RUN/gatec/native10-s13n-result.json` and its before/waiting/after receipts.
- #11 PASS bounded ordinary Patch failure: nonempty output reported cause and action; journal says `Lỗi`, not cancellation; four sampled hashes unchanged. Message is English. Invalid CSV without manifest was blocked before worker. `DEV_RUN/gatec/native11-s13n-result.json` and screenshots.
- #4 PARTIAL: recovery choices and picker/cancel observed on `fx2\renpy-nosdk` root (not its `game` child). UI says no alternative parser but loose-source missing-SDK branch calls `extract_loose_source`: investigate semantics and contract before acceptance. #5 NOT_PROVEN: process-only proxy launch was rejected by automatic review before execution; no detailed reason given and no workaround attempted. `DEV_RUN/gatec/native45-s13n-partial.json` and `native45_scope_prep.json`.
- Remaining mandatory native gates: #4/#5, #6, #13 read-back cancellation, #14/#15, #17–#22. Publication HOLD. CU kernel reset, no pending input/capture, app and worker absent by CIM at 12:09 UTC.
- Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26`, cursor 661, idle after API 429 `usage_limit_reached`, reset reported 22:00 Asia/Tokyo. Codex may temporarily write while quota exhausted; return to the same DEV after recovery. Keep this Coordinator and DEV; context pressure and phase count do not trigger a new session. Do not run a second coordinator or writer.
- Before this checkpoint: clean HEAD `a61fac618f1e6e534b3697fb615cab00ec4f4b8f`, epoch `epoch-20261027T150000Z-a61fac6`, ordinary hop 3/8. A docs commit invalidates the budget profile until one ordinary no-delete exact-CAS epoch transition; fifth rebaseline grant is consumed. Verify the resulting epoch and clean Git before gates. Candidate source and hashes below remain unchanged.
- `fx2` and `fx10` are registered RETAINED for SDK acceptance, `fx10` outputs empty; review retention when #4/#5 close. Latest profile receipt shows 6,480,308,015 B non-exempt and 2,646,497,489 B reserve; reverify live. Next: verify Git/epoch/live DEV and receipts, investigate #4 discrepancy, then continue remaining acceptance without bypassing the automatic review rejection.

## Release 0.1.13: IN PROGRESS, publication HOLD

- Authority: Owner authorized finishing bounded remediation, required gates, Setup/updater and publication after Brain ACCEPT, without repeated approval. Real-game E2E is deferred NOT TESTED; OPUS-MT limits accepted (not a semantic PASS). Baseline required 0.1.12 -> 0.1.13; pre-0.1.12 and Setup-origin 0.1.10 are out of acceptance; >=0.1.13 one action to latest. The cleanup policy is persisted in `AGENTS.md` "Cleanup và retention" and `CONTRACTS.md` §10a. The Owner context/history correction is in force and persisted in `AGENTS.md`; keep this Coordinator unless observed recovery failure or Owner request.
- Acceptance owner: `docs/RELEASE_0.1.13.md` ("Current summary" on top, 22 native items below); invariants `CONTRACTS.md`; gates `TEST_MATRIX.md`. Live operational checkpoint (fresher than this file): ignored `DEV_RUN/gatec/cleanup_phase_root_checkpoint.json`; treat any loaded checkpoint as advisory until checked against Git and live receipts.

## Candidate and verified results

- Setup `C:\v\RELEASE_RUN\candidate-0.1.13\p13n\release\Setup.exe`, SHA256 `08b504b48e1d46fad9118b5511b761f7f2bf5e76f92adc2c7c2d2ac5c02c3d29`; payload 7193 files / 514805427 bytes. Installed natively into `...\s13n`; exe `02acaf3b9107cb672f97cc15ff3fd6877fbd733ee0e045be053b37c471182412`, RELEASE.json source 5150fd9.
- Source gates on 5150fd9: patch/worker 79, affected patch 107, WPF 22 tests PASS/0 skip; DEV build and smoke PASS; publisher retry exit 0 (attempt 1 FAILED on the inventory cap, kept); release-verify + two smokes exit 0; updater named-0.1.12, health rollback, tampered cases PASS (7 other p13m cases not repeated: updater code unchanged). Wrapper `REVIEW_REQUIRED` for historical TEST_RUN is separate from child exit 0. Receipts under `DEV_RUN/gatec/`: `candidate-receipt-p13n.json`, `candidate-verify-p13n.json`, `updater-matrix-p13n-summary.json`, `native-handoff-s13n.json`.

## Native acceptance on p13n (Root, 2026-10-27)

- #12 PASS bounded generic text (preflight 8000/8000; retry into `fx9\patch-cancel-8k\out3`; verification PASS 8000; import report 8000/8000, no skip; installer present; game unchanged). Installer apply/restore not run; no Unity/Ren'Py/real-game claim.
- #13: cancel ack 23 ms, one terminal after 47.4 s, honest output-kept warning, `out2` empty, game unchanged, retry in a new empty output works; cancellation DURING READ-BACK NOT_PROVEN (cancel hit the initial stage) - remediation stays PARTIAL for that point; residual latency about 47 s. Receipts `native12-13-s13n-root.json`, `native13-s13n-cancel1.json`, `native12-s13n-retry.png`. `fx9\...\out` (p13m cancel output) and `out3` stay as evidence until Brain closes the finding; `out3` is registered.
- p13m evidence for #3, #7-#9, #16 is reused only as bounded evidence (patch-only source diff), not as p13n exact-native claims.

## Cleanup and budget

- Cleanup PARTIAL: about 2.33 GB removed; 29 historical TEST_RUN roots and old DEV directories retain unresolved descendant/consumer questions with DEV review after #10/#11. Not a release gate; see `DEV_RUN/gatec/cleanup_phase_result.json`. Keep candidate, registered fixtures, baselines, shared SDK/model and required receipts until their named consumers close; no cleanup loop.

## Next action

- Verify epoch/profile and live DEV; investigate #4 discrepancy, then continue acceptance in this session.
