using VNText.PatchInstaller;

// usage: InstallerCli <install|uninstall|restore-original> <patchDir> <gameRoot>
internal static class Cli
{
    private static int Main(string[] args)
    {
        if (args.Length != 3) { Console.Error.WriteLine("usage: InstallerCli <install|uninstall|restore-original> <patchDir> <gameRoot>"); return 2; }
        try
        {
            var service = new InstallerService(args[1]);
            if (args[0] == "install") { var state = service.Install(args[2]); Console.WriteLine($"installed {state.Files.Count}"); foreach (var n in state.Notes ?? new()) Console.WriteLine(n); }
            else { var r = service.Uninstall(args[2], null, args[0] == "restore-original" ? UninstallMode.CleanOriginal : UninstallMode.Previous); foreach (var n in r.Notes) Console.WriteLine(n); }
            return 0;
        }
        catch (Exception ex) { Console.Error.WriteLine(ex.Message); return 1; }
    }
}
