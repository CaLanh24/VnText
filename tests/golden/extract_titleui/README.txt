Unity UI extraction reference (external fixture only)

This directory intentionally contains no captured game rows or fixed object
identities. Generic UI/TypeTree coverage is tested with synthetic micro-
fixtures in `tests/unit/test_unity_capability_microfixtures.py`.

For an opt-in real-game check, set `VNTEXT_GAME_FOLDER` to an isolated copy.
The extractor must discover objects by current metadata and emit a locator;
it must not depend on a title, path, key list, or bundled reference corpus.
Missing external fixtures are `SKIP`/`NOT_TESTABLE`, never a PASS.
