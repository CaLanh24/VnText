using System.Drawing;
using System.Drawing.Drawing2D;
using System.Reflection;
using System.Windows.Forms;

namespace VNText.PatchInstaller;

internal static class InstallerTheme
{
    internal static readonly bool Dark = IsDark();
    private static bool IsDark()
    {
        var mode = Environment.GetEnvironmentVariable("VNTEXT_INSTALLER_THEME");
        if (mode is "dark" or "light") return mode == "dark";
        try { using var key = Microsoft.Win32.Registry.CurrentUser.OpenSubKey(@"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"); return key?.GetValue("AppsUseLightTheme") is int value && value == 0; }
        catch { return false; }
    }
    internal static Color C(string light, string dark) => ColorTranslator.FromHtml(Dark ? dark : light);
}

/// <summary>A filled, bordered rounded rectangle (card, status banner, text field frame) painted with anti-aliasing.</summary>
internal class RoundedPanel : Panel
{
    public int Radius { get; set; } = 14;
    public Color Fill { get; set; } = Color.White;
    public Color Border { get; set; } = Color.FromArgb(0xE5, 0xE7, 0xEB);

    public RoundedPanel() { DoubleBuffered = true; ResizeRedraw = true; }

    internal static GraphicsPath Path(Rectangle bounds, int radius)
    {
        var d = Math.Max(1, radius * 2);
        var path = new GraphicsPath();
        path.AddArc(bounds.X, bounds.Y, d, d, 180, 90);
        path.AddArc(bounds.Right - d, bounds.Y, d, d, 270, 90);
        path.AddArc(bounds.Right - d, bounds.Bottom - d, d, d, 0, 90);
        path.AddArc(bounds.X, bounds.Bottom - d, d, d, 90, 90);
        path.CloseFigure();
        return path;
    }

    protected override void OnPaintBackground(PaintEventArgs e) => e.Graphics.Clear(Parent?.BackColor ?? SystemColors.Control);

    protected override void OnPaint(PaintEventArgs e)
    {
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        using var path = Path(new Rectangle(0, 0, Width - 1, Height - 1), Radius);
        using var brush = new SolidBrush(Fill);
        using var pen = new Pen(Border);
        e.Graphics.FillPath(brush, path);
        e.Graphics.DrawPath(pen, path);
        base.OnPaint(e);
    }
}

/// <summary>Rounded button in the app's style: primary (blue) or outline, with hover, pressed, focus and disabled states.</summary>
internal sealed class RoundedButton : Button
{
    private static readonly Color Blue = Color.FromArgb(0x28, 0x68, 0xE8), BlueHover = Color.FromArgb(0x1F, 0x55, 0xC8), BlueSoft = Color.FromArgb(0xE9, 0xF1, 0xFF),
        Line = Color.FromArgb(0xD7, 0xDD, 0xE8), Ink = Color.FromArgb(0x11, 0x18, 0x27);
    private static readonly Color Muted = InstallerTheme.C("#8A96A8", "#8392A8"), Disabled = InstallerTheme.C("#F1F3F7", "#273245");
    private bool _hover, _down;
    public bool Primary { get; set; }

