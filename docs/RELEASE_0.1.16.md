# Release 0.1.16 — ledger

Trạng thái: **ĐÃ PHÁT HÀNH** — https://github.com/CaLanh24/VnText/releases/tag/v0.1.16, tag `v0.1.16` → source `de44d43fc621264f772b3e20aea807564cbcc7fa`. `v0.1.15` (source `4326abd`) và mọi tag/asset cũ là bất biến và không bị đụng.

**Phát hành (2026-11-05):** 9 asset được đọc lại từ GitHub, kích thước và sha256 khớp kho cục bộ (`C:/vnrg/evidence/publication-v0.1.16-readback.json`): `Setup.exe` (284.376.576 B, sha256 `2f9ce610…24bc`), feed + zip `current` (tuyến cũ 0.1.7) và các tuyến trực tiếp từ 0.1.15, 0.1.14, 0.1.13; `releases/latest` = v0.1.16. Chất lượng dịch là **bản nháp thô offline** (Owner chấp nhận lỗi thành ngữ/ngữ cảnh/văn phong của OPUS); lỗi do chính ứng dụng gây ra đã sửa: bước sửa sau dịch không còn ghi đè tiếng Việt đúng (do/so/in/me/men/man, ranh giới Unicode, nhánh `
` literal), placeholder trùng từ tiếng Việt (`{an}`, `{i}`, `{a}`) không còn xóa chữ, danh tính cache mang phiên bản postprocess (bản 3; bản ghi cũ miss, không xóa), dòng đã đóng băng/đã sửa tay giữ nguyên. Gate trên đúng nguồn: 352 test dịch/mt PASS (`727ca68`), 15 test publisher PASS (`de44d43`), `test_patch_installer` 4/4 PASS trên đúng byte installer đóng gói dưới root .NET riêng không có framework, smoke đóng gói PASS (model đóng gói giống từng byte bản công khai 0.1.15; cache cũ hỏng miss, placeholder/tag/newline thật và literal giữ nguyên). Wrapper canonical báo `REVIEW_REQUIRED` riêng (container installer/lịch sử được bảo vệ), không gộp thành PASS toàn gate. Native (Brain): Setup cuối cài sạch (EN, đủ các trang) và About 0.1.16 (VI); bố cục EN6/VI6 dùng lại bằng chứng ứng viên đã chấp nhận vì WPF/Setup.cs không đổi. Updater 0.1.15/0.1.14/0.1.13 → 0.1.16: biên nhận backend exit 0, canary không đổi, đọc lại 7196 file 0 lệch, health passed; tuyến 0.1.13 còn quan sát hộp thoại thành công và About 0.1.16. Baseline của giao dịch backend là payload Setup công khai GIẢI NÉN kèm file update-source do script ghi (không phải bản cài Setup). Hai app khởi động lại đầu không đóng được bằng CloseMainWindow (nhiều khả năng do hộp thoại modal); 4 process fixture của tôi (PID 13320, 6708, 1996, 11452) đã bị kết thúc — ghi nhận trung thực, không phải lỗi ứng dụng. Chưa chứng minh: gameplay của một game cụ thể (lần thử trên game gốc chỉ là cài/gỡ bằng CLI, 2 file mới, khôi phục chính xác 1433 file game + 483 file appdata; game chiếm 100% CPU trong VM render phần mềm nên computer-use timeout), lời đề nghị cập nhật công khai trực tiếp trong ứng dụng (fixture tùy chọn: `TEST_RUN/native0116/setup-015`), và ngữ nghĩa hoàn hảo. Ngân sách: các đỉnh vượt cap trong lúc publish run3 (8,89 GB), run5 (7,97 GB), run6 (6,89 GB) vẫn ghi nhận; lần publish cuối `de44d43` dưới cap (6.560.255.259 B < 6.710.886.400 B). Epoch kết thúc ở hop 8/8 (`epoch-20261105-publisher-de44d43`). Cleanup `REVIEW_REQUIRED` cho lịch sử được bảo vệ, không waive; các cleanup có phạm vi PASS. Chi tiết: `AI_STATE.md`.

## Authority

Owner2026-11-05 supersedes the earlier perfect-semantic-quality blocker:
deliver usable raw Vietnamese, free/offline, with idiom/context/style limits
left for editing or external tools. App-induced word corruption is unacceptable.
The confirmed homograph/cache and placeholder-echo defects must pass exact
packaged checks before release. Direct original-game install/uninstall testing
was explicitly authorised and completed with exact restoration; gameplay remains
NOT PROVEN. Persistent DEV hit session quota; Codex temporarily owns finishing
the same source, gates and release, without changing model or weakening guards.

Owner 2026-11-02: “nghiệm thu đi, xử lý nốt các vấn đề tồn đọng rồi release” — ghi đè lệnh “không release” trước đó; phiên bản kế tiếp suy ra là 0.1.16 (patch sau 0.1.15 công khai). Phạm vi cho phép: bump version owners, ledger/scope, gate, build candidate đầy đủ ở scope Release riêng, kiểm Setup/updater, chuẩn bị asset/ghi chú/lệnh phát hành. **Chưa push/tag/release trước khi Brain ACCEPT.** Không cài vào Desktop của Owner, không ghi game gốc, không đổi/tải model. Không ngụ ý rebaseline epoch.

## Phạm vi sản phẩm (từ 0.1.15, đã review từng gate)

