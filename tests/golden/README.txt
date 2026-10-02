Generic test fixture policy
===========================

This directory may contain only small, synthetic, reproducible inputs. It
must not contain a game copy, extracted corpus, translation reference, model,
Release binary, or user output.

Focused package tests create their own synthetic CSV/manifest/locator inputs.
External Unity verification is opt-in through VNTEXT_GAME_FOLDER and writes
only to a registered tests/golden/_work scope. Missing fixtures are SKIP or
NOT_TESTABLE, never a fabricated PASS.

Generic Unity patch-on-copy safety
---------------------------------------------------------------------
tests/golden/patch_unity/ retains only the generic copy-and-read-back note.
It contains no captured game bytes. Helpers copy explicit resources into
tests/golden/_work and never write to the external source root.

Canonical fixture status
------------------------
CAPTURED=no
FIXTURE_SOURCE=synthetic unit inputs or caller-supplied external root
RETENTION=keep only reproducible contract fixtures and required evidence

Unity patch-on-copy capture status
----------------------------------
UNITY_PATCH_CAPTURED=no
EXTERNAL_FIXTURE=required for UnityFS/Addressables read-back
ORIGINAL_SOURCE_UNCHANGED=required

External E2E policy
-------------------
No runtime/game E2E is claimed by this public snapshot. A caller may supply
an external fixture and must retain its own trace, hashes, and read-back
reports under the registered _work scope.

Addressables scope
---------------------------------------------
Addressables discovery and structure tests use synthetic bundles or an
explicit external fixture. Object-count, catalog, and read-back failures
remain fail-closed; no captured game expectation is part of this tree.

External fixture retention
-----------------------
The old game-derived e2e/extract snapshots were removed. User-supplied game
fixtures are never committed here; they remain outside the repository and
are copied only into a disposable, registered _work scope for opt-in tests.

