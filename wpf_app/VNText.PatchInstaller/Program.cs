using System.Drawing;
using System.Windows.Forms;

namespace VNText.PatchInstaller;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        var patchDir = AppContext.BaseDirectory;
        if (args.Length >= 3 && (args[0].Equals("--install", StringComparison.OrdinalIgnoreCase) || args[0].Equals("--uninstall", StringComparison.OrdinalIgnoreCase)))
        {
            try
            {
                var service = new InstallerService(args[2]);
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
    private readonly InstallerService _service;
    private readonly TextBox _gamePath = new() { Dock = DockStyle.Fill };
    private readonly Label _status = new() { AutoSize = true, MaximumSize = new Size(620, 0) };
    private readonly Button _install = new() { Text = "Cài đặt", AutoSize = true, Enabled = false };
    private readonly Button _uninstall = new() { Text = "Gỡ cài đặt", AutoSize = true, Enabled = false };

    public InstallerForm(string patchDir)
    {
        _service = new InstallerService(patchDir);
        Text = "VNText Patch Installer";
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(700, 300);
        Width = 760;
        Height = 330;

        var title = new Label { Text = "Cài đặt bản Việt hóa", AutoSize = true, Font = new Font(Font, FontStyle.Bold), Dock = DockStyle.Fill };
        var description = new Label { Text = "Chọn thư mục gốc của game (cùng cấp với file .exe và thư mục Unity *_Data). Installer sẽ kiểm tra layout, backup và hash trước khi ghi.", AutoSize = true, MaximumSize = new Size(650, 0), Dock = DockStyle.Fill };
        var browse = new Button { Text = "Chọn game...", AutoSize = true };
        browse.Click += (_, _) => BrowseGame();
        _gamePath.TextChanged += (_, _) => RefreshState();
        _install.Click += (_, _) => Install();
        _uninstall.Click += (_, _) => Uninstall();

        var pathRow = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, AutoSize = true };
        pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        pathRow.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
        pathRow.Controls.Add(_gamePath, 0, 0);
        pathRow.Controls.Add(browse, 1, 0);
        var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, FlowDirection = FlowDirection.LeftToRight };
        buttons.Controls.Add(_install);
        buttons.Controls.Add(_uninstall);
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(24), RowCount = 6, ColumnCount = 1 };
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        layout.Controls.Add(title, 0, 0);
        layout.Controls.Add(description, 0, 1);
        layout.Controls.Add(new Label { Text = "Thư mục game:", AutoSize = true }, 0, 2);
        layout.Controls.Add(pathRow, 0, 3);
        layout.Controls.Add(_status, 0, 4);
        layout.Controls.Add(buttons, 0, 5);
        Controls.Add(layout);
        Shown += (_, _) => RefreshState();
    }

    private void BrowseGame()
    {
        using var dialog = new FolderBrowserDialog { Description = "Chọn thư mục gốc của game" };
        if (dialog.ShowDialog(this) == DialogResult.OK) _gamePath.Text = dialog.SelectedPath;
    }

    private void RefreshState()
    {
        _install.Enabled = false;
        _uninstall.Enabled = false;
        if (string.IsNullOrWhiteSpace(_gamePath.Text))
        {
            _status.ForeColor = Color.DarkGoldenrod;
            _status.Text = File.Exists(_service.StatePath)
                ? "Patch đã cài. Chọn đúng thư mục game để kiểm tra và gỡ cài đặt."
                : "Chọn thư mục gốc của game để kiểm tra.";
            return;
        }
        try
        {
            if (File.Exists(_service.StatePath))
            {
                _service.ValidateInstalledState(_gamePath.Text);
                _uninstall.Enabled = true;
                _status.ForeColor = Color.DarkGreen;
                _status.Text = "Game hợp lệ. Patch đang được cài trên game này; có thể gỡ cài đặt.";
            }
            else
            {
                _service.ValidateGame(_gamePath.Text);
                _install.Enabled = true;
                _status.ForeColor = Color.DarkGreen;
                _status.Text = "Game hợp lệ. Sẵn sàng cài đặt.";
            }
        }
        catch (Exception ex)
        {
            _status.ForeColor = Color.DarkRed;
            _status.Text = ex.Message;
        }
    }

    private void Install()
    {
        try
        {
            var state = _service.Install(_gamePath.Text);
            MessageBox.Show(this, $"Đã cài {state.Files.Count} file. Backup đã được lưu theo manifest/hash.", "Cài đặt thành công", MessageBoxButtons.OK, MessageBoxIcon.Information);
            RefreshState();
        }
        catch (Exception ex) { MessageBox.Show(this, ex.Message, "Cài đặt thất bại", MessageBoxButtons.OK, MessageBoxIcon.Error); }
    }

    private void Uninstall()
    {
        try
        {
            if (MessageBox.Show(this, "Khôi phục toàn bộ file gốc của patch này?", "Xác nhận gỡ cài đặt", MessageBoxButtons.OKCancel, MessageBoxIcon.Warning) != DialogResult.OK) return;
            _service.Uninstall(_gamePath.Text);
            MessageBox.Show(this, "Đã gỡ patch và khôi phục đúng file gốc.", "Gỡ cài đặt thành công", MessageBoxButtons.OK, MessageBoxIcon.Information);
            RefreshState();
        }
        catch (Exception ex) { MessageBox.Show(this, ex.Message, "Gỡ cài đặt thất bại", MessageBoxButtons.OK, MessageBoxIcon.Error); }
    }
}
