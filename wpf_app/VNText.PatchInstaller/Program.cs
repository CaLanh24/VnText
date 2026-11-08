using System.Drawing;
using System.Windows.Forms;

namespace VNText.PatchInstaller;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        string patchDir;
        try { patchDir = EmbeddedPatch.Open(Environment.ProcessPath!, Environment.GetEnvironmentVariable("VNTEXT_PATCH_STORAGE")); }
        catch (Exception ex)
        {
            if (args.Length >= 2 && args[0].StartsWith("--", StringComparison.Ordinal)) { Console.Error.WriteLine(ex.Message); return 1; }     // scripted use never blocks on a dialog
            MessageBox.Show(ex.Message, "Không mở được patch", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        if (args.Length >= 2 && (args[0].Equals("--install", StringComparison.OrdinalIgnoreCase) || args[0].Equals("--uninstall", StringComparison.OrdinalIgnoreCase)))
        {
            try
            {
                var service = new InstallerService(args.Length >= 3 ? args[2] : patchDir);      // a bundled EXE uses its own verified payload
                if (args[0].Equals("--install", StringComparison.OrdinalIgnoreCase))
                {
                    var state = service.Install(args[1]);
                    Console.WriteLine($"Installed {state.Files.Count} files to {state.GameRoot}");
                }
                else
                {
                    service.Uninstall(args[1]);
                    Console.WriteLine("Uninstalled and restored original files");
                }
                return 0;
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine(ex.Message);
                return 1;
            }
        }

        ApplicationConfiguration.Initialize();
        Application.Run(new InstallerForm(patchDir));
        return 0;
    }
}

internal sealed class InstallerForm : Form
{
    private readonly record struct Tone(Color Fill, Color Border, Color Text);

    // Tokens taken from the app (Themes/DesignTokens.xaml): canvas, surface, ink, muted, line, blue, plus the About banner green.
    private static readonly Color Canvas = Color.FromArgb(0xF2, 0xF6, 0xFC), Surface = Color.White, Ink = Color.FromArgb(0x11, 0x18, 0x27),
        Muted = Color.FromArgb(0x4B, 0x5B, 0x71), Line = Color.FromArgb(0xE5, 0xE7, 0xEB), Blue = Color.FromArgb(0x28, 0x68, 0xE8),
        BlueHover = Color.FromArgb(0x1F, 0x55, 0xC8), BlueSoft = Color.FromArgb(0xE9, 0xF1, 0xFF);
    private static readonly Tone Good = new(Color.FromArgb(0xD8, 0xED, 0xE1), Color.FromArgb(0xA1, 0xE2, 0xBA), Color.FromArgb(0x15, 0x80, 0x3D));
    private static readonly Tone Warn = new(Color.FromArgb(0xFD, 0xF3, 0xDC), Color.FromArgb(0xF0, 0xCF, 0x8A), Color.FromArgb(0x8A, 0x50, 0x00));
    private static readonly Tone Bad = new(Color.FromArgb(0xFB, 0xE6, 0xE6), Color.FromArgb(0xEE, 0xB0, 0xB0), Color.FromArgb(0xA3, 0x2B, 0x2B));
    private static readonly Tone Info = new(Color.FromArgb(0xE9, 0xF1, 0xFF), Color.FromArgb(0xBF, 0xD6, 0xFB), Color.FromArgb(0x1F, 0x4F, 0xB8));

    private readonly InstallerService _service;
    private readonly TextBox _gamePath = new() { Dock = DockStyle.Fill, BorderStyle = BorderStyle.FixedSingle, Margin = new Padding(0, 4, 8, 0) };
    private readonly Label _status = new() { Dock = DockStyle.Top, AutoSize = false, Height = 64, Padding = new Padding(16, 8, 16, 8), TextAlign = ContentAlignment.MiddleLeft };
    private readonly Button _install = new() { Text = "Cài đặt", Enabled = false };
    private readonly Button _uninstall = new() { Text = "Gỡ cài đặt", Enabled = false };
    private readonly Button _confirm = new() { Text = "Xác nhận gỡ", Visible = false };
    private readonly Button _cancelConfirm = new() { Text = "Giữ patch", Visible = false };
    private readonly Button _browse = new() { Text = "Chọn game…" };
    private readonly ProgressBar _busy = new() { Dock = DockStyle.Top, Height = 4, Style = ProgressBarStyle.Marquee, MarqueeAnimationSpeed = 30, Visible = false };
    private bool _working;

