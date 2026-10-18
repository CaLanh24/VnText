using System.ComponentModel;
using System.Windows.Input;
using VNText.Studio.App.ViewModels;
using VNText.Studio.App.Services;

namespace VNText.Studio.App;

// Presentation-only contract. The production adapter delegates to the existing updater.
public interface IUpdatePresentation : INotifyPropertyChanged, IDisposable
{
    string CurrentVersion { get; }
    string Version { get; }
    string Notes { get; }
    string Status { get; }
    bool Available { get; }
    bool Downloading { get; }
    bool Ready { get; }
    long Received { get; }
    long Total { get; }
    bool CanStart { get; }
    bool IsTestFixture { get; }
    event Action? OfferRequested;
    Task CheckAsync();
    Task DownloadAsync();
    void Cancel();
    void Defer(bool skip);
    void Restart();
}

internal sealed class ViewModelUpdatePresentation : IUpdatePresentation
{
    private readonly MainViewModel _vm;
    public ViewModelUpdatePresentation(MainViewModel vm)
    {
        _vm = vm; vm.PropertyChanged += Changed; vm.UpdatePopupRequested += Offer;
    }
    public string CurrentVersion => _vm.CurrentVersionDisplay;
    public string Version => _vm.OfferedVersion;
    public string Notes => _vm.UpdateNotes;
    public string Status => _vm.GitHubUpdateStatus;
    public bool Available => _vm.GitHubUpdateState == GitHubUpdateState.OfferAvailable || Ready;
    public bool Downloading => _vm.DownloadingUpdate;
    public bool Ready => _vm.GitHubApplyEnabled;
    public long Received => _vm.DownloadReceived;
    public long Total => _vm.DownloadTotal;
    public bool CanStart => !_vm.Busy && !_vm.CsvEditorDirty && !_vm.GitHubUpdateChecking && !Downloading;
    public bool IsTestFixture => false;
    public event PropertyChangedEventHandler? PropertyChanged;
    public event Action? OfferRequested;
    private void Changed(object? sender, PropertyChangedEventArgs e) => PropertyChanged?.Invoke(this, new(""));
    private void Offer() => OfferRequested?.Invoke();
    public async Task CheckAsync() { _vm.RecheckUpdateCommand.Execute(null); await _vm.GitHubUpdateCheckTask; }
    public Task DownloadAsync() => _vm.DownloadOfferedUpdateAsync();
    public void Cancel() => _vm.CancelUpdateDownload();
    public void Defer(bool skip) => _vm.DeferUpdate(skip);
    public void Restart() => _vm.RestartForUpdate();
    public void Dispose() { _vm.PropertyChanged -= Changed; _vm.UpdatePopupRequested -= Offer; }
}
