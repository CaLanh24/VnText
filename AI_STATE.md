# Current checkpoint — Đã phát hành 0.1.41, 2026-11-28

**Release 0.1.41:** tag `v0.1.41` = `8a01de0ffce7c85668488156df2142ef3e4a36cf` (main + tag đã push; tag nhẹ, do `gh release create` tạo). https://github.com/CaLanh24/VnText/releases/tag/v0.1.41. Digest GitHub = local 5/5: Setup `b5855c9adb688af6528fb52a1e12989a4092d5c254a61a816d394ce6342d2ee3` (287.286.272 B); full update `559f8674…`; from-0.1.40 `4c05b340…`; hai `-current.json`. Cập nhật 0.1.40→0.1.41: 7341 tệp, 0 lệch; app đã cập nhật hiện 'Cập nhật thành công v0.1.41'.
**Nội dung:** chỉ chữ/trình bày (rà soát UX ngoài của 0.1.39/0.1.40): trang Dịch ảnh bằng tiếng Việt thường, dòng tiến độ dịch dở nêu từng số đếm (bỏ số 0, bỏ 'Bước n/3'), Cài đặt ('Lỗi thành phần', nút 'Cài bộ dịch', một thông báo gộp), log cũ '── stale ──' chỉ đổi khi hiển thị, từ vựng thống nhất. Test: `tests/unit/test_user_strings_0141.py`.
**Epoch:** chuỗi epoch đã hết độ sâu; Owner cho phép MỘT lần rebaseline metadata (không xóa) cho release-0.1.41 — đã dùng (epoch `epoch-20261128-083-rb-release041`), quyền hết hiệu lực. Release kế cần epoch mới theo quy trình thường.
**NOT_PROVEN:** trang Dịch ảnh bản tiếng Anh chỉ qua fixture; chưa chụp ảnh 'Dịch một phần' trên UI thật; module WPF harness chỉ xanh với `VNTEXT_WPF_FIXTURE_OFFSCREEN=1` trên phiên chậm này; thư mục `Documents/VNText_Output/Unity_Translation_Package` (đồ thử nghiệm) đã dời sang `C:/vj/aside`.
Receipts: `TEST_RUN/agent-evidence/release-0.1.41/`.
**Trước đó:** 0.1.40 (hành trình game thật, sửa cỡ chữ, tăng tốc extract), 0.1.39, 0.1.38 — xem docs release tương ứng.

## Điều còn hiệu lực từ các checkpoint trước

- **Writer:** DEV cố định là phiên "Dev" (`local_5bb2cdc3-cfd5-4f74-b1e3-4e11d68cceb1`); Brain/PM là phiên "PM". Không writer song song.
- **Công cụ UI native:** agent-desktop v1.0.2 tại `C:/Users/VNTextDev/.codex/tools/agent-desktop/v1.0.2/agent-desktop.exe` (gọi bằng đường dẫn tuyệt đối, quy tắc ở `ROUTING.md` thư mục cha). Dùng trước Computer Use.
- **Bằng chứng theo hành trình:** `tests/tools/journey_check.py`, `vntext/bug_report.py`, `tests/tools/synth_from_report.py`; nhãn ẩn danh (`corpus-*`), không tên game.
- **Còn mở từ trước (chưa chạy):** journey Unity v22+ `--grow` thật (dừng vì RAM 8 GB); cỡ chữ Ren'Py chưa kiểm bằng mắt trong game chạy thật; tối ưu extract game rất lớn (~5 phút cho ~240 nghìn dòng); `test_renpy_roundtrip` (cổng glyph từ chối bản dịch còn CJK) chờ Owner quyết.
- **Ngân sách:** `release/budget_policy.json` giữ nguyên (1 GiB). Dọn tổng 2026-11-25 xóa 1.143 mục DISPOSABLE (0,48 GB, terminal PASS; báo cáo vẫn REVIEW_REQUIRED vì 35.491 cold-MISSING — đúng thiết kế, không chặn xóa nữa); build tạm `DEV_RUN/obj`, `*/patch_installer_publish` đã xóa. Non-exempt còn ~1,3 GB, toàn là bằng chứng (`TEST_RUN/agent-evidence` 418 MB, `artifact-registry-epochs` 454 MB, `renpy-three-game-qa` 169 MB). Owner 2026-11-26 chọn GIỮ, không rà/xóa thêm. Hệ quả: `run_with_cleanup.py` và các test tạo workspace Ren'Py từ chối chạy vì quota (≈75 test full suite, gồm `test_renpy_roundtrip`) cho tới khi có chỗ hoặc một release task cấp ngân sách tạm; gate public (`audit_gates.py --group public`) không bị ảnh hưởng.

## Dọn dự án theo audit 2026-11-25 — đã xong, commit `d8a2f6c` đã push (CI PASS)

- Đã làm: gỡ UI Python Tk/Qt/QML + PyInstaller + lock `build`/`legacy-qt` (`app.py` chỉ còn `--release-*`); xóa hàm chết; gate `test_dependency_lock_closure`; harness C# tách BLOCKED/FAIL; dọn tổng áp quy tắc cold-MISSING như dọn theo scope; docs gọn (ẩn danh tên game, bảng release trong INDEX, ngắt dòng dài, tách chữ dính); skill planning ở `.claude/skills/`; hook Impeccable chỉ chạy khi chạm tệp UI; hook `wait-guard.mjs` (ngoài repo) áp cho mọi phiên, không còn gắn ID phiên DEV (bản cũ `.bak-20261126`); Git `remote.origin.fetch` đã đặt lại (Owner 2026-11-26).
- Giữ nguyên có lý do: chuỗi duyệt quyền trong `cleanup_work_artifacts.py` (so từng chữ với epoch đã khóa); `evaluation/` (khóa hash theo đường dẫn); tokenizer thay `transformers` (lệch 3/186 bản dịch); `__all__` cho module constants (facade `import *`).
- Chưa chứng minh: Setup chưa dựng lại sau khi bỏ PyInstaller/profile build — kiểm ở release kế; khi đó tái tạo bảng dependency trong `THIRD_PARTY_NOTICES.md`.

Checkpoint cũ (0.1.21 → 0.1.26): [docs/history/AI_STATE_2026-11-25.md](docs/history/AI_STATE_2026-11-25.md).
