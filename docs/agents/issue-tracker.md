# Issue tracker: local Markdown

Spec và ticket của dự án nằm trong `.scratch/<feature-slug>/`, chỉ trên máy
này; `.scratch/` được Git ignore. Không tự xuất bản ra GitHub hoặc gửi task.

- Spec: `.scratch/<feature-slug>/spec.md`.
- Ticket: mỗi việc một file `.scratch/<feature-slug>/issues/<NN>-<slug>.md`.
- Ghi `Status:` gần đầu ticket; khi cần ghi phụ thuộc bằng `Blocked by:`.
- Chỉ tạo hoặc đổi ticket khi Owner yêu cầu lập spec, ticket hoặc triage.
- Giữ các file này ngoài cleanup test; không coi chúng là artifact `_work`.

Việc thực thi vẫn do Active Coordinator điều phối theo `AGENTS.md`; ticket
không tự cấp quyền tạo Worker, chạy test hoặc sửa source.

## Lịch sử thứ tự phát triển Owner đã chọn (2026-10-09)

Lấy text → Sửa CSV → Patch → Dịch local cuối. Đây là thứ tự implementation/acceptance, không đổi workflow extract → translate/import CSV → patch hoặc quyền mặc định chạy game. Tại thời điểm 2026-10-09, mục cho Ren'Py native/archive/image là `.scratch/renpy-complete/spec.md`, `plan.md`, `tasks.md`; `.scratch/extract-readiness/` là hoàn tất bounded trước đó. Owner đã cho phép một lượt DEV trên bản copy đúng `Game copy/Divinity-Update2-pc` sau focused/native gates, theo quota/ownership ở CONTRACTS§10c; đây không phải Release/full-game acceptance. Detailed extraction invariants ở CONTRACTS§8, validation ở TEST_MATRIX; AI_STATE trỏ receipt hiện hành.

Trạng thái đang làm chỉ lấy từ [AI_STATE](../../AI_STATE.md); các đường dẫn .scratch và quyền game-run ở trên là lịch sử, không tự mở lại task. Chỉ mục: [INDEX](../INDEX.md).
