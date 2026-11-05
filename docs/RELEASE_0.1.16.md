# Release 0.1.16 — ledger

Trạng thái: **ĐANG CHUẨN BỊ (chưa phát hành)**. `v0.1.15` (source `4326abd`) và mọi tag/asset cũ là bất biến, không bị đụng.

**Trạng thái hiện hành (2026-11-05):** candidate xây từ source `37640ef0d081435800501bc97ba8e143db7833e6`, 9 asset trong `RELEASE_RUN/candidate-0.1.16/setup-exact-run5/ReleaseRoot` (Setup sha256 `ca407dba…50a80c7`, hash từng file ở `C:/vnrg/evidence/release-0116-final-hashes.json`). Commit tài liệu sau đó KHÔNG phải nguồn artifact; manifest vẫn ghi `37640ef`, không relabel. Installer vá đóng gói tự chứa dùng host pack .NET 8 (`37640ef`): 4/4 PASS dưới root .NET riêng không framework chung; Setup/updater/release-verify/cleanup 168 PASS; Setup 016 VI6/EN6 và smoke đã cài PASS; updater native 0.1.15/0.1.14/0.1.13 → 0.1.16 PASS qua CLI sản phẩm kèm hộp thoại + About (receipt `native016/014/013-updater-receipt.json`). Giới hạn: baseline 014/013 không được khởi chạy; offer UI từ nguồn cục bộ NOT PROVEN (không tính PASS); tuyến 0.1.7 không chạy native. Over-peak của publisher (`publish016-run5.log`: 7,971,430,756 B > cap 6,710,886,400 B trước cleanup) được giữ nguyên làm sự cố, không nâng cap. Cleanup `REVIEW_REQUIRED` (lịch sử được bảo vệ), không waive. **Publication BỊ CHẶN**: chất lượng dịch game NOT ACCEPTED (OPUS64 32 S2 / 5 F), câu hỏi phạm vi gửi Owner đang chờ. Trạng thái chi tiết: `AI_STATE.md` và `C:/vnrg/evidence/brain-current-checkpoint.json`.

## Authority

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

