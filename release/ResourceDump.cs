// Dumps the embedded "Payload.zip" resource of a VNText Studio Setup.exe (used by release/extract_setup_payload.py to rebuild baselines for update tests).
using System;
using System.IO;
using System.Reflection;
static class P {
    static int Main(string[] a) {
        if (a.Length != 2) { Console.Error.WriteLine("usage: ResourceDump <Setup.exe> <out.zip>"); return 64; }
        var asm = Assembly.LoadFrom(a[0]);
        using (var s = asm.GetManifestResourceStream("Payload.zip"))
        using (var o = File.Create(a[1])) { if (s == null) return 2; s.CopyTo(o); }
        return 0;
    }
}
