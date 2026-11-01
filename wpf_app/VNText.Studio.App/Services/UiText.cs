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
        ["Tài nguyên xử lý trên máy"] = "On-device resources",
        ["Chuẩn bị tài nguyên sau khi cài ứng dụng"] = "Prepare resources after installation",
        ["Tải tất cả tài nguyên"] = "Download all resources",
        ["Kiểm tra tài nguyên"] = "Check resources",
        ["Chọn SDK đã cài…"] = "Choose installed SDK…",
        ["Mở tài nguyên trong Cài đặt"] = "Open resources in Settings",
        ["Tìm ảnh có chữ và dịch tất cả"] = "Find text images and translate all",
        ["Chọn ảnh để sửa riêng"] = "Choose an image to edit",
        ["Tìm ảnh có chữ và dịch tự động theo lô. Chỉ sửa ảnh khi bạn chưa hài lòng với kết quả."] = "Find text-bearing images and translate them automatically. Edit only results you want to improve.",
        ["Chép nhật ký"] = "Copy log",
        ["Lần lấy text"] = "Extraction run",
        ["{0} dòng nhật ký"] = "{0} log lines",
        ["Đang chạy"] = "Running",
        ["Bị gián đoạn"] = "Interrupted",
        ["Ảnh tĩnh PNG/JPEG/WebP. Tự nhận diện chữ tiếng Anh, dịch và dựng bản nháp khi nền phù hợp. Chỉ xuất ảnh đã phát hiện chữ; nền phức tạp dùng bản nháp nền ước lượng được đánh dấu riêng để bạn xem kết quả. OCR, duyệt và dựng ảnh chỉ đọc ảnh gốc và ghi kết quả vào thư mục xuất riêng. Chỉ bước “Cài gói vào bản sao game…” ghi vào một BẢN SAO game do bạn chọn (có bản lưu và kiểm hash đọc lại); thư mục game gốc không bị ghi, và bản sao trùng hoặc nằm trong game gốc sẽ bị từ chối."] = "Static PNG/JPEG/WebP images. Detect English text, translate and render previews automatically. Only images with detected text are exported; estimated backgrounds are labelled for inspection. OCR and rendering preserve source images and write separate output. Only Install into a game copy writes to the copy you select, with backup and hash verification. The original game and overlapping source/copy paths are protected.",
        ["Vùng chữ phủ toàn ảnh; không đủ nền để dựng bản nháp an toàn."] = "The text region covers the whole image; there is not enough surrounding background for a safe preview.",
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
        ["Nhật ký"] = "Journal",
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
        ["CSV đã thay đổi bên ngoài — hãy tải lại trước khi lưu"] = "The CSV was changed outside the app — reload it before saving",
        ["Hoặc chọn file asset / bundle"] = "Or choose an asset / bundle file",
        ["Chọn thư mục xuất gói dịch"] = "Choose the translation package output folder",
        ["Chọn tệp CSV"] = "Choose a CSV file",
        ["Chọn thư mục Ren'Py 8.5.3 đã cài"] = "Choose the installed Ren'Py 8.5.3 folder",
        ["1 dòng"] = "1 row",
        ["{0} dòng"] = "{0} rows",
        ["Sẵn sàng dịch · {0} · đã có bản dịch {1}"] = "Ready to translate · {0} · translated so far {1}",
        ["{0} · lần dịch trước đã hủy; chạy lại để dịch tiếp"] = "{0} · the previous run was cancelled; run again to continue",
        ["Dịch tự động đang bị khóa — {0}"] = "Auto translate is locked — {0}",
        ["Không có dòng text để dịch • {0} ảnh đã OCR"] = "No text rows to translate • {0} images OCR’d",
        [", {0} bản dịch nháp"] = ", {0} draft translations",
        [" — bấm “Dịch ảnh…”, rồi duyệt, dựng và cài ảnh trong mục Text trong ảnh."] = " — press “Translate image…”, then approve, render and install the images in Text in images.",
        ["ETA: {0}"] = "ETA: {0}",
        ["{0} {1}"] = "{0} {1}",
        ["Không mở được review: {0}"] = "Could not open the review: {0}",
        ["Đã lưu review riêng: {0}"] = "Review saved separately: {0}",
        ["Lưu review lỗi: {0}"] = "Saving the review failed: {0}",
        ["Chưa hoàn tất: {0}"] = "Not finished: {0}",
        ["Không đọc được kết quả ảnh: {0}"] = "Could not read the image result: {0}",
        ["{0}× {1}"] = "{0}× {1}",
        ["Sẵn sàng đóng gói {0} dòng; {1} dòng bị chặn."] = "Ready to package {0} rows; {1} rows are blocked.",
        ["Kiểm tra CSV để xem dòng hợp lệ / bị chặn trước khi patch."] = "Check the CSV to see eligible / blocked rows before patching.",
        ["Có thay đổi chưa lưu — bấm «Lưu CSV» trước khi patch."] = "Unsaved changes — press «Save CSV» before patching.",
        ["Chỉnh translation trực tiếp; Patch dùng file đã lưu."] = "Edit translations directly; Patch uses the saved file.",
        ["Thiết lập giao diện, dữ liệu và cập nhật."] = "Set up the interface, data and updates.",
        ["Có thể dịch tiếp hoặc chuyển sang Tạo patch."] = "You can keep translating or switch to Create patch.",
        ["Tạo patch Việt hóa"] = "Create the Vietnamese patch",
        ["Đóng gói bản dịch thành patch cài vào game."] = "Package the translation as a patch to install into the game.",
        ["Workflow hoàn tất"] = "Workflow finished",
        ["Gói dịch và patch đã sẵn sàng. Có thể chạy lại bất kỳ bước nào."] = "The translation package and patch are ready. You can rerun any step.",
        ["Bước 2/3: Trạng thái dịch chưa được xác minh — pending {0}, review {1}; chưa thể Patch"] = "Step 2/3: The translation state is not verified — pending {0}, review {1}; Patch is not possible yet",
        ["Bước 2/3: Dịch một phần — pending {0}, review {1}, blocked {2}"] = "Step 2/3: Partly translated — pending {0}, review {1}, blocked {2}",
        ["Bước 1/3: Lấy text — chưa có translation.csv"] = "Step 1/3: Extract text — no translation.csv yet",
        ["Bước 2/3: Dịch tự động — cần bản dịch trong translation.csv"] = "Step 2/3: Auto translate — translations are needed in translation.csv",
        ["Bước 3/3: Tạo patch — cần translation.csv có bản dịch"] = "Step 3/3: Create the patch — translation.csv needs translations",
        ["Bước 3/3: Tạo patch — đóng gói bản dịch"] = "Step 3/3: Create the patch — package the translation",
        ["Hoàn tất — gói dịch và patch đã sẵn sàng"] = "Finished — the translation package and patch are ready",
        ["Bước 1/3: Lấy text"] = "Step 1/3: Extract text",
        ["Đang chạy: Tạo patch…"] = "Running: Create patch…",
        ["Đang tạo patch…"] = "Creating the patch…",
        ["CSV chưa hợp lệ"] = "The CSV is not valid yet",
        ["CSV chưa sẵn sàng"] = "The CSV is not ready",
        ["Không có dòng hợp lệ để patch"] = "No eligible row to patch",
        ["Lỗi — {0}"] = "Error — {0}",
        ["Đang hủy…"] = "Cancelling…",
        ["Chưa gửi được yêu cầu hủy"] = "The cancel request could not be sent yet",
        ["Hủy vẫn đang chờ tác vụ dừng an toàn"] = "The cancel is still waiting for the task to stop safely",
        ["Chưa chọn game"] = "No game chosen",
        ["Đang kiểm tra…"] = "Checking…",
        ["Cài cập nhật"] = "Install update",
        ["Đã cập nhật"] = "Updated",
        ["Kiểm tra lại"] = "Check again",
        ["Đang kiểm tra cập nhật…"] = "Checking for updates…",
        ["Chưa thể kiểm tra. Hãy thử lại sau."] = "Cannot check right now. Try again later.",
        ["Không thể kiểm tra bản cập nhật."] = "The update check failed.",
        ["Không thể kiểm tra bản cập nhật: {0}"] = "The update check failed: {0}",
        ["Bạn đang dùng phiên bản mới nhất."] = "You are using the latest version.",
        ["Có bản cập nhật mới; chưa tải gói."] = "A new update is available; the package is not downloaded yet.",
        ["Đã kiểm tra gói. Sẵn sàng cập nhật."] = "The package was verified. Ready to update.",
        ["Bản cập nhật này cần bộ cài mới."] = "This update needs a new installer.",
        ["Chưa thể kiểm tra cập nhật."] = "The update cannot be checked yet.",
        ["Đóng VNText Studio và áp dụng bản cập nhật?"] = "Close VNText Studio and apply the update?",
        ["Đóng VNText Studio và áp dụng bản cập nhật WPF ổn định v{0}?"] = "Close VNText Studio and apply the stable WPF update v{0}?",
        ["Không thể khởi chạy updater: {0}"] = "The updater could not be started: {0}",
        ["Không thể khởi chạy updater đã xác minh: {0}"] = "The verified updater could not be started: {0}",
        ["Tác vụ đang chạy. Bạn có muốn yêu cầu hủy an toàn rồi thoát sau khi worker báo kết thúc không? Ứng dụng sẽ tiếp tục chờ nếu worker chưa dừng."] = "A task is running. Do you want to request a safe cancel and exit once the worker reports it has finished? The app keeps waiting if the worker has not stopped.",
        ["Tác vụ chưa hoàn tất"] = "Task not finished",
        ["CSV có thay đổi chưa lưu. Chọn Lưu để kiểm tra và lưu trước khi thoát, Bỏ thay đổi để thoát và bỏ phần đang sửa, hoặc Hủy để tiếp tục làm việc."] = "The CSV has unsaved changes. Choose Save to check and save before exiting, Discard changes to exit and drop the edits, or Cancel to keep working.",
        ["CSV chưa lưu"] = "CSV not saved",
        ["Danh sách từ được lưu cùng gói dịch."] = "The term list is saved with the translation package.",
        ["Chọn file dịch trước khi thêm thuật ngữ."] = "Choose a translation file before adding terms.",
        ["Đã lưu {0} thuật ngữ."] = "Saved {0} terms.",
        ["Nhập từ gốc và cách dịch ưu tiên."] = "Enter the source word and its preferred translation.",
        ["Bản dịch cần giữ nguyên ký hiệu và xuống dòng của từ gốc."] = "The translation must keep the symbols and line breaks of the source word.",
        ["Đã lưu glossary: {0} → {1}"] = "Saved glossary: {0} → {1}",
        ["Không lưu được glossary: {0}"] = "Could not save the glossary: {0}",
        ["Xóa thuật ngữ “{0}”?"] = "Delete the term “{0}”?",
        ["Xác nhận xóa"] = "Confirm deletion",
        ["Lỗi worker"] = "Worker error",
        ["Lỗi worker — không khởi động được Python worker"] = "Worker error — the Python worker could not be started",
        ["Đang kiểm tra translation.csv và manifest…"] = "Checking translation.csv and the manifest…",
        ["Chọn gói dịch có translation.csv và manifest.json hợp lệ."] = "Choose a translation package with a valid translation.csv and manifest.json.",
        ["Đang kiểm tra gói dịch…"] = "Checking the translation package…",
        ["Lỗi kiểm tra gói"] = "Package check error",
        ["Bước: {0}"] = "Step: {0}",
        ["Mục: {0}"] = "Item: {0}",
        ["Ước tính còn: {0}"] = "Estimated remaining: {0}",
        ["Đã chạy {0}"] = "Ran {0}",
        ["Trước: {0}"] = "Before: {0}",
        ["Gói có {0:N0} ảnh: {1:N0} đã OCR, {2:N0} bản dịch nháp, {3:N0} chưa OCR được (cần xem tay). Để duyệt và cài, chọn ảnh thật trong thư mục game (không phải bản sao trong gói)."] = "This package has {0:N0} images: {1:N0} OCR-ready, {2:N0} translation drafts, {3:N0} not OCR-ready (manual review needed). To review and install, select the real image in the game folder (not the copy inside the package).",
        ["Đã hủy {0}. Ảnh gốc được giữ nguyên; kết quả hủy không được áp dụng vào màn hình này, nhưng phần đã ghi an toàn (nếu có) có thể còn trong thư mục xuất."] = "Cancelled {0}. The original image is untouched; the cancelled result is not applied to this screen, but anything already written safely (if any) may remain in the output folder.",
        ["{0} region cần review; tọa độ theo pixel ảnh gốc. Chọn đúng một chế độ nền cho từng vùng trước render."] = "{0} regions need review; coordinates are in source-image pixels. Choose exactly one background mode for each region before rendering.",
        ["Chưa thể {0}: chưa có ảnh dựng/gói khớp với review hiện tại. Dựng lại ảnh từ review đã duyệt trước."] = "Cannot {0}: there is no rendered image/package matching the current review. Render again from the approved review first.",
        ["Đang có tác vụ chạy; chưa thể {0}."] = "A task is running; cannot {0} yet.",
        ["Một tác vụ khác đang chạy ({0}) — chờ xong hoặc bấm Hủy trước khi dùng ảnh."] = "Another task is running ({0}) — wait for it to finish or press Cancel before using images.",
        ["Đang chạy: {0}."] = "Running: {0}.",
        ["Sau: {0}"] = "After: {0}",
        ["Thay thế {0} lần trong {1} dòng?"] = "Replace {0} times in {1} rows?",
        ["Tìm: {0}"] = "Find: {0}",
        ["Tìm: {0}\nThay bằng: {1}"] = "Find: {0}\nReplace with: {1}",
        ["Thay bằng: {0}"] = "Replace with: {0}",
        ["Chỉ sửa cột Bản dịch; cột Nguyên bản/key giữ nguyên."] = "Only the Translation column is edited; the Source/key columns stay unchanged.",
        ["Xóa cột translation của {0} dòng bị Patch Gate chặn?"] = "Clear the translation column of {0} rows blocked by the Patch Gate?",
        ["Chỉ xóa bản dịch — giữ nguyên key và source."] = "Only the translation is cleared — key and source stay.",
        ["Dịch lại {0} dòng bằng {1}?"] = "Retranslate {0} rows with {1}?",
        ["Chỉ các dòng đã chọn hoặc đang bị gate chặn (cấu trúc)."] = "Only the selected rows or those blocked by the gate (structure).",
        ["Chưa dịch"] = "Untranslated",
        ["Chỉ dòng lỗi"] = "Error rows only",
        ["Đã dịch"] = "Translated",
        ["Sẽ patch"] = "Will be patched",
        ["Trong review_only.csv (cần xem lại thủ công)"] = "In review_only.csv (needs manual review)",
        ["Chưa có bản dịch trong translation.csv"] = "No translation in translation.csv yet",
        ["Dòng synonym — dịch thủ công"] = "Synonym row — translate manually",
        ["Mất/sai placeholder {…}"] = "Missing/wrong placeholder {…}",
        ["Hỏng tag <…>"] = "Broken tag <…>",
        ["Synonym sai tiền tố"] = "Synonym with a wrong prefix",
        ["Synonym sai số biến thể"] = "Synonym with a wrong variant count",
        ["Sai số \\n"] = "Wrong \\n count",
        ["Sai số ký hiệu ♡"] = "Wrong ♡ symbol count",
        ["Sai số biến thể RandPick"] = "Wrong RandPick variant count",
        ["Hậu tố Anh sau placeholder"] = "English suffix after a placeholder",
        ["Validation MT"] = "MT validation",
        ["Gói dùng profile legacy không được hỗ trợ; hãy extract lại"] = "The package uses an unsupported legacy profile; extract again",
        ["Locator tham chiếu ngoài không được hỗ trợ; hãy extract lại"] = "An external-reference locator is not supported; extract again",
        ["Dịch lại vẫn bị chặn"] = "Retranslation is still blocked",
        ["Trong review_only.csv"] = "In review_only.csv",
        ["Ren'Py — native overlay (copy vào game root)"] = "Ren'Py — native overlay (copy into the game root)",
        ["Ren'Py overlay đã sẵn sàng — copy COPY_TO_GAME_ROOT vào game root."] = "The Ren'Py overlay is ready — copy COPY_TO_GAME_ROOT into the game root.",
        ["Patch văn bản thường"] = "Plain-text patch",
        ["Patch Unity/Naninovel"] = "Unity/Naninovel patch",
        ["Patch"] = "Patch",
        ["{0} đã sẵn sàng tại {1}. Mở VNTextPatchInstaller.exe để cài/gỡ."] = "{0} is ready at {1}. Open VNTextPatchInstaller.exe to install/uninstall.",
        ["Payload đã qua read-back tại {0}, nhưng thiếu installer. Chưa sẵn sàng cài/gỡ; cần VNTextPatchInstaller.exe phù hợp trước khi phân phối."] = "The payload passed read-back at {0}, but the installer is missing. It is not ready to install/uninstall; a matching VNTextPatchInstaller.exe is needed before distribution.",
        ["Xong: patch nằm tại {0}. Mở VNTextPatchInstaller.exe để cài/gỡ."] = "Done: the patch is at {0}. Open VNTextPatchInstaller.exe to install/uninstall.",
        ["Ren'Py native overlay đã sẵn sàng."] = "The Ren'Py native overlay is ready.",
        ["1. Đóng game."] = "1. Close the game.",
        ["2. Mở thư mục gói: {0}"] = "2. Open the package folder: {0}",
        ["3. Copy toàn bộ nội dung bên trong vào game root: {0}"] = "3. Copy everything inside into the game root: {0}",
        ["4. Giữ nguyên cấu trúc game/tl/vietnamese/ và game/."] = "4. Keep the game/tl/vietnamese/ and game/ structure unchanged.",
        ["Kiểm tra phiên bản mới khi bạn sẵn sàng."] = "Check for a new version when you are ready.",
        ["Đang kiểm tra mô hình dịch."] = "Checking the translation model.",
        ["Bước 1/3: Chọn game — chưa có đường dẫn game / asset"] = "Step 1/3: Choose a game — no game / asset path yet",
        ["Bước: Chưa bắt đầu"] = "Step: Not started",
        ["Chọn SDK 8.5.3 đã cài hoặc tải SDK để lấy lời thoại. Tiếp tục khi chưa có SDK chỉ quét tĩnh để xuất danh sách cần xem lại: không dịch, không tạo patch…"] = "Choose an installed SDK 8.5.3 or download the SDK to extract the dialogue. Continuing without an SDK only scans statically to export a list for review: no translation, no patch…",
        ["Chưa có thuật ngữ. Thêm từ bạn muốn dịch thống nhất."] = "No terms yet. Add words you want translated consistently.",
        ["Chưa xác định engine"] = "Engine not identified yet",
        ["Khi lấy text, app tự dùng công cụ đã có; nếu chưa có, kết quả sẽ được báo là chưa đầy đủ."] = "When extracting text the app uses the tools already installed; if none exist, the result is reported as incomplete.",
        ["Mục: —"] = "Item: —",
        ["Đã chạy 0 giây"] = "Ran 0 seconds",
        ["Ước tính còn: "] = "Estimated remaining: ",
        ["Bản dịch được kiểm tra tự động."] = "Translations are checked automatically.",
        ["file đã đổi bên ngoài"] = "the file changed outside the app",
        ["Cảnh báo: {0} dòng cần xem lại"] = "Warning: {0} rows need review",
        ["Phiên bản hiện tại {0}, gói mới đã được kiểm tra."] = "Current version {0}, the new package has been verified.",
        ["Phiên bản hiện tại {0}, đã có phiên bản mới."] = "Current version {0}, a newer version is available.",
        ["Chưa mở translation.csv"] = "No translation.csv open",
        ["Nhập chuỗi rồi bấm Xem trước."] = "Enter a string, then press Preview.",
        ["Chưa chọn file…"] = "No file chosen…",
        ["Chọn một dòng để xem mã kỹ thuật."] = "Select a row to see its technical key.",
        ["Mã dòng: {0}"] = "Row key: {0}",
        ["Đã chọn {0} dòng · Mã đầu tiên: {1}"] = "{0} rows selected · First key: {1}",
        [" Bản nháp của bạn vẫn được giữ và file ngoài không bị ghi đè; bấm “Tải lại” để chọn Lưu, Bỏ hoặc Hủy."] = " Your draft is kept and the outside file was not overwritten; press “Reload” to choose Save, Discard or Cancel.",
        [" Bản nháp của bạn vẫn được giữ; sửa lỗi rồi lưu lại."] = " Your draft is kept; fix the problem and save again.",
        ["không rõ lý do"] = "reason unknown",
        ["Không lưu được: {0}.{1}"] = "Could not save: {0}.{1}",
        ["Đã đổi nội dung lọc — hãy xem trước lại."] = "The filter text changed — preview again.",
        ["Đã đổi bộ lọc — hãy xem trước lại."] = "The filter changed — preview again.",
        ["Chưa lưu · {0} câu đã sửa"] = "Unsaved · {0} edited",
        ["Có thay đổi chưa lưu"] = "Unsaved changes",
        ["Chưa có bản dịch — chuyển sang Dịch tự động để bắt đầu."] = "No translations yet — switch to Auto translate to start.",
        ["Một số câu cần xem lại trước khi tạo gói. Chọn câu để xem lý do và chỉnh bản dịch."] = "Some lines need review before creating the package. Select a line to see why and edit the translation.",
        ["Bản dịch được kiểm tra tự động. Bạn có thể chỉnh ngữ cảnh, xưng hô và cách diễn đạt."] = "Translations are checked automatically. You can adjust context, forms of address and wording.",
        ["Đã thay đổi chuỗi tìm — hãy xem trước lại."] = "The search string changed — preview again.",
        ["Đã thay đổi chuỗi thay thế — hãy xem trước lại."] = "The replacement string changed — preview again.",
        ["Đã đổi phạm vi — hãy xem trước lại."] = "The scope changed — preview again.",
        ["Dòng đang lọc"] = "Filtered rows",
        ["dòng đang lọc"] = "filtered rows",
        ["Toàn bộ CSV"] = "Entire CSV",
        ["toàn bộ CSV"] = "the entire CSV",
        ["Chưa có câu"] = "No lines yet",
        ["Hiện {0} / {1} câu · Đã dịch {2} · Chưa dịch {3} · Cần xem lại {4}"] = "Showing {0} / {1} lines · Translated {2} · Untranslated {3} · Needs review {4}",
        ["Đang chạy tác vụ — tạm khóa chỉnh sửa CSV để tác vụ không ghi đè thay đổi của bạn."] = "A task is running — CSV editing is locked so the task cannot overwrite your changes.",
        ["Đang kiểm tra và lưu {0} dòng…"] = "Checking and saving {0} rows…",
        ["Đã hủy tải CSV ({0})"] = "CSV load cancelled ({0})",
        ["Chưa chọn translation.csv"] = "No translation.csv chosen",
        ["CSV có thay đổi chưa lưu. Lưu trước khi mở lại hoặc chọn file khác?"] = "The CSV has unsaved changes. Save before reopening or choosing another file?",
        ["Thay đổi CSV chưa lưu"] = "Unsaved CSV changes",
        ["CSV có thay đổi chưa lưu. Lưu trước khi đổi nguồn hoặc thư mục xuất?"] = "The CSV has unsaved changes. Save before changing the source or output folder?",
        ["Đang tải CSV…"] = "Loading CSV…",
        ["Không mở được CSV"] = "Could not open the CSV",
        ["CSV đã chọn"] = "the chosen CSV",
        ["chưa có file nào đang mở"] = "no file is open",
        ["đang giữ {0}"] = "keeping {0}",
        ["Không mở được {0}: {1} ({2})."] = "Could not open {0}: {1} ({2}).",
        ["Cảnh báo: {0} dòng cần xem lại — {1}. Xem cột Trạng thái hoặc lọc “Chỉ dòng lỗi”."] = "Warning: {0} rows need review — {1}. See the Status column or filter “Error rows only”.",
        ["Đã mở {0} dòng — {1}"] = "Opened {0} rows — {1}",
        ["Đang tải CSV… {0}/{1}"] = "Loading CSV… {0}/{1}",
        ["Đã mở {0} dòng — {1} (đang kiểm tra…)"] = "Opened {0} rows — {1} (checking…)",
        ["CSV đã được chỉnh sửa — hãy xem trước lại."] = "The CSV was edited — preview again.",
        ["Chưa chọn file CSV."] = "No CSV file chosen.",
        ["Nhập chuỗi cần tìm."] = "Enter the string to find.",
        ["Chuỗi tìm/thay, bộ lọc hoặc dữ liệu đã đổi trong lúc xem trước — hãy xem trước lại."] = "The find/replace text, filter or data changed during the preview — preview again.",
        ["Không xem trước được thao tác thay thế."] = "The replacement could not be previewed.",
        ["Không tìm thấy chuỗi trong cột Bản dịch."] = "The string was not found in the Translation column.",
        ["Sẽ thay {0} lần trong {1} dòng ({2})."] = "Will replace {0} times in {1} rows ({2}).",
        ["Trước: {0}\nSau: {1}"] = "Before: {0}\nAfter: {1}",
        ["Hãy lưu hoặc tải lại chỉnh sửa hiện tại trước khi áp dụng thay thế hàng loạt."] = "Save or reload the current edits before applying the bulk replacement.",
        ["Chuỗi tìm/thay, bộ lọc hoặc dữ liệu đã đổi trong lúc kiểm tra — hãy xem trước lại."] = "The find/replace text, filter or data changed during the check — preview again.",
        ["CSV đã thay đổi — hãy xem trước thao tác lần nữa."] = "The CSV changed — preview the operation again.",
        ["Thay thế {0} lần trong {1} dòng?\n\n"] = "Replace {0} times in {1} rows?\n\n",
        ["Tìm: {0}\nThay bằng: {1}\n"] = "Find: {0}\nReplace with: {1}\n",
        ["Chỉ sửa cột Bản dịch; cột Nguyên bản/key giữ nguyên.\n"] = "Only the Translation column is edited; the Source/key columns stay unchanged.\n",
        ["Ứng dụng sẽ tạo bản lưu khôi phục và kiểm tra file sau khi lưu."] = "The app creates a recovery copy and checks the file after saving.",
        ["Xác nhận thay thế hàng loạt"] = "Confirm bulk replacement",
        ["Thay thế hàng loạt thất bại."] = "The bulk replacement failed.",
        ["Đã áp dụng thay thế hàng loạt."] = "The bulk replacement was applied.",
        ["Đã thay {0} lần trong {1} dòng. Có thể hoàn tác; đã tạo bản lưu khôi phục."] = "Replaced {0} times in {1} rows. You can undo it; a recovery copy was created.",
        ["Hãy lưu hoặc tải lại chỉnh sửa hiện tại trước khi hoàn tác."] = "Save or reload the current edits before undoing.",
        ["Khôi phục CSV về trước lần thay thế hàng loạt gần nhất?"] = "Restore the CSV to before the latest bulk replacement?",
        ["Xác nhận hoàn tác"] = "Confirm undo",
        ["Hoàn tác thất bại."] = "The undo failed.",
        ["Đã hoàn tác — khôi phục {0} dòng từ bản lưu khôi phục."] = "Undone — restored {0} rows from the recovery copy.",
        ["Đang tải CSV — chờ xong rồi kiểm tra."] = "Loading the CSV — wait for it to finish, then check.",
        ["Chưa có dữ liệu để kiểm tra."] = "There is no data to check yet.",
        ["Đang kiểm tra CSV…"] = "Checking the CSV…",
        ["Kiểm tra thất bại"] = "The check failed",
        ["Chưa có bản dịch — chuyển sang Dịch tự động để dịch CSV."] = "No translations yet — switch to Auto translate to translate the CSV.",
        ["Chưa lưu — đang có tác vụ chạy trên gói này; hãy đợi tác vụ kết thúc hoặc hủy tác vụ rồi lưu lại."] = "Not saved — a task is running on this package; wait for it to finish or cancel it, then save again.",
        ["Đang tải CSV — chưa thể lưu."] = "Loading the CSV — cannot save yet.",
        ["Chưa chọn file CSV để lưu."] = "No CSV file chosen to save.",
        ["Chưa lưu — không xác minh được CSV gốc; hãy tải lại file."] = "Not saved — the original CSV could not be verified; reload the file.",
        ["không xác minh được CSV gốc"] = "the original CSV could not be verified",
        ["Chưa lưu — {0} key trùng"] = "Not saved — {0} duplicate keys",
        ["{0} key trùng — {1}"] = "{0} duplicate keys — {1}",
        ["Đang kiểm tra CSV trước khi lưu…"] = "Checking the CSV before saving…",
        ["Lưu thất bại: {0}"] = "Save failed: {0}",
        ["Không thể lưu — kiểm tra thất bại"] = "Cannot save — the check failed",
        ["Lưu thất bại"] = "Save failed",
        ["Lưu thất bại — không nhận được mã xác minh file đã lưu. Hãy tải lại CSV trước khi tiếp tục."] = "Save failed — no verification code for the saved file was received. Reload the CSV before continuing.",
        ["không nhận được mã xác minh file đã lưu"] = "no verification code for the saved file was received",
        ["Đã lưu {0} dòng — {1}"] = "Saved {0} rows — {1}",
        ["{0} (UTF-8 BOM, giữ nguyên cột)"] = "{0} (UTF-8 BOM, columns unchanged)",
        ["{0}; còn chỉnh sửa mới chưa lưu"] = "{0}; newer edits are not saved yet",
        ["Đã lưu CSV"] = "CSV saved",
        ["Hãy lưu hoặc tải lại chỉnh sửa hiện tại trước khi xóa bản dịch lỗi."] = "Save or reload the current edits before clearing faulty translations.",
        ["Không xem trước được"] = "Could not preview",
        ["Không có dòng lỗi cấu trúc nào có bản dịch để xóa."] = "No structurally faulty row has a translation to clear.",
        ["Xóa cột translation của {0} dòng bị Patch Gate chặn?\n\n"] = "Clear the translation column of {0} rows blocked by the Patch Gate?\n\n",
        ["Chỉ xóa bản dịch — giữ nguyên key và source.\n"] = "Only the translation is cleared — key and source stay.\n",
        ["File backup sẽ được tạo trước khi ghi."] = "A backup file is created before writing.",
        ["Xác nhận xóa bản dịch lỗi"] = "Confirm clearing faulty translations",
        ["Xóa bản dịch thất bại"] = "Clearing the translations failed",
        ["Đã xóa bản dịch {0} dòng — {1}"] = "Cleared the translations of {0} rows — {1}",
        ["Worker đang bận — hãy đợi hoặc hủy tác vụ hiện tại."] = "The worker is busy — wait or cancel the current task.",
        ["Không có dòng lỗi cấu trúc nào để dịch lại."] = "No structurally faulty row to retranslate.",
        ["Dịch lại {0} dòng bằng {1}?\n\n"] = "Retranslate {0} rows with {1}?\n\n",
        ["Chỉ các dòng đã chọn hoặc đang bị gate chặn (cấu trúc).\n"] = "Only the selected rows or those blocked by the gate (structure).\n",
        ["Backup CSV sẽ được tạo trước khi ghi. Validation chạy sau khi dịch."] = "A CSV backup is created before writing. Validation runs after translating.",
        ["Xác nhận dịch lại dòng lỗi"] = "Confirm retranslating faulty rows",
        ["CSV có thay đổi chưa lưu. Lưu trước khi dịch lại?"] = "The CSV has unsaved changes. Save before retranslating?",
        ["Lưu CSV"] = "Save CSV",
        ["Đang dịch lại {0} dòng lỗi…"] = "Retranslating {0} faulty rows…",
        ["File CSV đã đổi sau khi dịch xong — bấm Tải lại để xem bản mới (thay đổi chưa lưu được giữ nguyên)."] = "The CSV file changed after translating finished — press Reload to see the new version (unsaved changes are kept).",
        ["File không tồn tại"] = "The file does not exist",
        ["CSV không có dòng dữ liệu"] = "The CSV has no data rows",
        ["Phải là file .csv"] = "Must be a .csv file",
        ["Thiếu manifest.json cùng thư mục với translation.csv"] = "manifest.json is missing next to translation.csv",
        ["CSV trống hoặc thiếu header"] = "The CSV is empty or has no header",
        ["Header thiếu cột bắt buộc: key, source_text, translation"] = "The header lacks required columns: key, source_text, translation",
        ["CSV hợp lệ nhưng chưa có bản dịch (0/{0} dòng)"] = "The CSV is valid but has no translations yet (0/{0} rows)",
        ["Hợp lệ — {0}/{1} câu đã có bản dịch"] = "Valid — {0}/{1} lines have translations",
        ["Không đọc được CSV: {0}"] = "Could not read the CSV: {0}",
        ["Chưa chọn thư mục xuất"] = "No output folder chosen",
        ["Chưa có bản dịch"] = "No translation yet",
        ["Rác lặp từ/ký tự"] = "Repeated junk words/characters",
        ["HTML/entity rác"] = "HTML/entity junk",
        ["Synonym — dịch thủ công"] = "Synonym — translate manually",
        ["Hỏng tag"] = "Broken tag",
        ["translation.csv không tồn tại"] = "translation.csv does not exist",
        ["Thiếu manifest.json cùng thư mục"] = "manifest.json is missing in the same folder",
        ["Không khởi chạy được Python worker"] = "The Python worker could not be started",
        ["Kiểm tra patch thất bại"] = "The patch check failed",
        ["Lỗi kiểm tra patch: {0}"] = "Patch check error: {0}",
        ["CSV trống"] = "The CSV is empty",
        ["Header CSV thiếu cột bắt buộc, trùng hoặc không hợp lệ"] = "The CSV header lacks required columns, has duplicates or is invalid",
        ["CSV có key trống hoặc trùng"] = "The CSV has empty or duplicate keys",
        ["Dòng CSV có số cột không khớp header"] = "A CSV row has a different column count than the header",
        ["Validate thất bại"] = "Validation failed",
        ["Preview thất bại"] = "Preview failed",
        ["Thao tác thất bại"] = "The operation failed",
        ["Preview thay thế thất bại"] = "The replacement preview failed",
        ["Thay thế thất bại"] = "The replacement failed",
        ["Không đọc được CSV"] = "Could not read the CSV",
        ["Không khởi chạy được Python"] = "Python could not be started",
        ["CSV editor API không trả output"] = "The CSV editor API returned no output",
        ["CSV / preflight"] = "CSV / preflight",
        ["Patch preflight"] = "Patch preflight",
        ["Cần CSV hợp lệ trước khi kiểm tra chất lượng patch."] = "A valid CSV is needed before the patch quality check.",
        ["Không thể cập nhật trạng thái CSV: {0}"] = "Could not update the CSV state: {0}",
        ["Dịch chưa hoàn tất — pending {0}, review {1}, blocked {2}. Chưa thể tạo Patch."] = "Translation is not finished — pending {0}, review {1}, blocked {2}. The patch cannot be created yet.",
        ["Kiểm tra patch: {0} hợp lệ, {1} bị chặn."] = "Patch check: {0} eligible, {1} blocked.",
        ["Kiểm tra patch: {0}"] = "Patch check: {0}",
        ["Không tìm thấy gói ZIP đã xuất. Hãy xuất lại gói ở tab Dịch rồi chọn CSV."] = "The exported ZIP package was not found. Export it again on the Translate tab, then choose the CSV.",
        ["Chọn translation.csv đã dịch để nhập"] = "Choose the translated translation.csv to import",
        ["Lưu gói Cloud Repair"] = "Save the Cloud Repair package",
        ["Cloud Repair ZIP (*.zip)|*.zip|Tất cả (*.*)|*.*"] = "Cloud Repair ZIP (*.zip)|*.zip|All files (*.*)|*.*",
        ["Tiếng Việt"] = "Vietnamese",
        ["Đang kiểm tra mô hình dịch…"] = "Checking the translation model…",
        ["Worker chưa sẵn sàng: {0}"] = "The worker is not ready: {0}",
        ["Đang tải lịch sử phát hành…"] = "Loading the release history…",
        ["Chưa có ghi chú được lưu. Hãy kết nối mạng và kiểm tra cập nhật để lưu ghi chú phát hành."] = "No saved notes yet. Connect to the network and check for updates to save the release notes.",
        ["Không mở được liên kết: {0}"] = "Could not open the link: {0}",
        ["Không khởi chạy được kiểm tra model."] = "The model check could not be started.",
        ["Kiểm tra model exit {0}: {1}"] = "Model check exit {0}: {1}",
        ["Mô hình dịch đã sẵn sàng."] = "The translation model is ready.",
        ["Chưa có mô hình dịch trên máy."] = "No translation model on this computer yet.",
        ["Không kiểm tra được mô hình dịch: {0}"] = "Could not check the translation model: {0}",
        ["Thư mục chưa có."] = "The folder does not exist yet.",
        ["Không mở được thư mục: {0}"] = "Could not open the folder: {0}",
        ["Không lưu được cài đặt; file hiện có được giữ nguyên: {0}"] = "Could not save the settings; the existing file is kept: {0}",
        ["Mô hình dịch"] = "Translation model",
        ["Mô hình OPUS-MT · INT8 · CTranslate2."] = "OPUS-MT model · INT8 · CTranslate2.",
        ["Khi bật, bản dịch cần được bạn xem và lưu xác nhận trước khi đưa vào gói dịch."] = "When on, translations must be reviewed and confirmed by you before they go into the package.",
        ["Python worker"] = "Python worker",
        ["Tác giả: Calanh"] = "Author: Calanh",
        ["Giấy phép: Apache-2.0"] = "License: Apache-2.0",
        ["Tìm trong CSV"] = "Search in CSV",
        ["Tìm trong toàn bộ CSV"] = "Search the whole CSV",
        ["Phạm vi thay thế"] = "Replacement scope",
        ["Đếm các dòng và lần thay thế trước khi áp dụng."] = "Counts the rows and replacements before applying.",
        ["MÃ DÒNG"] = "ROW KEY",
        ["Đóng Thuật ngữ ưu tiên"] = "Close Preferred terms",
        ["Cập nhật VNText Studio"] = "Update VNText Studio",
        ["Hủy rồi thoát"] = "Cancel and exit",
        ["Biểu thức chính quy"] = "Regular expression",
        ["Nhật ký — Khắc phục lỗi"] = "Journal — Troubleshooting",
        ["Đóng Nhật ký"] = "Close Journal",
        ["khắc phục lỗi"] = "troubleshooting",
        ["Tất cả"] = "All",
        ["Thông tin"] = "Info",
        ["Cảnh báo"] = "Warning",
        ["Mức"] = "Level",
        ["Tìm trong nhật ký"] = "Search the journal",
        ["Làm mới"] = "Refresh",
        ["Xóa tệp nhật ký {0}?"] = "Delete the journal file {0}?",
        ["Không đọc được nhật ký: {0}"] = "Could not read the journal: {0}",
        ["Chưa có tệp nhật ký"] = "No journal file yet",
        ["{0} bản ghi/trang"] = "{0} entries/page",
        ["{0} bản ghi · {1}/{2}"] = "{0} entries · {1}/{2}",
        ["Đang tải xuống..."] = "Downloading...",
        ["Khởi động lại"] = "Restart",
        ["Cập nhật ngay"] = "Update now",
        ["Có bản cập nhật mới"] = "A new update is available",
        ["Cập nhật thành công"] = "Update successful",
        ["Đóng {0}"] = "Close {0}",
        ["Hủy tải cập nhật"] = "Cancel the update download",
        ["Có gì mới"] = "What's new",
        ["Tính năng mới"] = "New features",
        ["Bỏ qua phiên bản này"] = "Skip this version",
        ["Không tải được cập nhật: {0}"] = "Could not download the update: {0}",
        ["Phát hành {0}"] = "Released {0}",
        ["Ghi chú phiên bản"] = "Release notes",
        ["Đã cập nhật thành công lên phiên bản v{0}."] = "Successfully updated to version v{0}.",
        [" gói mới đã được kiểm tra."] = " the new package has been verified.",
        [" đã có phiên bản mới."] = " a newer version is available.",
        ["Chưa có ghi chú phát hành. Kiểm tra cập nhật để xem thông tin mới nhất."] = "No release notes yet. Check for updates to see the latest information.",
        ["Đang tải xuống... {0}%"] = "Downloading... {0}%",
        ["✓  VNText Studio đã cập nhật lên v{0} và sẵn sàng sử dụng."] = "✓  VNText Studio was updated to v{0} and is ready to use.",
        ["✓  Phiên bản v{0} đã sẵn sàng. Hãy khởi động lại để áp dụng."] = "✓  Version v{0} is ready. Restart to apply it.",
        ["Để sau"] = "Later",
        ["Tải phiên bản {0}"] = "Download version {0}",
        ["Không mở được trang tải. Hãy thử lại khi trình duyệt sẵn sàng."] = "The download page could not be opened. Try again when the browser is ready.",
        ["Mở trang tải"] = "Open the download page",
        ["Chưa có ghi chú được lưu. Kết nối mạng và kiểm tra cập nhật để tải lịch sử; sau đó bạn có thể xem lại khi ngoại tuyến."] = "No saved notes yet. Connect to the network and check for updates to load the history; you can then read it offline.",
        ["Không"] = "No",
        ["Có"] = "Yes",
        ["Bỏ thay đổi"] = "Discard changes",
        ["Lưu"] = "Save",
        ["Đường dẫn ảnh/output không được qua link hoặc reparse point."] = "Image/output paths must not go through links or reparse points.",
        ["Chỉ hỗ trợ ảnh tĩnh PNG/JPEG/WebP; không xử lý ảnh động."] = "Only still PNG/JPEG/WebP images are supported; animated images are not processed.",
        ["Ảnh vượt 32 MiB; hãy chọn crop nhỏ hơn."] = "The image is larger than 32 MiB; choose a smaller crop.",
        ["Ảnh tăng kích thước vượt budget; dừng đọc."] = "The image grew beyond the size budget; reading stopped.",
        ["Ảnh quá lớn hoặc có nhiều frame; hãy chọn ảnh tĩnh/crop."] = "The image is too large or has several frames; choose a still image/crop.",
        ["Region cần x,y,width,height nguyên."] = "A region needs whole-number x, y, width and height.",
        ["Region nằm ngoài ảnh hoặc kích thước không hợp lệ."] = "The region is outside the image or has an invalid size.",
        ["OCR ảnh hiện cần Windows OCR và language pack tiếng Anh."] = "Image OCR currently needs Windows OCR and the English language pack.",
        ["OCR quá 60 giây; chưa có kết quả hoàn tất."] = "OCR took longer than 60 seconds; no finished result yet.",
        ["Chữ nghiêng cần xoay/crop và review thủ công trước OCR."] = "Tilted text needs rotating/cropping and a manual review before OCR.",
        ["Schema review ảnh không hợp lệ."] = "The image review schema is not valid.",
        ["Output phải là file PNG mới; không ghi đè ảnh gốc/output đã có."] = "The output must be a new PNG file; the original image/existing output is never overwritten.",
        ["Ảnh nguồn đã thay đổi; OCR/review lại trước render."] = "The source image changed; run OCR/review again before rendering.",
        ["Không có region đã duyệt hoặc quá 500 region."] = "There is no approved region, or more than 500 regions.",
        ["Render vượt 30 giây; giảm số region."] = "Rendering took longer than 30 seconds; reduce the number of regions.",
        ["Region chồng nhau; gộp/sửa crop rồi duyệt lại."] = "Regions overlap; merge/fix the crops and approve again.",
        ["Chọn đúng một cách render: nền phẳng, chữ trong suốt, màu đặc, hoặc clone nền mẫu."] = "Choose exactly one render mode: flat background, transparent text, solid color, or sample-background clone.",
        ["Chế độ chữ trong suốt cần region có cả pixel trong suốt và glyph nhìn thấy."] = "Transparent-text mode needs a region with both transparent pixels and visible glyphs.",
        ["Vùng chữ có alpha trong suốt; chọn giữ nền trong suốt hoặc xác nhận thay nền region bằng màu đặc."] = "The text area has transparent alpha; keep the transparent background or confirm replacing the region background with a solid color.",
        ["Cần duyệt text/crop trước render."] = "Approve the text/crop before rendering.",
        ["Bản dịch region cần text đã duyệt, tối đa 2000 ký tự."] = "A region translation needs approved text of at most 2000 characters.",
        ["Font size phải từ 6 đến 144."] = "The font size must be between 6 and 144.",
        ["Màu nền/chữ phải là RGB."] = "Background/text colors must be RGB.",
        ["Nền region không đủ phẳng theo màu đã chọn; hãy crop/chuẩn bị nền thủ công."] = "The region background is not flat enough for the chosen color; crop or prepare the background manually.",
        ["Bản dịch tràn region; sửa xuống dòng/font/region rồi duyệt lại."] = "The translation overflows the region; fix the line breaks/font/region and approve again.",
        ["Vùng nền mẫu phải tách khỏi vùng chữ cần thay."] = "The sample background area must be separate from the text area to replace.",
        ["Chọn thư mục game/ảnh để tìm ảnh."] = "Choose a game/image folder to search for images.",
        ["Inventory ảnh vượt budget; chọn thư mục ảnh nhỏ hơn."] = "The image inventory exceeded its budget; choose a smaller image folder.",
        ["Ảnh nguồn đã thay đổi trong khi OCR."] = "The source image changed during OCR.",
        ["Vùng OCR quá lớn để dựng ảnh tự động."] = "The OCR area is too large to render automatically.",
        ["Các vùng OCR chồng nhau."] = "The OCR areas overlap.",
        ["Nền phức tạp: chưa thể tự xóa chữ mà giữ hình nền."] = "Complex background: the text cannot be removed automatically while keeping the background image.",
        ["Vùng OCR không có chữ nhìn thấy."] = "The OCR area has no visible text.",
        ["Bản dịch rỗng hoặc quá dài."] = "The translation is empty or too long.",
        ["Bản dịch không vừa vùng chữ, cần thử lại ảnh rõ/lớn hơn."] = "The translation does not fit the text area; try a clearer/larger image.",
        ["Ảnh vượt 32 MiB."] = "The image is larger than 32 MiB.",
        ["Đã chạm giới hạn 512 MiB cho lần xử lý ảnh này."] = "The 512 MiB limit for this image run was reached.",
        ["Không nhận diện được chữ tiếng Anh trong ảnh."] = "No English text could be recognised in the image.",
        ["Ảnh có quá 500 vùng chữ."] = "The image has more than 500 text areas.",
        ["Số dòng bản dịch không khớp OCR."] = "The number of translated lines does not match the OCR.",
        ["Model chưa dịch được đầy đủ chữ trong ảnh."] = "The model could not translate all the text in the image.",
        ["Output ảnh vượt giới hạn 512 MiB."] = "The image output exceeds the 512 MiB limit.",
        ["Dịch ảnh"] = "Translate image",
        ["Đang xử lý"] = "Processing",
        ["CHƯA KIỂM TRA"] = "NOT CHECKED",
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
        ["Review cũ có nhiều chế độ nền — hãy chọn đúng một chế độ."] = "This older review has several background modes — choose exactly one.",
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
        ["Chưa chọn chế độ nền — hãy chọn một chế độ trước khi duyệt."] = "No background mode chosen — choose one before approving.",
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
        ["CSV vừa được lưu — hãy kiểm tra lại. Patch cũ còn trên đĩa là của bản trước; cần đóng gói lại cho bản này."] = "The CSV was just saved — check it again. The older patch on disk belongs to the previous version; build it again for this one.",
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
        ["Chưa có thuật ngữ nào. Nhập từ trong game và cách dịch ở trên, rồi bấm Thêm."] = "No terms yet. Enter a game word and its translation above, then press Add.",
        ["Nhập thuật ngữ đầu tiên"] = "Enter the first term",
        ["Chuẩn bị mô hình dịch và Ren’Py SDK trước khi chọn game. OCR dùng gói tiếng Anh của Windows."] = "Prepare the translation model and Ren’Py SDK before choosing a game. OCR uses the Windows English language pack.",
        ["Đang chuẩn bị tài nguyên… Có thể hủy và thử lại; game không bị thay đổi."] = "Preparing resources… You can cancel and retry; the game is not modified.",
        ["Đang kiểm tra tài nguyên…"] = "Checking resources…",
        ["Đã hủy chuẩn bị tài nguyên; có thể tải lại. Tài nguyên đã cài vẫn được giữ."] = "Resource setup was cancelled; you can download again. Installed resources are kept.",
        ["Đã kiểm tra tài nguyên."] = "Resources checked.",
        ["Tài nguyên đã sẵn sàng."] = "Resources are ready.",
        ["Tài nguyên chưa đầy đủ."] = "Resources are incomplete.",
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
        ["Nhật ký"] = "Journal",
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
        ["Xóa"] = "Delete",
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
        ("Windows OCR thất bại: ", "Windows OCR failed: "),
    ];
    // (regex, English template, groups that are themselves app messages/labels)
    private static readonly (System.Text.RegularExpressions.Regex Pattern, string English, int[] Nested)[] DynamicPatterns =
    [
        (new(@"^(\d+)% • Bước: (.+?)(?: • Mục: (.+?))?(?: • ETA: (.+))?$"), "{1}% • Step: {2}{3}{4}", [2]),
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

    // ---- App-owned dynamic messages: a catalog FORMAT KEY + the raw arguments, never a lookup of the interpolated sentence ----
    // The producer (view model/service) builds the visible Vietnamese text with Msg/Compose. The produced string instance is remembered
    // together with its format key and raw arguments (by reference, so a user string that merely looks the same is never matched).
    // At display time the format key is translated and formatted with the SAME raw arguments: paths, file names, user text, exception text
    // and numbers are inserted as they are and are never searched in the catalog. Only an argument explicitly typed Key(...) is a catalog key.
    private sealed record Produced(string Format, object?[]? Args, string[]? Parts);
    private static readonly System.Runtime.CompilerServices.ConditionalWeakTable<string, Produced> ProducedMessages = new();

    /// <summary>An argument that is itself a catalog key (a UI label/state word), translated on its own before it is inserted.</summary>
    public readonly record struct SemanticKey(string Vi);
    public static SemanticKey Key(string vi) => new(vi);

    // an argument is a catalog key only when typed Key(...), or itself a produced message (localized by its own format key); everything else is shown as it is
    private static object? Shown(object? argument) => argument switch
    {
        SemanticKey key => TranslateDynamic(key.Vi),
        string text when ProducedMessages.TryGetValue(text, out _) => TranslateDynamic(text),
        _ => argument,
    };

    /// <summary>Builds the Vietnamese text for <paramref name="format"/> (a catalog key with {n} holes) and remembers format + raw arguments.</summary>
    public static string Msg(string format, params object?[] args)
    {
        var text = string.Format(System.Globalization.CultureInfo.CurrentCulture, format, args.Select(a => a is SemanticKey key ? key.Vi : a).ToArray());
        if (text.Length > 0) { text = new string(text.AsSpan()); ProducedMessages.Add(text, new Produced(format, args, null)); }
        return text;
    }

    /// <summary>Concatenates message parts (each a Msg/Compose/catalog text) and remembers them, so each part is localized by its own format key.</summary>
    public static string Compose(params string[] parts)
    {
        var text = string.Concat(parts);
        if (text.Length > 0) { text = new string(text.AsSpan()); ProducedMessages.Add(text, new Produced("", null, parts)); }
        return text;
    }

    /// <summary>Joins message lines (each a Msg/Compose/catalog text); every line is localized by its own key.</summary>
    public static string Lines(params string[] lines) => Join("\n", lines);

    /// <summary>Joins parts with a separator and remembers the parts, so each is localized by its own format key.</summary>
    public static string Join(string separator, IEnumerable<string> parts)
    {
        var list = new List<string>();
        foreach (var part in parts) { if (list.Count > 0) list.Add(separator); list.Add(part); }
        return Compose(list.ToArray());
    }

    /// <summary>First line and the rest of a message. A Lines/Join message splits at its own line parts, so both halves stay localizable; any other text splits at the first newline.</summary>
    public static (string First, string Remainder) SplitFirstLine(string text)
    {
        if (ProducedMessages.TryGetValue(text, out var produced) && produced.Parts is { Length: >= 3 } parts && parts[1] == "\n" && parts[0].IndexOf('\n') < 0)
            return (parts[0], Compose(parts[2..]));
        var cut = text.IndexOf('\n');
        return cut < 0 ? (text, "") : (text[..cut], text[(cut + 1)..]);
    }

    /// <summary>Localized text of a format key and its raw arguments (for bindings that carry the key in XAML and the arguments in the view model).</summary>
    public static string Format(string format, params object?[] args)
    {
        var template = Language == "en" && English.TryGetValue(format, out var english) ? english : format;
        return string.Format(System.Globalization.CultureInfo.CurrentCulture, template, args.Select(Shown).ToArray());
    }

    /// <summary>Exact catalog key, or an app-formatted duration ("2 giờ 5 phút"); anything else (user data) is returned untouched.</summary>
    public static string TranslateSemantic(string text)
    {
        if (Language != "en" || string.IsNullOrEmpty(text)) return text;
        if (English.TryGetValue(text, out var exact)) return exact;
        return DurationText.IsMatch(text) ? TranslateEta(text) : text;
    }

    // ETA text is produced by ProgressEtaFormatter: "12 giây", "3 phút", "2 giờ 5 phút", "1 ngày 2 giờ 5 phút".
    private static readonly System.Text.RegularExpressions.Regex DurationText = new(@"^\d+ (?:giây|phút|giờ|ngày)(?: \d+ (?:giây|phút|giờ|ngày))*$", System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    private static string TranslateEta(string eta)
    {
        var converted = System.Text.RegularExpressions.Regex.Replace(eta, @"(\d+) (giây|phút|giờ|ngày)", match => match.Groups[2].Value switch
        {
            "giây" => match.Groups[1].Value + (match.Groups[1].Value == "1" ? " second" : " seconds"),
            "phút" => match.Groups[1].Value + (match.Groups[1].Value == "1" ? " minute" : " minutes"),
            "giờ" => match.Groups[1].Value + (match.Groups[1].Value == "1" ? " hour" : " hours"),
            _ => match.Groups[1].Value + (match.Groups[1].Value == "1" ? " day" : " days"),
        });
        return converted;
    }

    /// <summary>Display-time translation of app messages. Order: a message produced with Msg/Compose (format key + raw arguments) → whole catalog key →
    /// app-formatted duration → the few anchored worker-protocol phrases below. Nothing else is touched: there is no substring, prefix or hole matching
    /// of free text, and captured user data/paths/file names/technical text are never looked up in the catalog.</summary>
    public static string TranslateDynamic(string text)
    {
        if (Language != "en" || string.IsNullOrEmpty(text)) return text;
        if (ProducedMessages.TryGetValue(text, out var produced))
            return produced.Parts is { } parts ? string.Concat(parts.Select(TranslateDynamic)) : Format(produced.Format, produced.Args ?? []);
        if (English.TryGetValue(text, out var exact)) return exact;
        if (DurationText.IsMatch(text)) return TranslateEta(text);          // "12 giây", "2 giờ 5 phút" (elapsed/ETA values)
        foreach (var (vi, en) in DynamicPrefixes)
            if (text.StartsWith(vi, StringComparison.Ordinal)) return en + text[vi.Length..];     // the tail (exception/worker text) stays as it is
        if (TranslateGateSummary(text) is { } gateSummary) return gateSummary;
        foreach (var (pattern, english, nested) in DynamicPatterns)
        {
            var match = pattern.Match(text);
            if (!match.Success) continue;
            var values = new string[match.Groups.Count];
            for (var group = 1; group < match.Groups.Count; group++)
            {
                var value = match.Groups[group].Value;
                if (Array.IndexOf(nested, group) >= 0) value = TranslateSemantic(value);
                else if (english.StartsWith("{1}% • Step: ", StringComparison.Ordinal) && group >= 3)
                    value = group == 3 ? (value.Length > 0 ? " • Item: " + value : "") : (value.Length > 0 ? " • ETA: " + TranslateEta(value) : "");
                else if (group == 2 && english.Contains("not confirmed{2}")) value = value.Length > 0 ? $"; inventory incomplete because {value} archives failed or are unsupported" : "";
                values[group] = value;
            }
            // one pass over the template: a captured value that itself contains "{2}" is never substituted again
            return System.Text.RegularExpressions.Regex.Replace(english, @"\{(\d+)\}", hole => int.Parse(hole.Groups[1].Value) < values.Length ? values[int.Parse(hole.Groups[1].Value)] : hole.Value).Trim();
        }
        if (text.Contains('\n'))
        {
            // a multi-line message made of known whole lines (each line an exact key or a produced message) is translated line by line
            var lines = text.Split('\n');
            var changed = false;
            for (var i = 0; i < lines.Length; i++)
            {
                var translated = ProducedMessages.TryGetValue(lines[i], out _) ? TranslateDynamic(lines[i]) : TranslateSemantic(lines[i]);
                if (!string.Equals(translated, lines[i], StringComparison.Ordinal)) { lines[i] = translated; changed = true; }
            }
            if (changed) return string.Join('\n', lines);
        }
        return text;
    }

    private static readonly System.Text.RegularExpressions.Regex GateSummaryPattern = new(
        @"^(?:(Hợp lệ (\d+), bị chặn (\d+)(?:, có thể xử lý hàng loạt (\d+))?)|(Kiểm tra patch — hợp lệ (\d+), bị chặn (\d+) \(manifest (\d+) dòng, translation\.csv có (\d+) bản dịch\)))(?: — (không phát hiện lỗi cấu trúc trên các dòng có bản dịch)\.|\. (.+))?$",
        System.Text.RegularExpressions.RegexOptions.Singleline | System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    /// <summary>The CSV-validation and patch-preflight summaries are built by the workers from fixed Vietnamese pieces: head + optional "reason: n; reason: n" tail.</summary>
    private static string? TranslateGateSummary(string text)
    {
        var m = GateSummaryPattern.Match(text);
        if (!m.Success) return null;
        string head;
        if (m.Groups[1].Success)
            head = $"Eligible {m.Groups[2].Value}, blocked {m.Groups[3].Value}" + (m.Groups[4].Success ? $", {m.Groups[4].Value} can be handled in bulk" : "");
        else
            head = $"Patch check — eligible {m.Groups[6].Value}, blocked {m.Groups[7].Value} (manifest {m.Groups[8].Value} rows, translation.csv has {m.Groups[9].Value} translations)";
        if (m.Groups[10].Success) return head + " — no structural errors found in the translated rows.";
        if (!m.Groups[11].Success) return head;
        var items = m.Groups[11].Value.Split("; ").Select(item =>
        {
            var colon = item.LastIndexOf(": ", StringComparison.Ordinal);
            if (colon > 0) return TranslateSemantic(item[..colon]) + item[colon..];
            var more = System.Text.RegularExpressions.Regex.Match(item, @"^… \(\+(\d+) nhóm\)$");
            return more.Success ? $"… (+{more.Groups[1].Value} groups)" : item;
        });
        return head + ". " + string.Join("; ", items);
    }

    /// <summary>Registers an application-owned message for a property; user editors and report bodies are never registered.</summary>
    public static void SetAppText(DependencyObject element, DependencyProperty property, string message)
    {
        AppMessages.GetOrCreateValue(element)[property] = message;
        element.SetCurrentValue(property, TranslateDynamic(message));
    }
    private static readonly ConditionalWeakTable<DependencyObject, Dictionary<DependencyProperty, string>> AppMessages = new();
    public static void SetLanguage(string language)
    {
        Language = language == "en" ? "en" : "vi";
        if (Application.Current is { } app && app.Dispatcher.CheckAccess() && !app.Dispatcher.HasShutdownStarted)
            foreach (var window in app.Windows.OfType<Window>().ToArray()) Apply(window);
    }
    public static void Install()
    {
        if (_installed) return;
        _installed = true;
        EventManager.RegisterClassHandler(typeof(FrameworkElement), FrameworkElement.LoadedEvent,
            new RoutedEventHandler((sender, _) => { if (sender is DependencyObject d) ApplyElement(d); }), true);
        // Settings sub-tabs realise their content lazily: localize it when the tab is selected.
        EventManager.RegisterClassHandler(typeof(System.Windows.Controls.TabControl), System.Windows.Controls.Primitives.Selector.SelectionChangedEvent,
            new RoutedEventHandler((sender, e) => { if (sender is System.Windows.Controls.TabControl tabs && ReferenceEquals(e.OriginalSource, tabs)) tabs.Dispatcher.BeginInvoke(new Action(() => Apply(tabs)), System.Windows.Threading.DispatcherPriority.Loaded); }), true);
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
        if (AppMessages.TryGetValue(element, out var messages))
            foreach (var (property, message) in messages) element.SetCurrentValue(property, TranslateDynamic(message));
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
        if (AppMessages.TryGetValue(element, out var messages) && messages.ContainsKey(property)) return;
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
