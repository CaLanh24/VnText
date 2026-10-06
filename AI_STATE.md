# Trạng thái hiện tại — VNText Studio

## DEV source 0.1.4 — update card simplification (2026-10-06)

- Working source changes simplify the WPF GitHub update card to one explicit
  stateful action: idle/checking/current/update/error. Local preview controls and
  technical update text are no longer rendered. This is source work only; no
  Setup, GitHub upload, publish, or installed-app acceptance was run for 0.1.4.
- `.dev-env` uses Python 3.12.14, the pinned requirements, official .NET SDK
  10.0.401, and OPUS-MT CT2 revision from `vntext/mt_ct2_constants.py`; model
  cache is outside Git. Focused UI assertions passed; the affected harness was
  built with the available .NET 8 targeting packs and the isolated fixture UI
  checks passed. The full harness remains unclaimed because its offline runner
  timed out and is not promoted to PASS.
- DEV executable was published to `DEV_RUN/VNText.Studio.App.exe`. With
  `VNTEXT_WORKER_PYTHON` and the pinned model path configured, `--smoke-worker`
  exited 0 and reported `smoke-translate` `complete` with `ok=true`, plus
  successful extract/patch steps. `TEST_RUN` was terminal and removed; public
  GitHub update acceptance remains the prior bounded 0.1.3 evidence.

## Stable update 0.1.3 đã public; installed-app GitHub acceptance PASS trong bounded scope (2026-10-05)

