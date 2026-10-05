Generic capability coverage notes
=================================

This directory contains only small synthetic risk/capability metadata. It
does not freeze an extracted corpus or identify a particular game.

Optional Unity E2E uses one caller-supplied external fixture, copied to the
registered TEST_RUN scope. The source stays read-only and no game
copy is committed. Missing fixture or runtime permission is SKIP or
NOT_TESTABLE, not a successful coverage claim.

Supported evidence states are PIPELINE_PASS, PIPELINE_FAIL,
FILE_OK_FONT_FAIL, and REACHABILITY_BLOCKED. A per-row locator/path id is
valid only when produced by the current fixture and recorded in evidence.
