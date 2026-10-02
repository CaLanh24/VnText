namespace VNText.Studio.App.Services;

public sealed record CsvFilterOption(string Value, string Label);

public static class CsvFilterModes
{
    public const string All = "all";
    public const string Untranslated = "untranslated";
    public const string ReviewOnly = "review_only";
    public const string Errors = "errors";

    public static IReadOnlyList<CsvFilterOption> Options { get; } =
    [
        new(All, "Tất cả"),
        new(Untranslated, "Chưa dịch"),
        new(ReviewOnly, "review_only"),
        new(Errors, "Chỉ dòng lỗi"),
    ];
}
