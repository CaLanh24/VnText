# VNText Studio — Trục kiến trúc

Trạng thái: phản ánh source hiện tại; SHA của checkpoint/evidence phải lấy từ Git và ghi trong `AI_STATE.md`, không hard-code một HEAD lịch sử trong bản đồ này. Đây là bản đồ tra cứu, không phải kế hoạch refactor mới.

## Nguồn sự thật và nguyên tắc đọc

- VERIFIED: source hiện tại và test/fixture/golden/E2E là nguồn chính.
- VERIFIED: `AI_STATE.md` ghi trạng thái và bằng chứng gần nhất.
- Dependency/call-path conclusions are verified from targeted source/tests and
  `rg`/`git grep`; generated graph/cache artifacts are not architecture
  sources and are not part of bootstrap.
- Khi docs mâu thuẫn source/test, sửa docs theo source/test; không sửa behavior để khớp docs.

## Nguyên tắc kiến trúc đa engine

Unity là engine được triển khai đầu tiên, không phải kiến trúc của toàn ứng dụng.

Các phần phụ thuộc engine như:

- phát hiện engine;
- phân tích game và tài nguyên;
- trích xuất text;
- tạo patch/repack;
- xác minh semantic sau patch;

phải được giữ sau ranh giới riêng của từng engine.

Các contract và hạ tầng dùng chung như:

- `Entry`;
- translation;
- glossary/context;
- traceability;
- package;
- backup;
- reporting;
- điều phối worker/app;

phải độc lập với engine càng nhiều càng tốt.

Khi bổ sung engine mới, ưu tiên triển khai phần riêng của engine đó theo hướng:

```text
Engine Detector
→ Engine Analyzer
→ Engine Extractor
→ Common Entry
→ Shared Translation
→ Engine Patcher
→ Engine-specific Verification
```

Không đưa logic đặc thù của Unity, Ren'Py hoặc engine khác vào shared/core nếu có thể giữ logic đó sau engine boundary.

Analyzer, Extractor, Patcher và Verifier của từng engine có thể có implementation khác nhau nhưng phải giao tiếp với hạ tầng chung qua contract rõ ràng.

Một capability chỉ được coi là hỗ trợ đầy đủ khi có đủ:

- extract;
- locator/provenance phù hợp;
- write-back/patch;
- verification tương ứng.

Nếu chưa đủ thì phải phân loại rõ `EXTRACT_ONLY`, `REVIEW_REQUIRED` hoặc `UNSUPPORTED`, không coi là hỗ trợ hoàn chỉnh.

## Cách đọc trạng thái capability

- `CAPABILITY_STATUS=IMPLEMENTED_CURRENT`: source có route hiện tại và test/fixture tương ứng chứng minh đúng phạm vi đã ghi.
- `CAPABILITY_STATUS=IMPLEMENTED_LIMITED`: có implementation và bằng chứng nhưng chỉ cho subset, fixture, version hoặc engine/profile cụ thể.
- `CAPABILITY_STATUS=EVIDENCE_INSUFFICIENT`: đã có discovery/route một phần nhưng chưa đủ bằng chứng để gọi là hỗ trợ.
- `CAPABILITY_STATUS=PLANNED`: hướng đã xác định nhưng chưa có implementation/contract/test hoàn chỉnh.
- `CAPABILITY_STATUS=NOT_IMPLEMENTED`: chưa có route tương ứng.
- `DOC_STATUS=CURRENT|STALE_DOC`: trạng thái tài liệu độc lập với capability; tài liệu không được dùng để nâng status runtime.

## Luồng hệ thống

```text
WPF App (App.xaml.cs/MainWindow/MainViewModel)
        │ NDJSON stdin/stdout
        ▼
vntext_worker.worker_main
        ▼
vntext_worker.task_runners
        ▼
vntext.app_tasks ───────────────┐
        │                        │
        ├─ extract               ├─ CT2 / OPUS-MT
        ├─ write package         ├─ patch preflight
        └─ patch                 └─ apply patch
                 │
                 ▼
translation.csv + manifest.json + .mt + Patch_Viet_Hoa/
```

Điểm vào Python:

