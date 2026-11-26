namespace VNText.Studio.App.Services;

internal static class RenpySdkRecovery
{
    public static string ResolveAction(string currentAction, bool sdkMissing, bool operationOk, bool cancelled)
    {
        if (sdkMissing && currentAction is not ("download" or "existing"))
            return "missing";
        if (currentAction is not ("download" or "existing"))
            return currentAction;
        if (cancelled)
            return "cancelled";
        return operationOk ? "ready" : "error";
    }

    /// <summary>The UI also uses "missing" / "ready" / "error" / "cancelled" to describe the LAST result; the worker only understands these four requests.</summary>
    public static string WorkerAction(string uiAction) => uiAction is "download" or "existing" or "none" or "auto" ? uiAction : "auto";

    public static string FormatStatus(string action, string error)
    {
        var detail = string.Join(" ", (error ?? "").Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        if (detail.Length > 180)
            detail = detail[..177] + "…";
        var suffix = string.IsNullOrWhiteSpace(detail) ? "" : $" Chi tiết: {detail}";
        return action switch
        {
            "download" => "Đang thử tải công cụ Ren'Py 8.5.3. Nếu lỗi hoặc hủy, bạn có thể thử lại hoặc chọn công cụ đã cài.",
            "existing" => "Đã chọn thư mục công cụ; sẽ kiểm tra khi lấy text.",
            "none" => "Sẽ chỉ quét tĩnh để xuất danh sách cần xem lại; không dịch, không tạo bản Việt hóa và kết quả luôn chưa đầy đủ.",
            "missing" => "Chưa dùng được công cụ Ren’Py 8.5.3. Hãy chọn thư mục công cụ hoặc thử tải lại; tiếp tục không có công cụ chỉ xuất danh sách cần xem lại (không dịch, không tạo bản Việt hóa)." + suffix,
            "cancelled" => "Đã hủy bước lấy text/tải công cụ. Chọn công cụ đã cài hoặc thử tải lại khi sẵn sàng.",
            "error" => "Không thể hoàn tất bước lấy text/tải công cụ. Hãy xem lỗi, chọn công cụ đã cài hoặc thử tải lại." + suffix,
            "ready" => "Công cụ Ren’Py 8.5.3 đã sẵn sàng.",
            _ => "Khi lấy text, app tự dùng công cụ đã có; nếu chưa có, kết quả sẽ được báo là chưa đầy đủ.",
        };
    }
}
