# Release 0.1.28 — hotfix: extract output lock no longer stuck on a reused pid

Owner 2026-11-22 asked for a hotfix release after the extract-lock fix. Task `release-0.1.28`, exact `RELEASE_RUN/candidate-0.1.28`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB; user data and evidence are preserved. Downloading the public baselines needs the Owner's explicit permission in the DEV session.

## Scope
- A lock left by a killed worker no longer blocks extraction forever when Windows gives its pid to another process: locks record the owner's creation time (`vntext/process_identity.py`); a live pid keeps the lock only when it matches. Same check for the traceability and translation-cache locks. Real running extractions are still refused, with a Vietnamese message.
- Version/provenance 0.1.27 → 0.1.28 and the scoped ordinary transition `release-0.1.27` → `release-0.1.28` in `tests/tools/cleanup_work_artifacts.py`.

## Evidence
Unit tests in `tests/unit/test_extract_output_refresh.py`, `test_traceability.py`, `test_translation_cache.py`; receipts in `TEST_RUN/agent-evidence/release-0.1.28/`.
