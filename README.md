# VNText Studio

VNText Studio hỗ trợ trích xuất văn bản để dịch game, nhập lại bản dịch và áp dụng vào **bản sao an toàn** của game. Dự án đang tập trung vào một số định dạng Unity; không phải mọi game Unity hay mọi phiên bản asset đều được hỗ trợ.

## Tải và sử dụng

Tải `Setup.exe` từ [GitHub Releases](https://github.com/Calanh24/VnText/releases). Nếu trang chưa liệt kê bản phù hợp, chưa có Setup công khai để tải. Không tải Setup từ nguồn không chính thức.

1. Cài ứng dụng, rồi mở thư mục của một bản sao game — không thử patch bản game duy nhất hoặc bản đang chơi.
2. Chọn **Extract** để tạo dữ liệu trích xuất và CSV.
3. Dịch trong ứng dụng hoặc chỉnh sửa/nhập CSV đã dịch. Giữ nguyên key, cột và cấu trúc CSV.
4. Chọn **Patch** để kiểm tra và áp dụng bản dịch. Giữ bản sao lưu riêng; không bỏ qua cảnh báo hoặc xác minh.

Khả năng trích xuất và patch phụ thuộc định dạng cụ thể của game. Kết quả Extract không bảo đảm game đó có thể patch an toàn; hãy dùng bản sao và kiểm tra game sau khi patch. Không đưa game, save, CSV riêng hoặc model tải về vào repository.

## Cập nhật và gỡ cài đặt

Ứng dụng có mã kiểm tra GitHub Releases và một luồng cập nhật giới hạn cho một số cập nhật chỉ gồm file WPF được cho phép. Cập nhật worker, runtime, installer hoặc file khác cần Setup mới. Luồng cập nhật GitHub trên một bản cài thực tế chưa được xác nhận; trong lúc chờ, hãy lấy Setup mới từ trang Releases. Không coi thư mục `Updates` cục bộ cạnh Setup là dịch vụ cập nhật công khai.

Gỡ ứng dụng bằng `Uninstall.exe` trong thư mục cài đặt. Xác nhận gỡ sẽ xóa toàn bộ nội dung trong thư mục cài, **bao gồm `data/` và dữ liệu do ứng dụng tạo**; thư mục cài còn lại nhưng rỗng. Sao lưu dữ liệu cần giữ trước khi gỡ.

## Mã nguồn và phát triển

Phiên bản source hiện tại: `0.1.0` (phiên bản file Windows `0.1.0.0`). Tag và phiên bản release thực tế được công bố trên trang Releases; phiên bản source không đồng nghĩa bản phát hành đã tồn tại.

Hướng dẫn thiết lập môi trường phát triển và các giới hạn khi chạy test nằm trong [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md). Quyền sử dụng và ghi nhận dependency được nêu trong [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); mã nguồn được cấp phép theo [LICENSE](LICENSE).
