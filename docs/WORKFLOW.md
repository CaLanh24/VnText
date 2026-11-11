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

Khi chuyển lịch sử: giữ nguyên nội dung evidence/SHA/verdict, ghi origin và commit trong INDEX; chỉ rebase link tương đối để điều hướng đúng khi chuyển chỗ; không sửa archive để nó trông như kết quả hiện tại. Đường dẫn tương đối dùng để điều hướng trong archive được rebase theo vị trí mới; kiểm chứng diff với blob gốc để bảo đảm chỉ đổi link, không đổi evidence. Liên kết được dùng để điều hướng phải resolve tới vị trí thật; anchor cũ ở landing page chỉ là compatibility pointer tới archive. Không replay archive để bootstrap. Không dùng số dòng làm giới hạn output: bảng dài/JSON phải chọn field/range.

Checkpoint sau compaction cần goal/authority/exclusions, sole writer/DEV ID/cursor, candidate/source, acceptance đã đạt/còn thiếu, receipt và một bước kế tiếp. Tự compact khi runtime hỗ trợ và cần thiết; không có ngưỡng %/số phase tạo session mới. Chỉ bàn giao tuần tự khi Owner yêu cầu hoặc phục hồi đã thất bại có bằng chứng. Không giả vờ có công cụ compact; thiếu công cụ thủ công không tự buộc đổi Brain.

Không commit checkpoint sau mỗi tool call. Khi epoch đang active, ghi delta tạm trong receipt ignored được AI_STATE trỏ rõ; gom cập nhật tracked ở boundary docs/source có sẵn trước activation tiếp theo. Không tạo vòng docs → epoch → docs. Với task `release-0.1.17` đã được Owner cho phép, các hop epoch thông thường cùng task/scope/budget chạy liên tục theo chính sách standing (CONTRACTS.md) — không còn hạn mức 8 hop; CAS, lịch sử, sạch/descendant, rollback vẫn bắt buộc, và đổi budget/scope/task/quyền vẫn cần Owner. Không chạy lại gate hợp lệ chỉ vì tổ chức tài liệu.

## Quy tắc chi tiết được giữ nguyên

## Quyền quyết định và điều phối

Canonical topic: [Quyền quyết định và điều phối](workflows/coordination.md). Read this bounded section when applicable; historical scope does not grant new authority.

## Owner workflow (2026-10-28)

Canonical topic: [Owner workflow (2026-10-28)](workflows/dev-lifecycle.md). Read this bounded section when applicable; historical scope does not grant new authority.

## Bootstrap và bằng chứng

Canonical topic: [Bootstrap và bằng chứng](workflows/bootstrap.md). Read this bounded section when applicable; historical scope does not grant new authority.

## Ngữ cảnh và phục hồi Coordinator

Canonical topic: [Ngữ cảnh và phục hồi Coordinator](workflows/context.md). Read this bounded section when applicable; historical scope does not grant new authority.

## Computer Use lifecycle

Canonical topic: [Computer Use lifecycle](workflows/native-lifecycle.md). Read this bounded section when applicable; historical scope does not grant new authority.

## Quy tắc workspace và đường dẫn

Canonical topic: [Quy tắc workspace và đường dẫn](workflows/workspace.md). Read this bounded section when applicable; historical scope does not grant new authority.

## Invariants sản phẩm

Canonical topic: [Invariants sản phẩm](workflows/product.md). Read this bounded section when applicable; historical scope does not grant new authority.

## Git, dữ liệu và artifacts

Canonical topic: [Git, dữ liệu và artifacts](workflows/git-data.md). Read this bounded section when applicable; historical scope does not grant new authority.

## Cleanup và retention

Canonical topic: [Cleanup và retention](workflows/cleanup.md). Read this bounded section when applicable; historical scope does not grant new authority.

## Release và cập nhật

Canonical topic: [Release và cập nhật](workflows/release.md). Read this bounded section when applicable; historical scope does not grant new authority.

## Compact bridge results at the caller

For read_agent, inspect structuredContent.agent, structuredContent.latest_result and cursor before rendering any tool output. Use tests/lib/dev_projection.py (latest) for log/report projection. A missing structured result is UNKNOWN, not permission to dump text history. In functions.exec use `const r = await tools.<read_agent>(...); const d = r.structuredContent || {}; text({agent: {id:d.agent?.id,status:d.agent?.status || d.agent?.state}, latest_result:d.latest_result?.payload?.result,cursor:d.cursor});`. Pagination/history is a separate explicit diagnostic action. No shared bridge reconnect or code mutation is needed for this caller contract.
