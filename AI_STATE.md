# Current checkpoint — 2026-10-27

## Authority và bước tiếp theo

- Release0.1.13 IN PROGRESS, publication HOLD. Owner cho hoàn thành remediation/gates/Setup/updater/publish sau Brain ACCEPT, không xin lại routine. Baseline0.1.12→0.1.13; >=0.1.13 một thao tác tới latest; pre0.1.12/Setup-origin0.1.10 ngoài scope. Giữ OPUS và giới hạn được chấp nhận, không semantic PASS. Real-game E2E deferred NOT TESTED; generated/installed native gates vẫn bắt buộc.
- Owner tạm dừng Brain để PM tổ chức tài liệu. PM sole docs writer; không runtime/product change. Sau validation và commit tài liệu, PM gửi lệnh rõ để cùng Brain tiếp tục; không tự tạo session. Model do Owner chọn.
- Brain hiện tại `01a17d30-bc24-7940-a814-f172fe463e3e` đã xác nhận idle/dừng, không gate/CU/pending/app/worker s13n. Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26`, last cursor661; last known idlequota429, reset từng báo22:00 Asia/Tokyo: phải kiểm live trước giao việc. Codex fallback chỉ khi quota thực còn hết, trả lại khi hồi phục; một writer.
- NEXT sau docs: xác minh Git/epoch/profile/DEV, ingest finding#4 rồi xử lý mâu thuẫn UI/contract/parser theo scope; tiếp tục native còn thiếu. Không rebuild hoặc replay gates do docs-only.

## Source, candidate và evidence

- Runtime candidate source `5150fd97d159c15456eac704f2aff337cbfd5f22`, p13n Setup tại `C:\v\RELEASE_RUN\candidate-0.1.13\p13n\release\Setup.exe`; installed `...\s13n`. Hash/receipt và bảng trạng thái tại [ledger hiện hành](docs/RELEASE_0.1.13.md). Runtime/package không bị thay bởi docs.
- Source gates79/107/22, publisher/verify/hai smoke và ba updater cases đã ghi. Cleanup/wrapper REVIEW_REQUIRED riêng. #12 PASS bounded generic8000/8000, #10/#11 PASS bounded; #13 read-back cancellation PARTIAL; #4PARTIAL/#5NOT_PROVEN; #6/#14/#15/#17–22OPEN. Không ReleaseACCEPT.
- Finding#4 mới nhất (Brain vừa xác nhận): thiếu SDK vẫn gọi loose parser; symmetry gate từ chối ba renpy_string, không CSV, UI incomplete; `DEV_RUN/gatec/native4-review-result.json` và `.png`. Đây là bằng chứng mâu thuẫn, không extraction PASS; chưa chọn remediation sản phẩm.
- Receipt prefix `C:\v\DEV_RUN\gatec`: native10-s13n-result.json, native11-s13n-result.json, native45-s13n-partial.json, native12-13-s13n-root.json, native13-s13n-cancel1.json. Bảng ledger tóm tắt giới hạn; history/index chỉ tra khi cần.

## Git/epoch và cleanup

- Docs base trước lượt tổ chức: `b7e842419beffad9ed2d8d0bc4829d69050ff3d8` main sạch, epoch hop4 đã được Brain verify; candidate source không đổi. Lượt tổ chức docs và sửa ba link archive được gom trước activation kế tiếp (không có gate/runtime change ở giữa). Trước gate kế tiếp Brain thực hiện một ordinary exact-CAS no-delete transition theo guard nếu cần để epoch khớp HEAD mới; fifth rebaseline đã dùng, không tự cấp quyền rebaseline mới. Chỉ docs commit không buộc build lại hoặc nâng evidence cũ thành exactHEAD.
- Checkpoint riêng đã cũ: `DEV_RUN/gatec/cleanup_phase_root_checkpoint.json`; KHÔNG ghi đè trạng thái mới ở đây bằng checkpoint cleanup cũ. Trong transaction mới có thể ghi operational delta vào receipt ignored được chỉ rõ, cập nhật tracked ở boundary đã có; không docs→epoch→docs loop.
- CleanupPARTIAL: khoảng2.33GB dọn, 29historical TEST_RUN roots/oldDEVdirs còn ownership/consumer questions, không releasegate. `cleanup_phase_result.json`; consumer/review point cần được đốichiếu live. Giữ p13n/s13n, fx9/fx8 và fx2/fx10 SDK đúng consumer, baseline có route, sharedSDK/model; dọn bulk hếtconsumer theo CONTRACTS/WORKFLOW. Latest profile trước docs6,480,308,015B nonexempt,2,646,497,489B reserve; remeasure trước allocation, không coi số này là hiện tại.

## Tra cứu

- [INDEX](docs/INDEX.md): toàn bộ tài liệu theo chủ đề/trạng thái; [WORKFLOW](docs/WORKFLOW.md): bootstrap/checkpoint/compact/history/cleanup.
- [CONTRACTS](CONTRACTS.md): invariant/authority theo mục; [TEST_MATRIX](TEST_MATRIX.md): gate theo vùng; [ARCHITECTURE](ARCHITECTURE.md): owner/source.
- [Release0.1.13](docs/RELEASE_0.1.13.md): current acceptance; [history](docs/history/RELEASE_0.1.13.md): chronology cũ, không task mới. Không tự đọc mọi tài liệu để resume.
