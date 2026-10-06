# Phát triển VNText Studio

Quy trình dành cho clone public mới trên Windows x64; không cần repo private,
virtualenv, registry lịch sử hay artifact trên máy cũ. `v0.1` là bản công khai
đầu tiên; source chuẩn là `0.1.0` cho public line `0.1`; bản update kế tiếp là `0.1.1`.

## Kiểm prerequisite trước khi tải

Luồng bootstrap công khai: chọn Python có sẵn để chạy script stdlib bên dưới.
Mặc định chỉ đọc, không cài/download/tạo environment. JSON stdout giữ từng
command, cwd, stdout/stderr và exit code; exit 2 là danh sách prerequisite/quota
chưa đủ, exit 1 là lỗi thực. Không suy Release PASS từ preflight DEV.

```powershell
# Dùng đường dẫn Python 3.11+ đã kiểm; không cần environment để chạy preflight.
python -B release/dev_bootstrap.py
# Khi dependency đã đủ: build offline bằng SDK/pack/NuGet cache hiện có.
.\.dev-env\.venv\Scripts\python.exe -B release/dev_bootstrap.py --action build
# Model phải có sẵn và được Owner cho phép sử dụng.
.\.dev-env\.venv\Scripts\python.exe -B release/dev_bootstrap.py --action smoke --model .dev-env/cache/models/opus-mt-en-vi-int8
$LASTEXITCODE
```

Script kiểm requirements bằng metadata và `pip check`, SDK8/WPF runtime/ref pack,
SDK10 local (thông tin optional), model file/hash và inventory toàn root theo
CONTRACTS §10a. NuGet readiness chỉ xác nhận sau build. Hash/version quan sát
không thay download receipt, model revision/license hoặc Release prerequisites.
Không đủ cache thì build báo lỗi; cài/restore từ nguồn chính thức là bước riêng
cần quyền tải/cài, không tự dùng mạng. Các lệnh thủ công phía dưới mô tả bước đó.

Output duy nhất của apply là `DEV_RUN/bootstrap-build`, có ownership marker;
không ghi đè directory có sẵn thiếu marker. Build dự phòng 128 MiB ngoài phần
miễn trừ, chặn trước nếu inventory thiếu hoặc vượt tổng 1+3 GiB cho `.dev-env`. Tái chạy dùng
cùng output/cache, không nhân bản venv/SDK/model. Môi trường APPDATA/LOCALAPPDATA
và NuGet riêng chỉ có hiệu lực trong child build; không sửa profile user.
Giữ command và JSON/exit code ngoài payload. Build/smoke không phải cleanup PASS.

Nếu thử source checkout cô lập trong cùng DEV đã được đăng ký owner/lifecycle,
truyền `--python <DEV-main>/.dev-env/.venv/Scripts/python.exe --model <DEV-main>/.dev-env/cache/models/opus-mt-en-vi-int8 --shared-root <DEV-main>`.
Script không copy dependency; shared-root phải nằm trong containing checkout.
Đây là nghiệm thu source sạch với environment dùng chung, không chứng minh cài
dependency trên máy mới. Không tạo snapshot/venv mới nếu chưa duyệt scope/budget.

Python 3.11+ cho DEV; publisher hiện yêu cầu Python **3.12.x** khi đóng runtime.
Kiểm `.dev-env/.venv` nếu có, `py -0p`, `Get-Command python,py,dotnet,git,pwsh`, và các
runtime/cache đã có trên máy. Ghi đường dẫn thực, `python --version`,
`dotnet --list-sdks`, `dotnet --list-runtimes`, `pip check` và version package.
Không sao chép virtualenv. Cache cùng máy có thể tái dùng khi nguồn/version/hash
được chứng minh; không dùng ZIP private hoặc suy provenance từ tên thư mục.

- Build DEV: Git, Python 3.11+, `requirements.txt`, SDK .NET 8 với WindowsDesktop
  targeting pack. NuGet restore cần nguồn chính thức hoặc cache package đủ.
- Smoke: các điều kiện DEV, model CT2/OPUS-MT đủ tokenizer/config/model, worker
  Python đúng `.dev-env/.venv`, và output/work root ghi được. Thiếu model không phải PASS.
