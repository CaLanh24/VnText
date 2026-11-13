# Release 0.1.19 — ledger

Trạng thái: **ĐÃ PHÁT HÀNH 2026-11-13** — https://github.com/CaLanh24/VnText/releases/tag/v0.1.19 (Latest); tag chú thích `v0.1.19` (`8611b551…`) → nguồn dựng `4c88acc0a16a347074f66f44f42d32142ce1c8fb`; `main` đẩy fast-forward tới `11e4faa`. Brain ACCEPT đúng ứng viên; 5 tài sản đọc lại băm từ bản tải công khai (khớp). **Root đã xác nhận cập nhật in-app công khai 18→19 (apply/restart) PASS; đã dọn cuối.** Bản vá vòng lặp cập nhật trong app (0.1.18 công khai chưa chứa bản sửa). Ứng viên cũ `28f62d3` (và Setup `32bc1924…`, `native019`) đã bị thay thế và dọn; hash của nó giữ ở `assets-019-28f62d3-superseded.json`/`candidate-receipt-28f62d3-superseded.json`.

## Nguồn và ứng viên (ĐÚNG MỘT nguồn dựng)
- Source dựng và epoch: **`4c88acc0a16a347074f66f44f42d32142ce1c8fb`** (commit quyền, hậu duệ của nguồn chuẩn bị `cba2a806fe111fb889267a363decad1d7f96904f`; epoch `epoch-20261113-037-rb-release019`). Snapshot sạch: `RELEASE_RUN/candidate-0.1.19/source`. Mọi gate/backend/hash dưới đây gắn đúng SHA này. Các commit tài liệu sau đó trên `main` không đổi nguồn dựng; tag phải trỏ `4c88acc`.
- Setup: `RELEASE_RUN/candidate-0.1.19/setup-019-4c88acc/ReleaseRoot/VNTextStudio-0.1.19-Setup.exe`, 286,729,728 B, sha256 `3ddebffc1a07ac406d2427b467f6fc8938296a4f7d0eba7386eb3e7f1a352c9f`; payload 7,327 tệp xác minh; `VNText Studio.exe` sha256 `da27e77b870021259a0271e0f36fadb2cc22a2f31af12bc093ab3f3ab1efab97`.
- 5 tài sản tối thiểu (`ReleaseRoot/Updates`; hash đầy đủ ở `TEST_RUN/agent-evidence/release-0.1.19/assets-019.json`):
  - `full-app-update-from-0.1.18-to-0.1.19-4f3db5b8f4599a88.zip` 67,361,881 B, sha256 `4f3db5b8f4599a8803c7c7fbc00fc3d330037c8e797d9e5afade1e8c18ce0727`; feed `full-app-update-from-0.1.18-to-0.1.19-current.json` 2,364,854 B, sha256 `c2adc537e795cce3a41710414438709d026d2ceed95b674a02ce5c46e49219df`.
  - `full-app-update-0.1.19-d5d33bdd0889e9da.zip` (tuyến legacy 0.1.7) 86,938,345 B, sha256 `d5d33bdd0889e9da43e7ad159a3616f82c5437ec5c1a17cc536b1cb6ddf27500`; feed `full-app-update-current.json` 2,550,947 B, sha256 `043d3563e9095221ee24e607f3e74f037eb2ef6b88708e5022592db7b7705ca3`.
  - Setup ở trên. Tuyến 0.1.17 đi chuỗi 17→18 (tài sản công khai có sẵn) rồi 18→19; không thêm ZIP.
- Phụ thuộc Python: khóa băm `requirements/locks/windows-cp312-{runtime,build}.txt` (52 distribution; `tpk_ar` 0.2.4 sdist chính thức) trong `.dev-env/release-venv` được tái dựng đúng khóa (venv tiền-khóa cũ đã kiểm kê và dispose; `old-release-venv-inventory.json`, `release-venv-after.json`: `dependency_profiles.py --check-installed` exit 0, `pip check` exit 0). Tái dùng nguyên, không tải lại.
- Baseline công khai tái dùng (đã xác minh băm, payload giải nén, KHÔNG phải cài Setup): v0.1.18 590,341,910 B (Setup `454ef46f…930a`), v0.1.17 584,299,498 B (`4e56da3e…cf7f`), v0.1.7 515,688,819 B (`82667f53…90f6`) + tài sản công khai 17→18 (zip `3e6a5d48…02f9`, feed `0e64ef01…c0ac`). `baseline-receipts-019.json`.

