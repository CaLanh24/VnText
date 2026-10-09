using System.Collections.ObjectModel;
using System.IO;
using System.Text.Json;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    internal static readonly JsonSerializerOptions ImageJson = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower, WriteIndented = true };
    private ImageTextDocument? _imageDocument;
    private string _imagePath = "", _imageStatus = "Chọn ảnh tĩnh để OCR; kết quả cần review, không tự tạo patch.", _imageTaskRoot = "";
    private ImageSource? _imagePreview;
    private BitmapSource? _imageSourcePreview;
    public string ImagePath { get => _imagePath; set { if (Set(ref _imagePath, value)) { _imageDocument = null; ImageRegions.Clear(); ImagePreview = null; } } }
    public string ImageStatus { get => _imageStatus; private set => Set(ref _imageStatus, value); }
    public ImageSource? ImagePreview { get => _imagePreview; private set => Set(ref _imagePreview, value); }
    public ObservableCollection<string> ImageCandidates { get; } = new();
    public ObservableCollection<ImageTextRegion> ImageRegions { get; } = new();
    public RelayCommand ChooseOcrImageCommand { get; private set; } = null!;
    public RelayCommand DiscoverImagesCommand { get; private set; } = null!;
    public RelayCommand RunImageOcrCommand { get; private set; } = null!;
    public RelayCommand OpenImageReviewCommand { get; private set; } = null!;
    public RelayCommand SaveImageReviewCommand { get; private set; } = null!;
    public RelayCommand RenderImageCommand { get; private set; } = null!;
    public RelayCommand AddImageRegionCommand { get; private set; } = null!;
    public RelayCommand RemoveImageRegionCommand { get; private set; } = null!;
    private string NewImageRoot() => string.IsNullOrWhiteSpace(OutputPath) ? throw new InvalidOperationException("Chọn thư mục xuất trước.") : Path.Combine(OutputPath, "image-review-" + Guid.NewGuid().ToString("N"));
    private void InitImageTextCommands()
    {
        ChooseOcrImageCommand = new RelayCommand(_ => { var p = _pathPicker.PickImageFile(); if (p is not null) ImagePath = p; }, _ => !Busy);
        DiscoverImagesCommand = new RelayCommand(_ => StartImageTask("image_inventory", InputPath), _ => !Busy && Directory.Exists(InputPath));
        RunImageOcrCommand = new RelayCommand(_ => StartImageTask("image_extract", ImagePath), _ => !Busy && File.Exists(ImagePath));
        OpenImageReviewCommand = new RelayCommand(_ => { var p = _pathPicker.PickImageFile(review: true); if (p is not null) TryLoadImageReview(p); }, _ => !Busy);
        SaveImageReviewCommand = new RelayCommand(_ => SaveImageReview(), _ => !Busy && _imageDocument is not null);
        RenderImageCommand = new RelayCommand(_ => RenderReviewedImage(), _ => !Busy && _imageDocument is not null);
        AddImageRegionCommand = new RelayCommand(_ => ImageRegions.Add(new ImageTextRegion { Id = "manual-" + Guid.NewGuid().ToString("N") }), _ => !Busy && _imageDocument is not null);
        RemoveImageRegionCommand = new RelayCommand(item => { if (item is ImageTextRegion region) ImageRegions.Remove(region); }, _ => !Busy);
    }
    private void StartImageTask(string task, string source)
    {
        if (string.IsNullOrWhiteSpace(OutputPath)) { ImageStatus = "Chọn thư mục xuất trước."; return; }
        _imageTaskRoot = NewImageRoot();
        if (task == "image_extract") { _imageDocument = null; ImageRegions.Clear(); ImagePreview = null; }
        BeginTask(task, new { src = source, @out = _imageTaskRoot }, "Đang xử lý text trong ảnh…");
    }
    internal bool TryLoadImageReview(string path)
    {
        try
        {
            if (new FileInfo(path).Length > 2 * 1024 * 1024) throw new InvalidDataException("Review ảnh vượt 2 MiB.");
            var document = JsonSerializer.Deserialize<ImageTextDocument>(File.ReadAllText(path), ImageJson) ?? throw new InvalidDataException("Review rỗng.");
            if (document.Schema != 1 || document.Width <= 0 || document.Height <= 0 || document.Regions.Count > 500
                || document.Regions.Any(r => r.Box.Length != 4)) throw new InvalidDataException("Schema/region không hợp lệ.");
            ImagePath = document.SourcePath;
            _imageDocument = document; ImageRegions.Clear();
            foreach (var region in document.Regions) { region.Approved = false; region.FlatBackgroundApproved = false; ImageRegions.Add(region); }
            var preview = Path.Combine(Path.GetDirectoryName(path)!, "source-preview.png");
            LoadImagePreview(File.Exists(preview) ? preview : document.SourcePath);
            _imageSourcePreview = ImagePreview as BitmapSource;
            ImageStatus = ImageRegions.Count == 0 ? "Không thấy text; chọn crop/ảnh khác hoặc thêm region thủ công."
                : $"{ImageRegions.Count} region cần review; tọa độ theo pixel ảnh gốc. Duyệt từng bản dịch và nền phẳng trước render.";
            return true;
        }
        catch (Exception e) { ImageStatus = "Không mở được review: " + e.Message; return false; }
    }
    private void LoadImagePreview(string path)
    {
        ImagePreview = null;
        if (!File.Exists(path)) return;
        if (new FileInfo(path).Length > 32 * 1024 * 1024) throw new InvalidDataException("Preview vượt 32 MiB.");
        using var stream = File.OpenRead(path);
        var decoder = BitmapDecoder.Create(stream, BitmapCreateOptions.DelayCreation, BitmapCacheOption.None);
        if ((long)decoder.Frames[0].PixelWidth * decoder.Frames[0].PixelHeight > 16000000) throw new InvalidDataException("Preview quá 16 triệu pixel.");
        stream.Position = 0;
        var bitmap = new BitmapImage(); bitmap.BeginInit(); bitmap.CacheOption = BitmapCacheOption.OnLoad;
        bitmap.StreamSource = stream; bitmap.EndInit(); bitmap.Freeze(); ImagePreview = bitmap;
    }
    private ImageTextDocument CurrentImageReview()
    {
        _imageDocument!.Regions = ImageRegions.ToList();
        return _imageDocument;
    }
    private void SaveImageReview()
    {
        try
        {
            var root = NewImageRoot(); Directory.CreateDirectory(root);
            using var stream = new FileStream(Path.Combine(root, "image_text.json"), FileMode.CreateNew);
            JsonSerializer.Serialize(stream, CurrentImageReview(), ImageJson);
            if (_imageSourcePreview is not null)
            {
                var encoder = new PngBitmapEncoder(); encoder.Frames.Add(BitmapFrame.Create(_imageSourcePreview));
                using var preview = new FileStream(Path.Combine(root, "source-preview.png"), FileMode.CreateNew);
                encoder.Save(preview);
            }
            ImageStatus = "Đã lưu review riêng: " + root;
        }
        catch (Exception e) { ImageStatus = "Lưu review lỗi: " + e.Message; }
    }
    private void RenderReviewedImage()
    {
        if (string.IsNullOrWhiteSpace(OutputPath)) { ImageStatus = "Chọn thư mục xuất trước."; return; }
        if (ImageRegions.Count == 0 || ImageRegions.Any(r => !r.Approved || !r.FlatBackgroundApproved || string.IsNullOrWhiteSpace(r.Translation)))
        { ImageStatus = "Duyệt text/crop và nền phẳng của mọi region trước render."; return; }
        _imageTaskRoot = NewImageRoot();
        var document = JsonSerializer.SerializeToElement(CurrentImageReview(), ImageJson);
        BeginTask("image_render", new { document, @out = _imageTaskRoot,
            font_path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Fonts), "arial.ttf") }, "Đang dựng ảnh từ bản dịch duyệt…");
    }
    private void CompleteImageTask(string task, WorkerEvent evt)
    {
        try
        {
            if (!evt.Ok) { ImageStatus = "Chưa hoàn tất: " + evt.Error; return; }
            if (task == "image_inventory")
            {
                using var index = JsonDocument.Parse(File.ReadAllText(Path.Combine(_imageTaskRoot, "image_index.json")));
                ImageCandidates.Clear(); foreach (var item in index.RootElement.GetProperty("image_paths").EnumerateArray()) ImageCandidates.Add(item.GetString()!);
                ImageStatus = evt.Summary ?? "Chọn ảnh để OCR.";
            }
            else if (task == "image_extract") TryLoadImageReview(Path.Combine(_imageTaskRoot, "image_text.json"));
            else { LoadImagePreview(Path.Combine(_imageTaskRoot, "translated.png")); ImageStatus = (evt.Summary ?? "Đã render") + " " + _imageTaskRoot; }
        }
        catch (Exception e) { ImageStatus = "Không đọc được kết quả ảnh: " + e.Message; }
        finally { StatusText = ImageStatus; AppendLog(ImageStatus); SelectedTab = WorkflowTabs.Extract; }
    }
}
