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

## Standard label correction (2026-11-14, after cfa43e6)
- Generic `Prologue`/`Epilogue` kept as English were not usable UI Vietnamese. The existing exact-label catalog (`vntext/ui_labels.py`, proven UI context only) now maps `prologue` -> "Lời mở đầu" and `epilogue` -> "Lời kết" (`quit` -> "Thoát" was already catalogued). No title-specific rule, no prose/proper-name rewriting, no model change.
- Bounds (tests): unknown context, dialogue and menu-choice contexts never match; only an exact standalone label does ("The Prologue", "Prologue [name]", "Prologue {b}..{/b}", "Prologue\nTwo", "Prologue: Kai" stay untouched); a dialogue "Prologue" remains a `copy_literal` name keep. The real OPUS selected-translate route yields Lời mở đầu / Lời kết / Thoát next to Chương 1 / Tắt tiếng tất cả / Cài đặt.
- Gates for this diff: legacy+catalog 18 OK; owner-flow e2e 4 OK; public-mt PASS. Earlier related157 (2 skips), WPF37 and public groups remain valid (no WPF/UI source change).
- Native: Root verified stale-selected refusal and unchanged external bytes plus a 7-row selected retry; native cancel remains NOT PROVEN (fixture/capture limits, no app defect diagnosed).

## UI batch V1–V7 (2026-11-14, base `e41df9c`)
Owner/QA findings (`TEST_RUN/agent-evidence/uiqa1114-review.json`) fixed together; nothing outside them redesigned. Fonts, palette, radii, elevation, navigation and the 30/36 DIP control roles are unchanged.

| Finding | Files | Regression |
|---|---|---|
| V1 CSV table floor | `MainWindow.xaml`, `MainWindow.CsvLayout.cs`, `Services/CsvEditorLayoutBudget.cs`, `ViewModels/MainViewModel.CsvEditor.cs` | `--csv-budget-fixture`, `--csv-native-repro-fixture`, `--csv-layout-fixture` |
| V2 find/replace alignment | `MainWindow.xaml` | `--csv-budget-fixture` (labels of one/two lines, both languages) |
| V3 row checkbox | `Themes/ControlStyles.xaml`, `MainWindow.xaml` | `--csv-budget-fixture` (token brushes, idle/checked/disabled, IsSelected) |
| V4 journal severity | `Converters/LogSeverityConverter.cs`, `Services/AppJournalStore.cs`, producers in `MainViewModel*.cs` | `--v-batch-fixture` (typed + content-negative, page == saved journal) |
| V5 Images states | `Services/ImagePackageProbe.cs`, `ViewModels/MainViewModel.ImageText.cs`, `Controls/ImageWorkspacePanel.xaml`, `Services/UiText.cs` | `--v-batch-fixture` (six states, Details, manual editor, English), `--region-grid-fixture` |
| V6 About border | `MainWindow.xaml` | `--v-batch-fixture` (Light/Dark token, hover unchanged, no layout shift) |
| V7 image icon | `Themes/IconGeometries.xaml`, `MainWindow.xaml` | `--v-batch-fixture` (distinct, centred, route/order/label unchanged) |

Design notes: the table has no forced minimum height; its three-row floor is measured from the real layout (UI scale applied, wrapped toolbars included). The find/replace group stays open whenever there is room (Owner 2026-11-02) and folds into one bar only when the measured viewport would otherwise keep fewer than three single-line rows. A one-line row is ~42 units; a larger selector control made every row ~10 taller, so the row checkbox keeps a 20-unit box area.

### V4/V5 corrections after independent review (2026-11-15)
- V4: `AppJournalStore.Level` no longer searches for `[error]`/`[warning]`/`[stderr]`/`scan_errors` anywhere in a line; page and saved journal both use `LogSeverityConverter.ClassifyText`, which normalises only leading timestamp/task wrappers, honours a leading `[stderr]` producer tag, and treats `scan_errors>0` only inside the `Unity analyzer:` envelope. Quoted source text carrying such tokens stays INFO in both places (`--v-batch-fixture`).
- V5: a parseable report whose images all failed (producer semantics in `vntext/image_batch.py`: failed OCR keeps status `UNTRANSLATED` with no `text_detected`) is `ImagePageKind.ScanFailed` (recovery action, no counts, manual editor kept), not the completed NO_TEXT state; a report whose images are all `NO_TEXT` stays completed. The fixture report helper now mirrors the producer (it had marked every non-NO_TEXT item `text_detected=true`, which made the failed case internally inconsistent). Report/hash/OCR guards are unchanged.

## Fresh review N1–N10 (2026-11-15, base `168354484d1e`)
Report `TEST_RUN/agent-evidence/fresh15-review-report.{html,json}`; V1–V7 acceptance is preserved (`vqa15-independent-acceptance.json`).

