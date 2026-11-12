# Release 0.1.19 — kế hoạch rebaseline một lần (CHƯA ÁP DỤNG, chờ Owner)

Trạng thái: **DỰ THẢO để Brain xin quyền Owner**. Không có mã, epoch hay registry nào bị đổi bởi tài liệu này. Không áp dụng khi chưa có câu trả lời trực tiếp của Owner.

## Vì sao
Epoch hiện tại `epoch-20261112-035-release019` (nguồn dựng `28f62d3`) đã ở giới hạn độ sâu 8 hop: hop thường kế tiếp bị chặn (`epoch_transition_depth_exceeded`). Nguồn bảo trì đã chuẩn bị (`main`) có sửa thật (mục danh mục tiếng Anh cho lỗi OCR `vntext/image_batch.py:74`, tồn tại từ 0.1.18) và sửa harness test; muốn đưa vào bản phát hành thì phải dựng lại từ nguồn mới, nên cần một epoch gắn nguồn đó. Cách duy nhất không nới 8 hop là một rebaseline một lần, đúng mẫu 0.1.16/0.1.17.

## Phạm vi xin (một lần, tiêu thụ ngay khi áp dụng)
- Nguồn đã chuẩn bị: **`cba2a80`** (`main`, cháu của `28f62d3`; VERSION 0.1.19; gồm `3679a5d` sửa harness runner, `0b38d5b` mục danh mục OCR + 3 sửa assertion/fixture WPF, và các commit tài liệu). Quyền áp dụng cho `cba2a80` và các hậu duệ chỉ gồm commit quyền/checkpoint/focused-prerequisite (không thêm tính năng).
- Task/scope/ngân sách GIỮ NGUYÊN: `release-0.1.19`, `RELEASE_RUN/candidate-0.1.19`, 5 GiB (5,368,709,120 B), shared `.dev-env` 11 GiB, guard 48 MiB, trả về 1 GiB ở dọn cuối. Không đổi mục tiêu, không đổi model, không xóa dữ liệu người dùng/lịch sử/cache, không nới validator/guard, không publication trước Brain/Root ACCEPT. Các grant trước vẫn đã tiêu thụ.
- Bảo vệ GIỮ NGUYÊN: CAS manifest đầy đủ + epoch mong đợi, snapshot rollback xác minh trước khi ghi, kiểm tra lịch sử/chu trình, cây sạch, không writer khác, đọc lại sau ghi; độ sâu 8 hop của chuỗi mới tính lại từ epoch rebaseline (không nới, không chính sách “standing”).

## Văn bản xin Owner (đề xuất; Owner có thể sửa)
“Cho phép MỘT lần rebaseline metadata epoch cho release 0.1.19 từ `epoch-20261112-035-release019`, nguồn đã chuẩn bị `cba2a80` (gồm sửa danh mục tiếng Anh cho lỗi OCR và sửa test harness) và hậu duệ quyền/checkpoint, giữ nguyên scope `release-0.1.19`, trần 5 GiB, shared 11 GiB, guard 48 MiB, CAS/rollback/lịch sử/8-hop; để chạy lại gate, dựng lại ứng viên và nghiệm thu native; không xóa dữ liệu, không publication trước ACCEPT.”

## Thay đổi mã khi (và chỉ khi) có quyền — một commit hậu duệ của `cba2a80`
1. `tests/tools/cleanup_work_artifacts.py`: thêm `RELEASE_TASK_0119_REBASELINE_ID = "owner-20261113-cba2a80-019"`, `…_PREPARED_SHA = <cba2a80 đầy đủ>`, `…_APPROVAL` (đúng lời Owner, trích nguyên văn) và mục trong `EPOCH_REBASELINE_AUTHORIZATIONS` → `("release-0.1.19", "0.1.19", approval)`; trong `_rebaseline_versions_match` thêm nhánh: version cả hai đầu = `0.1.19` và `_git_is_ancestor(PREPARED_SHA, target_sha)`. `_rebaseline_prior_task_allowed` đã cho phép cùng task. Không đụng ngân sách/limit.
2. Test đơn vị (cạnh `test_epoch_019_authority.py`): id/approval hợp lệ chỉ cho `release-0.1.19`, từ chối sai id/approval/task, từ chối khi nguồn đích không là hậu duệ của PREPARED_SHA, 8-hop và standing policy không đổi.
3. Cập nhật AI_STATE/ledger (cùng commit hoặc ngay sau, không đổi nguồn).

## Lệnh (sau commit ở trên, cây sạch, không writer khác)
```
cd C:\v   # HEAD = commit quyền (hậu duệ cba2a80)
# 1. plan (chỉ đọc)  --prospective-epoch-rebaseline-plan
# 2. apply (CAS)     --apply-prospective-epoch-rebaseline
# chung: --release-task-id release-0.1.19 --source-sha <HEAD> --rebaseline-from-epoch-id epoch-20261112-035-release019
#        --expected-manifest-sha256 <sha256 manifest đọc lúc chạy> --epoch-id epoch-20261113-037-rb-release019
#        --owner-rebaseline-authorization-id owner-20261113-cba2a80-019 --owner-rebaseline-authorization "<đúng văn bản approval>"
```
Kết quả plan/apply lưu ở `TEST_RUN/agent-evidence/release-0.1.19/rebaseline-{plan,apply}-*.json`; snapshot rollback do công cụ ghi trước khi đổi (đường dẫn ghi trong receipt apply). Nếu plan có lý do chặn (`reasons` khác rỗng) thì dừng, báo lý do, không áp dụng.

## Việc phải làm lại sau rebaseline (gắn SHA mới; không dùng lại gate của `28f62d3`)
Đăng ký lại/giữ scope `candidate-0.1.19` (`--register-release-task-scope`); đồng bộ source worktree sang SHA mới; **dựng lại** bằng `publish.ps1` (baseline 0.1.18/0.1.17/0.1.7 + hop 17→18 đã xác minh được tái dùng, không tải lại); chạy lại: nhóm Python công khai, `test_setup_package` (không PYTHONUTF8), release verify/publisher/guard, `test_wpf_workflow` đầy đủ 37 + runner contract (đủ điều kiện profile 5 GiB), regression updater WPF, ma trận backend gói thật A/B/C + N1–N4; ghi hash 5 tài sản mới; Root lặp lại native (Setup mới, nâng cấp, updater/Setup-required, công khai sau ACCEPT). Bản dựng `28f62d3` và `native019` hiện tại chỉ còn giá trị lịch sử.

## Rủi ro/ghi chú
- Không có rebaseline thì `28f62d3` vẫn dựng được và công bố được (thiếu một mục danh mục tiếng Anh cho một lỗi OCR hiếm — giống 0.1.18); quyết định thuộc Brain/Owner.
- Rebaseline chỉ siết lại metadata epoch; không xóa gì. Dung lượng: giữ candidate/baseline (≈ 3.2 GB project) trong khi chạy; trần 5 GiB.
