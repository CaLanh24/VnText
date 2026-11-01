# Current checkpoint — 2026-11-01

## Authority và bước tiếp theo

- Release 0.1.14 ĐÃ PHÁT HÀNH và bất biến: tag `v0.1.14` → `002035a4a523fb09a538dc0f20879c6cffc186c9` ([release](https://github.com/CaLanh24/VnText/releases/tag/v0.1.14)); Setup `902a32868de92ecf85a605f655d0de8dba67bd64cbc0e33a9e70d4bc762e0c27`; 15 asset. Ledger [0.1.14](docs/RELEASE_0.1.14.md), [0.1.13](docs/RELEASE_0.1.13.md).
- Release 0.1.15 ĐÃ PHÁT HÀNH (2026-11-01): [release](https://github.com/CaLanh24/VnText/releases/tag/v0.1.15), tag `v0.1.15` → `4326abd56d8d64e8c9024ca499d68303aa31db67`, Setup `fc98d13fea08de94cf6cffe611f6f37787ddb2691bb1c1e3974af263fa861694`, 17 asset. Quyền Owner đã dùng; không còn quyền publication mở. Native: Setup GUI PASS + updater GitHub UI LIVE PASS (Brain, có phạm vi).
- **Authority hiện hành (Owner 2026-11-01):** “Cho phép, lên 0.1.15 rồi kiểm Setup/updater và release luôn đi. Xong nhớ clean up. đừng dừng lại cho đến khi release.” Cho phép version 0.1.15, tải/cài tiên quyết trên bản sao đã đăng ký, kiểm Setup/updater, publication SAU KHI Brain ACCEPT (Brain làm bước accept/publication), đọc lại sau phát hành và dọn tài nguyên sở hữu. Không cài vào Desktop/game Owner; không đổi model/engine/guard. Ledger: [0.1.15](docs/RELEASE_0.1.15.md).
- QA fixed11 ĐÃ ACCEPT (Brain/QA receipt `VNTextReviewTools/fixed11-qa/receipt.json`: R1–R4 LIVE PASS có phạm vi, không finding mới); EXE `740ad632b1b29c7da7821065f292df39d1865d36c1cb3917806afaf6c1185355`, payload source `bb5c3557d727e906ff5714ef73944ad20f73cfb2`. Hành vi đã chấp nhận bị đóng băng, không polish thêm.
- Brain Codex `01a17d30-bc24-7940-a814-f172fe463e3e`; Claude DEV cố định `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26` là sole writer; không còn quota/Codex tạm writer, không writer khác.
- NEXT: Không có việc DEV mở. Release 0.1.15 hoàn tất và ACCEPT; cleanup baseline/artifact cũ (Owner 2026-11-01) đã làm: non-exempt 6.96 → 2.47 GiB, 129,945 → 8,499 mục; phần dư là chuỗi epoch bắt buộc (1.77 GB) + Setup Owner 0.445 GB + evidence được trích dẫn — xem ledger 0.1.15. Bản build tuyến update sau này dựng lại baseline từ Setup/update công khai theo công thức giữ trong `RELEASE_RUN/candidate-0.1.13/baselines/public-*`. Task mới cần Owner/Brain giao.

## Source, candidate và evidence

- Public 0.1.14: source `002035a`, exe `c92d992dc4247ac5e515eb8e281438a119d560f1dcbc2e139eebb58d77fb2c1d`. 0.1.13: tag `v0.1.13` → `9b2c05e`, Setup `ab06e365310ea15d4b9dc48bb2e337c9fb8c51fdc1c5beb12f2ea930b740383d`; Setup 0.1.13/0.1.14 của Owner ở `DEV_RUN/release-0.1.13|14/Setup.exe` là file của Owner, không xóa.
- Candidate test-only: `DEV_RUN/style-fixed11-0.1.14` (QA ACCEPT) và `style-fixed10-0.1.14` giữ cho đến khi Brain/Owner đóng; dữ liệu audit `DEV_RUN/style-fixed*-audit-data-014` giữ nguyên. Gate fixed11: `test_wpf_workflow` + authority 014 = 37 test PASS tại `b7d4089`.
- Owner quyết #4 (2026-10-27): quét tĩnh chỉ xuất review-only, MAIN rỗng, luôn PARTIAL (CONTRACTS). Bản cài Desktop `vntextapp` của người kiểm thử có file override updater ngoài payload Setup chính thức: cấu hình theo ngữ cảnh, không phải lỗi Setup.

## Git/epoch và cleanup

- Epoch 0.1.14 hiện tại `epoch-20261101-fixed11-014-bb5c355` (đã tiêu thụ 3 quyền rebaseline 0.1.14; không còn). Release 0.1.15 dùng chuyển thường sang epoch 0.1.15, không kế thừa rebaseline cũ, giữ 8 hop/CAS. Tránh vòng docs→epoch: docs chỉ commit cùng đợt hoặc ở boundary terminal.
- Cleanup (2026-11-01): baseline/artifact cũ đã dispose có đăng ký theo quyền Owner; dữ liệu user, Setup Owner 0.1.13/0.1.14, audit data, Desktop, Git, `.dev-env` giữ nguyên (hash 349 file khớp trước/sau). Epoch history 1.77 GB là chuỗi bắt buộc, giữ. Mục tiêu ≤ 1 GiB: REVIEW_REQUIRED đo được (2.47 GiB), chi tiết ở ledger.

## Tra cứu

- [INDEX](docs/INDEX.md): toàn bộ tài liệu theo chủ đề/trạng thái; [WORKFLOW](docs/WORKFLOW.md): bootstrap/checkpoint/compact/history/cleanup.
- [CONTRACTS](CONTRACTS.md): invariant/authority theo mục; [TEST_MATRIX](TEST_MATRIX.md): gate theo vùng; [ARCHITECTURE](ARCHITECTURE.md): owner/source.
- [Release 0.1.15](docs/RELEASE_0.1.15.md) đang chuẩn bị; [0.1.14](docs/RELEASE_0.1.14.md), [0.1.13](docs/RELEASE_0.1.13.md): current acceptance. Không tự đọc mọi tài liệu để resume.
