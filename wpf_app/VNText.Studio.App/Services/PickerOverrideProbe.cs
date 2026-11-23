#if DEV_PROBES
using System.Text.Json;

namespace VNText.Studio.App.Services;

/// <summary>
/// DEV_PROBES-only: lets a test run answer the font and image-spec file pickers without a Windows dialog.  The probe reads
/// <c>VNTEXT_PROBE_PICKS</c>, a JSON object such as {"font":"C:\x.ttf","imageSpec":"C:\y.json"}; a missing key falls back to the real dialog.
/// This file is excluded from every non-probe build (Services\*Probe.cs), and its call sites sit inside #if DEV_PROBES, so a release carries no trace of it.
/// </summary>
internal static class PickerOverrideProbe
{
    public static bool TryResolve(string kind, out string path)
    {
        path = "";
        var raw = Environment.GetEnvironmentVariable("VNTEXT_PROBE_PICKS");
        if (string.IsNullOrWhiteSpace(raw)) return false;
        try
        {
            using var document = JsonDocument.Parse(raw);
            if (document.RootElement.ValueKind == JsonValueKind.Object &&
                document.RootElement.TryGetProperty(kind, out var value) && value.ValueKind == JsonValueKind.String)
            {
                path = value.GetString() ?? "";
                return path.Length > 0;
            }
        }
        catch (JsonException) { }
        return false;
    }
}
#endif
