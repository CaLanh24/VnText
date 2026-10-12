# Thông báo cập nhật trong app — yêu cầu trước phát hành

Owner đã chọn version candidate **0.1.5** ngày2026-10-11. Chỉ đồng bộ VERSION và các version owner khi bắt đầu candidate sau checkpoint UI/updater; source hiện0.1.4, không đổi version để relabel evidence cũ.

## Ủy quyền điều phối DEV không đồng bộ — 2026-10-12

Owner ủy quyền Brain review, approve và điều phối Coordinator tiếp tục các bước DEV đã nằm trong scope UI/updater này khi Owner vắng mặt, gồm implementation/remediation bounded, validation và cleanup artifact có ownership đã chứng minh. Coordinator vẫn là source writer duy nhất; Brain không được coi quyền review là quyền sửa source hoặc mở scope mới. Riêng task này, Owner cho phép một lần refresh capability Computer Use chỉ cho cửa sổ VNText native và các kiểm tra UI bounded tiếp theo trên cửa sổ đó; quyền này không mở rộng sang app/cửa sổ khác hoặc thay đổi hệ điều hành. Brain access không tự cấp các quyền khác như license/admin, cài/tải dependency, game/model/Setup, push/upload/phát hành, thay đổi dịch vụ ngoài repo hoặc thay quyết định sản phẩm. Khi một prerequisite/quyền riêng chưa có, tiếp tục phần độc lập và giữ đúng trạng thái chưa xác minh.

## Mục tiêu và nguồn thiết kế

Owner chốt bổ sung ngày2026-10-11: **giữ nền sáng/xanh VNText, bố cục popup giống Cockpit**. Popup là modal có nền app dim nhẹ, feather/header/X, version mới nổi bật, mục Có gì mới cuộn riêng, vùng status/progress thật và footer nhạt với một hành động chính xanh. Dùng tokens/styles hiện có, không đổi theme/framework hoặc thêm runtime/feature. Giữ keyboard/focus/Escape, owner, busy/dirty/cancel/skip và validator. Một batch capture các trạng thái và Settings, tối đa một correction/confirmation; controlled success rendering không thay acceptance receipt/apply/restart thật.

Clarification của Brain trong quyền điều phối acceptance hiện tại (2026-10-11, thread01a0ffa3): “không new runtime” cấm provisioning/tải/cài mới; cho phép đúng một fixture terminal registered TEST_RUN dùng bản sao tối thiểu CPython/cache có sẵn và WPF source thực để kiểm local installed-tree. Bổ sung tối đa150MiB, tổng non-exempt root tối đa1GiB; không model/game/Setup/clone payload, không overlap run. Kiểm cap/prerequisite trước mutation; persist health exe, worker ready/exit, restart, receipt và negative rollback/recovery trước disposal. Đây là clarification của Brain, không phải một lời Owner mới; không thay acceptance Release/public GitHub.

Implementation đang tiếp tục trên base `583de06` cùng source diff của task: discovery metadata tách khỏi tải, retry và ready lease, receipt `txn-<Guid>` kiểm path/hash/version/pending journal, settings lưu atomic và giữ file hỏng. Dịch/Patch một cột, logs thu gọn, settings ba tab và model status qua Python resolver hiện có. Focused `ui-popup-final-focused` 8/8; affected `ui-popup-final-affected` 38/38, child/wrapper0, không skip/warning, cleanup PASS/TEST_RUN absent. Raw command/output/exit/report ở DEV_RUN cùng tên; evidence thuộc base + diff thực chạy, không relabel exact-HEAD. Lượt `ui-popup-corrections-focused` FAIL/1 vì ba assertion/caller test vẫn giả định manual discovery tự tải; đã sửa fixture caller sang explicit download, giữ assertion candidate lease/disposal. Native UI/local transaction receipt acceptance của batch này còn pending; không phải checkpoint PASS hoặc candidate Release acceptance.

