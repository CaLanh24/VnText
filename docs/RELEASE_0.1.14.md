# VNText Studio 0.1.14 — acceptance hiện hành

**IN PROGRESS — publication cần Brain ACCEPT.** Owner (2026-10-28): “Xem báo cáo này xem đúng k, nếu đúng thì sửa cho bản update 0.1.14, sửa xong release. Cần hoàn thành nhanh.” Báo cáo là UI QA 0.1.13 (source `9b2c05e`, receipt `DEV_RUN/uiqa28-receipt.json`, `uiqa28-deep-receipt.json`). Trạng thái hiện hành ở [AI_STATE](../AI_STATE.md); 0.1.13 đã phát hành ([ledger](RELEASE_0.1.13.md)).

## Quyền và phạm vi

- Owner cho chẩn đoán, sửa và release 0.1.14, gồm đợt visual bounded (batch 3: backdrop/scale modal, fill/elevation primary, localization) thay cho hạn chế “không sửa/không giao DEV/cần PM duyệt” của báo cáo. Không đổi geometry/motion đã freeze, hit target, command, palette semantic, kiến trúc, model hay validator.
- Version 0.1.14; giữ các baseline updater trực tiếp được hỗ trợ gồm 0.1.12/0.1.13 và các route cũ theo publisher contract. Budget/epoch riêng của release-0.1.14 (không thừa hưởng quyền rebaseline của 0.1.13). Không đưa uninstall, DPI, game thật hay QA toàn app vào gate. Publication sau Brain ACCEPT.

## Triage 9 finding báo cáo

| # | Finding | Kết luận | Nguyên nhân / source / evidence | Sửa |
|---|---|---|---|---|
| 1 | Updater About: cấu hình trỏ `Desktop\New folder` | **CONTEXTUAL (bàn giao test bị nhiễm), không phải lỗi sản phẩm** | `Desktop\vntextapp\.vntext-update-source.json` có `updates_root` = `DEV_RUN\release-0.1.13\Updates` (thư mục chưa tồn tại) và `work/backup/staging_root` = `Desktop\New folder\.update\…` cùng khóa `fault_inject_after_first_replace`: đúng định dạng override của harness updater. Payload Setup chính thức (7194 mục) **không** chứa file này; file tạo cùng giây với bản cài (18:33:37). Điều này chỉ gợi ý nó đi cùng bản cài; nguồn gốc chính xác (ví dụ chép từ cây test hay di chuyển thư mục cài) chưa có bằng chứng được theo dõi nên không khẳng định. Guard `update working directory must stay under the install test scope` hoạt động đúng. Cây Desktop không bị sửa | Không đổi source, không sửa cây Desktop, không rebase đường dẫn, không nới guard. Phản hồi thân thiện cho cài đặt bị di chuyển có thể cân nhắc sau (chưa làm). Bản Desktop cần cài sạch từ Setup chính thức hoặc bỏ file override (việc của người kiểm thử) |
| 2 | CSV lỗi → bảng rỗng, tiêu đề cũ, lý do chỉ ở Journal | **CONFIRMED** | `LoadCsvEditor` xóa hàng/số liệu trước khi biết file đọc được; `CsvEditorStatus` không hiển thị ở đâu | Giữ document đang mở tới khi file mới đọc được; banner inline “Không mở được X: lý do (đang giữ Y)”; dirty guard không đổi |
| 3 | Lưu có warning chỉ ghi “Đã lưu 4 dòng” | **CONFIRMED** | `FinishCsvEditorSave` bỏ qua kết quả validate; cột Trạng thái trống | Số dòng, lý do thường gặp và chỗ xem ngay ở kết quả lưu; cột Trạng thái điền từ validate; guard lưu draft/patch giữ nguyên |
| 4 | Bulk preview bị cắt | **CONFIRMED** | `MaxHeight="54"` | Vùng cuộn tối đa 170 DIP, đọc đủ; preview/confirm/backup/Undo giữ nguyên |
| 5 | Thiếu manifest: hai thông điệp mâu thuẫn | **CONFIRMED** | CSV bị từ chối khi chọn không được lưu; readiness rơi về file mặc định (“File không tồn tại”) | Readiness đánh giá chính CSV vừa chọn nên cùng lý do cụ thể; khóa Translate/Patch giữ nguyên |
| 6 | Nhãn patch “Unity/Naninovel” cho plain_text_line | **CONFIRMED** | `ApplyPatchDelivery` đặt tên engine cho mọi route installer | Nhãn nêu cách giao (“Gói patch có installer…”); hướng dẫn nêu loại nội dung thật (văn bản thường / Unity-Naninovel / chung); detection, thuật toán, read-back không đổi |
| 7 | Backdrop/scale modal không thống nhất | **CONFIRMED** | Journal dim 155/blur 7, glossary chỉ dim, dialog 140/blur 8; modal riêng không theo UI scale | Hằng backdrop chung (dim 140, blur 8) cho mọi modal kể cả glossary; Dialog/Journal/Release notes theo UI scale; ở 100% không đổi |
| 8 | Primary phẳng, không elevation | **CONFIRMED (visual bounded, Owner cho phép)** | `GuiPrimaryButtonStyle` nền `BlueBrush` phẳng | Token `PrimaryFillBrush` xanh→cyan (cùng họ màu `SettingsTitleBrush`), `PrimaryElevation`; disabled phẳng; hit target/command/palette giữ nguyên |
| 9 | Wording/casing/giờ/badge | **CONFIRMED** | Nút Journal trộn Anh–Việt; giờ theo culture máy (`ToString("g")`); badge là literal | “Mở nhật ký”, “Chép vị trí tệp”, “Chép thông tin lỗi”; giờ hiển thị theo ngôn ngữ app; badge qua binding; không dịch CSV/đường dẫn/log trên đĩa |
| — | Escape của release notes | **NOT_PROVEN (rút lại, không tạo bug)** | Binding CU chỉ trả owner; source có handler Escape | Không đổi |

