using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using VNText.Studio.App.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Effects;
using VNText.Studio.App.Services;
using VNText.Studio.App.ViewModels;

namespace VNText.Studio.App;

internal sealed class JournalWindow : Window
{
    private readonly AppJournalStore _store;
    private readonly MainViewModel _vm;
    private readonly ComboBox _files=new(){MinWidth=210}, _level=new(){Width=100}, _size=new(){Width=85};
    private readonly TextBox _query=new(){MinWidth=240}, _content=new(){IsReadOnly=true,AcceptsReturn=true,TextWrapping=TextWrapping.NoWrap,VerticalScrollBarVisibility=ScrollBarVisibility.Auto,HorizontalScrollBarVisibility=ScrollBarVisibility.Auto,FontFamily=new FontFamily("Courier New"),FontSize=12,Background=new SolidColorBrush(Color.FromRgb(15,23,42)),Foreground=new SolidColorBrush(Color.FromRgb(226,232,240)),BorderThickness=new Thickness(0),Padding=new Thickness(12,0,12,0)};
    private readonly ToggleButton _regex=new(){Content="Biểu thức chính quy",VerticalAlignment=VerticalAlignment.Center};
    private Button? _previousPage, _nextPage;
    private readonly TextBlock _pageSizeLabel=new(){VerticalAlignment=VerticalAlignment.Center,Margin=new Thickness(12,0,8,0)};
    private readonly TextBlock _status=new(){VerticalAlignment=VerticalAlignment.Center}, _modified=new(){VerticalAlignment=VerticalAlignment.Center};
    private int _page;
    private bool _loading;
    internal JournalWindow(MainWindow owner,MainViewModel vm)
    {
        _store=vm.JournalStore;_vm=vm;Owner=owner;Title="Nhật ký — Khắc phục lỗi";
        Width=956;Height=500;MaxWidth=Math.Max(600,owner.ActualWidth-30);MaxHeight=Math.Max(400,owner.ActualHeight-30);
        WindowStartupLocation=WindowStartupLocation.CenterOwner;WindowStyle=WindowStyle.None;ResizeMode=ResizeMode.NoResize;
        AllowsTransparency=true;Background=Brushes.Transparent;ShowInTaskbar=false;FontFamily=owner.FontFamily;FontSize=13;
        TextOptions.SetTextFormattingMode(this,TextFormattingMode.Display);
        KeyboardNavigation.SetTabNavigation(this,KeyboardNavigationMode.Cycle);
        Brush B(string key)=>(Brush)owner.FindResource(key);
        Foreground=B("InkBrush");Resources["JournalHoverBrush"]=new SolidColorBrush(Color.FromRgb(240,246,252));
        foreach(var combo in new[]{_files,_level,_size})
        {
            combo.Style=(Style)owner.FindResource("SettingsPreferenceCombo");combo.Background=B("SurfaceBrush");
            combo.ItemTemplate=(DataTemplate)System.Windows.Markup.XamlReader.Parse("""
            <DataTemplate xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"><TextBlock Text="{Binding}" FontFamily="Segoe UI" FontSize="12" FontWeight="Normal"/></DataTemplate>
            """);
        }
        _files.MinWidth=0;_files.Width=228;_files.Height=24;_files.FontSize=12;_level.MinWidth=0;_size.MinWidth=0;_level.Width=110;_level.Height=28;_level.FontSize=12;_size.Width=92;_size.Height=28;_size.FontSize=12;_query.Style=(Style)owner.FindResource("FieldTextBoxStyle");
        _query.MaxLength=500;_query.Height=36;_query.Background=B("SurfaceBrush");_query.BorderBrush=B("LineBrush");
        var actionStyle=(Style)System.Windows.Markup.XamlReader.Parse("""
        <Style xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" TargetType="Button">
          <Setter Property="Background" Value="{DynamicResource SurfaceBrush}"/><Setter Property="Foreground" Value="{DynamicResource InkBrush}"/>
          <Setter Property="FontSize" Value="13"/><Setter Property="FontWeight" Value="Normal"/><Setter Property="Cursor" Value="Hand"/>
          <Setter Property="Template"><Setter.Value><ControlTemplate TargetType="Button"><Border x:Name="Surface" CornerRadius="12" Background="{TemplateBinding Background}" BorderBrush="{DynamicResource LineBrush}" BorderThickness="1"><Border.RenderTransform><TranslateTransform/></Border.RenderTransform><Border.Effect><DropShadowEffect BlurRadius="6" ShadowDepth="2" Opacity=".08"/></Border.Effect><ContentPresenter Margin="{TemplateBinding Padding}" VerticalAlignment="Center" HorizontalAlignment="Center"/></Border><ControlTemplate.Triggers><Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Surface" Property="Background" Value="{DynamicResource JournalHoverBrush}"/><Setter TargetName="Surface" Property="BorderBrush" Value="#C5D7EC"/><Trigger.EnterActions><BeginStoryboard><Storyboard><DoubleAnimation Storyboard.TargetName="Surface" Storyboard.TargetProperty="(UIElement.RenderTransform).(TranslateTransform.Y)" To="-1" Duration="0:0:0.14"/></Storyboard></BeginStoryboard></Trigger.EnterActions><Trigger.ExitActions><BeginStoryboard><Storyboard><DoubleAnimation Storyboard.TargetName="Surface" Storyboard.TargetProperty="(UIElement.RenderTransform).(TranslateTransform.Y)" To="0" Duration="0:0:0.14"/></Storyboard></BeginStoryboard></Trigger.ExitActions></Trigger><Trigger Property="IsPressed" Value="True"><Setter TargetName="Surface" Property="Opacity" Value=".75"/></Trigger><Trigger Property="IsEnabled" Value="False"><Setter Property="Opacity" Value=".4"/></Trigger></ControlTemplate.Triggers></ControlTemplate></Setter.Value></Setter>
        </Style>
        """);
        var regexStyle=(Style)System.Windows.Markup.XamlReader.Parse("""
        <Style xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation" xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml" TargetType="ToggleButton">
          <Setter Property="Foreground" Value="{DynamicResource InkBrush}"/><Setter Property="Background" Value="{DynamicResource SurfaceBrush}"/>
          <Setter Property="Template"><Setter.Value><ControlTemplate TargetType="ToggleButton"><Border x:Name="Surface" CornerRadius="12" Background="{TemplateBinding Background}" BorderBrush="{DynamicResource LineBrush}" BorderThickness="1"><Border.RenderTransform><TranslateTransform/></Border.RenderTransform><Border.Effect><DropShadowEffect BlurRadius="5" ShadowDepth="2" Opacity=".06"/></Border.Effect><ContentPresenter Margin="14,7" VerticalAlignment="Center" HorizontalAlignment="Center"/></Border><ControlTemplate.Triggers><Trigger Property="IsMouseOver" Value="True"><Setter TargetName="Surface" Property="Background" Value="{DynamicResource JournalHoverBrush}"/><Setter TargetName="Surface" Property="BorderBrush" Value="#C5D7EC"/><Trigger.EnterActions><BeginStoryboard><Storyboard><DoubleAnimation Storyboard.TargetName="Surface" Storyboard.TargetProperty="(UIElement.RenderTransform).(TranslateTransform.Y)" To="-1" Duration="0:0:0.14"/></Storyboard></BeginStoryboard></Trigger.EnterActions><Trigger.ExitActions><BeginStoryboard><Storyboard><DoubleAnimation Storyboard.TargetName="Surface" Storyboard.TargetProperty="(UIElement.RenderTransform).(TranslateTransform.Y)" To="0" Duration="0:0:0.14"/></Storyboard></BeginStoryboard></Trigger.ExitActions></Trigger><Trigger Property="IsChecked" Value="True"><Setter TargetName="Surface" Property="Background" Value="{DynamicResource BlueSoftBrush}"/><Setter TargetName="Surface" Property="BorderBrush" Value="#8098EE"/><Setter Property="Foreground" Value="{DynamicResource InkBrush}"/></Trigger></ControlTemplate.Triggers></ControlTemplate></Setter.Value></Setter>
        </Style>
        """);
        _regex.Style=regexStyle;_regex.FontSize=13;_regex.Height=36;
        FrameworkElement IconLabel(string icon,string text)
        {
            var row=new StackPanel{Orientation=Orientation.Horizontal};
            row.Children.Add(new IconView{Icon=icon,Width=14,Height=14,StrokeBrush=B("MutedBrush"),Margin=new Thickness(0,0,6,0)});
            row.Children.Add(new TextBlock{Text=text,VerticalAlignment=VerticalAlignment.Center,TextTrimming=TextTrimming.CharacterEllipsis});return row;
        }
        Button Button(string label,Action action,bool primary=false)
        {
            var button=new Button {Content=label,Style=(Style)owner.FindResource(primary ? "PrimaryButton" : "OutlineButton"),Height=38,Margin=new Thickness(12,0,0,0),Padding=new Thickness(16,7,16,7)};
            if(primary){var labelRow=IconLabel("copy",label);((IconView)((StackPanel)labelRow).Children[0]).StrokeBrush=Brushes.White;button.Content=labelRow;}
            button.Click+=(_,_)=>Safe(action);return button;
        }
        var surface=new Border{Margin=new Thickness(AppDialogWindow.CardMargin),CornerRadius=new CornerRadius(AppDialogWindow.CardRadius),Background=B("SurfaceBrush"),Effect=new DropShadowEffect{BlurRadius=32,ShadowDepth=9,Opacity=.25}};
        var grid=new Grid();surface.Child=grid;Content=surface;
        if(UiAppearance.Scaled){surface.LayoutTransform=new ScaleTransform(UiAppearance.Scale,UiAppearance.Scale);Width*=UiAppearance.Scale;Height*=UiAppearance.Scale;}
        grid.RowDefinitions.Add(new(){Height=GridLength.Auto});grid.RowDefinitions.Add(new());grid.RowDefinitions.Add(new(){Height=GridLength.Auto});
        var header=new DockPanel{Margin=new Thickness(28,24,28,24)};
        var close=Button("×",Close);close.Content=new TextBlock{Text="×",FontSize=20,VerticalAlignment=VerticalAlignment.Center};close.Style=(Style)owner.FindResource("DialogCloseButton");close.Width=32;close.Height=32;close.ToolTip="Đóng (Esc)";System.Windows.Automation.AutomationProperties.SetName(close,"Đóng Nhật ký");DockPanel.SetDock(close,Dock.Right);header.Children.Add(close);
        header.Children.Add(new TextBlock{Text="khắc phục lỗi",FontSize=20,FontWeight=FontWeights.Bold,Foreground=B("InkBrush"),VerticalAlignment=VerticalAlignment.Center});
        grid.Children.Add(new Border{Child=header,BorderBrush=B("LineBrush"),BorderThickness=new Thickness(0,0,0,1)});
        var body=new Grid{Margin=new Thickness(28,28,28,28)};Grid.SetRow(body,1);grid.Children.Add(body);
        for(var i=0;i<3;i++)body.RowDefinitions.Add(new(){Height=GridLength.Auto});body.RowDefinitions.Add(new());
        var fileRow=new StackPanel{Orientation=Orientation.Horizontal,Margin=new Thickness(0,0,0,12)};body.Children.Add(fileRow);
        var fileChip=new StackPanel{Orientation=Orientation.Horizontal};fileChip.Children.Add(new IconView{Icon="journal",Width=14,Height=14,StrokeBrush=B("MutedBrush"),Margin=new Thickness(8,0,6,0)});fileChip.Children.Add(_files);
        fileRow.Children.Add(new Border{Child=fileChip,Background=B("SubtlePanelBrush"),CornerRadius=new CornerRadius(5),Padding=new Thickness(0,3,6,3)});
        var folder=Button("",()=>Process.Start(new ProcessStartInfo(_store.Root){UseShellExecute=true}));folder.Content=IconLabel("folder_outline",_store.Root);folder.ToolTip=_store.Root;folder.Width=268;folder.Height=30;folder.Padding=new Thickness(10,3,10,3);folder.Background=B("SubtlePanelBrush");fileRow.Children.Add(folder);
        var modifiedChip=new StackPanel{Orientation=Orientation.Horizontal};modifiedChip.Children.Add(new System.Windows.Shapes.Path{Data=Geometry.Parse("M20 7 A9 9 0 1 0 21 14 M20 2 V7 H15"),Stretch=Stretch.Uniform,Width=14,Height=14,Stroke=B("MutedBrush"),StrokeThickness=1.4,Margin=new Thickness(0,0,6,0)});modifiedChip.Children.Add(_modified);
        fileRow.Children.Add(new Border{Child=modifiedChip,Background=B("SubtlePanelBrush"),CornerRadius=new CornerRadius(5),Padding=new Thickness(10,6,10,6),Margin=new Thickness(8,0,0,0)});_modified.FontSize=12;
        var options=new StackPanel{Orientation=Orientation.Horizontal,HorizontalAlignment=HorizontalAlignment.Right,Margin=new Thickness(0,0,0,12)};Grid.SetRow(options,1);body.Children.Add(options);
        _level.ItemsSource=new[]{"Tất cả","Thông tin","Cảnh báo","Lỗi","Debug"};_level.SelectedIndex=0;
        _size.ItemsSource=new[]{100,200,500,1000};_size.SelectedItem=200;
        options.Children.Add(new TextBlock{Text="Mức",VerticalAlignment=VerticalAlignment.Center,Margin=new Thickness(0,0,8,0)});options.Children.Add(_level);
        options.Children.Add(_pageSizeLabel);options.Children.Add(_size);
        var previousPage=_previousPage=Button("‹",()=>{_page=Math.Max(0,_page-1);Render();});var nextPage=_nextPage=Button("›",()=>{_page++;Render();});
        foreach(var button in new[]{previousPage,nextPage}){button.Width=30;button.MinWidth=30;button.Padding=new Thickness(0);options.Children.Add(button);}
        _status.Visibility=Visibility.Collapsed;options.Children.Add(_status);
        var search=new Grid{Margin=new Thickness(0,0,0,10)};Grid.SetRow(search,2);body.Children.Add(search);
        search.ColumnDefinitions.Add(new());search.ColumnDefinitions.Add(new(){Width=GridLength.Auto});search.ColumnDefinitions.Add(new(){Width=GridLength.Auto});
        _query.ToolTip="Tìm trong nhật ký";search.Children.Add(_query);
        var placeholder=new TextBlock{Text="Tìm trong nhật ký",IsHitTestVisible=false,Foreground=B("MutedBrush"),Margin=new Thickness(12,0,0,0),VerticalAlignment=VerticalAlignment.Center};search.Children.Add(placeholder);
        _query.TextChanged+=(_,_)=>placeholder.Visibility=_query.Text.Length==0 ? Visibility.Visible : Visibility.Collapsed;
        _regex.Margin=new Thickness(12,0,8,0);Grid.SetColumn(_regex,1);search.Children.Add(_regex);
        var reset=Button("Xóa",()=>_query.Clear());reset.IsEnabled=false;_query.TextChanged+=(_,_)=>reset.IsEnabled=_query.Text.Length>0;Grid.SetColumn(reset,2);search.Children.Add(reset);
        var terminal=new Border{Background=_content.Background,CornerRadius=new CornerRadius(9),ClipToBounds=true,Child=_content};Grid.SetRow(terminal,3);body.Children.Add(terminal);terminal.SizeChanged+=(_,_)=>terminal.Clip=new RectangleGeometry(new Rect(0,0,terminal.ActualWidth,terminal.ActualHeight),9,9);
        var footer=new StackPanel{Orientation=Orientation.Horizontal,HorizontalAlignment=HorizontalAlignment.Right,Margin=new Thickness(20,20,28,20)};
        var footerSurface=new Border{Child=footer,Background=B("SubtlePanelBrush"),CornerRadius=new CornerRadius(0,0,AppDialogWindow.CardRadius,AppDialogWindow.CardRadius),BorderBrush=B("LineBrush"),BorderThickness=new Thickness(0,1,0,0)};Grid.SetRow(footerSurface,2);grid.Children.Add(footerSurface);
        footer.Children.Add(Button("Đóng",Close));footer.Children.Add(Button("Làm mới",Refresh));
        footer.Children.Add(Button("Xóa",()=>
        {
            if(_files.SelectedItem is string name && AppDialogService.Show($"Xóa tệp nhật ký {name}?","Nhật ký",MessageBoxButton.YesNo,MessageBoxImage.Question,this)==MessageBoxResult.Yes){_store.Clear(name);Refresh();}
        }));
        footer.Children.Add(Button("Mở nhật ký",()=>
        {
            if(_files.SelectedItem is string name){var info=new ProcessStartInfo("notepad.exe");info.ArgumentList.Add(_store.FilePath(name));Process.Start(info);}
        }));
        footer.Children.Add(Button("Chép vị trí tệp",()=>{if(_files.SelectedItem is string name)Clipboard.SetText(_store.FilePath(name));}));
        footer.Children.Add(Button("Chép thông tin lỗi",()=>Clipboard.SetText($"VNText Studio {vm.Version}\n{System.Runtime.InteropServices.RuntimeInformation.OSDescription}\n.NET {Environment.Version}\nLog: {_files.SelectedItem}\n\n{(_files.SelectedItem is string file ? _store.Read(file) : _content.Text)}"),true));
        var footerWidths=new[]{68d,88d,60d,116d,122d,172d};
        for(var i=0;i<footer.Children.Count;i++) if(footer.Children[i] is Button item){item.Width=footerWidths[i];item.Padding=new Thickness(8,7,8,7);}
        _files.SelectionChanged+=(_,_)=>{_page=0;Safe(Render);};_level.SelectionChanged+=(_,_)=>{_page=0;Safe(Render);};_size.SelectionChanged+=(_,_)=>{_page=0;Safe(Render);};
        _query.TextChanged+=(_,_)=>{_page=0;Safe(Render);};_regex.Checked+=(_,_)=>Safe(Render);_regex.Unchecked+=(_,_)=>Safe(Render);
        var previous=owner.Effect;Border? overlay=null;var panel=owner.Content as Panel;
        Loaded+=(_,_)=>
        {
            owner.Effect=new BlurEffect{Radius=AppDialogWindow.BackdropBlur};
            if(panel is not null){overlay=new Border{Background=new SolidColorBrush(AppDialogWindow.BackdropColor),IsHitTestVisible=false};Grid.SetRowSpan(overlay,20);Grid.SetColumnSpan(overlay,20);Panel.SetZIndex(overlay,int.MaxValue);panel.Children.Add(overlay);}
            Safe(Refresh);
        };
        Closed+=(_,_)=>{if(overlay is not null)panel?.Children.Remove(overlay);owner.Effect=previous;};
        PreviewKeyDown+=(_,e)=>{if(e.Key==Key.Escape){Close();e.Handled=true;}};
    }
    private void Safe(Action action)
    {
        try{action();}catch(Exception ex){_status.Text=ex.Message;_content.Text="Không đọc được nhật ký: "+ex.Message;}
    }
    private void Refresh()
    {
        var selected=_files.SelectedItem as string;_loading=true;
        try{_files.ItemsSource=_store.Files();_files.SelectedItem=selected;if(_files.SelectedIndex<0 && _files.Items.Count>0)_files.SelectedIndex=0;}
        finally{_loading=false;}
        Render();
    }
    private void Render()
    {
        if(_loading)return;
        if(_files.SelectedItem is not string file){_content.Text=_vm.JournalWriteFailed ? string.Join(Environment.NewLine,_vm.LogLines) : "";_status.Text="Chưa có tệp nhật ký";return;}
        var levels=new[]{"ALL","INFO","WARN","ERROR","DEBUG"};var size=_size.SelectedItem is int value ? value : 200;
        _pageSizeLabel.Text=$"{size} bản ghi/trang";
        var lines=AppJournalStore.Filter(_store.Read(file),_query.Text,levels[Math.Max(0,_level.SelectedIndex)],_regex.IsChecked==true);
        var pages=Math.Max(1,(lines.Length+size-1)/size);_page=Math.Clamp(_page,0,pages-1);
        if(_previousPage is not null){_previousPage.Visibility=pages>1?Visibility.Visible:Visibility.Collapsed;_previousPage.IsEnabled=_page>0;}
        if(_nextPage is not null){_nextPage.Visibility=pages>1?Visibility.Visible:Visibility.Collapsed;_nextPage.IsEnabled=_page<pages-1;}
        var start=Math.Max(0,lines.Length-(_page+1)*size);
        _content.Text=string.Join(Environment.NewLine,lines.Skip(start).Take(Math.Min(size,lines.Length-_page*size)));_content.ScrollToEnd();
        _status.Text=$"{lines.Length} bản ghi · {_page+1}/{pages}";_modified.Text=UiText.FormatLocalTime(File.GetLastWriteTime(_store.FilePath(file)));
    }
}
