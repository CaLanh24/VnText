using System.IO;
﻿using System.Windows;
using System.Windows.Controls;
using System.Windows.Threading;
using VNText.Studio.App;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

internal static partial class Program
{
    /// <summary>Real MainWindow at the reviewed small presentation: 1565x1080 physical at OS 150% = 1043x720 DIP, and a 600 DIP window stands for UI scale 120% (effective height 720/1.2).</summary>
    private static int RunCsvLayoutFixture()
    {
        var exitCode = 1;
        var thread = new Thread(() =>
        {
            try
            {
                var root = Environment.GetEnvironmentVariable("VNTEXT_LOCALAPPDATA") ?? throw new InvalidOperationException("isolated root required");
                Require(Path.GetFullPath(root).Contains(Path.DirectorySeparatorChar + "TEST_RUN" + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase), "the fixture needs the TEST_RUN isolation");
                var app = new VNText.Studio.App.App();
                app.InitializeComponent();
                app.ShutdownMode = ShutdownMode.OnExplicitShutdown;
                var worker = new PythonWorkerHost();
                var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false);
                vm.NavigateTabCommand.Execute("editcsv");
                var window = new MainWindow(vm, new FixtureUpdatePresentation());
                try
                {
                    window.WindowState = WindowState.Normal;
                    window.Width = 1043;
                    window.Height = 600;
                    window.Show();
                    window.UpdateLayout();
                    PumpFixture(250);
                    FrameworkElement Named(string name) => (FrameworkElement)(window.FindName(name) ?? throw new InvalidOperationException(name));
                    var grid = Named("CsvEditorGrid");

                    Require(Named("CsvEmptyState").IsVisible && Named("CsvEmptyChooseButton").IsVisible, "empty CSV shows its instruction and the Chọn CSV action");
                    Require(!Named("CsvBulkReplacePanel").IsVisible && !Named("CsvBulkSummary").IsVisible && !grid.IsVisible && !Named("CsvChooseHeaderButton").IsVisible,
                        "no CSV: bulk tools, table and the duplicate header action stay hidden");
                    var emptyHeight = Named("CsvEmptyState").ActualHeight;

                    vm.TestSetCsvEditorPath(Path.Combine(Path.GetTempPath(), "translation.csv"));
                    window.UpdateLayout();
                    PumpFixture(150);
                    Require(!vm.CsvBulkExpanded && Named("CsvBulkSummary").IsVisible && !Named("CsvBulkReplacePanel").IsVisible, "low height starts with the tools collapsed to ONE visible summary row");
                    Require(Named("CsvBulkOpenButton").IsVisible && Named("CsvBulkOpenButton").ActualHeight >= 29.5, "the collapsed summary has an explicit open button");
                    Require(grid.IsVisible && !Named("CsvEmptyState").IsVisible, "a loaded CSV shows the table, not the empty state");
                    Require(grid.ActualHeight >= 150, "the table keeps a finite viewport of at least three rows plus the header (got " + grid.ActualHeight + ")");
                    Require(Math.Abs(grid.ActualHeight - emptyHeight) <= Math.Max(60, emptyHeight * 0.5), "the table viewport does not jump against the empty state");

                    vm.CsvBulkFind = "cửa";
                    vm.CsvBulkReplace = "cổng";
                    vm.ToggleCsvBulkCommand.Execute(null);
                    window.UpdateLayout();
                    PumpFixture(100);
                    Require(vm.CsvBulkExpanded && Named("CsvBulkReplacePanel").IsVisible && !Named("CsvBulkSummary").IsVisible, "the open action expands the tools");
                    Require(Named("CsvBulkScopeComboBox").Height == 36, "bulk scope select is the 36 DIP standard size");
                    vm.ToggleCsvBulkCommand.Execute(null);
                    window.UpdateLayout();
                    PumpFixture(100);
                    Require(!vm.CsvBulkExpanded && vm.CsvBulkFind == "cửa" && vm.CsvBulkReplace == "cổng", "collapsing keeps the typed find/replace text");
                    vm.CsvFilterMode = "untranslated";
                    vm.CsvEditorSearch = "x";
                    PumpFixture(50);
                    Require(!vm.CsvBulkExpanded && vm.CsvBulkFind == "cửa", "filtering and searching neither expand nor reset the tools");
                    Console.WriteLine("WPF CSV low-height layout fixture: PASS (empty state, collapsed bulk tools, table viewport, 36 DIP selects)");
                    exitCode = 0;
                }
                finally { window.Close(); UiText.SetLanguage("vi"); UiAppearance.Apply("light", 100); app.Shutdown(); }
            }
            catch (Exception ex) { Console.Error.WriteLine(ex); exitCode = 1; }
        });
        thread.SetApartmentState(ApartmentState.STA);
        thread.Start();
        thread.Join();
        return exitCode;
    }

    private static void PumpFixture(int milliseconds)
    {
        var frame = new DispatcherFrame();
        var timer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(milliseconds) };
        timer.Tick += (_, _) => { timer.Stop(); frame.Continue = false; };
        timer.Start();
        Dispatcher.PushFrame(frame);
    }
    private sealed class FixtureUpdatePresentation : IUpdatePresentation
    {
        public string CurrentVersion => "0.1.14"; public string Version => ""; public string ReleaseDate => ""; public string Notes => ""; public string Status => "";
        public bool Available => false; public bool Downloading => false; public bool Ready => false; public long Received => 0; public long Total => 0; public bool CanStart => false; public bool IsTestFixture => true;
        public event System.ComponentModel.PropertyChangedEventHandler? PropertyChanged { add { } remove { } }
        public event Action? OfferRequested { add { } remove { } }
        public Task CheckAsync() => Task.CompletedTask; public Task DownloadAsync() => Task.CompletedTask; public void Cancel() { }
        public void Defer(bool skip) { } public void Restart() { } public void Dispose() { }
    }
}