## Sửa lỗi
- **Vòng lặp “tải → cần Setup”:** khi gói không áp dụng được cho bản đang cài, app dừng ở `SetupRequired`: nút “Mở trang tải”, giữ ghi chú/ngày, không tải lại gói đó khi bấm lặp, kiểm tra lại thủ công/tự động/định kỳ/nhắc hay khởi động lại.
- **Khóa từ chối có kiểu, giới hạn:** offer (version/sha/URL/size) + trạng thái thật của `app/RELEASE.json`, `app/VERSION.txt` và ≤16 tệp baseline lệch (missing/extra/differs; đọc tối đa 512 MiB; token cố định cho tệp không đọc được/quá lớn). Sửa tệp lệch (kể cả không phải exe), đổi bản cài hoặc offer mới → khóa đổi → thử lại tải + xác minh đầy đủ. Không đọc đường dẫn tùy ý/reparse/dữ liệu người dùng; không nới guard baseline/hash/readback; lỗi đọc băm không bao giờ thành READY.
- **Danh mục tiếng Anh** cho lỗi OCR “Kết quả OCR cũ chưa xác nhận được chữ…” (thiếu từ 0.1.18; nay đã có trong bản dựng).
- READY chỉ khi có lease gói đã xác minh; lỗi mạng/hash/cắt cụt là lỗi hành động được; hủy/thử lại; chặn khi CSV chưa lưu.

## Ủy quyền, ngân sách, epoch
- Owner 2026-11-12 (“push lên GitHub rồi release bản sửa …”) + mục lưu trữ đứng 2026-10-24: task `release-0.1.19`, trần đo được 5 GiB (5,368,709,120 B, ghi trước khi cấp: `allocation-plan-0.1.19.json`), guard 48 MiB, shared 11 GiB giữ nguyên; trả về 1 GiB ở dọn cuối.
- Owner 2026-11-13 trả lời trực tiếp “cho phép” cho yêu cầu cụ thể “Cho phép một lần rebaseline cho cba2a80, giữ nguyên scope/ngân sách, để build lại, kiểm nốt rồi push/release và dọn?” (`docs/RELEASE_0.1.19_REBASELINE_PLAN.md`): **một** rebaseline metadata không xóa, id `owner-20261113-cba2a80-019`, đã đăng ký trong `EPOCH_REBASELINE_AUTHORIZATIONS` kèm test (`Epoch019RebaselineGrantTests`), plan (`rebaseline-plan-037.json`, `reasons: []`) rồi apply một lần (`rebaseline-apply-037.json`) → epoch `epoch-20261113-037-rb-release019` @ `4c88acc`. Quyền ĐÃ TIÊU THỤ; chuỗi 8-hop mới tính lại từ epoch này, không có chính sách standing, không rebaseline khác. Các grant trước vẫn tiêu thụ.
- Dung lượng: đỉnh matrix backend (project non-exempt, không tính `.dev-env`) 4,131,330,506 B (< ngưỡng hủy 5,318,377,472 B); lúc bàn giao project 3,229,663,519 B (candidate 2,245,862,012 B gồm baseline 1,779,684,385 B; TEST_RUN 569,726,501 B); shared `.dev-env` 3,308,896,406 B (< 11 GiB).

