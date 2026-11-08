# Release 0.1.17 — ledger

Trạng thái: **ĐÃ PHÁT HÀNH** (2026-11-08T06:09:40Z) — https://github.com/CaLanh24/VnText/releases/tag/v0.1.17 (Latest), tag chú thích `v0.1.17` → source `ed3f5b58f1b0540e913785705080a1b3327d0455`. Các commit sau đó trên `main` chỉ đổi `tests/` (công cụ cleanup, guard game gốc, test) và docs; byte sản phẩm không đổi. `v0.1.16` và mọi asset của nó giữ nguyên (9 asset, `Setup.exe` sha256 `2f9ce610…1124bc`).

Mỗi mục dưới đây là một verdict riêng; không mục nào thay cho mục khác.

## Tests (nguồn chính xác `ed3f5b5`)
- WPF workflow 37 test (gồm fixture CSV real-open/real-Preview và fixture chuyển trạng thái cửa sổ cập nhật) + test aggregate + test guard game: 61 test, child exit 0 (wrapper `REVIEW_REQUIRED` vì lịch sử epoch được bảo vệ).
- Installer tự chứa không cần framework: `test_patch_installer` 4/4 trên đúng byte `e7a7ee98…`. Updater backend: public 0.1.16 → ứng viên, exit 0, 7196/7196 tệp, canary giữ nguyên (không phải UI native).
- Công cụ sau artifact (`775ef19`): 189 test cleanup/epoch/aggregate/guard, child exit 0, cleanup phạm vi PASS, wrapper `REVIEW_REQUIRED` (lịch sử được bảo vệ). Test dịch/MT/engine của chu kỳ trước dùng lại, không chạy lại vì không đổi.
- Aggregate `tests/tools/whole_game_acceptance.py` (inventory → CSV → overlay sinh lại bằng renderer sản phẩm → đọc lại): 311/311 MAIN, `ACCEPT_ELIGIBLE`, 0 chặn; Root ACCEPT ghi ở `release-readiness/root-accept-0.1.17.json` (aggregate sha `7ad9485a…`).

## Build
- Publish đúng source `ed3f5b5`: Setup `VNTextStudio-0.1.17-Setup.exe` 285.221.888 B sha256 `4e56da3e960c2030ce6c709bda2475b7c695a4dd680f1a1217817c7b836ccf7f`, payload 7197 tệp. Đỉnh dung lượng lấy mẫu 6.648.569.803 B, dưới ngưỡng hủy 6.660.554.752 B (cap 6,25 GiB + guard 48 MiB không đổi).
- Ba lần publish trước hỏng ở bước kiểm kê cuối (`inventory_timeout`, cleanup `REVIEW_REQUIRED`): xác minh chuỗi epoch giữ ~4,5 GB bộ nhớ trên máy 8 GB. Sửa ở `c649892`/`775ef19` (chiếu chỉ các trường cần kiểm, không giữ bản đồ lớn trong memo; 4,5 GB → 0,46 GB, 188 s → 73–80 s). Không đổi cap, guard hay sampler.

## Native
- Brain/Root (agent-desktop, CU 0): CSV ở 1043x720/UI 120% Dark — đủ 6 điều khiển trong khung, ≥3 dòng; cửa sổ cập nhật bằng UI sản phẩm thật + mạng giả có ZIP thật — dòng trạng thái và tên UIA nút chính theo trạng thái, canh giữa; nhãn nút phụ KHÔNG nằm trong kết luận. Setup/gỡ cài đặt VI dùng lại từ `f6a4cb5` (Setup.cs không đổi).
- Game Ren'Py thử trên bản gốc đã khóa hash từng tệp: tuyến tuyến tính 227 câu đến màn hình kết thúc, hai lần xem Lịch sử (dòng dài nhất #129, ngắn nhất #220), tiêu đề, thẻ Lưu/Tải A/Q, nạp lại autosave cuối; restore chính xác (1433 tệp game + tệp Owner hiện tại). Attestation `brain-native017-final-20261108.json` (sha `f3bb75cd…`).
- Suy luận được chấp nhận và gắn nhãn: việc nạp script thành tựu (không hiển thị được: popup tắt, gallery không có nơi gọi). Không có ảnh từng hộp thoại, không đánh giá ngữ nghĩa.
- Lời mời cập nhật CÔNG KHAI trong app chưa được kiểm native: checklist `release-readiness/native-checklist-public-offer.md` (fixture `run017/native-upd016`, verifier chỉ đọc `evidence/verify_public_offer_result.py`).

## Cleanup
- Cleanup phạm vi PASS; lịch sử epoch được bảo vệ vẫn `REVIEW_REQUIRED` (không phải lỗi child, không waive).
- Owner AppData: 497 tệp lịch sử → 2 tệp hiện tại, NGUYÊN NHÂN KHÔNG RÕ (Owner trả lời "Không hoặc không rõ", không phải phê duyệt). Backup 497 giữ nguyên, không khôi phục/quy kết; kiểm tra phạm vi hiện tại chính xác (guard `tests/tools/original_game_guard.py`, Root review `ROOT_REVIEWED_CURRENT_TASK`).
- Sau phát hành: đã xóa baseline đã dùng, harness scratch, worktree nguồn ứng viên, patch-ready; giữ `ReleaseRoot` cục bộ (đúng byte đã phát hành), fixture 0.1.16 cho kiểm tra công khai, evidence gọn, backup 497, lịch sử epoch.

## Publication
- Đúng 5 asset (không có asset checksum thứ sáu; checksum nằm trong thân release): `VNTextStudio-0.1.17-Setup.exe` 285.221.888 B; `full-app-update-0.1.17-d403c45f9fabb262.zip` 68.553.720 B; `full-app-update-current.json` 2.331.838 B; `full-app-update-from-0.1.16-to-0.1.17-current.json` 2.321.521 B; `full-app-update-from-0.1.16-to-0.1.17-f3d6a0c7871f87be.zip` 65.855.137 B. Sha256 từng tệp ở thân release và `release-readiness/SHA256SUMS.txt`.
- Đọc lại ẩn danh sau phát hành (`public-readback-0.1.17.json`): tag chú thích → `ed3f5b58f1b0540e913785705080a1b3327d0455`; release non-draft, non-prerelease, Latest; tải đủ 5 asset, byte và sha256 khớp kho cục bộ và digest của GitHub; thân release có liên kết Setup đầu tiên, source SHA và 5 checksum; không chứa tên game hay dữ liệu Owner.
- Đường cập nhật 0.1.16 → 0.1.17 và tuyến cũ (từ 0.1.7) được giữ; bản cũ hơn đi qua các release đã phát hành theo planner của client (chưa kiểm native công khai).

## Chưa chứng minh / không tuyên bố
Hoàn hảo ngữ nghĩa, kiểm từng dòng hộp thoại, mọi game/DPI/đường UI; lời mời cập nhật công khai trong app (chờ Root); nhãn "Để sau" bằng native; nguyên nhân mất 495 tệp AppData lịch sử.
