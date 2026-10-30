using System.Runtime.CompilerServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace VNText.Studio.App.Services;

// Only literal UI labels are localized. Bindings, editable text and user data stay intact.
public static class UiText
{
    private static bool _installed;
    public static string Language { get; private set; } = "vi";
    private static readonly ConditionalWeakTable<DependencyObject, Dictionary<DependencyProperty, string>> Originals = new();
    private static readonly Dictionary<string, string> English = new(StringComparer.Ordinal)
    {
        ["Chạy trên máy"] = "On-device processing",
        ["Mở nhật ký"] = "Open log",
        ["Model OPUS-MT INT8 sẵn sàng."] = "OPUS-MT INT8 model ready.",
        ["Model CTranslate2 chưa có trên máy. Cần tải model OPUS-MT en→vi INT8 trước khi dịch."] = "CTranslate2 model is not on this device. Download the OPUS-MT en→vi INT8 model before translating.",
        ["Chép vị trí tệp"] = "Copy file location",
        ["Chép thông tin lỗi"] = "Copy error details",
        ["Gói patch có installer — VNTextPatchInstaller.exe"] = "Patch package with installer — VNTextPatchInstaller.exe",
        ["Dịch Anh sang Việt trên máy"] = "Translate English to Vietnamese on this device",
        ["Mô hình dịch trên máy"] = "On-device translation model",
        ["Duyệt bản dịch trước khi đóng gói"] = "Review translations before packaging",
        ["Tải xuống"] = "Download",
        ["Hoàn tác"] = "Undo",
        ["Xem trước"] = "Preview",
        ["Áp dụng"] = "Apply",
        ["Duyệt dòng đã chọn để dùng trong gói"] = "Approve selected rows for this package",
        ["Duyệt bản dịch trong gói này"] = "Review translations for this package",
        ["Xác nhận đã duyệt"] = "Confirm reviewed translations",
        ["Hủy"] = "Cancel",
        ["{0} dòng đã chọn."] = "Selected rows: {0}.",
        ["Nguồn:"] = "Source:",
        ["Bản dịch:"] = "Translation:",
        ["Chỉ gói hiện tại và đúng nguồn, file, ngữ cảnh, cách nhập; không dùng cho gói khác."] = "Only this package and the exact source, file, context and import method; never another package.",
        ["Không dùng để huấn luyện hoặc làm bản dịch mặc định toàn app."] = "Not used for training or as app-wide default translations.",
        ["Bộ nhớ cũ sẽ được giữ bản sao; chỉ các dòng xác nhận được đưa vào bộ nhớ đã duyệt."] = "A copy of the old memory will be retained; only confirmed rows enter reviewed memory.",
        ["Đã duyệt {0} dòng để dùng trong gói hiện tại."] = "Approved rows: {0} for reuse in the current package.",
        ["Không thể xem trước bản dịch."] = "Cannot preview translations.",
        ["Không thể ghi bản dịch đã duyệt."] = "Cannot save reviewed translations.",
        ["Dữ liệu đã đổi; hãy chọn và xem trước lại."] = "Data changed; select the rows and preview again.",
        ["Cài đặt"] = "Settings",
        ["Nhật ký"] = "Logs",
        ["Chung"] = "General",
        ["Dữ liệu"] = "Data",
        ["Giới thiệu"] = "About",
        ["Giao diện"] = "Appearance",
        ["Ngôn ngữ"] = "Language",
        ["Chủ đề"] = "Theme",
        ["Sáng"] = "Light",
        ["Tối"] = "Dark",
        ["Theo hệ thống"] = "System",
        ["Hành động khi đóng"] = "When closing",
        ["Thoát ứng dụng"] = "Exit application",
        ["Ẩn xuống khay hệ thống"] = "Hide to system tray",
        ["Khởi động thu nhỏ"] = "Start minimized",
        ["Độ đậm nền"] = "Background intensity",
        ["Sau 4 giờ"] = "After 4 hours",
        ["Sau 1 ngày"] = "After 1 day",
        ["Sau 1 tuần"] = "After 1 week",
        ["Nhắc cập nhật"] = "Update reminder",
        ["Tự động tải cập nhật nền"] = "Download updates in background",
        ["Chỉ tải; bạn quyết định khi cài và khởi động lại."] = "Download only; you choose when to install and restart.",
        ["Khởi động và đóng"] = "Startup and closing",
        ["Mở VNText Studio"] = "Open VNText Studio",
        ["Thoát"] = "Exit",
        ["Tỷ lệ giao diện"] = "Interface scale",
        ["Nhớ vị trí và kích thước cửa sổ"] = "Remember window position and size",
        ["Cập nhật"] = "Updates",
        ["Kiểm tra cập nhật khi mở ứng dụng"] = "Check for updates on startup",
        ["Thông báo khi có phiên bản mới"] = "Notify when an update is available",
        ["Chỉ tải khi bạn chọn cập nhật."] = "Download only when you choose to update.",
        ["Thư mục dữ liệu"] = "Data folder",
        ["Mở thư mục"] = "Open folder",
        ["Môi trường dịch local"] = "Local translation environment",
        ["Lấy text"] = "Extract text",
        ["Dịch local"] = "Local translation",
        ["Dịch tự động"] = "Auto translate",
        ["Dịch trên máy bằng mô hình local, không gửi nội dung ra ngoài."] = "Translates on this computer with a local model; nothing is sent out.",
        ["Sửa CSV"] = "CSV editor",
        ["Tạo patch"] = "Create patch",
        ["Chọn game, rồi bấm Lấy text."] = "Choose a game, then extract text.",
        ["Dịch bằng mô hình local hoặc chọn CSV đã dịch."] = "Translate with a local model or select a translated CSV.",
        ["Chọn game và bản dịch để kiểm tra rồi đóng gói patch."] = "Choose a game and translation, validate, then package the patch.",
        ["Nguồn và gói dịch"] = "Source and translation package",
        ["Nguồn được giữ nguyên; gói dịch lưu riêng."] = "The source stays unchanged; translation packages are saved separately.",
        ["Game hoặc asset"] = "Game or asset",
        ["Game / asset"] = "Game / asset",
        ["Mở"] = "Open",
        ["Chọn..."] = "Choose...",
        ["Chọn file"] = "Choose file",
        ["Chọn file CSV"] = "Choose CSV file",
        ["Chọn CSV"] = "Choose CSV",
        ["Mở công cụ"] = "Open tools",
        ["Chưa bắt đầu"] = "Not started",
        ["Worker đã nhận yêu cầu hủy; đang chờ tác vụ dừng an toàn…"] = "The worker received the cancel request; waiting for the task to stop safely…",
        ["Đã hủy"] = "Cancelled",
        ["Lỗi"] = "Error",
        ["Đầu vào đã đổi"] = "The input changed",
        ["Phân tích hoàn tất"] = "Analysis finished",
        ["Hoàn tất"] = "Finished",
        ["Worker báo lỗi; đang chờ kết quả cuối để dừng an toàn…"] = "The worker reported an error; waiting for the final result to stop safely…",
        ["Đang bắt đầu…"] = "Starting…",
        ["Đã yêu cầu hủy; đang chờ worker xác nhận…"] = "Cancel requested; waiting for the worker to confirm…",
        ["Chưa có kết quả cuối sau 30 giây; hãy tiếp tục chờ và không đóng ứng dụng cưỡng bức."] = "No final result after 30 seconds; keep waiting and do not force-close the application.",
        ["Đóng (Esc)"] = "Close (Esc)",
        ["Ảnh tĩnh PNG/JPEG/WebP. OCR tiếng Anh luôn cần bạn xem lại: sửa text, nhập bản dịch, chọn đúng một chế độ nền rồi tick Duyệt. OCR, duyệt và dựng ảnh chỉ đọc ảnh gốc và ghi kết quả vào thư mục xuất riêng. Chỉ bước “Cài gói vào bản sao game…” ghi vào một BẢN SAO game do bạn chọn (có bản lưu và kiểm hash đọc lại); thư mục game gốc không bị ghi, và bản sao trùng hoặc nằm trong game gốc sẽ bị từ chối."] = "Still PNG/JPEG/WebP images. English-language OCR always needs your review: edit the text, enter the translation, choose exactly one background mode, then tick Approve. OCR, review and rendering only read the original image and write results to a separate output folder. Only the “Install package into game copy…” step writes, into a game COPY you choose (with a backup and a read-back hash check); the original game folder is never written, and a copy that is the same as, or inside, the original game is refused.",
        ["Tác vụ đang chạy"] = "Task running",
        ["Tiến trình và xác nhận hủy"] = "Progress and cancellation status",
        ["Hủy tác vụ đang chạy"] = "Cancel the running task",
        ["Tình trạng ảnh trong gói"] = "Image status in the package",
        ["1 · Chọn ảnh và OCR"] = "1 · Choose an image and run OCR",
        ["Chọn ảnh…"] = "Choose image…",
        ["Mở review đã lưu…"] = "Open saved review…",
        ["Ảnh ứng viên"] = "Candidate images",
        ["2 · Xem lại và duyệt"] = "2 · Review and approve",
        ["Chưa có ảnh để xem trước"] = "No image to preview yet",
        ["Vùng chữ trong ảnh"] = "Text regions in the image",
        ["TEXT OCR"] = "OCR TEXT",
        ["BẢN DỊCH"] = "TRANSLATION",
        ["CHẾ ĐỘ NỀN"] = "BACKGROUND MODE",
        ["DUYỆT"] = "APPROVED",
        ["XÓA"] = "DELETE",
        ["Xóa vùng"] = "Delete region",
        ["Chọn một dòng trong bảng để sửa crop, cỡ chữ, màu và chế độ nền của vùng đó."] = "Select a row in the table to edit that region's crop, font size, colors and background mode.",
        ["Chi tiết vùng đang chọn"] = "Selected region details",
        ["X (pixel gốc)"] = "X (source pixels)",
        ["X của vùng, pixel gốc"] = "Region X, source pixels",
        ["Y (pixel gốc)"] = "Y (source pixels)",
        ["Y của vùng, pixel gốc"] = "Region Y, source pixels",
        ["Chiều rộng của vùng"] = "Region width",
        ["Chiều cao của vùng"] = "Region height",
        ["Cỡ chữ"] = "Font size",
        ["Màu nền (RGB)"] = "Background color (RGB)",
        ["Màu nền RGB"] = "Background color RGB",
        ["Màu chữ (RGB)"] = "Text color (RGB)",
        ["Màu chữ RGB"] = "Text color RGB",
        ["Chế độ nền — chọn đúng một"] = "Background mode — choose exactly one",
        ["Chế độ nền phẳng đã kiểm"] = "Flat background mode, checked",
        ["Chế độ thay chữ trong suốt"] = "Replace transparent text mode",
        ["Thay region bằng màu đặc"] = "Replace region with solid color",
        ["Chế độ thay region bằng màu đặc"] = "Replace region with solid color mode",
        ["Chế độ clone nền mẫu đã kiểm"] = "Clone sample background mode, checked",
        ["X nền mẫu (clone)"] = "Sample X (clone)",
        ["Y nền mẫu (clone)"] = "Sample Y (clone)",
        ["Duyệt text/crop của vùng này"] = "Approve this region's text/crop",
        ["Duyệt text và crop của vùng"] = "Approve the region's text and crop",
        ["3 · Dựng ảnh và gói cài"] = "3 · Render and install package",
        ["Trạng thái xử lý ảnh"] = "Image processing status",
        ["Text trong ảnh…"] = "Text in images…",
        ["Text trong ảnh"] = "Text in images",
        ["Mở Text trong ảnh"] = "Open Text in images",
        ["Dịch ảnh…"] = "Translate image…",
        ["OCR, duyệt, dựng và cài ảnh trong game."] = "OCR, review, render and install images in the game.",
        ["OCR, duyệt, dựng và cài ảnh (không cần dòng text trong CSV)."] = "OCR, review, render and install images (no CSV text rows needed).",
        ["Chọn ảnh để tạo bản dịch nháp; việc này chỉ chạy khi bạn yêu cầu trong bước Dịch."] = "Choose an image to create a draft translation; this runs only when you ask for it in the Translate step.",
        ["Nền phẳng"] = "Flat background",
        ["Chữ trong suốt"] = "Transparent text",
        ["Màu đặc"] = "Solid color",
        ["Clone nền mẫu"] = "Clone sample background",
        ["Chưa chọn chế độ nền"] = "No background mode chosen",
        ["Chọn nhiều chế độ — cần đúng một"] = "Several modes chosen — exactly one is required",
        ["Chọn ảnh tĩnh để OCR; kết quả cần review, không tự tạo patch."] = "Choose a still image for OCR; the result needs review and never creates a patch by itself.",
        ["Chọn ảnh để xem trước và OCR"] = "Choose an image to preview and OCR",
        ["Bấm “OCR ảnh đã chọn” để xem trước và đọc text trong ảnh này."] = "Press “OCR the chosen image” to preview and read the text in this image.",
        ["tìm ảnh trong thư mục game"] = "find images in the game folder",
        ["OCR ảnh"] = "OCR images",
        ["dịch nháp ảnh"] = "draft image translation",
        ["dựng ảnh từ bản dịch đã duyệt"] = "render from the approved translation",
        ["tạo gói ảnh"] = "create the image package",
        ["cài gói vào bản sao game"] = "install the package into the game copy",
        ["phục hồi giao dịch ảnh"] = "recover the image transaction",
        ["dịch text trong CSV"] = "translate CSV text",
        ["lấy text"] = "extract text",
        ["phân tích game"] = "analyze the game",
        ["tạo patch"] = "create the patch",
        ["tác vụ"] = "task",
        ["Chưa chọn game / thư mục chứa ảnh."] = "No game / image folder chosen.",
        ["Chưa chọn thư mục xuất."] = "No output folder chosen.",
        ["Chưa có báo cáo OCR trong gói. Bấm “Tìm ảnh từ thư mục game”, chọn ảnh rồi OCR."] = "No OCR report in the package yet. Press “Find images in the game folder”, choose an image, then run OCR.",
        ["Để duyệt và cài, chọn ảnh thật trong thư mục game (không phải bản sao trong gói)."] = "To review and install, choose the real image in the game folder (not the copy inside the package).",
        ["Chọn thư mục xuất trước."] = "Choose the output folder first.",
        ["Review đã đổi sau khi dựng ảnh — hãy dựng lại trước khi tạo gói hoặc cài. Các file đã dựng trước đó vẫn được giữ trong thư mục xuất."] = "The review changed after rendering — render again before creating the package or installing. Files rendered earlier are kept in the output folder.",
        ["Đang dịch lại ảnh…"] = "Re-translating the image…",
        ["Đang tạo gói ảnh locale…"] = "Creating the locale image package…",
        ["Đang cài vào bản sao game…"] = "Installing into the game copy…",
        ["Đang phục hồi giao dịch ảnh…"] = "Recovering the image transaction…",
        ["Đang xử lý text trong ảnh…"] = "Processing the text in the image…",
        ["Đang dựng ảnh từ bản dịch duyệt…"] = "Rendering the image from the approved translation…",
        ["Review ảnh vượt 2 MiB."] = "The image review is larger than 2 MiB.",
        ["Review rỗng."] = "The review is empty.",
        ["Schema/region không hợp lệ."] = "Invalid schema/region.",
        ["Ảnh nguồn không tồn tại hoặc vượt 32 MiB."] = "The source image is missing or larger than 32 MiB.",
        ["Ảnh nguồn đã đổi hoặc hash review không khớp."] = "The source image changed or the review hash does not match.",
        ["Kích thước ảnh nguồn không khớp review."] = "The source image size does not match the review.",
        ["Không tìm thấy ảnh nguồn/preview."] = "The source image/preview was not found.",
        ["Preview vượt 32 MiB."] = "The preview is larger than 32 MiB.",
        ["Preview không hợp lệ hoặc quá 16 triệu pixel."] = "The preview is invalid or over 16 million pixels.",
        ["Không thấy text; chọn crop/ảnh khác hoặc thêm region thủ công."] = "No text found; choose another crop/image or add a region manually.",
        ["Duyệt text/crop và chọn đúng một chế độ: nền phẳng, giữ chữ trong suốt, thay region bằng màu đặc, hoặc clone vùng nền sạch (tọa độ X/Y nền mẫu)."] = "Approve the text/crop and choose exactly one mode: flat background, keep transparent text, replace the region with a solid color, or clone a clean background area (sample X/Y).",
        ["Review đã đổi trong lúc xử lý; kết quả cũ bị bỏ (file giữ trong thư mục xuất), hãy dựng lại cho review hiện tại."] = "The review changed during processing; the old result was dropped (files are kept in the output folder) — render again for the current review.",
        ["Ảnh đang chọn đã đổi trong lúc xử lý; kết quả cũ bị bỏ, hãy chạy lại cho ảnh hiện tại."] = "The chosen image changed during processing; the old result was dropped — run again for the current image.",
        ["Đã xử lý ảnh; xem thư mục images cạnh CSV."] = "Image processed; see the images folder next to the CSV.",
        ["Chưa dịch được ảnh."] = "The image could not be translated yet.",
        ["Chọn ảnh để OCR."] = "Choose an image to OCR.",
        ["Đã xử lý gói ảnh"] = "Image package processed",
        ["Đã render"] = "Rendered",
        ["Thư mục review ảnh phải mới; giữ nguyên kết quả đã có."] = "The image review folder must be new; existing results are kept.",
        ["Đã tạo gói ảnh locale Vietnamese. Cài vào bản sao game; cần chọn ngôn ngữ vietnamese trong game."] = "Vietnamese locale image package created. Install it into a game copy; choose Vietnamese in the game.",
        ["Đã cài ảnh vào bản sao game và kiểm hash đọc lại. Chưa xác nhận game đang chọn Vietnamese."] = "Images installed into the game copy and hash-verified on read-back. It is not confirmed that the game is set to Vietnamese.",
        ["Đã gỡ đúng ảnh của giao dịch; giữ nguyên ảnh nguồn."] = "The transaction's images were removed exactly; source images are untouched.",
        ["RPA member không phải ảnh tĩnh được hỗ trợ."] = "The RPA member is not a supported still image.",
        ["Ảnh thay đổi trong lúc OCR; hãy lấy lại text."] = "The image changed during OCR; extract the text again.",
        ["Không thấy text; kiểm ảnh/crop rồi thử lại."] = "No text found; check the image/crop and try again.",
        ["RPA container/member đã đổi; hãy tạo lại inventory và OCR."] = "The RPA container/member changed; rebuild the inventory and run OCR again.",
        ["Ảnh nguồn đã thay đổi; review lại."] = "The source image changed; review again.",
        ["Đã dựng ảnh từ bản dịch duyệt; mở preview để kiểm trước khi dùng. Ảnh nguồn giữ nguyên."] = "Image rendered from the approved translation; open the preview to check it before use. The source image is untouched.",
        ["Mở review text ảnh"] = "Open image-text review",
        ["Chọn ảnh có chữ"] = "Choose an image with text",
        ["Ảnh tĩnh"] = "Still images",
        ["SẴN SÀNG"] = "READY",
        ["CSV HỢP LỆ"] = "CSV VALID",
        ["CẦN XEM LẠI"] = "NEEDS REVIEW",
        ["CẦN KIỂM TRA LẠI"] = "CHECK AGAIN",
        ["Biểu thức tìm kiếm không hợp lệ."] = "The search expression is not valid.",
        ["Đã mở review. Vì an toàn, hãy chọn lại chế độ nền và duyệt các vùng trước khi dựng ảnh."] = "Review opened. For safety, choose the background mode again and approve the regions before rendering.",
        ["Nguồn bản dịch đã đổi — hãy kiểm tra lại trước khi tạo patch."] = "The translation source changed — check it again before creating the patch.",
        ["Xem ví dụ"] = "Show examples",
        ["Ẩn ví dụ"] = "Hide examples",
        ["Sai placeholder"] = "Wrong placeholder",
        ["Sai tag"] = "Wrong tag",
        ["Rác lặp"] = "Repeated junk",
        ["HTML rác"] = "HTML junk",
        ["Synonym thủ công"] = "Synonym (manual)",
        ["Thu gọn"] = "Collapse",
        ["Mở công cụ Tìm và thay thế"] = "Open Find and replace tools",
        ["Thu gọn công cụ Tìm và thay thế"] = "Collapse Find and replace tools",
        ["Chọn file translation.csv để xem và sửa bản dịch."] = "Choose a translation.csv file to view and edit translations.",
        ["Chưa có thuật ngữ nào. Nhập từ trong game và cách dịch ở trên, rồi bấm Thêm."] = "No terms yet. Enter a game word and its translation above, then press Thêm.",
        ["Nhập thuật ngữ đầu tiên"] = "Enter the first term",
        ["Chọn ảnh, chạy OCR, sửa và duyệt từng vùng rồi dựng ảnh."] = "Choose an image, run OCR, edit and approve each region, then render.",
        ["Game gốc không bị ghi: chỉ bước cài mới ghi vào một bản sao game do bạn chọn."] = "The original game is never written: only the install step writes, into a game copy you choose.",
        ["Chi tiết"] = "Details",
        ["Chi tiết an toàn và quy trình"] = "Safety and workflow details",
        ["Cần xem lại"] = "Needs review",
        ["Chọn CSV cần dịch"] = "Choose the CSV to translate",
        ["Chọn CSV để sửa"] = "Choose the CSV to edit",
        ["Chọn CSV để tạo patch"] = "Choose the CSV to create the patch",
        ["Thư mục xuất"] = "Output folder",
        ["Thư mục xuất / gói dịch"] = "Output / package folder",
        ["Phân tích game"] = "Analyze game",
        ["Phân tích"] = "Analyze",
        ["Kiểm tra khả năng lấy text; không sửa game."] = "Check extraction support without changing the game.",
        ["Chi tiết phân tích"] = "Analysis details",
        ["Tuỳ chọn trích xuất"] = "Extraction options",
        ["Tách dòng cần duyệt"] = "Separate rows requiring review",
        ["Mức lọc văn bản thô"] = "Raw text filtering",
        ["Sạch"] = "Clean",
        ["Cân bằng"] = "Balanced",
        ["Quét sâu"] = "Deep scan",
        ["Tiến trình quét"] = "Extraction progress",
        ["Tiến trình tải SDK và lấy text"] = "SDK download and extraction progress",
        ["Chưa có translation.csv — bấm “Chọn CSV” để chọn file cần dịch, hoặc Lấy text trước để tạo gói."] = "No translation.csv yet — click “Chọn CSV” to pick the file to translate, or run Extract first to create a package.",
        ["Đầu vào đã đổi • cần phân tích lại"] = "Input changed • analyze again",
        ["Nhật ký và cảnh báo"] = "Logs and warnings",
        ["Nhật ký"] = "Log",
        ["Nguồn dịch"] = "Translation source",
        ["File CSV cần xử lý"] = "CSV to process",
        ["Mô hình local"] = "Local model",
        ["Thuật ngữ ưu tiên"] = "Preferred terminology",
        ["Chỉnh sửa"] = "Edit",
        ["Quy tắc dịch"] = "Translation rules",
        ["Ghi đè bản dịch cũ"] = "Overwrite existing translations",
        ["Bắt buộc duyệt thủ công kết quả MT"] = "Require manual review of machine translations",
        ["Công cụ bổ trợ"] = "Additional tools",
        ["Dịch bằng công cụ bên ngoài"] = "Translate with an external tool",
        ["Xuất ZIP"] = "Export ZIP",
        ["Dùng lại bản dịch cũ"] = "Reuse a previous translation",
        ["Nhập bản dịch cũ"] = "Import previous translation",
        ["Bắt đầu dịch"] = "Start translation",
        ["Tiến trình dịch"] = "Translation progress",
        ["Hủy tác vụ"] = "Cancel task",
        ["Nguồn đóng gói"] = "Package source",
        ["File bản dịch"] = "Translation file",
        ["Kiểm tra"] = "Validate",
        ["Mở trong Sửa CSV…"] = "Open in CSV editor…",
        ["Kiểm tra CSV rồi đóng gói cho game."] = "Validate the CSV, then package it for the game.",
        ["Tiến trình đóng gói"] = "Packaging progress",
        ["Đóng gói patch"] = "Build patch",
        ["Kiểm tra trước khi build"] = "Pre-build checks",
        ["Kết quả kiểm tra"] = "Validation results",
        ["Phạm vi"] = "Scope",
        ["Tìm và thay thế bản dịch"] = "Find and replace translations",
        ["Tìm trong bản dịch"] = "Find in translations",
        ["Thay bằng"] = "Replace with",
        ["Xem trước & thay thế"] = "Preview & replace",
        ["Tải lại"] = "Reload",
        ["Lưu thay đổi"] = "Save changes",
        ["Nguồn CSV"] = "CSV source",
        ["Chỉnh sửa bản dịch trước khi đóng gói."] = "Edit translations before packaging.",
        ["Xóa bản dịch lỗi"] = "Remove invalid translations",
        ["Dịch lại dòng lỗi (CT2)"] = "Retranslate invalid rows (CT2)",
        ["NGUYÊN BẢN"] = "SOURCE",
        ["BẢN DỊCH TIẾNG VIỆT"] = "VIETNAMESE TRANSLATION",
        ["TRẠNG THÁI"] = "STATUS",
        ["CHƯA LƯU"] = "UNSAVED",
        ["HỢP LỆ"] = "VALID",
        ["BỊ CHẶN"] = "BLOCKED",
        ["BƯỚC CUỐI"] = "FINAL STEP",
        ["Tác giả"] = "Author",
        ["Giấy phép"] = "License",
        ["Kho mã nguồn"] = "Source repository",
        ["Phản hồi"] = "Feedback",
        ["Ghi chú phát hành"] = "Release notes",
        ["Kiểm tra cập nhật"] = "Check for updates",
        ["Báo lỗi và đề xuất trên GitHub"] = "Report issues and suggest features on GitHub",
        ["VNText hỗ trợ quy trình lấy text, chỉnh CSV và đóng gói patch."] = "Extract text, edit translations and package patches with VNText.",
        ["Chưa cấu hình nguồn cập nhật."] = "No update source configured.",
        ["Đóng"] = "Close",
        ["Thêm"] = "Add",
        ["Xóa"] = "Remove",
        ["Từ trong game"] = "In-game term",
        ["Dịch thành"] = "Translation",
        ["Ví dụ: pheromones"] = "Example: pheromones",
        ["Ví dụ: mị lực"] = "Example: allure",
        ["Chọn cách dịch muốn dùng thống nhất cho những từ thường gặp."] = "Choose consistent translations for frequently used terms.",
        ["Lưu review riêng"] = "Save review separately",
        ["Chọn ảnh"] = "Choose image",
        ["Text trong ảnh — OCR và bản dịch duyệt"] = "Text in images — OCR and reviewed translations",
        ["Tìm ảnh từ thư mục game"] = "Find images in game folder",
        ["Dịch lại ảnh…"] = "Retry image translation…",
        ["OCR ảnh đã chọn"] = "OCR selected image",
        ["Thêm region thủ công"] = "Add region manually",
        ["Duyệt text/crop"] = "Review text/crop",
        ["Dựng ảnh từ bản dịch duyệt"] = "Render image from reviewed translation",
        ["Tạo gói ảnh Ren'Py"] = "Create Ren'Py image package",
        ["Cài gói vào bản sao game…"] = "Install package into a game copy…",
        ["Phục hồi giao dịch ảnh…"] = "Recover image transaction…",
        ["Mở review đã lưu"] = "Open saved review",
        ["Thay chữ trong suốt"] = "Replace transparent text",
        ["Thay nền region bằng màu đặc"] = "Replace region with a solid background",
        ["Clone nền mẫu đã kiểm"] = "Clone a verified background sample",
        ["Chữ RGB"] = "Text RGB",
        ["Nền RGB"] = "Background RGB",
        ["Rộng"] = "Width",
        ["Cao"] = "Height",
        ["Tải công cụ rồi lấy text"] = "Download tools, then extract text",
        ["Tiếp tục, chỉ xuất để xem lại"] = "Continue; export for review only",
        ["Chọn công cụ đã cài"] = "Choose installed tools",
        ["Chỉ lấy văn bản"] = "Extract text only",
        ["Tài nguyên"] = "Assets",
        ["Có thể là văn bản"] = "Possible text",
        ["Cần xem lại / chưa hỗ trợ"] = "Needs review / unsupported",
        ["Có đường ghi lại; chưa kiểm patch"] = "Write-back route exists; patch unverified",
        ["Chưa xác định"] = "Unknown",
        ["Chưa có hoạt động"] = "No activity yet",
        ["Mở để xem chi tiết và cảnh báo."] = "Open to view details and warnings.",
        ["Mở thư mục output"] = "Open output folder",
        ["Game Ren'Py được nhận diện"] = "Ren'Py game detected",
        ["Nếu tiếp tục không có SDK, một số lời thoại sẽ cần xem lại."] = "Continuing without the SDK may leave dialogue requiring review.",
        ["Chỉ tìm trong cột Bản dịch"] = "Search only the Translation column",
        ["Chỉ nhập dòng khớp mã và câu gốc; dòng khác được giữ để sửa."] = "Import only matching keys and source text; keep other rows for review.",
        ["Khi bật, kết quả MT được ghi vào review_only.csv và phải duyệt trước khi tạo patch."] = "When enabled, machine translations go to review_only.csv and need review before patching.",
        ["Nếu CSV thuộc gói ZIP, ứng dụng đối chiếu gói trước khi tạo patch."] = "For CSV files from a ZIP package, package identity is checked before patching.",
        ["Phân tích chỉ đọc nguồn; kết quả này chưa kiểm tra việc ghi bản dịch vào game."] = "Analysis is read-only and does not verify translation write-back.",
        ["Engine: chưa xác định"] = "Engine: unknown",
        ["Engine: Unity"] = "Engine: Unity",
        ["Engine: Ren’Py"] = "Engine: Ren’Py",
        ["Engine: Unity + Ren’Py evidence"] = "Engine: Unity + Ren’Py evidence",
        ["Unity: có bằng chứng trong báo cáo phân tích."] = "Unity: detected in the analysis report.",
        ["Unity: báo cáo không xác nhận engine này."] = "Unity: not confirmed by the report.",
        ["Ren’Py: tìm thấy tệp .rpy/.rpym trong game/."] = "Ren’Py: .rpy/.rpym files found under game/.",
        ["Ren’Py: tìm thấy bytecode .rpyc/.rpymc có header RPC2 trong game/."] = "Ren’Py: .rpyc/.rpymc bytecode with RPC2 header found under game/.",
        ["Ren’Py: tìm thấy archive RPA hợp lệ cùng cấu trúc runtime."] = "Ren’Py: valid RPA archive found with runtime structure.",
        ["Ren’Py: chưa kiểm tra được nguồn tệp."] = "Ren’Py: source files could not be inspected.",
        ["Ren’Py: chưa xác nhận được bằng chứng hỗ trợ."] = "Ren’Py: no supported evidence was confirmed.",
        ["Phân tích chỉ đọc; chưa xác minh patch/write-back."] = "Read-only analysis; patch/write-back remains unverified.",
        ["Kết quả quét và các cảnh báo sẽ xuất hiện ở đây sau khi bạn bắt đầu."] = "Scan results and warnings appear here after you start.",
        ["Log phiên làm việc sẽ hiện ở đây khi có hoạt động."] = "Session logs appear here when there is activity.",
        ["Đang chờ bạn bắt đầu phiên dịch local."] = "Waiting for you to start local translation.",
        ["Tạo gói dịch để dịch bằng công cụ bên ngoài; sau đó chọn CSV kết quả ở Tạo patch."] = "Export a package for external translation, then select the resulting CSV in Create patch.",
        ["Bản dịch"] = "Translation",
        ["CTranslate2 · dịch Anh sang Việt · chạy offline."] = "CTranslate2 · English to Vietnamese · offline.",
        ["Dịch local — Chạy mô hình AI ngay trên máy của bạn. LOCAL AI."] = "Local translation — run AI models on your computer.",
        ["Nhật ký patch"] = "Patch log",
        ["Nền phẳng đã kiểm"] = "Verified plain background",
        ["X nền mẫu"] = "Sample background X",
        ["Y nền mẫu"] = "Sample background Y",
        ["Xóa thuật ngữ này"] = "Remove this term",
        ["Chọn thư mục game..."] = "Select game folder...",
        ["Chưa phân tích game"] = "Game not analyzed",
        ["Đã lưu cài đặt."] = "Settings saved.",
        ["Python worker có sẵn"] = "Python worker available",
        ["Thiếu Python worker"] = "Python worker missing",
        ["File model OPUS-MT INT8 có sẵn."] = "OPUS-MT INT8 model files available.",
        ["Thiếu file model OPUS-MT INT8."] = "OPUS-MT INT8 model files missing.",
        ["PNG/JPEG/WebP tĩnh. OCR tiếng Anh cần review. Chữ trên nền trong suốt có thể được thay bằng chữ mới; pixel ngoài region giữ nguyên. Nền phức tạp cần xác nhận thay toàn region bằng màu đặc. Output riêng, không tự patch game."] = "Static PNG/JPEG/WebP. English OCR needs review. Transparent text can be replaced; pixels outside the region stay unchanged. Complex backgrounds require explicit approval to replace the whole region with a solid color. Output is separate; games are not patched automatically.",
        ["Sửa text OCR, bản dịch và crop x/y/rộng/cao (pixel gốc). Với chữ trong suốt, region đã chọn sẽ được làm trong suốt rồi vẽ chữ mới; xác nhận chỉ khi vùng đó không chứa artwork cần giữ. Artwork phức tạp cần xác nhận thay toàn region bằng màu đặc. Chọn đúng một chế độ; pixel ngoài region giữ nguyên."] = "Edit OCR text, translation and crop x/y/width/height in original pixels. Transparent-text mode clears the selected region before drawing new text; approve only if no artwork in that region needs preserving. Complex artwork requires approval to replace the entire region with a solid color. Choose exactly one mode; pixels outside the region stay unchanged.",
        ["Ngôn ngữ hiển thị"] = "Display language",
        ["Chọn ngôn ngữ hiển thị giao diện"] = "Choose the interface display language",
        ["Chủ đề ứng dụng"] = "Application theme",
        ["Chuyển đổi chế độ sáng, tối hoặc theo hệ thống."] = "Switch between light, dark and system appearance.",
        ["Điều chỉnh sắc độ nền; không làm mờ chữ và điều khiển."] = "Adjust background tint without fading text or controls.",
        ["Điều chỉnh kích thước hiển thị của giao diện."] = "Adjust the display size of the interface.",
        ["Khôi phục vị trí và kích thước cửa sổ ở lần mở sau."] = "Restore the window position and size on the next launch.",
        ["Thoát ứng dụng hoặc tiếp tục chạy trong khay hệ thống."] = "Exit the application or keep it running in the system tray.",
        ["Mở ứng dụng ở trạng thái thu nhỏ; dùng khay nếu đã chọn."] = "Start minimized; use the tray when that close action is selected.",
        ["Tự kiểm tra phiên bản mới khi khởi động và định kỳ khi ứng dụng đang chạy."] = "Check at startup and periodically while the application is running.",
        ["Hiển thị thông báo khi có bản cập nhật."] = "Show a notification when an update is available.",
        ["Tải khi ứng dụng rảnh; chỉ cài và khởi động lại khi bạn xác nhận."] = "Download while idle; install and restart only after your confirmation.",
        ["Chọn thời gian nhắc lại sau khi bạn hoãn cập nhật."] = "Choose when to remind you after postponing an update.",
        ["Thực thi các tác vụ xử lý trên máy."] = "Run processing tasks on this computer.",
    };
    /// <summary>Display timestamps follow the app language, not the machine culture (never the on-disk log text).</summary>
    public static string FormatLocalTime(DateTime value) => Language == "en"
        ? value.ToString("yyyy-MM-dd HH:mm", System.Globalization.CultureInfo.InvariantCulture)
        : value.ToString("dd/MM/yyyy HH:mm", System.Globalization.CultureInfo.InvariantCulture);
    public static string Translate(string text) => Language == "en" && English.TryGetValue(text, out var translated) ? translated : text;

