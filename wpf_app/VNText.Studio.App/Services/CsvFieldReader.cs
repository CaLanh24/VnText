using System.IO;
using System.Text;

namespace VNText.Studio.App.Services;

internal static class CsvFieldReader
{
    public static IEnumerable<string[]> ReadRecords(TextReader reader)
    {
        var fields = new List<string>();
        var current = new StringBuilder();
        var inQuotes = false;
        var hasContent = false;

        while (true)
        {
            var value = reader.Read();
            if (value < 0)
                break;

            var ch = (char)value;
            if (inQuotes)
            {
                if (ch == '"')
                {
                    if (reader.Peek() == '"')
                    {
                        reader.Read();
                        current.Append('"');
                    }
                    else
                    {
                        inQuotes = false;
                    }
                }
                else
                {
                    current.Append(ch);
                }

                hasContent = true;
                continue;
            }

            if (ch == '"')
            {
                inQuotes = true;
                hasContent = true;
            }
            else if (ch == ',')
            {
                fields.Add(current.ToString());
                current.Clear();
                hasContent = true;
            }
            else if (ch == '\r' || ch == '\n')
            {
                if (ch == '\r' && reader.Peek() == '\n')
                    reader.Read();

                fields.Add(current.ToString());
                current.Clear();
                if (hasContent || fields.Any(static field => field.Length > 0))
                    yield return fields.ToArray();

                fields.Clear();
                hasContent = false;
            }
            else
            {
                current.Append(ch);
                hasContent = true;
            }
        }

        if (hasContent || fields.Count > 0 || current.Length > 0)
        {
            fields.Add(current.ToString());
            yield return fields.ToArray();
        }
    }

    public static string[] ParseLine(string line)
    {
        var fields = new List<string>();
        var current = new StringBuilder();
        var inQuotes = false;
        for (var i = 0; i < line.Length; i++)
        {
            var ch = line[i];
            if (inQuotes)
            {
                if (ch == '"')
                {
                    if (i + 1 < line.Length && line[i + 1] == '"')
                    {
                        current.Append('"');
                        i++;
                    }
                    else
                    {
                        inQuotes = false;
                    }
                }
                else
                {
                    current.Append(ch);
                }
            }
            else if (ch == '"')
            {
                inQuotes = true;
            }
            else if (ch == ',')
            {
                fields.Add(current.ToString());
                current.Clear();
            }
            else
            {
                current.Append(ch);
            }
        }
        fields.Add(current.ToString());
        return fields.ToArray();
    }
}
