# Release 0.1.15 — ledger

Trạng thái: **ĐÃ PHÁT HÀNH v0.1.15** (stable/latest, source `4326abd`); updater UI live chưa chứng minh. Tag/asset `v0.1.14` (source `002035a`) bất biến.

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

## Sai lệch đã ghi nhận (cleanup)

- DEV dispose app thử `style-fixed10-0.1.14` và `style-fixed11-0.1.14` để qua trần inventory 150,000 mục khi build 0.1.15 (không đổi guard). Hành động này NẰM NGOÀI quyền bảo toàn tường minh (Owner chỉ cho phép dọn fixed8). Dữ liệu giữ ở `DEV_RUN/style-fixed10-audit-data-014` (59 file, manifest sha256 `19d8edfaa8fa7838c3ef277f183b1065a10d387a478716e87cbd1d778b501e81`) và `DEV_RUN/style-fixed11-audit-data-014` (46 file, `784f3e0356e70a144487234cf1b55d2159ad4e828c21c038312c16377a807ded`); hai app không khôi phục được trừ khi build lại từ source `9248f97` / `bb5c355`. Không dispose thêm app được bảo vệ nào; app thử 0.1.15 (`DEV_RUN/vntext-0.1.15-candidate`) và mọi audit data được giữ.
- Câu “Terminal cleanup” của ngân sách `release-0.1.15` đã khôi phục đúng quy tắc chuẩn ≤ 1 GiB (bản ghi epoch cũ với câu “pre-release level” chỉ được chấp nhận như bản ghi trước đó, cùng trần 11 GiB). Nếu lịch sử được bảo vệ không cho về ≤ 1 GiB thì cleanup ghi REVIEW_REQUIRED chính xác, không xóa tùy ý, không waive.

## Phát hành và readback (2026-11-01)

- Brain ACCEPT publication (diff không đổi UI so với fixed11 QA ACCEPT; 65 Python + 32 WPF + 2 installer đúng payload; matrix 12/12; verify + 2 smoke). Owner đã cấp quyền phát hành.
- Tag annotated `v0.1.15` → `4326abd56d8d64e8c9024ca499d68303aa31db67` (peeled, đọc lại từ remote); `main` push fast-forward `8725ddc..27354a2`. Release stable/latest: https://github.com/CaLanh24/VnText/releases/tag/v0.1.15 (không draft, không prerelease), ghi chú tiếng Việt.
- Readback GitHub: 17 asset, tên/kích thước/sha256 khớp 100% receipt (`DEV_RUN/gatec/readback-015.txt`); Setup.exe 222,514,176 B `fc98d13fea08de94cf6cffe611f6f37787ddb2691bb1c1e3974af263fa861694`; latest API trả `v0.1.15`. Bất biến 0.1.14: tag `v0.1.14^{}` vẫn `002035a`, 15 asset không đổi.
- Native Setup (Brain, Sky UI, có phạm vi): Intel terms chấp nhận, Setup GUI cài vào `C:\v\TEST_RUN\setup15-install`, hoàn tất đúng đường dẫn; exe `7d70100eac4acde9066c7f5d16e2f0217a3a389ae3805e4ac192b5081562cf05`, `app\RELEASE.json` 0.1.15 / source 4326abd, install manifest đúng; mở app, Cài đặt → Giới thiệu hiện 0.1.15, đóng bình thường, không còn process dưới thư mục cài. **Updater UI vẫn NOT PROVEN** (chờ feed công khai; Brain chạy `updater15-public014` sau publication; file `.vntext-update-source.json` đã đổi tên inert `.inert-backup`).
- Cleanup đã làm (helper có đăng ký, receipt giữ hash): `setup15-install` (`setup15-install-dispose-receipt.json`), unpack ứng dụng thử 0.1.15 (`cand015-app-dispose-receipt.json`). Cleanup còn chờ sau updater UI: `updater15-public014`, `p15a/release` (asset đã lên GitHub), baseline trees, clone nguồn, inputs; mục tiêu ≤ 1 GiB; lịch sử được bảo vệ không về được thì ghi REVIEW_REQUIRED.
