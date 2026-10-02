VNText Studio

VNText Studio la ung dung WPF de extract text game, dich/nhap CSV va tao patch
fail-closed tren ban sao game do nguoi dung chon. Route dich san pham duoc ho
tro la CT2/OPUS-MT local.
Repository nay la source generic; khong kem game, corpus dich, model weights,
Release binary hay du lieu nguoi dung.
Phien ban source hien tai: 1.45.0 (ban phat trien, khong phai release public).

Cai dat tu source:
1. Cai Python 3.11+ va .NET 8 SDK.
2. Tao moi truong va cai dependency bang Python/PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Full WPF workflow test va publisher can them .NET 10 SDK tai
`DEV_RUN\dotnet-sdk-10`; SDK nay khong nam trong source. Test WPF co the dung
DEV_RUN root khac qua `VNTEXT_DEV_RUN_ROOT`.

Build/chay app dev:

```powershell
dotnet publish wpf_app\VNText.Studio.App\VNText.Studio.App.csproj `
  -c Release -r win-x64 --self-contained false -o DEV_RUN
.\DEV_RUN\VNText.Studio.App.exe --smoke-worker
```

Quy trinh:
1. Chon game copy ngoai repository va bam Extract.
2. Kiem tra package gom translation.csv va manifest.json.
3. Dich/nhap CSV bang CT2/OPUS-MT local.
4. Validate, bam Patch va doc lai target de xac minh; khong patch game goc.

Entry chi vao luong chinh khi co locator, writer va read-back proof. Candidate
khong du proof duoc giu la REVIEW_REQUIRED, EXTRACT_ONLY hoac UNSUPPORTED;
khong bi xoa hoac fallback ngam. Fixture Unity/game that phai duoc cap qua
VNTEXT_GAME_FOLDER va test opt-in.

Tao ban build noi bo bang script PowerShell:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\release\publish.ps1 `
  -WpfUpdateVersion <newer-version> `
  -GitHubOwner Calanh24 `
  -GitHubRepository VnText
```

Publisher chi bundle model CT2. VinAI khong con duoc cung cap trong app hoac
bo cai. Source khong kem model weights; neu model chua co, app tai model CT2/OPUS-MT
tu Hugging Face khi dich lan dau. Dat VNTEXT_CT2_NO_DOWNLOAD=1 de tat viec tai va
tu cung cap model local. Setup co the da kem model.

README.md la tai lieu clone/setup chuan. Setup co the duoc cau hinh de kiem tra
stable GitHub Releases voi hai tham so owner/repository o lenh publisher. App
chi ap dung goi WPF da xac minh; thay doi worker, runtime hoac installer can
Setup moi. Feed Updates local van la preview rieng. Test mock da co, nhung cap
nhat qua GitHub tren ban cai thuc te chua duoc xac minh. Python legacy khong
bat URL cap nhat tu xa mac dinh; can cau hinh VNTEXT_UPDATE_URL hoac dat
RELEASE.json canh EXE. Day khong phai luong updater WPF.

Apache-2.0 chi ap dung cho source VNText; xem THIRD_PARTY_NOTICES.md cho font,
model va dependency ben thu ba. File-level tests khong chung minh E2E cho moi
game hoac moi engine.