Owner yêu cầu ngày 2026-10-11: app có bảng thông báo khi có cập nhật mới, tham khảo ảnh Cockpit Tools đã cung cấp. Ưu tiên hoàn thiện UI/updater trong bản đang chuẩn bị, rồi phát hành trước khi thực hiện `TRANSLATION_QUALITY_PLAN.md`.

Ảnh tham khảo cho thấy các trạng thái: có bản mới với release notes, đang tải có tiến trình, sẵn sàng khởi động lại và cập nhật thành công. Đây là nguồn tham khảo UX, không phải bằng chứng updater VNText đã hoạt động. Không phụ thuộc đường dẫn ảnh/máy riêng để triển khai từ public clone.

Surface mode: Operate. Giữ WPF, font, màu, feather branding và component language của VNText; không sao chép dashboard hoặc dark theme của Cockpit. Popup gọn giữa cửa sổ app, có tiêu đề, nội dung và hàng hành động; notes dài cuộn trong vùng giới hạn, không làm popup tràn màn hình. Theo yêu cầu bổ sung của Owner, bỏ toàn bộ khối version/status/nút updater ở cuối sidebar; chuyển kiểm tra cập nhật thủ công vào Cài đặt → Giới thiệu.

## Tham khảo app trực tiếp và bổ sung của Owner

Brain đã mở Cockpit Tools bằng Computer Use ngày 2026-10-11: quan sát sidebar và cả bốn tab Chung, Dịch vụ mạng, Quản lý dữ liệu, Giới thiệu. Bản đang chạy `1.3.66`; thao tác Kiểm tra cập nhật trả “Đã là bản mới nhất v1.3.66”. Không tải/cài update hoặc lưu thay đổi settings. Popup newer/download/restart không xuất hiện trong lượt này vì không có bản mới; các trạng thái đó vẫn dựa ảnh Owner, không ghi là đã kiểm trực tiếp.

Bổ sung từ report Brain cùng ngày, ở lượt quan sát sau: manual check trong Giới thiệu của Cockpit `1.3.66` đã offer `1.3.67`. Popup thật có tiêu đề/X, version mới và hiện tại, notes cuộn riêng; sau scroll550, tiêu đề/version và footer Hủy/Bỏ qua phiên bản này/Cập nhật ngay vẫn cố định. Brain báo không bấm tải/cài/bỏ qua/đóng popup. Đây là evidence presentation được Brain báo cáo, không phải Coordinator trực tiếp quan sát hoặc bằng chứng download/restart/skip persistence. Giữ lượt current trước đó với provenance riêng. VNText dùng bố cục header/footer cố định và notes cuộn giới hạn, phong cách sáng/xanh/feather; không thêm updater vào sidebar.

Sidebar Cockpit có nhóm điều hướng cuối gồm Nhật ký/Cài đặt, không có khối chi tiết updater. Tab Giới thiệu đặt tên/icon app, version, Kiểm tra cập nhật và Ghi chú phát hành cạnh nhau. Tab Chung có tỷ lệ UI, nhớ cửa sổ, giảm chuyển động, tùy chọn update nền và nhắc update. Tab Dữ liệu có quản lý sao lưu/import/export; tab mạng có API/proxy riêng của sản phẩm đó. Chỉ ghi thông tin UI liên quan, không lưu tài khoản/token/cấu hình riêng từ app tham khảo.

Owner yêu cầu thêm: popup có thao tác bỏ qua/tải, sidebar cuối gọn, check update trong settings, và settings có tùy chỉnh thực tế. Source VNText ở checkpoint `c889bc5`: trang settings chủ yếu là lời hướng dẫn/runtime; `AppSettingsStore` có bốn lựa chọn workflow, chưa có nhóm tùy chỉnh giao diện/update như đề xuất dưới đây.

## Sidebar và Cài đặt

## Phạm vi UI được Owner duyệt triển khai — 2026-10-11

