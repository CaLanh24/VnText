# Trạng thái hiện tại — VNText Studio

## Cleanup toàn DEV — implementation đạt, disposition còn blocked (2026-10-04)

- Owner đã duyệt disposition trong Brain turn `01a1057b-96e0-7eb3-9fc4-3cec1bbd1a0b`,
  và xác nhận remaining root tại `01a105ad-e143-7851-a149-8754044831a5`.
  Tất cả tài nguyên giữ trong DEV. Bộ bảo toàn 564 file đã hash-verify;
  candidate tại `DEV_RUN/candidate-0.1.2/`, evidence/source test-only `f314a52`
  tại `DEV_RUN/evidence/cleanup-20261004/`. SDK 10.0.401 và pip cache dùng chung.
- Hai normal-close attempt thất bại; Owner cho terminate đúng hai process thử,
  exit 137, không tính GUI shutdown PASS. `ia` move tới baseline fullapp-013;
  all-file hashes khớp sau move; r12i và v01_audit/installed không đổi hash.
- 14/15 root disposal hoàn tất. Remaining root rc-14840e5-source chỉ còn wheel
  11.090 byte: Remove-Item thường và extended-length đều Access denied; ACL
  query cũng bị từ chối. Không sửa ACL/bypass; giữ raw errors/receipts.
- Complete main-root inventory sau tests: non-exempt 761.249.773 byte,
  combined exempt 3.854.821.885 byte, đạt hai cap dung lượng. Đây là số tại
  lúc đo, không phải cleanup PASS. Whole cleanup dry-run REVIEW_REQUIRED:
  ba UNKNOWN (signal-probe, report135byte, test-temp); giữ nguyên nội dung.
  Mười missing claim đã khép bằng deletion provenance có sẵn trong raw report
  rc-53cb9f8-full-unit-20261003, không dựng lại hoặc đổi outcome lịch sử.
- Focused/affected quota, cleanup, Release runner, work-path/write-policy:
  94 test, 0fail/error, 1skip, exit0 trên working source parent09804fd.
  Sáu wrapper integration đã chạy đạt. Skip external Unity fixture unset.
  Source gate counts containing main checkout from nested snapshots, enforces
  1GiB non-exempt +5GiB combined exemptions, blocks child/payload preflight.
  Generic cleanup path/ownership guards giữ nguyên. Raw logs/receipts:
  `.scratch/cleanup-review/`; preservation manifest nằm trong evidence root.
- Không build/full regression/Release/push/upload. Runtime candidate evidence
  vẫn gắn SHA060180f; public stable GitHub update NOT VERIFIED.

- Repository chính thức: [CaLanh24/VnText](https://github.com/CaLanh24/VnText), nhánh `main`. Clone mới chỉ cần source public và dependency theo `docs/DEVELOPMENT.md`; không tìm candidate, checkout hoặc lịch sử private.
- Owner yêu cầu một bản công khai `0.1`, README tiếng Việt dành cho người dùng và giữ mã test cần thiết, không đưa dữ liệu chạy test vào Git.
- [Release v0.1](https://github.com/CaLanh24/VnText/releases/tag/v0.1) đã công bố. Source build/tag: `4d22170a081557e1bf0ad11190f005a01c3edb74`; version sản phẩm `0.1.0`, version file Windows `0.1.0.0`. Các commit tài liệu sau đó không thay source/runtime của Setup này.
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
