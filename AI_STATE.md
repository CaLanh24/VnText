# Current checkpoint — 2026-10-28

## Authority và bước tiếp theo

- Release0.1.13 IN PROGRESS, publication HOLD. Owner cho hoàn thành remediation/gates/Setup/updater/publish sau Brain ACCEPT, không xin lại routine. Baseline0.1.12→0.1.13; >=0.1.13 một thao tác tới latest; pre0.1.12/Setup-origin0.1.10 ngoài scope. Giữ OPUS và giới hạn được chấp nhận, không semantic PASS. Real-game E2E deferred NOT TESTED; generated/installed native gates vẫn bắt buộc.
- Authority: Owner (2026-10-28) trao toàn quyền hoàn thành release: sixth rebaseline, DPI 125/150% tạm rồi khôi phục 100%, offline tạm rồi khôi phục, retry tải SDK chính thức, sửa hiệu năng hủy trace, dọn artifact tự tạo, publish sau Brain ACCEPT (CONTRACTS). Không vượt barrier của tool/automatic review/security; #22 bàn giao người dùng. Workflow giảm CU và DEV sở hữu task bounded (AGENTS/WORKFLOW) vẫn hiệu lực. Publication chỉ sau Brain ACCEPT.
- Brain `01a17d30-bc24-7940-a814-f172fe463e3e` (Codex, read-only review khi DEV là writer). Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3` session `76922e45-71b2-47a9-be97-cf18b927ae26` đã hồi phục quota, là sole writer (cursor sau 743). Một writer, không second DEV.
- NEXT: commit authority + sửa batch trace-abort → rebaseline thứ sáu bằng receipt đầy đủ → gate focused/affected → dọn artifact tự tạo trước khi cấp phát → build candidate mới nếu gate đạt → checklist native (offline, DPI, kích thước tối thiểu, SDK giữa chừng, #13 đo lại thời gian) cho Brain. Trạng thái candidate/epoch mới nằm ở checkpoint vận hành (DEV_RUN/gatec/resume_current_checkpoint.json) cho tới commit cần thiết kế tiếp.

## Source, candidate và evidence

- Candidate hiện hành p13o, source `4809077aecf614edbe26d30ebb0c7238bb3348c0`; Setup `C:\v\RELEASE_RUN\candidate-0.1.13\p13o\release\Setup.exe` sha256 `7b28ba564fff744f5465037eb0c02a7350e120d8e27bc2c3dbb880818be6ae91`, exe cài ra `0763a42984a563de570c541998a05b404252254da0f8ef79d969ee17af476206`. p13n (source `5150fd9`, s13n) là candidate cũ, không chứa remediation #4/#6. Chi tiết ở [ledger](docs/RELEASE_0.1.13.md).
- Gate trên `4809077` (canonical, child 0, không skip/warning): focused 66 (tại `db0e847`), affected 35 + 71 + 22 gồm WPF harness; publisher, release-verify, hai smoke worker và ba ca updater đạt trên p13o. Native p13o (bounded): #4, #6, #13 (hủy read-back; terminal trễ 43,231 s), #14, #15 PASS; #5 PASS cho cancel pha connect + retry tải SDK, giữa chừng/offline chưa; #17/#18/#19 PARTIAL (dark legible, maximize/restore, Tab/Return PASS; Esc dialog, kích thước tối thiểu, 125/150% chưa); #21 online PASS; #20 chưa; #22 PROVEN_BLOCKED (policy tool). Không Release ACCEPT.
- Owner quyết #4 (2026-10-27): "Cho quét tĩnh chỉ để xuất review-only; MAIN rỗng, không dịch/patch, luôn PARTIAL (khuyến nghị)" (CONTRACTS). Source `db0e847` + `4809077`; native p13o xác nhận: 0 MAIN / 8 review PARTIAL, không ID/proof, Translate/Patch bị khóa (`native47-review-result.json`). Receipt native: `native47-*`, `native48-sdk-result.json`, `native22-*.json`, `native13_prep.json`, `native13_watch.ps1` (chỉ đọc).
- Receipt prefix `C:\v\DEV_RUN\gatec`: native10-s13n-result.json, native11-s13n-result.json, native45-s13n-partial.json, native12-13-s13n-root.json, native13-s13n-cancel1.json. Bảng ledger tóm tắt giới hạn; history/index chỉ tra khi cần.

## Git/epoch và cleanup

- Git: nguồn epoch cuối của chuỗi thứ năm là `05b1e04`; HEAD docs `958f927` làm profile ngân sách release lệch. Commit này thêm authority thứ sáu và sửa trace-abort; rebaseline thứ sáu sẽ gắn vào đúng SHA của commit này (receipt đầy đủ). Candidate provenance p13o giữ `4809077`; docs-only không biến evidence thành PASS exact-HEAD; không docs→epoch loop.
- Checkpoint riêng đã cũ: `DEV_RUN/gatec/cleanup_phase_root_checkpoint.json`; KHÔNG ghi đè trạng thái mới ở đây bằng checkpoint cleanup cũ. Trong transaction mới có thể ghi operational delta vào receipt ignored được chỉ rõ, cập nhật tracked ở boundary đã có; không docs→epoch→docs loop.
- Cleanup PARTIAL; 29 historical TEST_RUN roots/old DEV dirs còn ownership/consumer questions, không phải release gate. Tài nguyên đang giữ (RETAINED, consumer native acceptance): `s13o` (871,690,914 B gồm SDK `renpy-8.5.3` 356,359,448 B, giữ tới consumer review sau acceptance), `s13p` (install #22, policy chặn uninstall), `fx12`, `fx13`, `fx9/.../out2` (patch hoàn chỉnh, receipt trong `native13_prep.json`) và `out4` (trống), `fx6` (edit đã khôi phục từ golden), p13n/s13n. Dispose qua registry helper sau receipt được nhận; remeasure budget trước allocation (reserve gần nhất khoảng 1.31 GB).

## Tra cứu

- [INDEX](docs/INDEX.md): toàn bộ tài liệu theo chủ đề/trạng thái; [WORKFLOW](docs/WORKFLOW.md): bootstrap/checkpoint/compact/history/cleanup.
- [CONTRACTS](CONTRACTS.md): invariant/authority theo mục; [TEST_MATRIX](TEST_MATRIX.md): gate theo vùng; [ARCHITECTURE](ARCHITECTURE.md): owner/source.
- [Release0.1.13](docs/RELEASE_0.1.13.md): current acceptance; [history](docs/history/RELEASE_0.1.13.md): chronology cũ, không task mới. Không tự đọc mọi tài liệu để resume.
