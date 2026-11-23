# Release 0.1.29 — merged fix: OS-level extract lock, Ren'Py native block audit, anonymous structure report

Owner 2026-11-23 asked in the DEV session for the merged 0.1.29 and its release. Task `release-0.1.29`, exact `RELEASE_RUN/candidate-0.1.29`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB; user data and evidence are preserved. The public 0.1.28 and 0.1.7 baselines are downloaded with the Owner's explicit permission in the DEV session.

## Scope
- The extract output lock is the operating system's byte-range lock on an open lock file: released by the system when its process ends, never decided by a pid. Legacy `{"pid"}` locks, garbage and self-named locks no longer block. A refusal names the holder (PID, program, lock age) without a path. The worker exits with its host process.
- Ren'Py `translate … python:` / `style` blocks are audited technical blocks (COMPLETE); other unsupported block shapes are a visible PARTIAL warning. Neither is a FAILED extract nor an accounting mismatch.
- Bug report schema 2: masked shape of the exact structure an extraction could not handle (`vntext/shape_mask.py`), replayed by `tests/tools/synth_from_report.py`; schema 1 still reads.
- Version/provenance 0.1.28 → 0.1.29 and the scoped ordinary transition `release-0.1.28` → `release-0.1.29`.

## Evidence
Receipts in `TEST_RUN/agent-evidence/release-0.1.29/`.

## Published
Tag `v0.1.29` = `22317d96b066a25db1b1fdc57fba57ae754a307e`. Digests (GitHub = local): Setup `06702d7c8b2c42ec00eee1d5061492cddcb9c57578854889ae9accb2b186cc95`; full update `51fd38e13dbf4eb7902f945eac4446c439ae5183792d10fd5a77faa395c2137a`; from-0.1.28 `5e2ea4e1255deaafb652f847bf24f6ff77cfdf2591a2bd0653984770ce230a74`. Update 0.1.28→0.1.29 with a legacy lock and an old CSV: PASS (7341 files). Smoke via agent-desktop on the updated app: scan, extract over a legacy lock, bug report, refusal while another process holds the lock and success after it is killed: PASS. NOT_PROVEN: full Ren'Py translate/patch/install/remove through the UI (needs the SDK), kill during a running extract, bug-report preview in the app, Unity/archive shapes.
