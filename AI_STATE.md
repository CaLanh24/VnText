# Current checkpoint — Báo lỗi sau phát hành 0.1.26, 2026-11-21

Owner yêu cầu chỉ ghi nhận để xử lý sau khi quota reset (lượt sau đã xử lý: xem checkpoint "Sửa lỗi sau 0.1.26" bên dưới). Baseline là tag `v0.1.26` (`4dea6b1`). Bằng chứng là hai ảnh Owner gửi trong chat ngày 21/11; lỗi dưới đây mới được báo, nguyên nhân chưa xác minh.

1. **Quét engine.** Chọn thư mục game và tiến trình đứng ở 99% lâu. Ảnh FallingApart-pc có kết quả font Ren’Py nhưng tiêu đề lại báo chưa nhận diện engine. Kiểm thời gian từng bước và tính nhất quán giữa kết quả, trạng thái và nguồn đang chọn.
2. **Lấy text.** Báo hơn 3 giờ mới 40%; ảnh hiện bước “Lọc ảnh không có chữ”, mục `1444.webp`, sau đó lên 41%. Đo riêng lấy text và quét/OCR ảnh; xác minh phần ảnh có đang chặn CSV và làm rõ tiến trình từng tác vụ.
3. **Màn nhận diện.** Chỉ hiện tóm tắt đủ để biết game đã nhận diện và có thể làm gì tiếp. Đưa danh sách font/ảnh, số liệu kỹ thuật chi tiết và lý do xuống Nhật ký.
4. **Hủy và thoát.** Hủy có thể treo mãi, nút X lại chờ hủy xong. Kiểm worker không phản hồi; nút X phải có đường thoát cưỡng bức hữu hạn, kể cả khi hủy treo. Kiểm khởi động lại và an toàn file đang ghi dở.
5. **Tạo patch.** Sau khi dịch, một nút “Tạo patch” mở tùy chọn font/cỡ chữ rồi chạy kiểm tra tự động và đóng gói. Bỏ bước bắt người dùng bấm “Kiểm tra”, kể cả sau khi đổi font. Chỉ hiện lỗi cụ thể có thể xử lý khi thật sự không thể đóng gói. Cho mở thư mục xuất ngay cả khi chưa có patch. Bỏ cách gọi “spec ảnh” khỏi luồng phổ thông; dùng lựa chọn ảnh dễ hiểu, tùy chọn.
6. **Gỡ patch.** Owner báo các cách gỡ của những bản trước vẫn không gỡ được. Tái hiện trên chuỗi cài/nâng cấp/gỡ từ bản cũ, kiểm file sau gỡ và dữ liệu người dùng bằng hash, báo đúng tình trạng nếu thiếu backup hoặc còn bản dịch cũ.

---

# Current checkpoint — Sửa lỗi sau 0.1.26, 2026-11-21 (Owner giao: sửa 6 nhóm, chưa push/release)