| Finding | Change | Files | Regression |
|---|---|---|---|
| N1 header | The compact header serves the CSV page only (`PageHeaderCompact` = compact AND tab == editcsv); other workflow pages keep the incumbent 38/32 DIP rhythm; `SelectedTab` raises it | `ViewModels/MainViewModel.CsvEditor.cs`, `MainViewModel.cs` | `--n15-fixture` (after fold + resize round trip) |
| N2 scroll thumb | `PageScrollViewer` is `Auto` on the existing overlay scroller (no gutter, no width jump); CSV grid/virtualization untouched | `MainWindow.xaml` | `--n15-fixture` |
| N3 OCR grid | Fixed action columns reserve measured width (`Auto` + `MinWidth`: Approved 92, Delete 96; English "BACKGROUND" header), text columns give way, source wraps with a tooltip, horizontal scroll is the fallback; font size unchanged | `Controls/ImageWorkspacePanel.xaml` | `--region-grid-fixture` (EN/UI120, dialog widths AND the real ~566-unit card width, no horizontal scroll needed) |
| N4 OCR checkbox | Approved display/editing use the scoped `CsvRowCheckBoxStyle`; binding and commit semantics unchanged | same | `--region-grid-fixture` (tokens, toggle, Space, disabled, Light/Dark) |
| N5 English | Root causes: `CsvCheckedText` had no dynamic localizer; picker titles lacked catalog keys; the new hint/menu strings are catalogued (no duplicate keys); CSV/game content is never localized | `MainWindow.xaml`, `Services/UiText.cs`, `WpfPathPickerService.cs` | `--n15-fixture` EN |
| N6 image identity | The chosen image's name (full path tooltip) shows in the manual editor before OCR; no OCR/review state is reused | `MainViewModel.ImageText.cs`, `ImageWorkspacePanel.xaml` | `--n15-fixture` |
| N7 patch source | `HasPatchSource` (exists) gates `RunPatchCommand`; a localized hint explains the missing/absent source; `RunPatch` keeps its guard; valid-subset path unchanged | `MainViewModel.cs`, `MainWindow.xaml` | `--n15-fixture`; patch preflight tests set an existing source |
| N8 picker | Folder and asset-file are two explicit routes (small menu on "Chọn..."); Cancel returns null and opens nothing else | `Services/*PathPickerService.cs`, `MainWindow.InputChoice.cs`, `MainViewModel.Paths.cs` | `--n15-fixture`; pin test |
| N9 names | Localized, distinct accessible names for the source/output Open/Choose buttons | `MainWindow.xaml`, `UiText.cs` | `--n15-fixture` |
| N10 journal | "Xóa tìm kiếm / Clear search" vs "Xóa nhật ký / Delete log" with a tooltip; the file-deletion confirmation is unchanged | `JournalWindow.cs` | `--n15-fixture` |

## Q1–Q2 scoped follow-up (2026-11-15)
Source chooser popup uses keyed InputChoiceMenuStyle/InputChoiceMenuItemStyle, shared semantic theme brushes/AppFont/UiBodySize and app UI scale; keyboard navigation and both commands remain native MenuItem behavior. No implicit/global menu style. CSV checked count has singular English for one, zero/plural retained and language refresh unchanged. `--n15-fixture` covers 0/1/2 selection and live language switch, popup theme/type/scale/target and disabled appearance. Native evidence and exact candidate SHA belong to ignored q15 receipts; this document does not claim Release acceptance.

## Polish batch U1–U9 / C1–C6 (2026-11-16, base `8dc6888`)
Report `TEST_RUN/agent-evidence/polish16-combined-review.{html,json}` (candidate values from the Owner task; not accepted until independent QA). Limited polish; no redesign, no backend/schema/worker change.

