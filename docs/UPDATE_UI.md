# Thông báo cập nhật trong app — yêu cầu trước phát hành

## Mục tiêu và nguồn thiết kế

Owner yêu cầu ngày 2026-10-11: app có bảng thông báo khi có cập nhật mới, tham khảo ảnh Cockpit Tools đã cung cấp. Ưu tiên hoàn thiện UI/updater trong bản đang chuẩn bị, rồi phát hành trước khi thực hiện `TRANSLATION_QUALITY_PLAN.md`.

Ảnh tham khảo cho thấy các trạng thái: có bản mới với release notes, đang tải có tiến trình, sẵn sàng khởi động lại và cập nhật thành công. Đây là nguồn tham khảo UX, không phải bằng chứng updater VNText đã hoạt động. Không phụ thuộc đường dẫn ảnh/máy riêng để triển khai từ public clone.

Surface mode: Operate. Giữ WPF, font, màu, feather branding và component language của VNText; không sao chép dashboard hoặc dark theme của Cockpit. Popup gọn giữa cửa sổ app, có tiêu đề, nội dung và hàng hành động; notes dài cuộn trong vùng giới hạn, không làm popup tràn màn hình. Theo yêu cầu bổ sung của Owner, bỏ toàn bộ khối version/status/nút updater ở cuối sidebar; chuyển kiểm tra cập nhật thủ công vào Cài đặt → Giới thiệu.

## Tham khảo app trực tiếp và bổ sung của Owner

Brain đã mở Cockpit Tools bằng Computer Use ngày 2026-10-11: quan sát sidebar và cả bốn tab Chung, Dịch vụ mạng, Quản lý dữ liệu, Giới thiệu. Bản đang chạy `1.3.66`; thao tác Kiểm tra cập nhật trả “Đã là bản mới nhất v1.3.66”. Không tải/cài update hoặc lưu thay đổi settings. Popup newer/download/restart không xuất hiện trong lượt này vì không có bản mới; các trạng thái đó vẫn dựa ảnh Owner, không ghi là đã kiểm trực tiếp.

Sidebar Cockpit có nhóm điều hướng cuối gồm Nhật ký/Cài đặt, không có khối chi tiết updater. Tab Giới thiệu đặt tên/icon app, version, Kiểm tra cập nhật và Ghi chú phát hành cạnh nhau. Tab Chung có tỷ lệ UI, nhớ cửa sổ, giảm chuyển động, tùy chọn update nền và nhắc update. Tab Dữ liệu có quản lý sao lưu/import/export; tab mạng có API/proxy riêng của sản phẩm đó. Chỉ ghi thông tin UI liên quan, không lưu tài khoản/token/cấu hình riêng từ app tham khảo.

Owner yêu cầu thêm: popup có thao tác bỏ qua/tải, sidebar cuối gọn, check update trong settings, và settings có tùy chỉnh thực tế. Source VNText ở checkpoint `c889bc5`: trang settings chủ yếu là lời hướng dẫn/runtime; `AppSettingsStore` có bốn lựa chọn workflow, chưa có nhóm tùy chỉnh giao diện/update như đề xuất dưới đây.

## Sidebar và Cài đặt

## Phạm vi UI được Owner duyệt triển khai — 2026-10-11

Owner đã yêu cầu chạy task UI/updater, nghiệm thu rồi tạm đóng đợt phát triển để chuẩn bị phát hành. Hoãn translation-quality/training theo plan riêng. Phạm vi settings đề xuất bên dưới được đưa vào task này: Chung/Dữ liệu/Giới thiệu; không bổ sung các tính năng đã ghi deferred.

Giữ phong cách nền sáng, xanh và feather branding; tham khảo thứ bậc và cách nhóm thông tin của Cockpit, không thay framework/theme. Bắt đầu bằng một màn hình Lấy text làm mẫu; Brain review trước khi áp dụng sang Dịch local, Sửa CSV, Tạo patch và Cài đặt. Không chạy game E2E cho thay đổi UI.

