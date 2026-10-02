using System.Windows;
using System.Windows.Threading;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

internal sealed record CompletionNotification(string Title, string Message, string Kind);

public sealed partial class MainViewModel
{
    private string _toastMessage = "";
    private bool _toastVisible;
    private string _toastKind = "success";
    private DispatcherTimer? _toastTimer;

    private string? _completionHandledKey;

    internal event EventHandler<CompletionNotification>? CompletionRequested;

    // Console/UI probes must observe the real workflow without a modal
    // MessageBox blocking the dispatcher before state can be collected.
    internal bool SuppressCompletionNotifications { get; set; }

    public string ToastMessage
    {
        get => _toastMessage;
        private set => Set(ref _toastMessage, value);
    }

    public bool ToastVisible
    {
        get => _toastVisible;
        private set => Set(ref _toastVisible, value);
    }

    /// <summary>success | warning | error | info</summary>
    public string ToastKind
    {
        get => _toastKind;
        private set => Set(ref _toastKind, value);
    }

    private void ShowToast(string message, string kind = "success", bool playSound = true)
    {
        if (string.IsNullOrWhiteSpace(message))
            return;

        void Apply()
        {
            _toastTimer?.Stop();
            ToastMessage = message.Trim();
            ToastKind = kind;
            ToastVisible = true;

            if (playSound)
            {
                switch (kind)
                {
                    case "error":
                        UserFeedback.PlayError();
                        break;
                    case "warning":
                        UserFeedback.PlayWarning();
                        break;
                    default:
                        UserFeedback.PlaySuccess();
                        break;
                }
            }

            _toastTimer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(4.5) };
            _toastTimer.Tick += (_, _) =>
            {
                ToastVisible = false;
                _toastTimer?.Stop();
            };
            _toastTimer.Start();
        }

        var dispatcher = Application.Current?.Dispatcher;
        if (dispatcher is null || dispatcher.CheckAccess())
            Apply();
        else
            dispatcher.BeginInvoke(Apply);
    }

    private void RequestCompletion(string title, string message, string kind)
    {
        if (SuppressCompletionNotifications || string.IsNullOrWhiteSpace(message))
            return;

        CompletionRequested?.Invoke(
            this,
            new CompletionNotification(title, message.Trim(), kind));
    }

    private bool TryClaimCompletion(WorkerEvent evt)
    {
        if (!string.IsNullOrWhiteSpace(evt.Id)
            && !string.IsNullOrWhiteSpace(_activeTaskId)
            && !string.Equals(evt.Id, _activeTaskId, StringComparison.Ordinal))
            return false;

        var key = !string.IsNullOrWhiteSpace(evt.Id)
            ? $"worker:{evt.Id}"
            : !string.IsNullOrWhiteSpace(_activeTaskId)
                ? $"active:{_activeTaskId}"
                : $"synthetic:{evt.Ok}:{evt.Complete}:{evt.Pending}:{evt.ReviewOnly}:{evt.Translated}:{evt.Summary}:{evt.Error}";

        if (string.Equals(_completionHandledKey, key, StringComparison.Ordinal))
            return false;

        _completionHandledKey = key;
        return true;
    }

    internal void TestShowToast(string message, string kind = "success", bool playSound = false) =>
        ShowToast(message, kind, playSound);
}