    public InstallerForm(string patchDir)
    {
        _service = new InstallerService(patchDir);
        Text = "VNText Studio — Cài đặt bản Việt hóa";
        Icon = Icon.ExtractAssociatedIcon(Environment.ProcessPath!);
        Font = new Font("Segoe UI", 10F);
        BackColor = Canvas; ForeColor = Ink;
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(640, 460); ClientSize = new Size(680, 480);

        var logo = new PictureBox { Size = new Size(40, 40), SizeMode = PictureBoxSizeMode.Zoom, Margin = new Padding(0, 0, 12, 0), Image = Icon!.ToBitmap() };
        var title = new Label { Text = "Cài đặt bản Việt hóa", AutoSize = true, Font = new Font("Segoe UI Semibold", 18F), Margin = new Padding(0, 4, 0, 0) };
        var heading = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 48, FlowDirection = FlowDirection.LeftToRight, WrapContents = false };
        heading.Controls.Add(logo); heading.Controls.Add(title);
        var subtitle = new Label { Text = "Chọn thư mục gốc của game (Unity hoặc Ren'Py). Chỉ các file bị sửa được sao lưu, để có thể gỡ patch về đúng bản gốc.", AutoSize = false, Height = 48, Dock = DockStyle.Top, ForeColor = Muted };

        foreach (var button in new[] { _browse, _install, _uninstall, _confirm, _cancelConfirm })
        {
            button.FlatStyle = FlatStyle.Flat; button.UseVisualStyleBackColor = false; button.Cursor = Cursors.Hand;
            button.BackColor = Surface; button.ForeColor = Ink; button.AutoSize = true; button.MinimumSize = new Size(104, 36);
            button.Padding = new Padding(12, 0, 12, 0); button.Margin = new Padding(0, 0, 8, 0);
            button.FlatAppearance.BorderColor = Line; button.FlatAppearance.BorderSize = 1;
            button.FlatAppearance.MouseOverBackColor = BlueSoft; button.FlatAppearance.MouseDownBackColor = BlueSoft;
            var captured = button;
            button.GotFocus += (_, _) => captured.FlatAppearance.BorderColor = Blue;        // visible keyboard focus
            button.LostFocus += (_, _) => captured.FlatAppearance.BorderColor = captured.BackColor == Blue ? Blue : Line;
        }
        foreach (var primary in new[] { _install, _confirm })
        {
            var captured = primary;
            captured.BackColor = Blue; captured.ForeColor = Color.White; captured.FlatAppearance.BorderColor = Blue;
            captured.FlatAppearance.MouseOverBackColor = BlueHover; captured.FlatAppearance.MouseDownBackColor = BlueHover;
        }
        _browse.Click += (_, _) => BrowseGame();
        _gamePath.TextChanged += (_, _) => RefreshState();
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

        var label = new Label { Text = "Thư mục game", AutoSize = false, Height = 28, Dock = DockStyle.Top, ForeColor = Muted };
        var pathRow = new TableLayoutPanel { Dock = DockStyle.Top, ColumnCount = 2, Height = 44 };
        pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100)); pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        pathRow.Controls.Add(_gamePath, 0, 0); pathRow.Controls.Add(_browse, 1, 0);
        var actions = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 56, FlowDirection = FlowDirection.LeftToRight, Padding = new Padding(0, 16, 0, 0) };
        actions.Controls.Add(_install); actions.Controls.Add(_uninstall); actions.Controls.Add(_confirm); actions.Controls.Add(_cancelConfirm);

        var card = new Panel { Dock = DockStyle.Fill, BackColor = Surface, Padding = new Padding(24) };
        card.Paint += (_, e) => { using var pen = new Pen(Line); e.Graphics.DrawRectangle(pen, 0, 0, card.Width - 1, card.Height - 1); };
        // The last control added docks first (top-most).
        card.Controls.Add(actions);
        card.Controls.Add(_status);
        card.Controls.Add(new Panel { Dock = DockStyle.Top, Height = 16 });
        card.Controls.Add(pathRow);
        card.Controls.Add(label);
        card.Controls.Add(subtitle);
        card.Controls.Add(heading);
        card.Controls.Add(_busy);
        var frame = new Panel { Dock = DockStyle.Fill, Padding = new Padding(20) };
        frame.Controls.Add(card);
        Controls.Add(frame);
        _status.Paint += (_, e) => { if (_status.Tag is Color c) { using var pen = new Pen(c); e.Graphics.DrawRectangle(pen, 0, 0, _status.Width - 1, _status.Height - 1); } };
        Shown += (_, _) => RefreshState();
    }

    private void SetStatus(Tone tone, string text)
    {
        _status.BackColor = tone.Fill; _status.ForeColor = tone.Text; _status.Text = text; _status.Tag = tone.Border; _status.Invalidate();
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
