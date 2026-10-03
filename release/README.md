# DEV → RELEASE

Chạy `release/publish.ps1 -WpfUpdateVersion <version>` để tạo `Setup.exe` và
thư mục `Updates` tại `ReleaseRoot`. Bắt buộc chọn version WPF cao hơn version
của Setup A mà publisher đang dựng.
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
công khai, nên trạng thái acceptance này vẫn là `NOT VERIFIED` và không được
quảng bá như tính năng đã nghiệm thu. Setup chỉ gọi đúng repository khi được
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
  -WpfUpdateVersion <newer-version>
```

Tùy chọn: `-SkipTests`, `-BuildLegacy`. `-SkipBuild` không được hỗ trợ cho
publish Setup chuẩn vì mỗi lượt phải dựng WPF Update mới.
Publisher dùng SDK .NET 10 ở `DEV_RUN\dotnet-sdk-10`, target runtime .NET 8
và đóng runtime riêng trong `app/dotnet/` để EXE chạy không cần cài .NET ngoài.

Chỉ model CT2/OPUS-MT được đóng gói; VinAI và PyTorch không nằm trong sản phẩm.

Build, verify, smoke và package chạy trong registered
`tests/golden/_work`. Publisher xác minh payload/hash trước khi thay Setup và
atomically công bố feed; ReleaseRoot chỉ còn `Setup.exe` và `Updates`. Báo
version, source SHA, Setup/package SHA256, payload size và số package/byte được
giữ lại. Chỉ khi tất cả release gates và acceptance bắt buộc đạt mới gọi
`RELEASE_VERIFIED`.

## Chuẩn bị 0.1.2

`v0.1` là bản public đầu tiên, `0.1.2` là source đang chuẩn bị. Publisher hiện
cần `-WpfUpdateVersion` lớn hơn version Setup đang build; đặt cả hai 0.1.2 sẽ
bị validator từ chối. Không nâng version hoặc tạo baseline giả để chạy qua gate.
Bản v0.1 nhận WPF asset có version đúng stable tag; nhận bridge 0.1.2 rồi nhận
full-app 0.1.2 bị strictly-newer gate chặn. Kế hoạch bridge 0.1.1 riêng trước
full-app 0.1.2 hoặc Setup 0.1.2 cần quyết định Owner; thao tác publish chỉ sau
ủy quyền riêng. `-FullAppUpdateBaselineRoot` cần baseline thực có inventory/hash
và provenance; package provenance giả trong harness không là Release evidence.

DEV setup và danh sách prerequisite/gate nằm trong `docs/DEVELOPMENT.md`.
Trước candidate: commit source/version sạch, epoch hợp lệ, scoped cleanup <=1GiB,
full regression + affected gates trên SHA cuối. Sau build: payload audit/hash,
release verify, smoke hai cwd, installer/GUI và installed upgrade/rollback/recovery.
Giữ raw command/output/exit code/skip/warning và lifecycle trước disposal. Không
suy candidate đạt từ focused gate; public stable GitHub vẫn **NOT VERIFIED**.
