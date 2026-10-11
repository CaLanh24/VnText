# Thông báo cập nhật trong app — yêu cầu trước phát hành

## Mục tiêu và nguồn thiết kế

Owner yêu cầu ngày 2026-10-11: app có bảng thông báo khi có cập nhật mới, tham khảo ảnh Cockpit Tools đã cung cấp. Ưu tiên hoàn thiện UI/updater trong bản đang chuẩn bị, rồi phát hành trước khi thực hiện `TRANSLATION_QUALITY_PLAN.md`.

Ảnh tham khảo cho thấy các trạng thái: có bản mới với release notes, đang tải có tiến trình, sẵn sàng khởi động lại và cập nhật thành công. Đây là nguồn tham khảo UX, không phải bằng chứng updater VNText đã hoạt động. Không phụ thuộc đường dẫn ảnh/máy riêng để triển khai từ public clone.

Surface mode: Operate. Giữ WPF, font, màu, feather branding và component language của VNText; không sao chép dashboard hoặc dark theme của Cockpit. Popup gọn giữa cửa sổ app, có tiêu đề, nội dung và hàng hành động; notes dài cuộn trong vùng giới hạn, không làm popup tràn màn hình. Sidebar vẫn gọn, không thêm lại card/box lớn.

## Luồng UX đề xuất cho implementation

Các điểm bên dưới là mặc định thiết kế để thực hiện yêu cầu popup; không phải chức năng đã có hoặc acceptance đã PASS.

1. **Kiểm tra:** dùng nguồn stable GitHub đã cấu hình. Kiểm tra nền không khóa UI. Chỉ offer phiên bản mới hơn đã qua metadata/compatibility; không hiện popup có bản mới từ tag giả hoặc package lỗi. Khi app đang extract/translate/patch hoặc có chỉnh sửa chưa lưu, hoãn popup tự mở và không restart làm mất công việc.
2. **Có bản mới:** tiêu đề “Có bản cập nhật mới”, phiên bản hiện tại/mới và “Có gì mới” bằng câu chữ phổ thông từ Release. Nút chính “Cập nhật”, nút phụ “Để sau”, tùy chọn “Bỏ qua phiên bản này” và đóng bằng X. Không hiện SHA, provenance, raw paths hoặc kết quả kiểm chứng nội bộ trong nội dung người dùng.
3. **Để sau/bỏ qua:** đóng không cài; không bật lại cùng offer liên tục trong phiên. Bỏ qua được lưu cho đúng version, version mới hơn vẫn thông báo. Người dùng có thể mở lại bằng kiểm tra thủ công, kể cả version đã bỏ qua.
4. **Tải và kiểm tra:** chỉ bắt đầu tải khi người dùng bấm “Cập nhật”; hiển thị tiến trình từ dữ liệu thật. Chưa biết tổng byte thì dùng trạng thái không xác định, không dựng phần trăm giả. Không chạy download/install trùng khi bấm nhiều lần. Đóng popup không được âm thầm apply hoặc làm hỏng transaction; định nghĩa rõ cancel/background theo khả năng service hiện có.
5. **Sẵn sàng:** chỉ báo “Sẵn sàng cập nhật” sau xác minh package đạt. Nút “Khởi động lại để cập nhật” và “Để sau”. Không tự đóng app/apply khi người dùng chưa chọn; kiểm lại busy/unsaved state trước restart, dùng flow lưu/hủy hiện có.
6. **Sau khởi động lại:** chỉ báo “Cập nhật thành công” khi version thực và transaction/health receipt xác nhận đã apply thành công. Hiện version mới và notes, nút “Đã hiểu”; chỉ hiện một lần cho transaction thành công. Rollback/interrupted update không được báo thành công.
7. **Không có bản mới hoặc có lỗi:** kiểm tra tự động không bật modal “đã mới nhất”/lỗi lặp lại; sidebar/manual check có feedback ngắn và hành động thử lại. Phân biệt offline/timeout/rate limit, metadata/package lỗi và trường hợp cần Setup mới. Lỗi có đường hồi phục, không hạ integrity gate để vượt lỗi.

## Scope và boundaries

Owner liên quan: `MainWindow.xaml`, WPF view/viewmodel popup và `MainViewModel` updater; `Services/WpfUpdateService.cs`, `FullAppUpdateService.cs`, settings/receipt owners khi cần cùng tests tương ứng. Coordinator phải xác minh caller/contract hiện có trước sửa; tái sử dụng updater, rollback, lease và settings, không tạo updater thứ hai.

Không thay translation/model/worker protocol/game semantics, installer/uninstaller, trust hosts, hash/baseline/path allowlists hoặc quyền hệ thống để làm popup. Release notes là nội dung bên ngoài: render an toàn với độ dài giới hạn, không chạy HTML/script hay command từ notes. Thiếu notes phải có fallback ngắn, không làm mất chức năng update.

Tách discovery metadata/notes khỏi tải package nếu source hiện gộp cả hai, nhưng giữ validation và cleanup semantics. Đây là việc cần kiểm premise source, không phải khẳng định implementation hiện tại đã tách.

Không tự chọn version phát hành hoặc tạo release chỉ từ tài liệu này. Quyền tải/cài mới, dữ liệu user và external publication vẫn theo Owner/AGENTS. Không cần game copy cho task này.

## Bằng chứng nghiệm thu

- Focused state tests: newer/current/ignored/manual reopen, busy/deferred/unsaved, repeated clicks, missing/long notes và lỗi discovery/download/validation; tiến trình và restart actions đúng state.
- Affected updater regression: integrity/baseline rejection, bảo toàn data/model, rollback và recovery khi gián đoạn; giữ tests âm, không coi mock là public acceptance.
- Actual WPF generated-fixture interaction trên executable DEV có provenance: popup/notes/scroll, tải và ready, defer/reopen, keyboard/focus và kích thước cửa sổ hỗ trợ. Không chỉ dựa build/harness hoặc source assertions để chốt UI.
- Local installed-tree apply/restart acceptance dùng fixture registered và version thật phù hợp; success receipt phải gắn đúng transaction/version. Chỉ dùng fixture nhỏ, không nhân bản toàn payload nếu không cần.
- Một DEV executable + semantic smoke; TEST_RUN terminal absent/empty; quota/evidence theo CONTRACTS. Release/public stable GitHub acceptance là bước riêng trên candidate được phép, không suy từ thử cục bộ. Version và publication cần quyết định/ủy quyền tương ứng trước bước đó.
