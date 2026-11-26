# Release 0.1.34 — Ren'Py native accounting that always adds up

Owner report (2026-11-26, v0.1.33, relayed by Brain): a Ren'Py extraction ended with "Ren'Py native accounting mismatch: native=1564, package=1525". Released under the Owner's standing permission (DEV session 2026-11-25: release VNText patches when the mandatory gate passes; public baselines downloaded with hash checks). Task `release-0.1.34`, exact `RELEASE_RUN/candidate-0.1.34`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB.

## Root cause (reproduced on a fake layout)
Re-extracting into an output whose `user_exclusions.json` records rows removed earlier — by "Xóa dòng đã chọn" in Sửa CSV, or by the machine-syntax cleanup that runs before every translation — drops those rows from the new package (by design, since 0.1.20). They were counted as native units but in no bucket, so the check reported a mismatch of exactly the number of recorded removals and the run was marked as an extraction error. Removing 2 rows and re-extracting reproduces `native=323, package=321`. Every native unit becomes exactly one entry and `write_package` drops none, so the recorded removals were the only path to a gap. The Owner's 39 has not been confirmed against their bug report.

## Scope
- Rows removed earlier are their own accounting bucket (`user_excluded`), recorded in `extract_status.json`.
- Every native unit is reconciled by identity (`vntext/native_accounting.py`): package row, engine-common exclusion or user exclusion. `native_accounting.json` lists the buckets and any unit counted in none — kind, hashed file label, line; no file names, text or identifiers.
- An unexplained gap is never an extraction error. The run is PARTIAL with the warning `NATIVE_ACCOUNTING_GAP` and the "Tạo gói báo lỗi" hint. Every row that was found stays in the CSV. The validator and the patch guards are unchanged: a gap still blocks the scoped patch.
- The bug report carries the accounting: buckets, counts by kind, and up to 50 masked unaccounted units. File labels are renumbered per report (`u1.rpy`…), so not even the hash leaves the machine.
- Found while testing: `user_exclusions.json` is carried into the staging folder and republished, but it was compared by modification time. Removing rows and re-extracting immediately could be refused as "Output changed externally". It is now compared by content, like the other republished files, so a real change during the run is still refused.
- Version/provenance 0.1.33 → 0.1.34 and the scoped ordinary transition `release-0.1.33` → `release-0.1.34`.

## Evidence
Receipts in `TEST_RUN/agent-evidence/release-0.1.34/`. `tests/unit/test_native_accounting.py`:
- reconciliation with masking and a sample cap;
- with the real Ren'Py SDK: re-extraction after removals is COMPLETE with every bucket adding up;
- an injected unknown loss gives PARTIAL, severity warning and 0 errors, with a masked unit in `native_accounting.json` and in the bug report;
- property test: on 6 random layouts (dialogue, narration, menus, nvl, `_()` strings, a string duplicated across files, screen text, engine-common words, several files and folders, random removals) the buckets always equal `native_units`.

## Published
Tag `v0.1.34` = `d4c0c0a366bdb39fcd6dd97b51e5d6e2c1b5c629`. Setup sha256 `0ca3434dd688dbe24e98816d24489da33346a0f9f866e046187d0d6e1f79ba23` (GitHub = local, 5/5 assets). Update 0.1.33→0.1.34: 7338 files verified. Gate: 381 tests; 5 patch/installer tests failed on the first run only because the 2026-11-25 cleanup had removed the test copy of the patch installer, and passed after rebuilding it from the current source. Smoke through the UI on the updated app (agent-desktop, real Ren'Py SDK): extract → translate → 2 rows removed → re-extract COMPLETE (320 = 320, user_excluded 2) → patch → install → uninstall equal to the original. NOT_PROVEN: the Owner's game bundle (not received yet).
