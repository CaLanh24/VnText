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
        if (args.Length >= 2 && (args[0].Equals("--install", StringComparison.OrdinalIgnoreCase) || args[0].Equals("--uninstall", StringComparison.OrdinalIgnoreCase)
            || args[0].Equals("--restore-original", StringComparison.OrdinalIgnoreCase) || args[0].Equals("--status", StringComparison.OrdinalIgnoreCase)))
        {
            try
            {
                var service = new InstallerService(args.Length >= 3 ? args[2] : patchDir);      // a bundled EXE uses its own verified payload
                if (args[0].Equals("--status", StringComparison.OrdinalIgnoreCase))
                {
                    var lines = service.DescribeOwnership(args[1]);
                    Console.WriteLine(lines.Count == 0 ? "Không có tệp nào do VNText hoặc người dùng đang giữ ở các đường dẫn của patch này." : string.Join(Environment.NewLine, lines));
                }
                else if (args[0].Equals("--install", StringComparison.OrdinalIgnoreCase))
                {
                    var state = service.Install(args[1]);
                    Console.WriteLine($"Installed {state.Files.Count} files to {state.GameRoot}");
                    foreach (var note in state.Notes ?? new List<string>()) Console.WriteLine(note);
                }
                else
                {
                    var clean = args[0].Equals("--restore-original", StringComparison.OrdinalIgnoreCase);
                    var result = service.Uninstall(args[1], null, clean ? UninstallMode.CleanOriginal : UninstallMode.Previous);
                    Console.WriteLine(clean ? "Restored the first original recorded before any VNText patch" : "Uninstalled and restored the files this install replaced");
                    foreach (var note in result.Notes) Console.WriteLine(note);
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

