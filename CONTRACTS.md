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

**Tests/evidence:** `tests/unit/test_unity_analyzer.py`; disposable game-copy inventory dưới `tests/golden/_work/unity_analyzer_phase2/`.

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

**Owner:** current product route: `mt_ct2_status.py`, `mt_ct2_pipeline.py`, `mt_memory.py`, `app_tasks.py`.

**Invariant:**

- Trạng thái phải phân biệt `translated`, `pending`, `review_only`, `blocked`, `applied`, `copied_vi`, `complete`, `pipeline_liveness`.
- `complete` chỉ đúng khi không còn pending, review-only hoặc blocked theo `_build_translate_result`/`snapshot_translate_status`; có progress nhưng còn review/pending/blocked là partial, không báo hoàn tất.
- CT2 giữ model readiness, retry/quality routing, known-bad clearing, translation memory/context family và retranslate behavior; retry của dòng bị gate chặn phải dùng đầy đủ mask/restore/segment strategy dù full batch chọn fast retry.
- Memory/glossary chỉ áp dụng khi đúng package/context; external reference data là read-only evidence, không phải translation memory và không dùng cache cũ để ghi đè bản dịch frozen ngoài policy.
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

**Tests/evidence:** `tests/unit/test_wpf_workflow.py`, `test_ui_app_workflow.py`, `test_qt_app_workflow.py`, `test_legacy_ui_task_contract.py`, `test_ui_progress.py`; WPF workflow harness trong `wpf_app/VNText.Studio.Workflow.Tests/Program.cs`.

## 7. Patch, UnityFS và Addressables

**Owner:** `patch_gate.py`, `patch_pipeline.py::apply_translation_package`, `patch_plain.py`, `patch_unity.py`, `patch_safety.py`, `patch_output.py`, `unity_fs.py`, `addressables.py`.

**Invariant:**

- Patch chỉ dùng translation đã qua gate; đọc CSV/manifest theo key và `file_path`, tạo `COPY_TO_GAME_ROOT`, `backup_original` và report. Unity route thêm `patch_manifest.json`/installer; Ren'Py loose-source route tạo native overlay riêng.
- Không ghi game gốc trong workflow tự động; output phải ở patch/work directory, installer/restore dùng exact original hash.
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

**Tests/evidence:** `tests/unit/test_renpy_patch.py`, `tests/unit/test_patch_delivery.py`, `tests/unit/test_worker_protocol.py`, `tests/unit/test_wpf_workflow.py`, WPF harness; external full-game/Release evidence chỉ được claim khi fixture và exact Release gate được cung cấp.

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
- WPF compatibility package giữ allowlist ba file `VNText Studio.exe`, `app/RELEASE.json`, `app/VERSION.txt`; asset SHA-256, manifest, semantic version, executable metadata, baseline và từng file hash phải khớp. WPF package cũ vẫn hoạt động cho release tương ứng; thiếu package áp dụng được dẫn tới official Releases/Setup route, không auto-run Setup.
- Full-app package được discovery theo stable GitHub release và asset chính xác `full-app-update-{version}-{sha256[:16]}.zip`; một release chỉ được có đúng một update asset WPF hoặc full-app phù hợp version. Repository/tag/HTTPS host, GitHub API size, tải thực tế, digest, manifest và package size đều phải được kiểm. Manifest gắn source commit SHA-1 và source tree fingerprint SHA-256 (`SHA256("git-tree-sha1:" + Git tree object ID)`), khớp metadata trong `app/RELEASE.json`; đây là provenance metadata, không phải chữ ký mật mã. Delta chỉ được áp dụng khi inventory/hash của toàn bộ `VNText Studio.exe` + `app/**` đúng baseline đã package, manifest add/replace/delete nhất quán và ZIP chứa đúng entry. Từ chối reparse/symlink, path traversal, trùng tên case-insensitive, file ngoài inventory, protected app data, package tamper, sai version/provenance hoặc baseline mismatch.
- Full-app staging, backup, journal, log và worker/updater helper ở install root, ngoài `data/`; package nén tối đa 512 MiB và expanded inventory tối đa 3 GiB/20.000 file. Chỉ thay executable và `app/**`; `app/worker/models/**` phải giữ nguyên hash/tập file theo baseline. App và worker dừng bình thường trước khi apply. Sau apply kiểm inventory, `RELEASE.json`, `VERSION.txt`, executable version/hash, app health và worker readiness; restart thành công mới commit journal. Health/restart failure hoặc gián đoạn phải rollback/khôi phục từ backup đã hash-verify. `data/`, game, model/cache người dùng và output không là update targets; file lạ dưới `app/` làm baseline mismatch.
- Full-app updater ghi danh sách file sở hữu tại `.update/owned-files.json`; Setup được build từ source hiện tại merge sidecar vào `data/install-manifest.json` để repair/upgrade kế tiếp nhận biết file được thêm. Setup v0.1 đã phát hành là binary cũ, không được sửa bởi source update và chưa được chứng minh có thể đọc sidecar; thay đổi `Setup.exe`, `Uninstall.exe` hoặc quyền hệ thống vẫn cần Setup mới. Bằng chứng local bridge trên bản cài không thay thế acceptance với stable GitHub release công khai. Cập nhật toàn app trên bản cài v0.1/GitHub vẫn **NOT VERIFIED** cho tới khi acceptance đó được chạy.
- Release không phụ thuộc Python hệ thống; `app/worker/.venv/pyvenv.cfg` trỏ bundled `app/worker/python`. Verify/smoke chạy trên staging trước khi đóng gói Setup. Publisher chỉ thay ReleaseRoot sau khi payload archive/hash và copied Setup hash hợp lệ.
- Version lấy từ `VERSION.txt`/`app_backend.VERSION`; publisher báo source SHA, Setup SHA256/size và payload file/byte count.

