# Phát triển VNText Studio

Tài liệu này mô tả thiết lập mới, độc lập với máy và checkout khác. Windows cần thiết để build/chạy ứng dụng WPF. Không sao chép virtualenv, cache NuGet, model, game hoặc artifact từ một máy khác.

## Yêu cầu

- Python 3.11 trở lên.
- .NET SDK 8 để build ứng dụng WPF `net8.0-windows`.
- .NET SDK 10 cho workflow harness và release tooling hiện tại.
- Git và kết nối mạng cho lần cài package. CTranslate2 được pin trong `requirements.txt`; model không được đóng gói trong source.

## Python worker

Từ thư mục gốc repository, tạo môi trường mới rồi cài dependency đã khai báo:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Chạy focused test Python theo phạm vi task và `TEST_MATRIX.md`, ví dụ:

```powershell
python tests/unit/test_entrypoint_docs_version.py
```

Một số kiểm tra dịch cần model OPUS-MT riêng và thời gian tải lớn. Model không nằm trong clone; chỉ lấy model theo quy trình/điều khoản của nguồn tương ứng. Test dùng dữ liệu game thật là opt-in, không thuộc unit suite mặc định.

## WPF development app

`DEV_RUN` là thư mục output local tổng quát, được ignore bởi Git; có thể dùng để
build/run ứng dụng trong lúc phát triển và không đưa nội dung của nó vào commit.
Build app từ repository root bằng .NET SDK 8 vào thư mục đó:

```powershell
dotnet build wpf_app/VNText.Studio.App/VNText.Studio.App.csproj -c Debug -o DEV_RUN
```

Chạy app và kiểm tra worker:

```powershell
.\DEV_RUN\VNText.Studio.App.exe
.\DEV_RUN\VNText.Studio.App.exe --smoke-worker
```

Workflow harness được gọi qua Python và cần .NET SDK 10 cùng các input/runtime test được mô tả trong script. Xem `tests/README.md` và `TEST_MATRIX.md` để chọn gate phù hợp; command harness:

```powershell
python tests/unit/test_wpf_workflow.py
```

## Release build

Release tooling cần .NET SDK 10. Dùng `TEST_MATRIX.md` để chọn build, smoke và
acceptance gates phù hợp trước khi tạo package. Lệnh publisher local từ root
repository:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File release/publish.ps1 -WpfUpdateVersion 0.1.1
```

Publisher có thể ghi vào delivery directory local; kiểm tra options và boundary
trong `release/publish.ps1`/`TEST_MATRIX.md` trước khi chạy. Lệnh này không upload
hoặc tạo GitHub Release; thao tác publish ra ngoài cần Owner ủy quyền riêng.

Build hoặc mock/harness PASS không xác nhận cài đặt, cập nhật GitHub, installer, game compatibility hay release. Mỗi kết luận phải nêu chính xác command và phạm vi đã chạy.
