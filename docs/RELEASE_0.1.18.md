# Release 0.1.18 — ledger

Trạng thái: **ĐÃ PHÁT HÀNH** (2026-11-12T07:02:00Z) — https://github.com/CaLanh24/VnText/releases/tag/v0.1.18 (Latest); tag chú thích `v0.1.18` (`c543869…`) → source dựng `956a7046e3f960f8a08c7338c4cbe50d44cd05cc`; các commit sau trên `main` chỉ là tài liệu. Brain ACCEPT đúng payload này; 5 tài sản tối thiểu đã đọc lại băm từ bản tải công khai (khớp), manifest trỏ đúng ZIP; tài sản/route của v0.1.17 và cũ hơn nguyên vẹn (digest không đổi). Baseline: `v0.1.17` (Setup sha256 `4e56da3e…ccf7f`).

## Nguồn và ứng viên
- Source dựng: `956a7046e3f960f8a08c7338c4cbe50d44cd05cc` (snapshot sạch `RELEASE_RUN/candidate-0.1.18/source`); các commit sau chỉ là tài liệu.
- Setup: `RELEASE_RUN/candidate-0.1.18/setup-018-956a704/ReleaseRoot/VNTextStudio-0.1.18-Setup.exe`, 286,726,656 B, sha256 `454ef46fa68d6211f22bef02981b8405fa28e4bbb300898a8d3e68e9bc5e930a`; payload 7,327 tệp / 589,162,754 B đã xác minh; `VNText Studio.exe` sha256 `9d0d6f291da5d87bdb6274f04617f39af4b5a9e139e6c80acc25775a0b890156`.
- Updater (tối thiểu, trong `ReleaseRoot/Updates`): `full-app-update-0.1.18-f875f83f609f3aa2.zip` (86,935,301 B) + `full-app-update-current.json` (tuyến cho client 0.1.7 bất biến); `full-app-update-from-0.1.17-to-0.1.18-3e6a5d4897310aef.zip` (86,801,135 B) + `…-current.json` (tuyến trực tiếp từ bản công khai 0.1.17). Tài sản cũ của 0.1.17 và trước đó giữ nguyên cho client cũ; không nhân bản ZIP cũ.
- Phụ thuộc Python: khóa băm `requirements/locks/windows-cp312-{runtime,build}.txt` (52 distribution; `tpk_ar` 0.2.4 là sdist chính thức duy nhất, dựng bằng setuptools đã khóa, không tải build-isolation) trong venv mới cô lập `.dev-env/release-venv-0.1.18`; `release/dependency_profiles.py --build --check-installed` PASS, `pip check` sạch. Không sửa `.venv`/`release-venv`/lock. Bảng giấy phép nằm ở `THIRD_PARTY_NOTICES.md`; mọi distribution có license text trong dist-info hoặc trong notice/`app/licenses` (xem `license-files-release-venv-0.1.18.json`).

## Ủy quyền, ngân sách, epoch
- Owner 2026-11-12 ("Xem còn vấn đề gì thì sửa nốt, xong thì release") + mục lưu trữ đứng 2026-10-24: task riêng `release-0.1.18`, trần đo được 3 GiB ban đầu rồi 4.5 GiB (4,831,838,208 B) sau khi hai baseline công khai được giải nén (0.1.17: 584,299,498 B; 0.1.7: 515,688,819 B); không kế thừa ngân sách/khoản 6,75 GiB/chính sách hop của 0.1.17; không rebaseline. Tải phụ thuộc theo lock được cho phép bởi ủy quyền lệnh/mạng của DEV (LOCAL-WORKFLOW 2026-10-25) cho release được giao, không suy từ quyền lưu trữ.
- Epoch chuyển tiếp thường (8-hop quy ước): 029→032 trên `release-0.1.18`; epoch hiện tại gắn source dựng `956a704` (+ hop tài liệu). Lỗi guard thật đã sửa: `registry_metadata_incomplete` do 28.917 bản ghi MISSING lạnh sau nén gzip; mọi vấn đề metadata khác vẫn chặn.
- Đỉnh dung lượng lấy mẫu (project + `C:/vnrg`): 3,968,864,530 B < ngưỡng hủy thật 4,781,506,560 B (= 4,831,838,208 − 50,331,648). Hiệu chỉnh: công cụ đo phụ `bud.py` từng dùng nhầm trần 6.25 GiB của 0.1.17 nên các số "free_to_abort" trong báo cáo chuẩn bị là SAI; profile thực `release-0.1.18` 4.5 GiB được launcher xác nhận gắn HEAD; số đúng ở `budget-correction.json`; các gate publish/updater dùng đúng trần. Mục tiêu dọn cuối: về giới hạn mặc định sau khi consumer kết thúc (xem Cleanup).

