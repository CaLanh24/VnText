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

## Thứ tự phát triển Owner đã chọn (2026-10-09)

Lấy text → Sửa CSV → Patch → Dịch local cuối. Đây là thứ tự implementation/acceptance, không đổi workflow extract → translate/import CSV → patch hoặc cấp quyền chạy game. Mục hiện hành: `.scratch/extract-readiness/spec.md`, `plan.md`, `tasks.md` (Spec Kit-style docs; chưa chạy Spec Kit). Real-game campaign chỉ xét sau cả bốn mục, theo quyền riêng và CONTRACTS§10c. Detailed extraction invariants ở CONTRACTS§8, validation ở TEST_MATRIX; AI_STATE trỏ receipt hiện hành.
