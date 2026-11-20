using System;

namespace UnityEngine
{
    public enum RuntimeInitializeLoadType
    {
        AfterSceneLoad = 0,
        BeforeSceneLoad = 1,
        AfterAssembliesLoaded = 2,
        BeforeSplashScreen = 3,
        SubsystemRegistration = 4,
    }

    [AttributeUsage(AttributeTargets.Method)]
    public class RuntimeInitializeOnLoadMethodAttribute : Attribute
    {
        public RuntimeInitializeOnLoadMethodAttribute() { }
        public RuntimeInitializeOnLoadMethodAttribute(RuntimeInitializeLoadType loadType) { this.loadType = loadType; }
        public RuntimeInitializeLoadType loadType { get; }
    }

    [Flags]
    public enum HideFlags
    {
        None = 0,
        HideInHierarchy = 1,
        HideInInspector = 2,
        DontSaveInEditor = 4,
        NotEditable = 8,
        DontSaveInBuild = 16,
        DontUnloadUnusedAsset = 32,
        DontSave = 52,
        HideAndDontSave = 61,
    }

    public class Object
    {
        public string name { get; set; }
        public HideFlags hideFlags { get; set; }
        public static bool operator ==(Object x, Object y) { throw null; }
        public static bool operator !=(Object x, Object y) { throw null; }
    }

    public class Application
    {
        public static string dataPath { get { throw null; } }
    }

    public class Debug
    {
        public static void Log(object message) { throw null; }
        public static void LogWarning(object message) { throw null; }
        public static void LogError(object message) { throw null; }
    }
}

namespace UnityEngine.Events
{
    public delegate void UnityAction<T0, T1>(T0 arg0, T1 arg1);
}

namespace UnityEngine.SceneManagement
{
    public enum LoadSceneMode
    {
        Single = 0,
        Additive = 1,
    }

    public struct Scene
    {
        public string name { get { throw null; } }
    }

    public class SceneManager
    {
        public static event UnityEngine.Events.UnityAction<Scene, LoadSceneMode> sceneLoaded;
    }
}