- Ren'Py: extract PARTIAL chỉ vì giới hạn dự kiến vẫn patch được tập MAIN đã xác minh (`patch_gate.scoped_patch_eligible`, `patch_coverage.json`); text động không bao giờ vào MAIN/patch; no-SDK/lỗi thật vẫn chặn (CONTRACTS “Scoped patch…”).
- OCR: guard TextAngle > 2° chỉ dỡ khi ink đo độc lập nằm ngang; chữ xoay thật vẫn bị từ chối.
- Danh mục nhãn UI chuẩn khớp chính xác (glossary người dùng cao hơn); chữ IN HOA giữ placeholder/tag.
- Setup wizard (VI/EN, resources-first), journal/extract UI, cảnh báo giới hạn dạng amber.
- Khóa registry artifact dùng guard do OS giữ (không còn lock bị cướp/TOCTOU).

## Version owners đã bump (0.1.15 → 0.1.16)

`VERSION.txt`, `vntext/__init__.py`, `vntext/app_backend.py`, `release/version_info.txt`, `release/publish.ps1` (allowlist candidate/snapshot), README, `docs/INDEX.md`; tài khoản ngân sách `release-0.1.16` trong `tests/tools/cleanup_work_artifacts.py` + `run_with_cleanup.py` (id riêng `RELEASE_TASK_0116_BUDGET_ID`, không nhầm `release-0.1.6`).

## Ngân sách (đo, KHÔNG kế thừa 11 GiB hay trần DEV 3,25 GiB)

| Hạng mục | Ước tính đo |
|---|---|
| Non-exempt hiện có (đo lúc build DEV) | 3,07 GiB (3,292,380,983 B) |
| 2 hop epoch thường | ≈ 0,06 GiB |
| Baseline công khai 0.1.15 (Setup 222,514,176 B + cây giải nén ≈ 0,53 GB) | ≈ 0,75 GiB |
| Build + đóng gói candidate (p15a thực tế 285,861,447 B) | ≈ 0,3 GiB |
| Bản sao cô lập Setup/updater tại đỉnh (số đo 0.1.15) | ≈ 1,5 GiB |
| Dự phòng | 0,5 GiB |
| **Trần đề xuất `release-0.1.16`** | **6,25 GiB (6400 MiB)** |

Giá trị đã ghi trong code là **đề xuất đo được, chờ Brain/Owner xác nhận con số trước lần cấp phát đầu tiên**: chưa áp hop epoch chuyển `dev-resources-0.1.15 → release-0.1.16`, chưa tải baseline, chưa build. Thiếu so với trần hiện tại (DEV 3,25 GiB = 3.33 GB; đang dùng 3.29 GB): **≥ 2,9 GiB cấp phát mới** (6,25 − 3,25), trần terminal 1 GiB là chuyện riêng.

## Cleanup (verdict riêng, không waive)

- Phân loại lại owner epoch lịch sử: allowlist terminal giờ chấp nhận 103 thư mục epoch cũ (owner `cleanup_work_artifacts.py`, RETAINED, chuỗi đã xác minh hash) — chỉ đọc, không sửa file bất biến.
- Đã dispose qua `dispose_stale_batch` (plan có ownership proof): 12 `worker_tasks_*` rỗng, 6 thư mục rỗng release*/release-verify*, `vntext-canonical-runner-6nwxd1x5`, 6 thư mục `tmp` — receipt `DEV_RUN/gatec/dispose-stale-receipt.json`.
- Còn lại (đo, không xóa): ~15,6 MB DISPOSABLE trong `TEST_RUN/tmp` (107 mục bị giữ vì có bản ghi con không-disposable), 6 mục `TEST_RUN` gốc cũ bị chặn bởi `registered_non_disposable_descendant`, `resource-ux-native` (5 mục UNKNOWN). Lịch sử epoch ≈ 2,2 GB nên mức ≤ 1 GiB **không đạt: REVIEW_REQUIRED trung thực**.

## Gate

Dùng lại đúng mã đã review: A/B/C + khóa + WPF harness (gate g2/g3 ở `07ac5c8`/`500ecb7`, mã sản phẩm không đổi); gate mới bắt buộc ở nguồn 0.1.16: Python release/Setup/updater/installer-guard/cleanup-budget, `test_wpf_workflow` (CSV-layout fixture Disc phân biệt), updater 0.1.15→0.1.16 fullapp staging + rollback, Setup payload thật (không stand-in), release-verify + smoke worker.

## Nghiệm thu native (Brain, danh sách hữu hạn)

App folder tự phân tích → extract → CT2 → lưu CSV → patch read-back; journal wheel; bảng UI 120; About hover; cảnh báo/lỗi; Settings cô lập resource; Setup mọi trang + cài cô lập; updater cô lập giữ dữ liệu user. **Native: NOT PROVEN** tới khi Brain trả bằng chứng (desktop Disc).

## Chuẩn bị phát hành (chưa chạy)

1. Baseline: lấy cache/asset `v0.1.15` (Setup `fc98d13f…1694`), kiểm hash trước.
2. `pwsh -NoProfile -ExecutionPolicy Bypass -File .\release\publish.ps1 -SkipWpfUpdatePackage -FullAppUpdateBaselineRoot <baseline 0.1.15>` trong scope `RELEASE_RUN/candidate-0.1.16`.
3. Sau Brain ACCEPT: `git tag -a v0.1.16 <sha>`, push fast-forward, `gh release create v0.1.16` với 17 asset (Setup + zip + feed) và ghi chú tiếng Việt (tóm tắt phạm vi ở trên), readback sha256/kích thước/latest, xác nhận `v0.1.15^{}` vẫn `4326abd`.