- `app.py::main`: compatibility entry cho runtime Python và các chế độ CLI của Release. UI shipped/default là WPF qua executable đã build tại `DEV_RUN\VNText.Studio.App.exe`; `app.py` mặc định legacy Tk. `VNTEXT_UI=qml` chỉ là nhánh QML tùy chọn, hiện UNKNOWN vì `qml_ui.bridge` không có trong source.
- `vntext_studio.py`: trình khởi chạy Tk và compatibility facade; re-export backend cũ cùng `VNTextApp`/`RawCandidateReviewer`.
- `vntext_worker/worker_main.py::main`: worker dài hạn, phát `ready`, nhận `run`/`cancel`, điều phối extract/translate/patch.
- WPF `wpf_app/VNText.Studio.App/App.xaml.cs::OnStartup`: app chính; `MainViewModel` khởi động `PythonWorkerHost`.

Luồng nghiệp vụ chuẩn:

1. `vntext.app_tasks::run_extract_task` gọi `vntext.app_backend::extract_project`, sau đó `write_package` tạo package.
2. Product route `run_translate_ct2_task` gọi CT2 pipeline và ghi trạng thái `.mt`; translation protection/postprocessing is owned by `mt_translation_safety.py` and shared constants by `mt_translation_constants.py`.
3. `run_patch_task` validate CSV, chạy `patch_gate`, gọi `apply_translation_package`, kiểm tra read-back và tạo installer/manifest output theo option hiện tại.
4. WPF nhận `complete`/`progress`/`log`, cập nhật state và chuyển tab Extract → Translate → Patch theo `MainViewModel.Worker.cs`.

## Ownership hiện tại

### Điều phối và package

- `vntext/app_tasks.py`: task cầu nối dùng chung cho Tk/Qt; không chứa widget. Giữ callback `progress/log/complete` và gọi facade/public API.
- `vntext/app_backend.py`: backend app-level: `extract_project`, asset index, raw candidate, internal Unity dump, package cleanup và `VERSION`.
- `vntext/app_workflow.py`: suy ra package directory, quản lý translation và trạng thái workflow.
- `vntext/package_io.py`: `CSV_FIELDS`, đọc/ghi CSV, backup CSV, phân loại patchable/review/raw, ghi `manifest.json` và report.
- `vntext/entry.py`: `Entry`, `make_key`, chuyển entry thành CSV row/manifest entry.
- `vntext/app_ui.py`: Tk app/reviewer tương thích cũ; `vntext/qt_app.py`, `qt_workers.py`, `qt_widgets.py`, `qt_theme.py`: Qt app, worker bridge và lớp hiển thị. UI gọi lớp điều phối, không sở hữu parser/writer.

### Extract