Owner đã yêu cầu chạy task UI/updater, nghiệm thu rồi tạm đóng đợt phát triển để chuẩn bị phát hành. Hoãn translation-quality/training theo plan riêng. Phạm vi settings đề xuất bên dưới được đưa vào task này: Chung/Dữ liệu/Giới thiệu; không bổ sung các tính năng đã ghi deferred.

Giữ phong cách nền sáng, xanh và feather branding; tham khảo thứ bậc và cách nhóm thông tin của Cockpit, không thay framework/theme. Bắt đầu bằng một màn hình Lấy text làm mẫu; Brain review trước khi áp dụng sang Dịch local, Sửa CSV, Tạo patch và Cài đặt. Không chạy game E2E cho thay đổi UI.

- Chuẩn hóa typography trong design tokens/styles: nội dung khoảng14, mô tả12–13, tiêu đề nhóm16–18; hạn chế nhãn9–11 nhỏ/mờ. Đây là hướng tương đối, cần kiểm DPI/window và bảng dữ liệu thực, không bulk-replace FontSize mù.
- Chuẩn hóa spacing, chiều cao input, icon, corner radii và thứ bậc nút chính/phụ; dùng component/style có sẵn, một hành động chính rõ cho mỗi bước. Không dùng màu nhấn tùy tiện hoặc hạ khả năng đọc của disabled/error state.
- Giảm mô tả lặp, badge và chrome ít thông tin; phần giải thích dài và tùy chọn ít dùng có thể mở rộng trong Trợ giúp/Nâng cao. Không giấu cảnh báo dữ liệu, điều kiện Patch, partial/unsupported hoặc lựa chọn workflow hiện có.
- Nhật ký không chiếm cột lớn khi chưa hoạt động; ưu tiên tiến độ, số xử lý, số cần sửa và bước tiếp theo. Chi tiết mở được, lỗi không bị mất và binding/state vẫn đúng. Giữ CSV virtualization, keyboard editing, dirty/save guards và trạng thái async.
- Màn hình mẫu cần actual WPF screenshot/interaction trên DEV có provenance với empty/ready/busy/error và kích thước cửa sổ hỗ trợ. Sau review, tái sử dụng cùng ngôn ngữ thiết kế cho các trang, tránh thiết kế độc lập từng trang. Có thể checkpoint từng phần với tối đa một executable DEV, không tạo nhiều payload/game copy.

Task implementation được commit source/test/docs đúng scope sau validation theo AGENTS. Version/publication là bước Release riêng, Owner chọn version trước khi build candidate; không suy artifact source cũ thành Release PASS của source mới.

## Chi tiết Sidebar và Cài đặt

**Yêu cầu đã chốt:** giữ điều hướng workflow và project, đưa Cài đặt thành mục gọn ở cuối sidebar; bỏ version/status/check/apply updater khỏi sidebar. Không tạo thêm trang Nhật ký hoặc panel trạng thái chỉ để giống Cockpit. Update mới được thao tác trên popup; kiểm tra thủ công ở Giới thiệu, không phụ thuộc sidebar.

**Scope Owner đã duyệt, chưa là implementation đã nghiệm thu:** chia settings ba tab, mỗi dòng gồm tên ngắn, một câu giải thích và điều khiển thật; không có toggle trang trí hoặc nút không có tác dụng.

- **Chung:** tỷ lệ UI với các mức giới hạn phù hợp cửa sổ hỗ trợ; nhớ vị trí/kích thước cửa sổ, có clamp khi đổi màn hình/DPI; bật/tắt tự kiểm tra cập nhật khi khởi động và bật/tắt nhắc popup. Manual check luôn hoạt động, không bị skipped-version hoặc toggle auto vô hiệu hóa. Không mặc định tải hoặc apply nền.
- **Dữ liệu:** hiển thị đường dẫn thực và nút mở thư mục dữ liệu/model bằng path resolver hiện có; báo model/worker có sẵn hay thiếu bằng trạng thái thực. Không tự đổi root, tải model, xóa model/CSV/game/backups hoặc mở một cleanup engine mới. Các lựa chọn extract/overwrite/human-review hiện có vẫn giữ ở bước workflow phù hợp, không nhân bản setting mâu thuẫn.
- **Giới thiệu:** feather icon, tên app, version executable thực, nút Kiểm tra cập nhật, Ghi chú phát hành và liên kết repository/phản hồi đã xác minh. Feedback checking/current/error/Setup-required và offer được hiển thị tại đây hoặc popup; copy phổ thông, không debug dump.

