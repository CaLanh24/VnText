# DEV → RELEASE

Chạy `release/publish.ps1 -SkipWpfUpdatePackage` để tạo Setup từ source hiện tại
không kèm WPF compatibility delta. Chỉ dùng `-WpfUpdateVersion <version>` khi
yêu cầu gói WPF riêng, và version đó phải cao hơn Setup baseline đang dựng.
Full-app delta riêng cần `-FullAppUpdateBaselineRoot` có provenance, version cũ
hơn candidate và toàn bộ inventory đúng baseline.
Setup nhúng EXE WPF chính, runtime .NET riêng trong `app/dotnet/`,
`VERSION.txt`, manifests và `app/worker/` cùng SHA256 inventory. Sau khi chọn
thư mục cài, `VNText Studio.exe` và `Uninstall.exe` nằm ngay ở đó;
worker/runtime nằm trong `app/`, dữ liệu trong `data/`. Không tạo shortcut hay file
app-managed trong AppData hoặc thư mục ngoài nơi cài.

Settings, work/cache/temp, Ren’Py SDK và default-generated packages ở
`<install-root>/data/`. Update staging, backup và log nằm tại install root
ngoài `data/`. Release không fallback LocalAppData/system Temp. Input/output
user chọn và game patch delivery giữ nguyên đường dẫn cùng contract.

Mọi Setup thường đều bật **Kiểm tra cập nhật** và trỏ tới `Updates` cạnh Setup.
Publisher dựng WPF B từ cùng source, kiểm version thực của EXE, baseline A,
allowlist và hash; chép package bất biến đã xác minh trước rồi mới thay manifest
hiện hành nguyên tử sau khi Setup mới được hash-check. Các package cũ được giữ
và dung lượng retention được báo. Owner cài Setup, mở app, bấm **Kiểm tra cập
nhật** rồi **Cập nhật**; không cần chạy script hay sửa cấu hình. Updater WPF của baseline v0.1 chỉ
thay `VNText Studio.exe`, `app/RELEASE.json`, `app/VERSION.txt`, có rollback và
giữ `data/`. Source hiện có full-app updater thay worker/dependency/runtime với
exact baseline inventory, health check và rollback theo CONTRACTS; chưa có
Release candidate hoặc stable GitHub acceptance. Thay installer/uninstaller
hoặc quyền hệ thống vẫn cần Setup mới. Feed chỉ dùng từ thư mục `Updates` cạnh Setup trên máy này; đây không
phải nguồn cập nhật GitHub và không hỗ trợ thông báo stable release trên máy
khác. WPF source đã có stable-release discovery trên GitHub và đường cập nhật
WPF-only; unit/mock tests không thay thế acceptance trên app đã cài. Chưa có
bằng chứng app cài thực tế kiểm tra và cập nhật từ một GitHub Release stable
công khai; acceptance trên bản cài Owner đã xác nhận offer/apply/restart. Setup chỉ gọi đúng repository khi được
publisher cấu hình tường minh bằng cả `-GitHubOwner` và `-GitHubRepository`.

`Uninstall.exe` hỏi xác nhận một lần, nêu rõ mọi nội dung sẽ bị xóa gồm
`data/`, rồi dọn các file và thư mục con sau safety scan/lock check. Helper cuối
chờ tiến trình Uninstall thoát, xác minh chỉ còn đúng `Uninstall.exe`, xóa file
đó và kiểm tra thư mục gốc cài đặt vẫn là thư mục thường rỗng. Thư mục cài đặt
vẫn còn trên đĩa nhưng không giữ lại dữ liệu; lỗi xóa hoặc hậu kiểm báo lỗi và
trả exit code khác 0. Repair/upgrade vẫn giữ data, hỏi trước khi tiếp tục và
chỉ dọn file cũ khi manifest của bản cài trước sở hữu chúng.

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\release\publish.ps1 `
  -SkipWpfUpdatePackage
```

Tùy chọn: `-SkipTests`, `-BuildLegacy`, `-FullAppUpdateBaselineRoot`. `-SkipBuild` không được hỗ trợ cho
publish Setup chuẩn vì mỗi lượt phải dựng WPF Update mới.
Publisher dùng SDK .NET 10 ở `.dev-env\dotnet-sdk-10`, target runtime .NET 8
và đóng runtime riêng trong `app/dotnet/` để EXE chạy không cần cài .NET ngoài.

Chỉ model CT2/OPUS-MT được đóng gói; VinAI và PyTorch không nằm trong sản phẩm.

Build, verify, smoke và package chạy trong registered
`TEST_RUN`. Publisher xác minh payload/hash trước khi thay Setup và
atomically công bố feed; ReleaseRoot chỉ còn `Setup.exe` và `Updates`. Báo
version, source SHA, Setup/package SHA256, payload size và số package/byte được
giữ lại. Chỉ khi tất cả release gates và acceptance bắt buộc đạt mới gọi
`RELEASE_VERIFIED`.

## Chuẩn bị 0.1.0 → 0.1.1

`v0.1` là bản public đầu tiên, public line hiện tại là `0.1`; bản update kế tiếp là `0.1.1`.
Không phát hành bridge riêng, không hứa một lần Setup cho baseline v0.1. Dùng
`-SkipWpfUpdatePackage` để không tạo version WPF cao hơn chưa được Owner chọn.
Không kết hợp switch này với `-WpfUpdateVersion`; gói được yêu cầu vẫn phải qua
integrity/baseline/version validation. `-FullAppUpdateBaselineRoot` cần bản cài
thực có inventory/hash và provenance; package dùng provenance giả trong harness
không là Release evidence. Một gói full-app nội bộ 0.1.2 từ payload public v0.1
có thể kiểm engine bằng helper mới; nó không chứng minh binary v0.1 tự update.
Mọi package kiểm dùng version override phải ghi rõ test-only, nguồn và giới hạn;
không upload hoặc coi là asset public đã nghiệm thu.

DEV setup và danh sách prerequisite/gate nằm trong `docs/DEVELOPMENT.md`.
Trước candidate: commit source/version sạch, epoch hợp lệ, scoped cleanup <=1GiB,
full regression + affected gates trên SHA cuối. Sau build: payload audit/hash,
release verify, smoke hai cwd, installer/GUI và installed upgrade/rollback/recovery.
Giữ raw command/output/exit code/skip/warning và lifecycle trước disposal. Không
suy candidate đạt từ focused gate; các giới hạn installer/uninstaller và runtime native vẫn giữ nguyên.