- `vntext/extract_pipeline.py::extract_project`: điều phối file, progress, timeout, gọi các nhóm xử lý và hậu xử lý; trả `(main, review, stats)`. Mọi entry đều qua `route_main_flow`; chỉ entry có đủ symmetry proof/locator mới vào `main`, phần còn lại được giữ ở review.
- `vntext/extract_text.py`: file text, line parser, length-prefixed/7-bit/msgpack string, semicolon language table và TextAsset line. `.txt`/`.nani`/`.scenario` dùng proof của line writer; structured JSON/CSV/XML có route theo field riêng, còn YAML vẫn ở ranh giới review/extract-only.
- `vntext/extract_sqlite.py`: kiểm kê schema/hàng SQLite có giới hạn, chỉ đọc ở input; subset an toàn `structured_sqlite_value` chỉ gồm rowid table thông thường có đúng một `INTEGER PRIMARY KEY`, cột text-like có tên/type phù hợp, không có WAL/SHM sidecar. Subset này có locator/schema/file fingerprint, transactional copied-database writer và reopen verification; các chuỗi ngoài subset vẫn là `sqlite_text_candidate` review-only.
- `vntext/extract_yaml.py`: kiểm kê dòng YAML strict-UTF-8 có giới hạn cho mapping/list/block scalar; chỉ phát hiện candidate thành `yaml_text_candidate` review entries với metadata line/column/field, không parse schema/anchor/tag và không có patch proof hay writer.
- `vntext/extract_unity.py`: UnityPy/TypeTree, Unity UI, aligned length-prefixed scan; phát metadata proof rõ ràng cho TextAsset/UI, object Naninovel Script trực tiếp, route giá trị Unity Localization StringTable đã được chứng minh và field TypeTree có dạng hiển thị.
- `vntext/unity_localization.py`: seam đọc/locator/precondition nghiêm ngặt cho StringTable; chỉ promote `m_TableData[*].m_Localized` dưới class identity `StringTable`, còn key/metadata của SharedTableData và schema Localization khác vẫn review-only.
- `vntext/extract_naninovel.py`: blob/script Naninovel, `@choice`/`@print`, path id, raw candidate và locator slot; entry Script trực tiếp có path-id/ordinal locator và proof roundtrip. Gợi ý choice ở cấp file dùng memory map chỉ đọc để không materialize resource Unity lớn thành toàn bộ `bytes`.
- `vntext/extract_quality.py`: chất lượng ứng viên, UI label, bộ lọc technical/code/binary/noise.
- `vntext/extract_postprocess.py`: dedupe, cân bằng main/review, raw candidate và postprocess.
- `vntext/extract_constants.py`: constants/import dùng chung cho extraction.
- `vntext/unity_analyzer.py`: analyzer Unity chỉ đọc; resolve executable/`*_Data`, kiểm kê theo signature, probe object type/class identity có giới hạn và tạo capability report. Marker class/path của Unity Localization chỉ là bằng chứng discovery và `REVIEW_REQUIRED`; route extractor StringTable có roundtrip method-level nhưng analyzer vẫn giữ `patch_verification=NOT_RUN` và không tuyên bố đã patch/reopen resource của game đang phân tích.
- `vntext.unity_analyzer.detect_resource_kind`: route signature có giới hạn dùng chung để nhận diện UTF text không có extension và Unity container header; sidecar resource không tự động bị đẩy vào UnityPy. `analyze_unity_game` cũng tạo block `coverage` chỉ đọc có thể đo được; `patch_verification` của analyzer giữ `NOT_RUN`, còn proof StringTable phía extractor đến từ roundtrip disposable. Marker path Localization/Addressables chỉ là cảnh báo capability; không được ghi đè route method JSON/CSV/XML generic đã được chứng minh nếu chưa có bằng chứng format-specific.
- `vntext/patchability.py`: các field proof của `Entry`/manifest, method registry, audit fail-closed và `route_main_flow`; các marker proof của TextAsset, UI, Naninovel Script, Unity Localization StringTable và TypeTree dạng hiển thị được chứng minh bằng micro-fixture/live-fixture.
- `vntext/extract.py`: compatibility facade; không phải owner algorithm. Public/private names cũ được re-export từ các leaf.

### Translation

- Dùng chung: `mt_check.py` (kiểm tra placeholder/tag/newline/language/structural), `mt_classify.py` (định tuyến row/technical/keep), `mt_strategies.py` (chiến lược CT2 bảo vệ), `mt_apply.py` (batch write gate), `mt_memory.py` (translation memory theo package), `mt_qa.py` (QA toàn file), `intentional_keep.py` (đối soát keep có chủ đích).
- Local Translation V2: `mt_classify.py` là decision boundary authoritative cho route CT2/status/trace; policy hash, reason/ledger/evidence và no-drop measurement được giữ ngoài CSV. `classify_row()` chỉ còn compatibility oracle nội bộ, còn caller bình thường dùng `classify_row_authoritative()` để REVIEW/UNSUPPORTED fail-closed. `traceability.py`/`app_tasks.py` ghi provenance theo package, entry và duplicate-aware target; `patch_readback.py` reopen từng target và tách `PATCHED` khỏi `READ_BACK_VERIFIED`.
- `mt_model_adapter.py` giữ model boundary nhỏ (`translate`, `translate_many`, config, metadata); CT2/OPUS-MT là route mặc định. `translation_cache.py` là cache SQLite package-local, single-writer/validated-only, fingerprint theo source/context/glossary/memory/classifier/model/strategy/protected inputs; cache hit vẫn phải qua validation.
- `glossary_v2.py` và `context_builder.py` là sidecar additive dưới `.mt/v2`: glossary scoped/exact/mask-restore có conflict fail-closed và giữ flat glossary; context chỉ tạo cửa sổ bounded khi có boundary rõ ràng cùng file/engine. Context có trạng thái `METADATA_ONLY`, được ghi/fingerprint nhưng chưa được bơm vào prompt CT2.
- Product translation exposes CT2/OPUS-MT only. The Argos route, dependency, and Argos-only implementation have been removed. The previous facade removal is an intentional source compatibility break; shared validation, masking, segmentation and postprocessing live in neutral translation modules. The former VinAI adapter and packaging route have also been removed; old benchmarks are historical only.
- CT2: điều phối ở `mt_ct2_pipeline.py`; truy cập model/status ở `mt_ct2_model.py` (chỉ thêm prefix ngôn ngữ đích do tokenizer khai báo); batch IO/chunking ở `mt_ct2_io.py`; trạng thái ở `mt_ct2_status.py`; import/constants dùng chung ở `mt_ct2_constants.py`.
- `mt_ct2.py`: compatibility facade for the current product route. `mt_argos.py` is intentionally absent; shared text behavior is in `mt_translation_safety.py`.

