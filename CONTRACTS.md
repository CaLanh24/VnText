# VNText Studio — Contracts Spine

Mỗi mục ghi `Owner`, invariant phải giữ và bằng chứng hiện có. Đây là contract kỹ thuật đã quan sát được; không mở rộng behavior ngoài source/test.

## 1. Entry, key, CSV và package

**Owner:** `vntext/entry.py::make_key`, `Entry.finalize`, `Entry.to_csv_row`, `Entry.to_manifest`; `vntext/package_io.py`.

**Invariant:**

- Key là SHA-1 16 ký tự đầu của UTF-8/surrogatepass cho chuỗi `file_path + "\n" + context + "\n" + method + "\n" + text`.
- `Entry.finalize()` chỉ tạo key khi key đang rỗng; không ghi đè key đã có.
- `CSV_FIELDS` và thứ tự hiện tại là cố định: `key`, `source_text`, `translation`, `context`, `file_path`, `object_info`, `import_method`, `safety`, `backend`, `byte_limit`, `patch_note`.
- CSV dùng `utf-8-sig`, `newline=""`; đọc giữ field cũ, bổ sung field bắt buộc còn thiếu; ghi giữ thứ tự field đầu vào rồi append field bắt buộc thiếu.
- `translation.csv` là main patch workflow. `review_only.csv`, `raw_candidates.csv`, `raw_unpatchable.csv`, `technical_skipped.csv` là các ledger/phân loại riêng theo `write_package`.
- `manifest.json` format hiện tại là `2`, có `tool`, `version`, `entries`, `technical_skipped`, `stats`; entry giữ locator, import method, backend, review state và duplicate locations.
- Không đổi thứ tự row, key, field name, locator hoặc cách phân tách main/review/raw nếu chưa có migration và golden evidence.

**Tests/evidence:** `tests/unit/test_characterization_key.py`, `test_characterization_package_split.py`, `test_csv_editor_api.py`, `test_golden_artifacts.py`, `test_refactor_contract_baseline.py`, `tests/golden/refactor_contract_baseline.json`.

### CSV editor write boundary
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
- Missing Ren'Py SDK recovery offers an installed SDK picker, pinned SDK download, cancel through the active task, retry through Extract, and explicit continue-with-review behavior. Unsupported extraction stays incomplete; no loose-parser fallback is permitted.

**Tests/evidence:** `tests/unit/test_wpf_workflow.py`, `test_ui_app_workflow.py`, `test_qt_app_workflow.py`, `test_legacy_ui_task_contract.py`, `test_ui_progress.py`; WPF workflow harness trong `wpf_app/VNText.Studio.Workflow.Tests/Program.cs`.

**Owner UX decision for update 0.1.11 (2026-10-24):** Text extraction defaults to exhaustive/deep mode; prior persisted Clean/Balanced values do not override this default and the normal extraction page does not expose a mode chooser. This does not change eligibility, review classification, locator, or patch validation. A structurally valid generated `translation.csv` with blank translation cells is ready to start local CT2 translation; Patch readiness still requires actual translations and all existing gates. Progress ETA is advisory seconds/minutes/hours and malformed/unknown values are omitted in favor of an estimating status. Engine analysis must report only evidence-backed detection and explicitly retain unknown/mixed states; Unity analyzer output alone does not classify other engines. Application confirmations/errors use themed WPF dialogs with cancel-safe results; native pickers/consent prompts stay native. CSV controls remain expandable and unclipped, and SDK failure status offers a clear retry/choose path without parser fallback.

## 7. Patch, UnityFS và Addressables

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

**Owner coordination decision (2026-10-21):** DEV records progress, candidate and terminal reports only in its own session. Brain actively reads that session and sends only necessary reviewed decisions/remediation; DEV does not message Brain back. This supersedes earlier report-back requests; no separate commit is needed solely for this rule.

**Owner role clarification (2026-10-23, bounded RenPy acceptance):** Owner → Brain for coordination, progress/evidence review, acceptance and task assignment → DEV as sole implementation Coordinator/writer. Brain does not edit the repository concurrently. DEV reports in its own chat for direct Brain review; this adds no child, parallel writer or reverse-message authority. The role clarification does not authorize another native trial beyond the currently bounded run11.


**Owner approval (2026-10-21, Release0.1.9):** “Cho phép 3 GiB cho Release 0.1.9”. Temporary3GiB total non-exempt checkout artifacts only for exact registered `RELEASE_RUN/candidate-0.1.9`, independent clean0.1.9 prospective epoch and `VNTEXT_RELEASE_TASK_ID=release-0.1.9`. Terminal scope cleanup returns to<=1GiB; shared `.dev-env` stays<=6GiB. Inventory/project each phase; preserve historical/user data. Descendant clean-source prerequisite fixes within this campaign retain same-version lineage/CAS/tamper/eight-hop guards. No rebaseline, validator relaxation, research resume or model promotion.

