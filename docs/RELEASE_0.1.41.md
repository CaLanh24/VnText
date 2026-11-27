# Release 0.1.41 — plain Vietnamese everywhere, from the external UX review of 0.1.39/0.1.40

The Owner asked (chat, 2026-11-27, relayed by Brain) to handle every point of the outside UX review in ONE release. Wording and presentation only: no behaviour, schema, worker protocol or identifier changed. The standing permission of 2026-11-25 applies. Task `release-0.1.41`, exact `RELEASE_RUN/candidate-0.1.41`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB.

## Changes (strings people read; identifiers and file names untouched)
- **Image page** (`Dịch ảnh`, edit view, errors and messages): "OCR" → "nhận dạng chữ", "region" → "vùng chữ", "review" → "bản xem lại", "render" → "dựng ảnh", "pixel" → "điểm ảnh", "crop" → "vùng cắt", "glyph" → "nét chữ", "clone" → "sao chép", "output" → "kết quả / nơi lưu ảnh". Example: "{0} region cần review; tọa độ theo pixel ảnh gốc" is now "{0} vùng chữ cần xem lại; tọa độ tính theo điểm ảnh của ảnh gốc…". Images inside game archives are listed by their path (`gui/button/…`), not the percent-encoded reference.
- **Progress line of an unfinished translation** names each count and leaves out zeros: "3 câu chưa dịch, 2 câu cần xem lại, 1 câu bị chặn". The "Bước 2/3" prefix is gone (the sidebar has four entries and no numbers): the line starts with the action.
- **Settings:** the component error says "Lỗi thành phần lúc …"; the translator row offers **"Cài bộ dịch"** when it is missing (otherwise "Mở thư mục") and no longer shows the technical path; when the background processor is missing too, ONE notice says both.
- **Saved logs:** an old run saved with "── stale ──" is mapped to plain words when it is shown; the saved file is not changed. A new "Lấy text" log is clean.
- **One vocabulary:** "Tệp bản dịch" (not "File bản dịch"), "Duyệt bản dịch trước khi tạo bản Việt hóa", "tệp" for file, "thành phần" for the things Settings installs and "dữ liệu của game" for what the game ships. Three screens that mixed Vietnamese and English in English mode are fixed.

## Tests
`tests/unit/test_user_strings_0141.py` scans every static string of every screen (all XAML), the Vietnamese literals of the app, the catalog keys, the English catalog values (no Vietnamese outside quoted button names) and the worker messages of the image and resource tasks for developer words. The WPF harness pins were moved to the new wording.
