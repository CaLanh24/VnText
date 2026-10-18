using System.IO;
using System.Text;
using System.Text.RegularExpressions;

namespace VNText.Studio.App.Services;

internal sealed class AppJournalStore
{
    internal const long MaxFileBytes = 1024 * 1024;
    private static readonly Regex OwnedName = new(@"^app\.log\.\d{4}-\d{2}-\d{2}(?:\.\d{2})?$",RegexOptions.CultureInvariant);
    private readonly object _gate = new();
    internal string Root { get; }
    internal AppJournalStore(string root) { Root=Path.GetFullPath(root); }
    private void Check(string path)
    {
        var node = new DirectoryInfo(Path.GetDirectoryName(path)!);
        for(;node is not null;node=node.Parent)
            if(node.Exists && (node.Attributes & FileAttributes.ReparsePoint)!=0) throw new IOException("Thư mục nhật ký không được qua liên kết.");
        if(File.Exists(path) && (File.GetAttributes(path)&FileAttributes.ReparsePoint)!=0) throw new IOException("Tệp nhật ký không được là liên kết.");
    }
    internal string FilePath(string name)
    {
        if(!OwnedName.IsMatch(name)) throw new IOException("Tên tệp nhật ký không hợp lệ.");
        var path=Path.Combine(Root,name);Check(path);return path;
    }
    internal string[] Files()
    {
        Check(Path.Combine(Root,"placeholder"));
        return Directory.Exists(Root) ? Directory.EnumerateFiles(Root).Select(Path.GetFileName).Where(n=>n is not null && OwnedName.IsMatch(n)).Select(n=>n!).OrderDescending(StringComparer.Ordinal).Take(30).ToArray() : [];
    }
    internal void Append(string message)
    {
        lock(_gate)
        {
            var text=message.Length>4000 ? message[..4000] : message;
            var line=$"{DateTimeOffset.Now:yyyy-MM-dd HH:mm:ss.fff zzz} {Level(text)} {text.Replace("\r","").Replace("\n"," ↵ ")}{Environment.NewLine}";
            var bytes=Encoding.UTF8.GetBytes(line);
            Check(Path.Combine(Root,"placeholder"));Directory.CreateDirectory(Root);
            var stem=$"app.log.{DateTime.Now:yyyy-MM-dd}";
            for(var i=0;i<30;i++)
            {
                var path=FilePath(i==0 ? stem : $"{stem}.{i:00}");
                if(File.Exists(path) && new FileInfo(path).Length+bytes.Length>MaxFileBytes) continue;
                if(!File.Exists(path) && Files().Length>=30) throw new IOException("Đã đủ 30 tệp nhật ký; xóa tệp cũ trong Nhật ký để ghi tiếp.");
                using var stream=new FileStream(path,FileMode.Append,FileAccess.Write,FileShare.ReadWrite);
                stream.Write(bytes);return;
            }
            throw new IOException("Nhật ký hôm nay đã đạt giới hạn.");
        }
    }
    internal string Read(string name)
    {
        lock(_gate)
        {
            var path=FilePath(name);
            if(new FileInfo(path).Length>MaxFileBytes) throw new IOException("Tệp nhật ký vượt 1 MiB.");
            return File.ReadAllText(path,Encoding.UTF8);
        }
    }
    internal void Clear(string name)
    {
        lock(_gate) { var path=FilePath(name);if(!File.Exists(path)) throw new IOException("Không tìm thấy tệp nhật ký.");File.Delete(path); }
    }
    internal static string Level(string text)
    {
        if(text.Contains("[error]",StringComparison.OrdinalIgnoreCase)||text.Contains("lỗi",StringComparison.OrdinalIgnoreCase)||text.Contains("exception",StringComparison.OrdinalIgnoreCase)||text.Contains("error",StringComparison.OrdinalIgnoreCase)||text.StartsWith("Không ",StringComparison.OrdinalIgnoreCase)) return "ERROR";
        if(text.Contains("[warning]",StringComparison.OrdinalIgnoreCase)||text.Contains("cảnh báo",StringComparison.OrdinalIgnoreCase)||text.Contains("[stderr]",StringComparison.OrdinalIgnoreCase)) return "WARN";
        return text.StartsWith("[tab]",StringComparison.Ordinal) ? "DEBUG" : "INFO";
    }
    internal static string[] Filter(string text,string query,string level,bool regex)
    {
        if(query.Length>500) throw new ArgumentException("Từ khóa tìm kiếm vượt 500 ký tự.");
        var clock=System.Diagnostics.Stopwatch.StartNew();
        Regex? expression=regex && query.Length>0 ? new Regex(query,RegexOptions.IgnoreCase|RegexOptions.CultureInvariant,TimeSpan.FromMilliseconds(100)) : null;
        return text.Split('\n',StringSplitOptions.RemoveEmptyEntries).Select(s=>s.TrimEnd('\r')).Where(s=>
        {
            if(clock.ElapsedMilliseconds>500) throw new TimeoutException("Tìm kiếm quá lâu; hãy dùng từ khóa/biểu thức đơn giản hơn.");
            return
            (level=="ALL" || Regex.IsMatch(s,@"^\S+ \S+ [+-]\d\d:\d\d "+Regex.Escape(level)+@" ")) &&
            (expression is not null ? expression.IsMatch(s) : query.Length==0 || s.Contains(query,StringComparison.OrdinalIgnoreCase));
        }).ToArray();
    }
}