**Owner approval (2026-10-23, Release0.1.10):** Owner replied “Cho phép 3 GiB cho release 0.1.10” to the bounded request for one registered candidate/test scope, terminal return to<=1GiB, shared `.dev-env`<=6GiB, and no history/user-data deletion. This grants **3 GiB total non-exempt checkout usage (3,221,225,472 bytes) only** for exact registered `RELEASE_RUN/candidate-0.1.10`, with `VNTEXT_RELEASE_TASK_ID=release-0.1.10` and an independent clean0.1.10 prospective epoch preserving the existing epoch/manifest lineage. It does not reuse the 0.1.9 approval or its epoch; no rebaseline, history/user-data deletion, shared-cap increase, package/update validator change or model promotion follows. Inventory the whole checkout and shared `.dev-env` before every allocation phase and preserve a measured reserve; stop before the 3 GiB limit. Dispose only this exact registered task scope after all owned processes exit, return non-exempt usage to<=1GiB, and keep `.dev-env`<=6GiB.

**Owner approval (2026-10-24, Release0.1.11):** Owner replied “Cho phép 3 GiB cho release 0.1.11” for the exact registered `RELEASE_RUN/candidate-0.1.11` candidate/test scope. This grants **3 GiB total non-exempt checkout usage (3,221,225,472 bytes) only** for 0.1.11, with `VNTEXT_RELEASE_TASK_ID=release-0.1.11` and an independent clean0.1.11 prospective epoch preserving the existing epoch/manifest lineage. Shared `.dev-env` remains capped at 6 GiB, and after terminal cleanup non-exempt usage returns to<=1GiB. Inventory the whole checkout and `.dev-env` before each allocation phase and preserve a measured reserve. Do not reuse another release's budget/epoch, delete history or user data, increase shared cache limits, or relax package/update validators. This approval authorizes only the bounded storage budget; all source, candidate, cleanup, and release gates remain required.


**Owner decision (2026-10-19, low-memory alternative):** Host has no spare RAM; keep VM4GiB. Owner authorizes identifying/closing unused applications and researching/executing a bounded alternate trial. No blind service termination or security disabling. Same pinned model/runtime, existing pagefile only, no downloads/system changes. Replace the earlier conservative file-size-plus512MiB guard for this test with measured mmap trial safeguards in the translation plan; do not infer quality or deployability from startup.

**Owner decision (2026-10-19, model-trial RAM):** Owner authorizes increasing RAM of the development VM sufficiently for the already approved single-model test and continuing the experiment. Inspect host available memory before choosing allocation; preserve work before any required shutdown. This supersedes the earlier no-VM-RAM-change boundary for this operation only. No host credentials/access are implied, and no security/firewall/service changes, unrelated VM changes, new model or product replacement are authorized.

**Owner decision (2026-10-19, translation-quality Step3):** Explicit permission to download the pinned Tencent Hy-MT2-1.8B Q4_K_M model and official portable Windows CPU runtime into shared `.dev-env`, increasing its current cap to **6 GiB** (supersedes the previous5GiB cap). Non-exempt checkout remains1GiB. One model/runtime copy, verified hashes and license provenance; test-only, OPUS product route unchanged. Check guest RAM before loading; no host/VM changes, training, additional candidates, system installation or publication authorized.

**Owner decision (2026-10-18, Release0.1.6):** Owner explicitly approves `.dev-env` up to **5 GiB** for the shared build environment (SDK10, Python3.12 and Release packages alongside current DEV). This supersedes older3GiB shared-environment limits below. The non-exempt checkout limit remains1GiB; no game/candidate exemption, package limit, cleanup ownership or validator changes follow. Inventory both totals before each payload phase.

**Additional Owner approval (2026-10-18):** Release0.1.6 may temporarily use3GiB non-exempt artifacts for the exact registered `RELEASE_RUN/candidate-0.1.6` scope, bound to a new clean-source0.1.6 prospective epoch and explicit `VNTEXT_RELEASE_TASK_ID=release-0.1.6`. Same exact-source/inventory/ownership guards as0.1.5, with its own approval; no old transition/rebaseline approval inherited. Terminal scope disposal returns non-exempt total to<=1GiB. Shared `.dev-env` stays separately<=5GiB. No package/update validator relaxation.

Within this same authorized release campaign, prerequisite/gate fixes may produce a descendant clean0.1.6 source. Its new prospective epoch must preserve the prior epoch/manifest, prove lineage and unchanged version, use the independent0.1.6 approval and retain the ordinary eight-hop/CAS/writer/tamper guards. No rebaseline or history deletion is authorized. Test temporary path components may be compact hashes; registry IDs, purposes, scope/run identity and cleanup boundaries retain full values.

**Owner:** `tests/lib/work_paths.py`, `tests/tools/cleanup_work_artifacts.py`, `tests/tools/run_with_cleanup.py`, `release/run_regression.ps1`.

**Owner decision (2026-10-15, Release 0.1.5 continuation):** Owner approved the bounded Windows `ERROR_UNABLE_TO_REMOVE_REPLACED` updater remediation, one no-delete evidence rebaseline preserving all prior epoch history, and one use of Setup for people on 0.1.4 (direct approval reply `call_4a31e293dabe487a98c54c4cdf706a07`). The normal 0.1.5 epoch chain remains capped at eight ancestor hops. This one explicit rebaseline records the approval and prior anchor, verifies the complete old chain, and preserves all prior records/files; a later rebaseline needs a new Owner approval. The update claim is Setup-only; no full-app ZIP or in-app update claim follows. Intel Setup terms/UI remain `NOT VERIFIED` until a human accepts them.

**Public-clone rule:** This section is canonical for current artifact lifecycle
and cleanup. A fresh checkout has no private registry/epoch or its historical
evidence; do not import or reconstruct them. Assess only the current checkout's
registered artifacts, and do not infer current cleanup or Release PASS from
unavailable historical reports.

