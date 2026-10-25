namespace VNText.Studio.App.Services;

public interface IPathPickerService
{
    /// <summary>Folder first, then single file asset fallback (Qt parity).</summary>
    string? PickInputPath();

    string? PickOutputFolder();

    string? PickTranslationCsvFile(string? title = null);

    string? PickRenpySdkFolder();

    string? PickImageFile(bool review = false);

    bool OpenPath(string path);
}
