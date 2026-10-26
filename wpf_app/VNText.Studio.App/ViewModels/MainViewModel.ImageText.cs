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
    public string ImagePath { get => _imagePath; set { if (Set(ref _imagePath, value)) { _renderedImage = ""; _imagePackage = ""; _renderedDocument = default; _imageDocument = null; _imageSourcePreview = null; ImageRegions.Clear(); SelectedImageRegion = null; ImagePreview = null; RefreshImageCommands(); } } }
    public string ImageStatus { get => _imageStatus; private set => Set(ref _imageStatus, value); }
    public ImageSource? ImagePreview
    {
        get => _imagePreview;
        private set
        {
            if (!Set(ref _imagePreview, value)) return;
            Raise(nameof(ImagePreviewPixelWidth));
            Raise(nameof(ImagePreviewPixelHeight));
        }
    }
    /// <summary>Preview size in source PIXELS.  Region boxes are source pixels, while BitmapSource.Width/Height are DPI-scaled
    /// DIPs (a 600x200 px image at 300 DPI is 192x64 DIP), so the overlay canvas must use these, not Width/Height.</summary>
    public double ImagePreviewPixelWidth => (_imagePreview as BitmapSource)?.PixelWidth ?? 0;
    public double ImagePreviewPixelHeight => (_imagePreview as BitmapSource)?.PixelHeight ?? 0;
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
    public RelayCommand OpenImageWorkspaceCommand { get; private set; } = null!;
    internal event Action? ImageWorkspaceRequested;
    private string _imageWorkspaceSummary = "";
    public string ImageWorkspaceSummary { get => _imageWorkspaceSummary; private set => Set(ref _imageWorkspaceSummary, value); }
    /// <summary>The region grid is editable only while no worker task owns the package.</summary>
    public bool ImageGridEnabled => !Busy;

    private ImageTextRegion? _selectedImageRegion;
    /// <summary>The region whose crop/font/colour/background options are shown in the detail form.</summary>
    public ImageTextRegion? SelectedImageRegion
    {
        get => _selectedImageRegion;
        set { if (Set(ref _selectedImageRegion, value)) Raise(nameof(HasSelectedImageRegion)); }
    }
    public bool HasSelectedImageRegion => _selectedImageRegion is not null;

    private static string ImageTaskLabel(string? task) => task switch
    {
        "image_inventory" => "tìm ảnh trong thư mục game",
        "image_extract" => "OCR ảnh",
        "image_batch" => "dịch nháp ảnh",
        "image_render" => "dựng ảnh từ bản dịch đã duyệt",
        "image_delivery" => "tạo gói ảnh",
        "image_apply" => "cài gói vào bản sao game",
        "image_rollback" => "phục hồi giao dịch ảnh",
        "translate" => "dịch text trong CSV",
        "extract" => "lấy text",
        "analyze" => "phân tích game",
        "patch" => "tạo patch",
        null or "" => "tác vụ",
        _ => task,
    };
    /// <summary>Which task owns the worker right now; empty when idle so the panel never implies phantom work.</summary>
    public string ImageWorkspaceTaskText => !Busy ? ""
        : _runningTask?.StartsWith("image_", StringComparison.Ordinal) == true
            ? $"Đang chạy: {ImageTaskLabel(_runningTask)}."
            : $"Một tác vụ khác đang chạy ({ImageTaskLabel(_runningTask)}) — chờ xong hoặc bấm Hủy trước khi dùng ảnh.";
    /// <summary>Latest progress / cancel-acknowledgement line of the running task; empty when idle.</summary>
    public string ImageWorkspaceProgressText => Busy ? ProgressSubtitle : "";
    internal void RaiseImageWorkspaceTaskState()
    {
        Raise(nameof(ImageWorkspaceTaskText));
        Raise(nameof(ImageWorkspaceProgressText));
    }

    /// <summary>Explicit (not getter-driven) refresh of the package image summary shown in the workspace.</summary>
    internal void RefreshImageWorkspace()
    {
        if (string.IsNullOrWhiteSpace(InputPath)) { ImageWorkspaceSummary = "Chưa chọn game / thư mục chứa ảnh."; return; }
        if (string.IsNullOrWhiteSpace(OutputPath)) { ImageWorkspaceSummary = "Chưa chọn thư mục xuất."; return; }
        var images = ImagePackageProbe.Read(WorkflowStatus.ResolvePackageDir(OutputPath));
        ImageWorkspaceSummary = images.Total == 0
            ? "Chưa có báo cáo OCR trong gói. Bấm “Tìm ảnh từ thư mục game”, chọn ảnh rồi OCR."
            : $"Gói có {images.Total:N0} ảnh: {images.OcrReady:N0} đã OCR, {images.TranslatedDrafts:N0} bản dịch nháp, " +
              $"{images.Total - images.OcrReady - images.TranslatedDrafts:N0} chưa OCR được (cần xem tay). " +
              "Để duyệt và cài, chọn ảnh thật trong thư mục game (không phải bản sao trong gói).";
    }
    private string NewImageRoot() => string.IsNullOrWhiteSpace(OutputPath) ? throw new InvalidOperationException("Chọn thư mục xuất trước.") : Path.Combine(OutputPath, "image-review-" + Guid.NewGuid().ToString("N"));
    private void RefreshImageCommands()
    {
        Raise(nameof(ImageGridEnabled));
        foreach (var command in new[] { OpenImageWorkspaceCommand, ChooseOcrImageCommand, DiscoverImagesCommand, RunImageOcrCommand,
            OpenImageReviewCommand, SaveImageReviewCommand, RenderImageCommand, AddImageRegionCommand,
            RemoveImageRegionCommand, CreateImageDeliveryCommand, InstallImageDeliveryCommand, RecoverImageDeliveryCommand, RetryImageCommand })
            command?.RaiseCanExecuteChanged();
    }
    // ---- ownership of the rendered snapshot ------------------------------------------------------------------
    // Every relevant change of the current review (any region property, add, remove, clear) bumps a version.  A render result and a
    // delivery package are valid only for the version they were made from; a change drops them from the commands (the files stay on
    // disk as history) and the user must render again.  A task result that arrives for an older version is dropped.
    private int _imageReviewVersion, _renderedReviewVersion = -1, _packageReviewVersion = -1;
    private int? _imageTaskReviewVersion;
    private readonly HashSet<ImageTextRegion> _trackedImageRegions = new();
    internal string ImageTaskRootForTest => _imageTaskRoot;

    private void OnImageRegionsChanged(object? sender, System.Collections.Specialized.NotifyCollectionChangedEventArgs e)
    {
        if (e.Action == System.Collections.Specialized.NotifyCollectionChangedAction.Reset)
        {
            foreach (var tracked in _trackedImageRegions) tracked.PropertyChanged -= OnImageRegionPropertyChanged;
            _trackedImageRegions.Clear();
        }
        if (e.OldItems is not null)
            foreach (ImageTextRegion region in e.OldItems) { region.PropertyChanged -= OnImageRegionPropertyChanged; _trackedImageRegions.Remove(region); }
        if (e.NewItems is not null)
            foreach (ImageTextRegion region in e.NewItems) if (_trackedImageRegions.Add(region)) region.PropertyChanged += OnImageRegionPropertyChanged;
        OnImageReviewChanged();
    }
    private bool CanCreateImageDelivery() =>
        !Busy && !string.IsNullOrWhiteSpace(OutputPath) && File.Exists(_renderedImage) && Directory.Exists(_renderGameRoot)
        && _renderedReviewVersion == _imageReviewVersion;
    private bool CanInstallImageDelivery() =>
        !Busy && !string.IsNullOrWhiteSpace(OutputPath) && Directory.Exists(_imagePackage) && _packageReviewVersion == _imageReviewVersion;
    private void RefuseStaleImageAction(string action)
    {
        ImageStatus = Busy
            ? $"Đang có tác vụ chạy; chưa thể {action}."
            : $"Chưa thể {action}: chưa có ảnh dựng/gói khớp với review hiện tại. Dựng lại ảnh từ review đã duyệt trước.";
        StatusText = ImageStatus; AppendLog(ImageStatus); RefreshImageCommands();
    }
    private void OnImageRegionPropertyChanged(object? sender, System.ComponentModel.PropertyChangedEventArgs e) => OnImageReviewChanged();

    private void OnImageReviewChanged()
    {
        _imageReviewVersion++;
        if (_renderedImage.Length > 0 || _imagePackage.Length > 0 || _renderedDocument.ValueKind != JsonValueKind.Undefined)
        {
            // Old render/package files are kept as history; only their use is revoked.
            _renderedImage = ""; _imagePackage = ""; _renderedDocument = default;
            if (_imageSourcePreview is not null) ImagePreview = _imageSourcePreview;
            ImageStatus = "Review đã đổi sau khi dựng ảnh — hãy dựng lại trước khi tạo gói hoặc cài. Các file đã dựng trước đó vẫn được giữ trong thư mục xuất.";
        }
        RefreshImageCommands();
    }

    private void InitImageTextCommands()
    {
        ImageRegions.CollectionChanged += OnImageRegionsChanged;
        OpenImageWorkspaceCommand = new RelayCommand(_ => { RefreshImageWorkspace(); ImageWorkspaceRequested?.Invoke(); }, _ => !Busy);
        RetryImageCommand = new RelayCommand(_ =>
        {
            var image = _pathPicker.PickImageFile();
            if (image is null) return;
            BeginTask("image_batch", new { src = image, @out = OutputPath }, "Đang dịch lại ảnh…");
        }, _ => !Busy && Directory.Exists(OutputPath));
        CreateImageDeliveryCommand = new RelayCommand(_ =>
        {
            // RelayCommand.Execute does not consult CanExecute, so the readiness is re-checked here, before any root/task exists.
            if (!CanCreateImageDelivery()) { RefuseStaleImageAction("tạo gói ảnh"); return; }
            _imageTaskRoot = NewImageRoot();
            MarkImageTaskIdentity();
            BeginTask("image_delivery", new { document = _renderedDocument, rendered = _renderedImage,
                game_root = _renderGameRoot, @out = _imageTaskRoot }, "Đang tạo gói ảnh locale…");
        }, _ => CanCreateImageDelivery());
        InstallImageDeliveryCommand = new RelayCommand(_ =>
        {
            // Before the folder picker: a stale or missing package must not even ask for a game copy.
            if (!CanInstallImageDelivery()) { RefuseStaleImageAction("cài gói vào bản sao game"); return; }
            var copy = _pathPicker.PickInputPath(); if (copy is null) return;
            _imageTaskRoot = NewImageRoot();
            BeginTask("image_apply", new { package = _imagePackage, game_copy = copy, @out = _imageTaskRoot }, "Đang cài vào bản sao game…");
        }, _ => CanInstallImageDelivery());
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
        if (task == "image_extract") PrepareImageExtractState();
        MarkImageTaskIdentity();
        BeginTask(task, new { src = source, @out = _imageTaskRoot }, "Đang xử lý text trong ảnh…");
    }

    /// <summary>
    /// A new OCR run drops the OLD review/render state but keeps the chosen source, so a cancelled or failed OCR
    /// can be retried on the same image without going through the picker again.
    /// </summary>
    internal void PrepareImageExtractState()
    {
        _renderedImage = ""; _imagePackage = ""; _renderedDocument = default; _imageDocument = null; _imageSourcePreview = null;
        ImageRegions.Clear(); SelectedImageRegion = null; ImagePreview = null;
        RefreshImageCommands();
    }

    // Identity of the image a running image task was started for.  The combo is locked while busy, but a result must
    // never attach to a different image even if the selection changes some other way.
    private string _imageTaskImagePath = "";
    private void MarkImageTaskIdentity() { _imageTaskImagePath = ImagePath; _imageTaskReviewVersion = _imageReviewVersion; }
    internal void MarkImageTaskIdentityForTest() => MarkImageTaskIdentity();
    /// <summary>Fixture helper: puts a loaded review back so cancel tests can prove it is kept.</summary>
    internal void MarkReviewForTest()
    {
        if (ImageRegions.Count == 0 && !string.IsNullOrWhiteSpace(ImagePath))
            ImageRegions.Add(new ImageTextRegion { Id = "restored", Box = new[] { 10, 10, 200, 40 }, SourceText = "Hello" });
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
        _renderedImage = ""; _imagePackage = ""; _renderedDocument = default; _imageDocument = null; _imageSourcePreview = null; ImageRegions.Clear(); SelectedImageRegion = null; ImagePreview = null; ImagePath = "";
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
        MarkImageTaskIdentity();
        BeginTask("image_render", new { document, @out = _imageTaskRoot,
            font_path = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Fonts), "arial.ttf") }, "Đang dựng ảnh từ bản dịch duyệt…");
    }
    private void CompleteImageTask(string task, WorkerEvent evt)
    {
        if (!evt.Ok && evt.Error?.Contains("cancelled", StringComparison.OrdinalIgnoreCase) == true)
        {
            // Cancellation is its own state: nothing returned by the cancelled task is applied to this screen, the review and the
            // chosen source are kept, and ordinary failures below still read as errors.  No rollback is promised: files a
            // task already wrote safely (for example earlier image_batch drafts) may remain in the output folder.
            ImageStatus = $"Đã hủy {ImageTaskLabel(task)}. Ảnh gốc được giữ nguyên; kết quả hủy không được áp dụng vào màn hình này, nhưng phần đã ghi an toàn (nếu có) có thể còn trong thư mục xuất.";
            StatusText = ImageStatus; AppendLog(ImageStatus); RefreshImageCommands();
            return;
        }
        if (evt.Ok && task is "image_render" or "image_delivery"
            && _imageTaskReviewVersion is int startedAt && startedAt != _imageReviewVersion)
        {
            ImageStatus = "Review đã đổi trong lúc xử lý; kết quả cũ bị bỏ (file giữ trong thư mục xuất), hãy dựng lại cho review hiện tại.";
            StatusText = ImageStatus; AppendLog(ImageStatus); RefreshImageCommands();
            return;
        }
        if (evt.Ok && task is "image_extract" or "image_render" or "image_delivery"
            && !string.Equals(_imageTaskImagePath, ImagePath, StringComparison.Ordinal))
        {
            ImageStatus = "Ảnh đang chọn đã đổi trong lúc xử lý; kết quả cũ bị bỏ, hãy chạy lại cho ảnh hiện tại.";
            StatusText = ImageStatus; AppendLog(ImageStatus); RefreshImageCommands();
            return;
        }
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
                if (task == "image_delivery") { _imagePackage = _imageTaskRoot; _packageReviewVersion = _renderedReviewVersion; }
                ImageStatus = (evt.Summary ?? "Đã xử lý gói ảnh") + " " + _imageTaskRoot;
            }
            else { _renderedImage = Path.Combine(_imageTaskRoot, "translated.png"); _renderedReviewVersion = _imageTaskReviewVersion ?? _imageReviewVersion; ImagePreview = LoadImagePreview(Path.Combine(_imageTaskRoot, "translated.png")); ImageStatus = (evt.Summary ?? "Đã render") + " " + _imageTaskRoot; }
        }
        catch (Exception e) { ImageStatus = "Không đọc được kết quả ảnh: " + e.Message; }
        finally { StatusText = ImageStatus; AppendLog(ImageStatus); SelectedTab = WorkflowTabs.Extract; RefreshImageCommands(); }
    }
}
