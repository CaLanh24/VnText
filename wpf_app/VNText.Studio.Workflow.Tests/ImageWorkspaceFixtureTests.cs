using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using VNText.Studio.App.Controls;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    private static bool PumpUntil(Func<bool> condition, int seconds)
    {
        var deadline = DateTime.UtcNow.AddSeconds(seconds);
        while (!condition() && DateTime.UtcNow < deadline)
        {
            var frame = new System.Windows.Threading.DispatcherFrame();
            System.Windows.Threading.Dispatcher.CurrentDispatcher.BeginInvoke(System.Windows.Threading.DispatcherPriority.Background, new Action(() => frame.Continue = false));
            System.Windows.Threading.Dispatcher.PushFrame(frame);
            Thread.Sleep(20);
        }
        return condition();
    }

    /// <summary>
    /// Real WPF fixture for the restored "Text trong ảnh" workspace: loads the compiled XAML inside the shared themed
    /// dialog shell and proves the bindings, enabled states, busy lock and Esc dismissal against a real view model.
    /// No worker, OCR or model is started; commands are only inspected, never executed.
    /// </summary>
    private static int RunImageWorkspaceFixture()
    {
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            var root = Path.Combine(TestTempRoot(), "vntext_wpf_image_workspace_" + Guid.NewGuid().ToString("N"));
            try
            {
                var app = new Application { ShutdownMode = ShutdownMode.OnExplicitShutdown };
                foreach (var dictionary in new[] { "DesignTokens", "IconGeometries", "ControlStyles" })
                    app.Resources.MergedDictionaries.Add(new ResourceDictionary { Source = new Uri($"pack://application:,,,/VNText.Studio.App;component/Themes/{dictionary}.xaml") });

                // OCR-only supported container: genuine game/ layout, the only text is inside an image; the CSV has no data rows.
                var container = Path.Combine(root, "container");
                var package = Path.Combine(root, "package");
                Directory.CreateDirectory(Path.Combine(container, "game", "images"));
                Directory.CreateDirectory(Path.Combine(package, "images"));
                File.WriteAllText(Path.Combine(container, "game", "options.rpy"), "define config.version = \"1.0\"\n", Encoding.UTF8);
                var png = Path.Combine(container, "game", "images", "ui_01.png");
                var pixels = Enumerable.Repeat((byte)255, 300 * 120 * 4).ToArray();
                var encoder = new System.Windows.Media.Imaging.PngBitmapEncoder();
                encoder.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(System.Windows.Media.Imaging.BitmapSource.Create(300, 120, 96, 96, PixelFormats.Bgra32, null, pixels, 300 * 4)));
                using (var stream = File.Create(png)) encoder.Save(stream);
                File.WriteAllText(Path.Combine(package, "translation.csv"), "key,source_text,translation,context,file_path,import_method\r\n", new UTF8Encoding(true));
                File.WriteAllText(Path.Combine(package, "manifest.json"), """{"entries":[]}""", Encoding.UTF8);
                File.WriteAllText(Path.Combine(package, "images", "report.json"), """{"schema":1,"items":[{"status":"OCR_READY"},{"status":"OCR_READY"},{"status":"UNTRANSLATED"}]}""", Encoding.UTF8);

                using var worker = new PythonWorkerHost();
                var picker = new FakePathPicker();
                using var vm = new MainViewModel(picker, worker, startWorker: false) { InputPath = container, OutputPath = package };
                vm.TestSetTranslationModelReady(true);
                var owner = new Window { Title = "Workspace fixture owner", Width = 1200, Height = 800 };
                owner.Show();
                var panel = new ImageWorkspacePanel { DataContext = vm };
                vm.RefreshImageWorkspace();
                var dialog = new AppDialogWindow(owner, "Text trong ảnh", panel, 1040);
                dialog.AddButton("Đóng", () => { });
                dialog.Show();
                dialog.UpdateLayout();

                Button B(string name) => panel.FindName(name) as Button ?? throw new InvalidOperationException("missing button " + name);
                // Every workflow stage is a real, bound control.
                AssertTrue(ReferenceEquals(B("DiscoverButton").Command, vm.DiscoverImagesCommand));
                AssertTrue(ReferenceEquals(B("ChooseButton").Command, vm.ChooseOcrImageCommand));
                AssertTrue(ReferenceEquals(B("OcrButton").Command, vm.RunImageOcrCommand));
                AssertTrue(ReferenceEquals(B("OpenReviewButton").Command, vm.OpenImageReviewCommand));
                AssertTrue(ReferenceEquals(B("AddRegionButton").Command, vm.AddImageRegionCommand));
                AssertTrue(ReferenceEquals(B("SaveReviewButton").Command, vm.SaveImageReviewCommand));
                AssertTrue(ReferenceEquals(B("RenderButton").Command, vm.RenderImageCommand));
                AssertTrue(ReferenceEquals(B("DeliveryButton").Command, vm.CreateImageDeliveryCommand));
                AssertTrue(ReferenceEquals(B("InstallButton").Command, vm.InstallImageDeliveryCommand));
                AssertTrue(ReferenceEquals(B("RecoverButton").Command, vm.RecoverImageDeliveryCommand));
                AssertTrue(ReferenceEquals(B("OpenOutputButton").Command, vm.OpenOutputCommand));
                var grid = panel.FindName("RegionGrid") as DataGrid ?? throw new InvalidOperationException("missing RegionGrid");
                AssertTrue(ReferenceEquals(grid.ItemsSource, vm.ImageRegions));
                // Compact main grid: reviewed line by line; crop/font/colour/background live in the labelled detail form.
                var bound = grid.Columns.OfType<DataGridBoundColumn>().Select(c => ((System.Windows.Data.Binding)c.Binding).Path.Path).ToArray();
                AssertEqual("SourceText,ModeSummary,Approved", string.Join(",", bound));
                AssertEqual(5, grid.Columns.Count);                       // OCR text, translation, mode summary, approve, delete
                AssertTrue(((TextBlock)panel.FindName("IntroText")).Text.Contains("BẢN SAO", StringComparison.Ordinal));
                AssertFalse(((TextBlock)panel.FindName("IntroText")).Text.Contains("game không bị sửa", StringComparison.Ordinal));
                // Accessibility: every form control has a name; none of the four background modes is ticked by default.
                foreach (var name in new[] { "RegionXBox", "RegionYBox", "RegionWidthBox", "RegionHeightBox", "RegionFontBox", "RegionBackgroundBox", "RegionForegroundBox",
                                             "FlatModeBox", "TransparentModeBox", "SolidModeBox", "CloneModeBox", "DonorXBox", "DonorYBox", "ApproveBox", "CancelButton", "TaskText", "ProgressText", "StatusLine" })
                    AssertTrue(!string.IsNullOrWhiteSpace(System.Windows.Automation.AutomationProperties.GetName((DependencyObject)panel.FindName(name))));
                AssertTrue(((TextBlock)panel.FindName("WorkspaceSummary")).Text.Contains("2 đã OCR", StringComparison.Ordinal));

                // Text-less CSV package: the image path is open and the text patch/translate stay closed.
                vm.NavigateTabCommand.Execute(WorkflowTabs.Translate);
                AssertTrue(PumpUntil(() => !vm.TranslateReadinessText.Contains("Đang kiểm tra", StringComparison.Ordinal), 10));
                AssertTrue(B("DiscoverButton").IsEnabled);
                AssertFalse(B("OcrButton").IsEnabled);                  // no image chosen yet
                AssertFalse(B("RenderButton").IsEnabled);               // nothing reviewed yet
                AssertFalse(B("DeliveryButton").IsEnabled);
                AssertFalse(B("InstallButton").IsEnabled);
                AssertFalse(vm.RunTranslateCommand.CanExecute(null));
                AssertFalse(vm.RunPatchCommand.CanExecute(null));

                // Choosing a real game image enables OCR; a loaded review enables region editing, save and render.
                vm.ImagePath = png;
                AssertTrue(B("OcrButton").IsEnabled);
                var sourceHash = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(png))).ToLowerInvariant();
                var review = Path.Combine(root, "image_text.json");
                File.WriteAllText(review, JsonSerializer.Serialize(new ImageTextDocument
                {
                    SourcePath = png, SourceSha256 = sourceHash, Width = 300, Height = 120, Status = "REVIEW_REQUIRED",
                    Regions = new List<ImageTextRegion> { new() { Id = "r1", Box = new[] { 10, 10, 200, 40 }, SourceText = "Hello" } },
                }, MainViewModel.ImageJson), Encoding.UTF8);
                AssertTrue(vm.TryLoadImageReview(review));
                var keptPath = vm.ImagePath;                              // the source as the app resolved it (long path form)
                panel.UpdateLayout();
                AssertEqual(1, vm.ImageRegions.Count);
                AssertTrue(B("SaveReviewButton").IsEnabled);
                AssertTrue(B("RenderButton").IsEnabled);
                AssertTrue(B("AddRegionButton").IsEnabled);
                var region = vm.ImageRegions[0];
                AssertFalse(region.Approved);                           // nothing is approved by loading or by the UI
                AssertFalse(region.FlatBackgroundApproved || region.TransparentTextApproved || region.ReplacementBackgroundApproved || region.CloneBackgroundApproved);
                AssertEqual("Chưa chọn chế độ nền", region.ModeSummary);
                AssertTrue(((FrameworkElement)panel.FindName("RegionDetailsHint")).IsVisible);
                AssertFalse(((FrameworkElement)panel.FindName("RegionDetailsForm")).IsVisible);
                vm.SelectedImageRegion = region;                         // what clicking a grid row does
                panel.UpdateLayout();
                AssertTrue(((FrameworkElement)panel.FindName("RegionDetailsForm")).IsVisible);
                AssertFalse(((FrameworkElement)panel.FindName("RegionDetailsHint")).IsVisible);
                CheckBox C(string name) => (CheckBox)panel.FindName(name);
                TextBox T(string name) => (TextBox)panel.FindName(name);
                AssertEqual("10", T("RegionXBox").Text);
                AssertEqual("200", T("RegionWidthBox").Text);
                // Explicit approval through the controls; the four modes stay independent flags.
                C("FlatModeBox").IsChecked = true;
                C("ApproveBox").IsChecked = true;
                AssertTrue(region.FlatBackgroundApproved && region.Approved);
                AssertEqual("Nền phẳng", region.ModeSummary);
                C("CloneModeBox").IsChecked = true;                      // a second mode is shown as invalid, never silently dropped
                AssertEqual("Chọn nhiều chế độ — cần đúng một", region.ModeSummary);
                C("CloneModeBox").IsChecked = false;
                // Editing any reviewed value through the form clears approval and every mode choice.
                T("RegionXBox").Text = "20";
                AssertEqual(20, region.X);
                AssertFalse(region.Approved);
                AssertFalse(region.FlatBackgroundApproved);
                AssertEqual("Chưa chọn chế độ nền", region.ModeSummary);
                C("FlatModeBox").IsChecked = true; C("ApproveBox").IsChecked = true;
                AssertTrue(region.Approved);
                region.Translation = "Trò chơi mới";                   // translation edit (grid cell) also invalidates
                AssertFalse(region.Approved);

                // Idle: no phantom work shown.
                AssertFalse(((FrameworkElement)panel.FindName("TaskBanner")).IsVisible);
                AssertEqual("", vm.ImageWorkspaceTaskText);
                // A running image task: owner shown, everything locked, Cancel available inside the modal.
                vm.TestSetActiveTask("fixture-image", "image_extract");
                panel.UpdateLayout();
                foreach (var name in new[] { "DiscoverButton", "ChooseButton", "OcrButton", "OpenReviewButton", "AddRegionButton", "SaveReviewButton", "RenderButton" })
                    AssertFalse(B(name).IsEnabled);
                AssertFalse(grid.IsEnabled);
                AssertFalse(((ComboBox)panel.FindName("CandidateCombo")).IsEnabled);     // the source cannot change under a running task
                AssertFalse(((FrameworkElement)panel.FindName("RegionDetails")).IsEnabled);
                AssertTrue(((FrameworkElement)panel.FindName("TaskBanner")).IsVisible);
                AssertTrue(((TextBlock)panel.FindName("TaskText")).Text.Contains("OCR ảnh", StringComparison.Ordinal));
                AssertTrue(((FrameworkElement)panel.FindName("TaskSpinner")).IsVisible);
                AssertTrue(ReferenceEquals(B("CancelButton").Command, vm.CancelCommand));
                AssertTrue(B("CancelButton").IsEnabled);
                // Cancel request -> acknowledgement are visible in the panel and the worker lifecycle is the normal one.
                vm.CancelCommand.Execute(null);
                panel.UpdateLayout();
                AssertTrue(((TextBlock)panel.FindName("ProgressText")).Text.Contains("hủy", StringComparison.OrdinalIgnoreCase));
                vm.TestHandleWorkerEvent(new WorkerEvent { Type = "cancel_ack", Id = "fixture-image", State = "accepted" });
                panel.UpdateLayout();
                AssertTrue(((TextBlock)panel.FindName("ProgressText")).Text.Contains("dừng an toàn", StringComparison.Ordinal));
                // Terminal: banner, spinner, task text and cancel disappear; controls unlock.
                vm.TestMarkTaskTerminal("fixture-image");
                panel.UpdateLayout();
                AssertFalse(((FrameworkElement)panel.FindName("TaskBanner")).IsVisible);
                AssertFalse(((FrameworkElement)panel.FindName("TaskSpinner")).IsVisible);
                AssertEqual("", vm.ImageWorkspaceTaskText);
                AssertEqual("", vm.ImageWorkspaceProgressText);
                AssertTrue(B("DiscoverButton").IsEnabled);
                AssertTrue(grid.IsEnabled);
                AssertTrue(((ComboBox)panel.FindName("CandidateCombo")).IsEnabled);
                // Another (non-image) task owning the worker is named and can be cancelled from here as well.
                vm.TestSetActiveTask("fixture-translate", "translate");
                panel.UpdateLayout();
                AssertFalse(((ComboBox)panel.FindName("CandidateCombo")).IsEnabled);
                AssertTrue(((TextBlock)panel.FindName("TaskText")).Text.Contains("tác vụ khác", StringComparison.Ordinal));
                AssertTrue(B("CancelButton").IsEnabled);
                vm.TestMarkTaskTerminal("fixture-translate");
                panel.UpdateLayout();
                AssertTrue(((ComboBox)panel.FindName("CandidateCombo")).IsEnabled);

                // ---- cancel -> acknowledgement -> terminal for each image task: explicit Vietnamese "Đã hủy", nothing applied ----
                void Terminal(string id, bool ok, string error) =>
                    vm.TestHandleWorkerEvent(new WorkerEvent { Type = "complete", Id = id, Ok = ok, Complete = ok, Error = error });
                foreach (var (task, label) in new[] { ("image_extract", "OCR ảnh"), ("image_render", "dựng ảnh"), ("image_batch", "dịch nháp ảnh") })
                {
                    var id = "cancel-" + task;
                    vm.MarkReviewForTest();
                    vm.TestSetActiveTask(id, task);
                    vm.CancelCommand.Execute(null);
                    vm.TestHandleWorkerEvent(new WorkerEvent { Type = "cancel_ack", Id = id, State = "accepted" });
                    AssertTrue(vm.Busy);                                    // still busy until the worker reports the terminal
                    Terminal(id, false, "cancelled");
                    panel.UpdateLayout();
                    AssertFalse(vm.Busy);
                    AssertTrue(vm.ImageStatus.StartsWith("Đã hủy", StringComparison.Ordinal));
                    AssertTrue(vm.ImageStatus.Contains(label, StringComparison.Ordinal));
                    AssertFalse(vm.ImageStatus.Contains("cancelled", StringComparison.OrdinalIgnoreCase));
                    AssertTrue(vm.ImageStatus.Contains("Ảnh gốc được giữ nguyên", StringComparison.Ordinal));
                    AssertTrue(vm.ImageStatus.Contains("có thể còn trong thư mục xuất", StringComparison.Ordinal));   // no rollback promise
                    AssertFalse(vm.ImageStatus.Contains("không áp dụng kết quả nào", StringComparison.Ordinal));
                    AssertFalse(vm.ImageStatus.Contains("Chưa hoàn tất", StringComparison.Ordinal));
                    AssertFalse(vm.ImageStatus.Contains("Đã render", StringComparison.Ordinal));
                    AssertEqual(vm.ImageStatus, vm.StatusText);
                    AssertFalse(((FrameworkElement)panel.FindName("TaskBanner")).IsVisible);
                    AssertFalse(vm.CreateImageDeliveryCommand.CanExecute(null));   // a cancelled render produced nothing to deliver
                    AssertEqual(keptPath, vm.ImagePath);                          // the chosen source and the loaded review are kept
                    AssertEqual(1, vm.ImageRegions.Count);
                }
                // An ordinary failure still reads as an error, not as a cancellation.
                vm.TestSetActiveTask("fail-render", "image_render");
                Terminal("fail-render", false, "Ảnh nguồn đã thay đổi");
                AssertEqual("Chưa hoàn tất: Ảnh nguồn đã thay đổi", vm.ImageStatus);

                // ---- OCR retry without the picker: a new OCR run clears the OLD review but keeps the chosen source ----
                vm.PrepareImageExtractState();
                AssertEqual(keptPath, vm.ImagePath);
                AssertEqual(0, vm.ImageRegions.Count);
                AssertTrue(vm.SelectedImageRegion is null);
                AssertTrue(vm.ImagePreview is null);
                vm.TestSetActiveTask("ocr-1", "image_extract");
                Terminal("ocr-1", false, "cancelled");                   // cancelled OCR
                AssertEqual(keptPath, vm.ImagePath);
                AssertTrue(vm.RunImageOcrCommand.CanExecute(null));
                AssertTrue(B("OcrButton").IsEnabled);
                vm.PrepareImageExtractState();
                vm.TestSetActiveTask("ocr-2", "image_extract");
                Terminal("ocr-2", false, "OCR quá 60 giây");             // failed OCR
                AssertEqual("Chưa hoàn tất: OCR quá 60 giây", vm.ImageStatus);
                AssertEqual(keptPath, vm.ImagePath);
                AssertTrue(vm.RunImageOcrCommand.CanExecute(null));

                // ---- late result for a different image is dropped, never attached ----
                vm.MarkImageTaskIdentityForTest();                       // task started for `png`
                var other = Path.Combine(Path.GetDirectoryName(png)!, "ui_02.png");
                File.Copy(png, other);
                vm.ImagePath = other;                                   // selection changed some other way
                vm.TestSetActiveTask("late-render", "image_render");
                Terminal("late-render", true, "");
                AssertTrue(vm.ImageStatus.Contains("kết quả cũ bị bỏ", StringComparison.Ordinal));
                AssertFalse(vm.CreateImageDeliveryCommand.CanExecute(null));
                AssertEqual(other, vm.ImagePath);
                vm.ImagePath = keptPath;
                // a selected region is dropped whenever the source changes
                vm.ImagePath = other;
                AssertTrue(vm.SelectedImageRegion is null);

                // ---- (A) preview overlay is in SOURCE PIXELS whatever the file's DPI metadata says ----
                foreach (var (dpiX, dpiY) in new[] { (96d, 96d), (300d, 300d), (96d, 300d) })
                {
                    var dpiPng = Path.Combine(container, "game", "images", $"dpi_{dpiX:0}_{dpiY:0}.png");
                    var dpiPixels = Enumerable.Repeat((byte)255, 600 * 200 * 4).ToArray();
                    var dpiSource = System.Windows.Media.Imaging.BitmapSource.Create(600, 200, dpiX, dpiY, PixelFormats.Bgra32, null, dpiPixels, 600 * 4);
                    var dpiEncoder = new System.Windows.Media.Imaging.PngBitmapEncoder();
                    dpiEncoder.Frames.Add(System.Windows.Media.Imaging.BitmapFrame.Create(dpiSource));
                    using (var dpiStream = File.Create(dpiPng)) dpiEncoder.Save(dpiStream);
                    var dpiHash = Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(dpiPng))).ToLowerInvariant();
                    var dpiReview = Path.Combine(root, $"review_{dpiX:0}_{dpiY:0}.json");
                    File.WriteAllText(dpiReview, JsonSerializer.Serialize(new ImageTextDocument
                    {
                        SourcePath = dpiPng, SourceSha256 = dpiHash, Width = 600, Height = 200, Status = "REVIEW_REQUIRED",
                        Regions = new List<ImageTextRegion> { new() { Id = "r1", Box = new[] { 10, 20, 200, 40 }, SourceText = "Hello" } },
                    }, MainViewModel.ImageJson), Encoding.UTF8);
                    AssertTrue(vm.TryLoadImageReview(dpiReview));
                    panel.UpdateLayout();
                    var loadedBitmap = (System.Windows.Media.Imaging.BitmapSource)vm.ImagePreview!;
                    AssertEqual(600, loadedBitmap.PixelWidth);
                    if (dpiX != 96d || dpiY != 96d) AssertTrue(Math.Abs(loadedBitmap.Width - 600) > 1 || Math.Abs(loadedBitmap.Height - 200) > 1);   // the DIP size really differs
                    AssertEqual(600d, vm.ImagePreviewPixelWidth);
                    AssertEqual(200d, vm.ImagePreviewPixelHeight);
                    var canvas = (Grid)panel.FindName("PreviewCanvas");
                    var image = (Image)panel.FindName("PreviewImage");
                    AssertEqual(600d, canvas.ActualWidth); AssertEqual(200d, canvas.ActualHeight);
                    AssertEqual(600d, image.ActualWidth); AssertEqual(200d, image.ActualHeight);
                    var box = FindVisual<System.Windows.Shapes.Rectangle>(canvas) ?? throw new InvalidOperationException("no region rectangle drawn");
                    var origin = box.TransformToAncestor(canvas).Transform(new Point(0, 0));
                    AssertEqual(10d, origin.X); AssertEqual(20d, origin.Y);                // the box sits on the same source pixels as the artwork
                    AssertEqual(200d, box.ActualWidth); AssertEqual(40d, box.ActualHeight);
                }

                // ---- (B) the rendered snapshot belongs to the review it was made from (real loaded review, real commands) ----
                AssertTrue(vm.TryLoadImageReview(review));
                var live = vm.ImageRegions[0];
                void Approve(ImageTextRegion r, string text) { r.Translation = text; r.FlatBackgroundApproved = true; r.Approved = true; }
                void RenderOk(string id)
                {
                    vm.RenderImageCommand.Execute(null);
                    AssertFalse(vm.ImageStatus.StartsWith("Duyệt", StringComparison.Ordinal));     // not refused
                    Directory.CreateDirectory(vm.ImageTaskRootForTest);
                    File.Copy(png, Path.Combine(vm.ImageTaskRootForTest, "translated.png"), overwrite: true);
                    vm.TestSetActiveTask(id, "image_render");
                    Terminal(id, true, "");
                    AssertFalse(vm.Busy);
                }
                void DeliverOk(string id)
                {
                    vm.CreateImageDeliveryCommand.Execute(null);
                    Directory.CreateDirectory(vm.ImageTaskRootForTest);
                    vm.TestSetActiveTask(id, "image_delivery");
                    Terminal(id, true, "");
                    AssertFalse(vm.Busy);
                }
                AssertFalse(vm.CreateImageDeliveryCommand.CanExecute(null));          // nothing rendered yet
                Approve(live, "Trò chơi mới");
                RenderOk("render-1");
                var firstRender = Path.Combine(vm.ImageTaskRootForTest, "translated.png");
                AssertTrue(vm.CreateImageDeliveryCommand.CanExecute(null));
                DeliverOk("deliver-1");
                var firstPackage = vm.ImageTaskRootForTest;
                AssertTrue(vm.InstallImageDeliveryCommand.CanExecute(null));
                // Edit the translation after render + package: both are revoked, the files stay as history, the preview returns to the source.
                live.Translation = "Bản dịch khác";
                AssertFalse(vm.CreateImageDeliveryCommand.CanExecute(null));
                AssertFalse(vm.InstallImageDeliveryCommand.CanExecute(null));
                AssertTrue(vm.ImageStatus.StartsWith("Review đã đổi sau khi dựng ảnh", StringComparison.Ordinal));
                AssertTrue(File.Exists(firstRender) && Directory.Exists(firstPackage));
                // Direct Execute (it does not consult CanExecute) must be refused BEFORE the picker, a new root or a worker task.
                var picksBefore = picker.InputPicks; var rootBefore = vm.ImageTaskRootForTest; var logBefore = vm.LogLines.Count;
                vm.InstallImageDeliveryCommand.Execute(null);
                AssertEqual(picksBefore, picker.InputPicks);                         // no folder picker opened
                AssertEqual(rootBefore, vm.ImageTaskRootForTest);                    // no new task root
                AssertFalse(vm.Busy);                                                // no worker task started
                AssertTrue(vm.ImageStatus.Contains("Dựng lại ảnh", StringComparison.Ordinal));
                vm.CreateImageDeliveryCommand.Execute(null);
                AssertEqual(rootBefore, vm.ImageTaskRootForTest);
                AssertFalse(vm.Busy);
                AssertTrue(vm.ImageStatus.StartsWith("Chưa thể tạo gói ảnh", StringComparison.Ordinal));
                AssertFalse(vm.LogLines.Skip(logBefore).Any(l => l.Contains("Gửi lệnh worker", StringComparison.Ordinal)));
                AssertTrue(ReferenceEquals(vm.ImagePreview, vm.ImagePreview) && vm.ImagePreviewPixelWidth == 300);
                // Re-render with the current review restores readiness.
                Approve(live, "Bản dịch khác");
                RenderOk("render-2");
                AssertTrue(vm.CreateImageDeliveryCommand.CanExecute(null));
                AssertFalse(vm.InstallImageDeliveryCommand.CanExecute(null));          // the old package belongs to the old review
                // Revoking approval, changing the mode, geometry or the collection each revoke the render; re-approving alone does not restore it.
                live.Approved = false;
                AssertFalse(vm.CreateImageDeliveryCommand.CanExecute(null));
                var revokeRoot = vm.ImageTaskRootForTest; var revokePicks = picker.InputPicks;
                vm.CreateImageDeliveryCommand.Execute(null); vm.InstallImageDeliveryCommand.Execute(null);
                AssertEqual(revokeRoot, vm.ImageTaskRootForTest); AssertEqual(revokePicks, picker.InputPicks); AssertFalse(vm.Busy);
                live.Approved = true;
                AssertFalse(vm.CreateImageDeliveryCommand.CanExecute(null));
                RenderOk("render-3");
                AssertTrue(vm.CreateImageDeliveryCommand.CanExecute(null));
                live.TransparentTextApproved = true;                                    // background mode change
                AssertFalse(vm.CreateImageDeliveryCommand.CanExecute(null));
                live.TransparentTextApproved = false;
                RenderOk("render-4");
                live.X = 11;                                                            // crop change (also clears approval and modes)
                AssertFalse(vm.CreateImageDeliveryCommand.CanExecute(null));
                Approve(live, "Bản dịch khác");
                RenderOk("render-5");
                vm.AddImageRegionCommand.Execute(null);                                 // collection change: add
                AssertFalse(vm.CreateImageDeliveryCommand.CanExecute(null));
                vm.RemoveImageRegionCommand.Execute(vm.ImageRegions[^1]);               // collection change: remove
                AssertFalse(vm.CreateImageDeliveryCommand.CanExecute(null));
                RenderOk("render-6");
                AssertTrue(vm.CreateImageDeliveryCommand.CanExecute(null));
                // A result that arrives after the review changed under it (same path) is dropped, never attached.
                vm.RenderImageCommand.Execute(null);                                    // task started for this review version
                Directory.CreateDirectory(vm.ImageTaskRootForTest);
                File.Copy(png, Path.Combine(vm.ImageTaskRootForTest, "translated.png"), overwrite: true);
                live.Translation = "Đổi trong lúc dựng";                                 // review changes while the task is in flight
                vm.TestSetActiveTask("render-late", "image_render");
                Terminal("render-late", true, "");
                AssertTrue(vm.ImageStatus.Contains("Review đã đổi trong lúc xử lý", StringComparison.Ordinal));
                AssertFalse(vm.CreateImageDeliveryCommand.CanExecute(null));
                AssertFalse(vm.InstallImageDeliveryCommand.CanExecute(null));
                Approve(live, "Đổi trong lúc dựng");
                RenderOk("render-7");                                                   // a fresh render restores readiness
                AssertTrue(vm.CreateImageDeliveryCommand.CanExecute(null));

                // Both entry points reach the same dialog through one command.
                var requested = 0;
                vm.ImageWorkspaceRequested += () => requested++;
                vm.OpenImageWorkspaceCommand.Execute(null);
                AssertEqual(1, requested);

                // Esc dismisses the themed shell like every other dialog.
                dialog.Dismiss();
                AssertFalse(dialog.IsVisible);
                owner.Close();
                Console.WriteLine("WPF image workspace fixture: PASS");
                exitCode = 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("WPF image workspace fixture: FAIL " + ex);
            }
            finally
            {
                try { if (Directory.Exists(root)) Directory.Delete(root, true); } catch (IOException) { }
                Application.Current?.Dispatcher.InvokeShutdown();
            }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        return exitCode;
    }
}
