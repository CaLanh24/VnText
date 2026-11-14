# Usability batch — 2026-11-13 (not accepted yet)

Owner requests a simple extract → translate/edit one CSV → create patch workflow, with image translation on its own page. No game execution or game testing in this batch. Public release 0.1.19 is unchanged; no new publication is authorized.

Baseline local HEAD: `723f9293d9ef414d3d2eab12eef768e0acf7797d`. Later Root fixes remain uncommitted. Claude DEV quota reset is 22:50 Asia/Tokyo; Root temporarily owns source writes under the AGENTS exception.

| Area | Change | Verification |
|---|---|---|
| RenPy extraction | Automatically separate technical syntax/engine metadata; recognize proved screen text and ordinary labels. Persist user exclusions across extraction. | Representative inert source fixture with official SDK source tooling; no game run. |
| One CSV | Row checkboxes, translate selected with existing OPUS, save into the same file, conflict-protected delete/exclude. | Real OPUS selected-row test preserves unselected manual multiline translation and empty rows. |
| Status | Update translated status/counts after editing; retain real structural diagnostics. | WPF behavior tests. |
| Patch | One visible packaging action, explicitly opting into valid translated subset; unrelated review/pending rows do not veto it. Keep per-row identity/hash/placeholder/writeback checks. | Guard tests and per-key CSV-to-payload readback; no game install. |
| Images | First-class sidebar page, cached results first; no redundant image buttons on Translate. Extract caches OCR; translation reuses it without rescanning. | Worker operation ownership tests; WPF fixture/native candidate still separate. |
| Notifications | Durable per-page notices; image failures do not fail text completion or appear on Extract. | Protocol and WPF navigation tests. |
| Resources | Read actual readiness; hide download when ready and repair only missing resources. | Focused resource/WPF tests. |
| Small CSV layout | Correct selection-bar/table/footer rows and use compact selection utilities. | WPF layout fixture in progress; earlier failed layouts are not PASS. |

## CSV and translation evidence

Small ignored evidence: `TEST_RUN/agent-evidence/usability-csv-quality/` contains fresh fixture CSV, technical exclusion audit, extraction status, per-key patch readback and `quality-review.json`.

The existing Owner CSV was **read only**: SHA256 `8e5d0e849a504b3e8354f676037e2c1ee55aaf5d2635cccb1e9a95a73a1bb0ef`, 319 rows, 311 nonempty translations. Its eight empty rows include seven technical strings and the misclassified “Mute All”. No replacement characters were found. Lexical flags include loanwords/scientific terms; flags alone do not establish bad translation. The 1,464-row CSV from the other machine is unavailable locally.

Fresh fixture review confirms readable rough Vietnamese, protected tags/placeholders and exact CSV-to-patch payload equality. “Return” originally became “Trả lại”; recognizing `RenPyScreen` as UI now gives “Quay lại”. “The Claiming” remains context-dependent; “Prologue” is retained as a name-like token. No claim of perfect semantics, every sentence being Vietnamese, whole-game coverage or gameplay quality is made.

## Gates / limits

- Focused Python run: 62 tests, two explicit native OCR skips; one test assertion used the wrong ledger path. After correcting it, the selected real-OPUS/protocol group passes 3/3. Other product checks in that run passed.
- Text integrity/catalog group: 31/31 PASS, including Vietnamese homographs, structure and newlines.
- WPF source/build/interaction/layout fixtures: **37/37 PASS**, final log `usability-20261114-wpf21.log`. Cancelled selected translation retains the picked CSV validity while withdrawing old patch claims. Selected/delete mutation uses the same separation; Delete dialog native behavior remains untested.
- Related Python: **97 PASS, 2 explicit native OCR skips**. Public groups CSV34/MT91/Patch37/maintenance44 PASS. Existing text-integrity31 PASS retained.
- Debug candidate build and OPUS smoke exit0 at `C:/v/DEV_RUN/bootstrap-build/VNText.Studio.App.exe`; EXE SHA256 `a36ac0b5e799ff2fb8194b3dfa40dfdf9f274d1245140456f9875957a7fd8f51`. This depends on the installed runtime and `.dev-env`, so it is not a portable build.
- The initial dirty-tree launcher refusal was resolved using the exact author metadata already present in the prior five commits (per-command only, no Git config change). Root launched the app through the clean launcher. Native verification found and fixed missing selection-command notifications; select-all/clear, confirmed delete/exclusion, source-English search and selected OPUS translation then worked. The synthetic CSV finished7/7 nonempty translations, with manual rows retained. No Owner data or game was used.
- Explicit Windows OCR/product OPUS image group: **32/32 PASS, no skips**. Two actual no-text PNGs produced0 detected/exported images and unchanged source bytes. Their summary exposed a negative remaining count and wrong unfinished label; both were corrected and regression-tested. Final evidence: `usability-20261114-image-report-final2.log`, `usability-20261114-no-text-native-final.json`.
- Final clean source/candidate/launcher/native handoff binding is in `TEST_RUN/agent-evidence/usability-20261114-root-final.json` and `DEV_RUN/bootstrap-build/build-identity.json`; older hashes above identify the earlier candidate only.
- Packaged candidate/native acceptance: **NOT PROVEN**. Owner approved temporary2.5GiB, but the Debug candidate fits the default1GiB and did not activate that grant. After author metadata/commit and launcher validation, perform the native checklist; no game run or release.
- No push, release, version change, Owner data mutation or game run.

