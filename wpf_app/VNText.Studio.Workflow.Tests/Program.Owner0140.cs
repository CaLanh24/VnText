using System.IO;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.Workflow.Tests;

/// <summary>0.1.40: findings from running real games.  Synthetic state only.</summary>
internal static partial class Program
{
    private static void Owner0140_ImageNamesShowThePathNotTheEncodedArchiveReference()
    {
        var encoded = "C%3A%5CUsers%5Cx%5Cgame%5Carchive.rpa?member=gui%2Fbutton%2Fabout_idle.png";
        AssertEqual("gui/button/about_idle.png", ImagePackageProbe.FriendlyName(encoded));
        AssertEqual("plain.png", ImagePackageProbe.FriendlyName(@"C:\g\images\plain.png"));
    }

    private static void Owner0140_CsvFromAnotherFolderIsSaidNextToTheOutputFolder()
    {
        using var worker = new PythonWorkerHost();
        using var vm = new MainViewModel(new FakePathPicker(), worker, startWorker: false);
        var root = Path.Combine(Path.GetTempPath(), "vnt0140-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(Path.Combine(root, "out")); Directory.CreateDirectory(Path.Combine(root, "elsewhere"));
        try
        {
            vm.OutputPath = Path.Combine(root, "out");
            AssertEqual("", vm.CsvElsewhereNote);
            vm.TestSetTranslationCsvPath(Path.Combine(root, "out", "translation.csv"));
            AssertEqual("", vm.CsvElsewhereNote);                                        // same folder: nothing to say
            vm.TestSetTranslationCsvPath(Path.Combine(root, "elsewhere", "translation.csv"));
            AssertTrue(vm.CsvElsewhereNote.Contains("elsewhere", StringComparison.OrdinalIgnoreCase));
            AssertTrue(vm.CsvElsewhereNoteVisible);
        }
        finally { try { Directory.Delete(root, true); } catch (IOException) { } }
    }
}
