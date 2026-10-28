# VNText Studio 0.1.13 — acceptance hiện hành

**IN PROGRESS — publication HOLD.** Đọc trạng thái mới nhất ở [AI_STATE](../AI_STATE.md); Owner đã cho hoàn thành/publish sau Brain ACCEPT, không xin lại duyệt routine. Không có Release ACCEPT từ việc tổ chức tài liệu.

## Candidate và quyền

- Candidate hiện hành p13o, source `4809077aecf614edbe26d30ebb0c7238bb3348c0`. Setup SHA256 `7b28ba564fff744f5465037eb0c02a7350e120d8e27bc2c3dbb880818be6ae91`; exe cài ra `0763a42984a563de570c541998a05b404252254da0f8ef79d969ee17af476206`; payload 7193 file / 514,808,080 byte. Candidate cũ p13n (source `5150fd97d159c15456eac704f2aff337cbfd5f22`, Setup `08b504b4…3d29`, exe `02acaf3b…2412`) không chứa remediation #4/#6; evidence native p13n chỉ thuộc p13n.
- Baseline bắt buộc 0.1.12 → 0.1.13; từ 0.1.13 một thao tác tới latest. Pre-0.1.12/Setup-origin0.1.10 ngoài scope. OPUS limits được chấp nhận, không semantic PASS. Real-game E2E defer NOT TESTED; generated/installed-app acceptance vẫn bắt buộc.
- p13o: focused 66 (`db0e847`), affected 35/71/22 gồm WPF harness (`4809077`), asset receipt 13 asset, release-verify + hai smoke worker, ba ca updater (named-0.1.12, health-rollback, tampered); lần đầu `named-0.1.12` fail chỉ do hằng số exe của script, đã sửa và chạy lại ca đó. Receipt prefix `DEV_RUN/gatec/`: `candidate-receipt-p13o.json`, `candidate-verify-p13o.json`, `updater-matrix-p13o-summary.json`, `handoff_p13o.json`. Wrapper REVIEW_REQUIRED do `terminal_root preexisting_test_run_content`, tách khỏi test exit 0. Gate p13n 79/107/22 là lịch sử của candidate cũ.

## Bảng trạng thái acceptance

| Mục | Trạng thái đã biết | Evidence/bước kế tiếp |
|---|---|---|
| #1 Setup, #2 identity | p13o Setup native vào s13p đúng đường, exe/source khớp (`native22-post-install.json` ok:true; lần kiểm đầu ok:false chỉ do Setup còn mở, chạy lại sau khi đóng) | native22-setup-success.png; p13n/s13n là evidence cũ |
| #3, #7–9, #16 | Evidence p13m chỉ được reuse bounded theo patch-only impact review | Không gọi p13n exact-native hoặc toàn bộ PASS |
| #4 SDK recovery | PASS bounded trên p13o (Owner 2026-10-27): không SDK → 0 MAIN / 8 review, PARTIAL, không ID/proof, Translate/Patch khóa | native47-review-result.json; gate canonical `db0e847`+`4809077` |
| #5 SDK offline/cancel | PARTIAL: cancel pha connect (0-byte .part) → terminal một lần, retry bật; retry tải SDK chính thức 8.5.3 vào `s13o/data/tools` COMPLETE (8 MAIN, 0 review, 316 common loại, không zip/.part). Cancel giữa chừng/offline NOT_PROVEN | native48-sdk-result.json; offline cần route Owner |
| #6 OCR | PASS bounded trên p13o: progress theo stage + ETA (97%, còn 24), 22 ready / 8 failed / 0 translated, untranslated là bản gốc, 31 hash nguồn khớp; không MT/render | native47-ocr-result.json |
| #10 cancel-exit | PASS bounded | native10-s13n-result.json; không có exit-code/in-flight-boundary proof |
| #11 ordinary failure | PASS bounded, thông báo nguyên nhân còn English | native11-s13n-result.json, sampled hash checks |
| #12 patch-readback | PASS bounded generic text 8000/8000 | native12-13-s13n-root.json; installer apply/restore chưa chạy; không engine/game claim |
| #13 patch-cancel | PARTIAL: cancel read-back NOT_PROVEN trên p13o (cancel tới 1,8 s sau verifier PASS; patch hoàn tất ở `out2`). Đã chuẩn bị watcher chỉ đọc và output trống `out4` | native13_prep.json, native13_watch.ps1; chỉ thử lại có đo, báo NOT_PROVEN nếu cửa sổ quá ngắn |
| #14/#15 editor | PASS bounded: search/preview/apply/undo (khôi phục đúng SHA)/lưu tay/reload; thay đổi ngoài ở dòng khác và cùng dòng bị từ chối, hash ngoài giữ nguyên, edit dirty giữ, Cancel giữ edit, discard reload bản ngoài | native47-csv-result.json; `fx6` edit đã khôi phục từ golden |
| #17–19 UI/DPI/keyboard | #17 mở. #18 NOT_PROVEN: cần Owner cho đổi OS display scale, Settings launch lỗi, không thay bằng app scale. #19 NOT_PROVEN: focus/Esc ambiguous (source có Esc) | Chờ câu trả lời thật của Owner; không suy diễn |
| #20/#21 update offline/cache | #21 PASS bounded: lịch sử release tiếng Việt online tới v0.1.12 (native48-release-notes.png). #20 và cache offline mở: cần route mạng offline do Owner cho phép | Headless matrix không thay offer/download/restart |
| #22 uninstall | PROVEN_BLOCKED/NOT_PROVEN: Setup vào s13p PASS, nhưng tool policy chặn mở `s13p/Uninstall.exe`; không vượt qua bằng CLI/đổi tên/automation | native22-result.json; giữ `s13p` cho native uninstall khi policy cho phép |
| Publication/readback | HOLD | Brain ACCEPT trước mutation; public exact asset/live-update checks riêng |
| Cleanup | PARTIAL, khoảng2.33GB đã dọn | cleanup_phase_result.json; unresolved roots phải có consumer/review point, không thành gate giả |

Receipt names above are relative to the `DEV_RUN/gatec` prefix and may be local-only; missing files do not establish PASS. Update this table once per meaningful phase and keep only current verdicts. Detailed source/gate history is in the archive below. Authority/invariants remain in CONTRACTS; checklist below preserves original acceptance wording, including the unresolved #4 contract discrepancy.

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

Pending: source/payload identities, exact validation and skips, installed/native/Setup/updater evidence, release assets/readback, cleanup disposition and Brain ACCEPT. No publication from partial evidence.

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
