# tests/ — bản đồ thư mục

```
tests/
  golden/          # Dữ liệu golden nguồn; không chứa runtime test
  TEST_RUN/        # Runtime test tạm, tự dọn absent/empty sau terminal outcome
  lib/             # Thư viện dùng chung (work_paths, fixture Unity, E2E lib)
  unit/            # unittest: test_*.py (publish gate chạy ở đây)
  harness/         # Harness E2E/điều tra; game-specific probes được track nhưng cần fixture bên ngoài
  tools/           # Dọn TEST_RUN, capture golden (maintenance)
```

## Chạy nhanh

```powershell
# Publish/unit gate (từng file hoặc cả unit/) — có lifecycle cleanup
.\.dev-env\.venv\Scripts\python.exe tests/tools/run_with_cleanup.py -- .\.dev-env\.venv\Scripts\python.exe -B -m unittest discover -s tests/unit -p "test_freeze_hashes.py" -v

# Dọn artifact TEST_RUN
.\.dev-env\.venv\Scripts\python.exe tests/tools/cleanup_work_artifacts.py

# Lập kế hoạch dọn, tuyệt đối read-only
.\.dev-env\.venv\Scripts\python.exe tests/tools/cleanup_work_artifacts.py --dry-run

# Mirror Release Output (read-only nguồn) → work_package trong RELEASE_RUN
.\.dev-env\.venv\Scripts\python.exe tests/tools/mirror_release_package.py

# Tracked vh_parity/Naninovel probe scripts are optional/manual and need
# explicitly supplied external game/reference fixtures; they are not unit gates.
```

## Import trong code test

```python
from bootstrap import bootstrap
TESTS, ROOT, LIB = bootstrap(__file__)
from work_paths import E2E_GAME_COPY
```

`work_paths.py` nằm trong `lib/`; `bootstrap(__file__)` thêm `lib/` vào `sys.path`.

Test/harness đăng ký artifact bằng `register_artifact(...)` hoặc
`artifact_scope(...)`, truyền `scope_id`/`run_id`/`scope_root` và finalize
trong `finally`. Giữ báo cáo `.md` nhỏ cần thiết; xóa game copy, staging,
package và log nặng sau PASS **lẫn** FAIL/SKIP/TIMEOUT/hủy. `artifact_scope`
gọi cleanup canonical sau PASS hoặc exception, giữ nguyên outcome và exception
gốc; `START_ERROR` được runner xử lý trước khi body bắt đầu. Nếu process còn
giữ file hoặc cleanup không chứng minh được, báo `LOCKED`/review-required;
không xóa game/user data hay nguồn ngoài `_work`. Theo chính sách và ngân sách
ở `AGENTS.md`.
`cleanup_work_artifacts.py --dry-run` chỉ đọc; `--output` ngoài `_work` mới
được phép ghi báo cáo dry-run.
Game-specific runtime probe scripts are tracked in this public source snapshot,
but game/reference packages and game data are not. The probes are opt-in/manual;
the unit suite uses synthetic fixtures and does not require game data.
