using System.Collections.ObjectModel;
using System.Text.RegularExpressions;
using System.Windows;
using VNText.Studio.App.Models;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public sealed partial class MainViewModel
{
    private string _glossaryTerm = "";
    private string _glossaryTranslation = "";
    private string _glossaryStatus = "Danh sách từ được lưu cùng gói dịch.";

    public ObservableCollection<GlossaryItem> GlossaryEntries { get; } = [];

    public string GlossaryTerm
    {
        get => _glossaryTerm;
        set => Set(ref _glossaryTerm, value);
    }

    public string GlossaryTranslation
    {
        get => _glossaryTranslation;
        set => Set(ref _glossaryTranslation, value);
    }

    public string GlossaryStatus
    {
        get => _glossaryStatus;
        private set => Set(ref _glossaryStatus, value);
    }

    private void InitGlossaryCommands()
    {
        AddGlossaryEntryCommand = new RelayCommand(_ => AddGlossaryEntry());
        RemoveGlossaryEntryCommand = new RelayCommand(item => RemoveGlossaryEntry(item as GlossaryItem));
    }

    private void LoadPackageGlossary()
    {
        GlossaryEntries.Clear();
        var path = PackageGlossaryService.ResolvePath(TranslationCsvPath);
        if (string.IsNullOrWhiteSpace(path))
        {
            GlossaryStatus = "Chọn file dịch trước khi thêm thuật ngữ.";
            return;
        }
        foreach (var item in PackageGlossaryService.Load(TranslationCsvPath)
                     .OrderBy(x => x.Key, StringComparer.OrdinalIgnoreCase))
            GlossaryEntries.Add(new GlossaryItem(item.Key, item.Value));
        GlossaryStatus = GlossaryEntries.Count == 0
            ? "Chưa có thuật ngữ. Thêm từ bạn muốn dịch thống nhất."
            : $"Đã lưu {GlossaryEntries.Count:N0} thuật ngữ.";
    }

    private void AddGlossaryEntry()
    {
        var term = (GlossaryTerm ?? "").Trim();
        var translation = (GlossaryTranslation ?? "").Trim();
        if (string.IsNullOrWhiteSpace(TranslationCsvPath))
        {
            ShowToast("Chọn file dịch trước khi thêm thuật ngữ.", "warning");
            return;
        }
        if (string.IsNullOrWhiteSpace(term) || string.IsNullOrWhiteSpace(translation))
        {
            ShowToast("Nhập từ gốc và cách dịch ưu tiên.", "warning");
            return;
        }
        if (!GlossaryStructureCompatible(term, translation))
        {
            ShowToast("Bản dịch cần giữ nguyên ký hiệu và xuống dòng của từ gốc.", "warning");
            return;
        }
        var entries = PackageGlossaryService.Load(TranslationCsvPath);
        var existing = entries.Keys.FirstOrDefault(k => string.Equals(k, term, StringComparison.OrdinalIgnoreCase));
        if (existing is not null)
            entries.Remove(existing);
        entries[term] = translation;
        try
        {
            PackageGlossaryService.Save(TranslationCsvPath, entries);
            GlossaryTerm = "";
            GlossaryTranslation = "";
            LoadPackageGlossary();
            ShowToast($"Đã lưu glossary: {term} → {translation}", "success");
            AppendLog($"Glossary package updated: {PackageGlossaryService.ResolvePath(TranslationCsvPath)}");
        }
        catch (Exception ex)
        {
            ShowToast($"Không lưu được glossary: {ex.Message}", "error");
        }
    }

    private void RemoveGlossaryEntry(GlossaryItem? item)
    {
        if (item is null || string.IsNullOrWhiteSpace(TranslationCsvPath))
            return;
        if (MessageBox.Show($"Xóa thuật ngữ “{item.Term}”?", "Xác nhận xóa", MessageBoxButton.YesNo, MessageBoxImage.Warning) != MessageBoxResult.Yes)
            return;
        var entries = PackageGlossaryService.Load(TranslationCsvPath);
        var key = entries.Keys.FirstOrDefault(k => string.Equals(k, item.Term, StringComparison.OrdinalIgnoreCase));
        if (key is not null)
            entries.Remove(key);
        PackageGlossaryService.Save(TranslationCsvPath, entries);
        LoadPackageGlossary();
    }

    private static bool GlossaryStructureCompatible(string source, string translation)
    {
        static string[] Tokens(string text) =>
            Regex.Matches(text, @"<[^>]*>|\{[^{}]*\}|\\n|\[br\]", RegexOptions.IgnoreCase)
                .Select(m => m.Value).ToArray();
        return Tokens(source).SequenceEqual(Tokens(translation), StringComparer.OrdinalIgnoreCase);
    }
}