**Invariant:**

- Every artifact under `TEST_RUN` is classified as `PROTECTED`, `RETAINED`, `DISPOSABLE`, `UNKNOWN`, `MISSING` or `STALE`, and registered with a non-empty owner and purpose. `artifacts_manifest.json` is the only registry; `cleanup_manifest.json` is a run report.
- **Feature lifecycle:** one task may use one `.dev-env`, one current `DEV_RUN` build and one disposable `TEST_RUN`. Focused tests stream a bounded summary (maximum 10 MiB) before terminal cleanup; the final bounded Markdown receipt lives under `DEV_RUN/runner-reports`, outside the transient root. After `PASS`, `FAIL`, `TIMEOUT`, `START_ERROR` or `CANCELLED`, `TEST_RUN` must be absent/empty unless the task explicitly sets `OWNER_TEST_PENDING=1`. If a verified prospective epoch already owns retained control-plane/release evidence, a wrapper may preserve only the verified epoch files/registry, unchanged registered release-gate evidence, append-only cleanup history, empty registered `tmp` containers, and previously registered canonical runner receipts whose path, owner, purpose, size and content hash verify; all payload, changed/unrecognized paths, incomplete inventory, or non-RETAINED lifecycle still forces `REVIEW_REQUIRED`. This exception does not make a failed test pass. Game copies, transient logs and caches remain disposable. A new task cannot start while a prior transient root is non-terminal or unknown.
- **Release lifecycle:** `RELEASE_RUN` is created only for an explicit Release task and may retain one baseline/candidate/evidence scope until acceptance. After publication and acceptance, retain only the compact canonical receipt; dispose payload copies and staging. Release evidence does not authorize a second environment or a persistent `TEST_RUN`.
- `TEST_RUN/game-copy` is protected from generic cleanup but is a temporary test copy, never a retained fixture/baseline. For every game-test outcome, first save needed reports/logs outside the copy and ensure the test process has exited. The canonical copy uses `dispose_e2e_game_copy`; a scoped copy must be registered at its exact root as `kind=test_game_copy`, `lifecycle=DISPOSABLE` and passed to `cleanup_after_test(..., disposable_paths=[copy])` with the actual test outcome. Both routes record terminal `MISSING`. Canonical non-game fixtures, user/game paths, models, baselines and retained evidence remain protected. Cleanup targets must stay under `TEST_RUN`; outside/protected paths are rejected and no process is killed to make deletion possible.
- An ACTIVE legacy entry whose path is absent becomes `MISSING`/`STALE`; an existing root without a registry entry becomes `UNKNOWN` unless an explicit protected/retained path rule covers it. Neither case is silently dropped or deleted.
- `--dry-run` performs no `TEST_RUN`, registry or evidence write; only an explicitly requested `--output` outside `TEST_RUN` may be written. Generic cleanup deletes only registered `DISPOSABLE` artifacts (plus the explicit audited migration allowlist). After `PASS`, `FAIL`, `TIMEOUT`, `START_ERROR` or `CANCELLED`, the runner streams the exact outcome/exit/command/test summary/error and bounded stdout/stderr excerpts, then disposes terminal `TEST_RUN` content. Raw logs and heavy disposable payload are not retained for debugging. If the child remains alive, do not finalize or claim cleanup success; report its PID and `REVIEW_REQUIRED`. Test verdict and cleanup status remain separate.
- Both dry-run and apply must block a deletion root when any live non-`DISPOSABLE` registry entry claims that root or a descendant; malformed claims fail closed. Dry-run reports the blocker, never a planned deletion; apply rechecks the same ownership guard immediately before removal. `PROTECTED`, `RETAINED`, `UNKNOWN`, `STALE`, external/user paths and descendants claimed by those entries remain untouched.
- Registry reads used for updates reject linked/nonregular files, unreadable or malformed JSON, non-object roots and invalid `artifacts`/`archive` container shapes. Reconciliation never rewrites malformed registry metadata; cleanup remains `REVIEW_REQUIRED` until it is resolved.
- Every canonical run carries `scope_id`, `run_id`, `scope_root` and provenance, captures before/after inventory, and finalizes lifecycle in `finally`. New or modified paths outside the current scope registration are UNKNOWN/review-required. Cleanup status and before/after/deleted/retained/protected/unknown/locked data are evidence; cleanup failure cannot be hidden behind a child test PASS.
- Validation that mutates the shared artifact registry or `TEST_RUN` is strictly sequential. Await the entire canonical wrapper's terminal state, complete cleanup, and persist its receipt before starting another run or dependent phase. Child process exit alone is insufficient; canonical wrappers must never overlap, including during reconciliation. If overlap creates UNKNOWN records, prove exact ownership from primary run receipts before canonical API reconciliation and cleanup; never delete UNKNOWN paths blindly. Preserve failed receipts separately.
- New cleanup reports use schema 4 for scoped runs and schema 3 for whole-work cleanup. Repeated inventory path maps are omitted from reports and represented by count plus deterministic SHA-256; lifecycle lists over 100 records retain a 100-record sample plus full count/hash. The canonical manifest remains the full record source, and historical reports are not rewritten.
- Runner-owned records use a stable ID derived from normalized physical path and related tree registrations are batched, so repeated runs update the same current record instead of adding one copy per `scope_id`/`run_id`. Existing historical entries are preserved; this does not reconcile or reclassify prior UNKNOWN/MISSING records.
- Deletion requires a complete inventory, a registered `DISPOSABLE` target, no active process using it, and no live non-disposable claim. Unknown or unproven paths stay untouched until ownership is resolved; they are reported with path/size and cannot be silently kept as an unlimited retention exception. Each cleanup reports before/after size and exact deletion/retention outcomes. Project-size inventory fails closed on links/reparse points, special files, stat/scandir errors or budget limits.
- Owner decision (2026-10-04): keep project-managed DEV environments, artifacts, baselines and evidence inside the DEV checkout; do not create an external archive or move them outside to satisfy the size gate. A cleanup `PASS` requires a complete inventory of the entire checkout, at most **1 GiB of non-exempt files**, and `.dev-env` at most **3 GiB**. Report both totals and each exact exemption root/reason. The only shared environment root is `.dev-env`; `DEV_RUN` is one current build, `TEST_RUN` is disposable test runtime, and `RELEASE_RUN` exists only for an explicit Release task. Consolidate reusable environments; duplicate snapshots, payload copies and obsolete fixtures are not exemptions. No blanket exemption for `DEV_RUN`, `TEST_RUN` or `.scratch`.
- Owner authorization (2026-10-14, Release 0.1.5): Owner confirmed “Ok” to one prospective epoch from the final clean 0.1.5 source and a temporary ceiling of **3 GiB total non-exempt files for the entire checkout**, inclusive of existing bytes, for candidate/test 0.1.5 only. `.dev-env` remains separately capped at 3 GiB. Inventory and project each phase before it starts; stop before the total cap can be exceeded. At terminal teardown, dispose only the exact registered 0.1.5 task scope and require the default **1 GiB** project limit again. Old payloads and user data are not deletion targets. This authorization does not exempt paths, change package/update validators, or increase limits for another task. The helper requires an active epoch carrying this exact approval, matching clean source SHA/version, the exact `RELEASE_RUN/candidate-0.1.5` `DISPOSABLE` registration, and explicit `VNTEXT_RELEASE_TASK_ID=release-0.1.5`; otherwise the 1 GiB limit applies. Once that registered scope is terminal `MISSING` and absent, the profile returns to 1 GiB.
- Cleanup is test/tooling infrastructure and must not change translation semantics, worker NDJSON, WPF product behavior or engine/game behavior.

