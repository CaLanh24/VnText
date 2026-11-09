using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Forms;

public sealed class PayloadManifest
{
    public int schema { get; set; }
    public Dictionary<string, PayloadFile> files { get; set; }
}

public sealed class PayloadFile
{
    public string sha256 { get; set; }
    public long size { get; set; }
}

public static class Setup
{
    private const string ManifestName = "payload-manifest.json";
    private const string InstallManifestName = "data/install-manifest.json";
    private const string FullAppOwnershipName = ".update/owned-files.json";
    private const string LegacyShortcutName = "VNText Studio.lnk";
    private const string UpdateSourceName = ".vntext-update-source.json";
    private const string GitHubUpdateSourceResourceName = "VNText.Studio.GitHubUpdateSource.json";
    private const string IntelTermsPath = "app/licenses/native/intel-2025.3-customer-terms.txt";
    private const string IntelEulaPath = "app/licenses/native/intel-2025.3-cpp-eula.rtf";

    [STAThread]
    public static int Main(string[] args)
    {
#if UNINSTALLER
        return Uninstall(args);
#else
        return Install(args);
#endif
    }

#if !UNINSTALLER
    private static int Install(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        bool accepted;
        termsVietnamese = UseVietnamese(args);          // the dialog chrome is localized; the legal text itself is shown exactly as shipped
        try { accepted = ConfirmIntelTerms(); }
        catch (Exception ex)
        {
            MessageBox.Show("Setup could not verify the Intel terms in its payload:\n" + ex.Message,
                "VNText Studio Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }
        if (!accepted) return 1;
        using (var wizard = new SetupWizard(UseVietnamese(args)))
        {
            Application.Run(wizard);
            return wizard.ExitCode;
        }
    }
#endif

#if !UNINSTALLER
    private const string ShortcutRecordName = "data/shortcuts.json";
    private const string ShortcutFileName = "VNText Studio.lnk";
    private const string AppExecutableName = "VNText Studio.exe";

    private static bool UseVietnamese(string[] args)
    {
        if (args != null)
            foreach (var arg in args)
            {
                if (String.Equals(arg, "/lang=vi", StringComparison.OrdinalIgnoreCase) || String.Equals(arg, "--lang=vi", StringComparison.OrdinalIgnoreCase)) return true;
                if (String.Equals(arg, "/lang=en", StringComparison.OrdinalIgnoreCase) || String.Equals(arg, "--lang=en", StringComparison.OrdinalIgnoreCase)) return false;
            }
        return String.Equals(System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName, "vi", StringComparison.OrdinalIgnoreCase);
    }

    private static long PayloadBytes()
    {
        try
        {
            using (var zipStream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Payload.zip"))
            {
                if (zipStream == null) return -1;
                using (var zip = new ZipArchive(zipStream, ZipArchiveMode.Read))
                {
                    long total = 0;
                    foreach (var file in ReadManifest(zip).files.Values) total += file.size;
                    return total;
                }
            }
        }
        catch (Exception) { return -1; }
    }

    /// <summary>Returns an error text (already localized by the caller's flag) or null; never creates anything.</summary>
    private static string ValidateDestination(string text, bool vi, out string root, out bool existingInstall)
    {
        root = null;
        existingInstall = false;
        try
        {
            if (String.IsNullOrWhiteSpace(text)) return vi ? "Hãy nhập thư mục cài đặt." : "Enter the install folder.";
            root = Path.GetFullPath(text.Trim().Trim('"'));
            var volume = Path.GetPathRoot(root);
            if (String.Equals(root.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
                volume.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar), StringComparison.OrdinalIgnoreCase))
                return vi ? "Hãy chọn một thư mục con, không phải thư mục gốc của ổ đĩa." : "Choose a subfolder, not the drive root.";
            var probe = root;
            while (!Directory.Exists(probe) && Path.GetDirectoryName(probe) != null) probe = Path.GetDirectoryName(probe);
            EnsureSafeDirectory(probe);
            if (!Directory.Exists(root)) return null;
            EnsureSafeDirectory(root);
            var existingState = SafeTarget(root, InstallManifestName);
            existingInstall = File.Exists(existingState);
            if (!existingInstall)
                using (var children = Directory.EnumerateFileSystemEntries(root).GetEnumerator())
                    if (children.MoveNext())
                        return vi ? "Thư mục đã chọn không trống và không phải bản cài VNText Studio. Hãy chọn thư mục trống."
                                  : "The selected folder is not empty and is not a recognized VNText Studio installation. Choose an empty folder.";
            return null;
        }
        catch (Exception ex) { return ex.Message; }
    }

    private static string ProgramsFolder()
    {
        return Environment.GetFolderPath(Environment.SpecialFolder.Programs);
    }

    /// <summary>A Start Menu folder is a relative name under the user's Programs folder: no drive, no traversal, no invalid characters.</summary>
    private static string ValidateMenuFolder(string text, bool vi, string programsDirectory, out string relative)
    {
        relative = null;
        var raw = (text ?? "").Trim();
        var name = raw.Trim('\\', '/');
        if (raw.StartsWith("\\") || raw.StartsWith("/"))
            return vi ? "Tên thư mục Start Menu không hợp lệ." : "The Start Menu folder name is not valid.";
        if (name.Length == 0) return vi ? "Hãy nhập tên thư mục Start Menu hoặc chọn không tạo." : "Enter a Start Menu folder name or choose not to create one.";
        if (name.Length > 120 || name.IndexOfAny(Path.GetInvalidPathChars()) >= 0 || name.IndexOf(':') >= 0)
            return vi ? "Tên thư mục Start Menu không hợp lệ." : "The Start Menu folder name is not valid.";
        var invalid = Path.GetInvalidFileNameChars();
        foreach (var part in name.Replace('/', '\\').Split('\\'))
            if (part.Length == 0 || part == "." || part == ".." || part.IndexOfAny(invalid) >= 0 || part.EndsWith(".") || part.EndsWith(" "))
                return vi ? "Tên thư mục Start Menu không hợp lệ." : "The Start Menu folder name is not valid.";
        var programs = Path.GetFullPath(programsDirectory).TrimEnd('\\') + "\\";
        var full = Path.GetFullPath(Path.Combine(programs, name));
        if (!full.StartsWith(programs, StringComparison.OrdinalIgnoreCase))
            return vi ? "Thư mục Start Menu phải nằm trong danh sách chương trình." : "The Start Menu folder must stay inside the Programs list.";
        relative = name.Replace('/', '\\');
        return null;
    }

    private static void SaveShortcut(string linkPath, string target, string workDirectory, string description)
    {
        var shellType = Type.GetTypeFromProgID("WScript.Shell");
        if (shellType == null) throw new InvalidOperationException("WScript.Shell is unavailable.");
        var shell = Activator.CreateInstance(shellType);
        var link = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { linkPath });
        var linkType = link.GetType();
        linkType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, link, new object[] { target });
        linkType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, link, new object[] { workDirectory });
        linkType.InvokeMember("Description", BindingFlags.SetProperty, null, link, new object[] { description });
        linkType.InvokeMember("IconLocation", BindingFlags.SetProperty, null, link, new object[] { target + ",0" });
        linkType.InvokeMember("Save", BindingFlags.InvokeMethod, null, link, null);
    }

    private static string ShortcutTarget(string linkPath)
    {
        var shellType = Type.GetTypeFromProgID("WScript.Shell");
        if (shellType == null) return null;
        var shell = Activator.CreateInstance(shellType);
        var link = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { linkPath });
        return Convert.ToString(link.GetType().InvokeMember("TargetPath", BindingFlags.GetProperty, null, link, null));
    }

    /// <summary>Creates only shortcuts the user chose; never overwrites a shortcut that is neither ours nor pointing at this install. Returns notes for the completion page.</summary>
    private static List<string> CreateShortcuts(string root, string desktopDirectory, string programsDirectory, string menuRelative, bool vi)
    {
        var notes = new List<string>();
        var exe = Path.Combine(root, AppExecutableName);
        var recordPath = SafeTarget(root, ShortcutRecordName);
        var recorded = new List<string>();
        string menuDirectory = null;
        var targets = new List<string>();
        if (desktopDirectory != null) targets.Add(Path.Combine(desktopDirectory, ShortcutFileName));
        if (menuRelative != null)
        {
            menuDirectory = Path.Combine(programsDirectory, menuRelative);
            targets.Add(Path.Combine(menuDirectory, ShortcutFileName));
        }
        foreach (var link in targets)
        {
            try
            {
                var directory = Path.GetDirectoryName(link);
                if (Directory.Exists(directory) && (File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0)
                    throw new IOException("shortcut folder is a link");
                if (File.Exists(link))
                {
                    var existing = ShortcutTarget(link);
                    if (!String.Equals(existing, exe, StringComparison.OrdinalIgnoreCase))
                    {
                        notes.Add(vi ? "Bỏ qua lối tắt đã có của ứng dụng khác: " + link : "Skipped an existing shortcut that is not ours: " + link);
                        continue;
                    }
                }
                Directory.CreateDirectory(directory);
                SaveShortcut(link, exe, root, "VNText Studio");
                recorded.Add(link);
            }
            catch (Exception ex)
            {
                notes.Add((vi ? "Không tạo được lối tắt " : "Could not create shortcut ") + link + ": " + ex.Message);
            }
        }
        var record = new Dictionary<string, object>();
        record["shortcuts"] = recorded;
        record["menu_folder"] = recorded.Count > 0 && menuDirectory != null ? menuDirectory : "";
        File.WriteAllText(recordPath, new JavaScriptSerializer().Serialize(record), Encoding.UTF8);
        return notes;
    }
#endif

    /// <summary>Uninstall removes only the shortcuts Setup recorded and only while they still point at this install.</summary>
    private static void RemoveRecordedShortcuts(string root, string programsDirectory)
    {
        try
        {
            var recordPath = SafeTarget(root, "data/shortcuts.json");
            if (!IsRegularFileNoLink(recordPath)) return;
            var record = new JavaScriptSerializer { MaxJsonLength = 1024 * 1024 }.Deserialize<Dictionary<string, object>>(File.ReadAllText(recordPath, Encoding.UTF8));
            var exe = Path.Combine(root, "VNText Studio.exe");
            object listValue;
            if (record != null && record.TryGetValue("shortcuts", out listValue) && listValue is System.Collections.IEnumerable)
                foreach (var item in (System.Collections.IEnumerable)listValue)
                {
                    var link = item as string;
                    if (link == null || !String.Equals(Path.GetFileName(link), "VNText Studio.lnk", StringComparison.OrdinalIgnoreCase)) continue;
                    if (!IsRegularFileNoLink(link)) continue;
                    var type = Type.GetTypeFromProgID("WScript.Shell");
                    if (type == null) continue;
                    var shell = Activator.CreateInstance(type);
                    var shortcut = type.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { link });
                    var target = Convert.ToString(shortcut.GetType().InvokeMember("TargetPath", BindingFlags.GetProperty, null, shortcut, null));
                    if (String.Equals(target, exe, StringComparison.OrdinalIgnoreCase)) File.Delete(link);
                }
            object menu;
            if (record != null && record.TryGetValue("menu_folder", out menu) && menu is string && ((string)menu).Length > 0)
            {
                var programs = Path.GetFullPath(programsDirectory).TrimEnd('\\') + "\\";
                var folder = Path.GetFullPath((string)menu);
                if (folder.StartsWith(programs, StringComparison.OrdinalIgnoreCase) && Directory.Exists(folder)
                    && (File.GetAttributes(folder) & FileAttributes.ReparsePoint) == 0)
                {
                    using (var children = Directory.EnumerateFileSystemEntries(folder).GetEnumerator())
                        if (!children.MoveNext()) Directory.Delete(folder);
                }
            }
        }
        catch (Exception) { /* shortcut cleanup is best effort; the install folder removal below is authoritative */ }
    }

    private static bool IsRegularFileNoLink(string path)
    {
        return File.Exists(path) && (File.GetAttributes(path) & FileAttributes.ReparsePoint) == 0;
    }

