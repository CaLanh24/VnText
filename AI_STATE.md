# Current checkpoint — 2026-10-27

## Release 0.1.13: IN PROGRESS, publication HOLD

- Owner authorized finishing bounded remediation, required gates, Setup/updater and publication after Brain ACCEPT, without repeated approval. Real-game E2E is deferred NOT TESTED; OPUS-MT limits accepted, not semantic PASS. Baseline required: 0.1.12 -> 0.1.13; pre-0.1.12 out of acceptance; >=0.1.13 one action to latest.
- Canonical acceptance: `docs/RELEASE_0.1.13.md` (22 native items); invariants/coordination: `CONTRACTS.md`; gate selection: `TEST_MATRIX.md`. This checkpoint replaces stale historical state; detailed history remains in task ledgers.
- Current Git: main, checkpoint commit `03735e7` (docs only: AGENTS/AI_STATE after candidate `5150fd9`). Candidate source stays `5150fd97d159c15456eac704f2aff337cbfd5f22`; later docs do not require rebuild or upgrade evidence to exact HEAD, but see the preflight barrier below. AI_STATE edits after `03735e7` stay uncommitted until Root review or new authority (no extra epoch hop).
- Brain successor is ACTIVE (same project, clean history); the old Brain is retired. One coordinator and one source writer. Persistent Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26`; last observed DEV cursor 599. Read latest before giving work.
- Context rule: AGENTS.md section "Giới hạn ngữ cảnh và bàn giao Coordinator". Owner-authorized sequential handoff supersedes old session lock. Claude remains sole writer; Codex fallback only on proven quota exhaustion, returned on recovery.

## Exact candidate / verified results

- Local Setup `C:\v\RELEASE_RUN\candidate-0.1.13\p13n\release\Setup.exe`, SHA256 `08b504b48e1d46fad9118b5511b761f7f2bf5e76f92adc2c7c2d2ac5c02c3d29`, 222478336 bytes. Payload 7193 files / 514805427 bytes.
- Installed via native Setup into registered `C:\v\RELEASE_RUN\candidate-0.1.13\s13n`; Intel terms accepted under Owner grant; Setup success dialog observed. Installed exe hash independently checked `02acaf3b9107cb672f97cc15ff3fd6877fbd733ee0e045be053b37c471182412`; RELEASE.json source matches 5150fd9.
- Source gates on 5150fd9: patch/worker 79, affected patch 107, WPF 22 tests PASS/0 skip; DEV build and smoke PASS. Wrapper historical TEST_RUN disposition REVIEW_REQUIRED remains separate from child exit 0.
- p13n publisher retry exit 0 / cleanup PASS (attempt 1 FAILED inventory cap retained); release-verify and two worker smokes exit 0; updater named-0.1.12, health rollback, tampered-package cases PASS. Seven other p13m cases not repeated: updater code/scripts unchanged; not p13n exact-candidate proof.
- Receipts under `DEV_RUN/gatec/`: `candidate-receipt-p13n.json`, `candidate-verify-p13n.json`, `updater-matrix-p13n-summary.json`, `native-handoff-s13n.json`. Last handoff's "s13n empty" is superseded by Setup observation above.

## Preflight barrier (native #13 on s13n) — Owner rebaseline GRANTED, application follows the authority commit

- Root's preflight `DEV_RUN/gatec/native13-s13n-preflight.json` (kept, not overwritten) ran under profile `default` (limit 1 GiB, non-exempt None). The recorded error is `inventory.errors[0].error = release_task_budget_scope_or_source_mismatch` (path `TEST_RUN/artifacts_manifest.json`); it matches `_release_task_budget_profile` in `tests/tools/cleanup_work_artifacts.py`: the release-0.1.13 profile needs HEAD == epoch source and the ordinary chain was 8/8 at `epoch-20261027T050000Z-5150fd9`.
- Owner answered question `call_567ecb4e733c463c8cd2b1fe2bb51ef6` with the exact reply 'Cho phép một lần rebaseline': ONE additional no-delete 0.1.13 epoch metadata rebaseline, history preserved, no validator relaxed. Recorded in `CONTRACTS.md` (fifth authority) and as `RELEASE_TASK_013_EPOCH_REBASELINE_APPROVAL_5`; single use. Candidate p13n stays source `5150fd9`; publication HOLD.
- s13n state (Root receipt `DEV_RUN/gatec/native13-s13n-idle-close.json`, 2026-10-27T08:07Z): closed through the native X, remaining_count 0, CU kernel reset OK, `patch_started` false. Last Root selection: game `fx9\patch-cancel-8k\game`, CSV `package\translation.csv` (UI valid 8000/8000), output `out2` empty. NO Patch started.
- Sequence: commit the authority at clean main -> plan (read-only) -> apply exactly one rebaseline against the exact active epoch and live manifest hash -> focused/affected gates -> read-only native13 preflight (new receipt `native13-s13n-preflight-after-rebaseline.json`; positive release-0.1.13 profile, reserve >= 512 MiB, input hashes unchanged, `out2` empty). Results of the application live in `DEV_RUN/gatec/rebaseline_fifth_*.json`; a docs commit after the rebaseline would break the profile again, so this file stays staged/uncommitted afterwards. Native launch, Patch and publication are NOT part of this step; Root runs native #13/#12 afterwards.

## Native acceptance still open

- p13m proved bounded translate/cancel/retry, missing-model readiness, version/notes, generated text patch 120/120 readback; receipts `native-evidence-p13m*.json`. They are old executable evidence, not automatically p13n acceptance.
- p13m #13 found cancellation delayed through verify, complete-looking output, wrong translate wording. Fixed in af88d24 then corrected in 5150fd9: poll cancel in readback, keep output without deleting/moving it, explicit warning/new-empty-output instruction, honest too-late success. Native retest on p13n NOT DONE.
- Next finite phase: native #13 on s13n with `fx9\patch-cancel-8k\game`, CSV `package\translation.csv`, fresh `out2`; confirm one cancelled terminal, honest output warning, game unchanged, no automatic output cleanup; retry in fresh output and verify #12 readback/installer. Old `out` is p13m evidence and must remain.
- HISTORICAL, superseded by the selected-input and close receipt above: interrupted before selecting game on s13n: folder picker was at `fx9\patch-cancel-8k`, no patch started. On recovery process inventory showed no VNText/python processes; task node_repl kernel reset successfully, no pending input/capture. App/worker absent; shared tool servers not killed.
- Remaining checklist gaps beyond #12/#13: #4 SDK recovery partial only; #5 download offline/cancel, #6 OCR, #10 complete before/after process evidence, #11 ordinary failure, #14 editor search/preview/apply/undo/save/reload, #15 dirty/external conflicts, #17-19 sweep/DPI/keyboard, #20-21 offline updater/cache, #22 uninstall. Review receipts per item; do not label partial as PASS. #7-9/#16 have p13m evidence; evaluate changed-source impact explicitly.
- Editor automation previously had null accessibility/focus: do not type into unconfirmed focus. Use computer-use skill; reset task kernel on backend/wait/interrupt/terminal.
- Real updater offer/download/restart needs GitHub, client API hardcoded; headless matrix not UI E2E. Publication remains HOLD until bounded acceptance; no public 0.1.13 mutation performed by this Brain. Public latest last checked 0.1.12, recheck before publication.

## Cleanup / next coordinator

- Last DEV budget receipt: non-exempt 6985677846 / 9126805504 bytes (~2.14 GB free), ~128.6k entries; verify before new allocation. Old registered fx7/p13l/fx4/s13e/s13l disposed with receipts; UNKNOWN historical roots untouched. TEST_RUN terminal_root REVIEW_REQUIRED persists.
- Epoch active at candidate source `epoch-20261027T050000Z-5150fd9`, ordinary chain 8/8; docs-only commits do not invalidate candidate. Before any new source gate inspect epoch rules; never bypass validator or assume broad rights manufacture exact rebaseline approval.
- Full one-page operational handoff: `DEV_RUN/gatec/brain-handoff-20261027.md`. First successor action: confirm Git/DEV/receipt state, then resume finite native #13/#12 phase. Do not rerun passed unrelated gates or open new scope.
