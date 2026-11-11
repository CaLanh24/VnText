# Release 0.1.18 — ledger (PREPUBLICATION, BLOCKED before build)

Trạng thái: **CHƯA PHÁT HÀNH, CHƯA BUILD.** Không push/tag/upload cho tới khi Brain ACCEPT đúng ứng viên. Baseline công khai hiện tại: `v0.1.17` (Latest, 2026-11-08T06:09:40Z; tag chú thích `1ffee3a…` → source `ed3f5b58f1b0540e913785705080a1b3327d0455`; Setup `VNTextStudio-0.1.17-Setup.exe` 285,221,888 B sha256 `4e56da3e960c2030ce6c709bda2475b7c695a4dd680f1a1217817c7b836ccf7f`; updater `full-app-update-0.1.17-d403c45f9fabb262.zip` + `full-app-update-current.json`, và tuyến trực tiếp `…from-0.1.16-to-0.1.17…`). Receipt đo: `C:/vnrg/evidence/release-0.1.18/preflight-blockers.json`.

## Blocker đã đo (chưa có quyền bên ngoài)
1. **Ngân sách/epoch.** Công cụ cleanup không nhận task `release-0.1.18` (`unsupported_release_task_id` → cap mặc định 1 GiB); `release-0.1.17` là lịch sử đã đóng (HEAD ≠ epoch, policy 6.25/6.75 GiB không áp dụng cho build mới). Setup+payload+baseline updater của 0.1.17 từng cần đỉnh ~6.65 GB. Cần Owner/Brain cấp task budget + epoch (scope mới/rebaseline) cho `release-0.1.18`; DEV không tự tạo.
2. **Cung cấp phụ thuộc theo lock.** `release/dependency_profiles.py --check-installed` FAIL trên mọi môi trường đã có: `.dev-env/.venv` (3.14.8, 23 lệch), `.dev-env/release-venv` (3.12.10, 21 lệch, vd pillow 13.0.0≠12.3.0, transformers 5.20.1≠5.19.0, thiếu pydantic/annotated-types/typing-inspection), `.dev-env/python-3.12` (trống). Publisher đã đổi sang bắt buộc lock + `--require-hashes`, nên dựng release cần tải đúng bộ wheel đã khóa (quyền tải/cài riêng, chưa có). `verify_dependency_locks.py` PASS chỉ ở mức metadata (cài native NOT_PROVEN).

## Đã kiểm trong phạm vi độc lập
- Ranh giới probe của release harness: `App.xaml.cs` chặn `*-probe`/`--wpf-workflow-e2e` khi build không có `DEV_PROBES`; harness release chỉ dùng `--release-version/--release-verify/--smoke-worker` (không bị biên dịch bỏ). Không thấy lỗi cần sửa.
- Registry gzip/cold: `test_registry_storage`, `test_cleanup_verification_memory`, `test_dependency_profiles` (12 test) OK trên HEAD docs `c4962ec`. Không thấy lỗi cần sửa; probe quota cho `release-0.1.18` bị chặn bởi mục 1.
- Giấy phép/notice: danh sách lock mới thêm gói runtime (pydantic, pydantic-core, annotated-types, typing-inspection, …) so với bản 0.1.17; cần kiểm dist-info license thực trong payload sau khi dựng (chưa làm được vì mục 2).

## Thay đổi từ v0.1.17 (đã có trên `main`, chưa phát hành)
- Dịch/OCR: phân loại mã/định dạng game (nhãn "Mã/định dạng game" trong CSV, bỏ qua khi patch), OCR chống dương tính giả (ảnh không chữ không còn bị dịch/dựng), dịch nháp offline cục bộ (CT2/OPUS-MT) — **bản nháp thô, không phải bản dịch hoàn chỉnh; cần người rà soát; không công bố chất lượng toàn game**.
- Patch: patch một phần từ các dòng đủ điều kiện (có xác nhận và đếm dòng bỏ qua), một EXE cài đặt có nhãn; trạng thái Patch theo bản CSV hiện tại; nhật ký có màu mức độ; cảnh báo preflight đến tận log tác vụ.
- Giao diện: tiến trình Analyze một thanh, thông báo thành công không chặn, tái dùng phân tích khi chỉ đổi thư mục xuất, nhãn tìm CSV xuống dòng, chuyển ngôn ngữ cập nhật trạng thái, nhập bản dịch cũ theo gói đang chọn, Apply/Undo thay thế hàng loạt giữ đúng phiên bản CSV.
- Setup: hộp thoại điều khoản bản địa hóa; bước tài nguyên; gỡ cài đặt trong khung.
- Kiểm toán R01–R12: lưu lịch sử registry nén gzip, hồ sơ phụ thuộc có khóa, ranh giới probe Debug/Release, bảo vệ dữ liệu người dùng.

## Giới hạn phải ghi trong ghi chú phát hành
Dịch offline thô; patch chỉ phần dòng đủ điều kiện; engine ngoài Ren'Py/Unity đã kiểm chưa được chứng minh; native visual cho sáu sửa đổi gần nhất chưa hoàn tất (desktop khóa); cài native các phụ thuộc theo lock chưa chứng minh.

## Tài sản phát hành dự kiến (tối thiểu)
`VNTextStudio-0.1.18-Setup.exe` + payload updater một-tệp `full-app-update-0.1.18-<digest16>.zip` + manifest `full-app-update-current.json` + tuyến trực tiếp `…from-0.1.17-to-0.1.18…` (bắt buộc cho client 0.1.17 theo quyết định tuyến cập nhật). Không nhân bản ZIP phiên bản cũ.