Historical baselines and incident snapshots are not current exemptions or clone
prerequisites. A Release task may register one owned baseline/candidate scope in
`RELEASE_RUN` until acceptance; after acceptance only the compact receipt remains.
Nested snapshots under `.scratch` or `TEST_RUN` inventory the containing main
checkout for quota; deletion and artifact ownership stay in the local run scope.
The exact Release 0.1.5 source snapshot under `RELEASE_RUN/candidate-0.1.5/source` also inventories the entire containing checkout. Its opt-in budget is read from the parent's canonical helper in an isolated process: exact containment, matching clean snapshot/parent SHA, verified parent active epoch and exact task registration, and unchanged full parent manifest bytes are required. No local epoch, copied environment, arbitrary environment path or local-only inventory can grant the parent budget. Registry updates and deletion stay local to the test scope. Regression child imports bind `tests` to the current repository test tree before discovery so dependency packages cannot shadow it; shared model/environment paths remain explicit child inputs. Mocked download tests isolate their no-download flag inside the mocked call only.
The canonical wrapper blocks child/payload creation when quota inventory is
incomplete or the active task cap is exceeded; it may write a bounded failure receipt.
For the authorized 0.1.5 task, register the exact candidate scope after applying
the matching prospective epoch, then invoke the canonical wrapper with
`--release-task-id release-0.1.5`. The exception raises only the total project
non-exempt limit; every path remains counted and registry ownership rules remain
unchanged. Finalize the exact candidate scope only after all children exit and
evidence is compacted; final inventory must pass at 1 GiB.

**Tests/evidence:** `tests/unit/test_cleanup_work_artifacts.py`, `test_artifact_write_policy.py`, `test_work_paths.py`, `test_release_regression_runner.py`; `tests/tools/run_with_cleanup.py`; terminal summary is streamed and `TEST_RUN` is absent/empty after feature runs.

## 10b. Prospective artifact-registry epoch

`tests/tools/cleanup_work_artifacts.py` owns the additive prospective epoch transition. `--prospective-epoch-plan` and `--verify-prospective-epoch` are read-only; `--apply-prospective-epoch` may write only a retained epoch scope and the canonical manifest metadata. Apply is fail-closed on a dirty tree, source SHA mismatch, active writer marker, incomplete/budget-limited inventory, invalid schema/provenance, missing or mismatched rollback snapshot, or conflicting active epoch. It never deletes artifacts.

The only active-epoch transition exception is the explicit Owner-authorized Release 0.1.5 path: `--prospective-epoch-transition-plan` / `--apply-prospective-epoch-transition` requires `--release-task-id release-0.1.5`, the exact active epoch ID, its current full-manifest SHA-256, a new epoch ID, the final clean source SHA, and the recorded Owner authorization. It verifies the old epoch files, 0.1.5 version and ancestor relationship; any stale manifest hash, old epoch corruption, writer/pending marker, incomplete inventory, different version, or non-descendant source blocks. The new epoch snapshots the exact previous manifest, retains all prior registry records and epoch files, records both source identities, and rolls back only its own new scope if activation verification fails. Existing active epochs are never silently reused for a new SHA; generic epoch creation still refuses a conflicting active epoch. Later cleanup may change ordinary run records or archive terminal records; verification protects the immutable prior epoch records/files and snapshot hashes without requiring the entire live registry to remain byte-identical forever. A competing manifest change during the transaction is never overwritten; its pending scope is preserved for explicit reconciliation.

