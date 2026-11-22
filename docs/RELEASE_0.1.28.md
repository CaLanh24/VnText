# Release 0.1.28 — hotfix: extract output lock no longer stuck on a reused pid

Owner 2026-11-22 asked for a hotfix release after the extract-lock fix. Task `release-0.1.28`, exact `RELEASE_RUN/candidate-0.1.28`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB; user data and evidence are preserved. Downloading the public baselines needs the Owner's explicit permission in the DEV session.

## Scope
- A lock left by a killed worker no longer blocks extraction forever when Windows gives its pid to another process: locks record the owner's creation time (`vntext/process_identity.py`); a live pid keeps the lock only when it matches. Same check for the traceability and translation-cache locks. Real running extractions are still refused, with a Vietnamese message.
- Version/provenance 0.1.27 → 0.1.28 and the scoped ordinary transition `release-0.1.27` → `release-0.1.28` in `tests/tools/cleanup_work_artifacts.py`.

## Evidence
Unit tests in `tests/unit/test_extract_output_refresh.py`, `test_traceability.py`, `test_translation_cache.py`; receipts in `TEST_RUN/agent-evidence/release-0.1.28/`.

## Published
Tag `v0.1.28` = `87cf4bd9a9eebb126d24da78bed4e8f293648ef5`, https://github.com/CaLanh24/VnText/releases/tag/v0.1.28. Digests (GitHub = local): Setup `9a2506e88a50d633b51135a4ee45b9b55ab65abbdf16a2b962d39a03ea1f8283`; full update `057e8018761c34cf9f228836697efc4ef8db8e7b8ac78ec8ce4bd7a148f0e036`; from-0.1.27 `77cc43f8b2f1da11b11b9a9068ed123de03e2d8fad78e875a8b11a6c63ac8e71`. Update 0.1.27→0.1.28 on a baseline copy: PASS (7340 files, 0 mismatches). NOT_PROVEN: native UI for the lock fix, native Setup install, Owner machine re-check. Known: `test_extract_layout_matrix` `unity_data_dir` handle error (pre-existing, order-dependent).
