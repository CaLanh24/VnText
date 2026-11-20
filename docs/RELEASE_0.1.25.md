# Release 0.1.25 — generalized Ren'Py font replacement (candidate, not published)

Owner 2026-11-20 granted a 7 GiB temporary `C:/v` allocation for exact `RELEASE_RUN/candidate-0.1.25` (task `release-0.1.25`, 48 MiB reserve, 11 GiB shared, terminal 1 GiB; no history/data deletion) for sequential native tests of the generalized font replacement on the original Dissonance, Lesson and The Wrath, fixes, and a conditional release after the gates. Public baseline is 0.1.23; 0.1.24 was built but not published. Not published by DEV.

## Scope
- Ren'Py: literal-font styles for game fonts lacking Vietnamese (cmap evidence) and the engine-level `config.font_replacement_map` block (CONTRACTS §8); Unity: unchanged TMP adapter route.
- Version/provenance 0.1.24 → 0.1.25 and the scoped ordinary transition `release-0.1.24` → `release-0.1.25` in `tests/tools/cleanup_work_artifacts.py`.

## Evidence
`TEST_RUN/agent-evidence/release-0.1.25/` (payload hashes, read-back, native receipts, gates). Runtime smoke: `tests/tools/renpy_font_replacement_smoke.py`.
