Unity patch-on-copy safety contract
===================================

This retained README documents the generic safety boundary. The public
repository does not bundle a Unity game, frozen game bytes, or a captured
patch baseline. External verification is opt-in and must receive an explicit
fixture root such as VNTEXT_GAME_FOLDER.

The test helpers copy only caller-selected resources into a registered
tests/golden/_work scope and never write to the source root. They preserve
UnityFS metadata, object locators, backups, and read-back reports when an
external fixture is supplied.

CAPTURED=no
SOURCE_ROOT=external fixture supplied by the caller
ORIGINAL_SOURCE_UNCHANGED=required by the external test contract
UNITYFS_HEADER_CHECK=required when a Unity resource is inspected
PATCH_READBACK=required; timeout or missing evidence is a failure
FIXTURE_POLICY=synthetic fixtures are preferred; real game E2E is opt-in only

