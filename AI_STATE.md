# Current checkpoint — 2026-10-29

## Authority và bước tiếp theo

- Release 0.1.14 ĐÃ PHÁT HÀNH: [https://github.com/CaLanh24/VnText/releases/tag/v0.1.14](https://github.com/CaLanh24/VnText/releases/tag/v0.1.14) (stable, latest), source `002035a4a523fb09a538dc0f20879c6cffc186c9`, Brain ACCEPT cho phạm vi sửa lỗi báo cáo UI QA 0.1.13 (ledger [0.1.14](docs/RELEASE_0.1.14.md)); 0.1.13 ở [ledger](docs/RELEASE_0.1.13.md). Không claim QA toàn app/pixel parity/game thật; model OPUS-MT và giới hạn giữ nguyên.
- Authority: Owner đã cho chẩn đoán + sửa + release 0.1.14 (xong); bản kế tiếp cần mục tiêu và quyền mới. DEV sở hữu task bounded, Brain review handoff, giảm CU, Brain chỉ chờ theo event (AGENTS/WORKFLOW).
- Brain `01a17d30-bc24-7940-a814-f172fe463e3e` (Codex, read-only review khi DEV là writer). Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3` session `76922e45-71b2-47a9-be97-cf18b927ae26` đã hồi phục quota, là sole writer (cursor sau 743). Một writer, không second DEV.
- NEXT: Owner granted ONE additional 0.1.14 metadata rebaseline via question `call_58ba2f8e4ba1469da8255b76b2617e83`, exact reply “Cho phép một lần rebaseline 0.1.14”. Claude DEV hit quota (reset reported 19:30 Asia/Tokyo); Codex temporarily owns source writing. Prepared idle-badge/OCR worker localization + independent authority committed at `2b0a5ce`; fixed6/fixed7 and audit data preserved. Rebaseline PLAN refused `epoch_rebaseline_approval_already_consumed` before any mutation: the exact-ID history traversal reaches depth 65 and fails closed at its 64-record limit, with no occurrence of the new ID. Active epoch remains `epoch-20261029T150000Z-3ebe495`. Evidence: `DEV_RUN/gatec/rebaseline014secondplan.json`, `inspect_epoch_chain.py`; Owner approved `call_102aae7f90e74cd4ac945b49ac5ba728` exact reply “Cho phép sửa giới hạn 64→256”; now applied depth proposal `proposed-history-depth-fix.patch` raises only this traversal safety bound 64→256, preserving cycle/malformed-history refusal and all existing authorization/CAS/eight-hop checks. Approval covers only the 64→256 bound; every other guard stays. No standard gate PASS, no new build, no push/release/version/tag change. Claude idle/failed quota, cursor 982; no active owned child. Resume by resolving this bounded helper limit, then rebaseline exactly once and focused gates/candidate build.

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
