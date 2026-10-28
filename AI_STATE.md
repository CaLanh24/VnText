# Current checkpoint — 2026-10-28

## Authority và bước tiếp theo

- Release 0.1.14 ĐANG LÀM (Owner 2026-10-28: xem báo cáo UI QA 0.1.13, đúng thì sửa rồi release). 0.1.13 đã phát hành ([v0.1.13](https://github.com/CaLanh24/VnText/releases/tag/v0.1.13), source `9b2c05e`); evidence và giới hạn của nó ở [ledger 0.1.13](docs/RELEASE_0.1.13.md). Acceptance 0.1.14, triage từng finding và kế hoạch: [ledger 0.1.14](docs/RELEASE_0.1.14.md). Publication sau Brain ACCEPT; model OPUS-MT và giới hạn giữ nguyên.
- Authority: Owner cho chẩn đoán + sửa + release 0.1.14, gồm visual bounded (backdrop/scale modal, primary fill/elevation, localization); không đổi geometry/motion freeze, hit target, command, palette, kiến trúc, model, validator (CONTRACTS). DEV sở hữu task bounded, Brain review handoff và làm native có mục tiêu; giảm CU. Budget/epoch riêng release-0.1.14, không thừa hưởng rebaseline 0.1.13.
- Brain `01a17d30-bc24-7940-a814-f172fe463e3e` (Codex, read-only review khi DEV là writer). Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3` session `76922e45-71b2-47a9-be97-cf18b927ae26` đã hồi phục quota, là sole writer (cursor sau 743). Một writer, không second DEV.
- NEXT: p14a bị từ chối (toast glossary bị blur). Sửa bằng `ModalBackdrop` → commit → hop thường → gate focused/affected → một lần build p14b → verify/smoke/updater → native có mục tiêu lần hai → Brain ACCEPT → publish. Native p14a đã PASS cho #2/#3/#4/#7/#8/#9 (ledger 0.1.14).

## Source, candidate và evidence

- 0.1.13 đã phát hành: tag `v0.1.13` → `9b2c05e`; Setup `ab06e365310ea15d4b9dc48bb2e337c9fb8c51fdc1c5beb12f2ea930b740383d`. Bản Setup đó đang giữ ở `DEV_RUN/release-0.1.13/Setup.exe` (OWNER_TEST_PENDING, file của Owner: không xóa). Bản cài Desktop `vntextapp` của người kiểm thử mang file override updater nằm ngoài payload Setup chính thức: cấu hình sai theo ngữ cảnh, không phải lỗi sản phẩm (finding 1); nguồn gốc chính xác chưa có bằng chứng được theo dõi.
- Gate: traceability 32 + cancel/readback 25 (`8c00998`, runtime giống `9b2c05e`), authority thứ sáu và worker_tasks 16 (`9b2c05e`); focused 66 và affected 35/71/22 + WPF reuse từ `4809077`; publisher, release-verify, hai smoke worker, ba ca updater đạt trên p13p. Native: #4, #6, #13 (10,818 s vs 43,231 s), #14, #15 PASS bounded; #5 PASS cho cancel pha connect + retry, giữa chừng NOT_PROVEN; #17/#18/#19/#20 PARTIAL/NOT_PROVEN ngoài release; #22 bỏ khỏi acceptance. Wrapper REVIEW_REQUIRED tách khỏi child exit 0.
- Owner quyết #4 (2026-10-27): "Cho quét tĩnh chỉ để xuất review-only; MAIN rỗng, không dịch/patch, luôn PARTIAL (khuyến nghị)" (CONTRACTS). Source `db0e847` + `4809077`; native p13o xác nhận: 0 MAIN / 8 review PARTIAL, không ID/proof, Translate/Patch bị khóa (`native47-review-result.json`). Receipt native: `native47-*`, `native48-sdk-result.json`, `native22-*.json`, `native13_prep.json`, `native13_watch.ps1` (chỉ đọc).
- Receipt prefix `C:\v\DEV_RUN\gatec`: native10-s13n-result.json, native11-s13n-result.json, native45-s13n-partial.json, native12-13-s13n-root.json, native13-s13n-cancel1.json. Bảng ledger tóm tắt giới hạn; history/index chỉ tra khi cần.

## Git/epoch và cleanup

- Git: `main` = commit docs sau `9b2c05e` (tag `v0.1.13` giữ ở `9b2c05e`); rebaseline thứ sáu ở `8c00998`, hop thường 1 ở `9b2c05e`; fifth/sixth rebaseline đã dùng, không tự cấp mới. Docs-only không biến evidence thành PASS exact-HEAD.
- Checkpoint riêng đã cũ: `DEV_RUN/gatec/cleanup_phase_root_checkpoint.json`; KHÔNG ghi đè trạng thái mới ở đây bằng checkpoint cleanup cũ. Trong transaction mới có thể ghi operational delta vào receipt ignored được chỉ rõ, cập nhật tracked ở boundary đã có; không docs→epoch→docs loop.
- Cleanup (sau publish, qua registry, đọc lại): đã dispose s13o+SDK, s13q, p13o, p13p, fx2/3/5/6/8/9/10/11/12/13; giữ baselines/inputs/fixtures/source (~3.4 GB) cho build route cập nhật bản kế tiếp (rà lại khi bắt đầu bản kế tiếp). 29 root TEST_RUN lịch sử còn câu hỏi ownership, không phải release gate. Budget cuối: non-exempt 5,523,988,924 / 9,126,805,504 B.

## Tra cứu

- [INDEX](docs/INDEX.md): toàn bộ tài liệu theo chủ đề/trạng thái; [WORKFLOW](docs/WORKFLOW.md): bootstrap/checkpoint/compact/history/cleanup.
- [CONTRACTS](CONTRACTS.md): invariant/authority theo mục; [TEST_MATRIX](TEST_MATRIX.md): gate theo vùng; [ARCHITECTURE](ARCHITECTURE.md): owner/source.
- [Release0.1.13](docs/RELEASE_0.1.13.md): current acceptance; [history](docs/history/RELEASE_0.1.13.md): chronology cũ, không task mới. Không tự đọc mọi tài liệu để resume.