Chưa đưa vào đợt này: dark/system theme hoàn chỉnh, thêm ngôn ngữ UI, tray/autostart, backup theo lịch, cloud sync/WebDAV, API server, proxy hoặc lựa chọn model mới. Giảm chuyển động chỉ đề xuất thêm nếu implementation có animation cần kiểm soát; không tạo setting không có hiệu lực. Các phần này cần task riêng nếu Owner chọn.

Settings mới phải lưu/khôi phục thực, giữ giá trị workflow hiện có khi migration; lỗi đọc/ghi phải báo rõ và không âm thầm ghi đè file hỏng. Không hạ quy tắc dữ liệu/artifact hoặc bỏ busy/unsaved guards vì thêm setting.

## Luồng UX đề xuất cho implementation

Các điểm bên dưới là mặc định thiết kế để thực hiện yêu cầu popup; không phải chức năng đã có hoặc acceptance đã PASS.

1. **Kiểm tra:** dùng nguồn stable GitHub đã cấu hình. Kiểm tra nền không khóa UI. Chỉ offer phiên bản mới hơn đã qua metadata/compatibility; không hiện popup có bản mới từ tag giả hoặc package lỗi. Khi app đang extract/translate/patch hoặc có chỉnh sửa chưa lưu, hoãn popup tự mở và không restart làm mất công việc.
2. **Có bản mới:** tiêu đề “Có bản cập nhật mới”, phiên bản hiện tại/mới và “Có gì mới” bằng câu chữ phổ thông từ Release. Nút chính “Cập nhật”, nút phụ “Để sau”, tùy chọn “Bỏ qua phiên bản này” và đóng bằng X. Không hiện SHA, provenance, raw paths hoặc kết quả kiểm chứng nội bộ trong nội dung người dùng.
3. **Để sau/bỏ qua:** đóng không cài; không bật lại cùng offer liên tục trong phiên. Bỏ qua được lưu cho đúng version, version mới hơn vẫn thông báo. Người dùng có thể mở lại bằng kiểm tra thủ công, kể cả version đã bỏ qua.
4. **Tải và kiểm tra:** chỉ bắt đầu tải khi người dùng bấm “Cập nhật”; hiển thị tiến trình từ dữ liệu thật. Chưa biết tổng byte thì dùng trạng thái không xác định, không dựng phần trăm giả. Không chạy download/install trùng khi bấm nhiều lần. Đóng popup không được âm thầm apply hoặc làm hỏng transaction; định nghĩa rõ cancel/background theo khả năng service hiện có.
5. **Sẵn sàng:** chỉ báo “Sẵn sàng cập nhật” sau xác minh package đạt. Nút “Khởi động lại để cập nhật” và “Để sau”. Không tự đóng app/apply khi người dùng chưa chọn; kiểm lại busy/unsaved state trước restart, dùng flow lưu/hủy hiện có.
6. **Sau khởi động lại:** chỉ báo “Cập nhật thành công” khi version thực và transaction/health receipt xác nhận đã apply thành công. Hiện version mới và notes, nút “Đã hiểu”; chỉ hiện một lần cho transaction thành công. Rollback/interrupted update không được báo thành công.
7. **Không có bản mới hoặc có lỗi:** kiểm tra tự động không bật modal “đã mới nhất”/lỗi lặp lại; manual check trong Cài đặt → Giới thiệu có feedback ngắn và hành động thử lại. Phân biệt offline/timeout/rate limit, metadata/package lỗi và trường hợp cần Setup mới. Lỗi có đường hồi phục, không hạ integrity gate để vượt lỗi.