## Native p14a (Brain, bản giải nén thử từ Setup thật, exe `286e53c6…6654`, 2026-10-29) và hiệu chỉnh

PASS có mục tiêu: #2 (CSV lỗi: tiêu đề/document 4 dòng giữ, banner inline nêu file, lý do, đang giữ `translation.csv`, toast đỏ), #3 (lưu draft: toast vàng có 4 dòng đã lưu + 1 cảnh báo + lý do placeholder + nơi xem; cột Trạng thái dòng 1 có lý do; dirty xóa), #4 (preview 3 dòng/4 thay thế đọc đủ trong vùng cuộn 170 DIP, Áp dụng gradient + shadow), #8 (primary gradient/elevation sáng và tối, disabled phẳng), #7/#9 (dark 120%: Journal và release notes theo scale, footer vừa; nhãn Việt, giờ `29/10/2026 00:07`; backdrop glossary đã blur; English badge “On-device processing”). Chưa pixel parity, chưa toàn app.

Lỗi mới phát hiện: `SetGlossaryBackdrop` blur mọi con của root trừ overlay, kể cả lớp toast, nên toast validation “Thêm” khi hai ô rỗng bị mờ không đọc được. **p14a bị từ chối cho release.** Sửa: `ModalBackdrop.BlurBackground` chỉ blur nội dung nền, bỏ qua overlay và mọi lớp có z-order ≥ overlay (toast z=200, lớp dim của dialog), khôi phục đúng effect cũ khi đóng; không đổi geometry/motion. Test harness mới `ModalBackdrop_BlursOnlyBackgroundAndKeepsToastSharpAndRestores` + kiểm tĩnh. Finding 5: với CSV hợp lệ đang mở, chọn CSV thiếu manifest giữ document cũ (đúng hành vi); case gốc (chưa chọn gì) cần native lại: **chọn CSV thiếu manifest trước**; test harness nay xác nhận cả dòng readiness lẫn workflow không còn “File không tồn tại”.

## Acceptance 0.1.14

| Mục | Trạng thái | Evidence |
|---|---|---|
| Source + test (harness 6, Python 3, static) và hiệu chỉnh glossary toast | Chờ gate canonical | `DEV_RUN/gatec/impl50-*.json` |
| Build/verify/smoke/updater trên candidate sửa | Chờ | Candidate p14b |
| Native có mục tiêu lần hai (no-manifest trước, nhãn patch plain text, glossary validation toast + một confirmation lồng) | Chờ | `native_plan_p14b.md` |
| Publication | HOLD tới Brain ACCEPT | — |
