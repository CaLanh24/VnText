# VNText Studio — WPF (.NET 8)

App chính mới (milestone 1): shell WPF + Python worker JSON stdin/stdout.

## Chạy DEV

Các lệnh dưới đây dành cho chạy thủ công cục bộ. Task agent sửa WPF phải dùng
FAST DEV BUILD và cleanup budget trong `AGENTS.md`; không để `bin/obj` hoặc
output test tăng vô hạn.

```bat
cd wpf_app
dotnet run --project VNText.Studio.App -c Release
```

Hoặc:

```bat
wpf_app\VNText.Studio.App\bin\Release\net8.0-windows\VNText.Studio.App.exe
```

## Smoke test (headless worker)

```bat
VNText.Studio.App.exe --smoke-worker
```

## Python worker

```bat
.venv\Scripts\python.exe -m vntext_worker.worker_main
```

Protocol: NDJSON `v=1` — `ready`, `log`, `progress`, `complete`, `error`; lệnh `run` / `cancel`.

Python source (`vntext/`, compatibility facades) is the worker backend; `app.py`
only keeps the `--release-*` verification modes. The legacy Tk/Qt/QML Python UIs
were removed on 2026-11-25; WPF is the only UI.