## Sửa lỗi / thay đổi từ v0.1.17
- **Glossary (lỗi thật mới xác nhận):** thuật ngữ không còn khớp bên trong từ khác ("ass"/"passage"), token sinh ra không bị thay lại bởi thuật ngữ sau, literal `ZZG…` trong nguồn không bị khôi phục nhầm; khớp theo từ/cụm (chữ Unicode + dấu kết hợp, NFC/NFD), không xếp tầng, token không trùng văn bản gốc; áp dụng cho glossary người dùng và v2; chiến lược cache đổi (`glossary-masking-3`), không xóa bản dịch đã lưu/thủ công. 13 test mới + bộ glossary/MT hiện có.
- **Publisher:** dựng installer patch một-tệp trước smoke worker (smoke Release cần installer này; trước đó smoke patch dừng với "Thiếu installer patch tự chứa").
- **Registry/epoch:** hỗ trợ task `release-0.1.18`, chuyển tiếp 0.1.17→0.1.18 theo phiên bản từng đầu mút, cold-registry MISSING không chặn bước epoch.
- **Icon:** icon thương hiệu sinh lại bằng make_icon.py đã sửa (pixel khác bản cũ) và commit trước khi đóng băng nguồn.
- Từ chu kỳ chất lượng sau 0.1.17 (đã trên `main`): OCR không còn dựng chữ giả trên ảnh không chữ; nhãn "Mã/định dạng game" cho dòng kỹ thuật; patch một phần từ các dòng đủ điều kiện (xác nhận, đếm dòng bỏ qua) với một EXE cài đặt; trạng thái/nhật ký Patch theo bản CSV hiện tại; Analyze thông báo không chặn và tái dùng phân tích khi chỉ đổi thư mục xuất; nhãn tìm CSV xuống dòng; chuyển ngôn ngữ cập nhật trạng thái; nhập bản dịch cũ vào gói đang chọn; Apply/Undo thay thế hàng loạt giữ đúng phiên bản CSV; Setup có điều khoản bản địa hóa; kiểm toán R01–R12.

## Gates (verdict riêng, gắn nguồn)
- Python công khai (`audit_gates --group public` @ code `ad2b05a`): csv 34, mt 91 (gồm 13 test glossary mới), patch 37, maintenance 44 — PASS, 0 skip; installed-model/native = SKIP có chủ đích. `test_setup_package` 13 PASS (chạy KHÔNG đặt PYTHONUTF8). `test_release_verify` + guard publisher + thứ tự installer 11 test PASS @ `956a704`. 215 test cleanup/epoch/registry/dependency/docs trước đó PASS.
- Build/package: `publish.ps1` (isolated, preinstalled locked deps) exit 0 @ `956a704`: release_verify tiền build, WPF 0 cảnh báo, smoke worker DEV và smoke Release exit 0, payload 7,327 tệp xác minh băm. Lần publish đầu @ `ad2b05a` dừng ở smoke patch (lỗi thứ tự installer, đã sửa và có test).
- Updater backend (KHÔNG phải native UI) trên gói thật: tuyến A (payload công khai 0.1.17 → ứng viên) và tuyến B (payload công khai 0.1.7 → ứng viên) — exit 0, version 0.1.18, exe khớp manifest, đọc lại 7,326 tệp 0 lệch, canary dữ liệu người dùng nguyên vẹn, health PASS (`updater018-backend-receipt-route-{A,B}-956a704.json`). Rollback/1175/hash-fail: mã updater app không đổi từ 0.1.17 (`FullAppUpdate*` không có diff) — dùng lại bằng chứng 0.1.17, KHÔNG chạy lại.
- MT/engine/OCR thật: dùng lại bằng chứng 0.1.17/tuần chất lượng cho phần không đổi; phần glossary mới chỉ chứng minh bằng test round-trip + fake translator, không phải chất lượng dịch toàn game.
- NOT_PROVEN: Setup cài mới/nâng cấp/gỡ trên máy thật (GUI-only, Root/Brain), cập nhật công khai trong app sau phát hành, mọi DPI/giao diện, âm thanh, game lớn. Không có test nào bị bỏ qua được tính là PASS.

## Giới hạn phải ghi trong ghi chú phát hành
Dịch offline chỉ là bản nháp thô, cần người rà soát; patch chỉ gồm các dòng đủ điều kiện; engine ngoài Ren'Py/Unity chưa được chứng minh; chất lượng dịch toàn game không được công bố.

## Ghi chú phát hành (nháp, tiếng Việt)
**VNText Studio 0.1.18** — bản vá chất lượng.
- Sửa lỗi từ điển người dùng: thuật ngữ chỉ khớp nguyên từ/cụm, không còn chèn nhầm vào từ khác hay làm hỏng dịch.
- Patch một phần từ các dòng đủ điều kiện (có xác nhận), một EXE cài đặt; nhãn "Mã/định dạng game" cho dòng kỹ thuật; OCR không còn dựng chữ giả trên ảnh không có chữ.
- Giao diện mượt hơn: Analyze thông báo nhẹ, nhãn tìm CSV không bị cắt, đổi ngôn ngữ cập nhật mọi dòng trạng thái.
- Cập nhật trong app từ 0.1.17 (và từ 0.1.7). Dữ liệu người dùng được giữ nguyên.
- Lưu ý: bản dịch offline chỉ là bản nháp thô, cần xem lại; chưa hỗ trợ mọi engine game.

