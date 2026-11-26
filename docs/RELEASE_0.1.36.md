# Release 0.1.36 — Sửa CSV and Tạo patch: every skipped line explained, nothing silent

The Owner tried 0.1.35 on a real Ren'Py game and reported six problems in Sửa CSV and Tạo patch. Brain relayed the report, with the instruction to release when the gate passes. This release falls under the Owner's standing permission (DEV session 2026-11-25). Every problem was reproduced on a synthetic Ren'Py layout built for the tests; no game data was used. Task `release-0.1.36`, exact `RELEASE_RUN/candidate-0.1.36`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB.

## Root causes and fixes

1. **No one-click selection of untranslated or needs-review rows.** The filters existed, but checking rows meant knowing to combine a filter with "Chọn đang lọc".
   - New buttons "Chọn dòng chưa dịch" and "Chọn dòng cần xem lại" check every matching row of the document, including rows the current filter hides. They switch the filter so the checked rows are the ones shown.
   - New filter "Patch sẽ bỏ qua" shows exactly the rows Tạo patch leaves out.

2. **A row translated by hand kept "Đã dịch · Chưa có đường ghi patch được chứng minh…".** There were two causes:
   - The editor read a row's review flag once, when the CSV opened. After Save, the review ledger (`review_only.csv`) correctly dropped the row, but validation fell back to the stale flag and kept the review status.
   - One label covered two different things: rows the machine translator could not translate safely, and rows with no proven way to write into the game.

   Fixes:
   - The status now always comes from the ledger. A saved translation that passes the checks clears it at once; an unsaved one says "Đã dịch — bấm Lưu để đưa dòng này vào patch".
   - The ledger now names its kinds: `mt_blocked`, `human_review`, `retranslate_blocked` (all resolved by a valid translation) and `review_only`.
   - `review_only` is never resolvable by a translation. Its label says "Không ghi được vào game…" and its fix says the row is simply skipped and can be removed ("Bỏ qua dòng này").

3. **"Dịch đã chọn" changed nothing and said nothing.**
   - Cause: a row left in the human-review ledger by an earlier run was protected from every later machine translation. A selected run skipped it even with review turned off.
   - Cause: the app then showed the generic "Dịch tự động hoàn tất", and the per-row reasons were codes in the log.

   Fixes:
   - An explicitly selected row is translated through every normal check.
   - With human review on, the new result goes back to the ledger as a draft. With it off, a passing result is saved and leaves the ledger.
   - The result dialog lists the counts and each distinct outcome in plain Vietnamese, with its row count (for example "bản dịch máy đang chờ bạn duyệt: bấm 'Chấp nhận đề xuất'…").

   This reverses an earlier test, renamed `test_human_review_toggle_off_translates_an_explicitly_selected_row`, which pinned the old protection.

4. **"Cần xem lại 5" with no reason or action.** Clicking a row now shows, under the grid, the reason, how to fix it, and the machine's proposal when there is one. Three actions sit with it:
   - **Chấp nhận đề xuất** uses the proposal and saves.
   - **Sửa bản dịch** opens the cell for editing.
   - **Bỏ qua dòng này** removes the row with the same conflict-checked removal as "Xóa đã chọn".

   The count refreshes from the ledger after each action.

5. **Tạo patch said 22 ineligible lines while Sửa CSV said 5.**
   - Cause: the patch audit walked every manifest entry. That included rows the person had deleted (still listed in the manifest) and extraction-only review rows kept outside the CSV in `review_only.csv`. Sửa CSV counted only CSV rows.
   - Fix: the audit now counts only rows of the CSV. Deleted rows (`user_excluded`) and review evidence outside the CSV (`outside_csv_review`) are reported apart and never called ineligible.
   - The audit returns every skipped row (up to 5,000) with its reason and fix.
   - The confirmation offers "Tạo patch", "Xem danh sách" and "Hủy". The list groups rows by reason with the fix for each group and opens Sửa CSV on "Patch sẽ bỏ qua".

6. **Tạo patch failed: "Ren'Py dialogue mapping conflict: <id>".**
   - Cause: the game already held a *different* Vietnamese translation for that line in `game/tl/vietnamese/`, and one such line aborted the whole patch. Two layouts lead there, and both are reproduced: a translation file shipped with the game (or from another tool), and an earlier VNText overlay copied in by hand with no install receipt.
   - Fix, in someone else's file: the game's translation is kept byte for byte and that line is left out (`existing_translation_conflict`). The rest of the patch is written. The result says how many lines and which file.
   - Fix, in VNText's own `vntext.rpy` copied in by hand: that line is rewritten with the newer translation, and there is never a second, competing block.
   - Unchanged: a VNText patch that was installed (receipt present) and then edited by hand still blocks the build. The message names the way out ("Gỡ và hoàn nguyên").
   - A failed Tạo patch now shows its cause and fix on the Patch screen, with the unit id masked to its hash suffix. "Gửi báo lỗi" (owed since 0.1.35), "Tạo gói báo lỗi" and "Mở Sửa CSV" sit next to it. The completion dialog uses the same text.
   - The send preview no longer says "Gói CHƯA được gửi đi…". Before sending it says "Gói chỉ được gửi khi bạn bấm Có ở dưới."; the manual "Tạo gói báo lỗi" route keeps its own wording.

## Tests
- `tests/unit/test_owner_report_0136.py`: one named test per issue, on an extracted synthetic Ren'Py layout. It covers:
  - rows waiting for review, rows blocked by the machine translator, and rows with no write route;
  - deleted rows;
  - a translation already shipped in the game's own file;
  - an earlier VNText overlay copied in by hand;
  - the product OPUS-MT model for "Dịch đã chọn";
  - the send-preview wording.
- WPF harness `Owner0136_Issue1…6`: bulk selection with a hiding filter, stale-flag clearing, the selected-translate result text, the focused-row reason/action/proposal, the "Patch sẽ bỏ qua" filter and list, and the explained failure with the bug-report buttons on the Patch screen.
- Updated tests that pinned the old fail-closed or protected behaviour: `test_renpy_patch` (string and dialogue conflicts in another file; an installed-and-edited patch still blocks), `test_renpy_roundtrip`, `test_human_review_workflow`, `test_patch_preflight`, `test_csv_editor_api`.

## Not done / not proven
- The Owner's own bundle was not received, so it is not known which of the two layouts produced the reported conflict on the real game. Both are fixed and tested on synthetic layouts.
- The 22-versus-5 gap is reproduced by structure (deleted rows plus review evidence outside the CSV), not with the Owner's numbers.
- No real send to the Owner's Discord channel.
- `test_renpy_roundtrip.test_own_overlay_reextract_keeps_authoritative_identity_and_source` fails on the previous HEAD as well, with the same error: its fixture translates CJK text that the bundled font lacks. It is outside the release gate and was left as it is.
