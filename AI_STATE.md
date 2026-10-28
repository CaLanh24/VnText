# Current checkpoint — 2026-10-28

## Authority và bước tiếp theo

- Release0.1.13 IN PROGRESS, publication HOLD. Owner cho hoàn thành remediation/gates/Setup/updater/publish sau Brain ACCEPT, không xin lại routine. Baseline0.1.12→0.1.13; >=0.1.13 một thao tác tới latest; pre0.1.12/Setup-origin0.1.10 ngoài scope. Giữ OPUS và giới hạn được chấp nhận, không semantic PASS. Real-game E2E deferred NOT TESTED; generated/installed native gates vẫn bắt buộc.
- Authority: Owner workflow mới (2026-10-28, AGENTS/WORKFLOW) hiệu lực: DEV sở hữu trọn task bounded, Brain review handoff có mục tiêu, không mốc giờ PM/cleanup cố định, không hard-stop 30 phút. Publication sau Brain ACCEPT không đổi.
- Brain `01a17d30-bc24-7940-a814-f172fe463e3e` (Codex, read-only review khi DEV là writer). Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3` session `76922e45-71b2-47a9-be97-cf18b927ae26` đã hồi phục quota, là sole writer (cursor sau 743). Một writer, không second DEV.
- NEXT: Owner chưa trả lời quyền đổi OS display scale (#18) và route mạng offline (#20): chờ câu trả lời thật, không suy diễn. Brain làm native còn lại theo quy trình giảm CU; một lần thử #13 có đo bằng watcher chỉ đọc (`native13_prep.json`). Chưa publish GitHub.

## Source, candidate và evidence

- Candidate hiện hành p13o, source `4809077aecf614edbe26d30ebb0c7238bb3348c0`; Setup `C:\v\RELEASE_RUN\candidate-0.1.13\p13o\release\Setup.exe` sha256 `7b28ba564fff744f5465037eb0c02a7350e120d8e27bc2c3dbb880818be6ae91`, exe cài ra `0763a42984a563de570c541998a05b404252254da0f8ef79d969ee17af476206`. p13n (source `5150fd9`, s13n) là candidate cũ, không chứa remediation #4/#6. Chi tiết ở [ledger](docs/RELEASE_0.1.13.md).
- Gate trên `4809077` (canonical, child 0, không skip/warning): focused 66 (tại `db0e847`), affected 35 + 71 + 22 gồm WPF harness; publisher, release-verify, hai smoke worker và ba ca updater đạt trên p13o. Wrapper REVIEW_REQUIRED do `terminal_root preexisting_test_run_content`, tách khỏi test. Native p13o (bounded): #4 PASS, #6 PASS (22 ready/8 failed/0 translated, ETA thấy), #14/#15 PASS, Setup vào s13p đúng đường (#22 phần cài PASS; lần kiểm đầu `ok:false` chỉ vì Setup còn mở, chạy lại sau khi đóng, report bị ghi đè nhưng đã nêu). #5: cancel pha connect + retry tải SDK chính thức vào `s13o/data/tools` PASS bounded; cancel giữa chừng/offline NOT_PROVEN. #13 read-back cancel NOT_PROVEN (cancel tới sau verifier PASS). #19 focus ambiguous (NOT_PROVEN). #18 chờ quyền Owner, Settings launch lỗi. #20 offline/cache mở; #21 lịch sử Việt online PASS bounded (v0.1.12), cache offline mở. #22 uninstall PROVEN_BLOCKED: tool policy chặn Uninstall.exe, không vượt qua. #10/#11/#12 PASS bounded (p13n). Không Release ACCEPT.
- Owner quyết #4 (2026-10-27): "Cho quét tĩnh chỉ để xuất review-only; MAIN rỗng, không dịch/patch, luôn PARTIAL (khuyến nghị)" (CONTRACTS). Source `db0e847` + `4809077`; native p13o xác nhận: 0 MAIN / 8 review PARTIAL, không ID/proof, Translate/Patch bị khóa (`native47-review-result.json`). Receipt native: `native47-*`, `native48-sdk-result.json`, `native22-*.json`, `native13_prep.json`, `native13_watch.ps1` (chỉ đọc).
- Receipt prefix `C:\v\DEV_RUN\gatec`: native10-s13n-result.json, native11-s13n-result.json, native45-s13n-partial.json, native12-13-s13n-root.json, native13-s13n-cancel1.json. Bảng ledger tóm tắt giới hạn; history/index chỉ tra khi cần.

## Git/epoch và cleanup

- Git: HEAD `05b1e04` (docs) trước commit docs này, epoch hop8 `epoch-20261028T020000Z-05b1e04`; candidate provenance giữ `4809077`; fifth rebaseline đã dùng, không tự cấp mới. Commit docs-only không biến gate/candidate thành PASS exact-HEAD: reuse có giới hạn; không docs→epoch loop, không PASS exact-HEAD mới.
- Checkpoint riêng đã cũ: `DEV_RUN/gatec/cleanup_phase_root_checkpoint.json`; KHÔNG ghi đè trạng thái mới ở đây bằng checkpoint cleanup cũ. Trong transaction mới có thể ghi operational delta vào receipt ignored được chỉ rõ, cập nhật tracked ở boundary đã có; không docs→epoch→docs loop.
- Cleanup PARTIAL; 29 historical TEST_RUN roots/old DEV dirs còn ownership/consumer questions, không phải release gate. Tài nguyên đang giữ (RETAINED, consumer native acceptance): `s13o` (871,690,914 B gồm SDK `renpy-8.5.3` 356,359,448 B, giữ tới consumer review sau acceptance), `s13p` (install #22, policy chặn uninstall), `fx12`, `fx13`, `fx9/.../out2` (patch hoàn chỉnh, receipt trong `native13_prep.json`) và `out4` (trống), `fx6` (edit đã khôi phục từ golden), p13n/s13n. Dispose qua registry helper sau receipt được nhận; remeasure budget trước allocation (reserve gần nhất khoảng 1.31 GB).

## Tra cứu

- [INDEX](docs/INDEX.md): toàn bộ tài liệu theo chủ đề/trạng thái; [WORKFLOW](docs/WORKFLOW.md): bootstrap/checkpoint/compact/history/cleanup.
- [CONTRACTS](CONTRACTS.md): invariant/authority theo mục; [TEST_MATRIX](TEST_MATRIX.md): gate theo vùng; [ARCHITECTURE](ARCHITECTURE.md): owner/source.
- [Release0.1.13](docs/RELEASE_0.1.13.md): current acceptance; [history](docs/history/RELEASE_0.1.13.md): chronology cũ, không task mới. Không tự đọc mọi tài liệu để resume.
