using System.Collections.Generic;
using UnityEngine;

namespace TMPro
{
    public class TMP_FontAsset : Object
    {
        public static TMP_FontAsset CreateFontAsset(Font font) { throw null; }
        public bool TryAddCharacters(string characters, out string missingCharacters) { throw null; }
    }

    public class TMP_Settings : Object
    {
        public static TMP_Settings instance { get { throw null; } }
        public static List<TMP_FontAsset> fallbackFontAssets { get { throw null; } }
    }
}