Source `181a2ed48fa603c76a8415a7b28904b4b6c2b3ed` (local, trên `v0.1.26`; chưa push, chưa tag). Receipt `TEST_RUN/agent-evidence/post-0.1.26-fixes/receipt.md` (thời gian trước/sau). Chưa có candidate đóng gói/native UI; DEV evidence không phải QA độc lập.
Nguyên nhân thật: (2) mỗi ảnh RPA mở lại và băm 2 lần file RPA 3,5 GB + PowerShell mới mỗi lần OCR → hàng giờ, và OCR chặn terminal của extract; (1) scan không báo tiến trình ở bước nhận diện engine/font/ảnh, UI duyệt lại thư mục bằng bộ phân loại riêng khác điều kiện với worker nên "có font mà chưa nhận diện engine"; (4) chờ hủy vô hạn, X chỉ hỏi rồi chờ; (5) "Tạo patch" bị khóa tới khi bấm "Kiểm tra", mỗi lần đổi font xóa kiểm tra; (6) thông báo gỡ không nêu file VNText cũ không biên nhận còn lại.
Đã sửa: worker phân loại engine một lần (`engine_detection` + `timings_seconds` trong báo cáo; `overall` trong progress); cache RPA read-only (ghi/patch giữ `fresh=True`); OCR một host PowerShell, đọc ảnh từ bộ nhớ; extract kết thúc sau text và gắn `image_scan_pending`, app tự chạy `image_batch after_extract` như tác vụ riêng (tiến trình riêng, hủy được); màn nhận diện chỉ còn tóm tắt, chi tiết xuống Nhật ký; hủy 10 giây rồi dừng cưỡng bức worker, X lần hai thoát ngay, giới hạn thoát 15 giây, worker tự khởi động lại; "Tạo patch" luôn sẵn sàng sau khi chọn game (tự lưu/kiểm, lỗi cụ thể + cách xử lý), "Mở thư mục xuất" ở tab Patch, "spec ảnh" → "ảnh đã chỉnh (tùy chọn)"; installer nêu bản trước hay game gốc sạch, liệt kê file VNText cũ còn lại kèm hash, backup thiếu → từ chối trước khi ghi; quét dọn stage/temp mồ côi của extract bị kill.
Giới hạn còn lại: (a) FallingApart-pc không có trên máy, chưa tái hiện; (b) **cỡ chữ**: backend không có tùy chọn cỡ chữ, chưa thêm (không bịa); hộp thoại gộp font + ảnh chưa làm, vẫn dùng nhóm Font ở tab Patch; (c) native UI/bản đóng gói chưa chạy (budget DEV 1,89/1,0 GiB non-exempt chặn cấp candidate; cleanup canonical TIMEOUT); (d) test Python dựa SDK Ren'Py/copy-quota (test_renpy_extract_task, test_renpy_archive_roots) và teardown cleanup của test_worker_tasks bị chặn bởi budget đó, không do thay đổi; C# workflow 38 lỗi giống hệt baseline HEAD; (e) tác vụ nền quét ảnh giữ worker đơn luồng: muốn dịch ngay phải bấm Hủy; (f) gỡ patch cũ chưa thử trên bản copy game thật, chỉ harness fixture (43/43).
Bước tiếp: Owner nghiệm thu native trên bản đóng gói sau khi dọn budget theo kế hoạch; quyết định cỡ chữ.

---

# Checkpoint lịch sử — Release 0.1.24 packaging, 2026-11-20

Fixed DEV sole writer; Brain reviews/publishes. Native ACCEPT on 603e86b (The Wrath both fonts) per Owner/Brain; ledger `docs/RELEASE_0.1.24.md`. Owned ~4 GiB Wrath payload disposed canonically (`TEST_RUN/renpy-three-game-qa/cleanup-wrath-payload-receipt.json`), compact evidence kept. Release gates/publisher: see the latest DEV terminal report; no push/tag/publication by DEV.

---

# Current checkpoint — Design QA 0.1.22 (4 findings), 2026-11-19

Owner assigned the 4-finding Design QA batch (`DEV_RUN/qa-0.1.22-3e89a97/design-qa/dev-task.md`): CSV header, outer rail, Settings Data error, Patch font group. Fixed DEV is the sole writer; builds only through the isolated `--artifacts-path` route (never the default bootstrap build or a plain App build; the earlier unauthorized plain build that wrote the blocked App `obj` is a disclosed deviation, current sentinel baseline = 91-file post-accident inventory, unchanged by this batch).
Result (fonts picker follow-up): source `627682e7220ba74f054367dfddbed065e89f8eb7`; QA candidate `DEV_RUN/qa-0.1.22-fp/Start-QA.cmd` (isolated build; hashes/evidence in `TEST_RUN/agent-evidence/fp-dev/fonts-picker-receipt.json`; dq2/dq/3e89a97 candidates kept). The OS file dialog refuses the shell Fonts folder ("permission" message) although the fonts are real files; a new "Font đã cài…" list resolves installed .ttf/.otf files read-only and reuses the same preview + rights acknowledgement + validation + cancel path. DEV evidence is not independent QA.
Previous: Result (follow-up): source `4f4deda948fbdc192893b47be40c95a471e2bca7`; QA candidate `DEV_RUN/qa-0.1.22-dq2/Start-QA.cmd` (isolated build, hashes in `TEST_RUN/agent-evidence/dq-dev/design-qa-followup-receipt.json`; prior candidates `qa-0.1.22-dq` and `qa-0.1.22-3e89a97` kept). CSV title/badge now on the same y as other pages (UI100 122/135, UI120 137/153) with tools open and 4 whole rows; B18 fixed against the task-owned Extract behaviour; outer rail thumb at the viewport edge, wheel/drag/nested CSV and Patch custom-font choose/preview/confirm/cancel proven natively. DEV evidence is not independent QA.

