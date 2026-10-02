using System.Media;

namespace VNText.Studio.App.Services;

public static class UserFeedback
{
    public static void PlaySuccess()
    {
        try
        {
            SystemSounds.Asterisk.Play();
        }
        catch
        {
            // ignore — optional feedback only
        }
    }

    public static void PlayWarning()
    {
        try
        {
            SystemSounds.Exclamation.Play();
        }
        catch
        {
        }
    }

    public static void PlayError()
    {
        try
        {
            SystemSounds.Hand.Play();
        }
        catch
        {
        }
    }
}