The explicit 0.1.5 transition may continue a verified transition chain, with at most eight strict source-ancestor hops. Each hop requires the exact current epoch ID and full-manifest hash CAS, clean target source and version 0.1.5. Verification traverses immutable rollback snapshots with cycle/depth guards, validates every prior policy/ledger/rollback and preserves all prior epoch registry records. A ninth hop, repeated epoch identity, corrupt ancestor, equal source SHA, stale CAS, writer/pending marker or incomplete inventory refuses without deletion. Generic conflicting active epochs still refuse. This bounded continuation does not reconstruct historical incident hygiene (`NOT_RECOVERABLE/UNVERIFIABLE`).

The single Owner-approved 2026-10-15 rebaseline is a separate no-delete CLI/API route, with a distinct approval ID and statement recorded in provenance. It requires the exact live active epoch ID and full-manifest SHA-256 CAS, a clean strict-descendant 0.1.5 source, full verification of the active epoch/history, complete bounded inventory, and no writer/pending marker. It snapshots the exact current manifest, preserves every prior artifact/archive record and epoch file, and activates by pending/active manifest writes with compare-before-restore rollback limited to its own new scope. Its verifier checks the prior anchor against the recorded rollback manifest and re-verifies the entire former chain, including old policy/ledger/rollback hashes; the rebaseline boundary resets only the hop counter while retaining cycle detection across the boundary. Ordinary transitions keep the eight-hop guard. The approval is single-use across later ordinary transitions; another rebaseline requires new Owner approval. It does not repair historical hygiene or claim deletion/cleanup success.

For the Owner-authorized 0.1.5 task only, `--apply-prospective-epoch --release-task-id release-0.1.5` records the fixed 3 GiB whole-checkout limit,
exact source SHA/version, exact candidate scope and approval statement inside
the epoch policy. `--register-release-task-scope` registers that scope as the
single `DISPOSABLE` owner `release-0.1.5`; it creates no payload. Runtime use
requires the explicit task ID, exact active registration and a clean matching
source. Invalid/incomplete epoch or registry data fails closed. Missing or
terminal scope falls back to the default 1 GiB limit. The `.dev-env` cap stays
3 GiB, no path is excluded from project totals, and update package/expanded-file
validators are unchanged. The budget is not copied into another epoch or task.

Each active epoch retains an exact pre-transition manifest rollback snapshot, policy, rollback metadata and a current filesystem ledger under `TEST_RUN/artifact-registry-epochs/<epoch-id>/`. The ledger is prospective only: registered evidence keeps its lifecycle, current unproven paths remain `UNKNOWN`, and preserved historical data is distinct from the rollback snapshot and new ledger. Private historical registries or reports are not present in a public clone, are not clone prerequisites, and cannot establish current cleanup or Release acceptance. Assess a new checkout and each release from its own evidence; do not infer historical PASS.

Mỗi public clone mới bắt đầu mà không có artifact epoch của checkout riêng
trước đó. Không nhập/tái tạo incident registry riêng, không tái dùng timestamp,
hash hay report lịch sử, và không yêu cầu tìm artifact private làm điều kiện
cho clone mới. Khi incident-preservation history vắng, caller có thể dùng
`--fresh-public-clone` để khởi tạo epoch bằng evidence hiện tại. Provenance phải
ghi `FRESH_PUBLIC_CLONE_NO_PRIVATE_HISTORY`, historical hygiene `UNKNOWN`,
incident identity `MISSING`, và không có reset/owner-reset claim. Đây chỉ ghi
nhận absence; không chứng minh history đã được khôi phục, cleanup PASS hay
incident đã được giải quyết. Chỉ đăng ký evidence của checkout hiện tại theo
canonical tool. Registry hiện tại nếu có vẫn phải là regular file đọc được và
đúng schema; state malformed, partial, linked hoặc unreadable phải block.
Active epoch, writer/pending transaction, incomplete inventory, hoặc current
`UNKNOWN` paths cũng block. Nếu manifest hiện tại tồn tại, giữ snapshot rollback
nguyên byte cùng SHA-256 và size; nếu không có thì snapshot ghi nhận trạng thái
absent. Preflight race không được xóa lock của writer khác. Không apply epoch
live trước khi source được commit sạch; test chỉ apply/rollback trong disposable
fixture. `--owner-reset-authorization` vẫn là route riêng cho reset có Owner
ủy quyền thực sự; fresh-clone mode không thay thế hoặc hạ thấp các guard đó.

### Prospective portable Release acceptance

Release verification reads the single `home` field in shipped `pyvenv.cfg`.
It must equal the bundled `worker/python` absolute path or the publisher's
exact token `__VNText_INSTALL_ROOT__\app\worker\python`; duplicate home fields,
relative paths, altered tokens and unrelated absolute paths are rejected.
The token is immutable inventory metadata: Release workers execute bundled
CPython with the pinned `PYTHONHOME`/site-packages environment, without
rewriting the configuration after installation or update.