## DEV handback delta (2026-11-14)
- **Regression fixed:** Root's patch invalidation for selected translate/Delete cleared the picked CSV's validity (`CancelledTranslate_KeepsThePickedCsvAndRestoresReadiness` failed). `InvalidatePatchSourceState` now has `keepCsvValidation`: old patch presentation/artifact claims are dropped (delivery withdrawn, preflight cleared, artifact marked behind, workflow not "done") while the current CSV stays valid and retryable; CSV SAVE still clears validation. New regression `SelectedTranslate_KeepsTheCurrentCsvValidButMarksTheOldPatchBehind`. WPF 37/37.
- **Budget/cleanup:** the default 1 GiB cap held for the DEV build after freeing owned disposable test scratch through the helper (127 dirs; 852 own stale MISSING records reclassified by the documented routine). No temporary budget was registered or needed.
- **Limits:** native/live acceptance is NOT_PROVEN; no game was run; the only Owner CSV used was local read-only (319 rows, 311 non-empty, 8 legacy-empty); the other-machine 1464-row CSV is absent. Candidate, launcher and fixture evidence: ignored receipts `TEST_RUN/agent-evidence/usability-20261114-final-*.json`.

## Functional audit delta (2026-11-14, post-quota reset)
- **Legacy CSV (older VNText, static screen candidates as review rows):** reproduced on a read-only copy of the Owner CSV (319 rows; source hash unchanged). Selecting "Mute All" used to report "no MT rows" because the 8 legacy rows sat in the human-review set. Fixed: `mt_ct2_status._effective_review_keys` (static candidates and excluded keys are not human review); `user_exclusions.exclude_machine_technical` auto-excludes and audits syntax-only candidates (319 -> 312 rows; "Mute All" drafted "Tắt tiếng tất cả"); the task end text says the drafted legacy row has no proven writeback path yet and that re-running Extract fixes it (`ok`/`complete` stay False). Patch guards unchanged.
- **Subset Patch e2e (real SDK source fixture, no game):** valid subset packages despite a stale `translate_status`, unsafe row omitted, per-key payload equals CSV, source/CSV/manifest unchanged; unscoped PARTIAL refused without the explicit subset; changed source hash and zero rows refuse.
- **Failure injection:** failed `os.replace` leaves the CSV byte-identical with a plain error.
- Tests: `tests/unit/test_legacy_csv_selected_translate.py` (4), `tests/unit/test_renpy_subset_patch_e2e.py` (5). Related set (extract/UI inventory/multiline/compiled/refresh/image batch/catalog/csv editor/exclusions/partial override/completion/worker translate): 149 PASS, 2 skips, 0 failures. Image and engine-analyze hypotheses are covered by the existing image-batch/extract-refresh tests and Root's native evidence; not re-run natively.
- Python-only change: the candidate worker runs from `C:/v`, so no rebuild; Root restarts the worker/app to pick it up. No push/release/version/tag/game run.

## Review fixes on 76ee674 (2026-11-14)
- **Stale revision (CAS):** the selected-translate payload now carries `expected_csv_sha256` (the opened `_csvEditorSourceSha256`); WPF refuses to start without one. `run_translate_keys_ct2_task` checks it BEFORE any mutation, including automatic machine exclusions; `run_ct2_translate_keys` re-verifies before every checkpoint/cancel/final flush and tracks the hash of its own last write, so an external edit before or during MT is never overwritten (`CsvRevisionConflict`, plain error, no traceback).
- **Editor reconcile:** cancel / error / partial terminal outcomes used to clear the pending flag and skip the reload. They now reconcile exactly the owned path through the existing safe refresh (clean editor reloads, dirty editor keeps unsaved edits and is marked stale, an unrelated CSV is untouched).
- **Exclusion ledger transaction:** `exclude_rows` writes the ledger first, but a failed CSV write now restores the previous ledger byte-for-byte (a ledger created by that call is removed; an existing one is never deleted); a failed rollback raises an error naming the ledger. `_exclude_legacy_machine_rows` no longer swallows failures: conflict/IO errors refuse the translation with nothing persisted.
- **Legacy completion:** a selected-only draft of a legacy row is `ok/complete` with summary "Bản nháp đã lưu; Patch sẽ bỏ qua N dòng khác…" (`patch_omissions`), never an error and never patch proof.
- **Generic labels (real OPUS + generic catalog, no title rule):** Chapter 1 → Chương 1, Mute All → Tắt tiếng tất cả, Settings → Cài đặt; "Prologue"/"Epilogue" stay English as a documented name-like keep (`copy_literal`, no catalog entry) - NOT a translation. Without a UI context, "Mute All" is plain MT and came out as "Mục lục": real extraction rows carry a UI context.
