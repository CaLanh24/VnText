# VNText Studio 0.1.13 — acceptance hiện hành

**PUBLISHED — [v0.1.13](https://github.com/CaLanh24/VnText/releases/tag/v0.1.13), stable, latest.** Release ACCEPT bởi Brain/Root (2026-10-28) cho phạm vi Owner yêu cầu và validation affected; không phải QA toàn bộ game. Trạng thái hiện hành ở [AI_STATE](../AI_STATE.md).

## Candidate và quyền

- Candidate đã phát hành p13p, source `9b2c05ea2aad8a6c9f4f1079db4138e81f153497` (tag `v0.1.13` annotated, peel đúng source này). Setup SHA256 `ab06e365310ea15d4b9dc48bb2e337c9fb8c51fdc1c5beb12f2ea930b740383d`; exe cài ra `0763a42984a563de570c541998a05b404252254da0f8ef79d969ee17af476206`; payload 7193 file / 514,809,021 byte; 13 asset (Setup + 6 gói + 6 feed). p13o (source `4809077`) và p13n (`5150fd9`) là candidate cũ đã dispose, không phát hành.
- Baseline bắt buộc 0.1.12 → 0.1.13; từ 0.1.13 một thao tác tới latest. Pre-0.1.12/Setup-origin0.1.10 ngoài scope. OPUS limits được chấp nhận, không semantic PASS. Real-game E2E defer NOT TESTED; generated/installed-app acceptance vẫn bắt buộc.
- p13p: traceability 32 + patch-cancel/readback 25 (`8c00998`, runtime giống `9b2c05e`), test authority thứ sáu và `test_worker_tasks` 16 (`9b2c05e`), không skip/warning; focused 66, affected 35/71/22 và WPF harness từ `4809077` reuse (không đổi WPF/extract/image). Asset receipt 13/13, release-verify + hai smoke worker, ba ca updater đạt trên p13p. Native p13p #13: hủy giữa read-back, child dừng 234 ms, terminal 10,818 s (p13o: 43,231 s), không read-back PASS, hash game/CSV không đổi (native51-result.json). Wrapper REVIEW_REQUIRED do `terminal_root preexisting_test_run_content`, tách khỏi child exit 0. Receipt `DEV_RUN/gatec/`: `handoff_p13p.json`, `candidate-receipt-p13p.json`, `candidate-verify-p13p.json`, `updater-matrix-p13p-summary.json`, `brain-accept-p13p.json`, `published_release_v0.1.13.json`.

## Bảng trạng thái acceptance

| Mục | Trạng thái đã biết | Evidence/bước kế tiếp |
|---|---|---|
| #1 Setup, #2 identity | p13o Setup native vào s13p đúng đường, exe/source khớp (`native22-post-install.json` ok:true; lần kiểm đầu ok:false chỉ do Setup còn mở, chạy lại sau khi đóng) | native22-setup-success.png; p13n/s13n là evidence cũ |
| #3, #7–9, #16 | Evidence p13m chỉ được reuse bounded theo patch-only impact review | Không gọi p13n exact-native hoặc toàn bộ PASS |
| #4 SDK recovery | PASS bounded trên p13o (Owner 2026-10-27): không SDK → 0 MAIN / 8 review, PARTIAL, không ID/proof, Translate/Patch khóa | native47-review-result.json; gate canonical `db0e847`+`4809077` |
| #5 SDK offline/cancel | PARTIAL: cancel pha connect (0-byte .part) → terminal một lần, retry bật; retry tải SDK chính thức 8.5.3 vào `s13o/data/tools` COMPLETE (8 MAIN, 0 review, 316 common loại, không zip/.part); lỗi tải/SDK không hợp lệ báo nguyên nhân, không bịa số review (test canonical). Cancel giữa chừng/offline NOT_PROVEN, ngoài release có giới hạn | native48-sdk-result.json |
| #6 OCR | PASS bounded trên p13o: progress theo stage + ETA (97%, còn 24), 22 ready / 8 failed / 0 translated, untranslated là bản gốc, 31 hash nguồn khớp; không MT/render | native47-ocr-result.json |
| #10 cancel-exit | PASS bounded | native10-s13n-result.json; không có exit-code/in-flight-boundary proof |
| #11 ordinary failure | PASS bounded, thông báo nguyên nhân còn English | native11-s13n-result.json, sampled hash checks |
| #12 patch-readback | PASS bounded generic text 8000/8000 | native12-13-s13n-root.json; installer apply/restore chưa chạy; không engine/game claim |
| #13 patch-cancel | PASS bounded trên p13p (native51): child read-back dừng 234 ms sau yêu cầu, terminal 10,818 s so với 43,231 s trên p13o (trace abort batch hóa), không read-back PASS, output giữ nguyên | native51-result.json, native49-readback-result.json |
| #14/#15 editor | PASS bounded: search/preview/apply/undo (khôi phục đúng SHA)/lưu tay/reload; thay đổi ngoài ở dòng khác và cùng dòng bị từ chối, hash ngoài giữ nguyên, edit dirty giữ, Cancel giữ edit, discard reload bản ngoài | native47-csv-result.json; `fx6` edit đã khôi phục từ golden |
| #17–19 UI/DPI/keyboard | #17 PARTIAL: dark Settings/Translate/glossary đọc được. #18 PARTIAL: phóng to 1556×800 và khôi phục 1428×794 ở 100%; kéo cạnh không đổi; kích thước tối thiểu và 125/150% NOT_PROVEN, ngoài release có giới hạn (Owner 2026-10-28). #19 PARTIAL: Tab/Return ở cửa sổ chính PASS bounded; Esc trong dialog NOT_PROVEN, ngoài release | native49-ui-result.json, native49-keyboard-result.json; không PASS giả |
| #20/#21 update offline/cache | #21 PASS bounded: lịch sử release tiếng Việt online tới v0.1.12. #20 và cache offline: NOT_PROVEN, ngoài release có giới hạn (Owner 2026-10-28), không đổi mạng | Headless matrix không thay offer/download/restart |
| #22 uninstall | BỎ khỏi release acceptance (Owner 2026-10-28); Setup vào s13p PASS, Uninstall chưa chạy, không PASS giả | native22-post-install.json |
| Publication/readback | ĐÃ PHÁT HÀNH [https://github.com/CaLanh24/VnText/releases/tag/v0.1.13](https://github.com/CaLanh24/VnText/releases/tag/v0.1.13): stable, latest, tag `v0.1.13` → `9b2c05e`, `main` fast-forward tới `9b2c05e` trước commit docs; 13/13 asset khớp tên, kích thước và sha256 với receipt cục bộ | published_release_v0.1.13.json |
| Cleanup | Đã dispose qua registry sau publish (đọc lại không còn): s13o (kèm SDK), s13q, p13o, p13p, fx2/3/5/6/8/9/10/11/12/13, ngoại lệ lịch sử p13n/s13n/s13p đã dispose trước đó. Giữ: baselines (≈3 GB, tái dựng từ release công khai; legacy-0.1.7 khó tái dựng) + inputs + fixtures + source clone, consumer: build route cập nhật của bản kế tiếp, mốc rà lại: lúc bắt đầu bản kế tiếp. 29 root TEST_RUN lịch sử còn câu hỏi ownership, không phải release gate | cleanup_final_result.json, budget_final_p13p.json |

Receipt names above are relative to the `DEV_RUN/gatec` prefix and may be local-only; missing files do not establish PASS. Update this table once per meaningful phase and keep only current verdicts. Detailed source/gate history is in the archive below. Authority/invariants remain in CONTRACTS; checklist below preserves original acceptance wording, including the unresolved #4 contract discrepancy.

## Phạm vi sửa được yêu cầu cho bản cập nhật này (Owner 2026-10-28)

| Mục sửa | Evidence | Trạng thái |
|---|---|---|
| #4 không SDK → review-only, MAIN rỗng, luôn PARTIAL (kể cả 0 dòng) | test canonical `db0e847`/`4809077`; native p13o 0 MAIN / 8 review | PASS bounded |
| #5 lỗi tải/SDK báo nguyên nhân, không bịa số review; cancel pha connect + retry | test canonical; native48 | PASS bounded (giữa chừng/offline ngoài release) |
| #6 OCR có ETA advisory, không MT/render | test canonical; native p13o 22/8/0, ETA thấy | PASS bounded |
| #13 hủy patch/read-back: terminal trung thực; trace abort batch hóa | native49 (child dừng 350 ms, terminal 43,2 s); test mới + 32 + 25 test canonical ở `8c00998` | Đo lại thời gian trên candidate mới |
| #14/#15 CSV editor, #11 lỗi thường, #12 patch read-back, #1/#2 Setup | native47/p13n; p13o Setup | PASS bounded |
| #3, #7–#10, #16 model/tiến trình/hủy | evidence p13m/p13n; đường trace batch cũng dùng ở dịch: test traceability đạt | Reuse có giới hạn, không PASS exact-native |
| Updater 0.1.12→0.1.13 | ma trận headless 3 ca | PASS headless |

## Native acceptance checklist (Gate C, packaged candidate)

Each item needs native evidence on the installed candidate (exact executable SHA-256 and source SHA recorded); automated or fake-adapter PASS does not satisfy it.

| # | Action / state | Expected | Evidence |
|---|---|---|---|
| 1 | Fresh Setup into an empty registered folder; Intel terms accepted deliberately | Install completes; `VNText Studio.exe` and `Uninstall.exe` at root; `app/`, `data/` created; no AppData/shortcut writes | Setup SHA, install inventory vs payload manifest, startup log shows worker ready |
| 2 | About / version | 0.1.13 and source SHA from `app/RELEASE.json` | Screenshot + RELEASE.json hash |
| 3 | Model absent (rename the packaged model dir in the test install only) | Translate readiness explains the missing model and offers no false Start; restoring it returns to ready | Screenshots before/after |
| 4 | Ren'Py SDK missing on a generated Ren'Py fixture | Recovery offers picker, pinned download, cancel, retry through Extract and continue as review-only export (Owner decision in CONTRACTS: review evidence only, MAIN empty, no native IDs/proof, no translate/patch, always PARTIAL); an SDK failure shows the cause and no review count | Screenshots of each choice + extract_status/CSV counts |
| 5 | SDK download offline / cancelled mid-transfer | Actionable failure, partial file removed, retry offered | Screenshot + absence of partial file |
| 6 | Extract on multi-image OCR-only fixture | Stage-specific progress, advisory ETA format, no machine translation or rendering during Extract | Screenshots + CSV/report counts |
| 7 | Translate a blank CSV; switch pages during the run | Progress stays on the owning card; late events cannot overwrite a newer/completed run | Screenshots at two pages |
| 8 | Cancel during a real CT2 call | Request → "đã nhận yêu cầu hủy" → terminal "Đã hủy"; busy clears; CSV keys/source unchanged; no `.tmp`; cache lock released | Screenshots + CSV hash/diff |
| 9 | Retry after cancel | Run completes normally; untouched rows translated; no stale terminal | Screenshot + CSV |
| 10 | Cancel-and-exit while translating | App waits for the terminal, exits once; no orphan worker process | Process list before/after |
| 11 | Ordinary failure (e.g. invalid CSV) | Shown as "Lỗi" with the real reason and action, never as cancellation | Screenshot |
| 12 | Patch → read-back on generated fixture | Preflight valid counts; read-back verified; delivery instructions shown | `patch_verification.json` + screenshot |
| 13 | Patch cancel | Single "Đã hủy" terminal; output state reported | Screenshot |
| 14 | 27k-row CSV: search, preview, apply, undo, save, reload | Responsive; counts correct; save preserves order/fields; reload shows saved data | Screenshots + CSV hash |
| 15 | Dirty edits + external file change / close with dirty edits | Themed Yes/No/Cancel; Cancel keeps edits; external change detected | Screenshots |
| 16 | Busy-state protection | Editing/actions that would race the running task are disabled with a visible reason | Screenshot |
| 17 | Pages/dialogs/notifications/tooltips sweep | Empty, loading, ready, running, cancel, error and success states legible in theme | Screenshot set |
| 18 | Small window, resize, 100/125/150 % DPI | No clipped controls; scroll where needed | Screenshot per size/DPI |
| 19 | Keyboard focus/tab order; Enter/Esc in dialogs | Logical order; visible focus; Esc cancels | Screenshot/notes |
| 20 | Update check offline | Actionable network failure with retry; no false success | Screenshot |
| 21 | Release history / Vietnamese notes / cached latest | Notes render; cache used offline; success wording correct after update | Screenshot |
| 22 | Uninstall | Single confirmation; folder left empty | Folder listing |

## Final acceptance record

Đã chốt: Release v0.1.13 công khai tại https://github.com/CaLanh24/VnText/releases/tag/v0.1.13; source `9b2c05ea2aad8a6c9f4f1079db4138e81f153497`; Setup `ab06e365310ea15d4b9dc48bb2e337c9fb8c51fdc1c5beb12f2ea930b740383d`; 13 asset đọc lại khớp; native p13o/p13p bounded và gate affected như trên; chưa kiểm: 125/150% DPI, kích thước cửa sổ tối thiểu, offline, lần hủy SDK giữa chừng thứ hai, Esc trong dialog, uninstall (Owner đã bỏ #22) — NOT_PROVEN ngoài release, không PASS giả. Không có QA toàn bộ game thật; model OPUS-MT giữ giới hạn đã chấp nhận.

## Lịch sử và provenance

- [Snapshot trước tổ chức tài liệu](history/RELEASE_0.1.13.md) giữ nguyên toàn bộ chronology, failed attempts, SHA và verdict tại docs source `b7e842419bef`.
- Các mốc 'NOT STARTED', 'pending', quyền/baseline cũ trong snapshot là lịch sử, không thay bảng hiện hành hay quyết định Owner mới.
- Tìm mục/ID trong [INDEX](INDEX.md), rồi đọc đúng dòng/trường cần thiết; không nạp cả snapshot vào context.

<a id="vntext-studio-0113--implementation-and-acceptance-ledger"></a>
<a id="current-summary-authoritative-everything-below-is-chronological-history"></a>
<a id="starting-point-and-publication-boundary"></a>
<a id="acceptance-ledger"></a>
<a id="execution-order"></a>
<a id="progress-and-evidence-history--chronological-statements-of-pendingcurrent-here-are-superseded-by-the-current-summary"></a>
<a id="native-acceptance-checklist-gate-c-packaged-candidate"></a>
<a id="final-acceptance-record"></a>