- Chuẩn hóa typography trong design tokens/styles: nội dung khoảng14, mô tả12–13, tiêu đề nhóm16–18; hạn chế nhãn9–11 nhỏ/mờ. Đây là hướng tương đối, cần kiểm DPI/window và bảng dữ liệu thực, không bulk-replace FontSize mù.
- Chuẩn hóa spacing, chiều cao input, icon, corner radii và thứ bậc nút chính/phụ; dùng component/style có sẵn, một hành động chính rõ cho mỗi bước. Không dùng màu nhấn tùy tiện hoặc hạ khả năng đọc của disabled/error state.
- Giảm mô tả lặp, badge và chrome ít thông tin; phần giải thích dài và tùy chọn ít dùng có thể mở rộng trong Trợ giúp/Nâng cao. Không giấu cảnh báo dữ liệu, điều kiện Patch, partial/unsupported hoặc lựa chọn workflow hiện có.
- Nhật ký không chiếm cột lớn khi chưa hoạt động; ưu tiên tiến độ, số xử lý, số cần sửa và bước tiếp theo. Chi tiết mở được, lỗi không bị mất và binding/state vẫn đúng. Giữ CSV virtualization, keyboard editing, dirty/save guards và trạng thái async.
- Màn hình mẫu cần actual WPF screenshot/interaction trên DEV có provenance với empty/ready/busy/error và kích thước cửa sổ hỗ trợ. Sau review, tái sử dụng cùng ngôn ngữ thiết kế cho các trang, tránh thiết kế độc lập từng trang. Có thể checkpoint từng phần với tối đa một executable DEV, không tạo nhiều payload/game copy.

Task implementation được commit source/test/docs đúng scope sau validation theo AGENTS. Version/publication là bước Release riêng, Owner chọn version trước khi build candidate; không suy artifact source cũ thành Release PASS của source mới.

## Chi tiết Sidebar và Cài đặt

**Yêu cầu đã chốt:** giữ điều hướng workflow và project, đưa Cài đặt thành mục gọn ở cuối sidebar; bỏ version/status/check/apply updater khỏi sidebar. Không tạo thêm trang Nhật ký hoặc panel trạng thái chỉ để giống Cockpit. Update mới được thao tác trên popup; kiểm tra thủ công ở Giới thiệu, không phụ thuộc sidebar.

**Đề xuất scope cho bản này, chưa là implementation hoặc toàn bộ quyết định đã duyệt:** chia settings ba tab, mỗi dòng gồm tên ngắn, một câu giải thích và điều khiển thật; không có toggle trang trí hoặc nút không có tác dụng.

- **Chung:** tỷ lệ UI với các mức giới hạn phù hợp cửa sổ hỗ trợ; nhớ vị trí/kích thước cửa sổ, có clamp khi đổi màn hình/DPI; bật/tắt tự kiểm tra cập nhật khi khởi động và bật/tắt nhắc popup. Manual check luôn hoạt động, không bị skipped-version hoặc toggle auto vô hiệu hóa. Không mặc định tải hoặc apply nền.
- **Dữ liệu:** hiển thị đường dẫn thực và nút mở thư mục dữ liệu/model bằng path resolver hiện có; báo model/worker có sẵn hay thiếu bằng trạng thái thực. Không tự đổi root, tải model, xóa model/CSV/game/backups hoặc mở một cleanup engine mới. Các lựa chọn extract/overwrite/human-review hiện có vẫn giữ ở bước workflow phù hợp, không nhân bản setting mâu thuẫn.
- **Giới thiệu:** feather icon, tên app, version executable thực, nút Kiểm tra cập nhật, Ghi chú phát hành và liên kết repository/phản hồi đã xác minh. Feedback checking/current/error/Setup-required và offer được hiển thị tại đây hoặc popup; copy phổ thông, không debug dump.

Chưa đưa vào đợt này: dark/system theme hoàn chỉnh, thêm ngôn ngữ UI, tray/autostart, backup theo lịch, cloud sync/WebDAV, API server, proxy hoặc lựa chọn model mới. Giảm chuyển động chỉ đề xuất thêm nếu implementation có animation cần kiểm soát; không tạo setting không có hiệu lực. Các phần này cần task riêng nếu Owner chọn.

Settings mới phải lưu/khôi phục thực, giữ giá trị workflow hiện có khi migration; lỗi đọc/ghi phải báo rõ và không âm thầm ghi đè file hỏng. Không hạ quy tắc dữ liệu/artifact hoặc bỏ busy/unsaved guards vì thêm setting.

## Luồng UX đề xuất cho implementation

Các điểm bên dưới là mặc định thiết kế để thực hiện yêu cầu popup; không phải chức năng đã có hoặc acceptance đã PASS.