- Owner trực tiếp xác nhận trong chat DEV: "Cho phép push và publish stable
  0.1.3", sau các gate và Brain review. Main/tag `v0.1.3` đã push exit0;
  [Release v0.1.3](https://github.com/CaLanh24/VnText/releases/tag/v0.1.3)
  public stable/latest, không draft/prerelease. Offer/apply/restart trên bản cài
  0.1.2 của Owner đã PASS; toàn product vẫn chưa `RELEASE_VERIFIED`. Source artifact/tag giữ đúng
  `cdf3ee0e11afa9fc85caab18959a59a9bdc6aed3`; docs sau publication không
  relabel candidate/evidence theo HEAD mới.
- Full-app ZIP `full-app-update-0.1.3-0e29640bce9604ca.zip`, 1.978.560byte,
  SHA256 `0e29640bce9604ca0ea6177dcd897285d393546cc7c2ed4dc7bce12e0476d106`.
  API read-back5asset size/digest/state khớp, remote tag/source đúng; tải ZIP
  public không đăng nhập cũng khớp byte/hash/manifest/source. v0.1/v0.1.2
  body/tag/flags/assets giữ nguyên. Receipt tại
  `DEV_RUN/candidate-0.1.3/publication/publication-summary.json`.
- Exact sourcecdf: full679tests,0failure/error,8skip,0warning,child/wrapper0,
  epoch verify0,cleanupPASS; build WPF/Release verify/two-cwd five-step smoke0;
  actual Patch Installer/GUI3/3,child/wrapper0,cleanupPASS. Ba skip thiếu EXE
  trong snapshot được kiểm riêng bằng candidate3/3; một legacy Tk/init.tcl và
  bốn external Unity/game opt-in vẫn skip, không quảng bá đã kiểm. Evidence:
  `DEV_RUN/candidate-0.1.3/evidence/REVIEW_PACKET.md` và `review-packet.json`.
- Bản sao `DEV_RUN/baselines/stable-012` có provenance đúng Setup0.1.2 public
  source060180f/7133records, không copy dữ liệu Owner. Actual local tests:
  baseline mismatch/tamper/health-failure exit5; interruption7, startup/helper
  recovery0; apply0.1.2→0.1.3 và installed smoke0; normal GUI close/reap0.
  Target7132app records khớp; fixture data,23model và Uninstall giữ nguyên.
  Root này hiện là witness0.1.3, không còn là pristine0.1.2. Bản cài Owner tại
  `C:\Users\Hiu\Downloads\Compressed\Release 0.1` được re-audit chỉ đọc sau
  tests, vẫn đủ7133hash/size của public0.1.2, không bị agent apply.
- Snapshot s13/staging p13 đã preserve SHA-checked lossless evidence rồi
  dispose đúng scope exit0. Whole-root inventory hoàn chỉnh, UNKNOWN/LOCKED/
  STALE/unexpectedMISSING0; khoảng558MB nonexempt và4,37GB exempt, trong caps
  1+5GiB. Giữ r12i/v01_audit/fullapp-013/dữ liệu Owner và root chưa đủ ownership.
  Runtime/cache dùng chung; không tạo environment/SDK/model cache mới.
  Bản sao payload duy nhất trong lượt này nằm ở baseline Owner đã duyệt.
- Package52ad5e7 b19b556d và test-onlyf314 không publish. Raw failures/skip và
  caller remediation được giữ, không đổi failed wrapper thành PASS. Guard
  portable Python home đã sửa đúng owner cdf, focused/affected23/23; không nới
  package/path/model validator. Historical WPF0x80070497 root cause UNKNOWN,
  không tái hiện ở focused/full cuối; không sửa updater theo suy đoán.
- **Public stable GitHub button acceptance đã quan sát trên bản cài thật** theo
  mục bên dưới; vẫn không gọi `RELEASE_VERIFIED` cho tới khi các giới hạn còn
  lại được khép. Setup/uninstall UI là Owner-reported,
  raw native process exit UNKNOWN; native/framework/dependency/model version
  migration không kiểm trong gói này vì bytes kế thừa nguyên từ Setup0.1.2.
  Không gọi RELEASE_VERIFIED. Người mới/v0.1 dùng Setup0.1.2; không có Setup013.

## Stable GitHub acceptance trên bản cài Owner (2026-10-05)

- Brain đã thao tác trực tiếp cửa sổ `C:\Users\Hiu\Downloads\Compressed\Release 0.1\VNText Studio.exe` theo ủy quyền Owner: UI ban đầu 0.1.2 hiện `Stable full-app update available: v0.1.3`; xác nhận Apply; app tự đóng và mở lại. UI sau restart hiển thị 0.1.3, `VNText Studio is up to date with stable GitHub releases.`, và log UI ghi Python worker sẵn sàng. Đây là UI evidence trực tiếp của offer/apply/restart, không chạy lại regression.
- Coordinator chỉ đọc sau thao tác: `.update/work/github-update-0.1.3-babdcc63d88a414c915a61530a0f1f6b.zip` 1.978.560 byte, SHA256 `0e29640bce9604ca0ea6177dcd897285d393546cc7c2ed4dc7bce12e0476d106`, khớp asset stable v0.1.3 và manifest. Inventory app sau update **7.132/7.132**; `app/RELEASE.json` version0.1.3/source cdf3ee0/tree fingerprint đúng; replace đúng5 file. `app/worker/models/**` giữ23 records; `data/` chỉ được kiểm sự hiện diện/đường dẫn, không đọc nội dung user data. Uninstall hash được giữ lại; backup/staging transaction đã terminal (0 file).
- Raw `.update/update.log` ghi `installed VNText Studio.exe`, bốn file metadata/worker, `full-app health check passed`, `full-app update completed`. Evidence gọn: `DEV_RUN/candidate-0.1.3/publication/owner-installed-acceptance.json`; UI observation và hash/inventory verification được tách rõ trong file này.
- Phạm vi kết luận: stable GitHub discovery, offer, apply, restart, installed version, package/source/hash, app inventory và worker-ready UI đã có bằng chứng trên bản cài thật. Vẫn **không gọi RELEASE_VERIFIED**: Setup/uninstall native exit và acceptance sản phẩm rộng hơn chưa có raw gate; nội dung user data không được đọc; native/runtime migration không đổi trong package; không thực hiện nút Apply lần nữa.

## Setup 0.1.2 public prerelease (2026-10-04)

- Owner yêu cầu tải thử Setup mới tại Brain turn01a106d0. Đã publish
  former v0.1.2 prerelease (now consolidated into the public 0.1 release),
  không stable/latest; tag đúng candidate source060180f8ba6c4c970dab7f3261d65b5c5d654f95.
- [public Setup](https://github.com/CaLanh24/VnText/releases/latest/download/VNTextStudio-0.1-Setup.exe)
  221.787.648byte, SHA256b374c2e24293d5a8bf9aa5e4b08863f97cde6ab61a6238eaf1fe659a529826e5.
  Upload/create và API read-back exit0;6assets size/digest khớp local: Setup,
  SHA256SUMS, RELEASE.json, payload-manifest, candidate-manifest và notices.
  Metadata/notices lấy từ chính Setup;7133manifest records khớp evidence.
- v0.1 tag/assets/metadata và latest giữ nguyên. Không upload full-app delta
  baselinev0.1 hoặc test-only013. Không rebuild/copy Setup/environment.
  Receipt tại DEV_RUN/candidate-0.1.2/publication/publication-summary.json;
  cleanup pre/post upload exit0/PASS, whole-root cap1+5GiB vẫn đạt.
- Bản thử chưa RELEASE_VERIFIED: Setup upgrade process exit UNKNOWN,
  uninstall UI/native runtime version migration chưa nghiệm thu. Public stable
  GitHub updater NOT VERIFIED; app bỏ qua prerelease. Backup data trước nâng cấp;
  uninstall xóa cả data. Đây là quyền publish bản thử, không quyền promote stable.

## Source prepublication review (2026-10-04)

- Owner yêu cầu tự kiểm/hoàn thiện và đẩy GitHub tại Brain turn01a106a1;
  scope hiện tại là source push sau Brain review, chưa upload/publish Release.
  Chỉ thị không-push cũ trong chronology bên dưới không còn là quyền hiện tại.
- Remote read ngoài sandbox: main0958358, v0.1 tag4d22170; gh api user trả
  CaLanh24. Sandbox credential/401 failures không chứng minh login hỏng.
  Main là descendant của remote, không force/rewrite/config change.
- Candidate giữ SHA060180f/hash riêng: Setup b374c2e2 (221.787.648byte),
  full-app757e78cc (14.131.877byte); không relabel theo HEAD tooling/docs.
  Raw full656/0error/7skip và publisher/verify/two-cwd smoke đã đối chiếu;
  installer2/2 và GUI1/1 sau build khép3 executable-dependent skips,4 external
  Unity/game opt-in vẫn deferred. Build có2 sacremoses warnings và thông báo
  thiếu optional PyTorch; không cài PyTorch cho routeCT2.
- Setup upgrade audit7133files không mismatch, data fixture giữ nguyên;
  process exit vẫn UNKNOWN, không suy exit0 từ báo cáo Owner/cài thành công.
  Full-app test-only013 sourcef314a52 thay python312.zip, giữ23model/data/
  uninstaller, smoke0; đổi phiên bản native Python/.NET và stable GitHub button
  acceptance chưa chứng minh. Studio Setup uninstall UI chưa có acceptance.
- Bổ sung2 prerequisite-negative fixtures cho bootstrap; focused/affected33test,
  0fail/error/skip,exit0. Đây là modeled missing dependency/tool detection,
  không VM/fresh-machine install. Production bootstrap/runtime không đổi.
  Bounded tracked audit370file: không runtime/build/cache/log/game artifact
  paths hoặc credential-pattern hits; không claim exhaustive secret audit.
- Packet/raw audit: `.scratch/prepublication`; không tạo environment/candidate,
  tải/cài dependency hoặc sửa Release. Public GitHub update NOT VERIFIED.

## Public DEV bootstrap (2026-10-04)

- Owner yêu cầu triển khai kế hoạch sau cleanup tại Brain turn01a105cc;
  task bounded ở `release/dev_bootstrap.py`, tests và hướng dẫn DEV.
- Preflight mặc định chỉ đọc; build/smoke offline dùng dependency chung,
  marker output riêng và quota toàn root, dự phòng128MiB. Không cài/tải,
  copy venv/SDK/model hoặc đổi product/updater. Release preconditions tách riêng.
- Tooling commit `3b43b29aa30cefbd237143ceb76ff07b0a18d8c1`:
  focused/affected31tests,0fail/error/skip,exit0 trước commit, source tool/test
  không đổi sau validation. Clean local Git source checkout tại đúng SHA này
  build/smoke và repeated run exit0,0build warnings; đủ5bước, complete
  extract/translate/patch ok=true,cleanup_error=null. Checkout20.311.250byte,
  không có venv/SDK/cache riêng, dùng dependency chung với path tường minh.
- Raw commands/stdout/stderr/exit ở `.scratch/bootstrap-dev`; lỗi NuGet profile,
  Unicode redirect và disposal read-only Git pack trước đó giữ verdict riêng.
  Disposal đầu exit1; bỏ read-only3packfile của exact owned disposable clone,
  hash không đổi, retry exit0; clone đã absent. Canonical dry-run exit0/PASS,
  UNKNOWN/LOCKED/errors/unexpected missing0. Whole-root inventory complete:
  non-exempt767.982.458byte,exempt3.854.852.003byte, cả hai dưới cap1+5GiB.
  Peak quan sát trong repeated run: non-exempt787.016.568byte,exempt3.854.852.003.
- Clone kiểm là source sạch từ Git local, không phải remote clone/fresh machine
  dependency installation. Model hashes/package metadata không thay provenance
  download/revision/license; thiếu dependency cần quyền riêng trước cài/tải.
- Đây không phải bằng chứng cài dependency trên máy mới hoặc Release candidate
  exact-HEAD. Candidate/runtime evidence vẫn SHA060180f; public GitHub NOT VERIFIED.

## Cleanup toàn DEV — disposition hoàn tất (2026-10-04)

- Owner duyệt disposition tại Brain turn01a1057b, exact remaining root tại
  turn01a105ad, retention/ACL tại turn01a105b5 và exact-file admin takeover
  tại turn01a105b9. Tất cả tài nguyên ở trong DEV; 15/15 root đã disposal.
- Bộ giữ 564 file tại DEV_RUN/evidence/cleanup-20261004 hash-verify, 0mismatch;
  candidate 0.1.2 tại DEV_RUN/candidate-0.1.2; source test-only f314a52 vẫn
  đọc được từ source-test013.git. SDK10.0.401/pip cache dùng chung, không thêm
  snapshot/venv/model. Ba baseline approved giữ nguyên data/model.
- Hai normal-close thử không thành công; terminate app/worker theo quyền Owner
  exit137, không tính GUI shutdown PASS. Baseline ia chuyển sang fullapp-013;
  hashes all-file khớp sau move. r12i và v01_audit/installed giữ nguyên.
- Wheel11.090byte bị Access denied với path thường/dài; ACL cha thành công
  nhưng ACL file thất bại. Admin takeown/icacls exact-file theo quyền riêng
  exit0, wheel đã xóa; chỉ xóa directory rỗng còn lại, không ACL đệ quy.
- signal-probe/report135byte và test-temp rỗng đã RETAINED theo quyết định giữ
  hiện tại của Owner; hash report không đổi, lịch sử vẫn UNVERIFIED. Mười
  missing claim khép bằng provenance có sẵn trong raw report rc-53cb9f8,
  không đổi verdict report lịch sử. Main root không có active epoch; snapshot
  epochs giữ trong evidence, không import/recreate hoặc suy Release PASS.
- Complete whole-root inventory sau disposition: non-exempt762.619.937byte,
  combined exempt3.854.821.885byte, dưới cap1+5GiB. Canonical _work dry-run PASS,
  UNKNOWN0/unexpected missing0/LOCKED0/errors0. Exact receipt/log/inventory:
  .scratch/cleanup-review/acceptance-complete.json và disposition-terminal.json.
- Quota implementation commit a773def: counts containing main checkout from
  nested snapshot, enforces both caps and blocks child/payload preflight;
  generic path/ownership validators unchanged. Focused/affected94tests,
  0fail/error,1skip,exit0; six wrapper integration passed. Skip external Unity
  fixture unset. Tooling unchanged after validation; later commits docs-only.
- Task này không build/full regression/Release/push/upload; candidate/runtime
  acceptance evidence vẫn SHA060180f. Public stable GitHub update NOT VERIFIED.

- Repository chính thức: [CaLanh24/VnText](https://github.com/CaLanh24/VnText), nhánh `main`. Clone mới chỉ cần source public và dependency theo `docs/DEVELOPMENT.md`; không tìm candidate, checkout hoặc lịch sử private.
- Owner yêu cầu một bản công khai `0.1`, README tiếng Việt dành cho người dùng và giữ mã test cần thiết, không đưa dữ liệu chạy test vào Git.
- Release public 0.1 hiện được duy trì tại [stable release page](https://github.com/CaLanh24/VnText/releases/tag/v0.1.3). Source build/tag lịch sử của Setup đầu tiên: `4d22170a081557e1bf0ad11190f005a01c3edb74`; version sản phẩm `0.1.0`, version file Windows `0.1.0.0`. Các commit tài liệu sau đó không thay source/runtime của Setup này.
- Setup mới: 221.765.120 byte; SHA-256 `4ec759a72114a87570fd1e6bbf9b4b239f32f02a5dd02b365b4f5294bb998e2e`. Digest asset GitHub khớp file build. Release chỉ chứa `Setup.exe` và `SHA256SUMS.txt`; hai Release/tag `v1.45.0`, `v1.45.1` đã xóa theo yêu cầu Owner.
- Publisher, build, release verify và smoke hai cwd đạt. Đối chiếu trực tiếp toàn bộ 7.134 file payload với manifest không có hash/size sai, file thiếu hoặc thừa; Intel/NVIDIA DLL và notice khớp provenance. Không có FMOD native binary hoặc Argos; helper Python `fmod_toolkit`/`pyfmodex` vẫn có trong payload, không đồng nghĩa có quyền phân phối FMOD native binary.
- Unittest trên source build: 651 test, 0 fail, 0 error, 7 skip, 0 warning. Sau build, kiểm tra installer 2/2 và GUI shutdown/worker reap 1/1 đạt; WPF harness 7/7 và DEV smoke đạt. Các skip cần game ngoài không chứng minh hỗ trợ mọi game hoặc chất lượng dịch.
- Canonical wrapper của full regression vẫn ghi `CANCELLED` dù child exit 0; nguồn keyboard interrupt chưa xác định. Cleanup hai lượt focused artifact là `REVIEW_REQUIRED`, có cảnh báo đường dẫn bị xóa ngoài registered scope. Không đổi các trạng thái này thành PASS; **RELEASE_VERIFIED chưa đạt**.
- Route dịch sản phẩm: CT2/OPUS-MT; phạm vi engine/định dạng có giới hạn. Bản cài thử v0.1 đã nhận gói WPF local 0.1.1 theo báo cáo acceptance trước đó; GitHub public vẫn **NOT VERIFIED**.
- Full-app updater, source-bound publisher và Setup ownership-sidecar merge đã được triển khai sau baseline HEAD `0958358c3c7b38a5cae24c21c79b9368bebc6aa3`. Focused C#/publisher tests, WPF build và DEV smoke exit 0; stdout/stderr smoke rỗng, worker events được kiểm trong source smoke chứ không có transcript. Bản sao của Setup v0.1 cài thật đã qua local bridge 0.1.1→0.1.2/0.1.5, full-app fixture 0.1.2→0.1.3 (worker/runtime), bảo toàn 25 file `data/`/model, worker smoke exit 0, baseline tamper từ chối exit 5, health-failure rollback exit 5, và startup recovery sau injected interruption exit 7. Các fixture dùng provenance giả có chủ đích, không phải Release candidate. GitHub asset behavior mới chỉ được kiểm bằng mocked HTTP; Setup.cs chỉ source-reviewed, Setup build chưa chạy. Chưa có exact Release candidate/Setup upgrade hoặc public stable-GitHub acceptance; cập nhật trong app vẫn **NOT VERIFIED**. Thay Setup/uninstaller hoặc quyền hệ thống vẫn cần Setup; model files được pin và không cập nhật bằng full-app delta.
- Người dùng bản 1.45.x cần sao lưu dữ liệu và cài Setup 0.1, không tự cập nhật xuống version thấp hơn. Gói WPF 0.1.1 do publisher tạo trong môi trường build không được đăng lên Release 0.1. `Updates` local không phải feed GitHub.
- Source Git không chứa `DEV_RUN`, `_work`, game, model hoặc artifact binary. Dữ liệu/evidence local không phải prerequisite hay bằng chứng PASS cho clone mới; giữ outcome hiện tại và không dựng lại lịch sử đã mất.
- Owner chọn `0.1.2` cho source chuẩn bị gate updater toàn app. Đây chưa phải Release candidate đã nghiệm thu; chỉ chạy Release gates trên một commit sạch trong snapshot cô lập sau khi registry/epoch và cleanup đạt. Public stable-GitHub update vẫn `NOT VERIFIED`.

## Chuẩn bị 0.1.2 — evidence đã ingest

- Tại `e59c3aac67890bdede8312f681f247120ea8b686`: focused cleanup 74/74,
  affected runner 3/3; full regression 651 test, 0 fail/error, 8 skip,
  child/wrapper exit 0 và scoped cleanup PASS. Các skip: 2 installer và 1 GUI
  chưa có executable build; 1 legacy Tk thiếu Tcl usable; 1 work-path và 3
  worker-QA cần game opt-in. Installer/GUI là gate cần chạy sau build; external
  game/visual/semantic acceptance vẫn theo phạm vi deferred của CONTRACTS.
  Evidence này gắn riêng SHA đó, không xác nhận candidate/source sau sửa.
- Publisher blocker QML tại `38123f94962ca96c82036535995f1da289f11ed9` đã sửa:
  focused integrity 1/1, affected Setup package 5/5, exit 0 và cleanup PASS.
  Giữ hash của cả bốn asset WPF; không tạo asset QML giả. Chưa chạy Release build
  trên SHA này. Raw evidence giữ trong snapshot local, không đưa vào Git.
- Smoke diagnostic thay đổi đang được kiểm bằng worker thật: model vắng trả 24
  ở bước translate với error/summary, model hiện có trả 0 qua đủ năm bước;
  đây là precommit DEV evidence, không phải nghiệm thu candidate.
- Source v0.1 chỉ chọn asset WPF theo version tag; manifest/EXE phải khớp version.
  Bridge 0.1.2 rồi full-app 0.1.2 không hợp lệ vì updater yêu cầu strictly newer.
  Publisher hiện còn dùng Setup A 0.1.2 làm baseline WPF nên không thể tạo B
  0.1.2 theo command cũ. Đã xin Owner chọn bridge 0.1.1 riêng trước full-app
  0.1.2, hoặc dùng Setup 0.1.2 làm điểm bắt đầu full-app. Chưa quyết định/publish.
- Không push/upload/sửa Release. Candidate 0.1.2 và stable GitHub update trên
  bản cài thực tiếp tục **NOT VERIFIED**. `DEV_RUN/v01_audit`, `test-temp` và
  artifact chưa đủ ownership được giữ nguyên; scoped cleanup không chứng minh
  cleanup toàn checkout hoặc giải quyết lịch sử UNKNOWN.

- Clone sạch tại `3d07265`: venv mới Python 3.12.14 từ runtime local, requirements
  public qua PyPI/cache, pip install/check/inspect UTF-8 exit 0; SDK 8.0.424 và
  SDK 10.0.401 có sẵn từ Microsoft; 10 model file khớp revision/ETag. Epoch verify
  và cleanup preflight exit 0. DEV build 0 warning/error, smoke lỗi model exit 24
  có diagnostic và smoke model thật exit 0; đây là DEV, không là candidate.
- Full regression `3d07265`: 652 test, 0 fail/error, 7 skip, child exit 0 nhưng
  wrapper exit 1 / cleanup REVIEW_REQUIRED. UNKNOWN là container rỗng
  `tmp/full-app-publisher`: helper đăng ký RETAINED dưới scope riêng của test,
  khác scope wrapper. Test được sửa kế thừa ambient scope và assert `report["ok"]`;
  report cũ không đổi thành PASS. EXE DEV mặc định mang 1.0.0, nên project app được
  sửa đọc VERSION.txt; override fixture vẫn riêng. Cần validation trên SHA sạch
  mới sau các sửa này. Hai installer skip vẫn cần build/acceptance; Tk legacy và
  bốn game opt-in skip không chứng minh acceptance sản phẩm.

- Owner đã chọn Setup 0.1.2 cho người còn ở v0.1; full-app cập nhật từ baseline
  mới. Không phát hành bridge riêng và không hứa một lần Setup cho baseline cũ.
  Publisher đang được sửa để không bắt buộc tạo gói WPF version cao hơn Setup;
  provenance/hash/model/data validators giữ nguyên. Chưa có candidate nghiệm thu.

- Candidate nội bộ tại `6e5598f`: full 654 test, 0 fail/error, 7 skip,
  child/wrapper 0, cleanup PASS; publisher exit/wrapper 0 và cleanup PASS,
  Release verify + smoke hai cwd đạt. Payload 7.134 file; installer 2/2 và GUI
  close 1/1 đạt trên executable lấy từ Setup. Hậu kiểm GUI phát hiện duy nhất
  `app/worker/.venv/pyvenv.cfg` đổi token thành absolute install path, làm hỏng
  exact baseline. Candidate không nghiệm thu. Runtime launcher đang sửa để
  giữ inventory bất biến; cần gate trên SHA sạch mới. Setup UI thật/upgrade,
  rollback/recovery exact candidate và stable GitHub vẫn NOT VERIFIED.
- Sửa launcher bất biến: precommit focused WPF 7/7, affected release-verify
  7/7; wrapper/child 0 và cleanup PASS, UNKNOWN 0. DEV build 0 warning/error,
  smoke model vắng 24 có worker diagnostic, model thật 0. Probe Python bundled
  trên payload public v0.1 import CT2/UnityPy/Marian thành công, cfg hash không
  đổi; probe này không thay thế acceptance candidate mới. Một focused run ở
  snapshot lồng sâu thất bại WinError 206; snapshot ngắn chạy đạt, không sửa
  test long-path hay validator để bỏ qua lỗi.

- Wrapper full tại `d163a83`: child 655 test, 0 fail/error, 6 skip, exit 0;
  wrapper CANCELLED/exit 1, cleanup PASS. Instrument giữ handler gốc chứng minh
  cache single-writer probe `os.kill(pid, 0)` phát native CTRL_C_EVENT đến wrapper
  sau khoảng 65 ms; SIGINT được xử lý trong `proc.wait()` khi child hoàn tất.
  Không phải bằng chứng full PASS. Cache Windows PID probe được sửa dùng process
  handle, không phát signal, giữ lock khi query không chắc chắn. Precommit focused
  cache 7/7 và affected traceability/runner/CT2 47/47, không skip, child/wrapper 0,
  cleanup PASS/UNKNOWN 0. Cần full và Release gates trên SHA sạch sau sửa.
- Baseline cài thật `r12i` từ Setup public v0.1: 7.134 file khớp hash/size;
  hai file bổ sung là update-source config và data/install-manifest.json. Chưa
  mở app. Owner cho phép build test-only 0.1.3 trong snapshot riêng có commit,
  SHA/version/hash thật để acceptance full-app từ baseline Setup 0.1.2; main
  và candidate sản phẩm vẫn 0.1.2, không push/upload/phát hành. Setup upgrade
  thực tế và stable GitHub vẫn NOT VERIFIED.

## Publication receipt — v0.1.4

- Public stable Release `404241058` titled `VNText Studio 0.1` and tag `v0.1.4` were published from source SHA `a5677ba493755bf5d0b6953c4fd7d45eb2b3cfe0`. Five public assets were uploaded; API size/digest read-back matched retained candidate staging. This receipt is publication evidence only.
- Installed-app offer/apply/restart acceptance from public `0.1.3` to `0.1.4` has not been run; stable GitHub update remains **NOT VERIFIED** for that acceptance layer.