This tracked acceptance contract applies to a portable RC with a new prospective
evidence epoch created from the current public checkout. It does not depend on a
private epoch or incident registry; the current initialization statement described above is still required by the helper. Historical private evidence
is unavailable and is not reconstructed or counted as current PASS/FAIL.
`RELEASE_VERIFIED` for this bounded portable scope requires all of the following
primary evidence tied to one clean final source SHA:

- Read-only verification of the **new** epoch's identity, schema, policy,
  rollback snapshot and ledger hashes succeeds. The canonical live registry
  and new epoch files are byte-identical before and after release gates,
  except a separately proven contract mutation. The deleted incident registry
  is disclosed as unavailable, never treated as a successful hash check.
- Full canonical unit regression and scoped cleanup pass in an exact-commit disposable project snapshot. The child and wrapper exit 0; raw output proves totals, failures, errors, skips and warnings. Every skip is explained. Each gate's inventory is complete, cleanup is `ok=true`, and current-scope `UNKNOWN`, `LOCKED`, `STALE` and unexpected `MISSING` are zero. Expected `MISSING` requires registration and deletion provenance.
- WPF build and worker smoke, installer restore/build/tests, portable publish/layout, `--release-verify`, Release worker smoke from Release cwd and an independent cwd, and the real RC GUI launch/close/worker-reap test pass with retained commands, raw outputs, exit codes and cleanup reports. Mandatory failures cannot be relabeled as skips.
- `RELEASE.json` source SHA, version, executable and installer hashes match the final commit and retained inventory. The RC is new, outside the tracked repository, free of forbidden source/test/cache/debug artifacts, and its payload/tree manifest and key SHA256 values are retained. No source change follows the exact-final regression; otherwise commit and rerun the affected acceptance gates on a new RC.

Historical private registry counts, incident records and cleanup evidence are not distributed with the public source and are not required to use or test a fresh clone. Their absence is not evidence of cleanup PASS or FAIL for this clone. Keep prospective cleanup verification scoped to evidence created and registered in the current checkout; preserve the separate UNKNOWN/unverified outcome for any unavailable history.

Owner explicitly defers real-game E2E and defects found there to a later version. Visual/pixel interaction, full-game support and semantic translation quality remain `NOT VERIFIED`; no such capability is implied by portable `RELEASE_VERIFIED`. External publishing requires separate authorization.

**Tests/evidence:** `tests/unit/test_cleanup_work_artifacts.py` prospective plan/apply/refusal/idempotency/hash/unknown tests, explicit 0.1.5 transition success/preservation/refusal/rollback and post-run lifecycle verification, affected work-path and artifact-write suites, epoch scope policy/ledger and rollback hashes under `_work`.

## TEST GAP đã biết

- Không có test tự động riêng mô phỏng double-click UI thật; WPF harness/build và Release smoke không thay thế hoàn toàn kiểm tra pixel/click thủ công.
- Chưa có active Ren’Py full-game E2E trong runtime test matrix; native unit/read-back/delivery coverage không thay thế exact external game và Release evidence.
- `app.py` giữ QML branch chỉ cho explicit legacy selection và gọi `qml_ui.bridge`, nhưng source public hiện không có `qml_ui.bridge` hoặc `qml_ui/icons/logo.png`; QML-ready path là UNKNOWN cho tới khi bridge tồn tại và `--release-verify-qml` PASS. Shipped/default UI là WPF.
- Worker tests còn `ResourceWarning` liên quan pipe/process theo AI_STATE; không tự sửa trong context task.


## 10c. DEV validation và chiến dịch game

Owner: `release/dev_bootstrap.py`, `tests/lib/worker_test_lib.py`; validation gates ở `TEST_MATRIX.md`, cách khởi chạy DEV ở `docs/DEVELOPMENT.md`.

Trước run, ghi scope/source SHA, thứ tự gate, số lượt và copy budget, executable path/hash/source/build config, runtime/worker/model thực, ownership/process/disposal và nơi giữ evidence nhỏ. Preflight phải read-only và đủ quota/prerequisite trước tạo payload. Version trùng không chứng minh binary cùng source.

Owner approval (2026-10-10, Brain turn01a12193 / human reply01a12194): tải SDK Ren'Py8.5.3 chính thức, kiểm archive hash và expanded/peak inventory trước cài vào `.dev-env/tools/renpy-8.5.3`; toàn `.dev-env` vẫn ≤3GiB. Ngoại lệ tạm chỉ cho một `TEST_RUN/renpy-complete/game-copy` ≤1.2GiB (1288490188 bytes) từ nguồn game Owner chỉ định; chỉ game-copy đó được loại khỏi phần non-exempt ≤1GiB, không gồm scratch/output/SDK hay root khác. Register/dispose theo scope thực; dọn ngay khi terminal sau process exit và evidence nhỏ. Ngoại lệ không tạo epoch, không tăng cap cache, không cho xóa nguồn.

