using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace VNText.Studio.App.Services;

/// <summary>One CSV row that Tạo bản Việt hóa leaves out, with its reason and what to do (from the patch gate's "items").</summary>
public sealed record PatchSkippedItem(string Key, string SourceText, string Translation, string Reason, string Label, string Action);

/// <summary>
/// Owner report (0.1.35): a failed Tạo bản Việt hóa showed only a raw worker line ("Ren'Py dialogue mapping conflict: …") in a log file, and the
/// "N câu chưa đủ điều kiện" count could not be opened.  This turns known worker failures into a cause and a fix in plain Vietnamese, masks the
/// game-specific part of a unit id, and renders the skipped-row list.
/// </summary>
internal static class PatchIssueText
{
    /// <summary>Hide the label part of a Ren'Py native id (it can name the game's own scene); keep the hash so the developer can match it.</summary>
    internal static string MaskUnitId(string id)
    {
        var match = Regex.Match(id ?? "", @"_([0-9a-f]{8})$");
        return match.Success ? "…_" + match.Groups[1].Value : "(đã che)";
    }

    internal static string Explain(string raw)
    {
        raw = (raw ?? "").Trim();
        if (raw.Length == 0) return "Tạo bản Việt hóa không thành công nhưng tác vụ không báo lý do. Bấm 'Gửi báo lỗi' hoặc 'Tạo gói báo lỗi' để gửi cho nhà phát triển.";
        if (raw.StartsWith("Game đang có bản Việt hóa VNText cài trước", StringComparison.Ordinal))
        {
            // The worker's own Vietnamese explanation (an installed VNText patch edited by hand): keep it, mask the unit id, drop the code tail.
            var text = Regex.Replace(raw, @"\s*Ren'Py (dialogue|string) mapping conflict\s*$", "");
            text = Regex.Replace(text, @"\(([A-Za-z0-9_]+_[0-9a-f]{8})\)", m => "(" + MaskUnitId(m.Groups[1].Value) + ")");
            return UiText.Lines(UiText.Msg("Nguyên nhân và cách xử lý: {0}", text), "Game gốc chưa bị thay đổi. Nếu vẫn lỗi, bấm 'Gửi báo lỗi'.");
        }
        var conflict = Regex.Match(raw, @"Ren'Py dialogue mapping conflict(?::\s*(\S+))?");
        if (conflict.Success)
            return UiText.Lines(
                UiText.Msg("Nguyên nhân: game đã có sẵn một bản dịch tiếng Việt khác cho cùng câu thoại (mã {0}), nên VNText không ghi đè.",
                    conflict.Groups[1].Success ? MaskUnitId(conflict.Groups[1].Value) : "(không rõ)"),
                "Cách xử lý: nếu đó là bản Việt hóa VNText cài trước, mở 'Cài trong VNText' → 'Gỡ và hoàn nguyên' rồi tạo bản Việt hóa lại; nếu là bản dịch có sẵn của game, VNText 0.1.36 trở lên tự giữ bản đó và chỉ bỏ qua câu trùng. Nếu vẫn lỗi, bấm 'Gửi báo lỗi'.");
        if (raw.Contains("string mapping conflict", StringComparison.OrdinalIgnoreCase))
            return UiText.Lines("Nguyên nhân: game đã có sẵn bản dịch tiếng Việt khác cho một chuỗi giao diện.",
                "Cách xử lý: gỡ bản dịch có sẵn (sao lưu trước) rồi tạo bản Việt hóa lại; nếu vẫn lỗi, bấm 'Gửi báo lỗi'.");
        if (raw.Contains("precondition drift", StringComparison.OrdinalIgnoreCase) || raw.Contains("changed during", StringComparison.OrdinalIgnoreCase))
            return UiText.Lines("Nguyên nhân: tệp của game đã thay đổi kể từ lúc Lấy text (game được cập nhật, hoặc tệp bị sửa).",
                "Cách xử lý: chạy 'Lấy text' lại cho game này rồi tạo bản Việt hóa lại. Bản dịch đã có được giữ cho các câu không đổi.");
        if (raw.Contains("Không có dòng nào đủ điều kiện", StringComparison.Ordinal) || raw.Contains("no translated eligible rows", StringComparison.OrdinalIgnoreCase))
            return UiText.Lines("Nguyên nhân: chưa có câu nào vừa được dịch vừa qua kiểm tra để ghi vào game.",
                "Cách xử lý: mở 'Sửa bản dịch', chọn bộ lọc 'Dòng sẽ bị bỏ qua' để xem lý do từng câu, dịch/sửa rồi bấm Lưu và tạo bản Việt hóa lại.");
        if (raw.Contains("mọi dòng đã dịch đều đã có bản dịch tiếng Việt KHÁC", StringComparison.Ordinal))
            return UiText.Lines("Nguyên nhân: mọi câu bạn đã dịch đều đã có bản dịch tiếng Việt khác sẵn trong game; VNText giữ bản có sẵn nên không có gì để ghi.",
                "Cách xử lý: muốn dùng bản dịch của bạn, gỡ bản dịch có sẵn khỏi game (sao lưu trước) rồi tạo bản Việt hóa lại.");
        if (raw.Contains("đang ghi vào game này", StringComparison.Ordinal) || raw.Contains("pending_install", StringComparison.OrdinalIgnoreCase))
            return UiText.Lines("Nguyên nhân: một lần cài bản Việt hóa vào game này chưa xong (đang chạy hoặc bị ngắt).", "Cách xử lý: đợi lần cài kia xong, hoặc mở 'Cài trong VNText' để khôi phục rồi thử lại.");
        // Anything else: keep the worker's own words (often already Vietnamese) and offer the report.
        return UiText.Lines(UiText.Msg("Chi tiết: {0}", raw), "Cách xử lý: nếu chưa rõ, bấm 'Gửi báo lỗi' (hoặc 'Tạo gói báo lỗi') để gửi gói ẩn danh cho nhà phát triển; game gốc không bị thay đổi.");
    }

