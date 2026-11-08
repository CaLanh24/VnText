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