Owner instruction (2026-10-10, current Ren'Py task): run one final bounded DEV extraction/image workflow on the read-only source `C:/Users/Hiu/Downloads/Compressed/Game copy/Divinity-Update2-pc`, copied only to the registered path above after focused and SDK gates pass. The source has 2,967 files / 1,112,309,849 bytes / tree SHA256 `f19c6d802afb063665046028fc8350f7dd30b1ab9b969f4b8541cf036374ecda`; the 4.6 GB `Game copy` parent includes other games and is not the approved Ren'Py source. This task-specific DEV run supersedes the earlier game-run deferral for this one copy only; it does not change Release acceptance, Unity scope, full-game support claims, or the prohibition on writing to the original.

Game campaign chỉ bắt đầu khi gate không-game đã PASS hoặc có explicit deferral/blocker không làm campaign invalid, và preflight fixture/read-only đủ; gate FAIL chưa giải quyết không đáp ứng điều kiện. Theo quyết định Owner hiện hành, game ở thư mục nguồn được chỉ định chỉ được đọc/kiểm kê và copy vào scope được quản lý trong `TEST_RUN` trước khi test; giữ nguyên nguồn. Chỉ giữ một bản game thử tại một thời điểm, dọn bản copy và output thử ngay khi lượt terminal sau khi lưu evidence nhỏ và process đã thoát. Owner cho phép copy lại khi cần kiểm một thay đổi hoặc giả thuyết mới có bằng chứng; ghi lý do và budget trước mỗi lượt, không lặp mù. Helper cần bản sao bổ sung phải khai báo trước và tuân thủ quota; không âm thầm nhân bản. Ghi `RUN_STARTED` trước bước đầu; PASS/FAIL/TIMEOUT/CANCELLED/START_ERROR đều tiêu thụ lượt đã bắt đầu. Quyết định này thay giới hạn một lượt của chiến dịch trước; không tự đổi cap dung lượng hoặc cấp quyền xóa nguồn.

Persist command/cwd/native exit, readiness, bounded complete/error và timeout reason từng bước ngay khi xảy ra. Worker helper stream tối đa64KiB event mỗi process, giữ64 event cuối (tối đa8192 ký tự/event) trong exception; caller lưu streamed output và exception trong evidence nhỏ trước cleanup. Native exit chỉ có sau process terminal; timeout/kill không đổi thành exit0.

Positive pipeline chỉ translate sau extract complete thành công và chỉ patch/apply sau các semantic prerequisite, QA/preflight theo contract thành công. Negative test được gửi dữ liệu lỗi có chủ đích và assert product từ chối. Read-back phải reopen và đối chiếu giá trị/locator/identity; tồn tại file không đủ.

Owner continuation (2026-10-11, Brain turn01a1294a): bounded acceptance on the two named Divinity-Update2-pc and TomieWGMv1.3801 sources, one registered copy/run at a time, limited translation sample, no broad game campaign. Existing Divinity1.2GiB exemption retains its exact root/cap; Unity gets no implicit quota increase. A declared sample package retains original extracted entry keys/source/locators and records its full-package provenance/selection; sample completion/readback never proves full-game translation/Patch or gameplay. Preserve the untouched full extraction and report its actual pending state separately.

Owner approval (2026-10-11, Brain human turn01a12965-aa84): one bounded Tomie run may temporarily exempt its registered copy/output/temp, total at most5368709120bytes (5GiB); no new copy/retry without further authorization. Exact roots under `TEST_RUN/two-game`: `unity-copy` (cap4026531840), `unity-patch` (cap536870912), `unity-temp` (cap402653184), `unity-packages` (cap134217728). Sum subcaps5100273664bytes; all residual scope files count toward total5GiB. Non-exempt outside these roots remains<=1GiB and shared `.dev-env`<=3GiB. Source Tomie2318files/3488952515bytes/treeSHAfb2cba0eff1b1df4f3407374756a54e7f23621ee2c49096d120cca05324ceb28 is read-only; copy exactly once, register DISPOSABLE with owner `two-game-unity`, persist compact evidence then dispose terminal. Abort on a measured cap breach; do not promote such a run to PASS. Read-only UnityFS metadata shows data.unity3d2959467712 uncompressed bytes, so this run only permits sample Patch of the existing Naninovel bundle37229646bytes/251381189 uncompressed bytes, with strict pre-write serialized-payload size check and no fallback to the large file. This exception changes neither validators/model nor Release acceptance; gameplay remains a separate observation.

Khi terminal, giữ evidence cần thiết ngoài payload trong checkout, kiểm process đã thoát rồi disposal đúng owner. Report test verdict và cleanup riêng. Registry/epoch/report cũ phải có disposition với path/hash/ownership và evidence trước khi xử lý; thiếu quyền không cho phép whole-root delete.

Owner confirmation (2026-10-11, Brain human reply01a129ca-e720): after option-label correction9b009ae, exactly one additional Tomie copy/run may confirm six-row Naninovel Patch/readback under the same exact roots/subcaps/total5GiB above. First Unity exit1 remains unchanged; no further retry, large-asset fallback, publication or model change authorized. Terminal disposal and original-source protection remain mandatory.

### Muc 1 continuation — compiled inspection, image editing and delivery
`renpy_compiled.py` interprets bounded RPYC slot-2 pickle instructions as inert data: no imports, constructors, reducers or state callbacks execute. Only validated native TranslateSay identities enter the compiled dialogue route; other AST classes/semantics produce explicit unresolved coverage and block COMPLETE. Unsupported RPYC structures fail closed. Compiled patch preflight reopens exact source/container/member bytes, verifies their hash and native ID/text/speaker, then uses the existing native overlay writer and unchanged contract validator. Generated SDK lookup/readback is required; a static string match alone is insufficient. Mixed Unity/RenPy and unproven compiled manifests remain blocked.
Rectangular clone-background editing reads the donor from the original image; donor/target bounds and non-overlap are checked, all pixels outside approved target regions remain unchanged. Donor coordinates are editable in WPF and changing them invalidates approval. This is manual background repair, not automatic inpainting.
Image delivery is an additive Vietnamese locale overlay at `game/tl/vietnamese/<original image-relative path>`; only static PNG/JPEG/WebP paths are allowed, never scripts. Source game/container/member and rendered bytes must match recorded hashes. Existing destination files are not overwritten. Installation tests use a separate explicit game copy; the source root remains read-only. A transaction records intent before creating any file, retains exact installed bytes for readback, and rollback only removes a file still matching the installed hash. Modified user files block rollback. Locale activation and native loader resolution require separate generated native evidence; package creation alone is not delivery acceptance.
Compiled-only inspection must remain non-executing: no arbitrary pickle loading or imported game classes. A safe static reader may only claim native identity for supported validated AST schema; unknown opcodes/nodes/version remain explicit unsupported. Current default SDK loader is not such a reader.


### Release 0.1.7 artifact approval — Owner 2026-10-19
Owner explicitly approved temporary 3 GiB non-exempt checkout artifacts for the new clean-source `release-0.1.7` prospective epoch and exact registered `RELEASE_RUN/candidate-0.1.7` scope only. Terminal cleanup returns to <=1 GiB; shared `.dev-env` remains <=5 GiB. Same source, inventory, ownership, lineage, CAS, tamper and eight-hop transition guards apply to descendant clean 0.1.7 prerequisite/gate fixes within this campaign. No rebaseline, dependency download, license acceptance, validator relaxation or game campaign is implied.


### Release 0.1.7 uninstall waiver — Owner 2026-10-19
Owner explicitly requested "Khỏi phải thử, phát hành đi" after Computer Use refused Uninstall.exe. For this 0.1.7 campaign only, publish the tested Setup with actual uninstall acceptance marked NOT VERIFIED / OWNER WAIVED. Canonical disposal of the task-owned candidate is cleanup, never uninstall PASS. This does not waive other gates or change future release requirements.


### Owner correction: regular updates stay in-app — 2026-10-19
Owner rejects asking users to download/reinstall Setup for ordinary app/worker changes. Continue the0.1.7 release campaign by building the missing full-app delta from exact public0.1.6 payload to exact public0.1.7 payload, preserve published Setup/tag/source and verify actual old-app offer/download/apply/restart/data preservation before claiming repair complete. Reuse the already approved same-campaign3GiB exact candidate-0.1.7 temporary scope, terminal<=1GiB/shared .dev-env<=5GiB; no new dependencies or game campaign. Existing hash/provenance/model/baseline/rollback validators remain mandatory. Setup fallback is not acceptance for this correction. Actual0.1.7 uninstall remains Owner-waived; cleanup is separate.


### Final Owner baseline decision — 2026-10-19
Supersedes the preceding0.1.6 repair plan: do not repair0.1.6 updater or add a0.1.6→0.1.7 asset. Owner accepts public Setup0.1.7 as the final manual installation baseline. From0.1.8 onward, ordinary releases must offer/download/apply/restart through the in-app full-app updater, preserving user data/model; asking users to reinstall Setup is not acceptance. Publisher must reject0.1.8+ without a complete older baseline>=0.1.7, explicit GitHub identity and full-app package; no competing WPF-only package for the same target. Validate actual0.1.7→0.1.8 offer/download/apply/restart plus inventory/health/data before claiming readiness. Existing integrity/provenance/rollback guards remain unchanged.

Owner explicitly approved temporary3GiB non-exempt artifacts for the independent0.1.8 campaign, exact registered RELEASE_RUN/candidate-0.1.8 and new clean0.1.8 prospective epoch; terminal<=1GiB, shared .dev-env<=5GiB. Descendant gate/prerequisite fixes retain ordinary lineage/CAS/tamper/eight-hop guards; no rebaseline, game campaign, download or license approval implied.


Future baseline routing (same Owner requirement,2026-10-19): retain the legacy `full-app-update-{target}-{digest16}.zip` from exact public0.1.7 for its immutable client. New0.1.8+ additionally support `full-app-update-from-{installed}-to-{target}-{digest16}.zip`, prefer exactly matching baseline, and search older stable releases for a compatible hop when the newest release advertises other baseline routes. After restart normal discovery advances again. No fallback past an invalid/tampered matching asset; all existing source/URL/size/digest/full-inventory/model/rollback validation remains. Future releases after0.1.8 must supply the supported predecessor baseline and exact legacy0.1.7 baseline, publish both route assets, and retain older stable hops. No promise of skipped-version support may be made from only a latest-version package test.

### Owner release distribution and notes decision — 2026-10-24
Every public release must provide both a version-matched Setup executable for new installations and the supported in-app updater package for existing installations. The release body is Vietnamese and describes only user-visible feature, interface, and bug-fix changes; test counts, source hashes, internal gates/reports, and workarounds for older Setup versions stay in canonical repository evidence. Required notices, checksums, and provenance remain in their appropriate release assets and evidence. Owner authorized completion and publication of update 0.1.11 with both Setup and full-app updater; release acceptance still requires exact-source gates and live readback. The earlier queued 0.1.10 release-body/Setup follow-up is deferred while 0.1.11 is active and is not part of this release authorization.
