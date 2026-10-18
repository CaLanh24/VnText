using System.Collections.ObjectModel;
using System.IO;
using System.Security.Cryptography;
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
    private string _renderedImage = "", _imagePackage = "", _renderGameRoot = "";
    private JsonElement _renderedDocument;
    private ImageSource? _imagePreview;
    private BitmapSource? _imageSourcePreview;
    public string ImagePath { get => _imagePath; set { if (Set(ref _imagePath, value)) { _renderedImage = ""; _imagePackage = ""; _imageDocument = null; _imageSourcePreview = null; ImageRegions.Clear(); ImagePreview = null; RefreshImageCommands(); } } }
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
    public RelayCommand CreateImageDeliveryCommand { get; private set; } = null!;
    public RelayCommand InstallImageDeliveryCommand { get; private set; } = null!;
    public RelayCommand RecoverImageDeliveryCommand { get; private set; } = null!;
    public RelayCommand RetryImageCommand { get; private set; } = null!;
    private string NewImageRoot() => string.IsNullOrWhiteSpace(OutputPath) ? throw new InvalidOperationException("Chọn thư mục xuất trước.") : Path.Combine(OutputPath, "image-review-" + Guid.NewGuid().ToString("N"));
    private void RefreshImageCommands()
    {
        foreach (var command in new[] { ChooseOcrImageCommand, DiscoverImagesCommand, RunImageOcrCommand,
            OpenImageReviewCommand, SaveImageReviewCommand, RenderImageCommand, AddImageRegionCommand,
            RemoveImageRegionCommand, CreateImageDeliveryCommand, InstallImageDeliveryCommand, RecoverImageDeliveryCommand, RetryImageCommand })
            command?.RaiseCanExecuteChanged();
    }
    private void InitImageTextCommands()
    {
        RetryImageCommand = new RelayCommand(_ =>
        {
            var image = _pathPicker.PickImageFile();
            if (image is null) return;
            BeginTask("image_batch", new { src = image, @out = OutputPath }, "Đang dịch lại ảnh…");
        }, _ => !Busy && Directory.Exists(OutputPath));
        CreateImageDeliveryCommand = new RelayCommand(_ =>
        {
            _imageTaskRoot = NewImageRoot();
            BeginTask("image_delivery", new { document = _renderedDocument, rendered = _renderedImage,
                game_root = _renderGameRoot, @out = _imageTaskRoot }, "Đang tạo gói ảnh locale…");
        }, _ => !Busy && !string.IsNullOrWhiteSpace(OutputPath) && File.Exists(_renderedImage) && Directory.Exists(_renderGameRoot));
        InstallImageDeliveryCommand = new RelayCommand(_ =>
        {
            var copy = _pathPicker.PickInputPath(); if (copy is null) return;
            _imageTaskRoot = NewImageRoot();
            BeginTask("image_apply", new { package = _imagePackage, game_copy = copy, @out = _imageTaskRoot }, "Đang cài vào bản sao game…");
        }, _ => !Busy && !string.IsNullOrWhiteSpace(OutputPath) && Directory.Exists(_imagePackage));
        RecoverImageDeliveryCommand = new RelayCommand(_ =>
        {
            var transaction = _pathPicker.PickOutputFolder(); if (transaction is null) return;
            _imageTaskRoot = NewImageRoot();
            BeginTask("image_rollback", new { transaction, @out = _imageTaskRoot }, "Đang phục hồi giao dịch ảnh…");
        }, _ => !Busy && !string.IsNullOrWhiteSpace(OutputPath));
        ChooseOcrImageCommand = new RelayCommand(_ => { var p = _pathPicker.PickImageFile(); if (p is not null) ImagePath = p; }, _ => !Busy);
        DiscoverImagesCommand = new RelayCommand(_ => StartImageTask("image_inventory", InputPath), _ => !Busy && Directory.Exists(InputPath));
        RunImageOcrCommand = new RelayCommand(_ => StartImageTask("image_extract", ImagePath), _ => !Busy && (File.Exists(ImagePath) || ImagePath.StartsWith("rpa-member://", StringComparison.Ordinal)));
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
        if (task == "image_extract") ClearImageReviewState();
        BeginTask(task, new { src = source, @out = _imageTaskRoot }, "Đang xử lý text trong ảnh…");
    }
    internal bool TryLoadImageReview(string path)
    {
        try
        {
            if (new FileInfo(path).Length > 2 * 1024 * 1024) throw new InvalidDataException("Review ảnh vượt 2 MiB.");
            var document = JsonSerializer.Deserialize<ImageTextDocument>(File.ReadAllText(path), ImageJson) ?? throw new InvalidDataException("Review rỗng.");
            if (document.Schema != 1 || document.Width <= 0 || document.Height <= 0 || document.Regions is null || document.Regions.Count > 500
                || document.Regions.Any(r => r.Box is null || r.Box.Length != 4 || r.Box[0] < 0 || r.Box[1] < 0 || r.Box[2] <= 0 || r.Box[3] <= 0
                    || (long)r.Box[0] + r.Box[2] > document.Width || (long)r.Box[1] + r.Box[3] > document.Height))
                throw new InvalidDataException("Schema/region không hợp lệ.");
            var sourcePath = Path.GetFullPath(document.SourcePath);
            if (!File.Exists(sourcePath) || new FileInfo(sourcePath).Length > 32 * 1024 * 1024)
                throw new InvalidDataException("Ảnh nguồn không tồn tại hoặc vượt 32 MiB.");
            var sourceBytes = File.ReadAllBytes(sourcePath);
            if (sourceBytes.Length > 32 * 1024 * 1024 || !Convert.ToHexString(SHA256.HashData(sourceBytes)).Equals(document.SourceSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Ảnh nguồn đã đổi hoặc hash review không khớp.");
            var sourcePreview = LoadImagePreview(sourceBytes);
            if (sourcePreview.PixelWidth != document.Width || sourcePreview.PixelHeight != document.Height)
                throw new InvalidDataException("Kích thước ảnh nguồn không khớp review.");
            ClearImageReviewState();
            ImagePath = sourcePath;
            _imageDocument = document;
            foreach (var region in document.Regions) { region.Approved = false; region.FlatBackgroundApproved = false; region.ReplacementBackgroundApproved = false; region.TransparentTextApproved = false; region.CloneBackgroundApproved = false; ImageRegions.Add(region); }
            _imageSourcePreview = sourcePreview;
            ImagePreview = sourcePreview;
            ImageStatus = ImageRegions.Count == 0 ? "Không thấy text; chọn crop/ảnh khác hoặc thêm region thủ công."
                : $"{ImageRegions.Count} region cần review; tọa độ theo pixel ảnh gốc. Chọn đúng một chế độ nền cho từng vùng trước render.";
            RefreshImageCommands();
            return true;
        }
        catch (Exception e) { ClearImageReviewState(); ImageStatus = "Không mở được review: " + e.Message; return false; }
    }
    private void ClearImageReviewState()
    {
        _renderedImage = ""; _imagePackage = ""; _imageDocument = null; _imageSourcePreview = null; ImageRegions.Clear(); ImagePreview = null; ImagePath = "";
        RefreshImageCommands();
    }
    private static BitmapSource LoadImagePreview(string path)
    {
        if (!File.Exists(path)) throw new FileNotFoundException("Không tìm thấy ảnh nguồn/preview.", path);
        if (new FileInfo(path).Length > 32 * 1024 * 1024) throw new InvalidDataException("Preview vượt 32 MiB.");
        return LoadImagePreview(File.ReadAllBytes(path));
    }
    private static BitmapSource LoadImagePreview(byte[] bytes)
    {
        using var stream = new MemoryStream(bytes, writable: false);
        var decoder = BitmapDecoder.Create(stream, BitmapCreateOptions.DelayCreation, BitmapCacheOption.None);
        if (decoder.Frames.Count == 0 || (long)decoder.Frames[0].PixelWidth * decoder.Frames[0].PixelHeight > 16000000) throw new InvalidDataException("Preview không hợp lệ hoặc quá 16 triệu pixel.");
        stream.Position = 0;
        var bitmap = new BitmapImage(); bitmap.BeginInit(); bitmap.CacheOption = BitmapCacheOption.OnLoad;
        bitmap.StreamSource = stream; bitmap.EndInit(); bitmap.Freeze(); return bitmap;
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
        if (ImageRegions.Count == 0 || ImageRegions.Any(r => !r.Approved || new[] { r.FlatBackgroundApproved, r.ReplacementBackgroundApproved, r.TransparentTextApproved, r.CloneBackgroundApproved }.Count(value => value) != 1 || string.IsNullOrWhiteSpace(r.Translation)))
        { ImageStatus = "Duyệt text/crop và chọn đúng một chế độ: nền phẳng, giữ chữ trong suốt, thay region bằng màu đặc, hoặc clone vùng nền sạch (tọa độ X/Y nền mẫu)."; return; }
        _imageTaskRoot = NewImageRoot();
        var document = JsonSerializer.SerializeToElement(CurrentImageReview(), ImageJson);
        _renderedImage = ""; _imagePackage = ""; _renderedDocument = document; _renderGameRoot = InputPath;
        BeginTask("image_render", new { document, @out = _imageTaskRoot,
            font_path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Fonts), "arial.ttf") }, "Đang dựng ảnh từ bản dịch duyệt…");
    }
    private void CompleteImageTask(string task, WorkerEvent evt)
    {
        if (task == "image_batch")
        {
            ImageStatus = evt.Ok ? evt.Summary ?? "Đã xử lý ảnh; xem thư mục images cạnh CSV." : evt.Error ?? "Chưa dịch được ảnh.";
            StatusText = ImageStatus; AppendLog(ImageStatus); RefreshImageCommands();
            return;
        }
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
            else if (task is "image_delivery" or "image_apply" or "image_rollback")
            {
                if (task == "image_delivery") _imagePackage = _imageTaskRoot;
                ImageStatus = (evt.Summary ?? "Đã xử lý gói ảnh") + " " + _imageTaskRoot;
            }
            else { _renderedImage = Path.Combine(_imageTaskRoot, "translated.png"); ImagePreview = LoadImagePreview(Path.Combine(_imageTaskRoot, "translated.png")); ImageStatus = (evt.Summary ?? "Đã render") + " " + _imageTaskRoot; }
        }
        catch (Exception e) { ImageStatus = "Không đọc được kết quả ảnh: " + e.Message; }
        finally { StatusText = ImageStatus; AppendLog(ImageStatus); SelectedTab = WorkflowTabs.Extract; RefreshImageCommands(); }
    }
}
