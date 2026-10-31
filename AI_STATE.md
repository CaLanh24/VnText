# Current checkpoint — 2026-10-31

## Authority và bước tiếp theo

- Release 0.1.14 ĐÃ PHÁT HÀNH: [https://github.com/CaLanh24/VnText/releases/tag/v0.1.14](https://github.com/CaLanh24/VnText/releases/tag/v0.1.14) (stable, latest), source `002035a4a523fb09a538dc0f20879c6cffc186c9`, Brain ACCEPT cho phạm vi sửa lỗi báo cáo UI QA 0.1.13 (ledger [0.1.14](docs/RELEASE_0.1.14.md)); 0.1.13 ở [ledger](docs/RELEASE_0.1.13.md). Không claim QA toàn app/pixel parity/game thật; model OPUS-MT và giới hạn giữ nguyên.
- Authority hiện hành: Owner giao MỘT BATCH sửa F1–F7 của fixed8, candidate riêng để QA; KHÔNG push/release/đổi version-tag/updater/game gốc. Phạm vi implementation đã xong; QA độc lập còn mở.
- Brain Codex `01a17d30-bc24-7940-a814-f172fe463e3e`; Claude DEV cố định `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26`, snapshot cursor 1007 / result 1006: quota, báo reset 11:10 JST. Codex tạm writer theo ngoại lệ quota, hoàn tất correction rồi đóng task ở boundary sạch; không có writer/child build còn chạy. Task sau reuse DEV này khi quota hồi phục, không tạo DEV khác.
- NEXT: QA mở [style-fixed10 0.1.14](<C:/v/DEV_RUN/style-fixed10-0.1.14/VNText Studio.exe>), source `9248f975c7a19bbef6bbfe5419072835a875bd35`, EXE SHA256 `515b4a40fd65b1d70f597e2d72f2e5fee6aaab47cd22457b9f8b39fcf2c46bc3`. DEV DONE / QA PENDING, native NOT PROVEN. Gate 32/32 (child 0, 0 skip/warning), build p14n + release-verify + hai worker smoke PASS. [Handoff F1–F7](<C:/v/DEV_RUN/gatec/fixed10-HANDOFF.md>), [native checklist](<C:/v/DEV_RUN/gatec/native_plan_p14n.md>), [599-key mapping](<C:/v/DEV_RUN/gatec/f6-full-string-map-fixed10.md>). Fixed9 nội bộ bị Brain từ chối trước handoff, payload pristine đã đóng; fixed8/audit vẫn giữ.

## Source, candidate và evidence

- 0.1.14: tag `v0.1.14` → `002035a`; Setup `902a32868de92ecf85a605f655d0de8dba67bd64cbc0e33a9e70d4bc762e0c27`; exe `c92d992dc4247ac5e515eb8e281438a119d560f1dcbc2e139eebb58d77fb2c1d`; 15 asset khớp (tên/kích thước/sha256). 0.1.13: tag `v0.1.13` → `9b2c05e`; Setup `ab06e365310ea15d4b9dc48bb2e337c9fb8c51fdc1c5beb12f2ea930b740383d`. Setup 0.1.13 đang ở `DEV_RUN/release-0.1.13/Setup.exe` (OWNER_TEST_PENDING, file của Owner: không xóa). Bản cài Desktop `vntextapp` của người kiểm thử mang file override updater ngoài payload Setup chính thức: cấu hình theo ngữ cảnh, không phải lỗi Setup; nguồn gốc không có bằng chứng được theo dõi.
- Gate 0.1.14: `test_wpf_workflow` 23 (`002035a`), Python 20 + epoch 3 (`e6b2efa`), traceability/cancel/worker_tasks reuse từ `9b2c05e`; release-verify, hai smoke, updater 3 ca trên p14b; native p14a/p14b có mục tiêu PASS (ledger). Wrapper REVIEW_REQUIRED tách khỏi child exit 0.
- Owner quyết #4 (2026-10-27): "Cho quét tĩnh chỉ để xuất review-only; MAIN rỗng, không dịch/patch, luôn PARTIAL (khuyến nghị)" (CONTRACTS). Source `db0e847` + `4809077`; native p13o xác nhận: 0 MAIN / 8 review PARTIAL, không ID/proof, Translate/Patch bị khóa (`native47-review-result.json`). Receipt native: `native47-*`, `native48-sdk-result.json`, `native22-*.json`, `native13_prep.json`, `native13_watch.ps1` (chỉ đọc).
- Receipt prefix `C:\v\DEV_RUN\gatec`: native10-s13n-result.json, native11-s13n-result.json, native45-s13n-partial.json, native12-13-s13n-root.json, native13-s13n-cancel1.json. Bảng ledger tóm tắt giới hạn; history/index chỉ tra khi cần.

## Git/epoch và cleanup

- Git/source: payload `9248f975c7a19bbef6bbfe5419072835a875bd35`; HEAD sau handoff chỉ thêm docs checkpoint, không rebuild vì docs. Epoch `epoch-20261031-fixed10-014-9248f97`, dùng đủ 8/8 ordinary hops sau quyền rebaseline 0.1.14 thứ hai đã tiêu thụ ở `6f9af5b`; không còn quyền rebaseline mới. Tag/public v0.1.14 vẫn `002035a`. Gate/build/native/cleanup/release là các verdict riêng.
- Checkpoint riêng đã cũ: `DEV_RUN/gatec/cleanup_phase_root_checkpoint.json`; KHÔNG ghi đè trạng thái mới ở đây bằng checkpoint cleanup cũ. Trong transaction mới có thể ghi operational delta vào receipt ignored được chỉ rõ, cập nhật tracked ở boundary đã có; không docs→epoch→docs loop.
- Cleanup hiện hành: chỉ dispose payload fixed9 pristine, runtime chẩn đoán, p14n/source và input/TEMP do task sở hữu sau khi consumer terminal; receipt tại `DEV_RUN/gatec/fixed10-close-fixed9.json`, `p14n-build-closure.json`, `candidate-verify-p14n.json`. GIỮ fixed8 + mọi dữ liệu audit/Owner, app fixed10 cho QA, baselines/inputs/fixtures còn consumer; không đụng Setup 0.1.13/0.1.14 của Owner hoặc Desktop. Historical/whole-workspace cleanup chưa phải PASS; xem disposition riêng trong handoff/receipt.

## Tra cứu

- [INDEX](docs/INDEX.md): toàn bộ tài liệu theo chủ đề/trạng thái; [WORKFLOW](docs/WORKFLOW.md): bootstrap/checkpoint/compact/history/cleanup.
- [CONTRACTS](CONTRACTS.md): invariant/authority theo mục; [TEST_MATRIX](TEST_MATRIX.md): gate theo vùng; [ARCHITECTURE](ARCHITECTURE.md): owner/source.
- [Release0.1.13](docs/RELEASE_0.1.13.md): current acceptance; [history](docs/history/RELEASE_0.1.13.md): chronology cũ, không task mới. Không tự đọc mọi tài liệu để resume.
