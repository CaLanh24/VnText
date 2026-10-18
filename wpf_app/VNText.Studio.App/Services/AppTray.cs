using System.IO;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;

namespace VNText.Studio.App.Services;

// Dedicated app tray icon. No global hooks, startup registry or host settings.
internal sealed class AppTray : IDisposable
{
    private readonly Window _window;
    private readonly Action _exit;
    private readonly HwndSource _source;
    private NotifyData _data;
    private IntPtr _icon;
    private bool _ownsIcon;
    private bool _disposed;
    private bool _hidden;
    private readonly uint _taskbarCreated = RegisterWindowMessage("TaskbarCreated");
    private WindowState _visibleState = WindowState.Maximized;
    private const int Callback = 0x8000 + 77;
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NotifyData
    {
        public uint Size; public IntPtr Window; public uint Id; public uint Flags; public uint Message; public IntPtr Icon;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=128)] public string Tip;
        public uint State, StateMask;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=256)] public string Info;
        public uint Timeout;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst=64)] public string InfoTitle;
        public uint InfoFlags; public Guid Guid; public IntPtr BalloonIcon;
    }
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] private static extern uint RegisterWindowMessage(string message);
    [DllImport("shell32.dll", CharSet=CharSet.Unicode)] private static extern bool Shell_NotifyIcon(uint message, ref NotifyData data);
    [DllImport("user32.dll")] private static extern IntPtr CreateIconFromResourceEx(byte[] bytes, uint size, bool icon, uint version, int width, int height, uint flags);
    [DllImport("user32.dll")] private static extern bool DestroyIcon(IntPtr icon);
    [DllImport("user32.dll")] private static extern IntPtr LoadIcon(IntPtr instance, IntPtr name);
    [DllImport("user32.dll")] private static extern bool SetForegroundWindow(IntPtr window);
    public AppTray(Window window, Action exit)
    {
        _window=window; _exit=exit;
        var handle=new WindowInteropHelper(window).EnsureHandle();
        _source=HwndSource.FromHwnd(handle)!; _source.AddHook(Hook);
        try
        {
            var resource=Application.GetResourceStream(new Uri("pack://application:,,,/VNText.Studio.App;component/Assets/vntext_studio.ico"));
            using var stream=resource!.Stream; using var memory=new MemoryStream(); stream.CopyTo(memory);
            var bytes=memory.ToArray(); var count=BitConverter.ToUInt16(bytes,4); var index=0;
            for(var i=0;i<count;i++) if(bytes[6+i*16]==32) { index=i; break; }
            var size=BitConverter.ToUInt32(bytes,6+index*16+8); var offset=BitConverter.ToUInt32(bytes,6+index*16+12);
            _icon=CreateIconFromResourceEx(bytes.AsSpan((int)offset,(int)size).ToArray(),size,true,0x30000,32,32,0); _ownsIcon=_icon!=IntPtr.Zero;
        } catch { }
        if(_icon==IntPtr.Zero) _icon=LoadIcon(IntPtr.Zero,(IntPtr)32512);
        _data=new NotifyData { Size=(uint)Marshal.SizeOf<NotifyData>(), Window=handle, Id=1, Flags=7, Message=Callback, Icon=_icon, Tip="VNText Studio",Info="",InfoTitle="" };
    }
    public bool Hide()
    {
        if(!Shell_NotifyIcon(0,ref _data)) return false;
        if(_window.WindowState!=WindowState.Minimized) _visibleState=_window.WindowState;
        _hidden=true; _window.Hide(); return true;
    }
    public void Restore()
    {
        _hidden=false; _window.Show(); _window.WindowState=_visibleState; _window.Activate(); Shell_NotifyIcon(2,ref _data);
    }
    private IntPtr Hook(IntPtr hwnd,int message,IntPtr wParam,IntPtr lParam,ref bool handled)
    {
        if ((uint)message == _taskbarCreated && _hidden) { if (!Shell_NotifyIcon(0, ref _data)) Restore(); return IntPtr.Zero; }
        if(message!=Callback) return IntPtr.Zero;
        var mouse=(int)lParam;
        if(mouse==0x203) Restore();
        if(mouse==0x205 || mouse==0x7B)
        {
            SetForegroundWindow(hwnd);
            var menu=new ContextMenu(); var open=new MenuItem { Header=UiText.Translate("Mở VNText Studio") }; open.Click+=(_,_)=>Restore();
            var exit=new MenuItem { Header=UiText.Translate("Thoát") }; exit.Click+=(_,_)=>{ Restore(); _exit(); };
            menu.Items.Add(open);menu.Items.Add(exit);menu.IsOpen=true;
        }
        handled=true;return IntPtr.Zero;
    }
    public void Dispose()
    {
        if(_disposed)return;_disposed=true;Shell_NotifyIcon(2,ref _data);_source.RemoveHook(Hook);if(_ownsIcon)DestroyIcon(_icon);
    }
}