### Patch và game formats

- `vntext/patch_gate.py`: audit eligibility chỉ đọc, kiểm tra garbage/HTML/identity/placeholder/tag/newline và từ chối fail-closed metadata profile/locator legacy đã bị loại khỏi public tree. `patch_pipeline.py` không tự áp corpus, profile hoặc locator ngoài manifest hiện tại.
- `vntext/patch_pipeline.py::apply_translation_package`: dispatcher theo engine/entry, route Ren'Py loose-source native overlay hoặc Unity/Naninovel/raw, backup, report, cập nhật Addressables và gọi read-back verification cuối; compiled-only/mixed Ren'Py route fail closed, không fallback Unity. `PATCHED` chỉ là write outcome, không phải `READ_BACK_VERIFIED`. `unity_typetree_field` generic và `unity_localization_string` đã được chứng minh dùng `path_id` + `field_path`, yêu cầu đủ `patch_proof` trước khi ghi, rồi flush TypeTree trước khi lưu. Ghi StringTable cũng bắt buộc precondition là giá trị serialized gốc còn khớp. Đăng ký bundle Addressables đi qua discovery catalog có giới hạn.
- `patch_plain.py`: thay thế plain/TextAsset/length-prefixed và kiểm tra slot-fit. Route plain text chính áp dụng line locator bắt đầu từ 1 (kể cả vị trí trùng), bảo toàn BOM/newline.
- `patch_unity.py`: object/TypeTree/UI field replacement và thay payload `Font` chỉ theo mapping explicit do caller cung cấp; thiếu source/target hoặc save lỗi phải fail-closed. Không có mapping/corpus game tích hợp sẵn.
- `patch_renpy.py`: native loose-source dialogue/string overlay, identity precondition và read-back verification; không dùng Unity installer output.
- `patch_naninovel.py`: Naninovel Script object/field replacement.
- `patch_safety.py`: backup, locator, raw fixed ops, encoded variants và verification output đã patch.
- `patch_output.py`: Unity `COPY_TO_GAME_ROOT`, generic executable/`*_Data` installer install/restore discovery, patch manifest và Unity save wrapper; Ren'Py native overlay delivery thuộc `app_tasks.py`.
- `wpf_app/VNText.PatchInstaller/`: validation install/restore generic từ executable và layout `*_Data`; các field manifest cũ vẫn tương thích.
- `unity_fs.py`: streaming/ghi lại UnityFS và bảo toàn metadata; `addressables.py`: parser/writer frozen catalog extra-data, cập nhật CRC/size; `addressables_discovery.py`: quan hệ catalog gần nhất theo cách generic, không sở hữu binary catalog format.
- `patch.py`: compatibility facade; không phải owner algorithm.

### Traceability và provenance

- `vntext/traceability.py`: TraceStore schema v2, package/entry/target identity, event lifecycle, migration, one-writer lock, WAL/FULL sync và crash recovery. `traceability.sqlite3`, `trace_summary.json`, `diagnostic_summary.json` và JSONL export là package-local evidence, không thay thế CSV/manifest. Diagnostic sidecar nhóm stage/root-cause, coverage, translation/patch measurements và actionable next step.
- Traceability là additive: worker/app extract-translate-patch route được trace đầy đủ theo caller; `vntext/release_verify.py` vẫn gọi pipeline trực tiếp và phải báo công khai `TRACE_NOT_ENABLED` cùng reason/impact, không được suy ra provenance đầy đủ.

### Worker và WPF

