using System.Text.Json;

namespace VNText.PatchInstaller;

/// <summary>Plain-language lines for the font / image inventory written by the Python scan (<c>renpy_assets</c>) and by the patch step
/// (<c>font_outcomes</c>).  The app shows these directly; nobody has to open the JSON.  Evidence only: nothing here claims automatic text recognition in bitmaps.</summary>
public static class AssetInventoryPresentation
{
    public const string ImageScopeNotice = "Chỉ phát hiện ảnh nút/menu theo khai báo trong script; chữ trong ảnh KHÔNG được nhận diện hay sửa tự động. Muốn dịch ảnh, hãy đính kèm file spec ảnh đã dựng sẵn ở bước bản Việt hóa.";

    public static string OutcomeLabel(string outcome) => outcome switch
    {
        "OK" => "Đủ chữ Việt",
        "WILL_REPLACE" => "Sẽ thay khi tạo bản Việt hóa",
        "REPLACED" => "Đã thay trong bản Việt hóa",
        "PRESERVED" => "Giữ nguyên",
        _ => "Chưa xử lý được",
    };

    public static string FontReason(string outcome, string status) => status switch
    {
        "COVERS_TRANSLATION" => "font đã có đủ ký tự cần dùng",
        "ENGINE_DEFAULT" => "font mặc định của Ren'Py",
        "NEEDS_VIETNAMESE_FONT" => outcome switch { "UNRESOLVED" => "không tạo được khóa thay thế an toàn (tên mơ hồ hoặc không hỗ trợ)", "REPLACED" => "thiếu chữ Việt; đã thay bằng font Việt khi chơi tiếng Việt", _ => "thiếu chữ Việt; sẽ thay bằng font Việt khi tạo bản Việt hóa" },
        "ICON_PRESERVED" => "font biểu tượng, không thay",
        "AMBIGUOUS_NAME" => "nhiều file cùng tên nên không thể chọn an toàn",
        "UNPARSABLE" => "không đọc được bảng ký tự của font",
        "UNSUPPORTED_FORMAT" => "định dạng font chưa được hỗ trợ",
        "UNRESOLVED_BINDING" => "kiểu chữ/thẻ trỏ tới font không tìm thấy trong game",
        _ => "chưa xác định",
    };

    public static string ImageStatusLabel(string status) => status switch
    {
        "SUPPORTED_LOSSLESS" => "có thể thay bằng ảnh đã dựng (PNG/WebP không nén mất dữ liệu)",
        "UNSUPPORTED_FORMAT" => "định dạng ảnh không hỗ trợ (cần PNG/WebP lossless)",
        "MISSING" => "không tìm thấy file ảnh",
        "AMBIGUOUS_SHADOW" => "có nhiều bản (loose và archive) nên không chọn được",
        _ => "chưa hỗ trợ",
    };

    /// <summary>One line per font: <c>Đã thay trong patch · fonts/A.ttf — lý do</c>.</summary>
    public static List<string> FontLines(JsonElement rows)
    {
        var lines = new List<string>();
        if (rows.ValueKind != JsonValueKind.Array) return lines;
        foreach (var row in rows.EnumerateArray())
        {
            var outcome = Str(row, "outcome"); var status = Str(row, "status");
            var source = Str(row, "source");
            lines.Add($"{OutcomeLabel(outcome)} · {(source.Length == 0 ? "(không rõ tên)" : source)} — {FontReason(outcome, status)}");
        }
        return lines;
    }

    public static string FontCountsLine(JsonElement counts)
    {
        if (counts.ValueKind != JsonValueKind.Object) return "";
        var parts = new List<string>();
        foreach (var key in new[] { "OK", "WILL_REPLACE", "REPLACED", "PRESERVED", "UNRESOLVED" })
            if (counts.TryGetProperty(key, out var value) && value.TryGetInt32(out var number) && number > 0) parts.Add($"{OutcomeLabel(key)}: {number}");
        return string.Join(" · ", parts);
    }