- Harness/Release: thêm SDK .NET 10 tại `.dev-env/dotnet-sdk-10`; harness hiện pin
  runtime/ref pack 8.0.30 và apphost pack 10.0.12. Publisher còn cần matching
  .NET 8 core/WPF runtime + ref packs + hostfxr dưới Program Files, .NET Framework
  `csc.exe`, Python 3.12.x portable, Pillow (`release/requirements-build.txt`), pinned model,
  baseline có provenance và registry/epoch hợp lệ. SDK 10 không thay SDK/runtime8.

Nếu thiếu, báo **một danh sách gộp**, đường dẫn/version đã kiểm, gate bị chặn,
nguồn tải và quyền cần thiết. Không cài admin, thay ACL/profile, chấp thuận license
hoặc tải model khi chưa được phép. Nguồn: [Python](https://www.python.org/downloads/windows/),
[Microsoft .NET](https://dotnet.microsoft.com/download/dotnet),
[script Microsoft](https://learn.microsoft.com/dotnet/core/tools/dotnet-install-script),
[PyPI](https://pypi.org), [NuGet](https://api.nuget.org/v3/index.json).

SDK 10.0.401 có thể cài local bằng script chính thức sau khi được phép:

```powershell
New-Item -ItemType Directory -Force .dev-env/cache | Out-Null
Invoke-WebRequest https://dot.net/v1/dotnet-install.ps1 -OutFile .dev-env/cache/dotnet-install.ps1
Get-FileHash .dev-env/cache/dotnet-install.ps1 -Algorithm SHA256
powershell -NoProfile -ExecutionPolicy Bypass -File .dev-env/cache/dotnet-install.ps1 -Version 10.0.401 -Architecture x64 -InstallDir .dev-env/dotnet-sdk-10 -NoPath -Verbose
.\.dev-env\dotnet-sdk-10\dotnet.exe --list-sdks
```

Giữ URL SDK thực trong raw output và đối chiếu SHA512 với release metadata của
Microsoft; hash tự tính chỉ chứng minh file hiện có. Script local không tự cung
cấp matching runtime8 dưới Program Files mà publisher hiện kiểm.

## Tạo Python worker mới

Chọn executable đã kiểm phiên bản (không giả định `py` có trên mọi máy):

```powershell
New-Item -ItemType Directory -Force .dev-env/cache | Out-Null
# Nếu launcher có Python 3.12; có thể thay bằng đường dẫn Python 3.12 đã xác minh.
py -3.12 -m venv .dev-env/.venv
.\.dev-env\.venv\Scripts\python.exe --version
.\.dev-env\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.dev-env\.venv\Scripts\python.exe -m pip check
.\.dev-env\.venv\Scripts\python.exe -X utf8 -m pip inspect > .dev-env/cache/pip-inspect.json
```

Release cần thêm `pip install -r release/requirements-build.txt`. Không cần PyTorch/Argos/VinAI;
CTranslate2 pin `4.8.1`. Ghi source URL, resolved version, install command/exit code;
package metadata không thay thế quyền phân phối trong `THIRD_PARTY_NOTICES.md`.

Model sản phẩm khai báo tại `vntext/mt_ct2_constants.py`: repo
`dekthedev/opus-mt-en-vi-ct2-int8`, revision
`c22547827b876e8ee939d6a9363965e5c9f769e1`. Sau quyền tải model, dùng đúng pin:

```powershell
$env:VNTEXT_CT2_MODEL = "$PWD/.dev-env/cache/models/opus-mt-en-vi-int8"
.\.dev-env\.venv\Scripts\python.exe -B -c "from vntext.mt_ct2_model import ensure_model; print(ensure_model())"
$env:VNTEXT_CT2_NO_DOWNLOAD = '1'
Get-ChildItem $env:VNTEXT_CT2_MODEL -Recurse -File | Get-FileHash -Algorithm SHA256
```

Giữ pin, log tải và inventory/hash. `ensure_model` chỉ kiểm `model.bin` có sẵn;
không chứng minh cache cũ đúng revision. Release phải đối chiếu inventory model
và license/provenance; model ngoài clone không phải source được commit.

## Build DEV và smoke

`DEV_RUN` ignored là output DEV. Không ghi đè bản cài/user data bên trong root này.
Có thể dùng config NuGet riêng để tránh phụ thuộc profile cũ:

```powershell
'<configuration><packageSources><clear/><add key="nuget.org" value="https://api.nuget.org/v3/index.json"/></packageSources></configuration>' | Set-Content .dev-env/cache/NuGet.Config
$env:NUGET_PACKAGES = "$PWD/.dev-env/cache/nuget"
$env:DOTNET_CLI_HOME = "$PWD/.dev-env/cache/dotnet-home"
$env:DOTNET_GENERATE_ASPNET_CERTIFICATE = 'false'
dotnet build wpf_app/VNText.Studio.App/VNText.Studio.App.csproj -c Debug -o DEV_RUN --configfile .dev-env/cache/NuGet.Config
$env:VNTEXT_WORKER_CWD = "$PWD"
$env:VNTEXT_WORKER_PYTHON = "$PWD/.dev-env/.venv/Scripts/python.exe"
$env:VNTEXT_DATA_ROOT = "$PWD/.dev-env/cache/dev-data"
.\DEV_RUN\VNText.Studio.App.exe
```

Smoke báo JSON gồm `exit_code`, `failed_step`, error/summary của worker `complete`.
Cancel và crash là phép thử chủ động nên sự kiện `ok=false` của hai bước đó là
mong đợi; extract/translate/patch cần `ok=true` và assertion output thực đạt.
Với WPF GUI executable, dùng tiến trình chờ và `--report` để giữ evidence:

```powershell
$smoke = Start-Process -FilePath "$PWD/DEV_RUN/VNText.Studio.App.exe" -ArgumentList '--smoke-worker','--report',"`"$PWD/.dev-env/cache/smoke.json`"" -Wait -PassThru -WindowStyle Hidden -RedirectStandardOutput .dev-env/cache/smoke.stdout.log -RedirectStandardError .dev-env/cache/smoke.stderr.log
$smoke.ExitCode
Get-Content .dev-env/cache/smoke.json
```

Exit 24 là translate không thành công; đọc error/summary thực, không đổi thành
PASS từ worker readiness. Lỗi ghi report trả 1. `cleanup_error` không được che;
cleanup gate độc lập vẫn phải đạt. Lưu command, cwd, env liên quan không có secret,
stdout/stderr, report và exit code thực. Smoke không thay acceptance GUI/installer.

## Test và Release

Test ghi artifact phải qua wrapper; đăng ký root trước tạo, giữ evidence ngoài
payload trước disposal. Clone/snapshot, staging/candidate, installed copy cần owner,
scope/lifecycle theo `CONTRACTS.md` §10a/b; private history vắng không là PASS/FAIL.
Không dọn `test-temp`, `DEV_RUN/v01_audit` hoặc đường dẫn chưa đủ ownership.

```powershell
.\.dev-env\.venv\Scripts\python.exe tests/tools/run_with_cleanup.py -- .\.dev-env\.venv\Scripts\python.exe -B -m unittest discover -s tests/unit -p test_entrypoint_docs_version.py -v
.\.dev-env\.venv\Scripts\python.exe tests/tools/run_with_cleanup.py -- .\.dev-env\.venv\Scripts\python.exe -B tests/unit/test_wpf_workflow.py
```

Harness fixture version độc lập với version sản phẩm; readiness phải đạt trước
bắt đầu timeout. Xem `tests/README.md`, `TEST_MATRIX.md`, `release/README.md` để
chọn gate. Publisher `publish.ps1` là local build, không upload/phát hành. Chỉ
build sau source commit sạch, epoch hợp lệ và inventory toàn root complete:
không miễn trừ <=1 GiB và `.dev-env` <=3 GiB theo exact roots trong CONTRACTS. Baseline
WPF/full-app phải có version và payload thực, không tạo metadata giả hoặc nới
validator để qua gate. Version package phải mới hơn baseline; version Owner chọn
cho candidate phải khớp source/EXE/manifests. Owner chọn Setup 0.1.2 cho người còn ở v0.1; full-app từ baseline mới.
Dùng `publish.ps1 -SkipWpfUpdatePackage` để build Setup không kèm WPF delta
version cao hơn chưa được chọn. Chỉ yêu cầu full-app delta khi baseline thực
nhỏ hơn candidate và provenance/inventory khớp. SDK/dependency/worker/model đầy đủ
không tự chứng minh Release PASS. Public stable GitHub update đã được nghiệm thu trên bản cài Owner; các giới hạn còn lại giữ nguyên.
