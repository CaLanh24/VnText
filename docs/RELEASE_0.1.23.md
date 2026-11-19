# Release 0.1.23 — Ren'Py generated-font payload fix

Owner 2026-11-19 authorized Release 0.1.23 **if the packaged Ren'Py create/install/uninstall gate passes**. Public 0.1.22 is `d7f4642`; source baseline for this release is `6463e08` (overlay validator accepts the generator's own font + bundled licence).

## Scope
- Version/provenance 0.1.22 → 0.1.23 (VERSION, `vntext/__init__.py`, `app_backend.VERSION`, `release/version_info.txt`, publisher candidate/version lists).
- Scoped ordinary release transition 0.1.22 → 0.1.23 in `tests/tools/cleanup_work_artifacts.py`: task `release-0.1.23`, exact `RELEASE_RUN/candidate-0.1.23`, 5500 MiB standing temporary allocation (measured against the exact candidate), 48 MiB reserve, 11 GiB shared cap, terminal 1 GiB limit; forward hand-off from `release-0.1.22` only; no standing-hop policy, no rebaseline, no deletion of history/user data. Test: `tests/unit/test_epoch_023_authority.py`.

## Gate (must pass before the Brain publishes; not published by DEV)
Inspect the final Setup's embedded payload, run the **bundled worker from the packaged payload** to create a Ren'Py patch (synthetic fixture; bundled font + verified licence), install and uninstall with the generated installer, verify font/licence/script bytes and that the original game is untouched; exercise the exact 0.1.22 → 0.1.23 update apply/restart/health and data canary where feasible. No game run, no Owner install change.

Evidence: `TEST_RUN/agent-evidence/release-0.1.23/`.