    public RoundedButton(string text, bool primary = false)
    {
        Text = text; Primary = primary; FlatStyle = FlatStyle.Flat; DoubleBuffered = true; Cursor = Cursors.Hand;
        FlatAppearance.BorderSize = 0; Margin = new Padding(0, 0, 10, 0); Font = new Font("Segoe UI Semibold", 10F);
        SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint | ControlStyles.OptimizedDoubleBuffer, true);
        AutoSize = false; Height = 40;
        Width = Math.Max(112, TextRenderer.MeasureText(text, Font).Width + 40);
    }

    protected override void OnMouseEnter(EventArgs e) { _hover = true; Invalidate(); base.OnMouseEnter(e); }
    protected override void OnMouseLeave(EventArgs e) { _hover = false; _down = false; Invalidate(); base.OnMouseLeave(e); }
    protected override void OnMouseDown(MouseEventArgs e) { _down = true; Invalidate(); base.OnMouseDown(e); }
    protected override void OnMouseUp(MouseEventArgs e) { _down = false; Invalidate(); base.OnMouseUp(e); }
    protected override void OnGotFocus(EventArgs e) { Invalidate(); base.OnGotFocus(e); }
    protected override void OnLostFocus(EventArgs e) { Invalidate(); base.OnLostFocus(e); }
    protected override void OnEnabledChanged(EventArgs e) { Invalidate(); base.OnEnabledChanged(e); }
    protected override void OnTextChanged(EventArgs e) { Width = Math.Max(112, TextRenderer.MeasureText(Text, Font).Width + 40); base.OnTextChanged(e); }

    protected override void OnPaint(PaintEventArgs e)
    {
        var g = e.Graphics; g.SmoothingMode = SmoothingMode.AntiAlias;
        g.Clear(Parent?.BackColor ?? SystemColors.Control);
        Color fill, border, text;
        if (!Enabled) { fill = Disabled; border = Disabled; text = Muted; }
        else if (Primary) { fill = _down || _hover ? BlueHover : Blue; border = fill; text = Color.White; }
        else { fill = _down || _hover ? InstallerTheme.C("#EEF2F7", "#334155") : InstallerTheme.C("#FFFFFF", "#1E293B"); border = _hover ? InstallerTheme.C("#D3D7DE", "#4B5869") : InstallerTheme.C("#E2E3E5", "#394352"); text = InstallerTheme.C("#475569", "#94A3B8"); }
        var bounds = new Rectangle(0, 0, Width - 1, Height - 1);
        using (var path = RoundedPanel.Path(bounds, 10))
        {
            using var brush = new SolidBrush(fill); g.FillPath(brush, path);
            using var pen = new Pen(border); g.DrawPath(pen, path);
        }
        if (Focused && ShowFocusCues)                                        // visible keyboard focus: an inner ring in the accent colour
        {
            using var ring = RoundedPanel.Path(new Rectangle(3, 3, Width - 7, Height - 7), 8);
            using var pen = new Pen(Primary ? Color.White : Blue, 2);
            g.DrawPath(pen, ring);
        }
        TextRenderer.DrawText(g, Text, Font, ClientRectangle, text, TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine);
    }
}

/// <summary>The app brand artwork (blue-to-cyan feather tile) clipped to the app's rounded-square shape.</summary>
internal sealed class RoundedPicture : Control
{
    public Image? Image { get; set; }
    public RoundedPicture() { DoubleBuffered = true; }
    protected override void OnPaint(PaintEventArgs e)
    {
        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias; e.Graphics.InterpolationMode = InterpolationMode.HighQualityBicubic;
        if (Image is null) return;
        using var path = RoundedPanel.Path(new Rectangle(0, 0, Width - 1, Height - 1), (int)(Width * 0.29));
        e.Graphics.SetClip(path);
        e.Graphics.DrawImage(Image, new Rectangle(0, 0, Width, Height));
    }
}

internal sealed class InstallerForm : Form
{
    private readonly record struct Tone(Color Fill, Color Border, Color Text);

