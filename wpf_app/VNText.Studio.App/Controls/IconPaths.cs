using System.Windows.Media;

namespace VNText.Studio.App.Controls;

public readonly record struct IconSpec(Geometry Geometry, bool Filled);

public static class IconPaths
{
    private static readonly Dictionary<string, IconSpec> _cache = new(StringComparer.OrdinalIgnoreCase);

    public static IconSpec Get(string name)
    {
        if (_cache.TryGetValue(name, out var spec))
            return spec;

        spec = name.ToLowerInvariant() switch
        {
            "extract" => Stroke(
                "M14,2 H6 a2,2 0 0 0 -2,2 v16 a2,2 0 0 0 2,2 h12 a2,2 0 0 0 2,-2 V8 Z",
                "M14,2 v6 h6",
                "M12,18 v-6",
                "m9,15 3,3 3,-3"),
            "translate" => Stroke(
                "M12,2 a10,10 0 1 0 0,20 a10,10 0 1 0 0,-20 Z",
                "M2,12 h20",
                "M12,2 a15.3,15.3 0 0 1 4,10 a15.3,15.3 0 0 1 -4,10 a15.3,15.3 0 0 1 -4,-10 a15.3,15.3 0 0 1 4,-10 Z"),
            "patch" => Stroke(
                "m12.83,2.18 2,5.82 H9.17 l2,-5.82 Z",
                "M5,8 h14",
                "M6,8 v12",
                "M18,8 v12",
                "M8,12 h8",
                "M8,16 h8"),
            "shield" => Stroke("M12,22 s8,-4 8,-10 V5 l-8,-3 -8,3 v7 c0,6 8,10 8,10 Z"),
            "stack" => Stroke(
                "M4,19.5 A2.5,2.5 0 0 1 6.5,17 H20",
                "M6.5,2 H20 v20 H6.5 A2.5,2.5 0 0 1 4,19.5 v-15 A2.5,2.5 0 0 1 6.5,2 Z"),
            "filter" => Stroke("M22,3 L2,3 10,12.46 10,19 14,21 14,12.46 22,3 Z"),
            "review" => Stroke(
                "M11,3 a8,8 0 1 0 0,16 a8,8 0 1 0 0,-16 Z",
                "m21,21 -4.3,-4.3"),
            "gear" => Stroke(
                "M12.22,2 h-.44 a2,2 0 0 0 -2,2 v.18 a2,2 0 0 1 -1,1.73 l-.43,.25 a2,2 0 0 1 -2,0 l-.15,-.08 a2,2 0 0 0 -2.73,.73 l-.22,.38 a2,2 0 0 0 .73,2.73 l.15,.1 a2,2 0 0 1 1,1.72 v.51 a2,2 0 0 1 -1,1.74 l-.15,.09 a2,2 0 0 0 -.73,2.73 l.22,.38 a2,2 0 0 0 2.73,.73 l.15,-.08 a2,2 0 0 1 2,0 l.43,.25 a2,2 0 0 1 1,1.73 V20 a2,2 0 0 0 2,2 h.44 a2,2 0 0 0 2,-2 v-.18 a2,2 0 0 1 1,-1.73 l.43,-.25 a2,2 0 0 1 2,0 l.15,.08 a2,2 0 0 0 2.73,-.73 l.22,-.39 a2,2 0 0 0 -.73,-2.73 l-.15,-.08 a2,2 0 0 1 -1,-1.74 v-.5 a2,2 0 0 1 1,-1.74 l.15,-.09 a2,2 0 0 0 .73,-2.73 l-.22,-.38 a2,2 0 0 0 -2.73,-.73 l-.15,.08 a2,2 0 0 1 -2,0 l-.43,-.25 a2,2 0 0 1 -1,-1.73 V4 a2,2 0 0 0 -2,-2 z",
                "M12,9 a3,3 0 1 0 0,6 a3,3 0 1 0 0,-6 Z"),
            "info" => Stroke(
                "M12,3 a9,9 0 1 0 0,18 a9,9 0 1 0 0,-18 Z",
                "M12,10.5 v5",
                "M12,6.6 a0.9,0.9 0 1 0 0,0.01 Z"),
            "folder_hero" => Stroke(
                "M3,9 h18",
                "M3,9 v10 q0,2 2,2 h14 q2,0 2,-2 V11 h-8 l-2,-2 H5 q-2,0 -2,2 z"),
            "folder_outline" or "game_folder" => Stroke(
                "M20,20 a2,2 0 0 0 2,-2 V8 a2,2 0 0 0 -2,-2 h-7.9 a2,2 0 0 1 -1.69,-0.9 L9.6,3.9 a2,2 0 0 0 -1.71,-0.9 H4 a2,2 0 0 0 -2,2 v13 a2,2 0 0 0 2,2 Z"),
            "paths" => Stroke(
                "M3,9 h18",
                "M3,9 v10 q0,2 2,2 h14 q2,0 2,-2 V11 h-8 l-2,-2 H5 q-2,0 -2,2 z"),
            "open" => Stroke(
                "M15,3 h6 v6",
                "M10,14 L21,3",
                "M18,13 v6 a2,2 0 0 1 -2,2 H5 a2,2 0 0 1 -2,-2 V8 a2,2 0 0 1 2,-2 h6"),
            "copy" => Stroke(
                "M8,4 h12 a2,2 0 0 1 2,2 v14 a2,2 0 0 1 -2,2 H8",
                "M4,8 h12 a2,2 0 0 1 2,2 v14 a2,2 0 0 1 -2,2 H4"),
            "chart" => Stroke("M3,3 v18 h18", "m19,9 -5,5 -4,-4 -3,3"),
            "journal" => Stroke(
                "M15,2 H6 a2,2 0 0 0 -2,2 v16 a2,2 0 0 0 2,2 h12 a2,2 0 0 0 2,-2 V7 Z",
                "M14,2 v4 a2,2 0 0 0 2,2 h4",
                "M10,9 H8",
                "M16,13 H8",
                "M16,17 H8"),
            "chevron_down" => Stroke("m6,9 6,6 6,-6"),
            "chevron_up" => Stroke("m18,15 -6,-6 -6,6"),
            "book" => Stroke(
                "M4,19.5 A2.5,2.5 0 0 1 6.5,17 H20",
                "M6.5,2 H20 v20 H6.5 A2.5,2.5 0 0 1 4,19.5 v-15 A2.5,2.5 0 0 1 6.5,2 Z",
                "M8,7 h8",
                "M8,11 h6"),
            "bulb" => Stroke(
                "M15,14 c.2,-1 .7,-1.7 1.5,-2.5 1,-.9 1.5,-2.2 1.5,-3.5 A6,6 0 0 0 6,8 c0,1 .2,2.2 1.5,3.5 .7,.7 1.3,1.5 1.5,2.5",
                "M9,18 h6",
                "M10,22 h4"),
            "globe" => Stroke(
                "M12,3.5 a8.5,8.5 0 1 0 0,17 a8.5,8.5 0 1 0 0,-17 Z",
                "M3.5,12 h17",
                "M12,3.5 a14,14 0 0 1 0,17",
                "M12,3.5 a14,14 0 0 0 0,17"),
            "moon" => Stroke("M12,3 a6,6 0 0 0 9,9 a7,7 0 1 1 -9,-9 Z"),
            "play" => Filled("M8,6.5 v11 l8,-5.5 Z"),
            _ => Stroke("M12,2 a10,10 0 1 0 0,20 a10,10 0 1 0 0,-20 Z"),
        };
        _cache[name] = spec;
        return spec;
    }

    private static IconSpec Stroke(params string[] figures)
    {
        var group = new GeometryGroup { FillRule = FillRule.Nonzero };
        foreach (var fig in figures)
            group.Children.Add(Geometry.Parse(fig));
        group.Freeze();
        return new IconSpec(group, false);
    }

    private static IconSpec Filled(string figure)
    {
        var g = Geometry.Parse(figure);
        g.Freeze();
        return new IconSpec(g, true);
    }
}
