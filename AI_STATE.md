# Current checkpoint — 2026-10-28

## Authority và bước tiếp theo

- Release 0.1.13 ĐÃ PHÁT HÀNH: [https://github.com/CaLanh24/VnText/releases/tag/v0.1.13](https://github.com/CaLanh24/VnText/releases/tag/v0.1.13) (stable, latest), source `9b2c05ea2aad8a6c9f4f1079db4138e81f153497`, Brain/Root ACCEPT trong phạm vi Owner yêu cầu. Baseline 0.1.12→0.1.13; OPUS và giới hạn được chấp nhận, không semantic PASS; real-game E2E NOT TESTED.
- Authority: Owner (2026-10-28) trao toàn quyền hoàn thành, bỏ #22 uninstall khỏi release và chốt phạm vi sửa được yêu cầu (CONTRACTS); DEV sở hữu task bounded, Brain review handoff, giảm CU (AGENTS/WORKFLOW). Việc phát hành đã xong; bản kế tiếp cần mục tiêu và quyền mới từ Owner.
- Brain `01a17d30-bc24-7940-a814-f172fe463e3e` (Codex, read-only review khi DEV là writer). Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3` session `76922e45-71b2-47a9-be97-cf18b927ae26` đã hồi phục quota, là sole writer (cursor sau 743). Một writer, không second DEV.
- NEXT: không còn việc mở của 0.1.13. Bản kế tiếp: chờ Owner đặt mục tiêu; epoch ở hop thường 2/8 của chuỗi thứ sáu (cần hop thường mới sau commit docs này trước khi dùng helper/runner).

## Source, candidate và evidence

- Phát hành: tag `v0.1.13` → `9b2c05e`; Setup `ab06e365310ea15d4b9dc48bb2e337c9fb8c51fdc1c5beb12f2ea930b740383d`; exe `0763a42984a563de570c541998a05b404252254da0f8ef79d969ee17af476206`; 13 asset khớp (tên/kích thước/sha256). Candidate cũ p13n/p13o đã dispose. Chi tiết ở [ledger](docs/RELEASE_0.1.13.md).
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
