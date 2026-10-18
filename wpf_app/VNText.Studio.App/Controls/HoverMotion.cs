using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;

namespace VNText.Studio.App.Controls;

// Small, opt-in presentation effect; transforms never participate in layout.
public static class HoverMotion
{
    public static readonly DependencyProperty KindProperty = DependencyProperty.RegisterAttached(
        "Kind", typeof(string), typeof(HoverMotion), new PropertyMetadata(null, Changed));
    public static string? GetKind(DependencyObject target) => (string?)target.GetValue(KindProperty);
    public static void SetKind(DependencyObject target, string value) => target.SetValue(KindProperty, value);

    private static void Changed(DependencyObject target, DependencyPropertyChangedEventArgs args)
    {
        if (target is not FrameworkElement element || args.NewValue is not string kind) return;
        var scale = new ScaleTransform(1, 1);
        var translate = new TranslateTransform();
        var rotate = new RotateTransform();
        var transforms = new TransformGroup();
        transforms.Children.Add(scale); transforms.Children.Add(translate); transforms.Children.Add(rotate);
        element.RenderTransformOrigin = new Point(.5, .5); element.RenderTransform = transforms;
        element.MouseEnter += (_, _) =>
        {
            // Owner explicitly requests this short local movement even when the
            // host disables general client-area animations; other effects keep that policy.
            if (kind == "SettingsTab") { ScaleTab(scale, 1.025); return; }
            if (kind == "AboutCard") { MoveAboutCard(translate, -1); return; }
            if (!SystemParameters.ClientAreaAnimation)
            {
                // Keep the About hover state legible without animated motion.
                return;
            }
            if (kind == "Close")
            {
                var wiggle = new DoubleAnimationUsingKeyFrames { Duration = TimeSpan.FromMilliseconds(180) };
                wiggle.KeyFrames.Add(new LinearDoubleKeyFrame(-3, KeyTime.FromPercent(.2)));
                wiggle.KeyFrames.Add(new LinearDoubleKeyFrame(3, KeyTime.FromPercent(.5)));
                wiggle.KeyFrames.Add(new LinearDoubleKeyFrame(-1, KeyTime.FromPercent(.75)));
                wiggle.KeyFrames.Add(new LinearDoubleKeyFrame(0, KeyTime.FromPercent(1)));
                rotate.BeginAnimation(RotateTransform.AngleProperty, wiggle);
            }
            else
            {
                Animate(scale, ScaleTransform.ScaleXProperty, kind is "Card" or "AboutCard" ? 1 : 1.025);
                Animate(scale, ScaleTransform.ScaleYProperty, kind is "Card" or "AboutCard" ? 1 : 1.025);
                if (kind is "Card" or "AboutCard") Animate(translate, TranslateTransform.YProperty, kind == "AboutCard" ? -5 : -1.5);
            }
        };
        element.MouseLeave += (_, _) =>
        {
            if (kind == "SettingsTab") { ScaleTab(scale, 1); return; }
            if (kind == "AboutCard") { MoveAboutCard(translate, 0); return; }
            Animate(scale, ScaleTransform.ScaleXProperty, 1);
            Animate(scale, ScaleTransform.ScaleYProperty, 1);
            Animate(translate, TranslateTransform.YProperty, 0);
            Animate(rotate, RotateTransform.AngleProperty, 0);
        };
        element.Unloaded += (_, _) =>
        {
            scale.BeginAnimation(ScaleTransform.ScaleXProperty, null); scale.BeginAnimation(ScaleTransform.ScaleYProperty, null);
            translate.BeginAnimation(TranslateTransform.YProperty, null); rotate.BeginAnimation(RotateTransform.AngleProperty, null);
        };
    }
    private static void ScaleTab(ScaleTransform target, double value)
    {
        foreach (var property in new[] { ScaleTransform.ScaleXProperty, ScaleTransform.ScaleYProperty })
            target.BeginAnimation(property, new DoubleAnimation((double)target.GetValue(property), value, TimeSpan.FromMilliseconds(160))
            { EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut } }, HandoffBehavior.SnapshotAndReplace);
    }
    private static void MoveAboutCard(TranslateTransform target, double y) =>
        target.BeginAnimation(TranslateTransform.YProperty,
            new DoubleAnimation(target.Y, y, TimeSpan.FromMilliseconds(160))
            { EasingFunction = new CubicEase { EasingMode = EasingMode.EaseOut } },
            HandoffBehavior.SnapshotAndReplace);

    private static void Animate(Animatable target, DependencyProperty property, double value) =>
        target.BeginAnimation(property, new DoubleAnimation(value, TimeSpan.FromMilliseconds(SystemParameters.ClientAreaAnimation ? 110 : 0))
        { EasingFunction = new QuadraticEase { EasingMode = EasingMode.EaseOut } });
}