| ID | Change | Files | Regression |
|---|---|---|---|
| U1 glossary | Row tooltip with both full sides; selecting/focusing a row fills a wrapped detail strip under the list (keyboard path); rows keep ellipsis/density; delete/validation untouched | `MainWindow.xaml`, `Converters/NullToCollapsedConverter.cs` | `--u16-fixture` |
| U2 choice controls | Keyed `ThemedRadioButtonStyle` / `ThemedCheckBoxStyle` (semantic brushes, hover/focus ring/disabled) replace the stock-white implicit styles in the region details; grid checkbox untouched | `Themes/ControlStyles.xaml`, `Controls/ImageWorkspacePanel.xaml` | `--u16-fixture` (live theme switch) |
| U3 numeric fields | `IntegerRangeRule` rejects empty/text/out-of-range before the model update (nothing coerced); rounded error surface + hint adorner in the gap under the field (no layout shift); X/Y/DonorX/DonorY 0–99999, Width/Height 1–99999, Font 1–999 | `Validation/IntegerRangeRule.cs`, `ImageWorkspacePanel.xaml`, `ControlStyles.xaml`, `UiText.cs` | `--u16-fixture` |
| U4 CSV tools label | `CsvToolsToggleText` raised on language change; the label is a bound `TextBlock` (a bare string Content let `UiText.Apply` replay the first catalogued string, so the drawn label stayed stale after open/close); same for the Images "Chi tiết" | `MainViewModel.Settings.cs`, `MainWindow.xaml`, `ImageWorkspacePanel.xaml` | `--u16-fixture` (VI↔EN, open/closed) |
| U5 form width | One `FormWidthCap` (1120 DIP, left axis) on Extract/Translate/Patch pages, the persistent error banner and the Settings tab content; CSV table and image page stay full width | `Converters/CapWidthConverter.cs`, `MainWindow.xaml` | `--u16-fixture` |
| U6 translate axis | The "Nguồn dịch" group drops its extra 10 DIP side padding, sharing the left axis of the other headings | `MainWindow.xaml` | `--u16-fixture` (heading X spread < 1 DIP) |
| U7 images actions | One action row (primary next step, results actions, "Sửa ảnh", "Quay lại"); "Chi tiết" is a light disclosure above it; OCR state machine and commands unchanged | `ImageWorkspacePanel.xaml` | `--u16-fixture` (large and 1055×720) |
| U8 release notes | 700 DIP column, height ≤ 85% of the owner and the work area, body scrolls, header/footer fixed, tighter bullet/paragraph rhythm; other dialogs unchanged | `UpdateWindow.cs` | `--u16-fixture` |
| U9 journal title | Header "Nhật ký — Khắc phục lỗi" / "Journal — Troubleshooting" | `JournalWindow.cs` | `--u16-fixture` |
| C1 primary gradient | Idle/hover/pressed gradients per Owner token table (pressed is a new `PrimaryFillPressedBrush`); white label ≥ 4.5:1 along the whole gradient and on rendered pixels | `UiAppearance.cs`, `DesignTokens.xaml`, `ControlStyles.xaml` | `--u16-fixture` |
| C2 WARN | `LogWarningForegroundBrush` (Light #9A5B00, Dark #E0A33A) for log/Journal WARN; toast border untouched | `SeverityLogBox.cs`, `MainWindow.xaml`, tokens | `--u16-fixture` |
| C3 switch | `SwitchStyle` uses `SwitchOff*/SwitchOn*` DynamicResource tokens, focus ring and disabled state; follows a live theme switch | `ControlStyles.xaml`, tokens | `--u16-fixture` |
| C4 control border | `CtrlBorderBrush` / `SettingsPreferenceBorderBrush` (Light #7B8798, Dark #71829C) used by outline buttons, text inputs and Settings combos; card/line stay soft; focus colours unchanged | `UiAppearance.cs`, `ControlStyles.xaml` | `--u16-fixture` (rendered pixels ≥ 3:1) |
| C5 disabled primary | Neutral fill/text/border via `DisabledPrimary*` tokens and a non-layout edge layer | `ControlStyles.xaml`, tokens | `--u16-fixture` |
| C6 hover Light | Settings row #F0F5FC, navigation #DFE7F2, secondary hover #EFF5FF + control border; Dark values kept | `UiAppearance.cs`, `ControlStyles.xaml` | `--u16-fixture` (tokens) + native hover |

Known limits: the `ToggleSwitch` UserControl in `Controls/` is unused (the live switches are `SwitchStyle` check boxes) and was not touched; the release-notes work-area clamp uses the primary work area and only follows an owner that is on screen.

## R1–R2 reference-fidelity correction (2026-11-16, base `5971d93`)
Task `TEST_RUN/agent-evidence/ref17-live-comparison-task.{html,json}` (raw measured pixels; not CSS claims). Supersedes U5 (1120 DIP cap) and the C4/C6 secondary-button border/hover for BUTTONS only; inputs/selects keep `CtrlBorderBrush`.

| ID | Change | Files | Regression |
|---|---|---|---|
| R1 secondary buttons | Own tokens `SecondaryButton{Fill,Edge,Text,HoverFill,HoverEdge,HoverText}Brush` (Light idle #FFFFFF/#E2E3E5/#475569, hover #EEF2F7/#D3D7DE/#0F172A; Dark idle #1E293B/#394352/#94A3B8, hover #334155/#4B5869/#F1F5F9); `GuiOutlineButtonStyle` (Secondary/Outline/Compact) and `AboutUtilityButton` use them; edge stroke 0.667 DIP + layout rounding = ONE device pixel at UI100/OS150; Light-only mild `SecondaryElevation` fitted to the measured falloff (never `PrimaryElevation`; Dark none; disabled none); size/radius/commands/disabled/blue focus unchanged | `DesignTokens.xaml`, `UiAppearance.cs`, `ControlStyles.xaml` | `--u16-fixture` (rendered at 144 dpi: one edge row then fill, left edge, falloff, Dark no shadow, tokens) |
| R2 form hosts | `FormWidthCap`/`CapWidthConverter` removed; Extract/Translate/Patch/Settings hosts and the error banner stretch with the current left axis and one shared 10 DIP (15 px at OS150) right inset; CSV table and image page untouched | `MainWindow.xaml` | `--u16-fixture` (host = viewport − 10 DIP, left axis, no horizontal scroll) |
Not proven: pressed state, animation, every secondary button, UI120 pixel equality; reference apps were not re-measured by DEV (raw report measurements used).
