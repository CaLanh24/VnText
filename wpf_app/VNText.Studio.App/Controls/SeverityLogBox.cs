using System.Windows;
using System.Windows.Controls;
using System.Windows.Documents;
using VNText.Studio.App.Converters;

namespace VNText.Studio.App.Controls;

/// <summary>Selectable, copyable journal text with per-line semantic severity.</summary>
internal sealed class SeverityLogBox : RichTextBox
{
    private string _text = "";
    public string Text
    {
        get => _text;
        set
        {
            _text = value ?? "";
            Document = new FlowDocument { PagePadding = new Thickness(0) };
            foreach (var line in _text.Split('\n'))
            {
                var run = new Run(line.TrimEnd('\r'));
                run.SetResourceReference(TextElement.ForegroundProperty, LogSeverityConverter.Severity(line) switch
                {
                    "ERROR" => "ToastErrorBorderBrush", "WARN" => "ToastWarningBorderBrush", "SUCCESS" => "GreenDarkBrush", _ => "InkBrush"
                });
                Document.Blocks.Add(new Paragraph(run) { Margin = new Thickness(0, 0, 0, 3) });
            }
        }
    }
}