## Scope và boundaries

Owner liên quan: `MainWindow.xaml`, WPF view/viewmodel popup, settings và `MainViewModel` updater; `Services/WpfUpdateService.cs`, `FullAppUpdateService.cs`, `AppSettingsStore.cs`, window lifecycle/receipt owners khi cần cùng tests tương ứng. Coordinator phải xác minh caller/contract hiện có trước sửa; tái sử dụng updater, rollback, lease và settings, không tạo updater thứ hai. Giữ design tokens và control styles của app.

Không thay translation/model/worker protocol/game semantics, installer/uninstaller, trust hosts, hash/baseline/path allowlists hoặc quyền hệ thống để làm popup. Release notes là nội dung bên ngoài: render an toàn với độ dài giới hạn, không chạy HTML/script hay command từ notes. Thiếu notes phải có fallback ngắn, không làm mất chức năng update.

Tách discovery metadata/notes khỏi tải package nếu source hiện gộp cả hai, nhưng giữ validation và cleanup semantics. Đây là việc cần kiểm premise source, không phải khẳng định implementation hiện tại đã tách.

Không tự chọn version phát hành hoặc tạo release chỉ từ tài liệu này. Quyền tải/cài mới, dữ liệu user và external publication vẫn theo Owner/AGENTS. Không cần game copy cho task này.

## Bằng chứng nghiệm thu

### Checkpoint native transaction — 2026-10-12

Product UI source `3c466c9`, fixture run source clean `06180d522ff2dbc15165303c8ac811a58f28098c` (docs-only clarification after UI). Bounded bright/green Cockpit visual packet và focused24/24, affected38/38, clean DEV build/semantic smoke0 giữ provenance riêng, không lặp để relabel SHA. Native production local apply/restart/success receipt+ack-once được Coordinator trực tiếp quan sát trong phase thành công của `ui-local-native4`; whole wrapper4 vẫn FAIL vì fixture reset sidecar sai ở phase sau. Worker-health rollback được chứng minh tại phase đúng của native5 (whole wrapper5 FAIL do helper recovery hash sai). Native6 corrected baseline-copy updater phục hồi gián đoạn: updater7, recovery health passed, baseline hash/journal/GUI/worker verified, child/wrapper0 và cleanup PASS. Literal worker-ready stdout/exit được giữ riêng tại health-evidence fixture; không relabel executable hashes giữa các run.

Fixture là version override test-only0.1.3→source0.1.4, existing system.NET8/minimal CPython3.12.14, dependency cache thật; không dùng published baseline provenance hoặc model inference. Single-file analyzer bị skip vì cache thiếu ILLink.Tasks, bundling thật vẫn chạy; không là Release gate. Canary data/model chỉ chứng minh bytes tạo riêng được bảo toàn. Các lỗi prefix ZIP, empty site-packages, stale sidecar và isolated-updater baseline mismatch được sửa trong helper; validator/product source giữ nguyên. Tất cả run lỗi/raw/exit và cleanup disposition được giữ; TEST_RUN terminal absent và whole-project quota đạt.

The earlier native transaction checkpoint above does not establish all UI acceptance. Its remaining status is consolidated in the Brain review below; retain its per-run outcomes and failures as historical evidence. Stable GitHub acceptance remains separate.

Brain đã review trực tiếp ngày2026-10-11 và chốt **ĐẠT checkpoint Lấy text**, bounded scope tại product source `8ef640d`, receipt docs `583de06`. Không phải toàn UI/updater hay Release PASS. Native click/scroll/log có provenance riêng; busy dùng controlled seam; final guard binding qua actual command/render probe. Không lặp gate để relabel SHA. Coordinator tiếp tục các trang/settings/popup trước bước candidate0.1.5.

### Brain review — settings persistence and local offer, 2026-10-12

