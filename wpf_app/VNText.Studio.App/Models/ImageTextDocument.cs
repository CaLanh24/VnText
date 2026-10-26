using System.Text.Json.Serialization;
using VNText.Studio.App.ViewModels;
namespace VNText.Studio.App.Models;

public sealed class ImageTextDocument
{
    public int Schema { get; set; } = 1;
    public string SourcePath { get; set; } = "";
    public string SourceSha256 { get; set; } = "";
    public string SourceContainerPath { get; set; } = "";
    public string SourceContainerSha256 { get; set; } = "";
    public string SourceMemberName { get; set; } = "";
    public string SourceMemberSha256 { get; set; } = "";
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
    private bool _approved, _flatBackgroundApproved, _replacementBackgroundApproved, _transparentTextApproved;
    private int _fontSize = 24, _donorX, _donorY;
    private bool _cloneBackgroundApproved;
    public int DonorX { get => _donorX; set { if (Set(ref _donorX, value)) { Approved = false; CloneBackgroundApproved = false; } } }
    public int DonorY { get => _donorY; set { if (Set(ref _donorY, value)) { Approved = false; CloneBackgroundApproved = false; } } }
    public bool CloneBackgroundApproved { get => _cloneBackgroundApproved; set { if (Set(ref _cloneBackgroundApproved, value)) Raise(nameof(ModeSummary)); } }
    public string SourceText { get => _sourceText; set { if (Set(ref _sourceText, value)) Approved = false; } }
    public string Translation { get => _translation; set { if (Set(ref _translation, value)) Approved = false; } }
    public string Background { get => _background; set { if (Set(ref _background, value)) { Approved = false; FlatBackgroundApproved = false; ReplacementBackgroundApproved = false; TransparentTextApproved = false; CloneBackgroundApproved = false; } } }
    public string Foreground { get => _foreground; set { if (Set(ref _foreground, value)) Approved = false; } }
    public int FontSize { get => _fontSize; set { if (Set(ref _fontSize, value)) Approved = false; } }
    public bool Approved { get => _approved; set => Set(ref _approved, value); }
    public bool FlatBackgroundApproved { get => _flatBackgroundApproved; set { if (Set(ref _flatBackgroundApproved, value)) Raise(nameof(ModeSummary)); } }
    public bool ReplacementBackgroundApproved { get => _replacementBackgroundApproved; set { if (Set(ref _replacementBackgroundApproved, value)) Raise(nameof(ModeSummary)); } }
    public bool TransparentTextApproved { get => _transparentTextApproved; set { if (Set(ref _transparentTextApproved, value)) Raise(nameof(ModeSummary)); } }
    /// <summary>One-line state of the four background modes for the compact grid; nothing is chosen by default.</summary>
    [JsonIgnore]
    public string ModeSummary
    {
        get
        {
            var chosen = new List<string>(4);
            if (_flatBackgroundApproved) chosen.Add("Nền phẳng");
            if (_transparentTextApproved) chosen.Add("Chữ trong suốt");
            if (_replacementBackgroundApproved) chosen.Add("Màu đặc");
            if (_cloneBackgroundApproved) chosen.Add("Clone nền mẫu");
            return chosen.Count switch { 0 => "Chưa chọn chế độ nền", 1 => chosen[0], _ => "Chọn nhiều chế độ — cần đúng một" };
        }
    }
    private void ChangeBox(int index, int value, string property)
    {
        if (Box.Length != 4) Box = new[] { 0, 0, 100, 40 };
        if (Box[index] == value) return;
        Box[index] = value; Approved = false; FlatBackgroundApproved = false; ReplacementBackgroundApproved = false; TransparentTextApproved = false; CloneBackgroundApproved = false; Raise(property);
    }
    [JsonIgnore] public int X { get => Box.Length == 4 ? Box[0] : 0; set => ChangeBox(0, value, nameof(X)); }
    [JsonIgnore] public int Y { get => Box.Length == 4 ? Box[1] : 0; set => ChangeBox(1, value, nameof(Y)); }
    [JsonIgnore] public int Width { get => Box.Length == 4 ? Box[2] : 0; set => ChangeBox(2, value, nameof(Width)); }
    [JsonIgnore] public int Height { get => Box.Length == 4 ? Box[3] : 0; set => ChangeBox(3, value, nameof(Height)); }
}
