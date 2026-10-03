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
        return Uninstall();
#else
        return Install();
#endif
    }

    private static int Install()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        bool accepted;
        try { accepted = ConfirmIntelTerms(); }
        catch (Exception ex)
        {
            MessageBox.Show("Setup could not verify the Intel terms in its payload:\n" + ex.Message,
                "VNText Studio Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }
        if (!accepted) return 1;
        using (var owner = new Form())
        using (var picker = new FolderBrowserDialog())
        {
            owner.Text = "VNText Studio Setup";
            owner.Width = 440;
            owner.Height = 165;
            owner.FormBorderStyle = FormBorderStyle.FixedDialog;
            owner.StartPosition = FormStartPosition.CenterScreen;
            owner.MaximizeBox = false;
            owner.ShowInTaskbar = true;
            owner.Controls.Add(new Label { Left = 18, Top = 18, Width = 390,
                Text = "Choose the folder where VNText Studio will be installed." });
            var choose = new Button { Left = 18, Top = 55, Width = 150, Height = 30,
                Text = "Choose folder..." };
            owner.Controls.Add(choose);
            picker.Description = "Choose the VNText Studio install folder. App data will be kept in its data subfolder.";
            picker.ShowNewFolderButton = true;
            picker.SelectedPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "VNText Studio");
            choose.Click += delegate
            {
                if (picker.ShowDialog(owner) != DialogResult.OK) return;
                owner.Tag = picker.SelectedPath;
                owner.DialogResult = DialogResult.OK;
            };
            if (owner.ShowDialog() != DialogResult.OK) return 1;
            var root = Path.GetFullPath((string)owner.Tag);
            try
            {
                Directory.CreateDirectory(root);
                EnsureSafeDirectory(root);
                var existingState = SafeTarget(root, InstallManifestName);
                if (File.Exists(existingState) && MessageBox.Show(
                    "This folder already has a VNText Studio install. Program files will be repaired or upgraded; its data folder will be preserved. Continue?",
                    "VNText Studio Setup", MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                    return 1;
                if (!File.Exists(existingState))
                {
                    using (var children = Directory.EnumerateFileSystemEntries(root).GetEnumerator())
                        if (children.MoveNext())
                            throw new InvalidDataException("The selected folder is not empty and is not a recognized VNText Studio installation. Choose an empty folder.");
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show("Setup could not install VNText Studio:\n" + ex.Message, "VNText Studio Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 2;
            }

            string error = null;
            using (var progress = CreateProgressWindow("VNText Studio Setup", "Verifying and installing files. This may take a few minutes; please wait."))
            {
                progress.Shown += async delegate
                {
                    try { await Task.Run(() => InstallPayload(root)); }
                    catch (Exception ex) { error = ex.Message; }
                    progress.Close();
                };
                Application.Run(progress);
            }
            if (error != null)
            {
                MessageBox.Show("Setup could not install VNText Studio:\n" + error, "VNText Studio Setup", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 2;
            }
            MessageBox.Show("VNText Studio was installed to:\n" + root, "VNText Studio Setup", MessageBoxButtons.OK, MessageBoxIcon.Information);
            return 0;
        }
    }

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
                    form.Text = "Intel oneAPI Redistributable Terms";
                    form.Width = 760;
                    form.Height = 560;
                    form.MinimumSize = new System.Drawing.Size(640, 420);
                    form.StartPosition = FormStartPosition.CenterScreen;
                    form.FormBorderStyle = FormBorderStyle.Sizable;
                    form.ShowInTaskbar = true;
                    text.ReadOnly = true;
                    text.WordWrap = true;
                    text.Dock = DockStyle.Fill;
                    text.Text = terms;
                    accept.Text = "Accept and continue";
                    accept.DialogResult = DialogResult.Yes;
                    accept.AutoSize = true;
                    decline.Text = "Decline";
                    decline.DialogResult = DialogResult.No;
                    decline.AutoSize = true;
                    viewEula.Text = "View original Intel agreement";
                    viewEula.AutoSize = true;
                    var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, AutoSize = true,
                        FlowDirection = FlowDirection.RightToLeft, Padding = new Padding(8) };
                    buttons.Controls.Add(accept);
                    buttons.Controls.Add(decline);
                    buttons.Controls.Add(viewEula);
                    form.Controls.Add(text);
                    form.Controls.Add(buttons);
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

    private static void ShowOriginalIntelEula(byte[] eula)
    {
        using (var form = new Form())
        using (var text = new RichTextBox())
        using (var close = new Button())
        using (var input = new MemoryStream(eula, false))
        {
            form.Text = "Intel End User License Agreement (Version August 2024)";
            form.Width = 820;
            form.Height = 640;
            form.StartPosition = FormStartPosition.CenterScreen;
            text.ReadOnly = true;
            text.Dock = DockStyle.Fill;
            text.LoadFile(input, RichTextBoxStreamType.RichText);
            close.Text = "Close";
            close.DialogResult = DialogResult.OK;
            close.AutoSize = true;
            var buttons = new FlowLayoutPanel { Dock = DockStyle.Bottom, AutoSize = true,
                FlowDirection = FlowDirection.RightToLeft, Padding = new Padding(8) };
            buttons.Controls.Add(close);
            form.Controls.Add(text);
            form.Controls.Add(buttons);
            form.AcceptButton = close;
            form.ShowDialog();
        }
    }

    private static Form CreateProgressWindow(string title, string status)
    {
        var form = new Form
        {
            Text = title,
            Width = 430,
            Height = 135,
            FormBorderStyle = FormBorderStyle.FixedDialog,
            StartPosition = FormStartPosition.CenterScreen,
            ControlBox = false,
            ShowInTaskbar = true
        };
        var label = new Label
        {
            Name = "progressStatus",
            Left = 18,
            Top = 16,
            Width = 380,
            Text = status
        };
        var bar = new ProgressBar
        {
            Name = "progressBar",
            Left = 18,
            Top = 52,
            Width = 380,
            Height = 22,
            Style = ProgressBarStyle.Marquee,
            MarqueeAnimationSpeed = 24
        };
        form.Controls.Add(label);
        form.Controls.Add(bar);
        return form;
    }

    private static void InstallPayload(string root)
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
                foreach (var entry in zip.Entries)
                {
                    if (entry.FullName == ManifestName) continue;
                    var target = SafeTarget(root, entry.FullName);
                    Directory.CreateDirectory(Path.GetDirectoryName(target));
                    using (var input = entry.Open())
                    using (var output = new FileStream(target, FileMode.Create, FileAccess.Write, FileShare.None))
                        input.CopyTo(output);
                }
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

    private static int Uninstall()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        var selfPath = Path.GetFullPath(Assembly.GetExecutingAssembly().Location);
        var root = Path.GetDirectoryName(selfPath);
        var volume = Path.GetPathRoot(root);
        if (String.Equals(root.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar),
            volume.TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar), StringComparison.OrdinalIgnoreCase))
        {
            MessageBox.Show("Không thể gỡ cài đặt khỏi thư mục gốc của ổ đĩa.", "Gỡ cài đặt VNText Studio",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }

        if (MessageBox.Show(
            "Gỡ cài đặt sẽ xóa mọi nội dung trong thư mục này, bao gồm dữ liệu trong data/. " +
            "Sau khi hoàn tất, thư mục cài đặt vẫn còn nhưng trống:\n" + root +
            "\n\nKhông thể khôi phục. Bạn có muốn tiếp tục?",
            "Gỡ cài đặt VNText Studio", MessageBoxButtons.YesNo, MessageBoxIcon.Warning,
            MessageBoxDefaultButton.Button2) != DialogResult.Yes)
            return 1;

        try
        {
            EnsureSafeDirectory(root);
            using (var progress = CreateUninstallProgressForm(
                root, selfPath, Process.GetCurrentProcess().Id, true, null))
            {
                Application.Run(progress);
                return Convert.ToInt32(progress.Tag);
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show("Không thể gỡ cài đặt:\n" + ex.Message, "Gỡ cài đặt VNText Studio",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }
    }

    private static Form CreateUninstallProgressForm(string root, string selfPath, int parentPid,
        bool launchFinalHelper, IList<Dictionary<string, object>> progressEvidence)
    {
        var form = CreateProgressWindow("Gỡ cài đặt VNText Studio", "Đang quét thư mục cài đặt.");
        form.Width = 600;
        form.Height = 350;
        form.ControlBox = false;
        var phaseLabel = (Label)form.Controls.Find("progressStatus", false)[0];
        phaseLabel.Width = 550;
        phaseLabel.Height = 24;
        phaseLabel.Font = new System.Drawing.Font("Segoe UI", 10, System.Drawing.FontStyle.Bold);
        var progress = (ProgressBar)form.Controls.Find("progressBar", false)[0];
        progress.Left = 18;
        progress.Top = 50;
        progress.Width = 550;
        progress.Height = 22;
        progress.Style = ProgressBarStyle.Marquee;
        var pathBox = new TextBox { Left = 18, Top = 82, Width = 550, ReadOnly = true, WordWrap = false, ScrollBars = ScrollBars.Horizontal, Text = root };
        var details = new TextBox { Name = "uninstallDetails", Left = 18, Top = 116, Width = 550, Height = 135, Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical };
        var heartbeat = new Label { Name = "uninstallHeartbeat", Left = 18, Top = 265, Width = 420, Height = 24 };
        var close = new Button { Name = "closeUninstall", Left = 478, Top = 260, Width = 90, Height = 30, Text = "Đóng", Enabled = false };
        form.Controls.AddRange(new Control[] { pathBox, details, heartbeat, close });

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
            pathBox.Text = (string)update["path"];
            details.Text = (string)update["message"];
            if (phase == "scanning")
            {
                phaseLabel.Text = String.Format("Đang quét: {0} mục đã tìm thấy", done);
                progress.Style = ProgressBarStyle.Marquee;
            }
            else
            {
                progress.Style = ProgressBarStyle.Continuous;
                progress.Maximum = Math.Max(1, total);
                progress.Value = Math.Min(progress.Maximum, Math.Max(0, done));
                if (phase == "checking") phaseLabel.Text = String.Format("Đang kiểm tra tệp đang được sử dụng: {0}/{1}", done, total);
                else if (phase == "deleting") phaseLabel.Text = String.Format("Đang xóa: {0}/{1} mục", done, total);
                else if (phase == "handoff") phaseLabel.Text = "Đang chuyển bước cuối cho trình trợ giúp bên ngoài.";
                else if (phase == "blocked") phaseLabel.Text = "Không thể tiếp tục vì có tệp đang được sử dụng.";
                else if (phase == "failed") phaseLabel.Text = "Không thể xóa toàn bộ thư mục cài đặt.";
            }
        };
        worker.RunWorkerCompleted += delegate(object sender, RunWorkerCompletedEventArgs e)
        {
            if (e.Error != null)
            {
                form.Tag = 2;
                phase = "failed";
                phaseClock.Restart();
                phaseLabel.Text = "Không thể hoàn tất gỡ cài đặt.";
                details.Text = e.Error.ToString();
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
                    phaseLabel.Text = launchFinalHelper
                        ? "Đã dọn nội dung; trình trợ giúp cuối sẽ xóa Uninstall.exe. Thư mục cài đặt sẽ vẫn còn nhưng trống."
                        : "Fixture đã dọn; worker kết thúc trong cửa sổ progress thật.";
                    details.Text = launchFinalHelper
                        ? "Trình trợ giúp bên ngoài đang chờ tiến trình này kết thúc rồi xóa Uninstall.exe. Thư mục cài đặt sẽ vẫn còn nhưng trống."
                        : "Trình trợ giúp cuối không chạy trong bài kiểm tra fixture.";
                }
                catch (Exception ex)
                {
                    form.Tag = 2;
                    phase = "failed";
                    phaseClock.Restart();
                    phaseLabel.Text = "Không thể chuyển bước xóa tệp cuối cùng.";
                    details.Text = ex.ToString();
                }
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