## Checklist native hữu hạn (Root/Brain; DEV không mở UI)
1. Setup 0.1.18 cài mới vào thư mục cô lập (máy sạch/ thư mục tạm): điều khoản VI/EN, bước tài nguyên, hoàn tất, mở app; tên tệp Setup đúng `VNTextStudio-0.1.18-Setup.exe`.
2. Nâng cấp: cài Setup công khai 0.1.17 (tải lại bằng `gh release download v0.1.17`, kiểm sha256 `4e56da3e…`), tạo dữ liệu canary trong `data/`, chạy Setup 0.1.18 chồng lên — dữ liệu còn nguyên.
3. Gỡ cài đặt: từ app/Uninstall khung installer; từ chối khi app đang chạy; thư mục dữ liệu theo lựa chọn.
4. Cập nhật trong app (sau khi Brain ACCEPT và publish): app 0.1.17 thật nhận lời mời 0.1.18, tải, Restart, dữ liệu giữ nguyên (cần Root, không phải DEV).
5. Glossary: CSV nhỏ có thuật ngữ "ass" và câu "The passage is clear." — kết quả dịch không chứa "mông" chen giữa; thuật ngữ "Alice" vẫn được thay đúng.
Fixture: không dùng game thật; thư mục `data/owner-preserve` canary do chính bước kiểm tạo.

## Cleanup
Đã dọn qua helper: fixture updater, scope publish lỗi, scratch release-check/icon/deps (0 refused). Còn giữ đến khi Brain ACCEPT + publish: `RELEASE_RUN/candidate-0.1.18/{source,setup-018-956a704,release-baselines}`, venv `.dev-env/release-venv-0.1.18`. Sau publish: dispose candidate/baselines/source worktree qua helper, trả project về ≤ 1 GiB, giữ receipt/hash.

## Nghiệm thu native (Root, UIA chức năng; ảnh chụp NOT_PROVEN)
Cài mới vào thư mục cô lập: điều khoản/đích tùy chọn, tài nguyên SDK tải thật sẵn sàng (model/renpy/ocr), app mở đúng EXE ứng viên; gỡ khi app chạy bị từ chối, không xóa tệp; gỡ sau khi đóng app hoàn tất, thư mục trống. Nâng cấp: Setup công khai 0.1.17 + 3 canary, Setup 0.1.18 nhận bản cài hiện có, giữ dữ liệu, hoàn tất, ba canary khớp byte, phiên bản/hash đúng, app mở lại. Chụp ảnh thất bại (agent-desktop WGC timeout/BitBlt 0x80070006; Computer Use CreateForMonitor 0x80070057) nên KHÔNG có bằng chứng ảnh/DPI/toàn game. Receipt: `root-native-receipt.json`. Glossary: 6 ca cấu trúc trên model CT2 thật (`glossary-real-model.json`), kèm giới hạn: literal giống sentinel có thể bị model tách khoảng trắng, bản dịch chỉ là nháp thô.

## Nghiệm thu công khai trong app (Root, native) và dọn cuối
- **PASS (chức năng, native):** cài Setup công khai 0.1.17 THẬT (không phải payload giải nén) vào `…/public-native-client`; khi khởi động app nhận lời mời v0.1.18, bấm "Cập nhật ngay", tải xong, "Khởi động lại", app mới (PID 12416) mở với hộp thoại "Cập nhật thành công"; `VNText Studio.exe` sha256 `9d0d6f29…0156` đúng; canary `root-canary.txt` sha256 `ad0fdb9e…1644a` không đổi; giao dịch `txn-45b6da1da4a24ed193e119a945f976c9`, `health_passed=true`, `update.log`: "full-app health check passed / update completed". Receipt: `root-public-native-receipt.json`; bản sao gọn success.json/log/hash: `public-native-client-proof/`.
- **Giới hạn hình ảnh:** Root xem ảnh chụp bước offer/ready/success (banner xanh đọc được); ảnh chụp Setup cài mới vẫn NOT_PROVEN; KHÔNG có bằng chứng DPI/giao diện đầy đủ/toàn game.
- **Dọn cuối (helper chuẩn, 0 refused, không theo junction):** đã dispose toàn bộ `RELEASE_RUN/candidate-0.1.18` (public-native-client + canary sinh bởi test, baseline 0.1.17 và 0.1.7, Setup cũ, source worktree — đã `git worktree prune` —, Setup/payload/updates ứng viên; bản công khai đã xác minh băm) và trung gian publish; combined 3,190,832,059 → 637,329,406 B; project non-exempt 442,416,408 B ≤ 1 GiB (profile mặc định), `.dev-env` dùng chung 11,632,755,202/11,811,160,064 B. Venv `.dev-env/release-venv-0.1.18` (372 MB) KHÔNG dispose được: helper từ chối `outside_allowed_roots` (môi trường chung); giữ nguyên, không đường vòng. Giữ: Owner data, `.venv`/`release-venv`/model, ứng viên audit cũ, evidence, release v0.1.18 công khai, v0.1.17 và cũ.
- Epoch: hop 6/8 (`034`) gắn HEAD `81aac75`; commit tài liệu này không có hop; không rebaseline.
