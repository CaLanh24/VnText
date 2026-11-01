# Release 0.1.15 — ledger

Trạng thái: **ĐANG CHUẨN BỊ, CHƯA PHÁT HÀNH.** Tag/asset `v0.1.14` (source `002035a`) bất biến. Không push/tag/release trước Brain ACCEPT.

## Authority

Owner 2026-11-01: “Cho phép, lên 0.1.15 rồi kiểm Setup/updater và release luôn đi. Xong nhớ clean up. đừng dừng lại cho đến khi release, t sẽ k ở máy 1 thời gian.” Cấp phép version 0.1.15, tải/cài tiên quyết trên bản sao thử nghiệm đã đăng ký, kiểm Setup/updater, commit/push/tag/publication SAU KHI Brain ACCEPT, đọc lại sau phát hành và dọn tài nguyên sở hữu. Tag/asset 0.1.14 bất biến. Không cài vào Desktop/game của Owner; không đổi model/engine/guard.

## Phạm vi

Gói các sửa đã được QA native chấp nhận sau 0.1.14: F1–F7 (giao diện Patch/CSV/OCR, dịch giao diện tiếng Anh, tên truy cập sidebar), R1–R4 (hủy sửa ô CSV, tín hiệu kiểm tra lại sau Save, nhãn Delete/Journal, picker/Download/readiness) và các sửa cùng đợt. QA độc lập fixed11 ACCEPT (hash EXE `740ad632b1b29c7da7821065f292df39d1865d36c1cb3917806afaf6c1185355`, source `bb5c355`; receipt `VNTextReviewTools/fixed11-qa/receipt.json`). Hành vi đã chấp nhận được đóng băng; không polish thêm.

## Gate và candidate (exact source `4326abd56d8d64e8c9024ca499d68303aa31db67`, version 0.1.15)

- Epoch `epoch-20261101-r015-4326abd` (chuyển thường 0.1.14→0.1.15; không kế thừa rebaseline; ngân sách `release-0.1.15` 11 GiB đo được, trần item inventory 150,000 không đổi).
- Gate tại đúng SHA (runner chuẩn, child 0): Python release/Setup/updater/installer-guard/cleanup-budget 65 test PASS (+2 test patch installer chạy lại trên installer đóng gói: 2 PASS), `test_wpf_workflow` 32 PASS (gồm updater harness với A/B fixture riêng). UI không đổi so với fixed11 đã QA ACCEPT (payload app giống `bb5c355`).
- Build p15a: Setup `fc98d13fea08de94cf6cffe611f6f37787ddb2691bb1c1e3974af263fa861694` (222,514,176 B), EXE `7d70100eac4acde9066c7f5d16e2f0217a3a389ae3805e4ac192b5081562cf05`, 17 asset (Setup + 8 zip + 8 feed) khớp receipt; release-verify trên payload Setup thật + 2 smoke worker (cwd cài đặt, TEMP ngắn) exit 0.
- Updater (FullAppUpdateService, giao dịch file thật): 12/12 PASS — named 0.1.14/0.1.13/0.1.12/0.1.11/0.1.10/0.1.9/0.1.8, generic 0.1.7, health-fail rollback, interrupt recovery, tampered package, từ chối route sai baseline; `data/` và model không đổi.
- Chưa có: Setup cài thật bằng GUI, updater UI live, publication/readback (Brain; checklist `DEV_RUN/gatec/native_plan_p15a.md`). Native NOT PROVEN.
