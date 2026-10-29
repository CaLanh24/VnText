# Current checkpoint — 2026-10-29

## Authority và bước tiếp theo

- Release 0.1.14 ĐÃ PHÁT HÀNH: [https://github.com/CaLanh24/VnText/releases/tag/v0.1.14](https://github.com/CaLanh24/VnText/releases/tag/v0.1.14) (stable, latest), source `002035a4a523fb09a538dc0f20879c6cffc186c9`, Brain ACCEPT cho phạm vi sửa lỗi báo cáo UI QA 0.1.13 (ledger [0.1.14](docs/RELEASE_0.1.14.md)); 0.1.13 ở [ledger](docs/RELEASE_0.1.13.md). Không claim QA toàn app/pixel parity/game thật; model OPUS-MT và giới hạn giữ nguyên.
- Authority: Owner đã cho chẩn đoán + sửa + release 0.1.14 (xong); bản kế tiếp cần mục tiêu và quyền mới. DEV sở hữu task bounded, Brain review handoff, giảm CU, Brain chỉ chờ theo event (AGENTS/WORKFLOW).
- Brain `01a17d30-bc24-7940-a814-f172fe463e3e` (Codex, read-only review khi DEV là writer). Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3` session `76922e45-71b2-47a9-be97-cf18b927ae26` đã hồi phục quota, là sole writer (cursor sau 743). Một writer, không second DEV.
- NEXT: bản chạy thử cho Owner (đợt style thứ hai, DEV chưa phát hành/chưa push/chưa thay tag, version vẫn 0.1.14): `C:\v\DEV_RUN\style-fixed2-0.1.14\VNText Studio.exe` (sha256 `be381a4b776100defb30647b7f18e7ea284b5d512937d47698f4bb49586119f6`, source `03aaa09a20ce9eca2d2745e8e41f12608929ef5a`) gồm 5 sửa còn lại (toast theo severity/theme, cửa sổ OCR trong work area kể cả khi nội dung tăng sau khi nạp, checkbox ảnh theo theme, hàng nút Lấy text, nhãn Cần xem lại + tiêu đề picker Patch) cộng 7 sửa style và 3 sửa uiqa29/29b trước đó. Native: chưa có (kế hoạch `DEV_RUN/gatec/native_plan_p14f.md`, 5 ca, đo bounds OCR trước/sau và toast tối). Bản `DEV_RUN\style-fixed-0.1.14` (c7e312c) được GIỮ NGUYÊN vì có `data` của lượt audit của người review (không xóa); hết hạn khi Owner/Brain xong rồi dispose qua helper. Epoch ordinary hop 2 tại `epoch-20261029T090000Z-03aaa09` (chuỗi mới sau rebaseline `owner-direct-20261029-cho-phep-lam-di-014`); commit docs này không kèm hop. Phát hành/đổi version/push thuộc Owner.

## Source, candidate và evidence

- 0.1.14: tag `v0.1.14` → `002035a`; Setup `902a32868de92ecf85a605f655d0de8dba67bd64cbc0e33a9e70d4bc762e0c27`; exe `c92d992dc4247ac5e515eb8e281438a119d560f1dcbc2e139eebb58d77fb2c1d`; 15 asset khớp (tên/kích thước/sha256). 0.1.13: tag `v0.1.13` → `9b2c05e`; Setup `ab06e365310ea15d4b9dc48bb2e337c9fb8c51fdc1c5beb12f2ea930b740383d`. Setup 0.1.13 đang ở `DEV_RUN/release-0.1.13/Setup.exe` (OWNER_TEST_PENDING, file của Owner: không xóa). Bản cài Desktop `vntextapp` của người kiểm thử mang file override updater ngoài payload Setup chính thức: cấu hình theo ngữ cảnh, không phải lỗi Setup; nguồn gốc không có bằng chứng được theo dõi.
- Gate 0.1.14: `test_wpf_workflow` 23 (`002035a`), Python 20 + epoch 3 (`e6b2efa`), traceability/cancel/worker_tasks reuse từ `9b2c05e`; release-verify, hai smoke, updater 3 ca trên p14b; native p14a/p14b có mục tiêu PASS (ledger). Wrapper REVIEW_REQUIRED tách khỏi child exit 0.
- Owner quyết #4 (2026-10-27): "Cho quét tĩnh chỉ để xuất review-only; MAIN rỗng, không dịch/patch, luôn PARTIAL (khuyến nghị)" (CONTRACTS). Source `db0e847` + `4809077`; native p13o xác nhận: 0 MAIN / 8 review PARTIAL, không ID/proof, Translate/Patch bị khóa (`native47-review-result.json`). Receipt native: `native47-*`, `native48-sdk-result.json`, `native22-*.json`, `native13_prep.json`, `native13_watch.ps1` (chỉ đọc).
- Receipt prefix `C:\v\DEV_RUN\gatec`: native10-s13n-result.json, native11-s13n-result.json, native45-s13n-partial.json, native12-13-s13n-root.json, native13-s13n-cancel1.json. Bảng ledger tóm tắt giới hạn; history/index chỉ tra khi cần.

## Git/epoch và cleanup

- Git: `main` = commit docs sau `002035a` (tag `v0.1.14` giữ ở `002035a`); epoch release-0.1.14 gắn `002035a` (chuỗi 0.1.13→0.1.14 đã handoff thường, không rebaseline). Docs-only không biến evidence thành PASS exact-HEAD.
- Checkpoint riêng đã cũ: `DEV_RUN/gatec/cleanup_phase_root_checkpoint.json`; KHÔNG ghi đè trạng thái mới ở đây bằng checkpoint cleanup cũ. Trong transaction mới có thể ghi operational delta vào receipt ignored được chỉ rõ, cập nhật tracked ở boundary đã có; không docs→epoch→docs loop.
- Cleanup (sau publish 0.1.14, qua registry, đọc lại): đã dispose p14b, s14b, fx14 và hai source clone; giữ baselines (0.1.8–0.1.13 + 0.1.7), inputs, fixtures 0.1.13 cho route bản kế tiếp (rà lại khi bắt đầu bản kế tiếp). Budget cuối: non-exempt 6,364,885,116 / 8,589,934,592 B. 29 root TEST_RUN lịch sử còn câu hỏi ownership, không phải release gate.

## Tra cứu

- [INDEX](docs/INDEX.md): toàn bộ tài liệu theo chủ đề/trạng thái; [WORKFLOW](docs/WORKFLOW.md): bootstrap/checkpoint/compact/history/cleanup.
- [CONTRACTS](CONTRACTS.md): invariant/authority theo mục; [TEST_MATRIX](TEST_MATRIX.md): gate theo vùng; [ARCHITECTURE](ARCHITECTURE.md): owner/source.
- [Release0.1.13](docs/RELEASE_0.1.13.md): current acceptance; [history](docs/history/RELEASE_0.1.13.md): chronology cũ, không task mới. Không tự đọc mọi tài liệu để resume.
