"""Explicit resource setup, independent of game discovery/extraction."""
from pathlib import Path
import json
import uuid
from vntext_worker.protocol import emit_complete, emit_progress, emit_log


def run_resources(task_id, params, is_cancelled):
    from vntext.renpy_toolchain import managed_sdk, managed_sdk_root, download_and_install_managed_sdk
    from vntext.mt_ct2_model import resolve_model_dir, ensure_model, model_status
    from vntext.runtime_paths import app_data_root
    download = params.get('download') is True
    results = []
    errors = []
    if is_cancelled():
        raise ValueError('cancelled')
    for name in ('model', 'renpy', 'ocr'):
        if is_cancelled():
            raise ValueError('cancelled')
        emit_progress(task_id, done=0, total=0, step='Kiểm tra tài nguyên', item=name)
        try:
            if name == 'model':
                folder = resolve_model_dir()
                if download:
                    ensure_model(folder, download=True)
                status = model_status()
                if not status.get('ready', False):
                    raise ValueError(str(status.get('message') or status.get('error') or 'Mô hình chưa sẵn sàng'))
                path = str(folder)
            elif name == 'renpy':
                try:
                    sdk = managed_sdk()
                except Exception:
                    if not download:
                        raise
                    sdk = None  # a retry replaces only the managed, verified SDK
                if sdk is None and download:
                    archive = app_data_root() / 'downloads' / ('renpy-sdk-' + uuid.uuid4().hex + '.zip')
                    try:
                        sdk = download_and_install_managed_sdk(archive, is_cancelled=is_cancelled,
                            progress=lambda done, total: emit_progress(task_id, done=done, total=total, step="Tải Ren'Py SDK 8.5.3"))
                    finally:
                        archive.unlink(missing_ok=True)
                if sdk is None:
                    raise ValueError("Chưa tải Ren'Py SDK 8.5.3")
                path = str(sdk.root)
            else:
                import os
                import subprocess
                if os.name != 'nt':
                    raise ValueError('OCR cần Windows với gói nhận diện tiếng Anh.')
                command = "[Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime] > $null; if (@([Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages | Where-Object {$_.LanguageTag -like 'en-*'}).Count -eq 0) { exit 2 }"
                check = subprocess.run([str(Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'), '-NoProfile', '-Command', command], capture_output=True, timeout=20)
                if check.returncode:
                    raise ValueError('Thiếu OCR tiếng Anh của Windows; cần cài gói ngôn ngữ tiếng Anh trong Windows trước khi xử lý ảnh.')
                path = 'Windows OCR · English'
            results.append({'resource': name, 'ready': True, 'path': path})
            emit_log(task_id, f'{name}: sẵn sàng · {path}')
        except Exception as exc:
            if is_cancelled():
                raise ValueError('cancelled') from exc
            errors.append(f'{name}: {exc}')
            results.append({'resource': name, 'ready': False, 'error': str(exc)})
            emit_log(task_id, f'[error] Tài nguyên {name}: {exc}')
    root = app_data_root()
    root.mkdir(parents=True, exist_ok=True)
    report = root / 'resource-status.json'
    temp = report.with_suffix('.tmp')
    temp.write_text(json.dumps({'resources': results}, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(report)
    emit_complete(task_id, ok=not errors, summary='Tài nguyên đã sẵn sàng.' if not errors else 'Tài nguyên chưa đầy đủ.', error='\n'.join(errors))