    // Tokens taken from the app (Themes/DesignTokens.xaml): canvas, surface, ink, muted, line, blue, plus the About banner green.
    private static readonly Color Canvas = InstallerTheme.C("#F2F6FC", "#172235"), Surface = InstallerTheme.C("#FFFFFF", "#202B3C"), Ink = InstallerTheme.C("#111827", "#EDF1F7"),
        Muted = InstallerTheme.C("#4B5B71", "#B7C2D3"), Line = InstallerTheme.C("#E5E7EB", "#3B4B63"), Blue = Color.FromArgb(0x28, 0x68, 0xE8);
    private static readonly Tone Good = new(Color.FromArgb(0xD8, 0xED, 0xE1), Color.FromArgb(0xA1, 0xE2, 0xBA), Color.FromArgb(0x15, 0x80, 0x3D));
    private static readonly Tone Warn = new(Color.FromArgb(0xFD, 0xF3, 0xDC), Color.FromArgb(0xF0, 0xCF, 0x8A), Color.FromArgb(0x8A, 0x50, 0x00));
    private static readonly Tone Bad = new(Color.FromArgb(0xFB, 0xE6, 0xE6), Color.FromArgb(0xEE, 0xB0, 0xB0), Color.FromArgb(0xA3, 0x2B, 0x2B));
    private static readonly Tone Info = new(Color.FromArgb(0xE9, 0xF1, 0xFF), Color.FromArgb(0xBF, 0xD6, 0xFB), Color.FromArgb(0x1F, 0x4F, 0xB8));

    private readonly InstallerService _service;
    private readonly TextBox _gamePath = new() { BorderStyle = BorderStyle.None, Dock = DockStyle.Fill, BackColor = Color.White };
    private readonly RoundedPanel _card = new() { Radius = 16, Padding = new Padding(24, 20, 24, 18) };
    private readonly RoundedPanel _statusBox = new() { Radius = 10, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(16, 12, 16, 12), Margin = new Padding(0, 14, 0, 10), MinimumSize = new Size(0, 52) };
    private readonly Label _status = new() { AutoSize = true, Location = new Point(16, 12) };
    private readonly Label _description = new() { AutoSize = true, ForeColor = Muted, Margin = new Padding(0, 4, 0, 4) };
    private readonly RoundedButton _install = new("Cài đặt", true) { Enabled = false };
    private readonly RoundedButton _uninstall = new("Gỡ cài đặt") { Enabled = false };
    private readonly RoundedButton _restoreClean = new("Về bản gốc sạch") { Enabled = false };
    private readonly RoundedButton _confirm = new("Xác nhận gỡ", true) { Visible = false };
    private readonly RoundedButton _cancelConfirm = new("Giữ patch") { Visible = false };
    private readonly RoundedButton _browse = new("Chọn game…") { Margin = new Padding(10, 0, 0, 0) };
    private readonly ProgressBar _busy = new() { Height = 4, Style = ProgressBarStyle.Marquee, MarqueeAnimationSpeed = 30, Visible = false, Dock = DockStyle.Top };
    private bool _working;
    private bool _confirmingInstall;
    private bool _cleanRequested;

    private static readonly Color Field = InstallerTheme.C("#FFFFFF", "#162033"), FieldLine = InstallerTheme.C("#D7DDE8", "#3B4B63");
    private readonly Label _summary = new() { AutoSize = true, ForeColor = Muted, Margin = new Padding(0, 10, 0, 0) };
    private readonly TableLayoutPanel _flow = new() { Dock = DockStyle.Top, ColumnCount = 1, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, BackColor = Surface };
    private readonly Panel _frame = new() { Dock = DockStyle.Fill, Padding = new Padding(16), BackColor = Canvas };
    private bool _fitting;

    [System.Runtime.InteropServices.DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);