#if !UNINSTALLER
    // ---- Resource preparation (a real Setup step) -------------------------------------------------------------------------------
    // After the files are installed, Setup hands off to the BUNDLED worker (app/worker, the same trusted code that Settings uses) with the
    // existing "resources" task and download=true: the pinned, hash-checked, atomically installed catalog (translation model, Ren'Py SDK 8.5.3,
    // Windows OCR check).  Valid resources that are already present (the bundled model, an installed SDK) are skipped by that task.  Setup
    // has NO downloader of its own; it only speaks the worker's JSON-line protocol, shows progress and reports the honest outcome.

    internal sealed class ResourceStepResult
    {
        public bool Ok;
        public bool Cancelled;
        public string Error = "";
        public string Summary = "";
    }

    /// <summary>The bundled worker command and the exact environment the app gives it (WorkerPaths.ConfigureReleaseEnvironment).  Returns an error text or null.</summary>
    private static string BuildResourceWorkerStart(string root, out string python, out string arguments, out string workDirectory, Dictionary<string, string> environment)
    {
        python = null; arguments = null; workDirectory = null;
        var worker = Path.Combine(root, "app", "worker");
        python = Path.Combine(worker, "python", "python.exe");
        if (!Directory.Exists(Path.Combine(worker, "vntext_worker")) || !File.Exists(python) || !File.Exists(Path.Combine(worker, ".venv", "Scripts", "python.exe")))
            return "The installed program has no resource worker (app\\worker is incomplete).";
        var data = Path.Combine(root, "data");
        var temp = Path.Combine(data, "temp");
        var cache = Path.Combine(data, "cache");
        Directory.CreateDirectory(temp);
        Directory.CreateDirectory(cache);
        environment["VNTEXT_DATA_ROOT"] = data;
        environment["VNTEXT_RENPY_TOOL_ROOT"] = Path.Combine(data, "tools");
        environment["TEMP"] = temp; environment["TMP"] = temp; environment["TMPDIR"] = temp;
        environment["LOCALAPPDATA"] = data; environment["APPDATA"] = data;
        environment["HF_HOME"] = Path.Combine(cache, "huggingface");
        environment["HF_HUB_CACHE"] = Path.Combine(cache, "huggingface", "hub");
        environment["TRANSFORMERS_CACHE"] = Path.Combine(cache, "huggingface", "transformers");
        environment["TORCH_HOME"] = Path.Combine(cache, "torch");
        environment["VNTEXT_DIRECT_GPU_ROOT"] = Path.Combine(cache, "gpu");
        environment["PYTHONHOME"] = Path.Combine(worker, "python");
        environment["PYTHONPATH"] = Path.Combine(worker, ".venv", "Lib", "site-packages");
        environment["PYTHONNOUSERSITE"] = "1";
        environment["PYTHONDONTWRITEBYTECODE"] = "1";
        environment["PYTHONUTF8"] = "1";
        environment["PYTHONIOENCODING"] = "utf-8";
        environment["TRANSFORMERS_OFFLINE"] = "1";
        environment["HF_HUB_OFFLINE"] = "1";
        environment["OMP_NUM_THREADS"] = "1";
        arguments = "-m vntext_worker.worker_main";
        workDirectory = worker;
        return null;
    }

    private static string StringField(Dictionary<string, object> message, string name)
    {
        object value;
        return message.TryGetValue(name, out value) && value != null ? Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture) : "";
    }

    private static long NumberField(Dictionary<string, object> message, string name)
    {
        object value;
        long number;
        return message.TryGetValue(name, out value) && value != null
            && Int64.TryParse(Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture), out number) ? number : 0;
    }

    /// <summary>
    /// Runs the worker's "resources" task to its end.  report(done, total, step, item) is called for progress (total 0 = unknown).  cancelled() is polled;
    /// on cancel the worker is asked to stop and is killed (with its children) if it does not finish in time.  Never reports success unless the worker's
    /// own "complete" event said ok.
    /// </summary>
    internal static ResourceStepResult RunResourceWorker(string python, string arguments, string workDirectory, Dictionary<string, string> environment,
        Action<long, long, string, string> report, Func<bool> cancelled, int readySeconds, int cancelGraceSeconds)
    {
        var result = new ResourceStepResult();
        var serializer = new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue };
        var lines = new System.Collections.Concurrent.ConcurrentQueue<string>();
        var signal = new System.Threading.AutoResetEvent(false);
        var lastError = new StringBuilder();
        var info = new ProcessStartInfo(python, arguments)
        {
            WorkingDirectory = workDirectory, UseShellExecute = false, CreateNoWindow = true,
            RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
            StandardOutputEncoding = new UTF8Encoding(false), StandardErrorEncoding = new UTF8Encoding(false),
        };
        foreach (var pair in environment) info.EnvironmentVariables[pair.Key] = pair.Value;
        Process process;
        try { process = Process.Start(info); }
        catch (Exception ex) { result.Error = "The resource worker did not start: " + ex.Message; return result; }
        using (process)
        {
            process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null) { lines.Enqueue(e.Data); signal.Set(); } };
            process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e)
            {
                if (String.IsNullOrWhiteSpace(e.Data)) return;
                lock (lastError) { lastError.Length = 0; lastError.Append(e.Data.Trim()); }
            };
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            var taskId = "setup-resources-" + Guid.NewGuid().ToString("N");
            var started = false;
            var cancelSent = false;
            var clock = Stopwatch.StartNew();
            double cancelAt = 0;
            try
            {
                while (true)
                {
                    string raw;
                    while (lines.TryDequeue(out raw))
                    {
                        Dictionary<string, object> message;
                        try { message = serializer.DeserializeObject(raw) as Dictionary<string, object>; }
                        catch (Exception) { continue; }          // not protocol output (a library banner); the worker's contract is JSON lines
                        if (message == null) continue;
                        var type = StringField(message, "type");
                        if (type == "ready" && !started)
                        {
                            started = true;
                            var command = serializer.Serialize(new Dictionary<string, object> {
                                { "v", 1 }, { "type", "run" }, { "id", taskId }, { "task", "resources" },
                                { "params", new Dictionary<string, object> { { "download", true } } } });
                            process.StandardInput.WriteLine(command);
                            process.StandardInput.Flush();
                        }
                        else if (type == "progress" && StringField(message, "id") == taskId)
                        {
                            if (report != null) report(NumberField(message, "done"), NumberField(message, "total"), StringField(message, "step"), StringField(message, "item"));
                        }
                        else if (type == "complete" && StringField(message, "id") == taskId)
                        {
                            object okValue;
                            result.Ok = message.TryGetValue("ok", out okValue) && okValue is bool && (bool)okValue;
                            result.Error = StringField(message, "error");
                            result.Summary = StringField(message, "summary");
                            result.Cancelled = !result.Ok && result.Error.IndexOf("cancel", StringComparison.OrdinalIgnoreCase) >= 0;
                            return result;
                        }
                    }
                    if (process.HasExited && lines.IsEmpty)
                    {
                        var tail = ""; lock (lastError) { tail = lastError.ToString(); }
                        result.Error = "The resource worker stopped before it finished (exit code " + process.ExitCode + ")." + (tail.Length > 0 ? " " + tail : "");
                        return result;
                    }
                    if (cancelled != null && cancelled() && !cancelSent)
                    {
                        cancelSent = true; cancelAt = clock.Elapsed.TotalSeconds;
                        if (started)
                        {
                            try
                            {
                                process.StandardInput.WriteLine(serializer.Serialize(new Dictionary<string, object> { { "v", 1 }, { "type", "cancel" }, { "id", taskId } }));
                                process.StandardInput.Flush();
                            }
                            catch (Exception) { /* the process is going away; the kill below covers it */ }
                        }
                    }
                    if (cancelSent && (!started || clock.Elapsed.TotalSeconds - cancelAt >= cancelGraceSeconds))
                    {
                        result.Cancelled = true;
                        result.Error = "cancelled";
                        return result;
                    }
                    if (!started && clock.Elapsed.TotalSeconds > readySeconds)
                    {
                        result.Error = "The resource worker did not become ready in " + readySeconds + " seconds.";
                        return result;
                    }
                    signal.WaitOne(100);
                }
            }
            finally
            {
                if (!process.HasExited)
                {
                    try { process.StandardInput.Close(); } catch (Exception) { }
                    if (!process.WaitForExit(2000))
                    {
                        try
                        {
                            var kill = Process.Start(new ProcessStartInfo("taskkill.exe", "/PID " + process.Id + " /T /F") { UseShellExecute = false, CreateNoWindow = true });
                            if (kill != null) kill.WaitForExit(5000);
                        }
                        catch (Exception) { }
                        try { if (!process.HasExited) process.Kill(); } catch (Exception) { }
                    }
                }
            }
        }
    }

    private sealed class SetupWizard : Form
    {
        private readonly bool vi;
        private readonly long payloadBytes;
        private readonly Label title = new Label(), subtitle = new Label();
        private readonly Panel body = new Panel();
        private readonly Panel[] pages = new Panel[7];
        private readonly Button back = new Button(), next = new Button(), cancel = new Button();
        private readonly TextBox destination = new TextBox(), menuFolder = new TextBox(), summary = new TextBox();
        private readonly CheckBox menuNone = new CheckBox(), desktopShortcut = new CheckBox(), launch = new CheckBox();
        private readonly Label diskNote = new Label(), installStatus = new Label(), installFile = new Label(), doneText = new Label(), doneNotes = new Label();
        private readonly ProgressBar bar = new ProgressBar();
        private readonly Label resStatus = new Label(), resItem = new Label(), resDetail = new Label();
        private readonly ProgressBar resBar = new ProgressBar();
        private int page;
        private bool installing;
        private bool preparing, resourceCancel, resourcesReady;
        private string resourceFailure;
        private List<string> shortcutNotes = new List<string>();
        private string root, menuRelative;
        private bool existingInstall;
        internal int ExitCode = 1;

        private string T(string vietnamese, string english) { return vi ? vietnamese : english; }

        internal SetupWizard(bool vietnamese)
        {
            vi = vietnamese;
            payloadBytes = PayloadBytes();
            Text = T("Cài đặt — VNText Studio", "Setup — VNText Studio");
            Font = new System.Drawing.Font("Segoe UI", 9F);
            ClientSize = new System.Drawing.Size(640, 450);
            FormBorderStyle = FormBorderStyle.FixedDialog;
            StartPosition = FormStartPosition.CenterScreen;
            MaximizeBox = false;
            MinimizeBox = true;
            ShowInTaskbar = true;
            try { Icon = System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }
            var header = new Panel { Dock = DockStyle.Top, Height = 72, BackColor = System.Drawing.Color.White };
            title.Font = new System.Drawing.Font("Segoe UI", 10.5F, System.Drawing.FontStyle.Bold);
            title.Left = 24; title.Top = 12; title.Width = 580; title.Height = 22;
            subtitle.Left = 40; subtitle.Top = 38; subtitle.Width = 570; subtitle.Height = 22;
            header.Controls.Add(title);
            header.Controls.Add(subtitle);
            var headerLine = new Panel { Dock = DockStyle.Top, Height = 1, BackColor = System.Drawing.Color.FromArgb(0xD0, 0xD0, 0xD0) };
            var footer = new Panel { Dock = DockStyle.Bottom, Height = 58, BackColor = System.Drawing.Color.FromArgb(0xF0, 0xF0, 0xF0) };
            var footerLine = new Panel { Dock = DockStyle.Top, Height = 1, BackColor = System.Drawing.Color.FromArgb(0xD0, 0xD0, 0xD0) };
            footer.Controls.Add(footerLine);
            foreach (var button in new[] { back, next, cancel })
            {
                button.Width = 96; button.Height = 30; button.Top = 14; button.UseVisualStyleBackColor = true;
                footer.Controls.Add(button);
            }
            cancel.Left = 530; next.Left = 426; back.Left = 322;
            back.Text = T("‹ Quay lại", "< Back");
            cancel.Text = T("Hủy", "Cancel");
            body.Dock = DockStyle.Fill;
            body.BackColor = System.Drawing.Color.FromArgb(0xF0, 0xF0, 0xF0);
            Controls.Add(body);
            Controls.Add(footer);
            Controls.Add(headerLine);
            Controls.Add(header);
            BuildPages();
            body.Resize += delegate
            {
                diskNote.Top = Math.Max(180, body.ClientSize.Height - diskNote.Height - 20);
                summary.Height = Math.Max(100, body.ClientSize.Height - summary.Top - 24);
            };
            diskNote.Top = Math.Max(180, body.ClientSize.Height - diskNote.Height - 20);
            summary.Height = Math.Max(100, body.ClientSize.Height - summary.Top - 24);
            back.Click += delegate { Go(page - 1); };
            next.Click += delegate { Advance(); };
            cancel.Click += delegate
            {
                if (page == 5) { if (preparing) RequestResourceCancel(); else ShowDone(); return; }       // Cancel stops preparation; after a failure it is Skip
                Close();
            };
            AcceptButton = next;
            FormClosing += delegate(object sender, FormClosingEventArgs e)
            {
                if (installing) { e.Cancel = true; return; }
                if (preparing) { e.Cancel = true; RequestResourceCancel(); return; }
                if (page < 4 && e.CloseReason == CloseReason.UserClosing && ExitCode != 0 &&
                    MessageBox.Show(T("Thoát Setup? VNText Studio chưa được cài đặt.", "Exit Setup? VNText Studio has not been installed yet."),
                        T("Cài đặt VNText Studio", "VNText Studio Setup"), MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                    e.Cancel = true;
            };
            Go(0);
        }

        private Panel NewPage(int index)
        {
            var panel = new Panel { Dock = DockStyle.Fill, Visible = false, BackColor = System.Drawing.Color.FromArgb(0xF0, 0xF0, 0xF0) };
            pages[index] = panel;
            body.Controls.Add(panel);
            return panel;
        }

        private Label AddLabel(Panel panel, string text, int left, int top, int width, int height)
        {
            var label = new Label { Left = left, Top = top, Width = width, Height = height, Text = text, AutoSize = false };
            panel.Controls.Add(label);
            return label;
        }

        private void BuildPages()
        {
            var p0 = NewPage(0);
            AddLabel(p0, T("Setup sẽ cài VNText Studio vào thư mục sau.", "Setup will install VNText Studio into the following folder."), 24, 28, 580, 22);
            AddLabel(p0, T("Để tiếp tục, nhấn Tiếp tục. Muốn chọn thư mục khác, nhấn Duyệt.", "To continue, click Next. If you would like to select a different folder, click Browse."), 24, 64, 580, 22);
            destination.Left = 24; destination.Top = 96; destination.Width = 480;
            destination.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "VNText Studio");
            var browse = new Button { Left = 516, Top = 94, Width = 90, Height = 27, Text = T("Duyệt…", "Browse…"), UseVisualStyleBackColor = true };
            browse.Click += delegate
            {
                using (var picker = new FolderBrowserDialog())
                {
                    picker.Description = T("Chọn thư mục cài đặt VNText Studio. Dữ liệu ứng dụng nằm trong thư mục con data.", "Choose the VNText Studio install folder. App data stays in its data subfolder.");
                    picker.ShowNewFolderButton = true;
                    if (Directory.Exists(destination.Text)) picker.SelectedPath = destination.Text;
                    if (picker.ShowDialog(this) == DialogResult.OK) destination.Text = picker.SelectedPath;
                }
            };
            p0.Controls.Add(destination);
            p0.Controls.Add(browse);
            diskNote.Left = 24; diskNote.Top = 380; diskNote.Width = 580; diskNote.Height = 22;
            diskNote.Text = payloadBytes > 0
                ? String.Format(T("Cần ít nhất {0:N1} MB dung lượng trống.", "At least {0:N1} MB of free disk space is required."), payloadBytes * 1.1 / (1024.0 * 1024.0))
                : "";
            p0.Controls.Add(diskNote);

            var p1 = NewPage(1);
            AddLabel(p1, T("Setup sẽ tạo lối tắt của chương trình trong thư mục Start Menu sau.", "Setup will create the program's shortcuts in the following Start Menu folder."), 24, 28, 580, 22);
            AddLabel(p1, T("Để tiếp tục, nhấn Tiếp tục. Muốn chọn thư mục khác, nhấn Duyệt.", "To continue, click Next. If you would like to select a different folder, click Browse."), 24, 64, 580, 22);
            menuFolder.Left = 24; menuFolder.Top = 96; menuFolder.Width = 480; menuFolder.Text = "VNText Studio";
            var browseMenu = new Button { Left = 516, Top = 94, Width = 90, Height = 27, Text = T("Duyệt…", "Browse…"), UseVisualStyleBackColor = true };
            browseMenu.Click += delegate
            {
                using (var picker = new FolderBrowserDialog())
                {
                    picker.Description = T("Chọn thư mục trong Start Menu.", "Choose a folder inside the Start Menu.");
                    picker.ShowNewFolderButton = true;
                    picker.SelectedPath = ProgramsFolder();
                    if (picker.ShowDialog(this) != DialogResult.OK) return;
                    var programs = Path.GetFullPath(ProgramsFolder()).TrimEnd('\\') + "\\";
                    var chosen = Path.GetFullPath(picker.SelectedPath).TrimEnd('\\') + "\\";
                    if (chosen.StartsWith(programs, StringComparison.OrdinalIgnoreCase) && chosen.Length > programs.Length)
                        menuFolder.Text = chosen.Substring(programs.Length).TrimEnd('\\');
                    else
                        MessageBox.Show(T("Hãy chọn một thư mục nằm trong danh sách chương trình của Start Menu.", "Choose a folder inside the Start Menu Programs list."), Text, MessageBoxButtons.OK, MessageBoxIcon.Information);
                }
            };
            menuNone.Left = 24; menuNone.Top = 140; menuNone.Width = 580; menuNone.Text = T("Không tạo thư mục trong Start Menu", "Don't create a Start Menu folder");
            menuNone.CheckedChanged += delegate { menuFolder.Enabled = !menuNone.Checked; browseMenu.Enabled = !menuNone.Checked; };
            p1.Controls.Add(menuFolder);
            p1.Controls.Add(browseMenu);
            p1.Controls.Add(menuNone);

            var p2 = NewPage(2);
            AddLabel(p2, T("Chọn các tác vụ bổ sung mà Setup sẽ thực hiện khi cài VNText Studio, rồi nhấn Tiếp tục.", "Select the additional tasks you would like Setup to perform while installing VNText Studio, then click Next."), 24, 28, 580, 40);
            AddLabel(p2, T("Biểu tượng bổ sung:", "Additional icons:"), 24, 84, 580, 22);
            desktopShortcut.Left = 24; desktopShortcut.Top = 112; desktopShortcut.Width = 580; desktopShortcut.Checked = true;
            desktopShortcut.Text = T("Tạo lối tắt trên màn hình nền", "Create a desktop shortcut");
            p2.Controls.Add(desktopShortcut);

            var p3 = NewPage(3);
            AddLabel(p3, T("Setup đã sẵn sàng cài VNText Studio vào máy của bạn.", "Setup is now ready to begin installing VNText Studio on your computer."), 24, 24, 580, 22);
            AddLabel(p3, T("Nhấn Cài đặt để tiếp tục, hoặc Quay lại nếu muốn xem lại hay đổi lựa chọn.", "Click Install to continue, or click Back if you want to review or change any settings."), 24, 48, 580, 40);
            summary.Left = 24; summary.Top = 96; summary.Width = 582; summary.Height = 250;
            summary.Multiline = true; summary.ReadOnly = true; summary.ScrollBars = ScrollBars.Vertical; summary.BackColor = System.Drawing.Color.White;
            p3.Controls.Add(summary);

            var p4 = NewPage(4);
            installStatus.Left = 24; installStatus.Top = 40; installStatus.Width = 580; installStatus.Height = 44;
            installFile.Left = 24; installFile.Top = 130; installFile.Width = 580; installFile.Height = 22;
            bar.Left = 24; bar.Top = 96; bar.Width = 580; bar.Height = 22; bar.Minimum = 0; bar.Maximum = 100;
            p4.Controls.Add(installStatus);
            p4.Controls.Add(bar);
            p4.Controls.Add(installFile);

            var p5 = NewPage(5);
            resStatus.Left = 24; resStatus.Top = 40; resStatus.Width = 580; resStatus.Height = 44;
            resBar.Left = 24; resBar.Top = 96; resBar.Width = 580; resBar.Height = 22; resBar.Minimum = 0; resBar.Maximum = 100;
            resItem.Left = 24; resItem.Top = 130; resItem.Width = 580; resItem.Height = 22;
            resDetail.Left = 24; resDetail.Top = 164; resDetail.Width = 580; resDetail.Height = 150;
            p5.Controls.Add(resStatus);
            p5.Controls.Add(resBar);
            p5.Controls.Add(resItem);
            p5.Controls.Add(resDetail);

            var p6 = NewPage(6);
            doneText.Left = 24; doneText.Top = 28; doneText.Width = 580; doneText.Height = 66;
            doneNotes.Left = 24; doneNotes.Top = 150; doneNotes.Width = 580; doneNotes.Height = 120;
            launch.Left = 24; launch.Top = 110; launch.Width = 580; launch.Checked = true;
            launch.Text = T("Mở VNText Studio", "Launch VNText Studio");
            p6.Controls.Add(doneText);
            p6.Controls.Add(launch);
            p6.Controls.Add(doneNotes);
        }

        private void Go(int target)
        {
            page = Math.Max(0, Math.Min(6, target));
            for (var i = 0; i < pages.Length; i++) pages[i].Visible = i == page;
            back.Visible = page > 0 && page < 4;
            cancel.Visible = page < 6;
            cancel.Enabled = page < 4;
            cancel.Text = T("Hủy", "Cancel");
            next.Enabled = true;
            switch (page)
            {
                case 0: title.Text = T("Chọn thư mục cài đặt", "Select Destination Location"); subtitle.Text = T("VNText Studio sẽ được cài vào đâu?", "Where should VNText Studio be installed?"); next.Text = T("Tiếp tục ›", "Next >"); break;
                case 1: title.Text = T("Chọn thư mục Start Menu", "Select Start Menu Folder"); subtitle.Text = T("Setup nên đặt lối tắt chương trình ở đâu?", "Where should Setup place the program's shortcuts?"); next.Text = T("Tiếp tục ›", "Next >"); break;
                case 2: title.Text = T("Chọn tác vụ bổ sung", "Select Additional Tasks"); subtitle.Text = T("Cần thực hiện thêm tác vụ nào?", "Which additional tasks should be performed?"); next.Text = T("Tiếp tục ›", "Next >"); break;
                case 3: title.Text = T("Sẵn sàng cài đặt", "Ready to Install"); subtitle.Text = T("Setup đã sẵn sàng bắt đầu cài VNText Studio.", "Setup is now ready to begin installing VNText Studio on your computer."); next.Text = T("Cài đặt", "Install"); RefreshSummary(); break;
                case 4: title.Text = T("Đang cài đặt", "Installing"); subtitle.Text = T("Vui lòng chờ trong khi Setup cài VNText Studio.", "Please wait while Setup installs VNText Studio on your computer."); next.Enabled = false; break;
                case 5: title.Text = T("Chuẩn bị tài nguyên", "Preparing Resources"); subtitle.Text = T("Setup đang tải và kiểm tra các tài nguyên cần thiết.", "Setup is downloading and checking the resources VNText Studio needs."); next.Enabled = false; break;
                default: title.Text = T("Hoàn tất cài đặt VNText Studio", "Completing the VNText Studio Setup"); subtitle.Text = T("Setup đã cài xong VNText Studio.", "Setup has finished installing VNText Studio on your computer."); next.Text = T("Hoàn tất", "Finish"); break;
            }
        }

        private void RefreshSummary()
        {
            var lines = new List<string>();
            lines.Add(T("Thư mục cài đặt:", "Destination location:"));
            lines.Add("      " + root);
            lines.Add("");
            lines.Add(T("Thư mục Start Menu:", "Start Menu folder:"));
            lines.Add("      " + (menuRelative ?? T("(không tạo)", "(none)")));
            lines.Add("");
            lines.Add(T("Tác vụ bổ sung:", "Additional tasks:"));
            lines.Add("      " + (desktopShortcut.Checked ? T("Tạo lối tắt trên màn hình nền", "Create a desktop shortcut") : T("(không có)", "(none)")));
            if (existingInstall)
            {
                lines.Add("");
                lines.Add(T("Thư mục này đã có VNText Studio: tệp chương trình sẽ được sửa/nâng cấp, thư mục data được giữ nguyên.", "This folder already has VNText Studio: program files will be repaired or upgraded and the data folder is preserved."));
            }
            summary.Text = String.Join(Environment.NewLine, lines.ToArray());
        }

        private void Advance()
        {
            switch (page)
            {
                case 0:
                    {
                        string full;
                        var error = ValidateDestination(destination.Text, vi, out full, out existingInstall);
                        if (error != null) { Warn(error); return; }
                        if (existingInstall && MessageBox.Show(
                            T("Thư mục này đã có bản cài VNText Studio. Tệp chương trình sẽ được sửa hoặc nâng cấp; thư mục data được giữ nguyên. Tiếp tục?",
                              "This folder already has a VNText Studio install. Program files will be repaired or upgraded; its data folder will be preserved. Continue?"),
                            T("Cài đặt VNText Studio", "VNText Studio Setup"), MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                            return;
                        try
                        {
                            var volume = new DriveInfo(Path.GetPathRoot(full));
                            if (payloadBytes > 0 && volume.AvailableFreeSpace < payloadBytes * 1.1)
                            { Warn(T("Ổ đĩa đã chọn không đủ dung lượng trống.", "The selected drive does not have enough free space.")); return; }
                        }
                        catch (Exception) { /* network or unusual volumes: the install itself reports a write failure */ }
                        root = full;
                        Go(1);
                        return;
                    }
                case 1:
                    {
                        if (menuNone.Checked) { menuRelative = null; Go(2); return; }
                        string relative;
                        var error = ValidateMenuFolder(menuFolder.Text, vi, ProgramsFolder(), out relative);
                        if (error != null) { Warn(error); return; }
                        menuRelative = relative;
                        Go(2);
                        return;
                    }
                case 2: Go(3); return;
                case 3: RunInstall(); return;
                case 5: if (!preparing) StartResources(); return;          // the page's primary button is "Retry" once a run has failed or was cancelled
                case 6:
                    ExitCode = 0;
                    if (launch.Checked) LaunchApp();
                    Close();
                    return;
            }
        }

        private void Warn(string text)
        {
            MessageBox.Show(text, T("Cài đặt VNText Studio", "VNText Studio Setup"), MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }

        private void LaunchApp()
        {
            try
            {
                var info = new ProcessStartInfo(Path.Combine(root, AppExecutableName)) { WorkingDirectory = root, UseShellExecute = false };
                Process.Start(info);
            }
            catch (Exception ex)
            {
                MessageBox.Show(T("Không mở được VNText Studio: ", "Could not start VNText Studio: ") + ex.Message,
                    T("Cài đặt VNText Studio", "VNText Studio Setup"), MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }

        private async void RunInstall()
        {
            installing = true;
            ControlBox = false;
            Go(4);
            installStatus.Text = T("Đang xác minh và cài đặt tệp. Việc này có thể mất vài phút; vui lòng chờ.", "Verifying and installing files. This may take a few minutes; please wait.");
            bar.Style = ProgressBarStyle.Marquee;
            var installRoot = root;
            var progress = new Action<int, string>(delegate(int percent, string name)
            {
                BeginInvoke(new Action(delegate
                {
                    if (bar.Style != ProgressBarStyle.Continuous) bar.Style = ProgressBarStyle.Continuous;
                    bar.Value = Math.Max(0, Math.Min(100, percent));
                    installStatus.Text = String.Format(T("Đang cài đặt tệp: {0}%", "Installing files: {0}%"), percent);
                    installFile.Text = name;
                }));
            });
            string failure = null;
            try
            {
                await Task.Run(delegate
                {
                    Directory.CreateDirectory(installRoot);
                    EnsureSafeDirectory(installRoot);
                    InstallPayload(installRoot, progress);
                });
            }
            catch (Exception ex) { failure = ex.Message; }
            installing = false;
            ControlBox = true;
            if (failure != null)
            {
                MessageBox.Show(T("Setup không cài được VNText Studio:\n", "Setup could not install VNText Studio:\n") + failure,
                    T("Cài đặt VNText Studio", "VNText Studio Setup"), MessageBoxButtons.OK, MessageBoxIcon.Error);
                ExitCode = 2;
                Close();
                return;
            }
            List<string> notes;
            try { notes = CreateShortcuts(installRoot, desktopShortcut.Checked ? Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory) : null, ProgramsFolder(), menuRelative, vi); }
            catch (Exception ex) { notes = new List<string>(); notes.Add(T("Không ghi được bản ghi lối tắt: ", "Could not record shortcuts: ") + ex.Message); }
            shortcutNotes = notes;
            ExitCode = 0;                // the files are installed; resource preparation below can fail without making the installation itself fail
            Go(5);
            StartResources();
        }

        private void RequestResourceCancel()
        {
            resourceCancel = true;
            cancel.Enabled = false;
            resStatus.Text = T("Đang hủy chuẩn bị tài nguyên…", "Cancelling resource preparation…");
        }

        private string ResourceItemName(string item)
        {
            switch (item)
            {
                case "model": return T("Mô hình dịch", "Translation model");
                case "renpy": return "Ren'Py SDK 8.5.3";
                case "ocr": return T("OCR của Windows", "Windows OCR");
                default: return item ?? "";
            }
        }

        private void ShowResourceProgress(long done, long total, string step, string item)
        {
            if (step != null && step.StartsWith("Tải Ren'Py SDK", StringComparison.Ordinal))
            {
                resStatus.Text = T("Đang tải Ren'Py SDK 8.5.3", "Downloading Ren'Py SDK 8.5.3");
                if (total > 0)
                {
                    if (resBar.Style != ProgressBarStyle.Continuous) resBar.Style = ProgressBarStyle.Continuous;
                    resBar.Value = (int)Math.Max(0, Math.Min(100, done * 100 / total));
                    resItem.Text = String.Format("{0:N1} / {1:N1} MB", done / 1048576.0, total / 1048576.0);
                }
                else resItem.Text = String.Format("{0:N1} MB", done / 1048576.0);
                return;
            }
            resStatus.Text = T("Đang kiểm tra các tài nguyên cần thiết…", "Checking the required resources…");
            resItem.Text = ResourceItemName(item);
        }

        /// <summary>The real resource step: a failed, cancelled or offline run never says "ready"; the person can retry or skip and finish.</summary>
        private async void StartResources()
        {
            preparing = true; resourceCancel = false; resourcesReady = false; resourceFailure = null;
            Go(5);
            next.Enabled = false;
            cancel.Visible = true; cancel.Enabled = true; cancel.Text = T("Hủy", "Cancel");
            next.Text = T("Tiếp tục ›", "Next >");
            resBar.Style = ProgressBarStyle.Marquee;
            resStatus.Text = T("Đang chuẩn bị các tài nguyên cần thiết…", "Preparing the required resources…");
            resItem.Text = "";
            resDetail.Text = T("Tài nguyên đã có sẵn trong bản cài sẽ được bỏ qua; các tệp cần tải được kiểm tra mã băm trước khi dùng.",
                "Resources already in the installation are skipped; files that need downloading are hash-checked before use.");
            var installRoot = root;
            var environment = new Dictionary<string, string>();
            string python, arguments, workDirectory;
            ResourceStepResult result;
            var startError = BuildResourceWorkerStart(installRoot, out python, out arguments, out workDirectory, environment);
            if (startError != null) result = new ResourceStepResult { Error = startError };
            else
            {
                var report = new Action<long, long, string, string>(delegate(long done, long total, string step, string item)
                {
                    BeginInvoke(new Action(delegate { ShowResourceProgress(done, total, step, item); }));
                });
                result = await Task.Run(delegate { return RunResourceWorker(python, arguments, workDirectory, environment, report, delegate { return resourceCancel; }, 120, 15); });
            }
            preparing = false;
            resBar.Style = ProgressBarStyle.Continuous;
            if (result.Ok)
            {
                resourcesReady = true;
                resBar.Value = 100;
                ShowDone();
                return;
            }
            resourceFailure = result.Cancelled ? T("Đã hủy chuẩn bị tài nguyên.", "Resource preparation was cancelled.")
                : String.IsNullOrWhiteSpace(result.Error) ? T("Không rõ nguyên nhân.", "The reason is unknown.") : result.Error.Trim();
            resBar.Value = 0;
            resStatus.Text = T("Tài nguyên chưa sẵn sàng", "Resources are not ready");
            resItem.Text = "";
            resDetail.Text = resourceFailure + Environment.NewLine + Environment.NewLine
                + T("Kiểm tra kết nối mạng rồi nhấn Thử lại, hoặc nhấn Bỏ qua để hoàn tất cài đặt và chuẩn bị sau trong Cài đặt › Dữ liệu.",
                    "Check your network connection and click Retry, or click Skip to finish the installation and prepare them later in Settings › Data.");
            next.Text = T("Thử lại", "Retry");
            next.Enabled = true;
            cancel.Text = T("Bỏ qua", "Skip");
            cancel.Enabled = true;
        }

        private void ShowDone()
        {
            var notes = new List<string>(shortcutNotes);
            notes.Insert(0, resourcesReady
                ? T("Tài nguyên cần thiết đã sẵn sàng.", "The required resources are ready.")
                : T("Tài nguyên chưa sẵn sàng: ", "Resources are not ready: ") + (resourceFailure ?? "")
                    + Environment.NewLine + T("Mở VNText Studio › Cài đặt › Dữ liệu để chuẩn bị lại.", "Open VNText Studio › Settings › Data to prepare them again."));
            doneText.Text = String.Format(T("VNText Studio đã được cài vào:\n{0}\n\nNhấn Hoàn tất để thoát Setup.", "VNText Studio was installed to:\n{0}\n\nClick Finish to exit Setup."), root);
            doneNotes.Text = String.Join(Environment.NewLine, notes.ToArray());
            Go(6);
        }
    }
#endif

    private static bool termsVietnamese;
    private static string TermsText(string vietnamese, string english) { return termsVietnamese ? vietnamese : english; }

    private static bool ConfirmIntelTerms()
    {
        using (var zipStream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Payload.zip"))
        {
            if (zipStream == null) throw new InvalidDataException("Setup payload is missing.");
            using (var zip = new ZipArchive(zipStream, ZipArchiveMode.Read))
            {
                var manifest = ReadManifest(zip);
                var termsEntry = VerifyPayloadEntry(zip, manifest, IntelTermsPath);
                var eulaEntry = VerifyPayloadEntry(zip, manifest, IntelEulaPath);
                string terms;
                byte[] eula;
                using (var reader = new StreamReader(termsEntry.Open(), Encoding.UTF8)) terms = reader.ReadToEnd();
                using (var input = eulaEntry.Open())
                using (var output = new MemoryStream()) { input.CopyTo(output); eula = output.ToArray(); }

                using (var form = new Form())
                using (var text = new RichTextBox())
                using (var accept = new Button())
                using (var decline = new Button())
                using (var viewEula = new Button())
                {
                    ConfigureInstallerFrame(form, "Intel oneAPI Redistributable Terms");
                    text.ReadOnly = true;
                    text.WordWrap = true;
                    text.Dock = DockStyle.Fill;
                    text.BorderStyle = BorderStyle.None;
                    text.BackColor = System.Drawing.Color.White;
                    text.Font = form.Font;
                    text.Text = terms;
                    accept.Text = TermsText("Chấp nhận và tiếp tục", "Accept and continue");
                    accept.DialogResult = DialogResult.Yes;
                    accept.AutoSize = true;
                    decline.Text = TermsText("Từ chối", "Decline");
                    decline.DialogResult = DialogResult.No;
                    decline.AutoSize = true;
                    viewEula.Text = TermsText("Xem thỏa thuận Intel gốc", "View original Intel agreement");
                    viewEula.AutoSize = true;
                    var buttons = InstallerFooter(accept, decline, viewEula);
                    var body = new Panel { Dock = DockStyle.Fill, Padding = new Padding(24, 16, 24, 16), BackColor = System.Drawing.Color.White };
                    body.Controls.Add(text);
                    form.Controls.Add(body);
                    form.Controls.Add(buttons);
                    form.Controls.Add(InstallerHeader("Intel oneAPI Redistributable Terms", TermsText("Hãy đọc điều khoản trước khi tiếp tục cài đặt VNText Studio.", "Read the terms before continuing with VNText Studio Setup.")));
                    accept.Name = "acceptIntelTerms";
                    decline.Name = "declineIntelTerms";
                    form.AcceptButton = accept;
                    form.CancelButton = decline;
                    viewEula.Click += delegate { ShowOriginalIntelEula(eula); };
                    return form.ShowDialog() == DialogResult.Yes;
                }
            }
        }
    }

    private static void ConfigureInstallerFrame(Form form, string title)
    {
        form.Text = title;
        form.Font = new System.Drawing.Font("Segoe UI", 9F);
        form.ClientSize = new System.Drawing.Size(640, 450);
        form.BackColor = System.Drawing.Color.FromArgb(240, 240, 240);
        form.StartPosition = FormStartPosition.CenterScreen;
        form.FormBorderStyle = FormBorderStyle.FixedDialog;
        form.MaximizeBox = false;
        form.ShowInTaskbar = true;
        try { form.Icon = System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }
    }

    private static Panel InstallerHeader(string title, string subtitle)
    {
        var panel = new Panel { Dock = DockStyle.Top, Height = 72, BackColor = System.Drawing.Color.White };
        panel.Controls.Add(new Label { Text = title, Left = 24, Top = 12, Width = 590, Height = 22,
            Font = new System.Drawing.Font("Segoe UI", 10.5F, System.Drawing.FontStyle.Bold) });
        panel.Controls.Add(new Label { Text = subtitle, Left = 40, Top = 38, Width = 570, Height = 22 });
        panel.Controls.Add(new Panel { Dock = DockStyle.Bottom, Height = 1, BackColor = System.Drawing.Color.FromArgb(208, 208, 208) });
        return panel;
    }

    private static Panel InstallerFooter(params Button[] buttons)
    {
        var footer = new Panel { Dock = DockStyle.Bottom, Height = 58, BackColor = System.Drawing.Color.FromArgb(240, 240, 240) };
        footer.Controls.Add(new Panel { Dock = DockStyle.Top, Height = 1, BackColor = System.Drawing.Color.FromArgb(0xD0, 0xD0, 0xD0) });
        var flow = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.RightToLeft, Padding = new Padding(14, 13, 14, 0),
            BackColor = System.Drawing.Color.FromArgb(240, 240, 240) };
        foreach (var button in buttons)
        {
            button.AutoSize = false;
            using (var measure = new System.Drawing.Font("Segoe UI", 9F))
                button.Size = new System.Drawing.Size(Math.Max(96, TextRenderer.MeasureText(button.Text, measure).Width + 32), 30);
            button.Margin = new Padding(8, 0, 0, 0);
            button.UseVisualStyleBackColor = true;
            flow.Controls.Add(button);
        }
        footer.Controls.Add(flow);
        return footer;
    }

    private static void ShowOriginalIntelEula(byte[] eula)
    {
        using (var form = new Form())
        using (var text = new RichTextBox())
        using (var close = new Button())
        using (var input = new MemoryStream(eula, false))
        {
            ConfigureInstallerFrame(form, "Intel End User License Agreement (Version August 2024)");
            text.ReadOnly = true;
            text.Dock = DockStyle.Fill;
            text.LoadFile(input, RichTextBoxStreamType.RichText);
            close.Text = TermsText("Đóng", "Close");
            close.DialogResult = DialogResult.OK;
            close.AutoSize = true;
            text.BorderStyle = BorderStyle.None;
            var body = new Panel { Dock = DockStyle.Fill, Padding = new Padding(24, 16, 24, 16), BackColor = System.Drawing.Color.White };
            body.Controls.Add(text);
            var buttons = InstallerFooter(close);
            form.Controls.Add(body);
            form.Controls.Add(buttons);
            form.Controls.Add(InstallerHeader("Intel End User License Agreement", TermsText("Thỏa thuận gốc — phiên bản tháng 8/2024", "Original agreement — Version August 2024")));
            form.AcceptButton = close;
            form.ShowDialog();
        }
    }

    private static void InstallPayload(string root, Action<int, string> report)
    {
        using (var zipStream = Assembly.GetExecutingAssembly().GetManifestResourceStream("Payload.zip"))
        {
            if (zipStream == null) throw new InvalidDataException("Setup payload is missing.");
            using (var zip = new ZipArchive(zipStream, ZipArchiveMode.Read))
            {
                var manifest = ReadManifest(zip);
                VerifyPayload(zip, manifest, root);
                var statePath = SafeTarget(root, InstallManifestName);
                var data = Path.Combine(root, "data");
                EnsureSafeDirectory(data);
                Directory.CreateDirectory(data);
                var previous = ReadInstallManifest(statePath, root);
                var previousSet = new HashSet<string>(previous, StringComparer.OrdinalIgnoreCase);
                var next = new List<string>(manifest.files.Keys);
                if (!next.Exists(delegate(string name) { return String.Equals(name, UpdateSourceName, StringComparison.OrdinalIgnoreCase); }))
                    next.Add(UpdateSourceName);
                var nextSet = new HashSet<string>(next, StringComparer.OrdinalIgnoreCase);
                foreach (var name in next)
                {
                    var target = SafeTarget(root, name);
                    if (File.Exists(target) && !previousSet.Contains(name))
                        throw new InvalidDataException("Install would overwrite a file not owned by the previous installation: " + name);
                }
                var combined = new List<string>(previous);
                var combinedSet = new HashSet<string>(previous, StringComparer.OrdinalIgnoreCase);
                foreach (var name in next)
                    if (combinedSet.Add(name)) combined.Add(name);
                WriteInstallManifest(statePath, combined);
                var copied = 0;
                var totalEntries = Math.Max(1, zip.Entries.Count);
                foreach (var entry in zip.Entries)
                {
                    copied++;
                    if (entry.FullName == ManifestName) continue;
                    if (report != null) report(copied * 100 / totalEntries, entry.FullName);
                    var target = SafeTarget(root, entry.FullName);
                    Directory.CreateDirectory(Path.GetDirectoryName(target));
                    using (var input = entry.Open())
                    using (var output = new FileStream(target, FileMode.Create, FileAccess.Write, FileShare.None))
                        input.CopyTo(output);
                }
                if (report != null) report(100, "");
                var obsolete = new List<string>();
                foreach (var name in previous)
                {
                    if (nextSet.Contains(name)) continue;
                    var target = SafeTarget(root, name);
                    if (IsUnderData(root, target)) continue;
                    if (File.Exists(target))
                    {
                        File.Delete(target);
                        obsolete.Add(name);
                    }
                }
                RemoveEmptyProgramDirectories(root, obsolete);
                WriteUpdateSource(root);
                WriteInstallManifest(statePath, next);
                var fullAppOwnershipPath = SafeTarget(root, FullAppOwnershipName);
                if (File.Exists(fullAppOwnershipPath)) File.Delete(fullAppOwnershipPath);
            }
        }
    }

    private static List<string> ReadInstallManifest(string path, string root)
    {
        var serializer = new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue };
        var names = new List<string>();
        var nameSet = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (File.Exists(path))
        {
            var installed = serializer.Deserialize<List<string>>(File.ReadAllText(path, Encoding.UTF8));
            if (installed == null) throw new InvalidDataException("Install manifest is invalid.");
            foreach (var name in installed)
            {
                SafeTarget(root, name);
                if (nameSet.Add(name)) names.Add(name);
            }
        }

        var ownershipPath = SafeTarget(root, FullAppOwnershipName);
        if (Directory.Exists(ownershipPath)) throw new InvalidDataException("Full-app ownership manifest path is a directory.");
        if (File.Exists(ownershipPath))
        {
            if (new FileInfo(ownershipPath).Length > 8 * 1024 * 1024)
                throw new InvalidDataException("Full-app ownership manifest is too large.");
            var updated = serializer.Deserialize<List<string>>(File.ReadAllText(ownershipPath, Encoding.UTF8));
            if (updated == null) throw new InvalidDataException("Full-app ownership manifest is invalid.");
            var updateSet = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            foreach (var name in updated)
            {
                if (!String.Equals(name, "VNText Studio.exe", StringComparison.OrdinalIgnoreCase)
                    && !name.StartsWith("app/", StringComparison.OrdinalIgnoreCase))
                    throw new InvalidDataException("Full-app ownership manifest contains a protected path: " + name);
                SafeTarget(root, name);
                if (!updateSet.Add(name)) throw new InvalidDataException("Full-app ownership manifest contains a duplicate path: " + name);
                if (nameSet.Add(name)) names.Add(name);
            }
        }
        return names;
    }

    private static void WriteInstallManifest(string path, List<string> names)
    {
        var serializer = new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue };
        var temp = path + ".tmp";
        if (File.Exists(temp) && (File.GetAttributes(temp) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException("Install manifest temporary path is a link: " + temp);
        File.WriteAllText(temp, serializer.Serialize(names), new UTF8Encoding(false));
        if (File.Exists(path)) File.Replace(temp, path, null);
        else File.Move(temp, path);
    }

    private static void WriteUpdateSource(string root)
    {
        var releaseRoot = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        if (String.IsNullOrEmpty(releaseRoot)) throw new InvalidDataException("Cannot resolve Setup source folder.");
        var updatesRoot = Path.GetFullPath(Path.Combine(releaseRoot, "Updates"));
        var sourcePath = SafeTarget(root, UpdateSourceName);
        var githubIdentity = ReadGitHubUpdateIdentity();
        var values = new Dictionary<string, object>
        {
            { "updates_root", updatesRoot },
            { "github_owner", githubIdentity[0] },
            { "github_repository", githubIdentity[1] },
            { "work_root", Path.Combine(root, ".update", "work") },
            { "backup_root", Path.Combine(root, ".update", "backup") },
            { "staging_root", Path.Combine(root, ".update", "staging") },
            { "updater_path", Path.Combine(root, ".update", "updater.exe") },
            { "log_path", Path.Combine(root, ".update", "update.log") },
            { "fault_inject_after_first_replace", false }
        };
        var temp = sourcePath + "." + Guid.NewGuid().ToString("N") + ".tmp";
        if (File.Exists(temp) && (File.GetAttributes(temp) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException("Update source temporary path is a link: " + temp);
        File.WriteAllText(temp, new JavaScriptSerializer().Serialize(values), new UTF8Encoding(false));
        if (File.Exists(sourcePath)) File.Replace(temp, sourcePath, null);
        else File.Move(temp, sourcePath);
    }

    private static string[] ReadGitHubUpdateIdentity()
    {
        using (var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(GitHubUpdateSourceResourceName))
        {
            if (stream == null) return new[] { "", "" };
            using (var reader = new StreamReader(stream, Encoding.UTF8))
            {
                var values = new JavaScriptSerializer().Deserialize<Dictionary<string, string>>(reader.ReadToEnd());
                var owner = values != null && values.ContainsKey("owner") ? values["owner"] ?? "" : "";
                var repository = values != null && values.ContainsKey("repository") ? values["repository"] ?? "" : "";
                if (owner.Length == 0 && repository.Length == 0) return new[] { "", "" };
                if (!IsValidGitHubIdentity(owner, repository))
                    throw new InvalidDataException("Embedded GitHub update identity is invalid.");
                return new[] { owner, repository };
            }
        }
    }

    private static bool IsValidGitHubIdentity(string owner, string repository)
    {
        if (String.IsNullOrEmpty(owner) || owner.Length > 39 || !IsAsciiAlphaNumeric(owner[0]) || !IsAsciiAlphaNumeric(owner[owner.Length - 1]))
            return false;
        for (var i = 0; i < owner.Length; i++)
            if (!IsAsciiAlphaNumeric(owner[i]) && owner[i] != '-') return false;
        if (String.IsNullOrEmpty(repository) || repository.Length > 100 || !IsAsciiAlphaNumeric(repository[0]) || !IsAsciiAlphaNumeric(repository[repository.Length - 1]))
            return false;
        for (var i = 0; i < repository.Length; i++)
            if (!IsAsciiAlphaNumeric(repository[i]) && repository[i] != '.' && repository[i] != '_' && repository[i] != '-') return false;
        return repository != "." && repository != "..";
    }

    private static bool IsAsciiAlphaNumeric(char value)
    {
        return (value >= 'A' && value <= 'Z') || (value >= 'a' && value <= 'z') || (value >= '0' && value <= '9');
    }

    private static bool IsUnderData(string root, string path)
    {
        var data = Path.GetFullPath(Path.Combine(root, "data"));
        var fullPath = Path.GetFullPath(path);
        return String.Equals(fullPath, data, StringComparison.OrdinalIgnoreCase)
            || fullPath.StartsWith(data.TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase);
    }

    private static void RemoveEmptyProgramDirectories(string root, List<string> names)
    {
        var rootPath = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
        var candidates = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var name in names)
        {
            var dir = Path.GetDirectoryName(SafeTarget(root, name));
            while (!String.IsNullOrEmpty(dir) && dir.StartsWith(rootPath, StringComparison.OrdinalIgnoreCase))
            {
                if (!IsUnderData(root, dir)) candidates.Add(dir);
                dir = Path.GetDirectoryName(dir);
            }
        }
        var ordered = new List<string>(candidates);
        ordered.Sort(delegate(string a, string b) { return b.Length.CompareTo(a.Length); });
        foreach (var dir in ordered)
        {
            if (!Directory.Exists(dir)) continue;
            var entries = Directory.GetFileSystemEntries(dir);
            if (entries.Length == 0) Directory.Delete(dir, false);
        }
    }

    private static PayloadManifest ReadManifest(ZipArchive zip)
    {
        var found = zip.GetEntry(ManifestName);
        if (found == null) throw new InvalidDataException("Setup payload manifest is missing.");
        using (var input = found.Open())
        using (var reader = new StreamReader(input, Encoding.UTF8))
        {
            var serializer = new JavaScriptSerializer { MaxJsonLength = Int32.MaxValue };
            var manifest = serializer.Deserialize<PayloadManifest>(reader.ReadToEnd());
            if (manifest == null || manifest.schema != 1 || manifest.files == null)
                throw new InvalidDataException("Setup payload manifest is invalid.");
            return manifest;
        }
    }

    private static void VerifyPayload(ZipArchive zip, PayloadManifest manifest, string root)
    {
        var entries = new Dictionary<string, ZipArchiveEntry>(StringComparer.OrdinalIgnoreCase);
        var manifestCount = 0;
        foreach (var entry in zip.Entries)
        {
            if (entry.FullName == ManifestName) { manifestCount++; continue; }
            if (!String.Equals(entry.FullName, "VNText Studio.exe", StringComparison.OrdinalIgnoreCase)
                && !String.Equals(entry.FullName, "Uninstall.exe", StringComparison.OrdinalIgnoreCase)
                && !entry.FullName.StartsWith("app/", StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Payload files must be in app/ except the main executable and Uninstall.exe: " + entry.FullName);
            SafeTarget(root, entry.FullName);
            if (entries.ContainsKey(entry.FullName)) throw new InvalidDataException("Duplicate Setup payload path: " + entry.FullName);
            entries.Add(entry.FullName, entry);
        }
        if (manifestCount != 1) throw new InvalidDataException("Setup payload manifest is duplicated.");
        if (entries.Count != manifest.files.Count) throw new InvalidDataException("Setup payload inventory mismatch.");
        foreach (var pair in manifest.files)
        {
            SafeTarget(root, pair.Key);
            ZipArchiveEntry entry;
            if (!entries.TryGetValue(pair.Key, out entry)) throw new InvalidDataException("Payload file missing: " + pair.Key);
            VerifyPayloadEntry(entry, pair.Value, pair.Key);
        }
    }

    private static ZipArchiveEntry VerifyPayloadEntry(ZipArchive zip, PayloadManifest manifest, string relative)
    {
        PayloadFile expected;
        if (!manifest.files.TryGetValue(relative, out expected))
            throw new InvalidDataException("Payload manifest entry missing: " + relative);
        var entry = zip.GetEntry(relative);
        if (entry == null) throw new InvalidDataException("Payload file missing: " + relative);
        VerifyPayloadEntry(entry, expected, relative);
        return entry;
    }

    private static void VerifyPayloadEntry(ZipArchiveEntry entry, PayloadFile expected, string relative)
    {
        using (var input = entry.Open())
        using (var sha = SHA256.Create())
        {
            var hash = BitConverter.ToString(sha.ComputeHash(input)).Replace("-", "").ToLowerInvariant();
            if (entry.Length != expected.size || hash != (expected.sha256 ?? "").ToLowerInvariant())
                throw new InvalidDataException("Payload hash mismatch: " + relative);
        }
    }

    private static string SafeTarget(string root, string relative)
    {
        if (String.IsNullOrEmpty(relative) || Path.IsPathRooted(relative) || relative.IndexOf(':') >= 0 || relative.IndexOf('\\') >= 0)
            throw new InvalidDataException("Unsafe payload path: " + relative);
        foreach (var part in relative.Split('/'))
            if (part.Length == 0 || part == "." || part == "..") throw new InvalidDataException("Unsafe payload path: " + relative);
        var normalizedRoot = Path.GetFullPath(root);
        var volumeRoot = Path.GetPathRoot(normalizedRoot) ?? "";
        if (normalizedRoot.Length > volumeRoot.Length)
            normalizedRoot = normalizedRoot.TrimEnd(Path.DirectorySeparatorChar);
        var fullRoot = normalizedRoot + (normalizedRoot.EndsWith(Path.DirectorySeparatorChar.ToString(), StringComparison.Ordinal) ? "" : Path.DirectorySeparatorChar.ToString());
        var target = Path.GetFullPath(Path.Combine(fullRoot, relative.Replace('/', Path.DirectorySeparatorChar)));
        if (!target.StartsWith(fullRoot, StringComparison.OrdinalIgnoreCase)) throw new InvalidDataException("Payload escapes install folder.");
        EnsureSafeDirectory(normalizedRoot);
        var current = normalizedRoot;
        var parts = relative.Replace('/', Path.DirectorySeparatorChar).Split(Path.DirectorySeparatorChar);
        for (var i = 0; i < parts.Length; i++)
        {
            current = Path.Combine(current, parts[i]);
            if (Directory.Exists(current)) EnsureSafeDirectory(current);
            else if (File.Exists(current) && (File.GetAttributes(current) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Payload target is a link and cannot be replaced: " + current);
        }
        return target;
    }

    private static void EnsureSafeDirectory(string path)
    {
        if (!Directory.Exists(path)) return;
        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
            throw new InvalidDataException("Install path contains a directory link; choose a regular folder: " + path);
    }

    // Uninstall speaks the person's language (Vietnamese or English, from the Windows UI language or /lang=vi|en) and uses the SAME installer frame as the Setup
    // wizard: white header with a rule, grey body, footer with a rule and 96x30 buttons, Segoe UI 9, the standard green progress bar.  The engineering
    // heartbeat is still measured (a hidden control, and a line in the temp log for a real uninstall) but is never part of what the person reads.
    private static bool uninstallVietnamese = String.Equals(System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName, "vi", StringComparison.OrdinalIgnoreCase);

    private static string U(string vietnamese, string english) { return uninstallVietnamese ? vietnamese : english; }

    private static void ApplyUninstallLanguage(string[] args)
    {
        if (args == null) return;
        foreach (var arg in args)
        {
            if (String.Equals(arg, "/lang=vi", StringComparison.OrdinalIgnoreCase) || String.Equals(arg, "--lang=vi", StringComparison.OrdinalIgnoreCase)) uninstallVietnamese = true;
            if (String.Equals(arg, "/lang=en", StringComparison.OrdinalIgnoreCase) || String.Equals(arg, "--lang=en", StringComparison.OrdinalIgnoreCase)) uninstallVietnamese = false;
        }
    }

    /// <summary>An uninstall message in the installer frame (instead of a bare system message box).</summary>
    private static void ShowUninstallMessage(string title, string subtitle, string text)
    {
        using (var form = new Form())
        using (var close = new Button { Text = U("Đóng", "Close"), DialogResult = DialogResult.OK })
        {
            ConfigureInstallerFrame(form, U("Gỡ cài đặt — VNText Studio", "Uninstall — VNText Studio"));
            var body = new Panel { Dock = DockStyle.Fill, BackColor = System.Drawing.Color.FromArgb(240, 240, 240) };
            body.Controls.Add(new Label { Left = 24, Top = 28, Width = 580, Height = 300, AutoSize = false, Text = text });
            form.Controls.Add(body);
            form.Controls.Add(InstallerFooter(close));
            form.Controls.Add(InstallerHeader(title, subtitle));
            form.AcceptButton = close; form.CancelButton = close;
            form.ShowDialog();
        }
    }

    private static int Uninstall(string[] args)
    {
        ApplyUninstallLanguage(args);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        var selfPath = Path.GetFullPath(Assembly.GetExecutingAssembly().Location);
        var root = Path.GetDirectoryName(selfPath);
        var volume = Path.GetPathRoot(root);
        if (String.Equals(root.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
            volume.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar), StringComparison.OrdinalIgnoreCase))
        {
            ShowUninstallMessage(U("Không thể gỡ cài đặt", "Cannot uninstall"), U("Thư mục không hợp lệ.", "The folder is not valid."),
                U("Không thể gỡ cài đặt khỏi thư mục gốc của ổ đĩa.", "Uninstall cannot run from the root folder of a drive."));
            return 2;
        }

        if (!ConfirmUninstall(root))
            return 1;

        try
        {
            EnsureSafeDirectory(root);
            RemoveRecordedShortcuts(root, Environment.GetFolderPath(Environment.SpecialFolder.Programs));
            using (var progress = CreateUninstallProgressForm(
                root, selfPath, Process.GetCurrentProcess().Id, true, null))
            {
                Application.Run(progress);
                return Convert.ToInt32(progress.Tag);
            }
        }
        catch (Exception ex)
        {
            ShowUninstallMessage(U("Không thể gỡ cài đặt", "Cannot uninstall"), U("Gỡ cài đặt chưa bắt đầu.", "Uninstall did not start."),
                U("Không thể gỡ cài đặt:", "Uninstall could not run:") + Environment.NewLine + Environment.NewLine + ex.Message);
            return 2;
        }
    }

    private static bool ConfirmUninstall(string root)
    {
        using (var form = new Form())
        using (var yes = new Button { Text = U("Gỡ cài đặt", "Uninstall"), DialogResult = DialogResult.Yes })
        using (var no = new Button { Text = U("Hủy", "Cancel"), DialogResult = DialogResult.No })
        {
            ConfigureInstallerFrame(form, U("Gỡ cài đặt — VNText Studio", "Uninstall — VNText Studio"));
            var message = new Label { Left = 24, Top = 28, Width = 580, Height = 300, AutoSize = false,
                Text = U("Gỡ cài đặt sẽ xóa mọi nội dung trong thư mục này, bao gồm dữ liệu trong data/. " +
                    "Sau khi hoàn tất, thư mục cài đặt vẫn còn nhưng trống:\n\n" + root +
                    "\n\nKhông thể khôi phục. Bạn có muốn tiếp tục?",
                    "Uninstall removes everything in this folder, including the data in data/. " +
                    "When it finishes, the install folder remains but is empty:\n\n" + root +
                    "\n\nThis cannot be undone. Do you want to continue?") };
            var body = new Panel { Dock = DockStyle.Fill, BackColor = System.Drawing.Color.FromArgb(240, 240, 240) };
            body.Controls.Add(message);
            form.Controls.Add(body);
            form.Controls.Add(InstallerFooter(no, yes));      // right-to-left: Cancel is the right-most button, as in the Setup wizard
            form.Controls.Add(InstallerHeader(U("Gỡ cài đặt VNText Studio", "Uninstall VNText Studio"),
                U("Kiểm tra thư mục và dữ liệu trước khi tiếp tục.", "Check the folder and its data before continuing.")));
            // Enter and Escape are both safe until the user explicitly chooses removal.
            form.AcceptButton = no; form.CancelButton = no;
            return form.ShowDialog() == DialogResult.Yes;
        }
    }

    private static Form CreateUninstallProgressForm(string root, string selfPath, int parentPid,
        bool launchFinalHelper, IList<Dictionary<string, object>> progressEvidence)
    {
        var form = new Form();
        ConfigureInstallerFrame(form, U("Gỡ cài đặt — VNText Studio", "Uninstall — VNText Studio"));
        form.ControlBox = false;
        var header = InstallerHeader(U("Đang gỡ cài đặt VNText Studio", "Uninstalling VNText Studio"),
            U("Vui lòng chờ trong khi ứng dụng được gỡ khỏi máy.", "Please wait while the app is removed from your computer."));
        var body = new Panel { Dock = DockStyle.Fill, BackColor = System.Drawing.Color.FromArgb(240, 240, 240) };
        var phaseLabel = new Label { Name = "progressStatus", Left = 24, Top = 40, Width = 580, Height = 44, AutoSize = false,
            Text = U("Đang quét thư mục cài đặt…", "Scanning the install folder…") };
        var progress = new ProgressBar { Name = "progressBar", Left = 24, Top = 96, Width = 580, Height = 22, Minimum = 0, Maximum = 100,
            Style = ProgressBarStyle.Marquee };
        var pathLabel = new Label { Name = "uninstallPath", Left = 24, Top = 130, Width = 580, Height = 22, AutoSize = false, AutoEllipsis = true, Text = root };
        var messageLabel = new Label { Name = "uninstallMessage", Left = 24, Top = 164, Width = 580, Height = 44, AutoSize = false,
            Text = U("Đang liệt kê các tệp trong thư mục cài đặt.", "Listing the files in the install folder.") };
        // Only shown for a blocked or failed uninstall: the files that were in use, or the technical reason.  Same style as the Setup summary box.
        var details = new TextBox { Name = "uninstallDetails", Left = 24, Top = 214, Width = 582, Height = 170, Multiline = true, ReadOnly = true,
            ScrollBars = ScrollBars.Vertical, BackColor = System.Drawing.Color.White, Visible = false };
        var heartbeat = new Label { Name = "uninstallHeartbeat", Visible = false };
        var close = new Button { Name = "closeUninstall", Text = U("Đóng", "Close"), Enabled = false };
        body.Controls.Add(phaseLabel);
        body.Controls.Add(progress);
        body.Controls.Add(pathLabel);
        body.Controls.Add(messageLabel);
        body.Controls.Add(details);
        body.Controls.Add(heartbeat);
        form.Controls.Add(body);
        form.Controls.Add(InstallerFooter(close));
        form.Controls.Add(header);
        var headerTitle = (Label)header.Controls[0];
        var headerSubtitle = (Label)header.Controls[1];

        form.Tag = 2;
        var terminal = false;
        var phase = "scanning";
        var phaseClock = Stopwatch.StartNew();
        var totalClock = Stopwatch.StartNew();
        var lastTick = Stopwatch.GetTimestamp();
        var heartbeatCount = 0;
        long maxTickGapMs = 0;
        var worker = new BackgroundWorker { WorkerReportsProgress = true };
        var timer = new System.Windows.Forms.Timer { Interval = 250 };
        timer.Tick += delegate
        {
            var now = Stopwatch.GetTimestamp();
            var gap = (long)(1000.0 * (now - lastTick) / Stopwatch.Frequency);
            if (gap > maxTickGapMs) maxTickGapMs = gap;
            lastTick = now;
            heartbeatCount++;
            heartbeat.Text = String.Format("UI heartbeat: {0}; max delay: {1} ms; total: {2:c}; phase: {3:c}",
                heartbeatCount, maxTickGapMs, totalClock.Elapsed, phaseClock.Elapsed);
            if (!launchFinalHelper && terminal && heartbeatCount >= 2) close.PerformClick();
        };
        timer.Start();

        Action<string> showFailure = delegate(string kind)
        {
            headerTitle.Text = U("Gỡ cài đặt chưa hoàn tất", "Uninstall did not finish");
            headerSubtitle.Text = U("Xem chi tiết bên dưới rồi thử lại.", "See the details below, then try again.");
            phaseLabel.Text = kind == "blocked" ? U("Chưa thể gỡ cài đặt", "Uninstall cannot continue yet") : U("Gỡ cài đặt dừng giữa chừng", "Uninstall stopped part-way");
            messageLabel.Text = kind == "blocked"
                ? U("Chưa có tệp nào bị xóa. Hãy đóng các chương trình đang dùng các tệp bên dưới rồi chạy lại Uninstall.exe.",
                    "No files were removed. Close the programs that are using the files below, then run Uninstall.exe again.")
                : U("Một số tệp có thể đã bị xóa. Chi tiết kỹ thuật ở bên dưới.", "Some files may already be removed. The technical details are below.");
            details.Visible = true;
        };

        worker.DoWork += delegate(object sender, DoWorkEventArgs e)
        {
            RemoveUninstallContents(root, selfPath, (BackgroundWorker)sender);
        };
        worker.ProgressChanged += delegate(object sender, ProgressChangedEventArgs e)
        {
            var update = (Dictionary<string, object>)e.UserState;
            if (progressEvidence != null) progressEvidence.Add(update);
            var nextPhase = (string)update["phase"];
            if (nextPhase != phase)
            {
                phase = nextPhase;
                phaseClock.Restart();
            }
            var done = Convert.ToInt32(update["done"]);
            var total = Convert.ToInt32(update["total"]);
            pathLabel.Text = (string)update["path"];
            if (phase == "scanning")
            {
                phaseLabel.Text = String.Format(U("Đang quét: {0} mục đã tìm thấy", "Scanning: {0} items found"), done);
                progress.Style = ProgressBarStyle.Marquee;
            }
            else
            {
                progress.Style = ProgressBarStyle.Continuous;
                progress.Maximum = Math.Max(1, total);
                progress.Value = Math.Min(progress.Maximum, Math.Max(0, done));
                if (phase == "checking")
                {
                    phaseLabel.Text = String.Format(U("Đang kiểm tra tệp đang được sử dụng: {0}/{1}", "Checking for files in use: {0}/{1}"), done, total);
                    messageLabel.Text = U("Đang bảo đảm không có chương trình nào đang dùng các tệp trước khi xóa.", "Making sure no program is using the files before anything is removed.");
                }
                else if (phase == "deleting")
                {
                    phaseLabel.Text = String.Format(U("Đang xóa: {0}/{1} mục", "Deleting: {0}/{1} items"), done, total);
                    messageLabel.Text = U("Đang xóa các tệp của VNText Studio, kể cả dữ liệu trong data/.", "Removing the VNText Studio files, including the data in data/.");
                }
                else if (phase == "handoff") phaseLabel.Text = U("Đang chuyển bước cuối cho trình trợ giúp bên ngoài.", "Handing the last step to the external helper.");
                else if (phase == "blocked")
                {
                    var text = (string)update["message"];
                    var separator = text.IndexOf(Environment.NewLine, StringComparison.Ordinal);
                    details.Text = separator >= 0 ? text.Substring(separator + Environment.NewLine.Length) : text;     // the files in use, one per line
                    showFailure("blocked");
                }
                else if (phase == "failed")
                {
                    details.Text = (string)update["message"];
                    showFailure("failed");
                }
            }
        };
        worker.RunWorkerCompleted += delegate(object sender, RunWorkerCompletedEventArgs e)
        {
            if (e.Error != null)
            {
                form.Tag = 2;
                if (phase != "blocked" && phase != "failed")
                {
                    phase = "failed";
                    phaseClock.Restart();
                    details.Text = e.Error.ToString();
                    showFailure("failed");
                }
                progress.Style = ProgressBarStyle.Continuous;
            }
            else
            {
                try
                {
                    if (launchFinalHelper)
                    {
                        var command = BuildUninstallCleanupCommand(root, parentPid, selfPath);
                        var encoded = Convert.ToBase64String(Encoding.Unicode.GetBytes(command));
                        var powershell = Path.Combine(Environment.SystemDirectory, "WindowsPowerShell\\v1.0\\powershell.exe");
                        if (!File.Exists(powershell)) throw new FileNotFoundException("Windows PowerShell is unavailable.", powershell);
                        var start = new ProcessStartInfo(powershell, "-NoProfile -WindowStyle Hidden -EncodedCommand " + encoded)
                        {
                            WindowStyle = ProcessWindowStyle.Hidden,
                            CreateNoWindow = true,
                            UseShellExecute = false,
                            WorkingDirectory = Environment.SystemDirectory
                        };
                        if (Process.Start(start) == null) throw new InvalidOperationException("The final uninstall helper did not start.");
                    }
                    form.Tag = 0;
                    phase = "handoff";
                    phaseClock.Restart();
                    headerTitle.Text = U("Hoàn tất gỡ cài đặt", "Uninstall complete");
                    headerSubtitle.Text = U("VNText Studio đã được gỡ khỏi máy.", "VNText Studio was removed from your computer.");
                    phaseLabel.Text = U("Đã gỡ cài đặt VNText Studio", "VNText Studio was uninstalled");
                    progress.Style = ProgressBarStyle.Continuous;
                    progress.Maximum = 100; progress.Value = 100;
                    pathLabel.Text = root;
                    messageLabel.Text = U("Đã dọn nội dung; trình trợ giúp cuối sẽ xóa Uninstall.exe. Thư mục cài đặt vẫn còn nhưng trống.",
                        "The contents were removed; a final helper deletes Uninstall.exe. The install folder remains but is empty.");
                }
                catch (Exception ex)
                {
                    form.Tag = 2;
                    phase = "failed";
                    phaseClock.Restart();
                    details.Text = ex.ToString();
                    showFailure("failed");
                    phaseLabel.Text = U("Không thể chuyển bước xóa tệp cuối cùng", "The last cleanup step could not start");
                    progress.Style = ProgressBarStyle.Continuous;
                }
            }
            if (launchFinalHelper)
            {
                // The measurements the person does not need still go somewhere: one line per uninstall in the temp folder (the install folder is being removed).
                try
                {
                    File.AppendAllText(Path.Combine(Path.GetTempPath(), "VNTextStudio-uninstall.log"),
                        DateTime.Now.ToString("s") + " exit=" + Convert.ToInt32(form.Tag) + " phase=" + phase + " | " + heartbeat.Text
                        + (details.Text.Length > 0 ? " | " + details.Text.Replace(Environment.NewLine, " / ") : "") + Environment.NewLine, Encoding.UTF8);
                }
                catch (Exception) { /* diagnostics only */ }
            }
            terminal = true;
            close.Enabled = true;
        };
        close.Click += delegate { form.Close(); };
        form.FormClosing += delegate(object sender, FormClosingEventArgs e)
        {
            if (!terminal) e.Cancel = true;
        };
        form.Shown += delegate { worker.RunWorkerAsync(); };
        form.FormClosed += delegate
        {
            timer.Stop();
            worker.Dispose();
            timer.Dispose();
        };
        return form;
    }

    private static void RemoveUninstallContents(string root, string selfPath, BackgroundWorker worker)
    {
        var entries = new List<string>();
        var targets = new List<string>();
        var locked = new List<string>();
        var phaseClock = Stopwatch.StartNew();
        var phase = "scanning";
        var currentPath = Path.GetFullPath(root);
        var deleted = 0;
        var total = 0;
        var blocked = false;
        try
        {
            root = Path.GetFullPath(root);
            selfPath = Path.GetFullPath(selfPath);
            var volume = Path.GetPathRoot(root);
            if (String.Equals(root.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
                volume.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar), StringComparison.OrdinalIgnoreCase))
                throw new InvalidDataException("Refusing to uninstall a drive root.");
            if (!Directory.Exists(root)) throw new DirectoryNotFoundException("Install folder does not exist: " + root);
            EnsureSafeDirectory(root);

            ReportUninstallProgress(worker, phase, 0, 0, root, "Scanning the install folder.", phaseClock);
            ScanUninstallEntries(root, entries, worker, phaseClock, ref currentPath);
            ReportUninstallProgress(worker, phase, entries.Count, 0, currentPath, "Scan complete; checking files for active locks.", phaseClock);
            foreach (var entry in entries)
                if (!String.Equals(Path.GetFullPath(entry), selfPath, StringComparison.OrdinalIgnoreCase))
                    targets.Add(entry);

            phase = "checking";
            phaseClock.Restart();
            total = targets.Count;
            var checkedCount = 0;
            foreach (var entry in targets)
            {
                currentPath = entry;
                var attributes = File.GetAttributes(entry);
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidDataException("Link/reparse point appeared during preflight: " + entry);
                if ((attributes & FileAttributes.Directory) == 0)
                {
                    try
                    {
                        using (new FileStream(entry, FileMode.Open, FileAccess.Read, FileShare.None)) { }
                    }
                    catch (Exception ex)
                    {
                        locked.Add(entry + ": " + ex.Message);
                    }
                }
                checkedCount++;
                if (ShouldReportUninstallProgress(checkedCount, total))
                    ReportUninstallProgress(worker, phase, checkedCount, total, entry, "Checking files for active locks.", phaseClock);
            }
            if (locked.Count > 0)
            {
                blocked = true;
                phase = "blocked";
                phaseClock.Restart();
                var message = "No files were removed. Close programs using these files, then run Uninstall.exe again:" +
                    Environment.NewLine + String.Join(Environment.NewLine, locked.ToArray());
                ReportUninstallProgress(worker, phase, checkedCount, total, root, message, phaseClock);
                throw new IOException(message);
            }

            phase = "deleting";
            phaseClock.Restart();
            foreach (var entry in targets)
            {
                currentPath = entry;
                var attributes = File.GetAttributes(entry);
                if ((attributes & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidDataException("Link/reparse point appeared during deletion: " + entry);
                if ((attributes & FileAttributes.Directory) != 0) Directory.Delete(entry, false);
                else
                {
                    File.SetAttributes(entry, FileAttributes.Normal);
                    File.Delete(entry);
                }
                deleted++;
                if (ShouldReportUninstallProgress(deleted, total))
                    ReportUninstallProgress(worker, phase, deleted, total, entry, "Deleted this item.", phaseClock);
            }
            phase = "handoff";
            phaseClock.Restart();
            ReportUninstallProgress(worker, phase, deleted, total, root,
                "All descendants and data are removed; the external helper will delete Uninstall.exe and the empty root after this process exits.",
                phaseClock);
        }
        catch (Exception ex)
        {
            if (!blocked)
            {
                var failedPhase = phase;
                phase = "failed";
                var message = failedPhase == "deleting"
                    ? String.Format("Uninstall stopped after {0} of {1} items at {2}. Some files may already be removed.{3}{4}",
                        deleted, total, currentPath, Environment.NewLine, ex)
                    : String.Format("Uninstall stopped before deleting files at {0}.{1}{2}", currentPath, Environment.NewLine, ex);
                ReportUninstallProgress(worker, phase, deleted, total, currentPath, message, phaseClock);
                throw new IOException(message, ex);
            }
            throw;
        }
    }

    private static void ScanUninstallEntries(string directory, List<string> entries, BackgroundWorker worker,
        Stopwatch phaseClock, ref string currentPath)
    {
        foreach (var entry in Directory.EnumerateFileSystemEntries(directory))
        {
            currentPath = entry;
            var attributes = File.GetAttributes(entry);
            if ((attributes & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("Link/reparse point blocks uninstall: " + entry);
            if ((attributes & FileAttributes.Directory) != 0)
                ScanUninstallEntries(entry, entries, worker, phaseClock, ref currentPath);
            entries.Add(entry);
            if (ShouldReportUninstallProgress(entries.Count, 0))
                ReportUninstallProgress(worker, "scanning", entries.Count, 0, entry, "Scanning the install folder.", phaseClock);
        }
    }

    private static bool ShouldReportUninstallProgress(int done, int total)
    {
        if (total <= 0) return done % 256 == 0;
        var step = Math.Max(1, (total + 99) / 100);
        return done == 1 || done == total || done % step == 0;
    }

    private static void ReportUninstallProgress(BackgroundWorker worker, string phase, int done, int total,
        string path, string message, Stopwatch phaseClock)
    {
        worker.ReportProgress(0, new Dictionary<string, object>
        {
            { "phase", phase }, { "done", done }, { "total", total }, { "path", path },
            { "message", message }, { "elapsedMilliseconds", phaseClock.ElapsedMilliseconds }
        });
    }

    private static string BuildUninstallCleanupCommand(string root, int parentPid, string selfPath)
    {
        return @"
$ErrorActionPreference = 'Stop'
$root = __ROOT__
$selfPath = __SELF__
$parentPid = __PID__
try {
    try {
        $parent = [Diagnostics.Process]::GetProcessById($parentPid)
        $parent.WaitForExit()
        $parent.Dispose()
    } catch [ArgumentException] { }
    if (-not [IO.Directory]::Exists($root)) { throw ('Install folder does not exist: ' + $root) }
    if (([IO.File]::GetAttributes($root) -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Install root became a link.' }
    $volume = [IO.Path]::GetPathRoot($root)
    $trimmedRoot = $root.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    $trimmedVolume = $volume.TrimEnd([IO.Path]::DirectorySeparatorChar, [IO.Path]::AltDirectorySeparatorChar)
    if ([string]::Equals($trimmedRoot, $trimmedVolume, [StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing to uninstall a drive root.' }
    $remaining = [IO.Directory]::GetFileSystemEntries($root)
    if ($remaining.Length -ne 1 -or -not [string]::Equals([IO.Path]::GetFullPath($remaining[0]), $selfPath, [StringComparison]::OrdinalIgnoreCase)) {
        throw ('Unexpected item appeared during final cleanup. Uninstall.exe was not removed: ' + $root)
    }
    if (-not [IO.File]::Exists($selfPath) -or [IO.Directory]::Exists($selfPath)) { throw 'Expected Uninstall.exe is missing or is not a regular file.' }
    if (([IO.File]::GetAttributes($selfPath) -band ([IO.FileAttributes]::Directory -bor [IO.FileAttributes]::ReparsePoint)) -ne 0) { throw 'Uninstall.exe became a directory or link.' }
    [IO.File]::Delete($selfPath)
    if (-not [IO.Directory]::Exists($root)) { throw ('Install folder disappeared: ' + $root) }
    $rootAttributes = [IO.File]::GetAttributes($root)
    if (($rootAttributes -band [IO.FileAttributes]::Directory) -eq 0) { throw ('Install root is no longer a directory: ' + $root) }
    if (($rootAttributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Install root became a link after final cleanup.' }
    if ([IO.Directory]::GetFileSystemEntries($root).Length -ne 0) { throw ('Install folder is not empty after final cleanup: ' + $root) }
} catch {
    Add-Type -AssemblyName System.Windows.Forms
    [void][Windows.Forms.MessageBox]::Show(('Final uninstall cleanup failed; the install folder may not be empty:' + [Environment]::NewLine + $root + [Environment]::NewLine + $_.Exception.Message), 'Gỡ cài đặt VNText Studio', 'OK', 'Error')
    exit 1
}
exit 0
".Replace("__ROOT__", PowerShellLiteral(Path.GetFullPath(root)))
            .Replace("__SELF__", PowerShellLiteral(Path.GetFullPath(selfPath)))
            .Replace("__PID__", parentPid.ToString());
    }
    private static string PowerShellLiteral(string value)
    {
        return "'" + value.Replace("'", "''") + "'";
    }

    private static string HashFileSha256(string path)
    {
        using (var sha = SHA256.Create())
        using (var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }
}