## Gates (verdict riêng, gắn nguồn `4c88acc`, cây sạch; không dùng lại gate của `28f62d3`)
- Python công khai (`audit_gates --group public`): csv 34, mt 91, patch 37, maintenance 44 — PASS, 0 skip; installed-model/native = SKIP có chủ đích.
- `test_wpf_workflow` **37/37 PASS** (gồm fixture native csv-layout, catalog OCR, XAML) và `test_release_regression_runner` **6/6 PASS** — hai test từng không xanh ở bản trước nay xanh dưới profile 5 GiB; `test_setup_package` 13 PASS (không PYTHONUTF8; 2589 s); `test_release_verify` 7 PASS; `test_full_app_update_publisher` 2 PASS; `test_publish_release_root_guard` PASS; `test_cleanup_work_artifacts` 157 PASS; epoch 017/018/019 (17), resources setup 7, installer order 1, mirror 2, artifact policy 8, cleanup finalize 3, work_paths 7 (1 skip) — PASS. `test_release_gui_shutdown` OK nhưng 1 skipped (GUI shutdown không chạy) — không tính PASS. Log: `gate-modules-4c88acc.log`, `gate-public-4c88acc.json`.
- Updater WPF (build Release 0 cảnh báo): `--updater-setup-only` PASS (UpdaterPresentation; Setup-required không retry & giữ ghi chú; **full-app: reject không re-offer qua kiểm tra thủ công/nền/khởi động lại, sửa tệp lệch không phải exe → thử lại xác minh, tệp khác/extra/metadata/offer mới, lỗi mạng/cắt cụt/tamper, hủy+thử lại, chặn CSV chưa lưu, READY chỉ khi có lease**) và `--full-app-update-only` 9 PASS (`focused-4c88acc-*.json`). Dùng HTTP giả + fixture gói full-app thật, KHÔNG phải nghiệm thu native.
- Build/package: `publish.ps1` (isolated, locked deps, preinstalled) exit 0 @ `4c88acc` (`publish019-4c88acc.log`); payload 7,327 tệp; Full-app Updates 2 gói. Receipt: `candidate-receipt.json`.
- Updater backend trên gói thật (KHÔNG phải UI native/Setup), receipts `updater019-backend-*-4c88acc.json`: **A** public 0.1.18→0.1.19, **B** legacy 0.1.7→0.1.19, **C** 0.1.17→(17→18 công khai)→0.1.19: exit 0, version 0.1.19, đọc lại manifest 0 lệch, canary `data/owner-preserve` nguyên vẹn, health PASS. Âm tính (mã updater đã đổi nên không tái dùng bằng chứng 0.1.18): **N1** zip bị sửa → exit 5; **N2** tệp baseline lệch → exit 5; **N3** gián đoạn sau thay thế đầu → exit 7 rồi `--recover-full-app-update` khôi phục đúng baseline; **N4** health lỗi → rollback; cả bốn: cây baseline không đổi, canary nguyên, không journal treo. Fixture từng kịch bản đã dispose qua helper (0 refused).
- NOT_PROVEN: Setup cài mới/nâng cấp/gỡ của ứng viên MỚI trên máy thật, Setup-required native của bản dựng, cập nhật công khai trong app sau phát hành, mọi DPI/giao diện, âm thanh, game lớn, chất lượng dịch toàn game. (Native Root trên ứng viên cũ `28f62d3`: cài mới + app PASS chức năng — không chuyển sang ứng viên mới.)

## Giới hạn phải ghi trong ghi chú phát hành
Dịch offline chỉ là bản nháp thô, cần người rà soát; engine ngoài Ren'Py/Unity chưa được chứng minh; chất lượng dịch toàn game không được công bố.

## Ghi chú phát hành (nháp, tiếng Việt)
**VNText Studio 0.1.19** — bản vá cập nhật trong app.
- Sửa vòng lặp “Tải về → cần cài lại”: khi gói cập nhật không khớp bản đang cài, app dừng ở bước cần Setup với nút “Mở trang tải”, giữ ghi chú, không tải lại cùng gói khi bấm lặp, kiểm tra lại hoặc mở lại app.
- Nếu bạn sửa lại tệp lệch hoặc cài lại, app tự thử lại và xác minh gói bình thường.
- Bổ sung bản dịch tiếng Anh cho một thông báo lỗi OCR.
- Cập nhật trong app từ 0.1.18 (và từ 0.1.17, 0.1.7). Dữ liệu người dùng được giữ nguyên.
- Lưu ý: bản dịch offline chỉ là bản nháp thô, cần xem lại; chưa hỗ trợ mọi engine game.

## Checklist native hữu hạn cho ứng viên MỚI (Root; DEV không mở UI)
1. Setup `VNTextStudio-0.1.19-Setup.exe` (sha256 `3ddebffc…2c9f`) cài mới vào thư mục cô lập, không shortcut: điều khoản, tài nguyên, hoàn tất, mở app; About = 0.1.19; EXE `da27e77b…ab97`.
2. Nâng cấp bằng Setup chồng lên bản công khai 0.1.18 với canary trong `data/` — dữ liệu còn nguyên.
3. Setup-required native: bản cài khác baseline (sao chép payload 0.1.18 ở `release-baselines/v0.1.18/installed`, đổi một tệp `app/`, KHÔNG dùng `Desktop/vntextapp`) + HTTP/ nguồn cục bộ cho gói: lời mời → tải → “Mở trang tải” (VI/EN); bấm lặp / Kiểm tra lại / đóng-mở lại app KHÔNG tải thêm; sửa tệp lệch → kiểm tra lại cho phép tải xác minh lại. Fixture: `--presentation-fixture --presentation-state setup-required` và `--native-update-ui` (env `VNTEXT_WPF_BASELINE_EXE`/`VNTEXT_WPF_CANDIDATE_EXE` như `DEV_RUN/scratch/run_focused.py`; scope build `TEST_RUN/updater-loop-check` còn).
4. Sau publish: app 0.1.18 THẬT nhận lời mời 0.1.19 → Cập nhật ngay → Khởi động lại → thành công, canary nguyên.
Không dùng game thật; canary do bước kiểm tạo; không động vào dữ liệu Owner.