- `vntext_worker/protocol.py`: NDJSON protocol, `PROTOCOL_VERSION`, emit/parse.
- `vntext_worker/worker_main.py`: vòng đời process, ready, busy, cancel và dispatch.
- `vntext_worker/task_runners.py`: validate params, map payload worker vào `app_tasks`, phát event.
- WPF `Services/PythonWorkerHost.cs`: khởi chạy Python portable, gửi command, đọc stdout/stderr, quản lý vòng đời event.
- WPF `Services/SmokeWorker.cs`: smoke tự chứa cho cancel/extract/translate/patch/crash; không đọc artifact hoặc đường dẫn game-specific.
- WPF `Models/WorkerEvent.cs`: deserialize các field của event.
- WPF `ViewModels/MainViewModel.cs`: field, property, command và public binding surface.
- WPF `MainViewModel.Workflow.cs`: workflow run/cancel; `Paths.cs`: picker/CSV/preflight; `Worker.cs`: event/progress/log/completion; `CsvEditor.cs`, `Glossary.cs`, `Notifications.cs`: các vùng còn lại.
- WPF `Services/WorkflowStatus.cs`, `WorkflowStepState.cs`, `WorkflowTabs.cs`: state machine và tab identifiers.
- WPF `Services/CsvPackageValidator.cs`, `PatchPreflightService.cs`: preflight trước patch.
- WPF `Services/WorkerPaths.cs`: DEV/RELEASE root, Python executable, guard `pyvenv.cfg` portable và app data root. Release mutable state ở `<install-root>/data/`, không fallback AppData/Temp.

### Release

- `release/publish.ps1`: preflight/build/venv portable/release verify/smoke trên staging; đóng gói Setup có manifest hash, WPF package và, khi có `-FullAppUpdateBaselineRoot`, full-app package bất biến từ đúng Release staging tree. Full-app feed/package được publish sau khi candidate `RELEASE.json` khớp source SHA và tree fingerprint; publisher không tự chọn baseline.
- `release/Setup.cs` và `release/package_installer.py`: chọn đích, kiểm SHA256/path traversal, giải nén trực tiếp; mọi Setup thường tạo nguồn update từ thư mục `Updates` cạnh Setup đang chạy. Uninstaller xác nhận một lần, xóa mọi nội dung gồm data, rồi helper chờ tiến trình thoát để xóa đúng `Uninstall.exe`; install root vẫn tồn tại như thư mục thường rỗng. Lỗi xóa hoặc hậu kiểm báo lỗi và trả exit code khác 0.
- `release/publish_owner_wpf_update.py` tạo gói WPF A→B tương thích cũ; `release/publish_full_app_update.py` tạo full-app delta từ một install baseline và một Release candidate đã build. Candidate và package cùng mang Git source SHA/tree fingerprint, SHA-256/size inventory, baseline inventory và manifest add/replace/delete. Publisher không đưa `app/worker/models/**` vào delta và từ chối khi model khác baseline.
- `wpf_app/.../Services/WpfUpdateService.cs` sở hữu discovery/download GitHub; `FullAppUpdateService.cs` kiểm hash/size, version/source provenance, inventory/baseline, manifest và ZIP, rồi stage/backup/journal/apply dưới install root ngoài `data/`. Full-app chỉ đụng `VNText Studio.exe` và file `app/**`; dừng app/worker, kiểm executable/worker health, restart và rollback/recover journal. `data/`, game, output người dùng và model không phải update targets. Setup-sidecar `.update/owned-files.json` cho Setup mới biết file do delta thêm.
- `release/prune_worker_venv.py`: loại package không cần khỏi worker venv.
- `release/make_venv_portable.py`: copy CPython bundled, ghi lại `pyvenv.cfg`, smoke import.
- `vntext/release_verify.py`: extract → translate → patch headless và verification progress/sound; workflow report ghi rõ `TRACE_NOT_ENABLED` vì đây là direct isolated caller.
- `wpf_app/VNText.PatchInstaller`: installer install/uninstall và restore theo exact hash.

### Test artifact lifecycle (test/tooling only)

- `tests/lib/work_paths.py` owns canonical `_work` paths, protected game-copy guards, scoped registry/provenance writes and the `artifact_scope` context manager. It must not alter product runtime behavior.
- `tests/tools/cleanup_work_artifacts.py` owns registry reconciliation, bounded inventory, the explicit legacy migration allowlist and cleanup reports. `artifacts_manifest.json` is the registry; `cleanup_manifest.json` is a retained report, never a second registry.
- `tests/tools/run_with_cleanup.py` wraps canonical Python unit/worker/WPF commands, allocates scope/run IDs and captures compact terminal evidence while keeping test and cleanup verdicts separate. Ownership, lifecycle, deletion and size-budget rules are defined in `CONTRACTS.md` §10a.
- `release/run_regression.ps1` is a caller of the same artifact policy for isolated Release patterns and records child outcome/cleanup evidence in `CLEANUP_COMPLETE.json` and `REGRESSION_COMPLETE.json`; it does not own a separate retention policy.
- This lifecycle is test/governance infrastructure only; it does not participate in `vntext/`, `vntext_worker/`, WPF product flow or game patch behavior.

