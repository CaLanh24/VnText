# Release 0.1.18 — ledger (PREPUBLICATION, BLOCKED before build)

Trạng thái: **CHƯA PHÁT HÀNH; Setup/updater CHƯA BUILD (chờ ủy quyền tải phụ thuộc theo lock).** Không push/tag/upload cho tới khi Brain ACCEPT đúng ứng viên. Baseline công khai hiện tại: `v0.1.17` (Latest, 2026-11-08T06:09:40Z; tag chú thích `1ffee3a…` → source `ed3f5b58f1b0540e913785705080a1b3327d0455`; Setup `VNTextStudio-0.1.17-Setup.exe` 285,221,888 B sha256 `4e56da3e960c2030ce6c709bda2475b7c695a4dd680f1a1217817c7b836ccf7f`; updater `full-app-update-0.1.17-d403c45f9fabb262.zip` + `full-app-update-current.json`, và tuyến trực tiếp `…from-0.1.16-to-0.1.17…`). Receipt đo: `C:/vnrg/evidence/release-0.1.18/preflight-blockers.json`.

## Ủy quyền, ngân sách và epoch (đã hòa giải)
- Ủy quyền: Owner 2026-11-12 ("Xem còn vấn đề gì thì sửa nốt, xong thì release") là ủy quyền phát hành 0.1.18; quyền lưu trữ tạm thời theo mục đứng 2026-10-24 (artifact-retention.md) cho phép Coordinator nâng trần theo nhu cầu đo được, không hỏi lại. Không dùng lại ngân sách 0.1.17 hay khoản 6,75 GiB đã đóng; không tạo rebaseline hay áp dụng chính sách hop đứng của 0.1.17.
- Mã hỗ trợ (routine, additive): task `release-0.1.18` (trần ban đầu 3 GiB trong `release/budget_policy.json`), quy tắc chuyển tiếp 0.1.17 → 0.1.18 bắt buộc mỗi đầu mút đúng phiên bản, danh sách phiên bản của `publish.ps1`, lựa chọn của `run_with_cleanup.py`. Lịch sử/ngân sách 0.1.17 không đổi.
- Từ chối thật của guard (không phải thiếu spec): sau khi có spec, kế hoạch chuyển epoch bị chặn bởi `registry_metadata_incomplete` ← `cold_missing_records_need_review` (28.917 bản ghi MISSING lạnh sau nén gzip). Đây là lỗi tương thích cold-registry: bản ghi MISSING lạnh chỉ cần xem xét ở báo cáo cleanup, như bản ghi MISSING sống trước khi nén vốn không chặn bước epoch. Đã sửa hẹp (`_epoch_blocking_metadata_issues`); mọi vấn đề metadata khác vẫn chặn. Có test.
- Epoch `epoch-20261112-029-release018` đã áp dụng (chuyển tiếp thường, plan/apply receipt trong `C:/vnrg/evidence/release-0.1.18/`), scope `RELEASE_RUN/candidate-0.1.18` đã đăng ký, profile `release-0.1.18` active: trần 3.221.225.472 B, project non-exempt đo được 389.086.351 B, `.dev-env` 11.280.157.835/11.811.160.064 B. Kế hoạch cấp phát/dọn: `allocation-plan-0.1.18.json`.

## Blocker còn lại: cung cấp phụ thuộc theo lock (cần ủy quyền riêng)
`release/dependency_profiles.py --check-installed` FAIL trên mọi môi trường hiện có (`.venv` 3.14.8: 23 lệch; `release-venv` 3.12.10: 21 lệch, vd pillow 13.0.0≠12.3.0, transformers 5.20.1≠5.19.0, thiếu pydantic/annotated-types/typing-inspection; `python-3.12` trống). Publisher bắt buộc lock + `--require-hashes`. Không có ủy quyền Owner nào đã tìm thấy cho việc tải phụ thuộc build (mục lưu trữ đứng và dev-validation đều nói rõ KHÔNG gồm tải/cài phụ thuộc hay chấp nhận giấy phép; các cho phép trước chỉ về model Hy-MT2/runtime và tải SDK Ren'Py). Chưa tải gì. Kế hoạch: `dependency-acquisition-plan.json` — 52 wheel (75.812.129 B nén, ~289 MB giải nén) từ files.pythonhosted.org vào venv mới cô lập `.dev-env/release-venv-0.1.18`, đỉnh ước tính ~365 MB, `.dev-env` sau đỉnh ~11,65 GB (< trần 11,81 GB). Không sửa `.venv`/`release-venv`/lock.

## Đã kiểm trong phạm vi độc lập
- Ranh giới probe của release harness: `App.xaml.cs` chặn `*-probe`/`--wpf-workflow-e2e` khi build không có `DEV_PROBES`; harness release chỉ dùng `--release-version/--release-verify/--smoke-worker` (không bị biên dịch bỏ). Không thấy lỗi cần sửa.
- Registry gzip/cold: lỗi thật đã sửa (xem trên). Gate không cần tải, trên HEAD mã `4f7630e`: 215 test (cleanup 193+, epoch 017/018, registry storage, cleanup verification, dev bootstrap, dependency profiles, docs version) OK; build Release WPF 0 cảnh báo, không có kiểu probe trong DLL, smoke worker 5 bước exit 0 (`wpf-release-build.json`, `wpf-release-smoke.json`, exe sha256 `4d538b69…5786`).
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
