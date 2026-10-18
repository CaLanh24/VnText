using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
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
    private readonly TextBox _query=new(){MinWidth=240}, _content=new(){IsReadOnly=true,AcceptsReturn=true,TextWrapping=TextWrapping.NoWrap,VerticalScrollBarVisibility=ScrollBarVisibility.Auto,HorizontalScrollBarVisibility=ScrollBarVisibility.Auto,FontFamily=new FontFamily("Consolas"),FontSize=11,Background=new SolidColorBrush(Color.FromRgb(15,23,42)),Foreground=new SolidColorBrush(Color.FromRgb(226,232,240)),BorderThickness=new Thickness(0),Padding=new Thickness(10)};
    private readonly CheckBox _regex=new(){Content="Biểu thức chính quy",VerticalAlignment=VerticalAlignment.Center};
    private readonly TextBlock _status=new(){VerticalAlignment=VerticalAlignment.Center}, _modified=new(){VerticalAlignment=VerticalAlignment.Center};
    private int _page;
    private bool _loading;
    internal JournalWindow(MainWindow owner,MainViewModel vm)
    {
        _store=vm.JournalStore;_vm=vm;Owner=owner;Title="Nhật ký — Khắc phục lỗi";
        Width=960;Height=500;MaxWidth=Math.Max(600,owner.ActualWidth-30);MaxHeight=Math.Max(400,owner.ActualHeight-30);
        WindowStartupLocation=WindowStartupLocation.CenterOwner;WindowStyle=WindowStyle.None;ResizeMode=ResizeMode.NoResize;
        AllowsTransparency=true;Background=Brushes.Transparent;ShowInTaskbar=false;FontFamily=owner.FontFamily;FontSize=13;
        KeyboardNavigation.SetTabNavigation(this,KeyboardNavigationMode.Cycle);
        Brush B(string key)=>(Brush)owner.FindResource(key);
        Foreground=B("InkBrush");
        foreach(var combo in new[]{_files,_level,_size}) combo.Style=(Style)owner.FindResource("SettingsPreferenceCombo");
        _files.Width=230;_query.Style=(Style)owner.FindResource("FieldTextBoxStyle");
        _query.MaxLength=500;
        Button Button(string label,Action action,bool primary=false)
        {
            var button=new Button {Content=label,Style=(Style)owner.FindResource(primary ? "GuiBluePrimaryButtonStyle" : "SecondaryButton"),Margin=new Thickness(4,0,0,0),Padding=new Thickness(12,7,12,7)};
            button.Click+=(_,_)=>Safe(action);return button;
        }
        var surface=new Border{Margin=new Thickness(18),CornerRadius=new CornerRadius(18),Background=B("SurfaceBrush"),Effect=new DropShadowEffect{BlurRadius=32,ShadowDepth=9,Opacity=.25}};
        var grid=new Grid();surface.Child=grid;Content=surface;
        grid.RowDefinitions.Add(new(){Height=GridLength.Auto});grid.RowDefinitions.Add(new());grid.RowDefinitions.Add(new(){Height=GridLength.Auto});
        var header=new DockPanel{Margin=new Thickness(24,24,24,24)};
        var close=Button("×",Close);close.Style=(Style)owner.FindResource("GhostButton");close.Width=28;close.Height=28;close.MinWidth=28;close.Padding=new Thickness(0);close.BorderThickness=new Thickness(0);DockPanel.SetDock(close,Dock.Right);header.Children.Add(close);
        header.Children.Add(new TextBlock{Text="Khắc phục lỗi",FontSize=18,FontWeight=FontWeights.Bold,Foreground=B("InkBrush"),VerticalAlignment=VerticalAlignment.Center});
        grid.Children.Add(new Border{Child=header,BorderBrush=B("LineBrush"),BorderThickness=new Thickness(0,0,0,1)});
        var body=new Grid{Margin=new Thickness(24,24,24,20)};Grid.SetRow(body,1);grid.Children.Add(body);
        for(var i=0;i<3;i++)body.RowDefinitions.Add(new(){Height=GridLength.Auto});body.RowDefinitions.Add(new());
        var fileRow=new WrapPanel{Margin=new Thickness(0,0,0,20)};body.Children.Add(fileRow);
        fileRow.Children.Add(_files);fileRow.Children.Add(Button("Mở thư mục",()=>Process.Start(new ProcessStartInfo(_store.Root){UseShellExecute=true})));
        fileRow.Children.Add(_modified);
        var options=new DockPanel{Margin=new Thickness(0,0,0,10)};Grid.SetRow(options,1);body.Children.Add(options);
        _level.ItemsSource=new[]{"Tất cả","Thông tin","Cảnh báo","Lỗi","Debug"};_level.SelectedIndex=0;
        _size.ItemsSource=new[]{100,200,500,1000};_size.SelectedItem=200;
        options.Children.Add(new TextBlock{Text="Mức",VerticalAlignment=VerticalAlignment.Center,Margin=new Thickness(0,0,8,0)});options.Children.Add(_level);
        options.Children.Add(new TextBlock{Text="Bản ghi/trang",VerticalAlignment=VerticalAlignment.Center,Margin=new Thickness(16,0,8,0)});options.Children.Add(_size);
        var previousPage=Button("‹",()=>{_page=Math.Max(0,_page-1);Render();});var nextPage=Button("›",()=>{_page++;Render();});
        foreach(var button in new[]{previousPage,nextPage}){button.Width=30;button.MinWidth=30;button.Padding=new Thickness(0);options.Children.Add(button);}
        _status.Margin=new Thickness(12,0,0,0);options.Children.Add(_status);
        var search=new Grid{Margin=new Thickness(0,0,0,10)};Grid.SetRow(search,2);body.Children.Add(search);
        search.ColumnDefinitions.Add(new());search.ColumnDefinitions.Add(new(){Width=GridLength.Auto});search.ColumnDefinitions.Add(new(){Width=GridLength.Auto});
        _query.ToolTip="Tìm trong nhật ký";search.Children.Add(_query);
        var placeholder=new TextBlock{Text="Tìm trong nhật ký",IsHitTestVisible=false,Foreground=B("MutedBrush"),Margin=new Thickness(12,0,0,0),VerticalAlignment=VerticalAlignment.Center};search.Children.Add(placeholder);
        _query.TextChanged+=(_,_)=>placeholder.Visibility=_query.Text.Length==0 ? Visibility.Visible : Visibility.Collapsed;
        _regex.Margin=new Thickness(12,0,8,0);Grid.SetColumn(_regex,1);search.Children.Add(_regex);
        var reset=Button("Xóa tìm kiếm",()=>_query.Clear());Grid.SetColumn(reset,2);search.Children.Add(reset);
        var terminal=new Border{Background=_content.Background,CornerRadius=new CornerRadius(10),ClipToBounds=true,Child=_content};Grid.SetRow(terminal,3);body.Children.Add(terminal);
        var footer=new StackPanel{Orientation=Orientation.Horizontal,HorizontalAlignment=HorizontalAlignment.Right,Margin=new Thickness(20,16,24,18)};
        var footerSurface=new Border{Child=footer,Background=B("SubtlePanelBrush"),CornerRadius=new CornerRadius(0,0,18,18),BorderBrush=B("LineBrush"),BorderThickness=new Thickness(0,1,0,0)};Grid.SetRow(footerSurface,2);grid.Children.Add(footerSurface);
        footer.Children.Add(Button("Đóng",Close));footer.Children.Add(Button("Làm mới",Refresh));
        footer.Children.Add(Button("Xóa",()=>
        {
            if(_files.SelectedItem is string name && MessageBox.Show(this,$"Xóa tệp nhật ký {name}?","Nhật ký",MessageBoxButton.YesNo,MessageBoxImage.Question)==MessageBoxResult.Yes){_store.Clear(name);Refresh();}
        }));
        footer.Children.Add(Button("Mở nhật ký",()=>
        {
            if(_files.SelectedItem is string name){var info=new ProcessStartInfo("notepad.exe");info.ArgumentList.Add(_store.FilePath(name));Process.Start(info);}
        }));
        footer.Children.Add(Button("Copy vị trí tệp",()=>{if(_files.SelectedItem is string name)Clipboard.SetText(_store.FilePath(name));}));
        footer.Children.Add(Button("Copy khắc phục lỗi",()=>Clipboard.SetText($"VNText Studio {vm.Version}\n{System.Runtime.InteropServices.RuntimeInformation.OSDescription}\n.NET {Environment.Version}\nLog: {_files.SelectedItem}\n\n{(_files.SelectedItem is string file ? _store.Read(file) : _content.Text)}"),true));
        _files.SelectionChanged+=(_,_)=>{_page=0;Safe(Render);};_level.SelectionChanged+=(_,_)=>{_page=0;Safe(Render);};_size.SelectionChanged+=(_,_)=>{_page=0;Safe(Render);};
        _query.TextChanged+=(_,_)=>{_page=0;Safe(Render);};_regex.Checked+=(_,_)=>Safe(Render);_regex.Unchecked+=(_,_)=>Safe(Render);
        var previous=owner.Effect;Border? overlay=null;var panel=owner.Content as Panel;
        Loaded+=(_,_)=>
        {
            owner.Effect=new BlurEffect{Radius=5};
            if(panel is not null){overlay=new Border{Background=new SolidColorBrush(Color.FromArgb(110,15,23,42)),IsHitTestVisible=false};Grid.SetRowSpan(overlay,20);Grid.SetColumnSpan(overlay,20);Panel.SetZIndex(overlay,int.MaxValue);panel.Children.Add(overlay);}
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
        var lines=AppJournalStore.Filter(_store.Read(file),_query.Text,levels[Math.Max(0,_level.SelectedIndex)],_regex.IsChecked==true);
        var pages=Math.Max(1,(lines.Length+size-1)/size);_page=Math.Clamp(_page,0,pages-1);
        var start=Math.Max(0,lines.Length-(_page+1)*size);
        _content.Text=string.Join(Environment.NewLine,lines.Skip(start).Take(Math.Min(size,lines.Length-_page*size)));_content.ScrollToEnd();
        _status.Text=$"{lines.Length} bản ghi · {_page+1}/{pages}";_modified.Text="  "+File.GetLastWriteTime(_store.FilePath(file)).ToString("g");
    }
}