Brain directly reviewed the three-session result and canonical cleanup report. The test harness was built from clean source SHA `d03adcc20ef20507b209ff93b618d09161e5f875`; harness SHA256 `bc0709ab7bb442ed2ea766de32910f22499ddfa4eec1dce0180d6c3ca2e5f252`. A later docs-only checkpoint is commit `97b6bd1a8aead3856d4f50b4c18d322317e319e3`; do not relabel the run to that SHA.

Actual WPF interaction proved settings saved and persisted across relaunch: scale 110%, RememberWindow off, AutoCheckUpdates on, NotifyUpdates off; About showed a newer result without opening a modal. Turning NotifyUpdates on and relaunching showed the offer automatically. Manual and automatic offers were generated fixture version `1.0.1` against app `0.1.4`, marked as non-public fixture notes; no download/apply/restart occurred. Three harness children and wrapper exited 0. Wrapper outcome/cleanup PASS, 0 unknown/locked/errors, TEST_RUN absent; inventory was `877,854,896→861,448,317` non-exempt bytes under 1GiB, `.dev-env` `3,046,953,586` bytes under 3GiB. Commands, stdout/stderr, exit, session state and cleanup report are in `DEV_RUN/ui-settings-native3.*` and `DEV_RUN/ui-updater-native-receipt.md`.

**Brain outcome: PASS for this bounded settings-persistence/local-mock-offer checkpoint only.** This is not whole-UI completion, candidate acceptance or Release verification. The failed `ui-settings-native2` run remains a historical FAIL. Public stable GitHub update remains **NOT VERIFIED**.

Remaining acceptance checklist for any broader UI/updater completion:

1. Native offer modal keyboard/focus behavior (Tab order, Escape/close behavior, and focus return) with a correctly identified modal or directly recorded keyboard interaction; no guessed window targeting.
2. Data/model folder actions on a test-owned isolated path, verifying the opened target. The prior ShellExecute attempt returned sandbox Access Denied, so this remains environment-limited/UNKNOWN.
3. Broader supported DPI/window geometry and workflow visibility checks; the 110% saved preference alone does not cover them.
4. Stable GitHub offer/apply/restart on an installed real baseline using the actual stable asset. This remains **NOT VERIFIED** and requires its separate public-asset acceptance; mock fixture evidence cannot satisfy it.

### UI follow-up — geometry and blocked native controls, 2026-10-12

Coordinator inspected the existing DEV WPF executable (`078b09c4…bfcf7`, build identity source `3c466c9…a29a3`) in the registered local TEST_RUN scope at clean source SHA `154d5719e90f298e7e10db4e5f83401128908b32`. Settings plus all four workflow pages were visibly checked at content scales 100%, 110% and 120%; Settings showed the selected scale was saved, and the Extract page scrolled at 120%. This is content-scale/UI geometry evidence at the configured minimum window size, not system-DPI coverage. The 5,000-row CSV fixture was generated with SHA256 `b7e15f53…c974ef`, but the file picker could not be controlled through the available helper, so CSV row virtualization remains UNKNOWN.

Settings displayed the exact isolated data/model roots under TEST_RUN and “Thiếu file model OPUS-MT INT8.” The Translate page’s “Sẵn sàng” text binds to the shared `_statusText` default in `MainViewModel.cs`, not model readiness; it is not contradictory evidence about the model. Both Settings folder buttons showed the exact fixture path in an `Access is denied` process-start error; no new Explorer window opened and no unrelated Explorer was touched.

The generated local mock offer showed fixture `1.0.1` against app `0.1.4`, focus on its Close button and “chưa tải gói.” No download/apply/restart or public GitHub request occurred. Modal UIA click, Escape, and owner-window close did not dismiss the offer; the helper exposes no separate modal target. The native keyboard/focus acceptance remains UNKNOWN.

