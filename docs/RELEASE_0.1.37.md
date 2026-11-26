# Release 0.1.37 — plain language, one vocabulary, numbered steps

An external UX review of 0.1.36 said the app "speaks like a programmer". Brain relayed it with the Owner's instruction (chat, 2026-11-27) to fix everything and release without asking, which falls under the Owner's standing permission (DEV session 2026-11-25). Presentation only: no change to schema, worker protocol, CSV format, or the patch/translate behaviour. Task `release-0.1.37`, exact `RELEASE_RUN/candidate-0.1.37`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB.

## Group 1 — internal errors shown in plain words, with a button that fixes them

- **Translate page, translator missing.** The raw "Không nạp được runtime CTranslate2 (ModuleNotFoundError…)" is replaced by "Chưa cài bộ dịch Anh → Việt trên máy…" with **Cài bộ dịch** (the existing resources install path) and **Xem chẩn đoán** next to the start button. The technical cause is written to the journal. The size of the download is not shown: the app does not know it before the download starts.
- **Error banner.** A translator-missing error (also when it comes from a task) shows the same plain sentence; the raw text goes to the journal.
- **Settings → data.** One summary instead of two repeated lines: "Thiếu N thành phần: bộ dịch, công cụ cho game Ren’Py." (no `model:`, `renpy:`, `Python worker`), with **Sửa tự động** (the existing download path, hashes checked). Details stay in the journal and behind **Xem chẩn đoán**.
- **Extract log.** Internal step and run states (`stale`, `unity_hash`, `discovery_inventory`, any `snake_case` token) are mapped to ordinary Vietnamese; an unknown token reads "Đang xử lý".
- **Earlier runs list.** Each item is read by its title instead of the type name `ExtractRunInfo`.

## Group 2 — one vocabulary

| Before | After |
|---|---|
| Tạo patch | Tạo bản Việt hóa (navigation, titles, buttons, dialogs, errors, worker messages, README) |
| Sửa CSV | Sửa bản dịch (CSV only in file-picker filters and details) |
| game / asset / bundle | Thư mục game (a game data file is "tệp dữ liệu của game") |
| Thư mục xuất / gói dịch | Nơi lưu bản dịch |
| OPUS-MT · INT8 · CTranslate2 | Dịch Anh → Việt trên máy |
| Mức lọc Sạch/Cân bằng/Quét sâu | one explaining line added |
| glyph / mapping font | "font có đủ dấu tiếng Việt" |
| Chọn SDK đã cài… | Chọn công cụ… |
| Kiểm tra trước khi build | Kiểm tra |
| engine | loại game |
| Python worker / worker | bộ xử lý nền / tác vụ |
| review_only.csv, locator, manifest | plain descriptions |
| "Patch sẽ bỏ qua" filter | "Dòng sẽ bị bỏ qua" |

Identifiers (task ids, file names such as `translation.csv`, `Patch_Viet_Hoa`, JSON keys) are unchanged.

## Group 3 — step guidance

- The sidebar numbers the four steps (1 Lấy text, 2 Dịch, 3 Sửa bản dịch, 4 Tạo bản Việt hóa) and shows a check mark when a step is done.
- A **Tiếp: …→** button in the page header jumps to the next step once the current one is finished.
- The build page already shares the game folder, the output folder and the translation file with the earlier steps; the translation file now shows its real path once it exists. Font, font size and images moved under **Tùy chọn nâng cao**, closed by default.
- Sửa bản dịch: the bulk actions (select filtered / untranslated / needs review / translatable, clear, delete selected) are one **Thao tác** menu; **Dịch đã chọn** stays outside it.

## Design decision
Earlier work removed every collapsible disclosure from the app. The Owner's UX review asked for font, size and image options to be folded, so the build page now has exactly one closed disclosure (`PatchAdvancedExpander`); `test_app_has_no_collapsible_disclosures…` allows that one and no other.

## Tests
- WPF harness `Owner0137_Group1…3` (7 checks): plain translator text and the install button when missing, resource summary and the fix button, no internal token in the extract log or run list, a scan of every static string on the main window for developer terms, no old names left in code, step numbering and next-step logic, advanced options folded and bulk actions in one menu.
- Updated harness and Python tests that pinned the old wording.

## Not done / not proven
See the checkpoint in `AI_STATE.md`.
