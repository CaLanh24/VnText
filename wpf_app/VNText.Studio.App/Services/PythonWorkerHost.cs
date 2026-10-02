using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using VNText.Studio.App.Models;

namespace VNText.Studio.App.Services;

public sealed class PythonWorkerHost : IDisposable
{
    private Process? _process;
    private StreamWriter? _stdin;
    private readonly object _writeLock = new();
    private string? _activeTaskId;
    private bool _ready;

    public event EventHandler<WorkerEvent>? EventReceived;

    public bool IsReady => _ready;
    public bool IsBusy => !string.IsNullOrEmpty(_activeTaskId);
    public int? ProcessId => _process is { HasExited: false } process ? process.Id : null;

    public async Task StartAsync(CancellationToken cancellationToken = default)
    {
        if (_process is { HasExited: false })
            return;

        var root = WorkerPaths.RepoRoot();
        var psi = new ProcessStartInfo
        {
            FileName = WorkerPaths.PythonExecutable(),
            Arguments = WorkerPaths.WorkerModuleArgs(),
            WorkingDirectory = root,
            UseShellExecute = false,
            RedirectStandardInput = true,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        WorkerPaths.ConfigureReleaseEnvironment(psi.Environment);
        psi.Environment["PYTHONUTF8"] = "1";
        psi.Environment["PYTHONIOENCODING"] = "utf-8";
        // Release smoke/GUI launches must not mutate the shipped runtime with
        // import caches.  The worker is disposable, so bytecode persistence is
        // never required for correctness here.
        psi.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        psi.Environment["TRANSFORMERS_OFFLINE"] = "1";
        psi.Environment["HF_HUB_OFFLINE"] = "1";
        psi.Environment["OMP_NUM_THREADS"] = "1";

        _process = new Process { StartInfo = psi, EnableRaisingEvents = true };
        _process.ErrorDataReceived += (_, e) =>
        {
            if (!string.IsNullOrWhiteSpace(e.Data))
                Publish(new WorkerEvent { Type = "log", Text = $"[stderr] {e.Data}" });
        };
        _process.Exited += (_, _) =>
        {
            _ready = false;
            var taskId = _activeTaskId ?? "";
            var wasBusy = !string.IsNullOrEmpty(_activeTaskId);
            _activeTaskId = null;
            if (wasBusy)
            {
                Publish(new WorkerEvent
                {
                    Type = "complete",
                    Id = taskId,
                    Ok = false,
                    Error = "Worker process exited unexpectedly",
                });
            }
            Publish(new WorkerEvent { Type = "error", Error = "Worker process exited" });
        };

        if (!_process.Start())
            throw new InvalidOperationException("Failed to start Python worker");

        _stdin = _process.StandardInput;
        _process.BeginErrorReadLine();
        _ = Task.Run(() => ReadStdoutAsync(_process, cancellationToken), cancellationToken);

        var deadline = DateTime.UtcNow.AddSeconds(15);
        while (!_ready && DateTime.UtcNow < deadline && _process is { HasExited: false })
            await Task.Delay(50, cancellationToken).ConfigureAwait(false);

        if (!_ready)
            throw new TimeoutException("Python worker did not emit ready");
    }

    public void RunTask(string taskId, string task, object? parameters = null)
    {
        EnsureStarted();
        if (IsBusy)
            throw new InvalidOperationException("Worker is busy");

        _activeTaskId = taskId;
        WriteCommand(new
        {
            v = 1,
            type = "run",
            id = taskId,
            task,
            @params = parameters ?? new { },
        });
    }

    public void Cancel(string? taskId = null)
    {
        if (!IsBusy && string.IsNullOrEmpty(taskId))
            return;
        WriteCommand(new { v = 1, type = "cancel", id = taskId ?? _activeTaskId ?? "" });
    }

    public void KillWorkerForSmoke()
    {
        var process = _process;
        if (process is { HasExited: false })
        {
            try
            {
                process.Kill(entireProcessTree: true);
                process.WaitForExit(2000);
            }
            catch { /* ignore */ }
        }
    }

    private void EnsureStarted()
    {
        if (_process is null || _process.HasExited || _stdin is null)
            throw new InvalidOperationException("Worker not started");
    }

    private void WriteCommand(object payload)
    {
        EnsureStarted();
        var json = JsonSerializer.Serialize(payload);
        lock (_writeLock)
        {
            _stdin!.WriteLine(json);
            _stdin.Flush();
        }
    }

    private async Task ReadStdoutAsync(Process process, CancellationToken cancellationToken)
    {
        try
        {
            while (!cancellationToken.IsCancellationRequested)
            {
                var line = await process.StandardOutput.ReadLineAsync(cancellationToken).ConfigureAwait(false);
                if (line is null)
                    break;
                var evt = WorkerEvent.FromJson(line);
                if (evt is null)
                    continue;

                if (evt.Type == "ready")
                    _ready = true;

                if (evt.Type is "complete" or "error")
                {
                    if (string.IsNullOrEmpty(evt.Id) || evt.Id == _activeTaskId)
                        _activeTaskId = null;
                }

                Publish(evt);
            }
        }
        catch (OperationCanceledException)
        {
            // Host shutdown/cancellation is expected.
        }
        catch
        {
            // Process exit/error is surfaced by the Exited handler.
        }
    }

    private void Publish(WorkerEvent evt) => EventReceived?.Invoke(this, evt);

    public void Dispose()
    {
        var stdin = Interlocked.Exchange(ref _stdin, null);
        try
        {
            // EOF is the worker protocol's graceful shutdown signal.  Avoid
            // killing a healthy worker while its reader drains the final line.
            stdin?.Dispose();
        }
        catch { /* ignore */ }

        var process = Interlocked.Exchange(ref _process, null);
        if (process is not null)
        {
            try
            {
                if (!process.HasExited && !process.WaitForExit(30000))
                    Console.Error.WriteLine($"Python worker did not exit after graceful EOF (pid {process.Id}).");
            }
            catch { /* ignore */ }
            process.Dispose();
        }
        _activeTaskId = null;
        _ready = false;
    }
}