The interactive helper was still live at final observation (scope `canonical-run-ee781c7766e840fabd54710aec44766b`, run `run-1060e1f25e5443f0b7a6df3aaf400efa`). Its session log identifies mock fixture PID `17000`; the UI helper reports window `26549790`. Brain's read-only host lookup reports that PID, exact TEST_RUN executable path and start time `2026-10-12T23:49:16.7682961+09:00`, confirming the fixture process remains live. Coordinator-local `Get-Process -Id 17000` could not see it and `tasklist /FI "PID eq 17000"` returned “The user name or password is incorrect”; this is execution-context visibility, not evidence of exit. The normal UI close request also left the owner window open, and this execution context has no process object for a process-level `CloseMainWindow`. No force termination or cleanup was performed. Wrapper exit, terminal cleanup and whole-project cleanup are therefore not PASS; TEST_RUN remains live. Detailed command/stage outputs and observed limits are in ignored `DEV_RUN/ui-remaining-live-evidence.md` and the live scope logs. Stable GitHub acceptance remains **NOT VERIFIED**.

## Corrected terminal disposition and latest Owner visual direction — 2026-10-13

The preceding live-state paragraph reflects an earlier observation and is superseded by the terminal evidence below. The run's final disposition is **CANCELLED**, not PASS: wrapper session `79993` returned outer exit code 1 after Coordinator sent Ctrl+C; persisted wrapper JSON still says `RUNNING`, and no `session_complete` event or reliable child exit code was recorded. The actual harness child was PID 17000; a read-only host check at `2026-10-13T00:02:57+09:00` found no PID 17000 and no VNText/Workflow.Tests process. Raw stdout/stderr were preserved at `DEV_RUN/ui-remaining-native.stdout.log` and `.stderr.log`; stdout ends at `session_started` and stderr is empty. The scoped cleanup command returned 0 with outcome `CANCELLED`, cleanup `PASS`, complete inventory, 6 registered disposable entries removed, 16,888,152 bytes freed and no unknown/locked/errors. The separately authorized terminal-root purge returned 0/PASS and `TEST_RUN` is absent. Cleanup PASS describes disposal only; native offer UI acceptance is incomplete/UNKNOWN.

Owner's latest direction, based on the current Cockpit Tools screen, is to carry its bright visual language through the VNText WPF UI: pale blue/cyan ambience, blue headings and actions, white rounded cards with restrained borders/shadows, and clear fixed left navigation. Preserve VNText page structure where it expresses workflow semantics. The live Cockpit screen was observed in Computer Use at version 1.3.68 offer over 1.3.67; its main dashboard showed a light theme with blue accents, pale cyan/blue canvas, rounded summary cards and the classic left sidebar. No Cockpit settings were changed and no update was applied.

The current source styling change is limited to WPF design resources, page accents and navigation foreground. It does not alter worker/update behavior. Stable GitHub update remains **NOT VERIFIED**.

## Cockpit bright visual implementation and DEV evidence — 2026-10-13

Source commit: `4cac13cde5b01a962e553dc2083e1822f52efc14` on `main`. Working tree was clean for build. Changes: a pale blue-to-cyan workspace canvas; brighter Cockpit blue actions, headings, focus rings and active navigation; blue-tinted field/panel surfaces; restrained cool borders; and a slightly larger brand mark with roomier sidebar rows. Green remains for actual ready/success states. Workflow routes, bindings, worker protocol and updater behavior are unchanged.

Direct Computer Use observation: the Cockpit reference was open in light theme with its left navigation and blue heading/actions, cyan-blue canvas and rounded white dashboard cards. The final DEV WPF window was then activated and captured at 1428x914: title and sidebar selection were blue, page cards white, background cool-tinted, and Local mode/status remained green. The window used the repository DEV launcher environment (`VNTEXT_DATA_ROOT` and `VNTEXT_LOCALAPPDATA` under `DEV_RUN/bootstrap-build`), with `VNTEXT_CT2_NO_DOWNLOAD=1`; no game was selected and no workflow action was invoked. The captured screenshot was displayed through Computer Use but not saved as a standalone file.