    /// <summary>Lines for the Scan results panel from <c>renpy_assets</c>; empty when the game is not a Ren'Py folder.</summary>
    public static List<string> FromScan(JsonElement renpyAssets)
    {
        var lines = new List<string>();
        if (renpyAssets.ValueKind != JsonValueKind.Object) return lines;
        if (renpyAssets.TryGetProperty("fonts", out var fonts) && fonts.ValueKind == JsonValueKind.Object)
        {
            if (fonts.TryGetProperty("error", out var error)) lines.Add("Font: không quét được — " + error.GetString());
            else
            {
                var total = fonts.TryGetProperty("total", out var t) && t.TryGetInt32(out var n) ? n : 0;
                lines.Add($"Font phát hiện: {total}" + (fonts.TryGetProperty("outcomes", out var counts) && FontCountsLine(counts) is { Length: > 0 } text ? " (" + text + ")" : ""));
                if (fonts.TryGetProperty("assets", out var assets)) lines.AddRange(FontLines(assets));
                if (fonts.TryGetProperty("coverage_scope", out var scope)) lines.Add("Phạm vi: " + (scope.GetString() ?? ""));
            }
        }
        if (renpyAssets.TryGetProperty("images", out var images) && images.ValueKind == JsonValueKind.Object)
        {
            if (images.TryGetProperty("error", out var error)) lines.Add("Ảnh: không quét được — " + error.GetString());
            else if (images.TryGetProperty("candidates", out var candidates) && candidates.ValueKind == JsonValueKind.Array)
            {
                lines.Add($"Ảnh nút/menu phát hiện: {candidates.GetArrayLength()}");
                foreach (var row in candidates.EnumerateArray())
                {
                    var states = row.TryGetProperty("states", out var s) && s.ValueKind == JsonValueKind.Array ? string.Join(", ", s.EnumerateArray().Select(x => x.GetString())) : "";
                    lines.Add($"Ảnh · {Str(row, "asset")}{(states.Length == 0 ? "" : " (" + states + ")")} — {ImageStatusLabel(Str(row, "status"))}");
                }
                lines.Add(ImageScopeNotice);
            }
        }
        return lines;
    }

    /// <summary>Compact lines for the install surfaces from the patch manifest's <c>font_preflight</c>: the counts, the fonts that need attention first
    /// (unresolved, then replaced), a one-line fallback note and a one-line image note.  Everything else stays in font_preflight.json.</summary>
    public static List<string> FromPatch(JsonElement? fontPreflight, int maxFontRows = 4)
    {
        var lines = new List<string>();
        if (fontPreflight is not { ValueKind: JsonValueKind.Object } evidence) return lines;
        if (evidence.TryGetProperty("font_outcomes", out var outcomes) && outcomes.ValueKind == JsonValueKind.Array && outcomes.GetArrayLength() > 0)
        {
            var counts = evidence.TryGetProperty("font_outcome_counts", out var c) ? FontCountsLine(c) : "";
            lines.Add("Font trong game: " + (counts.Length == 0 ? outcomes.GetArrayLength().ToString() : counts));
            var ordered = FontLines(outcomes).Zip(outcomes.EnumerateArray(), (line, row) => (line, rank: Str(row, "outcome") switch { "UNRESOLVED" => 0, "REPLACED" => 1, "WILL_REPLACE" => 1, _ => 2 }))
                .Where(item => item.rank < 2).OrderBy(item => item.rank).Select(item => item.line).ToList();
            lines.AddRange(ordered.Take(maxFontRows));
            if (ordered.Count > maxFontRows) lines.Add($"… và {ordered.Count - maxFontRows} font khác; xem font_preflight.json trong thư mục bản Việt hóa.");
        }
        if (evidence.TryGetProperty("glyph_fallback", out var fallback) && fallback.ValueKind == JsonValueKind.Object)
            lines.Add("Ký hiệu thiếu trong font đã chọn lấy từ font DejaVu đi kèm; mọi chữ còn lại dùng font đã chọn (chỉ kiểu chữ tĩnh).");
        if (evidence.TryGetProperty("image_candidates", out var images) && images.ValueKind == JsonValueKind.Object && images.TryGetProperty("candidates", out var rows)
            && rows.ValueKind == JsonValueKind.Array && rows.GetArrayLength() > 0)
            lines.Add($"Ảnh nút/menu phát hiện: {rows.GetArrayLength()}; chữ trong ảnh không được nhận diện tự động (cần spec ảnh ở bước bản Việt hóa).");
        return lines;
    }

    private static string Str(JsonElement row, string name) =>
        row.ValueKind == JsonValueKind.Object && row.TryGetProperty(name, out var value) && value.ValueKind == JsonValueKind.String ? value.GetString() ?? "" : "";
}
