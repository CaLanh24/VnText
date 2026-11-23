# Release 0.1.31 — bug report always reachable, clearer patch conflict, handle release, test fixes

Owner (DEV session 2026-11-24) asked for the follow-up and confirmed its release. Task `release-0.1.31`, exact `RELEASE_RUN/candidate-0.1.31`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB; user data and evidence are preserved. The public 0.1.30 and 0.1.7 baselines are downloaded with the Owner's explicit permission in the DEV session.

## Scope
- "Tạo gói báo lỗi" works while the worker is busy (image scan after an extract, a task being cancelled): the report is built in its own short-lived process (`vntext/bug_report_cli.py`, `Services/BugReportProcess.cs`).
- Patching a game that already carries a VNText patch with a different translation says how to continue (remove the old patch first) instead of a bare "mapping conflict".
- Game files opened by the analysis are released (garbage collection) before an extraction reports its end: fixes the order-dependent `unity_data_dir` handle error and helps removing a patch right after an extract.
- WPF fixture and product fixes found while diagnosing it: a race when the Ren'Py detection is cancelled twice (ObjectDisposedException), patch-page texts not refreshed on language change, and a stale cancel-watchdog expectation. The whole WPF harness (37 tests) passes.
- Version/provenance 0.1.30 → 0.1.31 and the scoped ordinary transition `release-0.1.30` → `release-0.1.31`.

## Evidence
Receipts in `TEST_RUN/agent-evidence/release-0.1.31/`.

## Published
Tag `v0.1.31` = `fcba562e523e0fa66814b94933afcb705ae6cdc5`. Setup sha256 `257b45e869ac7be4495840786f9bf1d7a8c4318e475c796811bda1db07fc9d7b` (GitHub = local, 5/5 assets). Update 0.1.30→0.1.31: 7344 files verified. Smoke through the UI on the updated app (agent-desktop, real Ren'Py SDK): bug report built while a 60,000-line extraction runs (it finishes COMPLETE), extract → translate → patch → install, new message when re-patching over an installed patch. NOT_PROVEN: system/DEV_PROBES pickers, Dịch ảnh through the UI.