    private static readonly (string Vi, string En)[] DynamicPrefixes =
    [
        ("Không mở được review: ", "Could not open the review: "), ("Đã lưu review riêng: ", "Review saved separately: "), ("Lưu review lỗi: ", "Saving the review failed: "),
        ("Chưa hoàn tất: ", "Not finished: "), ("Không đọc được kết quả ảnh: ", "Could not read the image result: "),
    ];
    private static readonly string[] SentenceKeys =
    [
        "Đã tạo gói ảnh locale Vietnamese. Cài vào bản sao game; cần chọn ngôn ngữ vietnamese trong game.",
        "Đã cài ảnh vào bản sao game và kiểm hash đọc lại. Chưa xác nhận game đang chọn Vietnamese.",
        "Đã gỡ đúng ảnh của giao dịch; giữ nguyên ảnh nguồn.", "Đã xử lý gói ảnh",
        "Đã dựng ảnh từ bản dịch duyệt; mở preview để kiểm trước khi dùng. Ảnh nguồn giữ nguyên.",
    ];
    // (regex, English template, groups that are themselves app messages/labels)
    private static readonly (System.Text.RegularExpressions.Regex Pattern, string English, int[] Nested)[] DynamicPatterns =
    [
        (new(@"^Đang chạy: (.+)\.$"), "Running: {1}.", [1]),
        (new(@"^Một tác vụ khác đang chạy \((.+)\) — chờ xong hoặc bấm Hủy trước khi dùng ảnh\.$"), "Another task is running ({1}) — wait for it to finish or press Cancel before using images.", [1]),
        (new(@"^Đang có tác vụ chạy; chưa thể (.+)\.$"), "A task is running; cannot {1} yet.", [1]),
        (new(@"^Chưa thể (.+): chưa có ảnh dựng/gói khớp với review hiện tại\. Dựng lại ảnh từ review đã duyệt trước\.$"), "Cannot {1}: there is no rendered image/package matching the current review. Render again from the approved review first.", [1]),
        (new(@"^Đã hủy (.+)\. Ảnh gốc được giữ nguyên; kết quả hủy không được áp dụng vào màn hình này, nhưng phần đã ghi an toàn \(nếu có\) có thể còn trong thư mục xuất\.$"), "Cancelled {1}. The original image is untouched; the cancelled result is not applied to this screen, but anything already written safely (if any) may remain in the output folder.", [1]),
        (new(@"^(\d+) region cần review; tọa độ theo pixel ảnh gốc\. Chọn đúng một chế độ nền cho từng vùng trước render\.$"), "{1} regions need review; coordinates are in source-image pixels. Choose exactly one background mode for each region before rendering.", []),
        (new(@"^Gói có (\S+) ảnh: (\S+) đã OCR, (\S+) bản dịch nháp, (\S+) chưa OCR được \(cần xem tay\)\.(?: (.*))?$"), "The package has {1} images: {2} OCR'd, {3} draft translations, {4} not OCR-able (need manual attention). {5}", [5]),
        (new(@"^Ảnh: (\d+) bản dịch nháp, (\d+) chưa dịch\. (.*)$"), "Images: {1} draft translations, {2} untranslated. {3}", []),
        (new(@"^Tìm thấy (\d+) ảnh ứng viên; chưa xác nhận có chữ(?:; inventory chưa đầy đủ do (\d+) archive lỗi/không hỗ trợ)?\. Chọn ảnh để OCR\.$"), "Found {1} candidate images; text is not confirmed{2}. Choose an image to OCR.", []),
        (new(@"^OCR (\d+) region — cần sửa text/tọa độ, duyệt nền phẳng và bản dịch trước render\.$"), "OCR found {1} regions — edit the text/coordinates, approve the flat background and the translation before rendering.", []),
    ];

