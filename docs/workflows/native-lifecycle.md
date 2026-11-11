<!-- Origin: docs/WORKFLOW.md at 242b5a97244234a4030a2ebf10bfa91ca72317cd; original section sha256 21275f43c9494c563bceff024d16a2abfd70e6057060febc8c5702d4da2f451f. Authority preserved, latest Owner instructions prevail. -->

## Computer Use lifecycle

- Chỉ khởi tạo Computer Use ngay trước khi cần thao tác native UI thật. Khi tác vụ native kết thúc, chuyển sang kiểm tra backend, chờ, bị dừng/interrupt/usage limit, hoặc gặp lỗi, phải hủy thao tác input/capture còn pending và dispose/reset session/kernel Computer Use do task sở hữu bằng API được hỗ trợ. Đóng app không đồng nghĩa đã đóng Computer Use.
- Không để input/capture/automation loop chạy nền khi task idle, terminal hoặc đã chuyển sang phương thức khác. Khi resume sau interrupt, crash hoặc usage limit, kiểm tra session/tác vụ Computer Use mồ côi trước khi khởi tạo session mới.
- Phân biệt session/kernel của task với process tool server dùng chung. Chỉ dispose/reset resource có quyền sở hữu rõ ràng; không kill process Node/Codex dùng chung để dọn một session chưa xác định.
- Báo trạng thái dispose/reset, thao tác còn pending và process app/worker do task sở hữu trong biên bản terminal. Nếu không xác minh được ownership hoặc trạng thái, ghi `UNKNOWN` và nêu giới hạn thay vì tự kết thúc process dùng chung.

Bàn giao ngắn: đã đổi gì, đã kiểm gì trên SHA nào, acceptance còn thiếu và bước tiếp theo. Đánh giá hiệu quả theo task hoàn thành đúng acceptance, thời gian và usage/cost khi có số liệu; số test/token/child không tự là chất lượng. Chỉ đổi model/effort hoặc cơ chế điều phối khi Owner cho phép và có workload/evidence phù hợp; không suy khả năng từ tên model.