**Tests/evidence:** `tests/unit/test_setup_package.py`, `test_runtime_paths.py`, `test_wpf_workflow.py`; `release/package_installer.py`, `release/publish.ps1`, `release/publish_owner_wpf_update.py`, `vntext/release_verify.py`. The package test runs the generated final PowerShell helper on a fixture and verifies that `Uninstall.exe` and every descendant are gone while the regular install root remains empty. Setup UI, selected-folder install, real whole-folder-content uninstall and button-driven A→B update require installed-app verification; do not infer them from package tests alone.

## 10a. Test artifact retention and cleanup lifecycle

**Owner:** `tests/lib/work_paths.py`, `tests/tools/cleanup_work_artifacts.py`, `tests/tools/run_with_cleanup.py`, `release/run_regression.ps1`.

**Public-clone rule:** This section is canonical for current artifact lifecycle
and cleanup. A fresh checkout has no private registry/epoch or its historical
evidence; do not import or reconstruct them. Assess only the current checkout's
registered artifacts, and do not infer current cleanup or Release PASS from
unavailable historical reports.

**Invariant:**

- Every artifact under `tests/golden/_work` is classified as `PROTECTED`, `RETAINED`, `DISPOSABLE`, `UNKNOWN`, `MISSING` or `STALE`, and registered with a non-empty owner and purpose. `artifacts_manifest.json` is the only registry; `cleanup_manifest.json` is a run report.
- `game_copy` is protected from generic cleanup but is a temporary test copy, never a retained fixture/baseline. For every game-test outcome, first save needed reports/logs outside the copy and ensure the test process has exited. The canonical copy uses `dispose_e2e_game_copy`; a scoped copy must be registered at its exact root as `kind=test_game_copy`, `lifecycle=DISPOSABLE` and passed to `cleanup_after_test(..., disposable_paths=[copy])` with the actual test outcome. Both routes record terminal `MISSING`. Canonical non-game fixtures, user/game paths, models, baselines and retained evidence remain protected. Cleanup targets must stay under `_work`; outside/protected paths are rejected and no process is killed to make deletion possible.
- An ACTIVE legacy entry whose path is absent becomes `MISSING`/`STALE`; an existing root without a registry entry becomes `UNKNOWN` unless an explicit protected/retained path rule covers it. Neither case is silently dropped or deleted.
- `--dry-run` performs no `_work`, registry or evidence write; only an explicitly requested `--output` outside `_work` may be written. Generic cleanup deletes only registered `DISPOSABLE` artifacts (plus the explicit audited migration allowlist). After `PASS`, `FAIL`, `TIMEOUT`, `START_ERROR` or `CANCELLED`, the runner preserves the exact outcome/exit/command/test summary/error and bounded stdout/stderr excerpts in compact Markdown, then attempts disposal after the process exits. Raw logs and heavy disposable payload are not retained for debugging. If the child remains alive, do not finalize or claim cleanup success; report its PID and `REVIEW_REQUIRED`. Test verdict and cleanup status remain separate.
- Both dry-run and apply must block a deletion root when any live non-`DISPOSABLE` registry entry claims that root or a descendant; malformed claims fail closed. Dry-run reports the blocker, never a planned deletion; apply rechecks the same ownership guard immediately before removal. `PROTECTED`, `RETAINED`, `UNKNOWN`, `STALE`, external/user paths and descendants claimed by those entries remain untouched.
- Registry reads used for updates reject linked/nonregular files, unreadable or malformed JSON, non-object roots and invalid `artifacts`/`archive` container shapes. Reconciliation never rewrites malformed registry metadata; cleanup remains `REVIEW_REQUIRED` until it is resolved.
- Every canonical run carries `scope_id`, `run_id`, `scope_root` and provenance, captures before/after inventory, and finalizes lifecycle in `finally`. New or modified paths outside the current scope registration are UNKNOWN/review-required. Cleanup status and before/after/deleted/retained/protected/unknown/locked data are evidence; cleanup failure cannot be hidden behind a child test PASS.
- New cleanup reports use schema 4 for scoped runs and schema 3 for whole-work cleanup. Repeated inventory path maps are omitted from reports and represented by count plus deterministic SHA-256; lifecycle lists over 100 records retain a 100-record sample plus full count/hash. The canonical manifest remains the full record source, and historical reports are not rewritten.
- Runner-owned records use a stable ID derived from normalized physical path and related tree registrations are batched, so repeated runs update the same current record instead of adding one copy per `scope_id`/`run_id`. Existing historical entries are preserved; this does not reconcile or reclassify prior UNKNOWN/MISSING records.
- Deletion requires a complete inventory, a registered `DISPOSABLE` target, no active process using it, and no live non-disposable claim. Unknown or unproven paths stay untouched until ownership is resolved; they are reported with path/size and cannot be silently kept as an unlimited retention exception. Each cleanup reports before/after size and exact deletion/retention outcomes. Project-size inventory fails closed on links/reparse points, special files, stat/scandir errors or budget limits. A cleanup `PASS` requires a complete after-snapshot with no more than 1 GiB of non-exempt project files; exemptions are measured per regular file and are limited to `.venv`, `DEV_RUN/dotnet-sdk-10`, `DEV_RUN/python`, `DEV_RUN/.venv` and `DEV_RUN/cache`, each with its fixed reason in `cleanup_work_artifacts.py`. These are exact roots, not blanket exemptions for `DEV_RUN` or `_work`.
- Cleanup is test/tooling infrastructure and must not change translation semantics, worker NDJSON, WPF product behavior or engine/game behavior.

