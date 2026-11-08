using System.Drawing;
using System.Drawing.Drawing2D;
using System.Reflection;
using System.Windows.Forms;

namespace VNText.PatchInstaller;

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
        Line = Color.FromArgb(0xD7, 0xDD, 0xE8), Ink = Color.FromArgb(0x11, 0x18, 0x27), Muted = Color.FromArgb(0x8A, 0x96, 0xA8), Disabled = Color.FromArgb(0xF1, 0xF3, 0xF7);
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
        else { fill = _down || _hover ? BlueSoft : Color.White; border = _hover ? Blue : Line; text = Ink; }
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
    private static readonly Color Canvas = Color.FromArgb(0xF2, 0xF6, 0xFC), Surface = Color.White, Ink = Color.FromArgb(0x11, 0x18, 0x27),
        Muted = Color.FromArgb(0x4B, 0x5B, 0x71), Line = Color.FromArgb(0xE5, 0xE7, 0xEB), Blue = Color.FromArgb(0x28, 0x68, 0xE8);
    private static readonly Tone Good = new(Color.FromArgb(0xD8, 0xED, 0xE1), Color.FromArgb(0xA1, 0xE2, 0xBA), Color.FromArgb(0x15, 0x80, 0x3D));
    private static readonly Tone Warn = new(Color.FromArgb(0xFD, 0xF3, 0xDC), Color.FromArgb(0xF0, 0xCF, 0x8A), Color.FromArgb(0x8A, 0x50, 0x00));
    private static readonly Tone Bad = new(Color.FromArgb(0xFB, 0xE6, 0xE6), Color.FromArgb(0xEE, 0xB0, 0xB0), Color.FromArgb(0xA3, 0x2B, 0x2B));
    private static readonly Tone Info = new(Color.FromArgb(0xE9, 0xF1, 0xFF), Color.FromArgb(0xBF, 0xD6, 0xFB), Color.FromArgb(0x1F, 0x4F, 0xB8));

    private readonly InstallerService _service;
    private readonly TextBox _gamePath = new() { BorderStyle = BorderStyle.None, Dock = DockStyle.Fill, BackColor = Color.White };
    private readonly RoundedPanel _card = new() { Radius = 16, Padding = new Padding(28, 24, 28, 24) };
    private readonly RoundedPanel _statusBox = new() { Radius = 10, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, Padding = new Padding(16, 12, 16, 12), Margin = new Padding(0, 16, 0, 12), MinimumSize = new Size(0, 52) };
    private readonly Label _status = new() { AutoSize = true, Location = new Point(16, 12) };
    private readonly Label _description = new() { AutoSize = true, ForeColor = Muted, Margin = new Padding(0, 4, 0, 4) };
    private readonly RoundedButton _install = new("Cài đặt", true) { Enabled = false };
    private readonly RoundedButton _uninstall = new("Gỡ cài đặt") { Enabled = false };
    private readonly RoundedButton _confirm = new("Xác nhận gỡ", true) { Visible = false };
    private readonly RoundedButton _cancelConfirm = new("Giữ patch") { Visible = false };
    private readonly RoundedButton _browse = new("Chọn game…") { Margin = new Padding(10, 0, 0, 0) };
    private readonly ProgressBar _busy = new() { Height = 4, Style = ProgressBarStyle.Marquee, MarqueeAnimationSpeed = 30, Visible = false, Dock = DockStyle.Top };
    private bool _working;

    public InstallerForm(string patchDir)
    {
        _service = new InstallerService(patchDir);
        Text = "VNText Studio — Cài đặt bản Việt hóa";
        Icon = Icon.ExtractAssociatedIcon(Environment.ProcessPath!);
        AutoScaleMode = AutoScaleMode.Dpi; AutoScaleDimensions = new SizeF(96F, 96F);
        Font = new Font("Segoe UI", 10F);
        BackColor = Canvas; ForeColor = Ink;
        StartPosition = FormStartPosition.CenterScreen;
        ClientSize = new Size(680, 520); MinimumSize = new Size(560, 500);

        // Header: the app's brand mark (same artwork as the app), a real title, then a description that wraps to its own height.
        Image? logo = null;
        using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("VNText.Logo.png")) if (stream is not null) logo = Image.FromStream(stream);
        var mark = new RoundedPicture { Size = new Size(56, 56), Image = logo, Margin = new Padding(0, 0, 16, 0), BackColor = Surface };
        var title = new Label { Text = "Cài đặt bản Việt hóa", AutoSize = true, Font = new Font("Segoe UI Semibold", 20F), Margin = new Padding(0, 0, 0, 0), Anchor = AnchorStyles.Left };
        var heading = new TableLayoutPanel { AutoSize = true, ColumnCount = 2, RowCount = 1, Dock = DockStyle.Top, BackColor = Surface };
        heading.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize)); heading.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        heading.Controls.Add(mark, 0, 0); heading.Controls.Add(title, 1, 0);
        _description.Text = "Chọn thư mục gốc của game (Unity hoặc Ren'Py). Chỉ các file bị sửa được sao lưu, để có thể gỡ patch về đúng bản gốc.";

        var label = new Label { Text = "Thư mục game", AutoSize = true, ForeColor = Muted, Margin = new Padding(0, 16, 0, 6) };
        var field = new RoundedPanel { Radius = 10, Border = Color.FromArgb(0xD7, 0xDD, 0xE8), Padding = new Padding(12, 11, 12, 8), Height = 42, Dock = DockStyle.Fill };
        field.Controls.Add(_gamePath);
        _gamePath.Enter += (_, _) => field.Border = Blue; _gamePath.Leave += (_, _) => field.Border = Color.FromArgb(0xD7, 0xDD, 0xE8);
        _gamePath.TextChanged += (_, _) => RefreshState();
        var pathRow = new TableLayoutPanel { AutoSize = true, ColumnCount = 2, RowCount = 1, Dock = DockStyle.Top, BackColor = Surface };
        pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        pathRow.Controls.Add(field, 0, 0); pathRow.Controls.Add(_browse, 1, 0);

        _statusBox.Controls.Add(_status);
        var actions = new FlowLayoutPanel { AutoSize = true, Dock = DockStyle.Top, FlowDirection = FlowDirection.LeftToRight, WrapContents = true, BackColor = Surface, Margin = new Padding(0) };
        actions.Controls.Add(_install); actions.Controls.Add(_uninstall); actions.Controls.Add(_confirm); actions.Controls.Add(_cancelConfirm);

        _browse.Click += (_, _) => BrowseGame();
        _install.Click += async (_, _) => await RunAsync(() =>
        {
            var state = _service.Install(_gamePath.Text);
            return (Good, $"Đã cài bản Việt hóa ({state.Files.Count} file). Bản gốc được sao lưu để có thể gỡ cài đặt.");
        });
        _uninstall.Click += (_, _) => ShowConfirm(true);
        _cancelConfirm.Click += (_, _) => ShowConfirm(false);
        _confirm.Click += async (_, _) =>
        {
            ShowConfirm(false);
            await RunAsync(() => { _service.Uninstall(_gamePath.Text); return (Good, "Đã gỡ patch và khôi phục đúng các file gốc."); });
        };
        AcceptButton = _install; CancelButton = _cancelConfirm;

        // One column, every row sized by its content (no fixed heights), so nothing is clipped at the default or minimum size or at 150% scaling.
        var flow = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 1, AutoScroll = false, BackColor = Surface };
        flow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        foreach (Control c in new Control[] { heading, _description, label, pathRow, _statusBox, _busy, actions })
        {
            c.Dock = DockStyle.Fill; flow.RowStyles.Add(new RowStyle(SizeType.AutoSize)); flow.Controls.Add(c);
        }
        _card.Controls.Add(flow);
        _card.Dock = DockStyle.Fill; _card.Fill = Surface;
        var frame = new Panel { Dock = DockStyle.Fill, Padding = new Padding(20), BackColor = Canvas };
        frame.Controls.Add(_card);
        Controls.Add(frame);

        void Fit()
        {
            var inner = Math.Max(240, _card.ClientSize.Width - _card.Padding.Horizontal);
            _description.MaximumSize = new Size(inner, 0);
            _status.MaximumSize = new Size(Math.Max(120, inner - _statusBox.Padding.Horizontal), 0);
        }
        _card.SizeChanged += (_, _) => Fit();
        Shown += (_, _) => { Fit(); RefreshState(); };
    }

    private void SetStatus(Tone tone, string text)
    {
        _statusBox.Fill = tone.Fill; _statusBox.Border = tone.Border; _status.ForeColor = tone.Text; _status.BackColor = tone.Fill; _status.Text = text;
        _statusBox.Invalidate();
    }

    private void BrowseGame()
    {
        using var dialog = new FolderBrowserDialog { Description = "Chọn thư mục gốc của game" };
        if (dialog.ShowDialog(this) == DialogResult.OK) _gamePath.Text = dialog.SelectedPath;
    }

    private void ShowConfirm(bool on)
    {
        _confirm.Visible = _cancelConfirm.Visible = on;
        _install.Visible = _uninstall.Visible = !on;
        if (on) { SetStatus(Warn, "Khôi phục toàn bộ file gốc của patch này? Chỉ những file patch đã ghi được hoàn tác."); _cancelConfirm.Focus(); }
        else RefreshState();
    }

    private async Task RunAsync(Func<(Tone Tone, string Text)> work)
    {
        if (_working) return;
        _working = true; _busy.Visible = true; _install.Enabled = _uninstall.Enabled = _browse.Enabled = _gamePath.Enabled = false;
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
        _install.Enabled = false; _uninstall.Enabled = false;
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
                _uninstall.Enabled = true;
                SetStatus(Good, "Game hợp lệ. Bản Việt hóa đang được cài trên game này; có thể gỡ cài đặt.");
            }
            else
            {
                _service.ValidateGame(_gamePath.Text);
                _install.Enabled = true;
                SetStatus(Good, "Game hợp lệ. Sẵn sàng cài đặt.");
            }
        }
        catch (Exception ex) { SetStatus(Bad, ex.Message); }
    }
}
