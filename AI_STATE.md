# Current checkpoint — Đã phát hành 0.1.39, 2026-11-27

**Release 0.1.39:** tag `v0.1.39` = `30a630a47344fa2f5105303dff9680b3aed5b52e` (main + tag đã push). https://github.com/CaLanh24/VnText/releases/tag/v0.1.39. Digest GitHub = local 5/5: Setup `f517f99ae534331392eff3bc339d8c43420079dd000c143f0474e51ca4c8ee5c` (287.283.712 B); full update `f2017c83…`; from-0.1.38 `9580305a…`; hai `-current.json`. Cập nhật 0.1.38→0.1.39: 7341 tệp khớp, 0 lệch.
**Quyền:** quyền thường trực 2026-11-25 + chỉ thị Owner 2026-11-27 (một bản gộp, bỏ số trên sidebar). Không gửi thật lên kênh Owner.
**Nội dung 0.1.39:** sửa tải model qua 'Sửa tự động'/'Cài bộ dịch' (worker offline chỉ nới lúc tải); Chấp nhận đề xuất tái kiểm tra sau lưu; chờ xem lại là cảnh báo không phải lỗi đỏ; sidebar bỏ số 1–4 (giữ thứ tự, ✓ sau tên); bỏ 'overlay/game root/ngoài CSV'; nhãn tiếng Việt mã kiểm tra MT; fixture CJK; dependency 47 gói. `docs/RELEASE_0.1.39.md`.
**Đã kiểm trên bản thật (agent-desktop):** tải model 77.490.5xx B thật bằng bản 0.1.39 đã cập nhật → 'Bộ dịch đã sẵn sàng'; tải Ren'Py 8.5.3 có kiểm hash → 'Sẵn sàng'; sidebar không số; dịch thật có xem lại 4 dòng, Chấp nhận/Bỏ qua, build, 'Gửi báo lỗi' xem trước (Không, không gửi).
**Gate:** harness WPF sạch (3 test updater chỉ chạy trong `test_wpf_workflow` 37/37); 18+6 module Python chạy riêng từng process đạt; publisher release_verify PASS (2 lần đầu tắt im ở bước [0/5], lần 3 qua, nguyên nhân chưa chứng minh).
**NOT_PROVEN / việc mở:** không có lần chạy full suite một process sạch (1708 test: ~33 lỗi phụ thuộc thứ tự do rò môi trường, từng module chạy riêng đều đạt); picker font/ảnh native (automation kẹt hộp Mở); Dịch ảnh qua UI; cỡ chữ Ren'Py trong game thật (cần game thật); hiệu năng extract rất lớn (~5 phút/240k dòng); Unity --grow; ResourceDump cần đưa vào release/ (mất cùng evidence); chưa gửi Discord thật; đường CSV có thể khác 'Nơi lưu bản dịch' khi chọn CSV ở nơi khác.
Receipts: `TEST_RUN/agent-evidence/release-0.1.39/`.
**Trước đó:** 0.1.38 (hiện dung lượng tải, nhãn MT tiếng Việt), 0.1.37 (UX ngôn ngữ thường), 0.1.35 (Gửi báo lỗi) — xem docs release tương ứng.

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
