# VNText Studio — Contracts Spine

> Tra cứu theo chủ đề, không nạp toàn file khi bootstrap. Trạng thái task/nguồn quyền hiện tại ở [AI_STATE.md](AI_STATE.md); bản đồ tài liệu ở [docs/INDEX.md](docs/INDEX.md). Evidence lịch sử dưới từng mục giữ nguyên SHA/phạm vi, không tự là gate đã đạt của task mới.

## Tra cứu nhanh

- [1. Entry, key, CSV và package](#1-entry-key-csv-và-package)
- [CSV editor write boundary](#csv-editor-write-boundary)
- [1a. Traceability, provenance và identity](#1a-traceability-provenance-và-identity)
- [2. Extract contract](#2-extract-contract)
- [2a. Unity analyzer và resource inventory](#2a-unity-analyzer-và-resource-inventory)
- [3. Translation structure và quality gate](#3-translation-structure-và-quality-gate)
- [4. Translation states và memory](#4-translation-states-và-memory)
- [4a. Local Translation V2: classifier, model, cache, glossary và context](#4a-local-translation-v2-classifier-model-cache-glossary-và-context)
- [5. Worker NDJSON protocol](#5-worker-ndjson-protocol)
- [6. WPF binding, command và workflow state](#6-wpf-binding-command-và-workflow-state)
- [7. Patch, UnityFS và Addressables](#7-patch-unityfs-và-addressables)
- [8. Naninovel và Ren’Py boundary](#8-naninovel-và-renpy-boundary)
- [9. Compatibility facade](#9-compatibility-facade)
- [10. Portable Release](#10-portable-release)
- [10a. Test artifact retention and cleanup lifecycle](#10a-test-artifact-retention-and-cleanup-lifecycle)
- [10b. Prospective artifact-registry epoch](#10b-prospective-artifact-registry-epoch)
- [TEST GAP đã biết](#test-gap-đã-biết)
- [10c. DEV validation và chiến dịch game](#10c-dev-validation-và-chiến-dịch-game)

Mỗi mục ghi `Owner`, invariant phải giữ và bằng chứng hiện có. Đây là contract kỹ thuật đã quan sát được; không mở rộng behavior ngoài source/test.

## 1. Entry, key, CSV và package

**Owner:** `vntext/entry.py::make_key`, `Entry.finalize`, `Entry.to_csv_row`, `Entry.to_manifest`; `vntext/package_io.py`.

**Invariant:**

- Key là SHA-1 16 ký tự đầu của UTF-8/surrogatepass cho chuỗi `file_path + "\n" + context + "\n" + method + "\n" + text`.
- `Entry.finalize()` chỉ tạo key khi key đang rỗng; không ghi đè key đã có.
- `CSV_FIELDS` và thứ tự hiện tại là cố định: `key`, `source_text`, `translation`, `context`, `file_path`, `object_info`, `import_method`, `safety`, `backend`, `byte_limit`, `patch_note`.
- CSV dùng `utf-8-sig`, `newline=""`; đọc giữ field cũ, bổ sung field bắt buộc còn thiếu; ghi giữ thứ tự field đầu vào rồi append field bắt buộc thiếu.
- Desktop (Owner 2026-11-09): một tài liệu `translation.csv` chứa cả dòng chính và dòng cần xem lại; sửa/lưu và chọn nguồn Patch trên cùng tài liệu. Manifest `unified_document` giữ vai trò review authoritative: nhập bản dịch không tự tạo writer proof hoặc mở khóa dòng chưa patch được. MT vẫn bỏ qua các dòng này. Technical audit ở JSON; legacy CLI/caller `separate_review=True` giữ các ledger CSV riêng theo `write_package`.
- `manifest.json` format hiện tại là `2`, có `tool`, `version`, `entries`, `technical_skipped`, `stats`; entry giữ locator, import method, backend, review state và duplicate locations.
- Không đổi thứ tự row, key, field name, locator hoặc cách phân tách main/review/raw nếu chưa có migration và golden evidence.

**Tests/evidence:** `tests/unit/test_characterization_key.py`, `test_characterization_package_split.py`, `test_csv_editor_api.py`, `test_golden_artifacts.py`, `test_refactor_contract_baseline.py`, `tests/golden/refactor_contract_baseline.json`.

### CSV editor write boundary

Audit R01: Save, bulk replacement and Undo share expected-revision/ownership checks. Bulk callers should carry source_sha256 from load_document; legacy callers snapshot at operation entry. Backups preserve exact pre-write bytes. Review-ledger reconciliation is staged and restored only while this operation still owns the resulting bytes. Undo uses a per-backup receipt for committed CSV/review revisions; a legacy backup without that receipt requires an explicit current CSV hash. Foreign writes are refused/preserved. These optimistic multi-file operations are recoverable, not an OS-level atomic compare-and-swap against hostile writers; retain backup/error evidence on partial rollback.

Editor load rejects ambiguous headers, mismatched record widths, malformed quoted records and empty/duplicate keys. Save compares the current on-disk baseline: field order, row count/order and every field except translation are immutable. Required legacy columns may be appended under the existing CSV contract. Backup precedes atomic CSV replacement; a synchronous readback/review-ledger failure restores exact CSV and existing review bytes, and reports rollback failure explicitly. This is not a multi-file crash transaction. Manual draft translations may still be saved with visible structural warnings; invalid drafts do not resolve review or pass Patch gates. Reload/open with unsaved edits offers Save/Discard/Cancel; Cancel preserves in-memory edits and disk bytes.

## 1a. Traceability, provenance và identity

**Owner:** `vntext/traceability.py::TraceStore`, `vntext/package_io.py`, `vntext/app_tasks.py`, `vntext/patch_readback.py`.

**Invariant:**

- Trace schema hiện tại là v2 và nằm trong package-local `.mt/traceability.sqlite3`; package identity chỉ phụ thuộc extraction identity, không phụ thuộc timestamp/statistics hoặc việc row chuyển ledger.
- `Entry.key` là identity gốc; `trace_id` được gắn với package/key; duplicate locator phải có `target_id` riêng, không gộp thành một patch target.
- Trace phải giữ source text/file/context, locator, classification/reason, model/translation/validation/patch/read-back metadata và các fingerprint đầu vào khi pipeline đã cung cấp.
- One-writer lock, WAL, `synchronous=FULL`, busy timeout và crash recovery là safety contract. Run/action đang dở không được suy ra PASS; phải thành `ABORTED`/`UNKNOWN` hoặc failure phù hợp.
- `PATCHED` chỉ chứng minh writer đã báo ghi; chỉ reopen target, đối chiếu locator/source/translated value và semantic verification mới được nâng thành `READ_BACK_VERIFIED`. Thiếu hoặc lỗi read-back là fail-closed/`NOT_TESTABLE`, không bị che bởi output file tồn tại.
- Trace là additive evidence. Worker/app normal route phải ghi `trace_summary.json`, `diagnostic_summary.json` và JSONL export; direct caller có thể opt out/`NullTraceSink` nhưng phải khai báo `TRACE_NOT_ENABLED` cùng reason/impact trong report. Không được tuyên bố provenance đầy đủ cho caller chưa đi qua TraceSink.

**Tests/evidence:** `tests/unit/test_traceability.py`, `test_patch_readback.py`, `test_patchability.py`; package trace integration trong `test_traceability.py`.

## 2. Extract contract

**Owner update 2026-11-04:** Re-extract may reuse a nonempty output directory. Overwrite generated result files without retaining old-output backups; preserve unrelated files and never clear the selected directory. Generate privately, invalidate readiness during publication, commit current readiness last, refuse source/output overlap, links and externally changed destinations. CSV editor Save/Discard/Cancel and its separate backup contract remain unchanged.

**Owner:** `vntext/extract_pipeline.py::extract_project`; family ở `extract_text.py`, `extract_unity.py`, `extract_naninovel.py`, `extract_quality.py`, `extract_postprocess.py`; output ở `package_io.py`.

**Invariant:**

- `extract_project(input_path, output_mode, progress_callback, extract_level)` trả `(main_entries, review_entries, stats)` và giữ progress/error/timeout behavior hiện tại. Trước khi trả kết quả, `route_main_flow` đánh giá mọi entry; chỉ entry `SUPPORTED_AND_PATCHABLE` có đủ proof mới vào `main`, entry còn lại vẫn được giữ trong `review` và đánh dấu `review_only`.
- `safe`/`deep` và `balanced`/các extract level hiện có là lựa chọn behavior, không tự đổi default.
- Extract phải giữ `Entry` metadata: `file_path`, `context`, `object_info`, `import_method`, `safety`, `locator`, `backend`, key.
- Raw slot/blob/unpatchable không trở thành dòng patchable trực tiếp; `package_io.is_direct_asset_patchable` và `split_asset_patchable_entries` quyết định phân loại. `naninovel_raw_candidate` chỉ có thể được `write_package` promote khi `auto_candidate_action` trả `promote`; các trường hợp còn lại giữ ở review/raw ledger.
- Plain text, TextAsset/language table, Unity TypeTree/UI, proven Unity Localization StringTable và Naninovel script/blob là các family riêng; postprocess/dedupe chạy sau scan.
- Discovery giữ suffix routing cũ cho format đã biết nhưng bổ sung bounded signature routing cho extensionless UTF text và Unity container header. Extensionless `.resource/.ress/.resS` sidecar không được coi là Unity asset patchable chỉ vì tên file.
- Plain-text entries chỉ được promote khi line locator + writer/reopen proof đủ: `.txt`, `.nani`, `.scenario` và extensionless text hiện dùng line route; JSON/CSV/XML/YAML/unknown structured text giữ review/extract-only boundary cho đến khi có field-level writer. Extensionless plain-text entries phải mang `patch_proof` đầy đủ và được kiểm tra bằng extract → package symmetry gate.
- TextAsset line/table và Unity UI entries có locator `path_id` + field/line metadata; display-like generic TypeTree entries chỉ được gắn proof sau micro-fixture roundtrip. No-TypeTree custom objects không được promote nếu chưa có reader/writer/reopen proof.
- Direct Naninovel Script `@choice`/`@print`/string entries có `path_id`, scan/display ordinal và proof của Script-object writer; raw blob/offset-only candidates không được promote.
- SQLite signature được route qua bounded read-only inventory. Chỉ subset `structured_sqlite_value` an toàn được vào `MAIN`: ordinary rowid table, đúng một `INTEGER PRIMARY KEY`, cột `TEXT`/`CHAR`/`CLOB` có tên/type text-like, không có WAL/SHM sidecar; locator phải có table/column/rowid/primary-key identity/schema fingerprint/file SHA-256 và full patch proof. Writer chỉ sửa database copy trong transaction, reopen và semantic-verify. Các schema composite/non-integer/`WITHOUT ROWID`/virtual/WAL-sidecar/custom hoặc text candidate ngoài subset dùng `sqlite_text_candidate`, `review_only=true`, không vào MAIN. Database lỗi/vượt boundary phải hiện trong extract error, không fallback raw scan để tạo bằng chứng giả.
- YAML `.yaml`/`.yml` được route qua bounded strict-UTF-8 line inventory; mapping/list/block scalar candidate chỉ vào `review_only` với line/column/field metadata, không vào `MAIN` và không có patch proof cho tới khi chứng minh parser/schema/anchor/tag semantics, stable writer, reopen và semantic verification. File lỗi UTF-8, vượt size/line/entry boundary hoặc không đọc được phải hiện trong extract error, không fallback `plain_text`/`raw_scan` để tạo bằng chứng giả.
- Analyzer path/class markers `Localization`/`catalog.json` chỉ là capability evidence chưa đủ, không tự động demote mọi structured row. Generic JSON/CSV/XML chỉ vào MAIN khi chính method đó có locator/precondition/writer/reopen proof. `unity_localization_string` chỉ vào MAIN khi class là `StringTable`, field path đúng `m_TableData[*].m_Localized` và có proof format-specific; SharedTableData keys/metadata, AssetTable, UI references và các schema khác vẫn `REVIEW_REQUIRED`.

**Tests/evidence:** `tests/unit/test_golden_artifacts.py`, `test_naninovel_script_extract.py`, `test_unity_capability_microfixtures.py`, `test_textasset_key_value_prefix.py`, `test_characterization_package_split.py`, `test_extensionless_roundtrip.py`, `test_sqlite_review_extract.py`, `test_yaml_review_extract.py`.

**Owner product decision (2026-10-24):** Extract performs image discovery/inventory and OCR only. It must not machine-translate or render image text. Image translation and rendering belong to Translate and remain supported capabilities with their existing provenance, image delivery, approval invalidation, output receipt, and rollback protections. This is a backend route change as well as a UI change; changing labels alone does not satisfy the decision.

## 2a. Unity analyzer và resource inventory

**Owner:** `vntext/unity_analyzer.py`; regression `tests/unit/test_unity_analyzer.py`.

**Invariant:**

- Analyzer nhận executable, game root hoặc `*_Data` directory và chỉ đọc input; không ghi xuống game root.
- Inventory giữ mọi regular file có thể enumerate được, kể cả extensionless/unknown. Scan error phải nằm trong `scan_errors` và làm `inventory_complete=false`; không được im lặng bỏ qua.
- Unity/container detection ưu tiên signature/header và object probe có giới hạn, không chỉ dựa extension. `resources`, `capabilities` và `summary` phải chứa status đo được.
- Status chỉ dùng `SUPPORTED_AND_PATCHABLE` khi có đủ reader, locator ổn định, writer, preflight, reopen và semantic verification. Inventory hiện tại không tự tạo bằng chứng roundtrip; các capability chưa có proof phải là `EXTRACT_ONLY` hoặc `REVIEW_REQUIRED`.
- `patch_verification=NOT_RUN` là trạng thái trung thực của analyzer read-only, không được diễn giải thành Patch PASS.
- Analyzer `coverage` tách resource status khỏi capability observations và phải báo riêng `writer_coverage`, `locator_precondition_coverage` và `patch_verification`; các trường này không được suy ra từ signature/object probe.
- Extractor mới phải route qua `route_main_flow` và app/release caller gọi `write_package(..., enforce_symmetry=True)` sau khi gắn `patch_proof`; caller legacy không truyền cờ này để giữ manifest/CSV characterization cho tới khi migration riêng được chứng minh.
- Signature routing không tự nâng capability status: extensionless Unity header chỉ được đưa vào existing Unity reader để reader tự chứng minh; extensionless text chỉ được promote khi locator/writer/reopen/semantic proof đã có.
- External game data is opt-in through an explicit input path. Generic Unity must not import bundled reference data or depend on character/name lists.
- Large Unity resources must not be loaded into a second whole-file Python `bytes` object for optional classification hints; the choice scan is read-only and failure of that hint must not abort or silently truncate object extraction.

**Tests/evidence:** `tests/unit/test_unity_analyzer.py`; disposable game-copy inventory dưới `TEST_RUN/unity_analyzer_phase2/`.

## 3. Translation structure và quality gate

**Owner:** `vntext/mt_check.py`, `mt_strategies.py`, `mt_classify.py`, `mt_apply.py`, `mt_qa.py`, `patch_gate.py`.

**Invariant:**

- Mask/restore không được làm mất placeholder, tag, variable, bracket token, literal `\\n`, ký hiệu `♡`, pipe/color/RandPick segment hoặc synonym prefix/variant.
- `mt_check.PH`, `TAG`, `BRACKET_TOKEN`, `structural_problems` là structural gate; không đổi regex/semantics chỉ để tăng số dòng dịch.
- Identity translation chỉ hợp lệ khi có lý do kỹ thuật/whitelist/Vietnamese source; Naninovel identifier không được dịch như display text.
- Garbage repetition, HTML/entity garbage, English residue, placeholder/tag/newline mismatch và legacy metadata có thể chặn patch qua `patch_gate.translation_passes_patch_gate`.
- External reference data, nếu người dùng cung cấp cho một audit riêng, chỉ là read-only evidence; không được tự ghi vào `translation.csv` và không miễn structural, quality, English hoặc Patch Gate.
- Preprocess fallback chỉ theo token English chung và tokenizer/model metadata; không theo CSV key, game path hoặc VH wording. Phân loại keep phải dựa source gốc, không được biến display text thành keep chỉ vì token đã được mask/restore.
- `mt_apply.apply_batch` là hard write gate; lỗi một batch không được âm thầm ghi dữ liệu sai vào CSV.

**Tests/evidence:** `tests/unit/test_mt_structural.py`, `test_mt_classify.py`, `test_mt_quality_routing.py`, `test_mt_strategies.py`, `test_patch_preflight.py`, `test_mt_patch_gate_write.py`, `test_user_glossary.py`, `test_intentional_keep.py`.

## 4. Translation states và memory

Owner clarification 2026-11-05 for0.1.16: usable raw Vietnamese output is the
product target; idiom, context and style errors may be manually revised or
handled by other tools. These model-quality limits must be disclosed but are
not a perfect-semantic-quality release gate. The app must not damage correct
Vietnamese during repair, silently drop content, bypass structural/Patch guards
or report unresolved rows complete. Translation stays free and offline; this
does not authorize an unreviewed backend/model switch.

Owner decision 2026-10-21 (direct instruction in Brain, relayed under existing
coordination authority): necessary downloads and execution permissions for the
active product semantic-quality goal may proceed without routine reapproval.
This supersedes that task's earlier no-download restriction. Each acquisition
still requires exact provenance/license/resource preflight and owned lifecycle;
0đ budget, one writer/no child, shared6GiB/nonexempt1GiB, no user/historical-data
deletion or unrelated host/publication actions remain. Model acquisition/testing
does not establish semantic/product acceptance. Integration must satisfy product
contracts and Brain review with actual semantic/workflow/native evidence.
Owner paused this semantic-quality plan on2026-10-21 because of guest RAM;
that pause takes precedence over execution permission. No automatic watcher,
retry or research resume until explicit Owner reopening. Subsequent Git delivery
authorization covers accepted source/test/docs only, not model integration or Release.

**Owner:** current product route: `mt_ct2_status.py`, `mt_ct2_pipeline.py`, `mt_memory.py`, `app_tasks.py`.

**Invariant:**

- Trạng thái phải phân biệt `translated`, `pending`, `review_only`, `blocked`, `applied`, `copied_vi`, `complete`, `pipeline_liveness`.
- `complete` chỉ đúng khi không còn pending, review-only hoặc blocked theo `_build_translate_result`/`snapshot_translate_status`; có progress nhưng còn review/pending/blocked là partial, không báo hoàn tất.
- WPF Dịch local preflight dùng CSV đang chọn, không kiểm một thư mục xuất khác. Sau dịch, hiển thị counts mới và hủy preflight cũ; package chưa complete không sẵn sàng đóng gói final Patch. CSV/manifest và structural/Patch validator vẫn là trust boundary.
- CT2 giữ model readiness, retry/quality routing, known-bad clearing, translation memory/context family và retranslate behavior; retry của dòng bị gate chặn phải dùng đầy đủ mask/restore/segment strategy dù full batch chọn fast retry.
- Memory/glossary chỉ áp dụng khi đúng package/context; external reference data là read-only evidence, không phải translation memory và không dùng cache cũ để ghi đè bản dịch frozen ngoài policy.
- Owner có thể ủy quyền agent duyệt nội dung; phải lưu riêng quyết định, nguồn quyền/reviewer, đúng ID/source/target/context/exclusions và hash gói gốc, không sửa bản nháp gốc thành approved. Duyệt do agent được ủy quyền không phải direct human linguistic gold, không tự cấp quyền training, bank toàn cục hay acceptance toàn app. Quyết định2026-10-20 “m duyệt đi” tại Brain turn01a158d1 áp dụng17câu/6terms của `evaluation/translation_owner_review_v1` theo `evaluation/translation_owner_approval_v1/decision.json`; giữ human_gold/training_eligible=false. Trước tích hợp phải chứng minh scope thực không rộng hơn scope được duyệt, kể cả fallback/cache/rebuild.
- Mỗi E2E run phải tạo package tạm từ input được khai báo, cô lập output dưới `_work`; `.mt`, review ledgers và patch output của run khác không được đi qua run sau. Bài partial chỉ chứng minh safety với `complete=false` và không chạy final Patch; bài final E2E chỉ gọi Patch sau `complete=true`.

**Tests/evidence:** `tests/unit/test_worker_translate.py`, `test_worker_qa_m3.py`, `test_mt_patch_gate_write.py`, `test_user_glossary.py`, `test_mt_structural.py`; `tests/lib/worker_test_lib.py`.

## 4a. Local Translation V2: classifier, model, cache, glossary và context

**Owner:** `vntext/mt_classify.py`, `vntext/mt_model_adapter.py`, `vntext/translation_cache.py`, `vntext/mt_ct2_pipeline.py`, `vntext/glossary_v2.py`, `vntext/context_builder.py`.

**Invariant:**

- Classifier V2 là decision boundary authoritative của route CT2/status/trace: giữ `TRANSLATE`/`REVIEW`/`DO_NOT_TRANSLATE`/`UNSUPPORTED`, policy version/hash, canonical reason, ledger, confidence và bounded evidence; giữ nguyên row order/key và không bỏ candidate. `classify_row()` vẫn tồn tại cho compatibility/internal rule evaluation; caller bình thường phải dùng adapter authoritative để REVIEW/UNSUPPORTED không lọt vào MT hoặc completion. `translation.csv` không nhận diagnostic V2.
- CT2/OPUS-MT là model route duy nhất của app. Model adapter chỉ lộ `translate`, `translate_many`, config và metadata; mọi output vẫn qua structural/quality/Patch Gate.
- The public product scope is CT2/OPUS-MT only. Argos route, dependency, and implementation are removed; retained Argos planning documents are historical records, not compatibility or product contracts.
- Translation cache là package-local SQLite; chỉ ghi candidate đã validation PASS; fingerprint bao phủ key/source/context/glossary/memory/classifier/model/strategy/protected-span inputs; cache hit phải được revalidate. Single-writer lock/WAL/transaction/reopen là contract cache, không chia sẻ tùy tiện giữa package.
- Retry là selective: row lỗi/rejected mới vào full-sentence/strategy retry; retry attempt phải có trace/evidence riêng và không làm mất frozen translation hoặc biến lỗi thành `complete=true`.
- `.mt/v2/glossary.json` là additive schema có scope/priority/kind/fingerprint; flat glossary cũ vẫn tương thích. Exact conflict cùng priority phải fail-closed/review; mask/restore không được chạm tag, placeholder, control token hoặc protected span.
- Glossary V2 conflict là row-local: term phải có occurrence maskable ngoài vùng protected của parser hiện hữu, đúng case/scope/word boundary; absent/protected-only term không chặn dòng khác. Nonconflicting mask token ordinal/restore mapping giữ nguyên. Cache strategy của package có glossary entries mang version applicability2 để không tái dùng draft thiếu prose từ policy cũ; không xóa cache cũ hoặc tự ghi đè CSV frozen.
- `.mt/v2/context.jsonl` chỉ ghi context bounded khi có boundary rõ ràng theo file + engine + group; thiếu metadata là `insufficient_metadata`, không đoán xuyên file/engine. Sidecar trả status `METADATA_ONLY`, được record/fingerprint; đây không phải bằng chứng context đã được model sử dụng hiệu quả và không được mô tả như prompt injection.
- Historical VinAI benchmark results are R&D evidence only. VinAI has been removed from the app route and Release packaging; `model=vinai` is rejected. The shipped model runtime is CT2/OPUS-MT only.

**Tests/evidence:** `tests/unit/test_mt_classify.py`, `test_translation_cache.py`, `test_glossary_context_v2.py`, `test_traceability.py`, `test_worker_protocol.py`, `test_worker_translate.py`; CT2 worker and strategy regression.

## 5. Worker NDJSON protocol

**Owner:** `vntext_worker/protocol.py`, `worker_main.py`, `task_runners.py`; consumer `wpf_app/VNText.Studio.App/Models/WorkerEvent.cs`, `Services/PythonWorkerHost.cs`.

**Invariant:**

- `PROTOCOL_VERSION = 1`; mỗi event emit có `v=1`.
- Host gửi object `{"v":1,"type":"run","id":...,"task":...,"params":...}` hoặc `cancel`; worker phát `ready`, `log`, `progress`, `complete`, `error`.
- Task hiện có: `sample`, `extract`, `translate`, `patch`; `translate` chỉ nhận `model=ct2` (mặc định), từ chối model đã gỡ và giữ process sống theo protocol.
- `progress` giữ `id`, `done`, `total`, `step`, `item`, optional `eta`; `complete` giữ `ok`, `summary`, `error` và các count state khi có. Patch completion có thể thêm `patch_engine`, `patch_delivery`, `patch_payload_path` và `patch_install_instructions` để WPF hiển thị đúng cách cài theo engine.
- `cancel` receives task-ID-scoped `cancel_ack` with state `accepted` or `stale`; this acknowledges command receipt only and never replaces that task's terminal `complete` event.
- Worker busy/cancel/unexpected exit phải tạo state mà WPF hiểu được; stdout là NDJSON, log stderr không làm hỏng stdout contract.

**Tests/evidence:** `tests/unit/test_worker_protocol.py`, `test_worker_tasks.py`, `test_worker_translate.py`, `test_worker_qa_m3.py`; WPF `wpf_app/VNText.Studio.Workflow.Tests/Program.cs` và `test_wpf_workflow.py`.

## 6. WPF binding, command và workflow state

**Owner:** `MainViewModel.cs` và partials `MainViewModel.Workflow.cs`, `Paths.cs`, `Worker.cs`, `CsvEditor.cs`, `Glossary.cs`, `Notifications.cs`; `WorkflowStatus.cs`, `WorkflowTabs.cs`, `WorkflowStepState.cs`.

**Invariant:**

- Public binding/property/command names hiện có phải giữ: `RunExtractCommand`, `RunTranslateCommand`, `RunPatchCommand`, `CancelCommand`, picker commands, tab/state/progress/log/CSV validation properties.
- Workflow state là Extract → Translate → Patch → Done; extract complete chuyển Translate, translate complete chuyển Patch, partial/review không chuyển Done.
- External CSV phải validate trước khi thay selection; patch phải có CSV/manifest và preflight eligible.
- Worker progress không được báo 100 trước complete; cancel/error phải clear busy và hiển thị trạng thái thật.
- Drag/drop, settings persistence, glossary/CSV editor và notification behavior là surface đang được test; không đổi binding/XAML contract khi chỉ sửa backend.
- WPF-owned confirmations and errors use the themed app dialog and preserve Yes/No/Cancel semantics; operating-system file pickers and security/license consent remain native and require a deliberate user choice.
- CSV editor validates automatically after load/save, keeps actionable validation visible, and exposes bulk find/replace in an expandable area without a nested height-clamped controls scroller. Routine CSV actions do not expose maintenance commands that bypass the normal edit/save/Patch workflow; the existing validator and Patch gates remain unchanged.
- Missing Ren'Py SDK recovery offers an installed SDK picker, pinned SDK download, cancel through the active task, retry through Extract, and an explicit continue that only exports a review-only list (see the Owner decision below). Unsupported extraction stays incomplete; no loose-parser result is ever promoted to MAIN, translated or patched.

**Tests/evidence:** `tests/unit/test_wpf_workflow.py`, `test_ui_app_workflow.py`, `test_qt_app_workflow.py`, `test_legacy_ui_task_contract.py`, `test_ui_progress.py`; WPF workflow harness trong `wpf_app/VNText.Studio.Workflow.Tests/Program.cs`.

**Owner UX decision for update 0.1.11 (2026-10-24):** Text extraction defaults to exhaustive/deep mode; prior persisted Clean/Balanced values do not override this default and the normal extraction page does not expose a mode chooser. This does not change eligibility, review classification, locator, or patch validation. A structurally valid generated `translation.csv` with blank translation cells is ready to start local CT2 translation; Patch readiness still requires actual translations and all existing gates. Progress ETA is advisory seconds/minutes/hours and malformed/unknown values are omitted in favor of an estimating status. Engine analysis must report only evidence-backed detection and explicitly retain unknown/mixed states; Unity analyzer output alone does not classify other engines. Application confirmations/errors use themed WPF dialogs with cancel-safe results; native pickers/consent prompts stay native. CSV controls remain expandable and unclipped, and SDK failure status offers a clear retry/choose path without a parser-based translation or patch route.

**Owner decision for no-SDK Ren'Py recovery (2026-10-27):** "Cho quét tĩnh chỉ để xuất review-only; MAIN rỗng, không dịch/patch, luôn PARTIAL (khuyến nghị)". Without a usable SDK the loose scan is inert (nothing executes) and exports review evidence only: MAIN is empty, every row is review-only with no native ID, unit type, native contract or patch proof, `translation.csv` has no data row, nothing is translated or patched, `extract_status.json` is always PARTIAL and never COMPLETE, and the final Patch gate keeps refusing it. The scan rejects a native template (`template_root`) when `review_only` is requested. RPA/compiled-only/no-SDK fail-closed routes, the symmetry/Patch gates and validators are unchanged and are never loosened or given an exception. An SDK recovery failure (download, chosen SDK not valid) produces no package and no review count: the UI says no package was created and the real cause, never the generic sentinel as a row count. Extract OCR progress carries an advisory ETA (elapsed/progress, same seconds/minutes convention; omitted when unknown); it adds no machine translation or rendering and does not loosen the tilt gate.

**Owner workflow decision for post-0.1.11 remediation (2026-10-24):** Each Extract, Translate, image-translation, and Patch run owns an independent task identity and terminal state; delayed progress cannot overwrite a newer or completed run. Extract is text/OCR only; Translate owns image MT/render. Cancel and cancel-and-exit must expose request, acknowledgement/acceptance, terminal result, timeout, and recovery while preserving safe write/rollback boundaries. UI progress is task-owned, and completion is determined by the terminal protocol event. See `docs/POST_0.1.11_UX_REMEDIATION.md` for the ordered acceptance gates and evidence limits.

Owner UX decision (2026-11-09, local quality batch): MT completion/review counts are advisory for Patch. Run the current per-entry preflight; allow a non-empty proven eligible translated subset, with an explicit omitted-count confirmation for a partial patch. Never promote no-writer/unknown/dynamic rows by acknowledging linguistic review. Preserve source/manifest/hash/schema/placeholder/locator, extraction-identity and writeback guards; keep excluded coverage honest. Whole runtime formatting/control-only Ren'Py rows belong to technical-skipped output, not human translation review. Automatic image MT requires independent crop OCR consensus; an older unconfirmed OCR result must not be silently reused for automatic rendering.

## 7. Patch, UnityFS và Addressables

**Owner update 2026-11-04:** User-facing installation may target the actual game directory; a full game copy is not required. Only modified files need pre-install backups for exact uninstall. Installer must validate source identity/payload hashes, read back installed bytes, refuse changed targets or tampered backups on uninstall, and prevent traversal/link writes. Ren'Py image installation is additive under `game/tl/vietnamese`, preserving original image/archive bytes, with a reversible journal. Validation runs remain on declared fixtures/copies unless Owner separately asks to install on their real game. This supersedes older mandatory-copy wording only for the explicit install/uninstall operation; Extract/Translate/Build still never modify the source game.

**Owner:** `patch_gate.py`, `patch_pipeline.py::apply_translation_package`, `patch_plain.py`, `patch_unity.py`, `patch_safety.py`, `patch_output.py`, `unity_fs.py`, `addressables.py`.

**Invariant:**

- Patch chỉ dùng translation đã qua gate; đọc CSV/manifest theo key và `file_path`, tạo `COPY_TO_GAME_ROOT`, `backup_original` và report. Unity route thêm `patch_manifest.json`/installer; Ren'Py loose-source route tạo native overlay riêng.
- Không ghi game gốc trong workflow tự động; output phải ở patch/work directory, installer/restore dùng exact original hash.
- Patch source paths must be relative, without traversal/drive/absolute components; resolved source paths stay inside the selected game root. Output cannot overlap the game tree. Unity output must be new/empty; retry uses a new directory. Ren'Py retains its existing transactional replacement/rollback contract.
- When explicit CSV/manifest worker params name their own package directory as output, the worker resolves a separate flat `Patch_Viet_Hoa` child. A distinct explicit output remains the caller-selected patch root; source/output validators are not bypassed.
- Patch CSV rejects ambiguous headers, width/key errors and duplicate keys, including untranslated rows. Translated keys/source text and declared path/method/backend must match the manifest. An existing extraction sidecar must be COMPLETE with complete=true; absent legacy sidecars retain compatibility, without adding discovery proof.
- UnityPy cycles must release source/output file handles after a completed writer returns. Native installer/restore must be able to consume the generated payload without relying on worker process exit. Missing installer is reported as payload-only readiness, never an instruction to open a missing executable.
- UnityFS metadata/block flags/serialized file layout phải giữ; replacement dài hơn slot chỉ được xử lý theo owner policy, không blind truncate/grow.
- `unity_typetree_field` rows are auto-patchable only when all five `patch_proof` fields are true; proof-less legacy manifests fail closed as skipped/review-required. Proven rows still require stable `path_id` + `field_path` and the existing TypeTree growth guard.
- `unity_localization_string` rows are auto-patchable only when all five `patch_proof` fields are true, locator identity is `StringTable` and `m_TableData[*].m_Localized`, and the current serialized value equals `source_text`; source drift fails closed without mutation.
- A writer result of `PATCHED` is not read-back proof. `patch_readback.py` must reopen each target on the copied output, verify the exact locator and translated value, then record `READ_BACK_VERIFIED`; missing/failed/unsupported reopen remains `NOT_TESTABLE` or failure and cannot be promoted by the presence of a patch file.
- Addressables catalog phải cập nhật CRC/size đúng bundle sau rewrite; bundle sidecar/serialized CAB không được hỏng.
- Unity UI/TextAsset and font payload routes are generic opt-in operations: they require an explicit locator or source/target mapping, source precondition, save and reopen proof. No mapping or corpus is bundled in the repository; missing target or save error is FAIL/FAIL-CLOSED, never Patch PASS.
- `patch_manifest.json` may carry `game_data_path` and `game_executable`; when absent, installer fallback remains backward-compatible. Install/restore must discover a generic executable plus `*_Data` and must not require a title-specific name.
- Unity `write_patch_manifest`, `patch_manifest.json` và `VNTextPatchInstaller.exe` là output/install surface; Ren'Py native overlay dùng `COPY_TO_GAME_ROOT/game/tl/vietnamese/vntext.rpy` và `COPY_TO_GAME_ROOT/game/zzz_vntext_vietnamese.rpy`, không tạo Unity artifact/instruction. Patch output không tạo compatibility batch launcher.

**Tests/evidence:** `tests/unit/test_patch_preflight.py`, `test_unity_patch_baseline.py`, `test_unityfs_block_flags.py`, `test_unityfs_notypetree_grow.py`, `test_preserve_slot_layout.py`, `test_addressables_bundle_structure.py`, `test_unity_capability_microfixtures.py`, `test_patch_installer.py`, `test_patch_readback.py`, `test_patch_delivery.py`.

## 8. Naninovel và Ren’Py boundary

**Naninovel owner:** `extract_naninovel.py`, `patch_naninovel.py` and the shared locator/read-back services.

**Naninovel invariant:** giữ `@choice`/`@print` display text, script object path id, variable/identifier không dịch nhầm, locator và object count; patch roundtrip trên game copy không làm đổi fingerprint game gốc.

**Ren’Py owner:** `renpy_adapter.py`, `renpy_extract.py`, `patch_renpy.py` và `app_tasks.py` delivery routing.

**Ren’Py invariant:** `RENPY_LOOSE_SOURCE` có native dialogue/string patch route, read-back identity và output overlay tại `COPY_TO_GAME_ROOT`; WPF/worker phải truyền engine/delivery/payload/instruction theo complete event. `RENPY_COMPILED_ONLY`, method không hỗ trợ và manifest mixed engine fail closed, không fallback sang Unity delivery. Full game E2E/Release evidence vẫn là gate riêng.

Vietnamese presentation support is additive inside the same transactional native overlay, never a game profile or source rewrite. A verified engine-bundled DejaVuSans font may supply language-scoped default/explicit GUI text-font styles identified by inert bounded source inspection; literal icon fonts/dynamic font expressions are not rewritten, and no font asset is downloaded or copied. Source/font/container hashes and the support inventory are checked before and after publication; changed support on repeat patch fails closed. A language-name UI helper is eligible only when its zero-argument body is a pure literal language-name dictionary and fixed branches, with a direct text callsite and no ambiguous definitions. A single static language-item list may receive Vietnamese only with a verified pure item constructor; existing items/selection and other-language function behavior remain unchanged. Unknown/custom/dynamic structures are not covered; native switching/rendering and real-game quality remain separate acceptance gates.

Existing target mappings are separate from SDK-generated source-template authority. Re-extraction must preserve native ID/source/speaker/location and original game bytes; target values do not become approved translations. Patch inventories bounded static Vietnamese mappings, refuses conflicts/unverifiable state, preserves unselected mappings when replacing its own overlay, and checks the target inventory before/after activation. Foreign additions or changed mappings fail closed with owned-output rollback; foreign state must survive. Generated SDK repeat-patch lookup is bounded evidence, not whole-game completeness.

Static native Say handling preserves literal/identifier speaker, identifier attributes and a simple `with transition_identifier` through fingerprinted source preconditions and overlay emission. Source/target semantics must agree. Unsupported generated blocks retain raw block/native ID/source/template provenance in an unresolved ledger and force PARTIAL while unrelated supported rows survive. Default parser remains strict; this bounded grammar does not admit expression evaluation or arbitrary statements, and does not prove gameplay.

RPA source recovery separates raw `member_name` from `resolved_game_path` for standard game-relative and legacy `game/` member roots. Archive/member hashes and raw-member lookup must survive this mapping; case-insensitive resolved-path collisions across nested archives fail closed before copy. Materializing readable archived `.rpy` for SDK discovery does not prove the original engine loads it: keep explicit runtime_execution_proven=false and PARTIAL until independent runtime evidence exists.

Unmarked static screen text/textbutton/tooltip slots first enter an inventory with source hash/location. Proven one-line literal slots with enabled Text substitution may use the existing native global-string writer through fingerprinted `display_slot` preconditions and exact source-slot revalidation. Global mapping changes displayed text, not raw tooltip/`_()` values; `substitute=False`, dynamic/composed/multiline or unsupported slots remain review/unresolved and force PARTIAL. Keep SDK native, additional static-global and non-native review accounting distinct; final patch-completion validators still apply. Only exact review-only inventory method/backend may accompany native entries without being treated as a foreign engine.

Compiled Menu/static-localization/Screen slots use version-guarded inert typed AST inspection with exact compiled hash/location and raw archive provenance. Literal Menu labels under static conditions, pure literal `_()` assignments and the bounded static Text/textbutton/tooltip screen tree can use native global-string contracts only after native SDK display/write-back evidence; patch preflight revalidates typed slot/ordinal/text and source hash. Disabled substitution/dynamic or unknown AST stays review/unresolved/PARTIAL. Parsing syntax does not authorize evaluation or invoking pickle constructors/reducers; no completion gate is relaxed. Native mapping evidence does not prove whole-game gameplay or arbitrary screen/AST coverage.

Compiled-game re-extraction excludes target `tl` scripts and the exact canonical non-text VNText activation helper from source-engine classification. A same-named helper with different bytes is not ignored. Existing target inventory/CAS is retained separately; native mapping values never replace source authority.

RenPy static display expressions may span physical lines and contain adjacent string literals, parenthesized literals or bounded constant-string addition, optionally exact `_` of a static string. Decode screen Python-expression semantics through inert AST only; Say source normalization remains SDK-authoritative and must not be replaced by screen/Python normalization. Preserve raw expression/span/location/hash/classification; compiled PyExpr metadata may have unknown columns explicitly null. Exact source/typed-slot binding and native display readback authorize the existing global writer, never runtime evaluation. Interpolation-bearing source templates keep tokens; concat variables/calls/branches/user input/f-strings are runtime-generated, not fragment translations or synthesized final text. Malformed/ambiguous/disabled-substitution forms stay review/unresolved/PARTIAL, including marked strings also seen by SDK. Dynamic count/reason/ledger must remain explicit; no completion-gate relaxation or runtime-capture hook follows from static recovery.

Extract orchestration chặn unproven compiled-only/mixed/missing input; declared compiled-native static TranslateSay route giữ identity và báo PARTIAL cho AST chưa hỗ trợ; UNKNOWN chỉ dùng generic asset route khi bounded signature/format hiện có nhận diện được text/structured/Unity container. Không cần model dịch để lấy text. Gói xuất có `translation.csv` hoặc `manifest.json` được giữ nguyên; lấy lại text (kể cả thêm SDK sau partial) phải chọn output mới. `extract_status.json` ghi COMPLETE/PARTIAL/EMPTY/FAILED và count sau package filtering, không thay proof/locator. Partial/empty không tự advance; sửa CSV không tự chữa lỗi discovery hoặc tạo native identity thiếu. Muốn xử lý thiếu SDK/discovery cần lấy lại text ở output mới; explicit CSV/import/patch vẫn dùng validator hiện có. Package legacy không có sidecar giữ compatibility behavior.

Ren'Py SDK pinned8.5.3; managed DEV SDK ở `.dev-env/tools/renpy-8.5.3`, cache khác trong source repo bị từ chối. Input game không bị ghi. Native template units phải được đối chiếu thành game-owned, engine-common, technical-skip hoặc unresolved; chỉ game-owned rows có contract mới vào translation flow. Chuỗi `renpy/common/` do SDK nhận diện là engine-common phải được ghi riêng trong `renpy_engine_common_exclusions.json` kèm source/member provenance và lý do; chúng không chặn hoàn thành phần game-owned. Missing-source engine-common vẫn phải được đếm/ghi riêng; không thể biến missing-source game-owned thành exclusion. Technical skips luôn giữ reason/count. `COMPLETE` chỉ có nghĩa phần game-owned hỗ trợ đã được trích xuất, khi inventory/native accounting khép kín, không còn game-owned review/error và exclusion/skip counts vẫn hiển thị; không được chỉ đổi status.

Archive adapters chỉ hỗ trợ các RPA header/version được khai báo và kiểm bằng fixtures. Index parsing không được gọi pickle loader hoặc chạy code từ archive. Bắt buộc có giới hạn compressed/decompressed index, số member/kích cỡ tổng/member, kiểm path traversal/duplicate/range/overlap và hash; unsupported/malformed archive làm kết quả fail-closed. Mọi archive entry giữ `container path + container SHA256 + member path + member SHA256`; member source được đọc theo giới hạn, không materialize toàn archive. Image members dùng cùng identity ở OCR, editable review và render. Compiled-only/mixed script không vào main nếu không có parser/source precondition và native read-back proof; no fallback Unity. Workspace đo file/byte, free disk và project quota trước copy, dành 16 MiB; SDK child terminal trước khi dọn.

**Image text invariant:** inventory gồm PNG/JPEG/WebP tĩnh trong loose tree và archive formats đã hỗ trợ; không đọc animation. OCR sidecar gắn source SHA256, original-pixel boxes, và archive container/member identity khi có. Không có confidence score thì mọi OCR cần người duyệt. Người dùng phải sửa/thêm vùng và bản dịch được; preview luôn ràng buộc đúng source hash. Render dùng output riêng không ghi đè input, giữ kích thước/bounds và mọi pixel ngoài vùng sửa. Transparent-glyph mode chỉ nhận region có alpha 0 lẫn visible glyph pixels; nó xóa toàn bộ region rồi compositing glyph antialias, nên chỉ dùng khi nội dung cũ cần bỏ. Nền phức tạp cần thao tác người dùng chỉnh mask/background hoặc xác nhận thay toàn region; flat-fill-only không được coi là hoàn thiện. Không thêm generative inpainting trong contract này. Output ảnh không phải CSV/native patch proof hoặc hoàn thành workflow game.

**Tests/evidence:** `tests/unit/test_renpy_patch.py`, `tests/unit/test_patch_delivery.py`, `tests/unit/test_worker_protocol.py`, `tests/unit/test_wpf_workflow.py`, WPF harness; external full-game/Release evidence chỉ được claim khi fixture và exact Release gate được cung cấp.

### Automatic image drafts — Owner decision 2026-10-18 (after0.1.6)

Owner replaces mandatory in-app OCR review with automatic scan/OCR/en→vi translation beside CSV. This supersedes the manual-review requirement above only for the new automatic draft route; existing manual APIs retain their checks. Hide the OCR table; keep one action to retry an image. Export `images/original`, `images/translated`, `images/untranslated` and a per-image report, preserving source/archive identity. Generated translations are drafts, never fake human approvals. Unsupported/failed images remain unchanged with reasons; missing OCR/model does not invalidate CSV or authorize downloads. No new model/generative inpainting, automatic game installation, or claim of artwork/translation quality. Retry creates a new output set, never overwrites prior results. Use existing CT2/OPUS-MT, infer flat/transparent backgrounds automatically; unsupported complex backgrounds remain untranslated. Preserve dimensions and all pixels outside detected regions.

## 9. Compatibility facade

**Owner:** `vntext_studio.py`, `vntext/extract.py`, `vntext/mt_ct2.py`, `vntext/patch.py`.

**Invariant:** caller cũ qua các module/path trên vẫn import được public/private helper đã được kiểm chứng; facade re-export owner leaf, không trở thành nơi chứa algorithm mới. `vntext_studio.py` vẫn cung cấp surface cũ cho tests/tools/legacy UI.

`vntext.mt_argos` was intentionally removed as a breaking source-compatibility change for the CT2/OPUS-only product. CT2-shared text/protection helpers now live under `vntext.mt_translation_*`; callers importing the removed Argos route or facade must migrate. No current product code may depend on Argos packages or modules.

**Evidence:** import references trong `tests/unit`, `tests/harness`, `tests/tools`; đặc biệt `test_characterization_key.py`, `test_characterization_package_split.py`, `test_naninovel_script_extract.py`, `test_addressables_bundle_structure.py`.

## 10. Portable Release

**Owner:** `release/publish.ps1`, `release/Setup.cs`, `release/package_installer.py`, `release/prune_worker_venv.py`, `release/make_venv_portable.py`, `vntext/release_verify.py`, `wpf_app/.../WorkerPaths.cs`.

**Invariant:**

- Publisher yêu cầu `-WpfUpdateVersion` tường minh và tạo WPF B trong registered staging từ cùng source SHA, kiểm version mới hơn cùng baseline/allowlist/hash trước khi đóng gói. Publisher hoàn tất với `Setup.exe` và thư mục `Updates` tại `ReleaseRoot`; `Updates` giữ manifest hiện hành và package lịch sử. Setup nhúng EXE WPF chính, runtime .NET riêng trong `app/dotnet/`, manifests và `app/worker/` cùng SHA256 inventory. Install root có EXE thật `VNText Studio.exe`, `Uninstall.exe`, `app/`, `data/` và cấu hình nguồn cập nhật do Setup tạo; Setup không tạo shortcut. Upgrade xóa shortcut cũ chỉ khi manifest của bản VNText Studio trước ghi nhận file đó. Thư viện/runtime/worker nằm trong `app/`; `data/` dành cho dữ liệu app. Setup chỉ cho phép EXE chính và Uninstall ở root, kiểm hash/path traversal trước khi ghi.
- Runtime Release xác định application root từ executable; settings, worker scratch, default-generated package, TEMP/TMP/TMPDIR, model/cache và Ren’Py SDK ở `<install-root>/data/`. **WPF updater staging/backup/log ở install root ngoài `data/`** theo update contract bên dưới. Không fallback LocalAppData/system Temp; folder không ghi được phải báo lỗi. Explicit user input/output và game patch delivery giữ nguyên contract. Chỉ CT2 được đóng gói; VinAI/PyTorch không thuộc sản phẩm.
- `Uninstall.exe` hỏi xác nhận một lần, nêu rõ mọi nội dung sẽ bị xóa gồm `data/`, rồi xóa descendants sau safety scan và lock check. Helper ngoài chờ tiến trình Uninstall thoát, xác minh chỉ còn đúng `Uninstall.exe`, xóa file đó, rồi xác minh install root vẫn là thư mục thường không phải reparse point và rỗng tuyệt đối. Install root vẫn tồn tại nhưng rỗng; dữ liệu không được giữ lại. Xóa bị khóa, có path bất ngờ hoặc hậu kiểm thất bại phải báo lỗi và trả exit code khác 0. Không dùng install manifest để giới hạn nội dung cần xóa, không force-kill tiến trình. Repair/upgrade vẫn giữ data, hỏi trước khi tiếp tục, rồi chỉ dọn file cũ có trong manifest.
- `Updates` cạnh Setup vẫn là local Owner-preview feed, không phải public update channel. Setup ghi các field `github_owner`/`github_repository`; publisher chỉ nhúng identity khi cả `-GitHubOwner` và `-GitHubRepository` được cung cấp tường minh. Cả hai mặc định trống, không có identity hard-code; thiếu identity thì GitHub check là `Unconfigured` và không gửi request.
- Public WPF updater chỉ đọc GitHub Releases bằng HTTPS GET, không token. Chỉ stable semantic-version tags được xét; draft/prerelease bị bỏ qua và phiên bản được sắp theo thứ tự số. Chỉ asset đúng `wpf-update-{version}-{sha256[:16]}.zip`, URL của repository đã cấu hình trên host GitHub HTTPS tin cậy, cùng asset digest `sha256:<64 hex>` mới được tải. Redirect asset chỉ theo HTTPS hosts GitHub allowlist. Status phân biệt unconfigured, current, WPF update available, Setup required, invalid metadata/package, offline, timeout và rate limit.
- Quyết định sản phẩm của Owner: `v0.1` là bản công khai đầu tiên và là baseline để phát triển tiếp. Mục tiêu là người dùng cài Setup một lần rồi nhận các phiên bản sau an toàn trong app, kể cả thay WPF, Python worker, dependency và runtime. Khả năng chuyển tiếp của **bản cài v0.1 đã phát hành** phải được chứng minh từ Setup/payload và hành vi cài đặt thực trước khi hứa mục tiêu này cho người dùng v0.1; nếu bản đó không thể nhận gói chuyển tiếp thì cần quyết định sản phẩm mới của Owner. Thay đổi installer/uninstaller hoặc quyền hệ thống vốn không thể thay bằng updater trong app vẫn cần Setup. Chưa có acceptance bản cài thực tế thì không gọi cập nhật toàn app là sẵn sàng.
- Quyết định Owner cho 0.1.2: người còn ở bản public v0.1 dùng Setup 0.1.2;
  full-app update bắt đầu từ baseline mới. Không hứa cài Setup một lần cho người
  còn ở v0.1. Binary v0.1 chỉ chọn stable mới nhất và WPF asset khớp tag; khi
  stable mới nhất thiếu asset phù hợp, nó trả SetupRequired, không tự đi qua
  bridge cũ hơn. Publisher được phép build Setup/candidate không kèm gói WPF
  version cao hơn; package được yêu cầu vẫn phải qua đầy đủ integrity/baseline.
  Mọi acceptance transaction bằng helper mới trên payload v0.1 phải nêu rõ đây
  không phải nút update của binary v0.1. Stable GitHub acceptance trên bản cài 0.1.2 đã PASS trong bounded scope; toàn product vẫn chưa RELEASE_VERIFIED.
- Quyết định Owner (2026-10-04, Brain turn01a106e6): chọn **0.1.3** cho update stable thực từ Setup0.1.2; được sửa version/source/test/publisher cần thiết, commit/push/build/package và publish sau mandatory gates cùng Brain review. Không promote test-only0.1.3 f314a52, không đổi installer/uninstaller/framework/native runtime trong task này. Offer/apply/restart stable GitHub trên bản cài Owner đã PASS trong bounded scope; báo cáo này không nâng thành RELEASE_VERIFIED.
- WPF compatibility package giữ allowlist ba file `VNText Studio.exe`, `app/RELEASE.json`, `app/VERSION.txt`; asset SHA-256, manifest, semantic version, executable metadata, baseline và từng file hash phải khớp. WPF package cũ vẫn hoạt động cho release tương ứng; thiếu package áp dụng được dẫn tới official Releases/Setup route, không auto-run Setup.
- Full-app package được discovery theo stable GitHub release và asset chính xác `full-app-update-{version}-{sha256[:16]}.zip`; một release chỉ được có đúng một update asset WPF hoặc full-app phù hợp version. Repository/tag/HTTPS host, GitHub API size, tải thực tế, digest, manifest và package size đều phải được kiểm. Manifest gắn source commit SHA-1 và source tree fingerprint SHA-256 (`SHA256("git-tree-sha1:" + Git tree object ID)`), khớp metadata trong `app/RELEASE.json`; đây là provenance metadata, không phải chữ ký mật mã. Delta chỉ được áp dụng khi inventory/hash của toàn bộ `VNText Studio.exe` + `app/**` đúng baseline đã package, manifest add/replace/delete nhất quán và ZIP chứa đúng entry. Từ chối reparse/symlink, path traversal, trùng tên case-insensitive, file ngoài inventory, protected app data, package tamper, sai version/provenance hoặc baseline mismatch.
- Full-app staging, backup, journal, log và worker/updater helper ở install root, ngoài `data/`; package nén tối đa 512 MiB và expanded inventory tối đa 3 GiB/20.000 file. Chỉ thay executable và `app/**`; `app/worker/models/**` phải giữ nguyên hash/tập file theo baseline. App và worker dừng bình thường trước khi apply. Sau apply kiểm inventory, `RELEASE.json`, `VERSION.txt`, executable version/hash, app health và worker readiness; restart thành công mới commit journal. Health/restart failure hoặc gián đoạn phải rollback/khôi phục từ backup đã hash-verify. `data/`, game, model/cache người dùng và output không là update targets; file lạ dưới `app/` làm baseline mismatch.
- Full-app updater ghi danh sách file sở hữu tại `.update/owned-files.json`; Setup được build từ source hiện tại merge sidecar vào `data/install-manifest.json` để repair/upgrade kế tiếp nhận biết file được thêm. Setup v0.1 đã phát hành là binary cũ, không được sửa bởi source update và thay đổi `Setup.exe`, `Uninstall.exe` hoặc quyền hệ thống vẫn cần Setup mới. Stable GitHub offer/apply/restart từ baseline 0.1.2 đã PASS trong bounded installed-app acceptance; các gate ngoài phạm vi đó vẫn không được suy ra PASS.
- Release không phụ thuộc Python hệ thống; `app/worker/.venv/pyvenv.cfg` trỏ bundled `app/worker/python`. Verify/smoke chạy trên staging trước khi đóng gói Setup. Publisher chỉ thay ReleaseRoot sau khi payload archive/hash và copied Setup hash hợp lệ.
- Release app thực thi CPython bundled trực tiếp với `PYTHONHOME` bên trong
  `app/worker/python`, `PYTHONPATH` chỉ tới dependency `.venv/Lib/site-packages`,
  tắt user-site/bytecode. Worker, verify, CSV editor, patch preflight và health
  check không rewrite `pyvenv.cfg` hoặc file app khi relocation/khởi chạy;
  inventory/hash baseline vẫn kiểm nguyên byte, không normalize hay bỏ file.
- Version lấy từ `VERSION.txt`/`app_backend.VERSION`; publisher báo source SHA, Setup SHA256/size và payload file/byte count.

**Owner decision (2026-10-24, public release assets and notes):** Every public stable VNText release includes a version-matched Setup named `VNTextStudio-<version>-Setup.exe` and the full-app updater package or packages required by the supported baseline routes in this contract. The GitHub release body is Vietnamese and gives a concise, user-facing account of product features, UI changes and fixes delivered in that version. Keep test results, hashes, gate status, internal history, and instructions for working around or reusing an older Setup out of the release body. Keep technical provenance and acceptance evidence in their dedicated records/assets, and retain applicable license notices and legal materials. Release notes must not imply acceptance beyond the evidence for the stated behavior.

**Tests/evidence:** `tests/unit/test_setup_package.py`, `test_runtime_paths.py`, `test_wpf_workflow.py`; `release/package_installer.py`, `release/publish.ps1`, `release/publish_owner_wpf_update.py`, `vntext/release_verify.py`. The package test runs the generated final PowerShell helper on a fixture and verifies that `Uninstall.exe` and every descendant are gone while the regular install root remains empty. Setup UI, selected-folder install, real whole-folder-content uninstall and button-driven A→B update require installed-app verification; do not infer them from package tests alone.

## 10a. Test artifact retention and cleanup lifecycle

Canonical topic: [10a. Test artifact retention and cleanup lifecycle](docs/contracts/artifact-retention.md). Preserved authority/history, origin SHA and scoped decisions live there; this router grants no new permission.

## 10b. Prospective artifact-registry epoch

Canonical topic: [10b. Prospective artifact-registry epoch](docs/contracts/registry-epoch.md). Preserved authority/history, origin SHA and scoped decisions live there; this router grants no new permission.

## TEST GAP đã biết

- Không có test tự động riêng mô phỏng double-click UI thật; WPF harness/build và Release smoke không thay thế hoàn toàn kiểm tra pixel/click thủ công.
- Chưa có active Ren’Py full-game E2E trong runtime test matrix; native unit/read-back/delivery coverage không thay thế exact external game và Release evidence.
- `app.py` giữ QML branch chỉ cho explicit legacy selection và gọi `qml_ui.bridge`, nhưng source public hiện không có `qml_ui.bridge` hoặc `qml_ui/icons/logo.png`; QML-ready path là UNKNOWN cho tới khi bridge tồn tại và `--release-verify-qml` PASS. Shipped/default UI là WPF.
- Worker tests còn `ResourceWarning` liên quan pipe/process theo AI_STATE; không tự sửa trong context task.


## 10c. DEV validation và chiến dịch game

Canonical topic: [10c. DEV validation và chiến dịch game](docs/contracts/dev-validation.md). Preserved authority/history, origin SHA and scoped decisions live there; this router grants no new permission.
