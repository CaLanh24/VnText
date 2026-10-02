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