## Dependency direction hợp lệ

Ưu tiên dependency từ lớp ngoài vào lớp sở hữu:

```text
WPF/Tk/Qt
  → điều phối worker/task
  → app_backend / translation facade / patch facade
  → các module sở hữu nhóm xử lý
  → các primitive dùng chung (entry, package_io, mt_check, UnityFS/addressables)
```

Compatibility facade được phép re-export leaf để giữ caller cũ. Leaf không được lấy runtime dependency bằng binder hoặc mutate global namespace của facade. Một số edge hiện hữu cần coi là ngoại lệ tương thích, không tự sửa trong task thường:

- `mt_ct2_constants.py` and `mt_strategies.py` import shared helpers directly from `vntext.mt_translation_safety`.
- Các compatibility facade còn gọi public patch API qua `vntext.patch`.
- `patch_constants.py` dùng extraction facade cho helper dùng chung.

Các edge này là technical debt/ranh giới tương thích đã quan sát từ source; thay đổi chúng cần task riêng kèm import/behavior regression.

## Vùng nhạy cảm

- key/CSV/manifest: `entry.py`, `package_io.py`, golden/characterization.
- scanner Unity/Naninovel/TextAsset: mọi thay đổi có thể đổi key, locator hoặc số dòng.
- translation gate: `mt_check.py`, `mt_strategies.py`, `patch_gate.py`; không nới gate để làm test xanh.
- UnityFS/Addressables/generic UI/profile Font: chỉ test trên game copy, luôn kiểm fingerprint game gốc.
- worker protocol và WPF state: đổi payload hoặc completion semantics có thể làm UI báo hoàn tất giả.
- portable release: không dùng Python hệ thống trong RELEASE, không dùng artifact cũ làm bằng chứng.

## Bắt đầu ở đâu khi thêm feature loại X?

- Extract family mới: `extract_pipeline.py` để nối flow; parser ở `extract_text.py`, `extract_unity.py` hoặc `extract_naninovel.py`; quality ở `extract_quality.py`; output/schema chỉ đổi trong `package_io.py` khi có contract evidence.
- CSV/key/manifest: `entry.py` + `package_io.py`; bắt đầu bằng characterization/golden.
- CT2: `mt_ct2_pipeline.py`, model ở `mt_ct2_model.py`, chunk/IO ở `mt_ct2_io.py`.
- Trace/provenance/read-back: `traceability.py`, `package_io.py`, `app_tasks.py`, `patch_readback.py`; trước tiên phải giữ stable key/locator và phân biệt write với reopen verification.
- Model/cache/glossary/context: `mt_model_adapter.py`, `translation_cache.py`, `glossary_v2.py`, `context_builder.py`; chỉ mở rộng additive sidecar/fingerprint, không đổi CSV fields hoặc default model nếu chưa có contract.
- Placeholder/tag/escape/newline/quality: `mt_check.py` hoặc `mt_strategies.py`; patch eligibility ở `patch_gate.py`.
- Plain/TextAsset: `patch_plain.py`; Unity object/TypeTree: `patch_unity.py`/`unity_fs.py`; Addressables: `addressables.py`.
- Naninovel: extract ở `extract_naninovel.py`, patch ở `patch_naninovel.py`; script/object route phải có locator và read-back proof.
- Unity UI/TextAsset: dùng extract/patch Unity generic, không nhét identity game cụ thể vào raw patch.
- Worker payload/lifecycle: `vntext_worker/protocol.py` + `task_runners.py`, đối chiếu `WorkerEvent.cs`/`PythonWorkerHost.cs`.
- WPF binding/command/state: `MainViewModel` partial đúng trách nhiệm + `WorkflowStatus`/`WorkerPaths`; không đổi tên public property/command nếu chưa có migration.
- Release/portable: `release/publish.ps1`, `make_venv_portable.py`, `prune_worker_venv.py`, `release_verify.py`, `WorkerPaths.cs`.
