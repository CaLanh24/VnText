namespace VNText.Studio.App.Services;

public interface IPathPickerService
{
    /// <summary>The game FOLDER picker.  Cancel returns null and nothing else opens (N8: no silent second picker).</summary>
    string? PickInputPath();

    /// <summary>The explicit single asset / bundle FILE picker (a separate choice from the folder).</summary>
    string? PickInputAssetFile();

    string? PickOutputFolder();

    string? PickTranslationCsvFile(string? title = null);

    string? PickRenpySdkFolder();

    string? PickImageFile(bool review = false);

    bool OpenPath(string path);
}
