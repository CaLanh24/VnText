# Current checkpoint — usability batch after 0.1.19 (Owner task 2026-11-13); PARTIAL, mid-batch

## Authority and scope
Release 0.1.19 is closed (published, Root-accepted, cleaned; tag/assets untouched). This NEW Owner task fixes end-to-end usability failures from four screenshots. NO push/tag/release/version authority; no inherited 0.1.19 rebaseline/budget (consumed). Normal DEV default profile (1 GiB; project 714,699,086 B at this checkpoint). All work in `C:/v`; no Owner app/data/game writes; Root is the only UI owner; vntext-ui skill verified (Impeccable 4.8.0, Operate mode, palette and 36+30 DIP style preserved).

## Done at this boundary (local commits only, HEAD `053def8`, tree clean, nothing pushed)
- Item 3 (safe-subset Patch): `vntext/patch_gate.py` explicit `partial_patch_override` (ContextVar, no sticky state) relaxes ONLY the PARTIAL extraction-status check; per-row identity/hash/schema/path/placeholder/locator checks and row skip rules unchanged; FAILED/EMPTY/COMPLETE-with-flags stay blocked; `run_patch_task(partial_override=)` + worker param `partial_override`; `patch_coverage.json` records `USER_SAFE_SUBSET`, `owner_override`, included/omitted/review-only counts and is never a full-coverage claim; zero eligible rows says so and builds nothing; `patch_gate --partial-override` for the preflight. WPF: "Patch phần an toàn" secondary action next to "Đóng gói patch" with a counts confirmation, VI/EN catalog. Tests: `tests/unit/test_partial_patch_override.py` (5) + `test_patch_input_safety` (15) PASS.
- Item 4 (resources): Settings/Data reads real readiness once on first open (check-only task, no download), shows one brief "Sẵn sàng" state when all installed, hides the primary download, shows "Sửa/tải tài nguyên còn thiếu" only when something is missing/corrupt; detail goes to the log.
- Item 2 (partial): a manual CSV save now refreshes translated/total counts and safe-subset availability immediately.
- Gates: WPF Release build 0 warnings, `test_wpf_workflow` 37/37, public Python groups (34/91/37/44) PASS.

## NOT done (still open in this task; no claim made)
Item 1 (row checkboxes, translate/exclude selected, persisted exclusions), rest of item 2 (provenance reason retained after save, status wording), item 5 (Image Translation as a sidebar tab), item 6 (per-operation error/progress ownership, completion dialogs), item 7 (novice audit). Native behaviour of every change is NOT_PROVEN until Root. No DEV candidate built: a candidate needs about 0.6-0.9 GB payload plus obj under a 1 GiB project cap already at ~0.71 GB; a bounded DEV task budget (about 2.5 GiB, own scope + registered epoch) would need to be decided; no guard bypass was attempted.
Known stale tests (not from this batch, default path unchanged): `test_renpy_multiline_dynamic.test_product_dynamic_...` and `test_renpy_ui_inventory.test_unproven_dynamic_...` assert a blanket block that the Owner's 2026-11-02 scoped-patch decision superseded; not re-measured on the previous commit.

## Writer
Fixed Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26`, cwd `C:/v`.
