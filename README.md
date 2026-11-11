# VNText Studio


Tải bản đã phát hành tại [**GitHub Releases**](https://github.com/CaLanh24/VnText/releases/latest). Từ 0.1.17, bộ cài có tên `VNTextStudio-<phiên bản>-Setup.exe`; các bản cũ giữ tên tệp cũ. Phiên bản mã nguồn hiện tại: 0.1.18 (bản công khai mới nhất vẫn là bản trên trang Releases cho tới khi 0.1.18 được phát hành).

Đã cài VNText: mở **Cài đặt → Giới thiệu → Kiểm tra cập nhật**. Người mới tải bộ cài từ trang Releases.

## Không gian trọn quy trình để Việt hóa game trên Windows

VNText Studio giúp bạn nhận diện game, lấy văn bản, tạo bản dịch nháp tiếng Việt offline và đóng gói patch. Tuyến cài/gỡ được hỗ trợ có thể thao tác trực tiếp trên thư mục game, sao lưu từng file và kiểm hash; không cần nhân bản cả game.

## Điểm nổi bật

- **Nhận diện game và chọn quy trình phù hợp**: ứng dụng kiểm tra cấu trúc dự án trước khi bắt đầu.
- **Lấy văn bản có tổ chức**: tạo workspace và CSV, đồng thời giữ thông tin cần thiết để đưa bản dịch trở lại đúng vị trí.
- **Dịch ngay trên máy**: nội dung game được xử lý trong ứng dụng, không cần gửi lên dịch vụ dịch thuật đám mây.
- **Biên tập và rà soát trong ứng dụng**: tìm kiếm, lọc theo trạng thái và chỉnh sửa trực tiếp trong bảng CSV.
- **Làm việc với CSV**: nhập hoặc xuất CSV để dùng Excel và công cụ quen thuộc, vẫn giữ key, placeholder, tag, biến và xuống dòng.
- **Thuật ngữ nhất quán**: thêm danh sách thuật ngữ cho từng gói dịch để tên riêng và cách gọi được dùng ổn định.
- **Patch có kiểm tra**: ứng dụng kiểm tra dữ liệu, sao lưu từng file bị thay đổi và xác minh kết quả cài/gỡ.
- **Cập nhật trong ứng dụng**: kiểm tra phiên bản mới ngay trong app khi có bản cập nhật phù hợp.

## Engine hiện được hỗ trợ

### Ren’Py

Đây là luồng hoàn thiện hơn hiện tại cho các dự án dùng mã nguồn rời: có thể lấy và patch lời thoại hoặc chuỗi văn bản, sau đó tạo lớp bản dịch để đưa vào thư mục game. Dự án chỉ có thể tiếp tục khi cấu trúc và tệp nguồn phù hợp; game chỉ có tệp đã biên dịch có thể cần xem lại hoặc chưa dùng được.

### Unity

Hỗ trợ các cấu trúc và asset Unity phù hợp, gồm những dạng văn bản đã có đủ thông tin để xác định vị trí và kiểm tra lại sau khi ghi. Khả năng tương thích đang tiếp tục mở rộng theo từng cấu trúc game.

## Quy trình sử dụng

1. Tải và chạy [Setup từ GitHub Releases](https://github.com/CaLanh24/VnText/releases).
2. Cài ứng dụng trên Windows, chuẩn bị tài nguyên trong **Cài đặt → Dữ liệu**, rồi chọn thư mục game.
3. App tự nhận diện engine; chọn **Lấy text** để tạo gói văn bản.
4. **Dịch trong ứng dụng** hoặc xuất, chỉnh sửa rồi nhập CSV lại.
5. Rà soát bản dịch, thêm thuật ngữ nếu cần, rồi chọn **Patch**.
6. Với gói có installer, chọn thư mục game để cài/gỡ, rồi chạy game kiểm tra kết quả. Giữ các file sao lưu cho đến khi gỡ patch.

## Lưu ý

Khả năng tương thích tùy cấu trúc từng game. Đọc preflight và phạm vi chưa hỗ trợ trước khi cài. Bản dịch offline là bản nháp thô, vẫn có thể sai nghĩa, thành ngữ hoặc văn phong; bạn có thể chỉnh trong CSV trước khi đóng gói.

[Giấy phép](LICENSE)
