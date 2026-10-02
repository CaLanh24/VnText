VNText Studio — source setup

Tai lieu nay danh cho checkout source public, khong phai tai lieu cai dat
Windows per-user. Source khong kem game, model, Release binary hay du lieu
nguoi dung.

Cai dat dependency bang Python/PowerShell:
1. Cai Python 3.11+ va .NET 8 SDK.
2. Tai source va chay:

   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Bo requirements mac dinh theo san pham CT2/OPUS-MT. Payload cua Setup WPF can
duoc kiem tra rieng truoc khi phat hanh.

Build va chay ban dev:

   dotnet publish wpf_app\VNText.Studio.App\VNText.Studio.App.csproj -c Release -r win-x64 --self-contained false -o DEV_RUN
   .\DEV_RUN\VNText.Studio.App.exe --smoke-worker

Quy trinh extract/translate/patch chi duoc thuc hien tren game copy do nguoi
dung chon. Khong patch game goc.

Cap nhat source: dung git pull, sau do chay lai cac lenh setup/build o tren.
Tao Release bang:

   pwsh -NoProfile -ExecutionPolicy Bypass -File .\release\publish.ps1 -WpfUpdateVersion <newer-version>

Source public khong theo doi cac launcher cai dat/cap nhat cu. Cac script patch
duoc tao luc runtime la mot phan cua contract patch va do app quan ly.
