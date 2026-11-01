# Current checkpoint — 2026-11-01

## Authority và bước tiếp theo

- Release 0.1.14 ĐÃ PHÁT HÀNH và bất biến: tag `v0.1.14` → `002035a4a523fb09a538dc0f20879c6cffc186c9` ([release](https://github.com/CaLanh24/VnText/releases/tag/v0.1.14)); Setup `902a32868de92ecf85a605f655d0de8dba67bd64cbc0e33a9e70d4bc762e0c27`; 15 asset. Ledger [0.1.14](docs/RELEASE_0.1.14.md), [0.1.13](docs/RELEASE_0.1.13.md).
- Release 0.1.15 ĐÃ PHÁT HÀNH (2026-11-01): [release](https://github.com/CaLanh24/VnText/releases/tag/v0.1.15), tag `v0.1.15` → `4326abd56d8d64e8c9024ca499d68303aa31db67`, Setup `fc98d13fea08de94cf6cffe611f6f37787ddb2691bb1c1e3974af263fa861694`, 17 asset. Quyền Owner đã dùng; không còn quyền publication mở. Native: Setup GUI PASS + updater GitHub UI LIVE PASS (Brain, có phạm vi).
- **Authority hiện hành (Owner 2026-11-01):** “Cho phép, lên 0.1.15 rồi kiểm Setup/updater và release luôn đi. Xong nhớ clean up. đừng dừng lại cho đến khi release.” Cho phép version 0.1.15, tải/cài tiên quyết trên bản sao đã đăng ký, kiểm Setup/updater, publication SAU KHI Brain ACCEPT (Brain làm bước accept/publication), đọc lại sau phát hành và dọn tài nguyên sở hữu. Không cài vào Desktop/game Owner; không đổi model/engine/guard. Ledger: [0.1.15](docs/RELEASE_0.1.15.md).
- QA fixed11 ĐÃ ACCEPT (Brain/QA receipt `VNTextReviewTools/fixed11-qa/receipt.json`: R1–R4 LIVE PASS có phạm vi, không finding mới); EXE `740ad632b1b29c7da7821065f292df39d1865d36c1cb3917806afaf6c1185355`, payload source `bb5c3557d727e906ff5714ef73944ad20f73cfb2`. Hành vi đã chấp nhận bị đóng băng, không polish thêm.
- Brain Codex `01a17d30-bc24-7940-a814-f172fe463e3e`; Claude DEV cố định `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26` là sole writer; Claude DEV là sole writer (không còn writer khác).
- NEXT: Task DEV tài nguyên/SDK/OCR/Setup (Owner 2026-11-01..02) đã xong phía source + test + build; chờ Brain NATIVE accept (checklist `DEV_RUN/gatec/native-checklist-resources-dev15.md`). Claude DEV là sole writer trở lại (Codex tạm đã trả ở clean `cdd882d`). Source cuối `96269da` (commit trước docs); không push/release/tag/version. Lỗi SDK trong ảnh chụp KHÔNG phải transport: SDK 8.5.3 tải/cài OK (log app); nguyên nhân là quét UI tĩnh nạp cả `renpy/**` (engine) thành ứng viên game → symmetry gate (đúng) từ chối. Đã loại framework `renpy/**` khỏi ứng viên, guard sở hữu không đổi, có test ép dòng engine vào MAIN vẫn bị từ chối. Setup có wizard tuần tự (thư mục cài → Start Menu → lối tắt desktop → Ready Back/Install → tiến trình → Hoàn tất + mở app) VI/EN, giữ safe-path/hash/atomic/data/updater guard; lối tắt chỉ tạo khi chọn, ghi `data/shortcuts.json`, gỡ cài chỉ xóa lối tắt đã ghi và còn trỏ đúng app. Build DEV: `DEV_RUN/resources-dev15/VNText.Studio.App.exe` sha256 `173b6acf0bd40027642f28cb297237e62a37604be83a37f28df49fb282e96d2d` (dùng Start-DEV.cmd). Gate: focused 241 test PASS ở `5d1e61d` + Setup/resources 18 PASS ở `96269da`; cleanup verdict RIÊNG: REVIEW_REQUIRED do mốc terminal 1 GiB (đo 2.95 GB gồm epoch history 1.77 GB bắt buộc + candidate DEV); native GUI NOT PROVEN. Epoch `epoch-20261102-devresources-wiz3-96269da` (task `dev-resources-0.1.15`, hop thường 4/8, không rebaseline mới); commit docs này làm HEAD lệch epoch (docs lag, không dùng hop). Task mới cần Owner/Brain giao.

## Source, candidate và evidence

- Public 0.1.14: source `002035a`, exe `c92d992dc4247ac5e515eb8e281438a119d560f1dcbc2e139eebb58d77fb2c1d`. 0.1.13: tag `v0.1.13` → `9b2c05e`, Setup `ab06e365310ea15d4b9dc48bb2e337c9fb8c51fdc1c5beb12f2ea930b740383d`; Setup 0.1.13/0.1.14 của Owner ở `DEV_RUN/release-0.1.13|14/Setup.exe` là file của Owner, không xóa.
- Candidate test-only: `DEV_RUN/style-fixed11-0.1.14` (QA ACCEPT) và `style-fixed10-0.1.14` giữ cho đến khi Brain/Owner đóng; dữ liệu audit `DEV_RUN/style-fixed*-audit-data-014` giữ nguyên. Gate fixed11: `test_wpf_workflow` + authority 014 = 37 test PASS tại `b7d4089`.
- Owner quyết #4 (2026-10-27): quét tĩnh chỉ xuất review-only, MAIN rỗng, luôn PARTIAL (CONTRACTS). Bản cài Desktop `vntextapp` của người kiểm thử có file override updater ngoài payload Setup chính thức: cấu hình theo ngữ cảnh, không phải lỗi Setup.

## Git/epoch và cleanup

- Epoch hiện hành `epoch-20261102-devresources-wiz3-96269da` (task DEV `dev-resources-0.1.15`, scope `DEV_RUN/resources-dev15`, trần 3 GiB, hop thường 4/8; rebaseline metadata duy nhất của Owner `call_d07908f4c24b4411b3e2a35c409d6634` ĐÃ DÙNG, không còn). Release 0.1.15 đã đóng và bất biến. Tránh vòng docs→epoch: docs chỉ commit ở boundary terminal.
- Cleanup (2026-11-01): baseline/artifact cũ đã dispose có đăng ký theo quyền Owner; dữ liệu user, Setup Owner 0.1.13/0.1.14, audit data, Desktop, Git, `.dev-env` giữ nguyên (hash 349 file khớp trước/sau). Epoch history 1.77 GB là chuỗi bắt buộc, giữ. Mục tiêu ≤ 1 GiB: REVIEW_REQUIRED đo được (2.47 GiB), chi tiết ở ledger.

## Tra cứu

- [INDEX](docs/INDEX.md): toàn bộ tài liệu theo chủ đề/trạng thái; [WORKFLOW](docs/WORKFLOW.md): bootstrap/checkpoint/compact/history/cleanup.
- [CONTRACTS](CONTRACTS.md): invariant/authority theo mục; [TEST_MATRIX](TEST_MATRIX.md): gate theo vùng; [ARCHITECTURE](ARCHITECTURE.md): owner/source.
- [Release 0.1.15](docs/RELEASE_0.1.15.md) đang chuẩn bị; [0.1.14](docs/RELEASE_0.1.14.md), [0.1.13](docs/RELEASE_0.1.13.md): current acceptance. Không tự đọc mọi tài liệu để resume.
