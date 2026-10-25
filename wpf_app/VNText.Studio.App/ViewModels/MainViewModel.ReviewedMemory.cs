using System.Windows;
using System.Windows.Controls;
using VNText.Studio.App.Services;

namespace VNText.Studio.App.ViewModels;

public partial class MainViewModel
{
    public RelayCommand ApproveCsvMemoryCommand { get; private set; } = null!;
    internal Func<string, IReadOnlyList<string>, string?, ReviewedMemoryResult> ReviewMemoryRequest { get; set; }
        = (path, keys, token) => TranslationCsvEditorService.ReviewMemory(path, keys, token);
    internal Func<ReviewedMemoryResult, bool> ReviewMemoryConfirmation { get; set; } = ShowReviewMemoryPreview;

    private bool CanApproveCsvMemory() => !Busy && !CsvEditorDirty && !CsvEditorLoading
        && !string.IsNullOrWhiteSpace(CsvEditorPath) && _csvEditorSelectedKeys.Count > 0;

    private void ApproveCsvMemory()
    {
        if (!CanApproveCsvMemory()) return;
        var path = CsvEditorPath;
        var keys = _csvEditorSelectedKeys.ToArray();
        var preview = ReviewMemoryRequest(path, keys, null);
        if (!preview.Ok) { ShowToast(preview.Error ?? UiText.Translate("Không thể xem trước bản dịch."), "error"); return; }
        if (!ReviewMemoryConfirmation(preview)) return;
        // Dialog is modal, but recheck editor/task state and selection anyway.
        if (!CanApproveCsvMemory() || path != CsvEditorPath || !keys.SequenceEqual(_csvEditorSelectedKeys))
        { ShowToast(UiText.Translate("Dữ liệu đã đổi; hãy chọn và xem trước lại."), "warning"); return; }
        var result = ReviewMemoryRequest(path, keys, preview.PreviewToken);
        if (!result.Ok) { ShowToast(result.Error ?? UiText.Translate("Không thể ghi bản dịch đã duyệt."), "error"); return; }
        CsvEditorStatus = string.Format(UiText.Translate("Đã duyệt {0} dòng để dùng trong gói hiện tại."), result.Count);
        ShowToast(CsvEditorStatus, "success");
    }

    private static bool ShowReviewMemoryPreview(ReviewedMemoryResult preview)
    {
        var explanation = string.Format(UiText.Translate("{0} dòng đã chọn."), preview.Count) + " "
            + UiText.Translate("Chỉ gói hiện tại và đúng nguồn, file, ngữ cảnh, cách nhập; không dùng cho gói khác.")
            + "\n" + UiText.Translate("Không dùng để huấn luyện hoặc làm bản dịch mặc định toàn app.")
            + (preview.ConvertsLegacy ? "\n" + UiText.Translate("Bộ nhớ cũ sẽ được giữ bản sao; chỉ các dòng xác nhận được đưa vào bộ nhớ đã duyệt.") : "");
        var text = string.Join("\n\n", preview.Rows.Select(row =>
            $"{row.GetValueOrDefault("key")} — {row.GetValueOrDefault("file_path")} / {row.GetValueOrDefault("context")}\n{UiText.Translate("Nguồn:")} {row.GetValueOrDefault("source_text")}\n{UiText.Translate("Bản dịch:")} {row.GetValueOrDefault("translation")}"));
        var body = new StackPanel();
        var heading = new TextBlock { Text = explanation, TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 0, 0, 12) };
        heading.SetResourceReference(FrameworkElement.StyleProperty, "UiBodyTextStyle");
        body.Children.Add(heading);
        var previewText = new TextBox { Text = text, IsReadOnly = true, TextWrapping = TextWrapping.Wrap, Height = 320,
            VerticalContentAlignment = VerticalAlignment.Top,
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto, HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled };
        previewText.SetResourceReference(FrameworkElement.StyleProperty, "FieldTextBoxStyle");
        previewText.SetResourceReference(Control.FontSizeProperty, "UiBodySize");
        body.Children.Add(previewText);
        var accepted = false;
        var dialog = new AppDialogWindow(Application.Current?.MainWindow, UiText.Translate("Duyệt bản dịch trong gói này"), body, 760);
        // X / Esc dismiss keeps the safe default: nothing is approved.
        dialog.AddButton(UiText.Translate("Hủy"), () => accepted = false);
        dialog.AddButton(UiText.Translate("Xác nhận đã duyệt"), () => accepted = true, primary: true);
        dialog.ShowDialog();
        return accepted;
    }
}
