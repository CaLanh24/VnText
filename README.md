# VNText Studio

Bản public hiện tại: **0.1.2**; source đang chuẩn bị bản cập nhật **0.1.3**.

## Không gian trọn quy trình để Việt hóa game trên Windows

VNText Studio giúp bạn nhận diện cấu trúc game, lấy văn bản, dịch và đưa bản dịch trở lại **bản sao an toàn** của game. Mọi bước nằm trong một quy trình rõ ràng để bạn dễ theo dõi từ đầu đến cuối.

## Điểm nổi bật

- **Nhận diện game và chọn quy trình phù hợp**: ứng dụng kiểm tra cấu trúc dự án trước khi bắt đầu.
- **Lấy văn bản có tổ chức**: tạo workspace và CSV, đồng thời giữ thông tin cần thiết để đưa bản dịch trở lại đúng vị trí.
- **Dịch ngay trên máy**: nội dung game được xử lý trong ứng dụng, không cần gửi lên dịch vụ dịch thuật đám mây.
- **Biên tập và rà soát trong ứng dụng**: tìm kiếm, lọc theo trạng thái và chỉnh sửa trực tiếp trong bảng CSV.
- **Làm việc với CSV**: nhập hoặc xuất CSV để dùng Excel và công cụ quen thuộc, vẫn giữ key, placeholder, tag, biến và xuống dòng.
- **Thuật ngữ nhất quán**: thêm danh sách thuật ngữ cho từng gói dịch để tên riêng và cách gọi được dùng ổn định.
- **Patch có kiểm tra**: ứng dụng kiểm tra dữ liệu, tạo bản sao lưu, áp dụng vào bản sao game và xác minh lại kết quả.
- **Cập nhật trong ứng dụng**: kiểm tra phiên bản mới ngay trong app khi có bản cập nhật phù hợp.

## Engine hiện được hỗ trợ

### Ren’Py

Đây là luồng hoàn thiện hơn hiện tại cho các dự án dùng mã nguồn rời: có thể lấy và patch lời thoại hoặc chuỗi văn bản, sau đó tạo lớp bản dịch để đưa vào thư mục game. Dự án chỉ có thể tiếp tục khi cấu trúc và tệp nguồn phù hợp; game chỉ có tệp đã biên dịch có thể cần xem lại hoặc chưa dùng được.

### Unity

Hỗ trợ các cấu trúc và asset Unity phù hợp, gồm những dạng văn bản đã có đủ thông tin để xác định vị trí và kiểm tra lại sau khi ghi. Khả năng tương thích đang tiếp tục mở rộng theo từng cấu trúc game.

## Quy trình sử dụng

1. Tải và chạy [`VNTextStudio-0.1-Setup.exe`](https://github.com/CaLanh24/VnText/releases/latest/download/VNTextStudio-0.1-Setup.exe) từ [GitHub Releases](https://github.com/CaLanh24/VnText/releases).
2. Cài ứng dụng trên Windows và chọn một bản sao game để làm việc.
3. Chọn **Extract** để nhận diện game và tạo workspace văn bản.
4. **Dịch trong ứng dụng** hoặc xuất, chỉnh sửa rồi nhập CSV lại.
5. Rà soát bản dịch, thêm thuật ngữ nếu cần, rồi chọn **Patch**.
6. Mở bản sao game để kiểm tra kết quả và giữ lại bản sao lưu.

## Lưu ý

Khả năng tương thích tùy cấu trúc từng game. Hãy thao tác trên bản sao, giữ backup và đọc kết quả kiểm tra trước khi dùng bản dịch.

[Giấy phép](LICENSE)
