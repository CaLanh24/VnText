using System;
using System.Collections.Generic;

// Minimal behavioural stand-in for the Unity/TMP members the adapter uses (same names/signatures as the compile-only stubs).
namespace UnityEngine
{
    public enum RuntimeInitializeLoadType { AfterSceneLoad = 0, BeforeSceneLoad = 1 }

    [AttributeUsage(AttributeTargets.Method)]
    public class RuntimeInitializeOnLoadMethodAttribute : Attribute
    {
        public RuntimeInitializeOnLoadMethodAttribute(RuntimeInitializeLoadType loadType) { }
    }

    [Flags]
    public enum HideFlags { None = 0, DontUnloadUnusedAsset = 32 }

    public class Object
    {
        public string name { get; set; }
        public HideFlags hideFlags { get; set; }
        public bool Destroyed;

        // Unity semantics: a destroyed object compares equal to null.
        public static bool operator ==(Object x, Object y)
        {
            bool xNull = ReferenceEquals(x, null) || x.Destroyed;
            bool yNull = ReferenceEquals(y, null) || y.Destroyed;
            return xNull || yNull ? xNull && yNull : ReferenceEquals(x, y);
        }

        public static bool operator !=(Object x, Object y) { return !(x == y); }
        public override bool Equals(object obj) { return ReferenceEquals(this, obj); }
        public override int GetHashCode() { return base.GetHashCode(); }
    }

    public class Application { public static string dataPath; }

    public class Debug
    {
        public static List<string> Lines = new List<string>();
        public static void Log(object message) { Lines.Add("LOG " + message); }
        public static void LogWarning(object message) { Lines.Add("WARN " + message); }
        public static void LogError(object message) { Lines.Add("ERROR " + message); }
    }

    public sealed class Font : Object { public Font(string path) { name = path; } }
}

namespace UnityEngine.Events
{
    public delegate void UnityAction<T0, T1>(T0 arg0, T1 arg1);
}

namespace UnityEngine.SceneManagement
{
    public enum LoadSceneMode { Single = 0, Additive = 1 }

    public struct Scene { public string name { get; set; } }

    public class SceneManager
    {
        public static event UnityEngine.Events.UnityAction<Scene, LoadSceneMode> sceneLoaded;

        public static int Subscribers { get { return sceneLoaded == null ? 0 : sceneLoaded.GetInvocationList().Length; } }

        public static void Raise(string scene)
        {
            if (sceneLoaded != null) sceneLoaded(new Scene { name = scene }, LoadSceneMode.Single);
        }
    }
}

namespace TMPro
{
    public class TMP_FontAsset : UnityEngine.Object
    {
        public static int Created;

        public static TMP_FontAsset CreateFontAsset(UnityEngine.Font font)
        {
            Created++;
            return new TMP_FontAsset { name = "dyn" + Created };
        }

        public bool TryAddCharacters(string characters, out string missingCharacters, bool includeFontFeatures = false)
        {
            missingCharacters = "";
            return true;
        }
    }

    public class TMP_Settings : UnityEngine.Object
    {
        private static List<TMP_FontAsset> fallback = new List<TMP_FontAsset>();

        public static List<TMP_FontAsset> fallbackFontAssets { get { return fallback; } }

        // The game / TMP reloads its settings asset and its global fallback list is replaced.
        public static void Replace(List<TMP_FontAsset> list) { fallback = list; }
    }
}