    /// <summary>"Tạo bản Việt hóa" / "Xem danh sách" / "Hủy": returns 1 to build, 2 to show the list, 0 to cancel (also on Esc/close).</summary>
    internal static int ConfirmPatch(string message, Window? owner = null)
    {
        var app = Application.Current;
        owner ??= app?.Windows.OfType<Window>().FirstOrDefault(window => window.IsVisible && window.IsActive) ?? app?.MainWindow;
        var choice = 0;
        var box = new TextBox
        {
            Text = message, IsReadOnly = true, TextWrapping = TextWrapping.Wrap, BorderThickness = new Thickness(0), Background = Brushes.Transparent,
            Foreground = app?.TryFindResource("InkBrush") as Brush ?? Brushes.Black, FontSize = 14,
        };
        var dialog = new AppDialogWindow(owner, UiText.Translate("Tạo bản Việt hóa"), box, 560);
        dialog.OnDismiss = () => choice = 0;
        dialog.AddButton("Hủy", () => choice = 0, isDefault: true);
        dialog.AddButton("Xem danh sách", () => choice = 2);
        dialog.AddButton("Tạo bản Việt hóa", () => choice = 1, primary: true);
        dialog.ShowDialog();
        return choice;
    }

    /// <summary>The skipped rows, grouped by reason with the fix for each group, then every row (source preview only, read-only).</summary>
    internal static string FormatList(IReadOnlyList<PatchSkippedItem> items, bool truncated, int userExcluded, int outsideCsv)
    {
        var lines = new List<string>();
        foreach (var group in items.GroupBy(item => item.Reason).OrderByDescending(g => g.Count()))
        {
            var first = group.First();
            lines.Add(UiText.Msg("■ {0} — {1} câu", UiText.TranslateDynamic(first.Label), group.Count().ToString("N0")));
            lines.Add("   " + UiText.Msg("Cách xử lý: {0}", UiText.TranslateDynamic(first.Action)));
            foreach (var item in group.Take(200))
                lines.Add("   • " + Shorten(item.SourceText) + (string.IsNullOrWhiteSpace(item.Translation) ? "" : "  →  " + Shorten(item.Translation)));
            if (group.Count() > 200) lines.Add("   " + UiText.Msg("… và {0} câu nữa (lọc 'Dòng sẽ bị bỏ qua' trong Sửa bản dịch để xem hết).", (group.Count() - 200).ToString("N0")));
            lines.Add("");
        }
        if (truncated) lines.Add(UiText.Translate("Danh sách đã rút gọn; lọc 'Dòng sẽ bị bỏ qua' trong Sửa bản dịch để xem hết."));
        if (userExcluded > 0 || outsideCsv > 0)
            lines.Add(UiText.Msg("Không tính vào số trên: {0} dòng bạn đã xóa khỏi bản dịch, {1} dòng chỉ để xem lại (không có trong bản dịch). Các dòng này không được dịch hay bản Việt hóa.",
                userExcluded.ToString("N0"), outsideCsv.ToString("N0")));
        return string.Join("\n", lines).TrimEnd();
    }

    private static string Shorten(string text)
    {
        text = (text ?? "").Replace("\r", " ").Replace("\n", " ");
        return text.Length > 90 ? text[..90] + "…" : text;
    }

    /// <summary>Read-only list window with "Mở Sửa bản dịch" (returns true when chosen).</summary>
    internal static bool ShowList(string text, Window? owner = null)
    {
        var app = Application.Current;
        owner ??= app?.Windows.OfType<Window>().FirstOrDefault(window => window.IsVisible && window.IsActive) ?? app?.MainWindow;
        var box = new TextBox
        {
            Text = text, IsReadOnly = true, TextWrapping = TextWrapping.Wrap, BorderThickness = new Thickness(0), Background = Brushes.Transparent,
            Foreground = app?.TryFindResource("InkBrush") as Brush ?? Brushes.Black, FontSize = 13, MaxHeight = 460,
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
        };
        System.Windows.Automation.AutomationProperties.SetName(box, UiText.Translate("Danh sách câu bị bỏ qua"));
        var openEditor = false;
        var dialog = new AppDialogWindow(owner, UiText.Translate("Các câu bị bỏ qua"), box, 720);
        dialog.AddButton("Đóng", () => { }, isDefault: true);
        dialog.AddButton("Mở Sửa bản dịch", () => openEditor = true, primary: true);
        dialog.ShowDialog();
        return openEditor;
    }
}