Focused validation before commit, on the source worktree whose final source diff was committed above:

- `.\.dev-env\.venv\Scripts\python.exe tests\tools\run_with_cleanup.py -- .\.dev-env\.venv\Scripts\python.exe -B tests\unit\test_wpf_workflow.py -v` — final attempt exit `0`; 8 tests, 0 failures/errors/skips/warnings; child exit `0`; cleanup `PASS`; `TEST_RUN` absent. Output/exit: `DEV_RUN/ui-cockpit-wpf-final.stdout.log`, `.stderr.log`, `.exit.txt`.
- `.\.dev-env\.venv\Scripts\python.exe tests\tools\run_with_cleanup.py -- .\.dev-env\.venv\Scripts\python.exe -B tests\unit\test_ui_progress.py -v` with `TEMP`, `TMP`, `TMPDIR` set to `.dev-env/cache/ui-progress-temp` — exit `0`; 4 tests, 0 failures/errors/skips/warnings; cleanup `PASS`; `TEST_RUN` absent. Its earlier unredirected-temp attempt exited `1` on `PermissionError: [WinError 5]` while Python removed a temporary directory under the sandbox-provided `%TEMP%`; that attempt's cleanup also passed. Both receipts are retained separately under `DEV_RUN/ui-cockpit-progress*`.

Clean-source DEV build and worker smoke:

- Preflight with repo-local SDK `10.0.401` returned exit `1` because that SDK root lacked SDK 8, `Microsoft.WindowsDesktop.App.Ref 8`, and WPF runtime 8. The already-installed system SDK/runtime was then used; `release/dev_bootstrap.py --action check --gate smoke --dotnet "C:\Program Files\dotnet\dotnet.exe" --model .\.dev-env\cache\models\opus-mt-en-vi-int8` returned `0`, finding SDK `8.0.424`, WindowsDesktop reference pack/runtime `8.0.30`, Python `3.12.14`, all required Python packages, and local model files. No tool or model was installed/downloaded in this step. Model file hashes identify current bytes only; model revision/license provenance remains `UNKNOWN`.
- `.\.dev-env\.venv\Scripts\python.exe -B release\dev_bootstrap.py --action smoke --dotnet "C:\Program Files\dotnet\dotnet.exe" --model .\.dev-env\cache\models\opus-mt-en-vi-int8` — exact source SHA above; exit `0`; build succeeded with 0 warnings/errors; executable `DEV_RUN/bootstrap-build/VNText.Studio.App.exe`, SHA-256 `b2ec6e01c42557f2eba9dbd30b2bbcbe2356fd03bc38dd4e8f1ce59badbc7567`. Smoke JSON: `ok=true`, exit `0`, `failed_step=null`, `cleanup_error=null`; extract, translate and patch returned `complete.ok=true`, cancel/crash returned expected negative completion; no skipped smoke steps. Full command, build stdout/stderr and raw worker events/summary are in `DEV_RUN/ui-cockpit-build-smoke.stdout.log`, `.stderr.log`, `.exit.txt` and `DEV_RUN/bootstrap-build/smoke.json`.
- Scope cleanup after each focused gate was `PASS`; `TEST_RUN` is absent. Build preflight/after inventory was complete and below repository limits (latest after: non-exempt `862,439,021` bytes / `1,073,741,824`; `.dev-env` `3,046,955,974` / `3,221,225,472`).

This is a bounded DEV visual/build/smoke result, not broad DPI acceptance, installed-app acceptance, candidate/Release verification or updater acceptance. The previously interrupted native offer remains `CANCELLED`/acceptance `UNKNOWN`; its terminal disposal is separately `PASS` as recorded above. Public stable GitHub update remains **NOT VERIFIED**.

The earlier checkpoint boundary above is superseded by this bounded DEV visual implementation. No candidate build, Setup, GitHub mutation, push or publication was performed.
