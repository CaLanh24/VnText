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
    internal const string DefaultImageStatus = "Chọn ảnh tĩnh để nhận dạng chữ; kết quả cần xem lại, không tự tạo bản Việt hóa.";
    private string _imagePath = "", _imageStatus = DefaultImageStatus, _imageTaskRoot = "";
    private string _renderedImage = "", _imagePackage = "", _renderGameRoot = "";
    private JsonElement _renderedDocument;
    private ImageSource? _imagePreview;
    private BitmapSource? _imageSourcePreview;
    public string ImageFileName => string.IsNullOrWhiteSpace(_imagePath) ? "" : Path.GetFileName(_imagePath);
    public bool ImageHasSelectedFile => !string.IsNullOrWhiteSpace(_imagePath);
    public string ImagePath { get => _imagePath; set { if (Set(ref _imagePath, value)) { Raise(nameof(ImageFileName)); Raise(nameof(ImageHasSelectedFile)); _renderedImage = ""; _imagePackage = ""; _renderedDocument = default; _imageDocument = null; _imageSourcePreview = null; ImageRegions.Clear(); SelectedImageRegion = null; ImagePreview = null; RefreshImageCommands(); RaiseImageContentState(); } } }
    public string ImageStatus { get => _imageStatus; private set { if (Set(ref _imageStatus, value)) Raise(nameof(ImageShowStatus)); } }
    /// <summary>The initial manual-OCR hint is shown only in the edit view; any real status (task result, error) is shown in both views.</summary>
    public bool ImageShowStatus => _imageEditMode || _imageStatus != DefaultImageStatus;
    public ImageSource? ImagePreview
    {
        get => _imagePreview;
        private set
        {
            if (!Set(ref _imagePreview, value)) return;
            Raise(nameof(ImagePreviewPixelWidth));
            Raise(nameof(ImagePreviewPixelHeight));
            RaiseImageContentState();
        }
    }
    /// <summary>The preview and the region grid only take room once there is an image/data to show; otherwise one hint explains the next step.</summary>
    public bool ImageHasPreview => _imagePreview is not null;
    public bool ImageHasRegions => ImageRegions.Count > 0;
    public bool ImageShowEmptyState => !ImageHasPreview && !ImageHasRegions;

    // Results first.  Edit mode is entered only by "Sửa ảnh" and left by "Quay lại kết quả"; the manual OCR/crop/render tools exist only there.
    private bool _imageEditMode;
    public bool ImageEditMode { get => _imageEditMode; set { if (Set(ref _imageEditMode, value)) { RaiseImageViewState(); RefreshImageCommands(); } } }
    public bool ImageResultsView => !_imageEditMode;
    public bool ImageHasResults => ImageResults.Count > 0;
    public bool ImageHasUntranslated => ImageResults.Any(r => r.Status != "Đã dịch nháp");
    public bool ImageShowOpenResults => ImageHasResults && !ImageHasUntranslated;
    public bool ImageShowResultText => !_imageEditMode && ImageHasRegions;
    /// <summary>The read-only translations of the selected result; empty in the edit view so nothing is realised there.</summary>
    public System.Collections.IEnumerable ImageResultTexts => _imageEditMode ? Array.Empty<ImageTextRegion>() : ImageRegions;
    public RelayCommand EnterImageEditCommand { get; private set; } = null!;
    public RelayCommand LeaveImageEditCommand { get; private set; } = null!;
    private void RaiseImageViewState()
    {
        Raise(nameof(ImageResultsView)); Raise(nameof(ImageHasResults)); Raise(nameof(ImageHasUntranslated)); Raise(nameof(ImageShowOpenResults)); Raise(nameof(ImageShowResultText)); Raise(nameof(ImageResultTexts)); Raise(nameof(ImageShowStatus));
    }
    public string ImageEmptyHint => string.IsNullOrWhiteSpace(_imagePath)
        ? "Chọn ảnh để xem trước và nhận dạng chữ"
        : "Bấm “Nhận dạng chữ trong ảnh đã chọn” để xem trước và đọc chữ trong ảnh này.";
    internal void TestSetImagePreview(ImageSource? preview) => ImagePreview = preview;
    /// <summary>The OCR panel shows these through the display-time localizer; a language switch refreshes them.</summary>
    internal void RaiseImageLanguageText()
    {
        Raise(nameof(ImageStatus)); Raise(nameof(ImageEmptyHint)); Raise(nameof(ImageWorkspaceSummary)); Raise(nameof(ImageWorkspaceTaskText)); Raise(nameof(ImageWorkspaceProgressText));
        Raise(nameof(ImagePageHeadline)); Raise(nameof(ImagePageDetail)); Raise(nameof(ImageDetailsToggleText));
        foreach (var region in ImageRegions) region.RaiseLanguageText();
    }
    private void RaiseImageContentState()
    {
        Raise(nameof(ImageHasPreview)); Raise(nameof(ImageHasRegions)); Raise(nameof(ImageShowEmptyState)); Raise(nameof(ImageEmptyHint)); RaiseImageViewState();
    }
    /// <summary>Preview size in source PIXELS.  Region boxes are source pixels, while BitmapSource.Width/Height are DPI-scaled
    /// DIPs (a 600x200 px image at 300 DPI is 192x64 DIP), so the overlay canvas must use these, not Width/Height.</summary>
    public double ImagePreviewPixelWidth => (_imagePreview as BitmapSource)?.PixelWidth ?? 0;
    public double ImagePreviewPixelHeight => (_imagePreview as BitmapSource)?.PixelHeight ?? 0;
    public ObservableCollection<string> ImageCandidates { get; } = new();
    public ObservableCollection<ImagePackageProbe.ImageResult> ImageResults { get; } = new();
    private ImagePackageProbe.ImageResult? _selectedImageResult;
    public ImagePackageProbe.ImageResult? SelectedImageResult
    {
        get => _selectedImageResult;
        set
        {
            if (!Set(ref _selectedImageResult, value) || value is null) return;
            if (!string.IsNullOrEmpty(value.ReviewPath)) TryLoadImageReview(value.ReviewPath, fromSavedReview: true);
            if (!string.IsNullOrEmpty(value.DraftPath))
                try { ImagePreview = LoadImagePreview(value.DraftPath); } catch (IOException) { }
        }
    }
    public ObservableCollection<ImageTextRegion> ImageRegions { get; } = new();
    public RelayCommand ChooseOcrImageCommand { get; private set; } = null!;
    public RelayCommand DiscoverImagesCommand { get; private set; } = null!;
    public RelayCommand TranslateAllImagesCommand { get; private set; } = null!;
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
    // The summary and the page state text are produced on demand in the CURRENT language (a hot language switch re-reads them), never cached as a translated string.
    private Func<string> _imageWorkspaceSummary = static () => "";
    public string ImageWorkspaceSummary => _imageWorkspaceSummary();
    private void SetImageSummary(Func<string> summary) { _imageWorkspaceSummary = summary; Raise(nameof(ImageWorkspaceSummary)); }

    // ---- Images page state (V5).  Exactly one state describes the page; counts and "scanned" wording exist ONLY for a state backed by a valid report. ----
    /// <summary>NoSource: no game/folder; NoOutput: no export folder; NoReport: nothing scanned yet; Unreadable: the report cannot be read;
    /// NoText: a valid report whose scan found no image with text (a COMPLETED scan); Results: images with text were found.</summary>
    public enum ImagePageKind { NoSource, NoOutput, NoReport, Unreadable, ScanFailed, NoText, Results }
    private ImagePageKind _imagePage = ImagePageKind.NoSource;
    private Func<string> _imagePageHeadline = static () => "", _imagePageDetail = static () => "";
    private bool _imageDetailsOpen;
    public ImagePageKind ImagePage => _imagePage;
    public string ImagePageHeadline => _imagePageHeadline();
    public string ImagePageDetail => _imagePageDetail();
    /// <summary>Only the states that need the user to go and choose/scan show a next action; it opens the Extract step.</summary>
    public bool ImagePageHasAction => _imagePage is ImagePageKind.NoSource or ImagePageKind.NoOutput or ImagePageKind.NoReport or ImagePageKind.Unreadable or ImagePageKind.ScanFailed;
    /// <summary>The package counts/path line belongs to the states that have a report.</summary>
    public bool ImageSummaryVisible => _imagePage is ImagePageKind.Results or ImagePageKind.NoText;
    public RelayCommand OpenExtractForImagesCommand { get; private set; } = null!;
    /// <summary>The long safety/format/workflow explanation lives behind this one explicit control; it never changes the page state.</summary>
    public bool ImageDetailsOpen { get => _imageDetailsOpen; private set { if (Set(ref _imageDetailsOpen, value)) { Raise(nameof(ImageDetailsToggleText)); } } }
    public string ImageDetailsToggleText => _imageDetailsOpen ? "Ẩn chi tiết" : "Chi tiết";
    public RelayCommand ToggleImageDetailsCommand { get; private set; } = null!;
    private void SetImagePage(ImagePageKind kind, Func<string> headline, Func<string> detail)
    {
        _imagePage = kind;
        _imagePageHeadline = headline;
        _imagePageDetail = detail;
        Raise(nameof(ImagePage)); Raise(nameof(ImagePageHeadline)); Raise(nameof(ImagePageDetail)); Raise(nameof(ImagePageHasAction)); Raise(nameof(ImageSummaryVisible));
    }
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
        "image_extract" => "nhận dạng chữ trong ảnh",
        "image_batch" => "dịch nháp ảnh",
        "image_render" => "dựng ảnh từ bản dịch đã duyệt",
        "image_delivery" => "tạo gói ảnh",
        "image_apply" => "cài gói vào game",
        "image_rollback" => "phục hồi giao dịch ảnh",
        "translate" => "dịch text trong bản dịch",
        "extract" => "lấy text",
        "analyze" => "phân tích game",
        "patch" => "tạo bản Việt hóa",
        null or "" => "tác vụ",
        _ => task,
    };
    /// <summary>Which task owns the worker right now; empty when idle so the panel never implies phantom work.</summary>
    public string ImageWorkspaceTaskText => !Busy ? ""
        : _runningTask?.StartsWith("image_", StringComparison.Ordinal) == true
            ? UiText.Msg("Đang chạy: {0}.", UiText.Key(ImageTaskLabel(_runningTask)))
            : UiText.Msg("Một tác vụ khác đang chạy ({0}) — chờ xong hoặc bấm Hủy trước khi dùng ảnh.", UiText.Key(ImageTaskLabel(_runningTask)));
    /// <summary>Latest progress / cancel-acknowledgement line of the running task; empty when idle.</summary>
    public string ImageWorkspaceProgressText => Busy ? ProgressSubtitle : "";
    /// <summary>Own task with its own progress: the text CSV is already published, so image OCR can run (and be cancelled) without it.</summary>
    private void StartBackgroundImageScan()
    {
        if (Busy || !Directory.Exists(InputPath) || string.IsNullOrWhiteSpace(OutputPath)) return;
        AppendLog("Bản dịch text đã sẵn sàng. Bắt đầu quét ảnh có chữ như một tác vụ riêng (hủy được, không ảnh hưởng bản dịch).");
        BeginTask("image_batch", new { src = InputPath, @out = WorkflowStatus.ResolvePackageDir(OutputPath), after_extract = true }, "Đang quét ảnh có chữ (nền)…");
    }

    internal void RaiseImageWorkspaceTaskState()
    {
        Raise(nameof(ImageWorkspaceTaskText));
        Raise(nameof(ImageWorkspaceProgressText));
    }

    /// <summary>Explicit (not getter-driven) refresh of the package image summary shown in the workspace.</summary>
    internal void RefreshImageWorkspace()
    {
        if (string.IsNullOrWhiteSpace(InputPath))
        {
            ImageResults.Clear(); RaiseImageViewState();
            SetImageSummary(static () => "Chưa chọn game / thư mục chứa ảnh.");
            SetImagePage(ImagePageKind.NoSource, static () => "Chưa chọn game / thư mục chứa ảnh.", static () => "Chọn nguồn ở bước Lấy text; ảnh có chữ được quét ở đó.");
            return;
        }
        if (string.IsNullOrWhiteSpace(OutputPath))
        {
            ImageResults.Clear(); RaiseImageViewState();
            SetImageSummary(static () => "Chưa chọn nơi lưu bản dịch.");
            SetImagePage(ImagePageKind.NoOutput, static () => "Chưa chọn nơi lưu bản dịch.", static () => "Chọn nơi lưu bản dịch ở bước Lấy text; báo cáo ảnh nằm trong gói xuất.");
            return;
        }
        var packageDir = WorkflowStatus.ResolvePackageDir(OutputPath);
        var report = ImagePackageProbe.ReadReport(packageDir);
        var images = ImagePackageProbe.Read(packageDir);
        ImageResults.Clear();
        foreach (var result in ImagePackageProbe.ReadResults(packageDir)) ImageResults.Add(result);
        RaiseImageViewState();
        switch (report.Kind)
        {
            case ImagePackageProbe.ReportKind.Missing:
                SetImageSummary(static () => "Chưa có báo cáo ảnh cho gói này.");
                SetImagePage(ImagePageKind.NoReport, static () => "Chưa có báo cáo ảnh cho gói này.", static () => "Báo cáo được tạo khi Lấy text quét ảnh; chưa quét thì chưa có số ảnh.");
                return;
            case ImagePackageProbe.ReportKind.Unreadable:
                SetImageSummary(static () => "Không đọc được báo cáo ảnh.");
                SetImagePage(ImagePageKind.Unreadable, static () => "Không đọc được báo cáo ảnh.", static () => "Báo cáo hỏng hoặc quá lớn; Lấy text lại để tạo báo cáo mới.");
                return;
            case ImagePackageProbe.ReportKind.Valid when images.Total == 0 && report.NoText < report.Scanned:
                SetImageSummary(static () => "Quét ảnh chưa hoàn tất.");
                SetImagePage(ImagePageKind.ScanFailed, static () => "Quét ảnh chưa hoàn tất.", static () => "Một số ảnh chưa kiểm tra được. Lấy text lại hoặc mở Sửa ảnh.");
                return;
            case ImagePackageProbe.ReportKind.Valid when images.Total == 0:
                var scannedText = report.Scanned.ToString("N0");
                SetImageSummary(() => UiText.Msg("Đã quét {0} ảnh: không ảnh nào chứa chữ cần dịch.", scannedText));
                SetImagePage(ImagePageKind.NoText, static () => "Quét xong: không có ảnh chứa chữ.", static () => "Không cần nhận dạng chữ hay dịch ảnh cho gói này. Bạn vẫn có thể sửa ảnh thủ công.");
                return;
        }
        var detectedText = images.Total.ToString("N0");
        SetImagePage(ImagePageKind.Results, () => UiText.Msg("{0} ảnh có chữ trong gói.", detectedText), static () => "Bản dịch nháp được tạo ở bước Dịch; chọn ảnh bên dưới nếu muốn sửa.");
        if (_selectedImageResult is null && !ImageHasPreview && ImageResults.Count > 0) SelectedImageResult = ImageResults[0];      // show the first result right away
        var resultsSummary = $"{images.Total:N0} ảnh có chữ · {images.TranslatedDrafts:N0} bản dịch nháp · {images.Total - images.TranslatedDrafts:N0} cần dịch / xem lại.\nKết quả: {Path.Combine(WorkflowStatus.ResolvePackageDir(OutputPath), "images")}\nBấm Dịch ở tab Dịch để dịch cả text và ảnh. Chọn một ảnh bên dưới để xem hoặc sửa.";
        SetImageSummary(() => resultsSummary);
    }
    private string NewImageRoot() => string.IsNullOrWhiteSpace(OutputPath) ? throw new InvalidOperationException(UiText.Msg("Chọn nơi lưu bản dịch trước.")) : Path.Combine(OutputPath, "image-review-" + Guid.NewGuid().ToString("N"));
    private void RefreshImageCommands()
    {
        Raise(nameof(ImageGridEnabled));
        foreach (var command in new[] { EnterImageEditCommand, LeaveImageEditCommand, OpenImageWorkspaceCommand, ChooseOcrImageCommand, DiscoverImagesCommand, TranslateAllImagesCommand, RunImageOcrCommand,
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
        RaiseImageContentState();
        OnImageReviewChanged();
    }
    private bool CanCreateImageDelivery() =>
        !_imageDraftInvalid && !Busy && !string.IsNullOrWhiteSpace(OutputPath) && File.Exists(_renderedImage) && Directory.Exists(_renderGameRoot)
        && _renderedReviewVersion == _imageReviewVersion;
    private bool _imageDraftInvalid;
    /// <summary>True while a numeric field of the region editor shows a rejected draft (the model still holds its last valid number); set by the panel from the live validation state.</summary>
    public bool ImageDraftInvalid { get => _imageDraftInvalid; internal set { if (Set(ref _imageDraftInvalid, value)) RefreshImageCommands(); } }
    private bool RefuseDraftImageAction(string action)
    {
        if (!_imageDraftInvalid) return false;
        ImageStatus = UiText.Msg("Chưa thể {0}: một ô số trong chi tiết vùng đang báo lỗi. Hãy sửa giá trị (hoặc chọn vùng khác) trước.", UiText.Key(action));
        StatusText = ImageStatus; AppendLog(ImageStatus); RefreshImageCommands();
        return true;
    }
    private bool CanInstallImageDelivery() =>
        !_imageDraftInvalid && !Busy && !string.IsNullOrWhiteSpace(OutputPath) && Directory.Exists(_imagePackage) && _packageReviewVersion == _imageReviewVersion;
    private void RefuseStaleImageAction(string action)
    {
        ImageStatus = Busy
            ? UiText.Msg("Đang có tác vụ chạy; chưa thể {0}.", UiText.Key(action))
            : UiText.Msg("Chưa thể {0}: chưa có ảnh đã dựng khớp với bản xem lại hiện tại. Hãy dựng lại ảnh từ bản xem lại đã duyệt trước.", UiText.Key(action));
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
            ImageStatus = "Bản xem lại đã đổi sau khi dựng ảnh — hãy dựng lại trước khi tạo gói hoặc cài. Các tệp đã dựng trước đó vẫn được giữ trong nơi lưu bản dịch.";
        }
        RefreshImageCommands();
    }

    private void InitImageTextCommands()
    {
        ImageRegions.CollectionChanged += OnImageRegionsChanged;
        EnterImageEditCommand = new RelayCommand(_ => ImageEditMode = true, _ => !Busy && !_imageEditMode);
        LeaveImageEditCommand = new RelayCommand(_ => ImageEditMode = false, _ => !Busy && _imageEditMode);
        OpenImageWorkspaceCommand = new RelayCommand(_ => { ImageEditMode = false; NavigateTab(WorkflowTabs.Images); }, _ => !Busy);
        OpenExtractForImagesCommand = new RelayCommand(_ => NavigateTab(WorkflowTabs.Extract));
        ToggleImageDetailsCommand = new RelayCommand(_ => ImageDetailsOpen = !ImageDetailsOpen);
        RetryImageCommand = new RelayCommand(_ =>
        {
            var image = _pathPicker.PickImageFile();
            if (image is null) return;
            BeginTask("image_batch", new { src = image, @out = OutputPath }, "Đang dịch lại ảnh…");
        }, _ => !Busy && Directory.Exists(OutputPath));
        CreateImageDeliveryCommand = new RelayCommand(_ =>
        {
            // RelayCommand.Execute does not consult CanExecute, so the readiness is re-checked here, before any root/task exists.
            if (RefuseDraftImageAction("tạo gói ảnh")) return;
            if (!CanCreateImageDelivery()) { RefuseStaleImageAction("tạo gói ảnh"); return; }
            _imageTaskRoot = NewImageRoot();
            MarkImageTaskIdentity();
            BeginTask("image_delivery", new { document = _renderedDocument, rendered = _renderedImage,
                game_root = _renderGameRoot, @out = _imageTaskRoot }, "Đang tạo gói ảnh…");
        }, _ => CanCreateImageDelivery());
        InstallImageDeliveryCommand = new RelayCommand(_ =>
        {
            // Before the folder picker: a stale or missing package must not even ask for a game.
            if (RefuseDraftImageAction("cài gói vào game")) return;
            if (!CanInstallImageDelivery()) { RefuseStaleImageAction("cài gói vào game"); return; }
            var copy = _pathPicker.PickInputPath(); if (copy is null) return;
            _imageTaskRoot = NewImageRoot();
            BeginTask("image_apply", new { package = _imagePackage, game_copy = copy, @out = _imageTaskRoot }, "Đang cài vào game…");
        }, _ => CanInstallImageDelivery());
        RecoverImageDeliveryCommand = new RelayCommand(_ =>
        {
            var transaction = _pathPicker.PickOutputFolder(); if (transaction is null) return;
            _imageTaskRoot = NewImageRoot();
            BeginTask("image_rollback", new { transaction, @out = _imageTaskRoot }, "Đang phục hồi giao dịch ảnh…");
        }, _ => !Busy && !string.IsNullOrWhiteSpace(OutputPath));
        ChooseOcrImageCommand = new RelayCommand(_ => { var p = _pathPicker.PickImageFile(); if (p is not null) ImagePath = p; }, _ => !Busy);
        DiscoverImagesCommand = new RelayCommand(_ => StartImageTask("image_inventory", InputPath), _ => !Busy && Directory.Exists(InputPath));
        TranslateAllImagesCommand = new RelayCommand(_ =>
        {
            if (Busy || !Directory.Exists(InputPath) || string.IsNullOrWhiteSpace(OutputPath)) return;
            BeginTask("image_batch", new { src = InputPath, @out = WorkflowStatus.ResolvePackageDir(OutputPath), cached_only = true }, "Đang dịch ảnh đã nhận dạng chữ…");
        }, _ => !Busy && Directory.Exists(InputPath) && !string.IsNullOrWhiteSpace(OutputPath));
        RunImageOcrCommand = new RelayCommand(_ => StartImageTask("image_extract", ImagePath), _ => !Busy && (File.Exists(ImagePath) || ImagePath.StartsWith("rpa-member://", StringComparison.Ordinal)));
        OpenImageReviewCommand = new RelayCommand(_ => { var p = _pathPicker.PickImageFile(review: true); if (p is not null) TryLoadImageReview(p, fromSavedReview: true); }, _ => !Busy);
        SaveImageReviewCommand = new RelayCommand(_ => SaveImageReview(), _ => !Busy && !_imageDraftInvalid && _imageDocument is not null);
        RenderImageCommand = new RelayCommand(_ => RenderReviewedImage(), _ => !Busy && !_imageDraftInvalid && _imageDocument is not null);
        AddImageRegionCommand = new RelayCommand(_ => ImageRegions.Add(new ImageTextRegion { Id = "manual-" + Guid.NewGuid().ToString("N") }), _ => !Busy && _imageDocument is not null);
        RemoveImageRegionCommand = new RelayCommand(item => { if (item is ImageTextRegion region) ImageRegions.Remove(region); }, _ => !Busy);
    }
    private void StartImageTask(string task, string source)
    {
        if (string.IsNullOrWhiteSpace(OutputPath)) { ImageStatus = "Chọn nơi lưu bản dịch trước."; return; }
        _imageTaskRoot = NewImageRoot();
        if (task == "image_extract") PrepareImageExtractState();
        MarkImageTaskIdentity();
        BeginTask(task, new { src = source, @out = _imageTaskRoot }, "Đang xử lý chữ trong ảnh…");
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
    internal const string SavedReviewOpenedMessage = "Đã mở bản xem lại. Để an toàn, hãy chọn lại chế độ nền và duyệt các vùng trước khi dựng ảnh.";

    internal bool TryLoadImageReview(string path, bool fromSavedReview = false)
    {
        try
        {
            if (new FileInfo(path).Length > 2 * 1024 * 1024) throw new InvalidDataException(UiText.Msg("Bản xem lại ảnh vượt 2 MiB."));
            var document = JsonSerializer.Deserialize<ImageTextDocument>(File.ReadAllText(path), ImageJson) ?? throw new InvalidDataException(UiText.Msg("Review rỗng."));
            if (document.Schema != 1 || document.Width <= 0 || document.Height <= 0 || document.Regions is null || document.Regions.Count > 500
                || document.Regions.Any(r => r.Box is null || r.Box.Length != 4 || r.Box[0] < 0 || r.Box[1] < 0 || r.Box[2] <= 0 || r.Box[3] <= 0
                    || (long)r.Box[0] + r.Box[2] > document.Width || (long)r.Box[1] + r.Box[3] > document.Height))
                throw new InvalidDataException(UiText.Msg("Cấu trúc hoặc vùng chữ không hợp lệ."));
            var sourcePath = Path.GetFullPath(document.SourcePath);
            if (!string.IsNullOrWhiteSpace(document.SourceReference))
            {
                var reference = Path.GetFullPath(document.SourceReference);
                var game = Path.GetFullPath(Path.Combine(InputPath, "game")) + Path.DirectorySeparatorChar;
                if (!reference.StartsWith(game, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Ảnh trong kết quả thuộc game khác; hãy lấy text lại.");
                sourcePath = reference;
                document.SourcePath = reference;
            }
            if (!File.Exists(sourcePath) || new FileInfo(sourcePath).Length > 32 * 1024 * 1024)
                throw new InvalidDataException(UiText.Msg("Ảnh nguồn không tồn tại hoặc vượt 32 MiB."));
            var sourceBytes = File.ReadAllBytes(sourcePath);
            if (sourceBytes.Length > 32 * 1024 * 1024 || !Convert.ToHexString(SHA256.HashData(sourceBytes)).Equals(document.SourceSha256, StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException(UiText.Msg("Ảnh nguồn đã đổi hoặc mã kiểm tra của bản xem lại không khớp."));
            var sourcePreview = LoadImagePreview(sourceBytes);
            if (sourcePreview.PixelWidth != document.Width || sourcePreview.PixelHeight != document.Height)
                throw new InvalidDataException(UiText.Msg("Kích thước ảnh nguồn không khớp bản xem lại."));
            ClearImageReviewState();
            ImagePath = sourcePath;
            _imageDocument = document;
            foreach (var region in document.Regions) { region.Approved = false; region.FlatBackgroundApproved = false; region.ReplacementBackgroundApproved = false; region.TransparentTextApproved = false; region.CloneBackgroundApproved = false; ImageRegions.Add(region); }
            _imageSourcePreview = sourcePreview;
            ImagePreview = sourcePreview;
            ImageStatus = ImageRegions.Count == 0 ? "Không thấy chữ; chọn vùng cắt hoặc ảnh khác, hoặc thêm vùng chữ thủ công."
                : fromSavedReview ? UiText.Translate(SavedReviewOpenedMessage)     // the saved text/crop are loaded, the approvals are not: say what to do next
                : UiText.Msg("{0} vùng chữ cần xem lại; tọa độ tính theo điểm ảnh của ảnh gốc. Chọn đúng một chế độ nền cho từng vùng trước khi dựng ảnh.", ImageRegions.Count);
            RefreshImageCommands();
            return true;
        }
        catch (Exception e) { ClearImageReviewState(); ImageStatus = UiText.Msg("Không mở được bản xem lại: {0}", e.Message); return false; }
    }
    private void ClearImageReviewState()
    {
        _renderedImage = ""; _imagePackage = ""; _renderedDocument = default; _imageDocument = null; _imageSourcePreview = null; ImageRegions.Clear(); SelectedImageRegion = null; ImagePreview = null; ImagePath = "";
        RefreshImageCommands();
    }
    private static BitmapSource LoadImagePreview(string path)
    {
        if (!File.Exists(path)) throw new FileNotFoundException(UiText.Msg("Không tìm thấy ảnh nguồn hoặc ảnh xem trước."), path);
        if (new FileInfo(path).Length > 32 * 1024 * 1024) throw new InvalidDataException(UiText.Msg("Ảnh xem trước vượt 32 MiB."));
        return LoadImagePreview(File.ReadAllBytes(path));
    }
    private static BitmapSource LoadImagePreview(byte[] bytes)
    {
        using var stream = new MemoryStream(bytes, writable: false);
        var decoder = BitmapDecoder.Create(stream, BitmapCreateOptions.DelayCreation, BitmapCacheOption.None);
        if (decoder.Frames.Count == 0 || (long)decoder.Frames[0].PixelWidth * decoder.Frames[0].PixelHeight > 16000000) throw new InvalidDataException(UiText.Msg("Ảnh xem trước không hợp lệ hoặc quá 16 triệu điểm ảnh."));
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
        if (RefuseDraftImageAction("lưu bản xem lại riêng")) return;          // RelayCommand.Execute does not consult CanExecute
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
            ImageStatus = UiText.Msg("Đã lưu bản xem lại riêng: {0}", root);
        }
        catch (Exception e) { ImageStatus = UiText.Msg("Lưu bản xem lại bị lỗi: {0}", e.Message); }
    }
    private void RenderReviewedImage()
    {
        if (RefuseDraftImageAction("dựng ảnh từ bản dịch đã duyệt")) return;
        if (string.IsNullOrWhiteSpace(OutputPath)) { ImageStatus = "Chọn nơi lưu bản dịch trước."; return; }
        if (ImageRegions.Count == 0 || ImageRegions.Any(r => !r.Approved || new[] { r.FlatBackgroundApproved, r.ReplacementBackgroundApproved, r.TransparentTextApproved, r.CloneBackgroundApproved }.Count(value => value) != 1 || string.IsNullOrWhiteSpace(r.Translation)))
        { ImageStatus = "Duyệt chữ và vùng cắt, rồi chọn đúng một chế độ: nền phẳng, giữ chữ trong suốt, thay cả vùng bằng một màu, hoặc sao chép vùng nền sạch (tọa độ X/Y nền mẫu)."; return; }
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
            ImageStatus = UiText.Msg("Đã hủy {0}. Ảnh gốc được giữ nguyên; kết quả hủy không được áp dụng vào màn hình này, nhưng phần đã ghi an toàn (nếu có) có thể còn trong nơi lưu bản dịch.", UiText.Key(ImageTaskLabel(task)));
            StatusText = ImageStatus; AppendLog(ImageStatus); RefreshImageCommands();
            return;
        }
        if (evt.Ok && task is "image_render" or "image_delivery"
            && _imageTaskReviewVersion is int startedAt && startedAt != _imageReviewVersion)
        {
            ImageStatus = "Bản xem lại đã đổi trong lúc xử lý; kết quả cũ bị bỏ (tệp vẫn nằm trong nơi lưu bản dịch), hãy dựng lại theo bản xem lại hiện tại.";
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
            RefreshImageWorkspace();
            ImageStatus = evt.Ok ? evt.Summary ?? "Đã xử lý ảnh; xem thư mục images cạnh CSV." : evt.Error ?? "Chưa dịch được ảnh.";
            StatusText = ImageStatus; AppendLog(ImageStatus); RefreshImageCommands();
            return;
        }
        try
        {
            if (!evt.Ok) { ImageStatus = UiText.Msg("Chưa hoàn tất: {0}", UiText.Key(evt.Error ?? "")); return; }
            if (task == "image_inventory")
            {
                using var index = JsonDocument.Parse(File.ReadAllText(Path.Combine(_imageTaskRoot, "image_index.json")));
                ImageCandidates.Clear(); foreach (var item in index.RootElement.GetProperty("image_paths").EnumerateArray()) ImageCandidates.Add(item.GetString()!);
                ImageStatus = evt.Summary ?? "Chọn ảnh để nhận dạng chữ.";
            }
            else if (task == "image_extract") TryLoadImageReview(Path.Combine(_imageTaskRoot, "image_text.json"));
            else if (task is "image_delivery" or "image_apply" or "image_rollback")
            {
                if (task == "image_delivery") { _imagePackage = _imageTaskRoot; _packageReviewVersion = _renderedReviewVersion; }
                ImageStatus = UiText.Msg("{0} {1}", UiText.Key(evt.Summary ?? "Đã xử lý gói ảnh"), _imageTaskRoot);
            }
            else { _renderedImage = Path.Combine(_imageTaskRoot, "translated.png"); _renderedReviewVersion = _imageTaskReviewVersion ?? _imageReviewVersion; ImagePreview = LoadImagePreview(Path.Combine(_imageTaskRoot, "translated.png")); ImageStatus = UiText.Msg("{0} {1}", UiText.Key(evt.Summary ?? "Đã dựng ảnh"), _imageTaskRoot); }
        }
        catch (Exception e) { ImageStatus = UiText.Msg("Không đọc được kết quả ảnh: {0}", e.Message); }
            finally { StatusText = ImageStatus; AppendLog(ImageStatus); SelectedTab = WorkflowTabs.Images; RefreshImageCommands(); }
    }
}
