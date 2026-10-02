namespace VNText.Studio.App.Models;

public sealed class GlossaryItem
{
    public GlossaryItem(string term, string translation)
    {
        Term = term;
        Translation = translation;
    }

    public string Term { get; }
    public string Translation { get; }

}
