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

    public class Object
    {
        public string name { get; set; }
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
