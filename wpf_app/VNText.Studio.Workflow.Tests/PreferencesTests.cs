using System.IO;
using System.ComponentModel;
using System.Net;
using System.Net.Http;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;
using VNText.Studio.App;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static class PreferencesTests
{
    private sealed class NotesHttpHandler(Func<HttpResponseMessage> response) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            Check(request.RequestUri?.ToString()=="https://api.github.com/repos/CaLanh24/VnText/releases?per_page=100", "history uses the official release endpoint");
            return Task.FromResult(response());
        }
    }
    private static void Check(bool value,string name) { if(!value)throw new InvalidOperationException(name); }
    public static int Run()
    {
        var root=Environment.GetEnvironmentVariable("VNTEXT_LOCALAPPDATA") ?? throw new InvalidOperationException("isolated preference root required");
        Check(Path.GetFullPath(root).Contains(Path.DirectorySeparatorChar+"TEST_RUN"+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase),"tests require TEST_RUN isolation");
        var app=new VNText.Studio.App.App(); app.InitializeComponent(); app.ShutdownMode=ShutdownMode.OnExplicitShutdown;
        try
        {
            var settings=new AppSettings { Language="en",Theme="dark",CloseAction="tray",StartMinimized=true,BackgroundStrength=40,BackgroundUpdateDownload=true,UpdateReminderHours=4,
                ReleaseNotesHistory=[new ReleaseNotesCacheEntry { Version="0.1.11", ReleaseDate="2026-10-24", Notes="Ghi chú tiếng Việt", CachedAtUtc=DateTime.UtcNow }] };
            AppSettingsStore.Save(settings); var loaded=AppSettingsStore.Load();
            Check(loaded.Language=="en" && loaded.Theme=="dark" && loaded.CloseAction=="tray" && loaded.StartMinimized && loaded.BackgroundStrength==40 && loaded.BackgroundUpdateDownload && loaded.UpdateReminderHours==4,"preference round-trip");
            Check(loaded.ReleaseNotesHistory.Count==1 && loaded.ReleaseNotesHistory[0].Version=="0.1.11" && loaded.ReleaseNotesHistory[0].ReleaseDate=="2026-10-24" && loaded.ReleaseNotesHistory[0].Notes=="Ghi chú tiếng Việt" && loaded.ReleaseNotesHistory[0].DisplayLabel.Contains("2026-10-24",StringComparison.Ordinal),"release notes history persistence / date label");
            var historyCards = UpdateWindow.RenderHistory(new Border(), new[] {
                loaded.ReleaseNotesHistory[0], new ReleaseNotesCacheEntry { Version="0.1.10", Notes="- Sửa giao diện" } });
            Check(historyCards.Children.OfType<Border>().Count()==2, "each cached release has its own visible card");
            Check(loaded.ReleaseNotesHistory[0].DownloadUrl=="https://github.com/CaLanh24/VnText/releases/tag/v0.1.11", "release download is version-matched");
            Check(new ReleaseNotesCacheEntry { Version="0.1.11/../../evil" }.DownloadUrl=="", "invalid cached version cannot become a download link");
            using (var historyHandler = new NotesHttpHandler(() => new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(JsonSerializer.Serialize(new[] {
                new { tag_name="v0.1.11", draft=false, prerelease=false, body="- Giao diện", published_at="2026-10-24T08:00:00Z", assets=Array.Empty<object>() },
                new { tag_name="v0.1.13", draft=true, prerelease=false, body="Nháp", published_at="2026-10-25T08:00:00Z", assets=Array.Empty<object>() },
                new { tag_name="v0.1.12", draft=false, prerelease=false, body="- Tiến trình", published_at="2026-10-25T08:00:00Z", assets=Array.Empty<object>() }
            })) }))
            {
                var history = WpfUpdateService.ReadReleaseNotesHistoryAsync(historyHandler).GetAwaiter().GetResult();
                Check(history.Error=="" && history.Entries.Count==2 && history.Entries[0].Version=="0.1.12" && history.Entries[1].Version=="0.1.11", "history fetch is independent of installed updater baseline and excludes drafts");
            }
            using (var offlineHandler = new NotesHttpHandler(() => new HttpResponseMessage(HttpStatusCode.ServiceUnavailable)))
            {
                var offline = WpfUpdateService.ReadReleaseNotesHistoryAsync(offlineHandler).GetAwaiter().GetResult();
                Check(offline.Entries.Count==0 && offline.Error.Length>0, "offline history reports failure without replacing cached entries");
            }
            loaded.ReleaseNotesHistory=[.. Enumerable.Range(1,25).Select(i=>new ReleaseNotesCacheEntry { Version=$"1.0.{i}", Notes=new string('x',16001), CachedAtUtc=DateTime.UtcNow.AddSeconds(i) })];
            AppSettingsStore.Save(loaded); loaded=AppSettingsStore.Load();
            Check(loaded.ReleaseNotesHistory.Count==20 && loaded.ReleaseNotesHistory.All(entry=>entry.Notes.Length==16000),"release notes history bounds");
            settings.Language="bad";settings.Theme="bad";settings.CloseAction="bad";settings.BackgroundStrength=double.NaN;settings.UpdateReminderHours=1;
            AppSettingsStore.Save(settings);loaded=AppSettingsStore.Load();
            Check(loaded.Language=="vi" && loaded.Theme=="light" && loaded.CloseAction=="exit" && loaded.BackgroundStrength==100 && loaded.UpdateReminderHours==24,"normalization");
            var path=AppSettingsStore.SettingsPath();File.WriteAllText(path,"{broken");AppSettingsStore.Load(out var error);
            Check(error.Length>0,"corruption surfaced");try { AppSettingsStore.Save(new());throw new Exception("corrupt file overwritten"); }catch(JsonException){}
            Check(File.ReadAllText(path)=="{broken","corrupt bytes retained");File.Delete(path);
            Console.WriteLine("PASS persistence / ranges / corrupt-file preservation");

            UiText.Install();UiText.SetLanguage("en");
            var literal=new TextBlock { Text="Cài đặt" };var userText=new TextBlock();userText.SetBinding(TextBlock.TextProperty,new Binding { Source="Cài đặt" });
            var panel=new StackPanel();panel.Children.Add(literal);panel.Children.Add(userText);var localizationWindow=new Window { Content=panel,Width=300,Height=120 };
            localizationWindow.Show();UiText.Apply(localizationWindow);
            Check(literal.Text=="Settings" && userText.Text=="Cài đặt","localization excludes user bindings");
            UiText.SetLanguage("vi");UiText.Apply(localizationWindow);Check(literal.Text=="Cài đặt","language reversal");localizationWindow.Close();
            Console.WriteLine("PASS language switch / bound-user-data isolation");

            UiAppearance.Apply("dark",100);Check(((SolidColorBrush)app.FindResource("SurfaceBrush")).Color==Color.FromRgb(32,43,60),"dark palette");
            UiAppearance.Apply("light",0);var gradient=(LinearGradientBrush)app.FindResource("SidebarBrush");Check(gradient.GradientStops.All(s=>s.Color==Colors.White),"strength zero affects decorative palette");
            var zeroTop=RenderBrushPixel((Brush)app.FindResource("WorkspaceCanvasBrush"),230,30);
            var zeroBottom=RenderBrushPixel((Brush)app.FindResource("WorkspaceCanvasBrush"),230,240);
            Check(zeroTop.R>=254 && zeroTop.G>=254 && zeroTop.B>=254 && zeroBottom.R>=254 && zeroBottom.G>=254 && zeroBottom.B>=254,"zero strength neutralizes all canvas layers");
            UiAppearance.Apply("light",100);gradient=(LinearGradientBrush)app.FindResource("SidebarBrush");Check(gradient.GradientStops.First().Color!=gradient.GradientStops.Last().Color,"sidebar gradient");
            var canvas=(Brush)app.FindResource("WorkspaceCanvasBrush");
            var upper=RenderBrushPixel(canvas,230,30);var lower=RenderBrushPixel(canvas,230,240);var middle=RenderBrushPixel(canvas,120,30);
            Check(upper.G>upper.R+8 && lower.R>upper.R+10 && lower.B>=lower.G && middle.R>upper.R+10,"upper cyan and neutral lower canvas distribution");
            var title=(LinearGradientBrush)app.FindResource("SettingsTitleBrush");
            Check(title.GradientStops.First().Color!=title.GradientStops.Last().Color,"Settings title keeps distinct blue and cyan ends");
            Console.WriteLine($"PASS rendered canvas upper={upper}, lower={lower}, center={middle}; strength0 white");
            Console.WriteLine("PASS theme / background strength / gradient");

            var card = new Border { Width=180, Height=90 };
            VNText.Studio.App.Controls.HoverMotion.SetKind(card,"AboutCard");
            var motionWindow = new Window { Content=card, Width=220, Height=140 };motionWindow.Show();motionWindow.UpdateLayout();Pump(100);
            var lift=(TranslateTransform)((TransformGroup)card.RenderTransform).Children[1];
            var layoutHeight=card.ActualHeight;
            card.RaiseEvent(new System.Windows.Input.MouseEventArgs(System.Windows.Input.Mouse.PrimaryDevice,0) { RoutedEvent=System.Windows.Input.Mouse.MouseEnterEvent });
            Pump(60);Console.WriteLine($"About Y at intermediate frame: {lift.Y:R}");Check(lift.Y<0 && lift.Y>-1,"About card moves through intermediate upward positions");
            Pump(180);Check(Math.Abs(lift.Y+1)<.01 && card.ActualHeight==layoutHeight,"About lift endpoint without layout change");
            card.RaiseEvent(new System.Windows.Input.MouseEventArgs(System.Windows.Input.Mouse.PrimaryDevice,0) { RoutedEvent=System.Windows.Input.Mouse.MouseLeaveEvent });
            Pump(240);Check(Math.Abs(lift.Y)<.01,"About card returns to original position");motionWindow.Close();
            Console.WriteLine("PASS real WPF About translation / intermediate frame / return (not shadow-only)");

            var tabPill=new Border { Width=100,Height=40 };
            VNText.Studio.App.Controls.HoverMotion.SetKind(tabPill,"SettingsTab");
            var tabWindow=new Window { Content=tabPill,Width=220,Height=140 };tabWindow.Show();tabWindow.UpdateLayout();Pump(100);
            var tabScale=(ScaleTransform)((TransformGroup)tabPill.RenderTransform).Children[0];
            var tabLift=(TranslateTransform)((TransformGroup)tabPill.RenderTransform).Children[1];
            tabPill.RaiseEvent(new System.Windows.Input.MouseEventArgs(System.Windows.Input.Mouse.PrimaryDevice,0) { RoutedEvent=System.Windows.Input.Mouse.MouseEnterEvent });
            Pump(60);Console.WriteLine($"Tab pill intermediate scale: {tabScale.ScaleX:R}");Check(tabScale.ScaleX>1 && tabScale.ScaleX<1.025 && tabLift.Y==0,"whole pill scales from center without vertical movement");
            Pump(180);Check(Math.Abs(tabScale.ScaleX-1.025)<.001 && tabLift.Y==0,"tab pill zoom endpoint without lift");
            tabPill.RaiseEvent(new System.Windows.Input.MouseEventArgs(System.Windows.Input.Mouse.PrimaryDevice,0) { RoutedEvent=System.Windows.Input.Mouse.MouseLeaveEvent });
            Pump(240);Check(Math.Abs(tabScale.ScaleX-1)<.001 && Math.Abs(tabScale.ScaleY-1)<.001 && tabLift.Y==0,"tab pill scale returns");tabWindow.Close();
            Console.WriteLine("PASS whole tab pill centered zoom / no translation / return");

            var policy=new AppSettings { BackgroundUpdateDownload=true,NotifyUpdates=true };
            Check(UpdatePreferencePolicy.CanDownload(policy,false,false,"1.0.1"),"download opted in");
            Check(!UpdatePreferencePolicy.CanDownload(policy,true,false,"1.0.1") && !UpdatePreferencePolicy.CanDownload(policy,false,true,"1.0.1"),"busy/dirty block download");
            policy.SkippedUpdateVersion="1.0.1";Check(!UpdatePreferencePolicy.CanDownload(policy,false,false,"1.0.1") && !UpdatePreferencePolicy.CanRemind(policy,DateTime.UtcNow,"1.0.1"),"skip respected");
            policy.SkippedUpdateVersion="";policy.NextUpdateReminderUtc=DateTime.UtcNow.AddHours(1);Check(!UpdatePreferencePolicy.CanRemind(policy,DateTime.UtcNow,"1.0.1"),"reminder deferred");
            policy.NextUpdateReminderUtc=DateTime.MinValue;Check(UpdatePreferencePolicy.CanRemind(policy,DateTime.UtcNow,"1.0.1"),"reminder due");policy.BackgroundUpdateDownload=false;Check(!UpdatePreferencePolicy.CanDownload(policy,false,false,"1.0.1"),"default/manual download");
            Console.WriteLine("PASS background-download / busy / skip / reminder policy (no network/install)");

            var vm=new MainViewModel(new Picker(),new PythonWorkerHost(),startWorker:false);vm.NavigateTabCommand.Execute("settings");
            var window=new MainWindow(vm,new Presentation());window.Show();window.UpdateLayout();
            vm.Language="en";vm.Theme="dark";vm.BackgroundStrength=60;window.Dispatcher.Invoke(()=>{},DispatcherPriority.ApplicationIdle);
            CaptureReview(window,"settings-dark-top");
            Check(AppSettingsStore.Load().Language=="en" && AppSettingsStore.Load().Theme=="dark" && vm.Theme=="dark","view-model settings persisted");
            Check(Find<TextBlock>(window,t=>t.Text=="Display language") is not null && Find<TextBlock>(window,t=>t.Text=="Appearance") is not null,"real Settings rows localized");
            vm.NavigateTabCommand.Execute("extract");window.Dispatcher.Invoke(()=>{},DispatcherPriority.ApplicationIdle);
            vm.NavigateTabCommand.Execute("settings");window.Dispatcher.Invoke(()=>{},DispatcherPriority.ApplicationIdle);
            Check(Find<TextBlock>(window,t=>t.Text=="Display language") is not null && vm.Theme=="dark","deferred Settings content retains language and selection");
            var settingsScroll=(ScrollViewer)window.FindName("SettingsScrollViewer");
            window.UpdateLayout();settingsScroll.ScrollToEnd();window.Dispatcher.Invoke(()=>{},DispatcherPriority.ApplicationIdle);
            Check(settingsScroll.ScrollableHeight>0 && settingsScroll.VerticalOffset>0,"Settings lower options remain scroll-accessible");
            CaptureReview(window,"settings-dark-lower");
            vm.RememberWindow=false;vm.StartMinimized=false;vm.AutoCheckUpdates=false;vm.NotifyUpdates=false;vm.BackgroundUpdateDownload=false;
            window.UpdateLayout();Pump(100);AssertSettingsToggleTrack(window,false);CaptureReview(window,"settings-dark-toggles-off");
            vm.RememberWindow=true;vm.StartMinimized=true;vm.AutoCheckUpdates=true;vm.NotifyUpdates=true;vm.BackgroundUpdateDownload=true;
            window.UpdateLayout();Pump(100);AssertSettingsToggleTrack(window,true);CaptureReview(window,"settings-dark-toggles-on");
            settingsScroll.ScrollToTop();vm.Theme="light";window.UpdateLayout();Pump(100);CaptureReview(window,"settings-light-top");
            settingsScroll.ScrollToEnd();window.UpdateLayout();Pump(100);
            vm.RememberWindow=false;vm.StartMinimized=false;vm.AutoCheckUpdates=false;vm.NotifyUpdates=false;vm.BackgroundUpdateDownload=false;
            window.UpdateLayout();Pump(100);AssertSettingsToggleTrack(window,false);CaptureReview(window,"settings-light-toggles-off");
            vm.RememberWindow=true;vm.StartMinimized=true;vm.AutoCheckUpdates=true;vm.NotifyUpdates=true;vm.BackgroundUpdateDownload=true;
            window.UpdateLayout();Pump(100);AssertSettingsToggleTrack(window,true);CaptureReview(window,"settings-light-toggles-on");
            var tabs=Find<TabControl>(window,_=>true)!;tabs.SelectedIndex=2;
            window.WindowState=WindowState.Normal;window.Width=1050;window.UpdateLayout();Pump(100);
            var about=(Grid)window.FindName("AboutDestinationsGrid");var narrow=about.ActualWidth;
            window.Width=1450;window.UpdateLayout();Pump(100);
            Check(about.ActualWidth>narrow+250,"About cards expand with the window instead of a fixed max width");
            Console.WriteLine($"PASS About responsive card grid {narrow:0.0} -> {about.ActualWidth:0.0}");
            vm.Language="vi";vm.Theme="light";window.Close();
            Console.WriteLine("PASS real MainWindow / preference bindings / language-theme integration");

            var trayWindow=new Window { Width=300,Height=120,Title="VNText preference tray test" };trayWindow.Show();
            using(var tray=new AppTray(trayWindow,()=>{})) { Check(tray.Hide() && !trayWindow.IsVisible,"tray hide");tray.Restore();Check(trayWindow.IsVisible,"tray restore"); }
            trayWindow.Close();Console.WriteLine("PASS native tray icon / hide / restore / disposal");
            UiText.SetLanguage("vi");UiAppearance.Apply("light",100);Console.WriteLine("Preferences tests: PASS (8 groups)");return 0;
        }
        finally { app.Shutdown(); }
    }
    private static Color RenderBrushPixel(Brush brush,int x,int y)
    {
        var visual=new DrawingVisual();using(var context=visual.RenderOpen())context.DrawRectangle(brush,null,new Rect(0,0,256,256));
        var bitmap=new System.Windows.Media.Imaging.RenderTargetBitmap(256,256,96,96,PixelFormats.Pbgra32);bitmap.Render(visual);
        var pixel=new byte[4];bitmap.CopyPixels(new Int32Rect(x,y,1,1),pixel,4,0);
        return Color.FromArgb(pixel[3],pixel[2],pixel[1],pixel[0]);
    }
    private static void CaptureReview(Window window,string name)
    {
        var directory=Environment.GetEnvironmentVariable("VNTEXT_UI_REVIEW_OUT");if(string.IsNullOrWhiteSpace(directory))return;
        Directory.CreateDirectory(directory);window.UpdateLayout();
        var width=Math.Max(1,(int)Math.Ceiling(window.ActualWidth));var height=Math.Max(1,(int)Math.Ceiling(window.ActualHeight));
        var bitmap=new RenderTargetBitmap(width,height,96,96,PixelFormats.Pbgra32);bitmap.Render(window);
        using var stream=File.Create(Path.Combine(directory,name+".png"));var encoder=new PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(bitmap));encoder.Save(stream);
        Console.WriteLine($"UI review render {name}: window={window.ActualWidth:0.0}x{window.ActualHeight:0.0}, dpi={VisualTreeHelper.GetDpi(window).PixelsPerInchX:0.0}x{VisualTreeHelper.GetDpi(window).PixelsPerInchY:0.0}");
    }
    private static void AssertSettingsToggleTrack(Window window,bool isOn)
    {
        var toggle=Find<CheckBox>(window,c=>System.Windows.Automation.AutomationProperties.GetName(c)=="Tự động tải cập nhật nền");
        Check(toggle is not null && toggle.IsChecked==isOn,"Settings toggle state bound to view model");
        toggle!.ApplyTemplate();
        var track=toggle.Template.FindName("Track",toggle) as Border;
        var actual=track?.Background as SolidColorBrush;
        Check(actual is not null,"Settings toggle track template instantiated");
        var key=isOn?"BlueBrush":"SwitchOffBrush";
        Check(window.TryFindResource(key) is SolidColorBrush expected && actual!.Color==expected.Color,
            $"Settings {(isOn?"on":"off")} toggle track uses {key} resource");
    }
    private static void Pump(int milliseconds)
    {
        var frame=new DispatcherFrame();var timer=new DispatcherTimer { Interval=TimeSpan.FromMilliseconds(milliseconds) };
        timer.Tick+=(_,_)=>{timer.Stop();frame.Continue=false;};timer.Start();Dispatcher.PushFrame(frame);
    }
    private static T? Find<T>(DependencyObject root,Func<T,bool> test) where T:DependencyObject
    { if(root is T item && test(item))return item;for(var i=0;i<VisualTreeHelper.GetChildrenCount(root);i++){var found=Find(VisualTreeHelper.GetChild(root,i),test);if(found is not null)return found;}return null; }
    private sealed class Picker:IPathPickerService
    { public string? PickInputPath()=>null;public string? PickOutputFolder()=>null;public string? PickTranslationCsvFile(string? title=null)=>null;public string? PickRenpySdkFolder()=>null;public string? PickImageFile(bool review=false)=>null;public bool OpenPath(string path)=>false; }
    private sealed class Presentation:IUpdatePresentation
    {
        public string CurrentVersion=>"0.1.5";public string Version=>"";public string ReleaseDate=>"";public string Notes=>"";public string Status=>"";
        public bool Available=>false;public bool Downloading=>false;public bool Ready=>false;public long Received=>0;public long Total=>0;public bool CanStart=>false;public bool IsTestFixture=>true;
        public event PropertyChangedEventHandler? PropertyChanged { add{} remove{} } public event Action? OfferRequested { add{} remove{} }
        public Task CheckAsync()=>Task.CompletedTask;public Task DownloadAsync()=>Task.CompletedTask;public void Cancel(){}public void Defer(bool skip){}public void Restart(){}public void Dispose(){}
    }
}
