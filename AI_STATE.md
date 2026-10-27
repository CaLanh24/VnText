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

## Preflight barrier (native #13 on s13n) — CLEARED by the fifth rebaseline

- The earlier preflight `DEV_RUN/gatec/native13-s13n-preflight.json` (kept, FAILED) fell back to profile `default` because HEAD differed from the epoch source after the 8/8 chain (`inventory.errors[0].error = release_task_budget_scope_or_source_mismatch`).
- Owner answered question `call_567ecb4e733c463c8cd2b1fe2bb51ef6` with 'Cho phép một lần rebaseline'; applied ONCE at commit `494a1c9` (epoch `epoch-20261027T120000Z-494a1c9`, plan and apply ok, no deletions; gates f5a 117 tests and f5c 37 tests child PASS, f5b FAIL kept = a misspelled module name). Result receipt `DEV_RUN/gatec/rebaseline_fifth_result.json`; positive preflight `DEV_RUN/gatec/native13-s13n-preflight-after-rebaseline.json`. The fifth grant is consumed.
- Any dirty or staged tree makes `_release_task_budget_profile` fall back to the default profile: after an epoch activation keep Git clean and keep live results only in ignored `DEV_RUN` receipts, never as a staged checkpoint.
- s13n state (Root receipt `DEV_RUN/gatec/native13-s13n-idle-close.json`): closed, CU reset OK, `patch_started` false; selected `fx9\patch-cancel-8k\game`, CSV `package\translation.csv` (valid 8000/8000), output `out2` empty. Native #13/#12 are Root's next step after the cleanup phase; no Patch was started.

## Current objective: bounded cleanup phase (Owner 2026-10-27)

- Policy: `AGENTS.md` "Cleanup và retention" and `CONTRACTS.md` §10a. One bounded pass before the next large allocation/native: routine C:\v artifacts without a consumer, and the expired checkout C:\b (Git clean at detached 6bcfde4, main 5fdf879 and release-source 26d40c8 verified as ancestors in C:\v) after consumer checks and a small provenance receipt; C:\ctest stays as the minimum session cwd until the bridge can move. Preserve p13n/s13n, fx9 (including the old `out` until the #13 finding closes), fx8/#12, baselines with a route consumer, shared SDK/model/cache in use, source and user data.
- Plan, before/after readback, remaining items with consumer and expiry, and the cleanup verdict live in ignored `DEV_RUN/gatec/cleanup_phase_*.json`; the docs commit of this phase used one ordinary no-delete epoch transition (hop 1 of the new chain). No source or docs change until the phase is terminal.

## Native acceptance still open

- p13m proved bounded translate/cancel/retry, missing-model readiness, version/notes, generated text patch 120/120 readback; receipts `native-evidence-p13m*.json`. They are old executable evidence, not automatically p13n acceptance.
- p13m #13 found cancellation delayed through verify, complete-looking output, wrong translate wording. Fixed in af88d24 then corrected in 5150fd9: poll cancel in readback, keep output without deleting/moving it, explicit warning/new-empty-output instruction, honest too-late success. Native retest on p13n NOT DONE.
- Next finite phase: native #13 on s13n with `fx9\patch-cancel-8k\game`, CSV `package\translation.csv`, fresh `out2`; confirm one cancelled terminal, honest output warning, game unchanged, no automatic output cleanup; retry in fresh output and verify #12 readback/installer. Old `out` is p13m evidence and must remain.
- HISTORICAL, superseded by the selected-input and close receipt above: interrupted before selecting game on s13n: folder picker was at `fx9\patch-cancel-8k`, no patch started. On recovery process inventory showed no VNText/python processes; task node_repl kernel reset successfully, no pending input/capture. App/worker absent; shared tool servers not killed.
- Remaining checklist gaps beyond #12/#13: #4 SDK recovery partial only; #5 download offline/cancel, #6 OCR, #10 complete before/after process evidence, #11 ordinary failure, #14 editor search/preview/apply/undo/save/reload, #15 dirty/external conflicts, #17-19 sweep/DPI/keyboard, #20-21 offline updater/cache, #22 uninstall. Review receipts per item; do not label partial as PASS. #7-9/#16 have p13m evidence; evaluate changed-source impact explicitly.
- Editor automation previously had null accessibility/focus: do not type into unconfirmed focus. Use computer-use skill; reset task kernel on backend/wait/interrupt/terminal.
- Real updater offer/download/restart needs GitHub, client API hardcoded; headless matrix not UI E2E. Publication remains HOLD until bounded acceptance; no public 0.1.13 mutation performed by this Brain. Public latest last checked 0.1.12, recheck before publication.

## Cleanup / next coordinator

- Budget (verify before any new allocation): at 494a1c9 non-exempt 7,542,297,296 / 9,126,805,504 bytes (reserve 1,584,508,208), shared `.dev-env` reported separately (exempt, cap 6 GiB). Earlier disposals (fx7/p13l/fx4/s13e/s13l) have receipts; UNKNOWN historical roots are investigated in the cleanup phase above, not kept by default. TEST_RUN terminal_root REVIEW_REQUIRED persists until that investigation is closed.
- Epoch: fifth rebaseline applied at `494a1c9` (`epoch-20261027T120000Z-494a1c9`); the ordinary chain restarts at 0/8 and each docs/source commit needs its own ordinary no-delete hop (exact epoch + full-manifest CAS) before gates or native preflight. Never bypass the validator or assume a broad right manufactures a rebaseline approval.
- Full one-page operational handoff: `DEV_RUN/gatec/brain-handoff-20261027.md`. First successor action: confirm Git/DEV/receipt state, then resume finite native #13/#12 phase. Do not rerun passed unrelated gates or open new scope.