    /// <summary>Display-time translation of app messages that contain numbers/labels. Vietnamese is returned untouched; user data, paths and
    /// unknown (technical/Windows) text pass through unchanged because only whole known messages, known prefixes and anchored patterns match.</summary>
    public static string TranslateDynamic(string text)
    {
        if (Language != "en" || string.IsNullOrEmpty(text)) return text;
        if (English.TryGetValue(text, out var exact)) return exact;
        foreach (var (vi, en) in DynamicPrefixes)
            if (text.StartsWith(vi, StringComparison.Ordinal)) return en + TranslateDynamic(text[vi.Length..]);
        foreach (var key in SentenceKeys)
            if (text.Length > key.Length && text.StartsWith(key + " ", StringComparison.Ordinal)) return English[key] + text[key.Length..];
        foreach (var (pattern, english, nested) in DynamicPatterns)
        {
            var match = pattern.Match(text);
            if (!match.Success) continue;
            var result = english;
            for (var group = 1; group < match.Groups.Count; group++)
            {
                var value = match.Groups[group].Value;
                if (Array.IndexOf(nested, group) >= 0) value = TranslateDynamic(value);
                else if (group == 2 && english.Contains("not confirmed{2}")) value = value.Length > 0 ? $"; inventory incomplete because {value} archives failed or are unsupported" : "";
                result = result.Replace("{" + group + "}", value);
            }
            return result.Trim();
        }
        return text;
    }
    public static void SetLanguage(string language) => Language = language == "en" ? "en" : "vi";
    public static void Install()
    {
        if (_installed) return;
        _installed = true;
        EventManager.RegisterClassHandler(typeof(FrameworkElement), FrameworkElement.LoadedEvent,
            new RoutedEventHandler((sender, _) => { if (sender is DependencyObject d) ApplyElement(d); }), true);
        // Collapsed Expander content is not in the visual tree until it opens: localize it then.
        EventManager.RegisterClassHandler(typeof(System.Windows.Controls.Expander), System.Windows.Controls.Expander.ExpandedEvent,
            new RoutedEventHandler((sender, _) => { if (sender is System.Windows.Controls.Expander expander) expander.Dispatcher.BeginInvoke(new Action(() => Apply(expander)), System.Windows.Threading.DispatcherPriority.Loaded); }), true);
    }
    public static void Apply(DependencyObject root)
    {
        ApplyElement(root);
        for (var i = 0; i < VisualTreeHelper.GetChildrenCount(root); i++) Apply(VisualTreeHelper.GetChild(root, i));
    }
    private static void ApplyElement(DependencyObject element)
    {
        if (element is TextBlock) Literal(element, TextBlock.TextProperty);
        if (element is ContentControl) Literal(element, ContentControl.ContentProperty);
        if (element is HeaderedContentControl) Literal(element, HeaderedContentControl.HeaderProperty);
        if (element is FrameworkElement)
        {
            Literal(element, FrameworkElement.ToolTipProperty); Literal(element, FrameworkElement.TagProperty);
            Literal(element, System.Windows.Automation.AutomationProperties.NameProperty); Literal(element, System.Windows.Automation.AutomationProperties.HelpTextProperty);
        }
        if (element is DataGrid rowsGrid && RowHooked.TryGetValue(rowsGrid, out _) == false)
        {
            // Rows are realised later (and recycled): their templated labels are localized as each row loads.
            RowHooked.Add(rowsGrid, new object());
            rowsGrid.LoadingRow += (_, e) => rowsGrid.Dispatcher.BeginInvoke(new Action(() => Apply(e.Row)), System.Windows.Threading.DispatcherPriority.Loaded);
        }
        if (element is DataGrid grid)
            foreach (var column in grid.Columns)
            {
                if (!ColumnHeaders.TryGetValue(column, out var original))
                {
                    if (column.Header is not string header || !English.ContainsKey(header)) continue;
                    ColumnHeaders.Add(column, original = header);
                }
                column.Header = Translate(original);
            }
    }
    private static readonly ConditionalWeakTable<DataGridColumn, string> ColumnHeaders = new();
    private static readonly ConditionalWeakTable<DataGrid, object> RowHooked = new();
    private static void Literal(DependencyObject element, DependencyProperty property)
    {
        if (System.Windows.Data.BindingOperations.IsDataBound(element, property)) return;
        var originals = Originals.GetOrCreateValue(element);
        if (!originals.TryGetValue(property, out var original))
        {
            // Values written by a template/style are not "local"; read the effective value so templated cells and rows localize too.
            var raw = element.ReadLocalValue(property);
            if (raw is not string) raw = element.GetValue(property);
            if (raw is not string text || !English.ContainsKey(text)) return;
            originals[property] = original = text;
        }
        element.SetCurrentValue(property, Translate(original));
    }
}
