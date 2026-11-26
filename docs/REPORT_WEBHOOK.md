# Kênh nhận báo lỗi (Discord webhook)

Nút **Gửi báo lỗi** trong app tạo gói báo lỗi ẩn danh rồi mở hộp xem trước. Chỉ khi người dùng bấm **Có (Gửi)** thì gói mới được gửi tới một kênh Discord riêng của nhà phát triển. App không bao giờ tự gửi.

## Owner: tạo kênh và webhook (một lần)
1. Trong máy chủ Discord của bạn, tạo một kênh văn bản **riêng tư**, ví dụ `#vntext-bao-loi`.
2. Vào **Cài đặt kênh → Tích hợp → Webhook → Webhook mới**, đặt tên rồi **Sao chép URL webhook**.
3. Tạo tệp `%USERPROFILE%\.vntext-secrets\report_webhook.txt`, dán URL vào, đúng **một dòng**, rồi lưu.
   - Tệp phải nằm **ngoài** mọi thư mục Git. Bước dựng release kiểm điều này và bỏ qua tệp nằm trong một repo.
   - **Đừng dán URL vào chat, issue hay tài liệu.** Ai có URL đều gửi được tin vào kênh.
4. Muốn dùng tệp ở chỗ khác, đặt biến môi trường `VNTEXT_REPORT_WEBHOOK_FILE` trỏ tới tệp đó trước khi dựng release.

## Bước dựng release
`release/publish.ps1` gọi `release/embed_report_endpoint.py`:
- Tệp hợp lệ: URL được nhúng vào `app/worker/vntext/report_endpoint.bin` (đã che bằng XOR + base64). Log chỉ in `report endpoint: CONFIGURED`.
- Không có tệp, tệp rỗng, sai định dạng, nhiều dòng, hoặc nằm trong repo: bản dựng vẫn thành công nhưng **không có nút Gửi**. Log in `NOT CONFIGURED (<lý do>)`.
- Publish dừng nếu chuỗi địa chỉ webhook xuất hiện ở dạng đọc thẳng trong payload.
- URL không bao giờ được in ra log, Nhật ký, gói báo lỗi, receipt hay AI_STATE.

**Giới hạn:** việc che chỉ để địa chỉ không đọc thẳng được trong tệp cài đặt. Người có ý trích xuất vẫn lấy được, vì app phải tự giải mã để gửi. Hãy coi URL là thứ có thể lộ, và đổi nó khi bị lạm dụng.

## Gửi từ app
- **Nội dung gửi:** tệp zip của gói báo lỗi, đã ẩn danh như nút "Tạo gói báo lỗi". Kèm một tin ngắn: phiên bản app, engine, trạng thái và mức độ, số lỗi, mã cảnh báo, số khối hoặc đơn vị chưa xử lý, mã gói (16 ký tự đầu của sha256) và kích thước. Không có tên game, tên tệp, đường dẫn hay nội dung thoại. Tin không ping ai (`allowed_mentions` rỗng).
- **Giới hạn gửi:** gói tối đa 8 MB; tối đa 1 lần mỗi 60 giây và 5 lần mỗi giờ trên một máy; timeout 20 giây.
- **Thử lại và báo lỗi:** gặp lỗi mạng, 429 hoặc 5xx thì thử lại tối đa 2 lần. Lỗi 4xx khác (ví dụ webhook đã bị xóa) thì báo "kênh từ chối gói" và hướng dẫn gửi thủ công.
- **Không làm treo app:** việc gửi chạy trong một tiến trình riêng (`vntext.report_upload_cli`).

## Bị spam hoặc lộ URL: thu hồi và đổi
1. Discord → **Cài đặt kênh → Tích hợp → Webhook** → xóa webhook cũ. Mọi bản app đang có sẽ nhận lỗi 404 và hiện "kênh từ chối gói".
2. Tạo webhook mới, ghi đè URL mới vào tệp `report_webhook.txt`.
3. Phát hành bản kế tiếp; bản mới nhúng URL mới.

## Sau khi gói tới kênh
Owner tải tệp zip về rồi báo Brain đường dẫn. Cách dựng lại layout giả từ gói được mô tả trong `docs/WORKFLOW.md` (mục báo lỗi).

Phương án phụ: người dùng có thể đính kèm tệp zip vào một issue mới tại https://github.com/CaLanh24/VnText/issues/new (issue là công khai; gói đã ẩn danh).
