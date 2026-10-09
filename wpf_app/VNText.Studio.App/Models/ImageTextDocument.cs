using System.Text.Json.Serialization;
using VNText.Studio.App.ViewModels;
namespace VNText.Studio.App.Models;

public sealed class ImageTextDocument
{
    public int Schema { get; set; } = 1;
    public string SourcePath { get; set; } = "";
    public string SourceSha256 { get; set; } = "";
    public int Width { get; set; }
    public int Height { get; set; }
    public string Backend { get; set; } = "";
    public double? Confidence { get; set; }
    public string Status { get; set; } = "";
    public List<ImageTextRegion> Regions { get; set; } = new();
}

public sealed class ImageTextRegion : NotifyBase
{
    public string Id { get; set; } = "";
    public string OcrText { get; set; } = "";
    public int[] Box { get; set; } = new[] { 0, 0, 100, 40 };
    private string _sourceText = "", _translation = "", _background = "#FFFFFF", _foreground = "#000000";
    private bool _approved, _flatBackgroundApproved;
    private int _fontSize = 24;
    public string SourceText { get => _sourceText; set { if (Set(ref _sourceText, value)) Approved = false; } }
    public string Translation { get => _translation; set { if (Set(ref _translation, value)) Approved = false; } }
    public string Background { get => _background; set { if (Set(ref _background, value)) { Approved = false; FlatBackgroundApproved = false; } } }
    public string Foreground { get => _foreground; set { if (Set(ref _foreground, value)) Approved = false; } }
    public int FontSize { get => _fontSize; set { if (Set(ref _fontSize, value)) Approved = false; } }
    public bool Approved { get => _approved; set => Set(ref _approved, value); }
    public bool FlatBackgroundApproved { get => _flatBackgroundApproved; set => Set(ref _flatBackgroundApproved, value); }
    private void ChangeBox(int index, int value, string property)
    {
        if (Box.Length != 4) Box = new[] { 0, 0, 100, 40 };
        if (Box[index] == value) return;
        Box[index] = value; Approved = false; FlatBackgroundApproved = false; Raise(property);
    }
    [JsonIgnore] public int X { get => Box.Length == 4 ? Box[0] : 0; set => ChangeBox(0, value, nameof(X)); }
    [JsonIgnore] public int Y { get => Box.Length == 4 ? Box[1] : 0; set => ChangeBox(1, value, nameof(Y)); }
    [JsonIgnore] public int Width { get => Box.Length == 4 ? Box[2] : 0; set => ChangeBox(2, value, nameof(Width)); }
    [JsonIgnore] public int Height { get => Box.Length == 4 ? Box[3] : 0; set => ChangeBox(3, value, nameof(Height)); }
}
