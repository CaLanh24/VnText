namespace VNText.Studio.App.Services;

public static class ExtractLevels
{
    public const string Clean = "clean";
    public const string Balanced = "balanced";
    public const string Exhaustive = "exhaustive";

    public static readonly IReadOnlyList<ExtractLevelOption> Options =
    [
        new(Clean, "Sạch"),
        new(Balanced, "Cân bằng"),
        new(Exhaustive, "Quét sâu"),
    ];

    public static string Normalize(string? value)
    {
        var v = (value ?? "").Trim().ToLowerInvariant();
        return v is Clean or Balanced or Exhaustive ? v : Balanced;
    }
}

public sealed record ExtractLevelOption(string Value, string Label);
