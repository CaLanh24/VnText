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

    public static string FormatStatus(string action, string error)
    {
        var detail = string.Join(" ", (error ?? "").Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
        if (detail.Length > 180)
            detail = detail[..177] + "…";
        var suffix = string.IsNullOrWhiteSpace(detail) ? "" : $" Chi tiết: {detail}";
        return action switch
        {
            "download" => "Đang thử tải SDK Ren'Py 8.5.3. Nếu lỗi hoặc hủy, bạn có thể thử lại hoặc chọn SDK đã cài.",
            "existing" => "Sẽ dùng thư mục công cụ Ren'Py đã chọn.",
            "none" => "Sẽ tiếp tục không có công cụ; một số lời thoại cần xem lại.",
            "missing" => "Chưa dùng được SDK Ren'Py 8.5.3. Hãy chọn thư mục SDK hoặc thử tải lại; tiếp tục không SDK sẽ cho kết quả chưa đầy đủ." + suffix,
            "cancelled" => "Đã hủy bước lấy text/SDK. Chọn SDK đã cài hoặc thử tải lại khi sẵn sàng.",
            "error" => "Không thể hoàn tất bước lấy text/SDK. Hãy xem lỗi, chọn SDK đã cài hoặc thử tải lại." + suffix,
            "ready" => "Đã sẵn sàng SDK Ren'Py 8.5.3.",
            _ => "Khi lấy text, app tự dùng công cụ đã có; nếu chưa có, kết quả sẽ được báo là chưa đầy đủ.",
        };
    }
}
