# Release 0.1.38 — follow-up to 0.1.37: sizes, plain reasons, cleaner wording

Follow-up the Owner asked for in chat on 2026-11-27 ("dọn hết… làm xong 0.1.38 và release luôn"), under the standing permission of 2026-11-25. Presentation and test fixes only: no change to schema, worker protocol, CSV format or translate/patch behaviour. Task `release-0.1.38`, exact `RELEASE_RUN/candidate-0.1.38`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB.

## Changes
- **Download sizes shown before pressing the button.** The translator-missing sentence says "khoảng 75 MB"; the Settings summary adds "Dung lượng tải khoảng N MB" from the missing components (translator ≈ 75 MB, Ren’Py tools ≈ 156 MB; measured from the shipped model folder and the public SDK archive).
- **Every machine-translation check code has a Vietnamese label.** The build confirmation had shown "question mark lost". `REASON_LABELS_VI` now covers all `mt_check` codes; developer words ("placeholder", "synonym", "profile legacy", "extract lại") are gone from the labels. Test `test_reason_labels_0138`.
- **Warning wording.** "Cảnh báo: N dòng cần xem lại" counted every row with a note, while the footer's "Cần xem lại" counts the review ledger: two numbers with one name. The warning now says "cần chú ý".
- **Component check failure.** An unreadable status file no longer prints the raw .NET exception; the plain sentence points to "Kiểm tra lại" and "Xem chẩn đoán", the cause goes to the journal.
- **Wording left over from the bulk rename.** "Sẽ bản Việt hóa", "Câu Tạo bản Việt hóa sẽ bỏ qua", "Chọn nơi lưu bản dịch gói dịch" and similar phrases were rewritten as proper Vietnamese.
- **Sidebar** widened to 218 px so "4 Tạo bản Việt hóa" is not clipped; English label "Build translation".
- **Test fix.** `test_renpy_roundtrip.test_own_overlay_reextract_keeps_authoritative_identity_and_source` failed on every build since the font-coverage gate: its fixture translated CJK text and the bundled Vietnamese font has no CJK glyphs. The gate is right; the fixture now translates to Vietnamese-renderable text.
- **THIRD_PARTY_NOTICES** has a regenerated inventory of the 47 locked runtime distributions (PyInstaller is no longer a dependency).

## Checked in the real UI (dev build, agent-desktop, synthetic 8-row Ren'Py layout)
"Thao tác" menu and its selection, "Chọn chưa dịch" (4 rows), step ✓ and "Tiếp: Dịch →" after extraction, the build page with filled paths and the closed advanced options, the confirmation with skipped lines and "Xem danh sách", the Settings component summary.

## Published
Tag `v0.1.38` = `b0c753e715448d0bca0bda10b5e65e5aa76cbe84`. Setup sha256 `7d89ec05d4f982691cd3b283dd49bcba1a35287fec5c262d93bfb39027a89157` (GitHub = local, 5/5 assets). Update 0.1.37→0.1.38: 7341 files verified.

## Found after the build, not in this release
In the real app, "Sửa tự động" installed the Ren'Py tools (hash checked) but could not download the translator model: the worker runs with `HF_HUB_OFFLINE=1`. The fix (`_online_for_model_download`, offline switches lifted only during the explicit download) is committed after the tag and ships with the next version.

## Not done / not proven
See `AI_STATE.md`.
