# Vận hành agent và lưu trữ lịch sử

Quy tắc chi tiết được chuyển từ AGENTS.md tại commit `b7e842419bef`; [AGENTS.md](../AGENTS.md) là điểm vào bắt buộc. Chỉ đọc mục cần dùng. Chỉ thị Owner mới nhất ưu tiên hơn snapshot/quy tắc cũ được nạp lại; snapshot không phải một quyết định mới. Không tự thay model/effort.

## Luồng tiếp tục tối thiểu

1. Đọc AGENTS và AI_STATE; xác nhận quyền/mục tiêu, writer, Git và đúng candidate.
2. Tìm chủ đề trong INDEX; chỉ đọc contract/gate cần cho thao tác kế tiếp.
3. Đọc delta DEV/receipt từ cursor; không đọc lại transcript hay toàn bộ ledger.
4. Khép một acceptance cụ thể, cập nhật checkpoint/receipt nhỏ; giữ verdict và SHA thật.

## Phân lớp trạng thái và lịch sử

| Lớp | Nơi lưu | Cách đọc/cập nhật |
|---|---|---|
| Quy tắc vận hành | AGENTS và tài liệu này | Thay rule cũ khi Owner đổi; không nhân bản vào từng report |
| Invariant/gate | CONTRACTS, TEST_MATRIX theo mục | Source/tests kiểm chứng; quyết định Owner xác định authority |
| Trạng thái đang làm | AI_STATE | Một bản hiện hành, không nối nhiều đoạn “supersedes below” |
| Acceptance task hiện tại | Ledger được AI_STATE trỏ tới | Checklist hiện tại, receipt pointer, phạm vi và phần còn thiếu |
| Lịch sử task/chủ đề | docs/history và ledger có ngày | Tra từ INDEX theo câu hỏi/ID; không tự tiếp tục quyền/task cũ |
| Raw/tool events | Log/receipt ngoài Git và cursor DEV | Đọc đoạn/trường cần thiết; cleanup bulk theo lifecycle |

AI_STATE hướng tới 1.500 từ/12 KiB; gói phục hồi thông thường gồm AGENTS + AI_STATE + các đoạn liên quan, không đọc toàn INDEX/ledger/history. Ledger hiện tại hướng tới 16 KiB; nếu vượt vì chronology, chuyển phần đã khép sang history một lần, giữ checklist/contract còn hiệu lực và liên kết. Đây là mục tiêu tổ chức, không là guard quota mới và không được cắt bỏ authority hoặc evidence thiết yếu.

Khi chuyển lịch sử: giữ nguyên nội dung evidence/SHA/verdict, ghi origin và commit trong INDEX; chỉ rebase link tương đối để điều hướng đúng khi chuyển chỗ; không sửa archive để nó trông như kết quả hiện tại. Đường dẫn tương đối dùng để điều hướng trong archive được rebase theo vị trí mới; kiểm chứng diff với blob gốc để bảo đảm chỉ đổi link, không đổi evidence.
Liên kết được dùng để điều hướng phải resolve tới vị trí thật; anchor cũ ở landing page chỉ là compatibility pointer tới archive. Không replay archive để bootstrap. Không dùng số dòng làm giới hạn output: bảng dài/JSON phải chọn field/range.

Checkpoint sau compaction cần goal/authority/exclusions, sole writer/DEV ID/cursor, candidate/source, acceptance đã đạt/còn thiếu, receipt và một bước kế tiếp. Tự compact khi runtime hỗ trợ và cần thiết; không có ngưỡng %/số phase tạo session mới. Chỉ bàn giao tuần tự khi Owner yêu cầu hoặc phục hồi đã thất bại có bằng chứng. Không giả vờ có công cụ compact; thiếu công cụ thủ công không tự buộc đổi Brain.

Không commit checkpoint sau mỗi tool call. Khi epoch đang active, ghi delta tạm trong receipt ignored được AI_STATE trỏ rõ; gom cập nhật tracked ở boundary docs/source có sẵn trước activation tiếp theo. Không tạo vòng docs → epoch → docs. Với task `release-0.1.17` đã được Owner cho phép, các hop epoch thông thường cùng task/scope/budget chạy liên tục theo chính sách standing (CONTRACTS.md) — không còn hạn mức 8 hop; CAS, lịch sử, sạch/descendant, rollback vẫn bắt buộc, và đổi budget/scope/task/quyền vẫn cần Owner. Không chạy lại gate hợp lệ chỉ vì tổ chức tài liệu.

## Quy tắc chi tiết theo chủ đề

Đọc đúng mục khi cần; phạm vi lịch sử trong các mục không cấp quyền mới.

| Chủ đề | Tài liệu |
|---|---|
| Quyền quyết định và điều phối | [coordination.md](workflows/coordination.md) |
| Owner workflow (2026-10-28) | [dev-lifecycle.md](workflows/dev-lifecycle.md) |
| Bootstrap và bằng chứng | [bootstrap.md](workflows/bootstrap.md) |
| Ngữ cảnh và phục hồi Coordinator | [context.md](workflows/context.md) |
| Computer Use lifecycle | [native-lifecycle.md](workflows/native-lifecycle.md) |
| Quy tắc workspace và đường dẫn | [workspace.md](workflows/workspace.md) |
| Invariants sản phẩm | [product.md](workflows/product.md) |
| Git, dữ liệu và artifacts | [git-data.md](workflows/git-data.md) |
| Cleanup và retention | [cleanup.md](workflows/cleanup.md) |
| Release và cập nhật | [release.md](workflows/release.md) |

Ghi chú bridge dành riêng cho Codex (`read_agent`/`functions.exec`) đã chuyển sang [history/WORKFLOW_codex_bridge.md](history/WORKFLOW_codex_bridge.md).

## Bằng chứng theo hành trình, không theo game

Quy tắc dữ liệu game ở AGENTS.md. Công cụ: `tests/tools/journey_check.py` (hành trình quét → lấy text → quét ảnh → patch → cài trên bản link → gỡ → so hash, có ngân sách thời gian và phát hiện đứng; nhãn ẩn danh), `vntext/bug_report.py` (gói báo lỗi ẩn danh) và `tests/tools/synth_from_report.py` (dựng layout giả từ gói báo lỗi để tái hiện). Release receipt chỉ ghi nhãn ẩn danh, số mục đã chạy và phần chưa chạy.

Gói tới qua nút 'Gửi báo lỗi' (kênh Discord, xem [REPORT_WEBHOOK](REPORT_WEBHOOK.md)) hoặc GitHub Issues: Owner tải zip về và báo Brain đường dẫn, Brain chuyển DEV. DEV đọc `report.json` (structure: khối Ren'Py chưa xử lý, `native_accounting` với đơn vị chưa tính đã che), chạy `python tests/tools/synth_from_report.py <zip> TEST_RUN/tmp/<nhãn>` để dựng layout giả rồi tái hiện bằng layout giả cộng dạng khối trong gói; không tải game, không ghi tên game hay nội dung vào tài liệu/receipt.
