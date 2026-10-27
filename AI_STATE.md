# Current checkpoint — 2026-10-28

## Authority và bước tiếp theo

- Release0.1.13 IN PROGRESS, publication HOLD. Owner cho hoàn thành remediation/gates/Setup/updater/publish sau Brain ACCEPT, không xin lại routine. Baseline0.1.12→0.1.13; >=0.1.13 một thao tác tới latest; pre0.1.12/Setup-origin0.1.10 ngoài scope. Giữ OPUS và giới hạn được chấp nhận, không semantic PASS. Real-game E2E deferred NOT TESTED; generated/installed native gates vẫn bắt buộc.
- Authority: Owner workflow mới (2026-10-28, AGENTS/WORKFLOW) hiệu lực: DEV sở hữu trọn task bounded, Brain review handoff có mục tiêu, không mốc giờ PM/cleanup cố định, không hard-stop 30 phút. Publication sau Brain ACCEPT không đổi.
- Brain `01a17d30-bc24-7940-a814-f172fe463e3e` (Codex, read-only review khi DEV là writer). Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3` session `76922e45-71b2-47a9-be97-cf18b927ae26` đã hồi phục quota, là sole writer (cursor sau 743). Một writer, không second DEV.
- NEXT: Brain review handoff p13o; cài p13o vào thư mục trống mới và chạy native #4/#5/#6 (Root làm UI nếu cần); các mục OPEN còn lại trên candidate mới. Chưa publish GitHub.

## Source, candidate và evidence

- Candidate hiện hành p13o, source `4809077aecf614edbe26d30ebb0c7238bb3348c0`; Setup `C:\v\RELEASE_RUN\candidate-0.1.13\p13o\release\Setup.exe` sha256 `7b28ba564fff744f5465037eb0c02a7350e120d8e27bc2c3dbb880818be6ae91`, exe cài ra `0763a42984a563de570c541998a05b404252254da0f8ef79d969ee17af476206`. p13n (source `5150fd9`, s13n) là candidate cũ, không chứa remediation #4/#6. Chi tiết ở [ledger](docs/RELEASE_0.1.13.md).
- Gate trên `4809077` (canonical, child 0, không skip/warning): focused 66 (tại `db0e847`), affected 35 + 71 + 22 gồm WPF harness; publisher, release-verify, hai smoke worker và ba ca updater đạt trên p13o (`handoff_p13o.json`). Wrapper REVIEW_REQUIRED do `terminal_root preexisting_test_run_content`, tách khỏi test. #10/#11/#12 PASS bounded (p13n); #13 PARTIAL; #4 PARTIAL, #5 NOT_PROVEN, #6 PARTIAL (chưa native trên p13o); #14/#15/#17–22 OPEN. Không Release ACCEPT.
- Owner quyết #4 (2026-10-27): "Cho quét tĩnh chỉ để xuất review-only; MAIN rỗng, không dịch/patch, luôn PARTIAL (khuyến nghị)" (CONTRACTS). Source `db0e847` + `4809077` thực thi: không SDK → 8 dòng review-only, MAIN rỗng, kể cả 0 dòng vẫn PARTIAL; lỗi SDK không bịa số review; OCR có ETA advisory. Native p13n cũ: `native4-review-result.json/png`, `native6-result.json`.
- Receipt prefix `C:\v\DEV_RUN\gatec`: native10-s13n-result.json, native11-s13n-result.json, native45-s13n-partial.json, native12-13-s13n-root.json, native13-s13n-cancel1.json. Bảng ledger tóm tắt giới hạn; history/index chỉ tra khi cần.

## Git/epoch và cleanup

- Git: source `4809077` (candidate provenance), epoch hop7 `epoch-20261028T010000Z-4809077`; fifth rebaseline đã dùng, không tự cấp mới. Commit docs-only sau đó không biến gate/candidate thành PASS exact-HEAD: reuse có giới hạn vì chỉ đổi docs; nếu guard đòi epoch thì xử lý ở native allocation. Không docs→epoch loop.
- Checkpoint riêng đã cũ: `DEV_RUN/gatec/cleanup_phase_root_checkpoint.json`; KHÔNG ghi đè trạng thái mới ở đây bằng checkpoint cleanup cũ. Trong transaction mới có thể ghi operational delta vào receipt ignored được chỉ rõ, cập nhật tracked ở boundary đã có; không docs→epoch→docs loop.
- CleanupPARTIAL: khoảng2.33GB dọn, 29historical TEST_RUN roots/oldDEVdirs còn ownership/consumer questions, không releasegate. `cleanup_phase_result.json`; consumer/review point cần được đốichiếu live. Giữ p13n/s13n, fx9/fx8 và fx2/fx10 SDK đúng consumer, baseline có route, sharedSDK/model; dọn bulk hếtconsumer theo CONTRACTS/WORKFLOW. Latest profile trước docs6,480,308,015B nonexempt,2,646,497,489B reserve; remeasure trước allocation, không coi số này là hiện tại.

## Tra cứu

- [INDEX](docs/INDEX.md): toàn bộ tài liệu theo chủ đề/trạng thái; [WORKFLOW](docs/WORKFLOW.md): bootstrap/checkpoint/compact/history/cleanup.
- [CONTRACTS](CONTRACTS.md): invariant/authority theo mục; [TEST_MATRIX](TEST_MATRIX.md): gate theo vùng; [ARCHITECTURE](ARCHITECTURE.md): owner/source.
- [Release0.1.13](docs/RELEASE_0.1.13.md): current acceptance; [history](docs/history/RELEASE_0.1.13.md): chronology cũ, không task mới. Không tự đọc mọi tài liệu để resume.
