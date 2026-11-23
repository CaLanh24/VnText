# Release 0.1.29 — merged fix: OS-level extract lock, Ren'Py native block audit, anonymous structure report

Owner 2026-11-23 asked in the DEV session for the merged 0.1.29 and its release. Task `release-0.1.29`, exact `RELEASE_RUN/candidate-0.1.29`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB; user data and evidence are preserved. The public 0.1.28 and 0.1.7 baselines are downloaded with the Owner's explicit permission in the DEV session.

## Scope
- The extract output lock is the operating system's byte-range lock on an open lock file: released by the system when its process ends, never decided by a pid. Legacy `{"pid"}` locks, garbage and self-named locks no longer block. A refusal names the holder (PID, program, lock age) without a path. The worker exits with its host process.
- Ren'Py `translate … python:` / `style` blocks are audited technical blocks (COMPLETE); other unsupported block shapes are a visible PARTIAL warning. Neither is a FAILED extract nor an accounting mismatch.
- Bug report schema 2: masked shape of the exact structure an extraction could not handle (`vntext/shape_mask.py`), replayed by `tests/tools/synth_from_report.py`; schema 1 still reads.
- Version/provenance 0.1.28 → 0.1.29 and the scoped ordinary transition `release-0.1.28` → `release-0.1.29`.

## Evidence
Receipts in `TEST_RUN/agent-evidence/release-0.1.29/`.