---

# Current checkpoint — Release0.1.21 + uiqa24,2026-11-18

Owner authorizes multi-hop updater source repair, route018 tests, push/release; added all uiqa24 F1–F6 then release. No real-game runs, preserve installed020 and all Owner data. Report TEST_RUN/uiqa24/review.html is evidence, not extra authority.

Root temporary sole writer; fixed Claude DEV72329c3d-5883-4cc8-8d14-60c73886ebd3/session76922e45-71b2-47a9-be97-cf18b927ae26 idle quota-failed cursor1940, live rechecked. No parallel agent/child. Source995bd10 updater focused PASS with exact old-source negative-control failure; updater code unchanged in uiqa24 batch. Source9c3b770 compiled App/installer PASS and focused core/status PASS. Its90 Python tests exposed2 new output-rollback failures (font report created too early), not accepted. Current grouped correction stages font/report in the overlay transaction, restores extras on failure, accounts audited legacy exclusions, distinguishes technical rows from human review, and uses the existing modal shell for install/preview. Added bounded loose/archive font/style/tag/variant inventory with source hashes and explicit compiled/dynamic UNKNOWN; icon/glyph roles remain excluded from text replacement. Product cmap uses indexed lookup.21 pure tests PASS on the prepared source; IO/model/build/native gates pending. No new candidate/native acceptance yet.

Six findings: selected-row authoritative classification/pre-confirmation and per-key outcomes; task-owned Extract status; common straight scrollbar tokens; content-height standalone installer status and confirmation; shared-core in-app install/restore with artifact/CSV/manifest revision binding; bounded glyph NFC/NFD inspection and explicit RenPy replacement-font preview/payload/restore. Font glyph PASS is not runtime/mapping PASS: dynamic/inline/bold/italic mapping remains explicit NOT_PROVEN; Unity/TMP replacement is refused without verified adapter. No blind TTF injection or compatibility claim.

Epoch045-release021@9c3b770 active, eight transitions since037; next ordinary-hop eligibility must be checked by canonical plan, no assumed extra hop. Owner reply call_2d1757edade2431a9fd3eceeb2be54c4 now grants ONE no-delete rebaseline for106ba4a and focused batch descendants, from045; not yet consumed. No standing extra hops. Measured6GiB exact RELEASE_RUN/candidate-0.1.21 under standing2026-10-24 authority; shared11GiB/guard48MiB, terminal1GiB. Existing candidate holds clean source snapshot995bd10, public020/018/007 verified baselines and harness044. Refresh snapshot only after final source. Keep blocked TEST_RUN/u16-focused, TEST_RUN/r17b-focused, App/obj untouched. Owner Setupdownload deletion policy-rejected; no retry/bypass.

Ledger docs/RELEASE_0.1.21.md; small evidence TEST_RUN/agent-evidence/release-0.1.21/current-checkpoint.md and focused-receipt.json. No021push/tag/release. Original018 downloader binary is immutable and buggy; fixed-code018-input route proof is separate from original018 Setup upgrade. Do not edit historical assets or claim old-client in-app success without proof.

Next: commit prepared inventory/authority additions, canonical single-use rebaseline plan/activation and budget check; targeted build/backend/native for affected code, then isolated package, updater/public readback, publish and owned cleanup. Prior020 unrelated gates reusable only with exact unchanged basis; fourteen pure tests pass precommit but no packaged/native acceptance for this batch.