**Tests/evidence:** `tests/unit/test_cleanup_work_artifacts.py`, `test_artifact_write_policy.py`, `test_work_paths.py`, `test_release_regression_runner.py`; `tests/tools/run_with_cleanup.py`; cleanup report under `_work` after an explicit cleanup run.

## 10b. Prospective artifact-registry epoch

`tests/tools/cleanup_work_artifacts.py` owns the additive prospective epoch transition. `--prospective-epoch-plan` and `--verify-prospective-epoch` are read-only; `--apply-prospective-epoch` may write only a retained epoch scope and the canonical manifest metadata. Apply is fail-closed on a dirty tree, source SHA mismatch, active writer marker, incomplete/budget-limited inventory, invalid schema/provenance, missing or mismatched rollback snapshot, or conflicting active epoch. It never deletes artifacts.

Each active epoch retains an exact pre-transition manifest rollback snapshot, policy, rollback metadata and a current filesystem ledger under `tests/golden/_work/artifact-registry-epochs/<epoch-id>/`. The ledger is prospective only: registered evidence keeps its lifecycle, current unproven paths remain `UNKNOWN`, and preserved historical data is distinct from the rollback snapshot and new ledger. Private historical registries or reports are not present in a public clone, are not clone prerequisites, and cannot establish current cleanup or Release acceptance. Assess a new checkout and each release from its own evidence; do not infer historical PASS.

Mỗi public clone mới bắt đầu mà không có artifact epoch của checkout riêng
trước đó. Không nhập/tái tạo incident registry riêng, không tái dùng timestamp,
hash hay report lịch sử, và không yêu cầu tìm artifact private làm điều kiện
cho clone mới. Khi helper khởi tạo epoch mà incident-preservation history vắng,
helper hiện vẫn yêu cầu caller cung cấp statement tường minh qua
`--owner-reset-authorization`. Với clone mới, statement chỉ ghi nhận đây là
fresh public clone không có private history; nó không chứng minh history đã
được khôi phục, cleanup PASS hay incident đã được giải quyết. Chỉ đăng ký
evidence của checkout hiện tại theo canonical tool. Registry hiện tại nếu có
vẫn phải là regular file đọc được và đúng schema; state malformed, partial,
linked hoặc unreadable phải block. Nếu manifest hiện tại tồn tại, giữ snapshot
rollback nguyên byte cùng SHA-256 và size; nếu không có thì snapshot ghi nhận
trạng thái absent. Preflight race không được xóa lock của writer khác. Không
apply epoch live trước khi source được commit sạch; test chỉ apply/rollback
trong disposable fixture.

### Prospective portable Release acceptance

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

**Tests/evidence:** `tests/unit/test_cleanup_work_artifacts.py` prospective plan/apply/refusal/idempotency/hash/unknown tests, affected work-path and artifact-write suites, epoch scope policy/ledger and rollback hashes under `_work`.

## TEST GAP đã biết

- Không có test tự động riêng mô phỏng double-click UI thật; WPF harness/build và Release smoke không thay thế hoàn toàn kiểm tra pixel/click thủ công.
- Chưa có active Ren’Py full-game E2E trong runtime test matrix; native unit/read-back/delivery coverage không thay thế exact external game và Release evidence.
- `app.py` giữ QML branch chỉ cho explicit legacy selection và gọi `qml_ui.bridge`, nhưng source hiện chỉ có asset `qml_ui/icons/logo.png`; QML-ready path là UNKNOWN cho tới khi bridge tồn tại và `--release-verify-qml` PASS. Shipped/default UI là WPF.
- Worker tests còn `ResourceWarning` liên quan pipe/process theo AI_STATE; không tự sửa trong context task.
