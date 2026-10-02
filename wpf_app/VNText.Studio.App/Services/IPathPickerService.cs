namespace VNText.Studio.App.Services;

public interface IPathPickerService
{
    /// <summary>Folder first, then single file asset fallback (Qt parity).</summary>
    string? PickInputPath();

    string? PickOutputFolder();

    string? PickTranslationCsvFile();

    string? PickRenpySdkFolder();

    bool OpenPath(string path);
}
