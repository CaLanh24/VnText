using System.Runtime.InteropServices;
using System.Text;
using System.Windows;
using System.Windows.Interop;
using System.Windows.Threading;

namespace VNText.Studio.App.Services;

/// <summary>
/// Keeps Process.CloseMainWindow deterministic on Windows.  WPF can create
/// visible, ownerless Text Services input-indicator windows on the UI thread;
/// .NET may otherwise select one of those handles instead of the real Window.
/// </summary>
internal static class MainWindowHandleNormalizer
{
    private const int GwlpHwndParent = -8;
    private const string InputIndicatorOverlay = "UAC_InputIndicatorOverlayWnd";
    private const string InputIndicator = "UAC Input Indicator";

    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassName(IntPtr hWnd, StringBuilder className, int maxCount);

    [DllImport("user32.dll")]
    private static extern IntPtr SetWindowLongPtr(IntPtr hWnd, int index, IntPtr value);

    public static void AttachAuxiliaryInputWindows(Window mainWindow)
    {
        var mainHandle = new WindowInteropHelper(mainWindow).Handle;
        if (mainHandle == IntPtr.Zero)
            return;

        var processId = (uint)Environment.ProcessId;
        EnumWindows((hWnd, _) =>
        {
            if (hWnd == mainHandle || GetWindowThreadProcessId(hWnd, out var ownerPid) == 0 || ownerPid != processId)
                return true;

            var className = new StringBuilder(128);
            GetClassName(hWnd, className, className.Capacity);
            if (className.ToString() is InputIndicatorOverlay or InputIndicator)
                SetWindowLongPtr(hWnd, GwlpHwndParent, mainHandle);
            return true;
        }, IntPtr.Zero);
    }

    public static void Schedule(Window mainWindow)
    {
        var timer = new DispatcherTimer(DispatcherPriority.Background, mainWindow.Dispatcher)
        {
            Interval = TimeSpan.FromSeconds(1),
        };
        timer.Tick += (_, _) =>
        {
            timer.Stop();
            AttachAuxiliaryInputWindows(mainWindow);
        };
        timer.Start();
    }
}