## Dọn cuối (sau Root ACCEPT + publish)
Dispose qua helper (target chính xác, không theo junction): `RELEASE_RUN/candidate-0.1.19` (source worktree → `git worktree prune`, `setup-019-4c88acc`, baselines ≈1.78 GB, ResourceDump, mọi thư mục native Root tạo), `TEST_RUN/updater-loop-check`; giữ `release-venv` (consumer: publish lại) đến sau publish; giữ receipt/hash trong `TEST_RUN/agent-evidence/release-0.1.19/` (compact); trả project về ≤ 1 GiB. Đã dọn trong lượt này: `candidate-0.1.19/native019` và `setup-019-28f62d3` (consumer đóng, hash đã lưu), mọi fixture backend.

## Native Root — tiến độ ứng viên MỚI `4c88acc` (cập nhật 2026-11-13)
- Root báo (chưa kiểm bởi DEV trừ hash): Setup mới `3ddebffc…` cài tương tác vào `native-final` (SDK/tài nguyên tải thật xong, EXE `da27e77b…`, app mở), **gỡ cài đặt 0.1.19 hoàn tất** (UI tiếng Anh; installer xóa toàn bộ thư mục test, không dữ liệu Owner; `native-final` rỗng sau khi đóng). Ảnh: `native-final-setup-state/ready/uninstall.png`. Root cũng tải Setup công khai 0.1.18 (`454ef46f…` — DEV khớp hash) và cài `native-upgrade` (EXE `9d0d6f29…`, canary `data/native-owner-canary.txt`), đã đóng. Receipts/manifest dọn: `native-root-receipts-and-cleanup-manifest.json`, `native-upgrade-copy-receipt.json`.
- DEV chuẩn bị (không mở UI, không dựng lại): bản sao byte-giống `native-upgrade-copy` (10,556 tệp, 0 hardlink/reparse) để Setup 18→19; giữ nguyên `native-upgrade` cho cập nhật in-app công khai; fixture `--native-update-ui` mã MỚI + launcher có log bền (`native-update-ui/README-ROOT.txt`, `harness-binding.json`). Đã đăng ký các root native; đã dispose baseline giải nén 0.1.17 và 0.1.7 (không còn consumer backend). Project 4,308,755,095 B < 5 GiB.
- Còn NOT_PROVEN: Setup 18→19 native, Setup-required native (mã mới), cập nhật in-app công khai 18→19.

## Phát hành (2026-11-13)
- Root receipt `root-prepublication-accept.json`: Setup mới + SDK thật + app PASS; gỡ cài đặt PASS; Setup 18→19 trên bản sao byte-giống bản 0.1.18 thật PASS (canary nguyên, 3228 tệp dữ liệu không mất); fixture Setup-required mã mới (TEST_ONLY, HTTP giả) PASS.
- Đã dọn trước publish: `native-upgrade-copy`, baseline 0.1.18 giải nén, public hop. Giữ: `native-upgrade` (0.1.18 thật + canary) và Setup chính thức 0.1.18 cho Root cập nhật in-app công khai.
- Readback công khai: `public-readback-receipt.json` (5/5 khớp, không tệp thừa); tệp tải đã dispose.

## Nghiệm thu sau phát hành và dọn cuối (2026-11-13)
- Root (`root-public-update-accept.json`, `native-public-update.log`, ảnh `native-public-*.png`): bản 0.1.18 thật (Setup công khai, `native-upgrade`) nhận lời mời 0.1.19 từ GitHub (ghi chú/ngày), tải → Khởi động lại bật, app mới thay thế, hộp thoại “Cập nhật thành công 0.1.19” (txn `txn-780a5e75…`, health true, EXE `da27e77b…`), About mới nhất 0.1.19, kiểm tra thủ công không còn lời mời; 3,228 tệp dữ liệu còn đủ, canary nguyên, chỉ settings/log thay đổi. PASS chức năng.
- Giới hạn: không tuyên bố toàn game, mọi DPI/giao diện; ma trận restart/không-tải-lại cho Setup-required được tự động hóa (không lặp native đầy đủ); Setup-required native tiếng Anh chưa chạy riêng.
- Dọn cuối (`final-cleanup-receipt.json`): dispose `candidate-0.1.19` (gồm `native-upgrade`, Setup 0.1.18 tải về, baseline, worktree nguồn đã prune) và `TEST_RUN/updater-loop-check` qua helper, 0 từ chối; project non-exempt 2,757,927,134 → 955,090,123 B (< 1 GiB mặc định), profile 5 GiB đã đóng, shared `.dev-env` 3,308,896,406 B không đổi. Không động vào dữ liệu/ứng dụng Owner.
