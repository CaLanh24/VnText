# Release 0.1.30 — completes what 0.1.29 left open

Owner (DEV session 2026-11-23/24) asked for the 0.1.30 completion and confirmed its release. Task `release-0.1.30`, exact `RELEASE_RUN/candidate-0.1.30`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB; user data and evidence are preserved. The public 0.1.29 and 0.1.7 baselines are downloaded with the Owner's explicit permission in the DEV session; the official Ren'Py 8.5.3 SDK (hash pinned in `vntext/renpy_toolchain.py`) is downloaded for tests only.

## Scope
- Trace store and translation cache locks are operating-system locks (`vntext/os_lock.py`), like the extract output lock.
- Bug report: masked context lines around unsupported Ren'Py blocks; Unity bundle / serialized file and ZIP container shapes (`vntext/structure_shapes.py`) replayed by `tests/tools/synth_from_report.py`; a preview dialog lists every part with its size and says nothing was sent.
- DEV_PROBES-only font / image-spec picker override (`Services/PickerOverrideProbe.cs`), excluded from every non-probe build.
- Test fixes: the `unity_fs` contract hash was refreshed after the intentional Unity v22 change; the WPF fixture expectation for the Patch button follows the Owner's 2026-11-21 behaviour.
- Version/provenance 0.1.29 → 0.1.30 and the scoped ordinary transition `release-0.1.29` → `release-0.1.30`.

## Evidence
Receipts in `TEST_RUN/agent-evidence/release-0.1.30/`.
