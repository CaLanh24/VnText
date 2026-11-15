# Current checkpoint — polish batch U1–U9 / C1–C6, 2026-11-16

## Authority / writer
Owner requested ONE batch fixing the combined QA report `TEST_RUN/agent-evidence/polish16-combined-review.{html,json}` (baseline `8dc6888`): U1 glossary reading, U2 radio/checkbox theme, U3 numeric validation, U4 CSV tools label, U5/U6 form width + axis, U7 image empty-state actions, U8 release-notes modal, U9 Journal title, C1 primary gradient, C2 log WARN, C3 switch tokens, C4 control borders, C5 disabled primary, C6 Light hover. Colours/sizes are Owner-assigned candidates, not accepted results. No push/release/tag/version change, no real game, no Owner CSV/app data writes, no new download/install.
Writer: the fixed Claude DEV (agent `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26`) is the sole source writer and sole UI owner; Root reviews independently after handoff. A DEV PASS is not QA acceptance.
Git: per-command `git -c user.name=Calanh -c user.email=316325487+CaLanh24@users.noreply.github.com commit`; Git config is never edited.

## Scope and map
Source map and per-finding regressions: docs/USABILITY_2026-11-13.md, section "Polish batch U1–U9 / C1–C6" (focused `--u16-fixture`, wired into `tests/unit/test_wpf_workflow.py`). Frozen: CSV dirty/save/CAS, selection, preview/apply/undo, partial patch/read-back, OCR approval, schema/key/order/placeholders, worker protocol, model.

## Verification and limits
Evidence (ignored): `TEST_RUN/agent-evidence/u16/` (fixture/module logs, receipt) and the live matrix receipts there; the candidate identity is `DEV_RUN/bootstrap-build/build-identity.json`. Read those receipts, not this text. Pressed state and any state the capture tool cannot reach is NOT PROVEN unless the receipt says otherwise. Independent QA of the live app is still required.

## Candidate / retention
Candidate `DEV_RUN/bootstrap-build/Start-DEV.cmd` (Debug, installed .NET/.dev-env; isolated data under that folder). Keep a clean tracked tree after the final commit; later native/handoff state only in ignored receipts. Owner CSV remains read-only (SHA `8e5d0e849a504b3e8354f676037e2c1ee55aaf5d2635cccb1e9a95a73a1bb0ef`).