1. **Kiểm tra:** dùng nguồn stable GitHub đã cấu hình. Kiểm tra nền không khóa UI. Chỉ offer phiên bản mới hơn đã qua metadata/compatibility; không hiện popup có bản mới từ tag giả hoặc package lỗi. Khi app đang extract/translate/patch hoặc có chỉnh sửa chưa lưu, hoãn popup tự mở và không restart làm mất công việc.
2. **Có bản mới:** tiêu đề “Có bản cập nhật mới”, phiên bản hiện tại/mới và “Có gì mới” bằng câu chữ phổ thông từ Release. Nút chính “Cập nhật”, nút phụ “Để sau”, tùy chọn “Bỏ qua phiên bản này” và đóng bằng X. Không hiện SHA, provenance, raw paths hoặc kết quả kiểm chứng nội bộ trong nội dung người dùng.
3. **Để sau/bỏ qua:** đóng không cài; không bật lại cùng offer liên tục trong phiên. Bỏ qua được lưu cho đúng version, version mới hơn vẫn thông báo. Người dùng có thể mở lại bằng kiểm tra thủ công, kể cả version đã bỏ qua.
4. **Tải và kiểm tra:** chỉ bắt đầu tải khi người dùng bấm “Cập nhật”; hiển thị tiến trình từ dữ liệu thật. Chưa biết tổng byte thì dùng trạng thái không xác định, không dựng phần trăm giả. Không chạy download/install trùng khi bấm nhiều lần. Đóng popup không được âm thầm apply hoặc làm hỏng transaction; định nghĩa rõ cancel/background theo khả năng service hiện có.
5. **Sẵn sàng:** chỉ báo “Sẵn sàng cập nhật” sau xác minh package đạt. Nút “Khởi động lại để cập nhật” và “Để sau”. Không tự đóng app/apply khi người dùng chưa chọn; kiểm lại busy/unsaved state trước restart, dùng flow lưu/hủy hiện có.
6. **Sau khởi động lại:** chỉ báo “Cập nhật thành công” khi version thực và transaction/health receipt xác nhận đã apply thành công. Hiện version mới và notes, nút “Đã hiểu”; chỉ hiện một lần cho transaction thành công. Rollback/interrupted update không được báo thành công.
7. **Không có bản mới hoặc có lỗi:** kiểm tra tự động không bật modal “đã mới nhất”/lỗi lặp lại; manual check trong Cài đặt → Giới thiệu có feedback ngắn và hành động thử lại. Phân biệt offline/timeout/rate limit, metadata/package lỗi và trường hợp cần Setup mới. Lỗi có đường hồi phục, không hạ integrity gate để vượt lỗi.

## Scope và boundaries

Owner liên quan: `MainWindow.xaml`, WPF view/viewmodel popup, settings và `MainViewModel` updater; `Services/WpfUpdateService.cs`, `FullAppUpdateService.cs`, `AppSettingsStore.cs`, window lifecycle/receipt owners khi cần cùng tests tương ứng. Coordinator phải xác minh caller/contract hiện có trước sửa; tái sử dụng updater, rollback, lease và settings, không tạo updater thứ hai. Giữ design tokens và control styles của app.

Không thay translation/model/worker protocol/game semantics, installer/uninstaller, trust hosts, hash/baseline/path allowlists hoặc quyền hệ thống để làm popup. Release notes là nội dung bên ngoài: render an toàn với độ dài giới hạn, không chạy HTML/script hay command từ notes. Thiếu notes phải có fallback ngắn, không làm mất chức năng update.

Tách discovery metadata/notes khỏi tải package nếu source hiện gộp cả hai, nhưng giữ validation và cleanup semantics. Đây là việc cần kiểm premise source, không phải khẳng định implementation hiện tại đã tách.

Không tự chọn version phát hành hoặc tạo release chỉ từ tài liệu này. Quyền tải/cài mới, dữ liệu user và external publication vẫn theo Owner/AGENTS. Không cần game copy cho task này.

## Bằng chứng nghiệm thu

- Focused state tests: newer/current/ignored/manual reopen, busy/deferred/unsaved, repeated clicks, missing/long notes và lỗi discovery/download/validation; tiến trình và restart actions đúng state.
- Affected updater regression: integrity/baseline rejection, bảo toàn data/model, rollback và recovery khi gián đoạn; giữ tests âm, không coi mock là public acceptance.
- Actual WPF generated-fixture interaction trên executable DEV có provenance: popup/notes/scroll, tải và ready, defer/reopen, keyboard/focus và kích thước cửa sổ hỗ trợ. Không chỉ dựa build/harness hoặc source assertions để chốt UI.
- Sidebar không còn khối updater; keyboard/navigation tới settings và workflow vẫn hoạt động. Nếu scope settings được triển khai: actual UI tương tác tab/control, save/reopen persistence, path actions đúng root, scaling/DPI/geometry không che/cắt nút hoặc làm CSV virtualization hỏng; giữ lựa chọn workflow cũ và báo lỗi settings thật. Auto/notify toggles có tác dụng, manual check vẫn mở offer đã bỏ qua.
- Local installed-tree apply/restart acceptance dùng fixture registered và version thật phù hợp; success receipt phải gắn đúng transaction/version. Chỉ dùng fixture nhỏ, không nhân bản toàn payload nếu không cần.
- Một DEV executable + semantic smoke; TEST_RUN terminal absent/empty; quota/evidence theo CONTRACTS. Release/public stable GitHub acceptance là bước riêng trên candidate được phép, không suy từ thử cục bộ. Version và publication cần quyết định/ủy quyền tương ứng trước bước đó.