    public InstallerForm(string patchDir)
    {
        _service = new InstallerService(patchDir);
        Text = "VNText Studio — Cài đặt bản Việt hóa";
        Icon = Icon.ExtractAssociatedIcon(Environment.ProcessPath!);
        AutoScaleMode = AutoScaleMode.Dpi; AutoScaleDimensions = new SizeF(96F, 96F);
        Font = new Font("Segoe UI", 10F);
        BackColor = Canvas; ForeColor = Ink;
        _gamePath.BackColor = Field; _gamePath.ForeColor = Ink; _gamePath.AccessibleName = "Thư mục game";
        // A compact dialog sized to its content: fixed width, height follows the content (no resizable or maximisable empty surface).
        FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; StartPosition = FormStartPosition.CenterScreen; KeyPreview = true;
        ClientSize = new Size(720, 320);              // the in-app modal's width

        // Same content order as the in-app install modal: what will be installed, the font truth, the game folder, the status, then the footer.
        Image? logo = null;
        using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("VNText.Logo.png")) if (stream is not null) logo = Image.FromStream(stream);
        var mark = new RoundedPicture { Size = new Size(48, 48), Image = logo, Margin = new Padding(0, 0, 14, 0), BackColor = Surface };
        var title = new Label { Text = "Cài trong VNText", AutoSize = true, Font = new Font("Segoe UI Semibold", 18F), Margin = new Padding(0), Anchor = AnchorStyles.Left };
        var heading = new TableLayoutPanel { AutoSize = true, ColumnCount = 2, RowCount = 1, Dock = DockStyle.Top, BackColor = Surface };
        heading.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize)); heading.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        heading.Controls.Add(mark, 0, 0); heading.Controls.Add(title, 1, 0);
        _description.Text = "Chọn thư mục gốc của game (Unity hoặc Ren'Py). Chỉ các file bị sửa được sao lưu, để có thể gỡ patch về đúng bản gốc.";
        _summary.Text = SummaryText();

        var label = new Label { Text = "Thư mục game", AutoSize = true, ForeColor = Muted, Margin = new Padding(0, 14, 0, 6) };
        var field = new RoundedPanel { Radius = 10, Fill = Field, Border = FieldLine, Padding = new Padding(12, 11, 12, 8), Height = 42, Dock = DockStyle.Fill };
        field.Controls.Add(_gamePath);
        _gamePath.Enter += (_, _) => field.Border = Blue; _gamePath.Leave += (_, _) => field.Border = FieldLine;
        _gamePath.TextChanged += (_, _) => RefreshState();
        var pathRow = new TableLayoutPanel { AutoSize = true, ColumnCount = 2, RowCount = 1, Dock = DockStyle.Top, BackColor = Surface };
        pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        pathRow.Controls.Add(field, 0, 0); pathRow.Controls.Add(_browse, 1, 0);

        _statusBox.Controls.Add(_status);
        // Footer: right-aligned like the in-app modal (outline actions, then the primary action last/right-most), directly under the content.
        _install.Text = "Cài patch"; _uninstall.Text = "Gỡ và hoàn nguyên";
        var actions = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Top, FlowDirection = FlowDirection.RightToLeft, WrapContents = true, BackColor = Surface, Padding = new Padding(0, 6, 0, 0) };
        foreach (var button in new[] { _install, _confirm, _uninstall, _restoreClean, _cancelConfirm }) { button.Margin = new Padding(10, 0, 0, 0); actions.Controls.Add(button); }

        _browse.Click += (_, _) => BrowseGame();
        _install.Click += (_, _) => { _confirmingInstall = true; ShowConfirm(true); };
        _uninstall.Click += (_, _) => ShowConfirm(true);
        _restoreClean.Click += (_, _) => { _cleanRequested = true; ShowConfirm(true); };
        _cancelConfirm.Click += (_, _) => ShowConfirm(false);
        _confirm.Click += async (_, _) =>
        {
            var install = _confirmingInstall;
            var clean = _cleanRequested;
            var target = _gamePath.Text;
            ShowConfirm(false);
            await RunAsync(() =>
            {
                if (install)
                {
                    var state = _service.Install(target);
                    return (Good, $"Đã cài bản Việt hóa ({state.Files.Count} file). Bản gốc được sao lưu để có thể gỡ cài đặt." + Environment.NewLine + string.Join(Environment.NewLine, state.Notes ?? new List<string>())); }
                var result = _service.Uninstall(target, null, clean ? UninstallMode.CleanOriginal : UninstallMode.Previous);
                return (Good, (clean ? "Đã khôi phục bản gốc đầu tiên trước mọi patch VNText." : "Đã gỡ patch và khôi phục đúng các file mà lần cài này đã thay.") + Environment.NewLine + string.Join(Environment.NewLine, result.Notes));
            });
        };
        // Native keyboard: Tab follows reading order, Space/Enter act on the focused button, Escape backs out of a confirmation or closes an idle dialog.
        _gamePath.TabIndex = 0; _browse.TabIndex = 1; _restoreClean.TabIndex = 2; _uninstall.TabIndex = 3; _install.TabIndex = 4; _cancelConfirm.TabIndex = 5; _confirm.TabIndex = 6;
        foreach (var button in new[] { _browse, _restoreClean, _uninstall, _install, _cancelConfirm, _confirm }) button.TabStop = true;
        KeyDown += (_, e) =>
        {
            if (e.KeyCode != Keys.Escape || _working) return;
            e.Handled = true; e.SuppressKeyPress = true;
            if (_confirm.Visible) ShowConfirm(false); else Close();
        };

        // One column of content-sized rows: nothing stretches to fill spare height, so the card is exactly as tall as its content.
        _flow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        foreach (Control c in new Control[] { heading, _description, _summary, label, pathRow, _statusBox, _busy, actions })
        {
            c.Dock = DockStyle.Top; _flow.RowStyles.Add(new RowStyle(SizeType.AutoSize)); _flow.Controls.Add(c);
        }
        _card.Padding = new Padding(24, 20, 24, 18);
        _card.Controls.Add(_flow);
        _card.Dock = DockStyle.Fill; _card.Fill = Surface; _card.Border = Line;
        _frame.Controls.Add(_card);
        Controls.Add(_frame);

        _card.SizeChanged += (_, _) => FitToContent();
        Shown += (_, _) => { FitToContent(); RefreshState(); _gamePath.Focus(); };
        HandleCreated += (_, _) => { var on = InstallerTheme.Dark ? 1 : 0; DwmSetWindowAttribute(Handle, 20, ref on, sizeof(int)); };
    }

    /// <summary>What the install will do, in the same words as the in-app modal: file count, backup, and what the patch says about fonts.</summary>
    private string SummaryText()
    {
        try
        {
            var manifest = _service.LoadManifest();
            var lines = new List<string> { $"Số file sẽ cài: {manifest.Files.Count}. Bản gốc được sao lưu." };
            var font = AssetInventoryPresentation.FromPatch(manifest.FontPreflight);
            lines.AddRange(font);
            return string.Join(Environment.NewLine, lines);
        }
        catch (Exception) { return ""; }
    }

    /// <summary>Sizes the window to its content (bounded by the screen): fixed width, height = rows + card + frame padding.  Never grows to fill spare space.</summary>
    private void FitToContent()
    {
        if (_fitting || !IsHandleCreated) return;
        _fitting = true;
        try
        {
            var inner = Math.Max(240, _card.ClientSize.Width - _card.Padding.Horizontal);
            _description.MaximumSize = new Size(inner, 0); _summary.MaximumSize = new Size(inner, 0);
            _status.MaximumSize = new Size(Math.Max(120, inner - _statusBox.Padding.Horizontal), 0);
            var need = _flow.GetPreferredSize(new Size(inner, 0)).Height + _card.Padding.Vertical + _frame.Padding.Vertical;
            var chrome = Height - ClientSize.Height;
            var limit = Math.Max(240, Screen.FromControl(this).WorkingArea.Height - chrome - 24);
            _flow.AutoScroll = need > limit;
            var height = Math.Min(need, limit);
            if (Math.Abs(height - ClientSize.Height) > 1) ClientSize = new Size(ClientSize.Width, height);
        }
        finally { _fitting = false; }
    }

    private void SetStatus(Tone tone, string text)
    {
        _statusBox.Fill = tone.Fill; _statusBox.Border = tone.Border; _status.ForeColor = tone.Text; _status.BackColor = tone.Fill; _status.Text = text;
        _statusBox.Invalidate();
        if (IsHandleCreated) BeginInvoke(FitToContent);
    }

    private void BrowseGame()
    {
        using var dialog = new FolderBrowserDialog { Description = "Chọn thư mục gốc của game" };
        if (dialog.ShowDialog(this) == DialogResult.OK) _gamePath.Text = dialog.SelectedPath;
    }

    private void ShowConfirm(bool on)
    {
        _confirm.Visible = _cancelConfirm.Visible = on;
        _install.Visible = _uninstall.Visible = _restoreClean.Visible = !on;
        AcceptButton = null;                              // during a confirmation Enter acts on the focused button, which starts on the safe choice
        if (on)
        {
            _confirm.Text = _confirmingInstall ? "Xác nhận cài" : _cleanRequested ? "Xác nhận về gốc" : "Xác nhận gỡ";
            _cancelConfirm.Text = _confirmingInstall ? "Quay lại" : "Giữ patch";
            if (_cleanRequested) SetStatus(Warn, "Đưa các file về đúng bản gốc đầu tiên được ghi nhận trước mọi patch VNText (gỡ cả các lớp patch cũ hơn). File có sẵn không do VNText quản lý được trả lại nguyên trạng, không bị xóa.");
            else SetStatus(Warn, _confirmingInstall ? "Cài vào thư mục đã chọn và sao lưu bản gốc? Font/mapping trong game chưa được chứng minh đầy đủ." : "Khôi phục toàn bộ file gốc của patch này? Chỉ những file patch đã ghi được hoàn tác.");
            _cancelConfirm.Focus();
        }
        else { _confirmingInstall = false; _cleanRequested = false; RefreshState(); }
    }

    private async Task RunAsync(Func<(Tone Tone, string Text)> work)
    {
        if (_working) return;
        _working = true; _busy.Visible = true; _install.Enabled = _uninstall.Enabled = _restoreClean.Enabled = _browse.Enabled = _gamePath.Enabled = false;
        SetStatus(Info, "Đang xử lý… vui lòng không đóng cửa sổ này.");
        Tone tone; string text;
        try { (tone, text) = await Task.Run(work); }
        catch (Exception ex) { tone = Bad; text = ex.Message; }
        _working = false; _busy.Visible = false; _browse.Enabled = _gamePath.Enabled = true;
        RefreshState();
        SetStatus(tone, text);
    }

    private void RefreshState()
    {
        if (_working) return;
        _install.Enabled = false; _uninstall.Enabled = false; _restoreClean.Enabled = false; AcceptButton = null;
        if (string.IsNullOrWhiteSpace(_gamePath.Text))
        {
            SetStatus(Warn, File.Exists(_service.StatePath) ? "Patch đã được cài. Chọn đúng thư mục game để kiểm tra và gỡ cài đặt." : "Chọn thư mục gốc của game để kiểm tra.");
            return;
        }
        try
        {
            if (File.Exists(_service.StatePath))
            {
                _service.ValidateInstalledState(_gamePath.Text);
                _uninstall.Enabled = true; _restoreClean.Enabled = true;
                SetStatus(Good, "Game hợp lệ. Bản Việt hóa đang được cài trên game này; có thể gỡ cài đặt (về trạng thái trước lần cài này) hoặc về bản gốc sạch.");
            }
            else
            {
                _service.ValidateGame(_gamePath.Text);
                _install.Enabled = true; AcceptButton = _install;
                var owned = _service.DescribeOwnership(_gamePath.Text);
                SetStatus(Warn, "Game hợp lệ. Chưa chứng minh mapping font trong game; kiểm font và xác nhận trước khi cài." + (owned.Count == 0 ? "" : Environment.NewLine + string.Join(Environment.NewLine, owned)));
            }
        }
        catch (Exception ex) { SetStatus(Bad, ex.Message); }
    }
}
