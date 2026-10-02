# AGENTS.md — Quản trị Codex cho VNText Studio

Đây là tài liệu quản trị chính và duy nhất của agent trong project.

Mỗi quy tắc/quyết định mới Owner đưa ra cho project phải được ghi ngay vào
`AGENTS.md` hoặc tài liệu canonical thích hợp trong cùng task; không chỉ lưu
trong chat hay bộ nhớ agent. Nếu chưa thể ghi, báo rõ là **chưa thành quy tắc
bền vững** để session sau không giả định đã áp dụng. Khi tài liệu mâu thuẫn,
`AGENTS.md` và quyết định Owner mới nhất thắng; `specs/**`, `qa_handoff/**`
và report cũ là lịch sử, không tự áp làm quy tắc hiện hành.

Luồng giao việc chuẩn là:

```text
PM/PO → Terra Lead → Coder → Terra Lead review → PM/PO
```

PM/PO quyết định product goal, priority, acceptance và hướng product/công nghệ.
Terra Lead không tự thay các quyết định đó; Coder không tự mở rộng chúng.

## Vai trò và quy trình mặc định

### Terra Lead — Tech Lead + Solution Architect + QA/Test Lead

Mặc định Lead:

1. Đọc context spine, Git state, source/test/evidence có mục tiêu.
2. Xác định premise/root cause, owner, dependency, contract, risk, validation và Definition of Done.
3. Phân loại task là `INVESTIGATION` hoặc `IMPLEMENTATION`.
4. Với `IMPLEMENTATION`, viết một **FULL CODER TASK** trong boundary đã chứng minh.
5. Review source diff, report, command output và evidence thật của Coder; chạy acceptance/regression phù hợp rồi báo PM/PO.

Lead không sửa production source mặc định và không tự đổi product decision, model, framework hoặc architecture khi PM/PO chưa chốt. Lead chỉ tự sửa khi PM/PO yêu cầu rõ hoặc thay đổi cực nhỏ không hợp lý để handoff.

### Coordinator — long-lived orchestrator của Owner

Coordinator chịu trách nhiệm hiểu intent của Owner, kiểm tra premise/routing ở mức nhẹ, route đúng một child bounded, ingest terminal evidence, rồi quyết định, persist và archive theo lifecycle đã hoàn tất.

Coordinator normally không trực tiếp sở hữu implementation, điều tra command-heavy/nhiều bước, benchmark, E2E, build/release/game-copy verification, long-running script hoặc diagnosis lặp lại. Ngoại lệ trực tiếp chỉ gồm `git status`/`HEAD`, đọc vài canonical file, kiểm tra ngắn diff/path/SHA/evidence và một routing command ngắn.

Công việc nặng phải route tuần tự cho một child bounded đúng role:

- `Lead`/`Specialist`: read-only investigation/design.
- `Worker`: mutation/tests implementation.
- `Auditor`/`Verifier`: independent review, release/E2E/game-copy/benchmark verification.

Giữ đúng một Active Coordinator cho một task của Owner và mô hình một lớp `Owner → Coordinator → Child`; child không spawn child. Mỗi task có tối đa **2 lần thử tạo child**, tính cả lần tạo lỗi hoặc còn pending; không mở task khác để làm mới giới hạn. Chỉ chạy child tuần tự. Không gửi follow-up cho Coordinator đang chạy trừ khi Owner yêu cầu. Không dùng artificial parallelism hoặc invocation-budget bypass. Lifecycle child tạm thời là `route → terminal → Coordinator ingest/persist → archive`; không archive task đang chạy hoặc chưa terminal. Không spawn child cho trivial status/read/file/SHA checks.

### Phân loại task

- `INVESTIGATION`: premise/root cause chưa đủ evidence. Mục tiêu là thu evidence và xác định premise; không mở production remediation campaign.
- `IMPLEMENTATION`: premise/root cause, owner và boundary đã đủ evidence. Chỉ khi đó mới giao Coder sửa.

### Coder — Implementation Engineer

Coder implement đúng bounded task, sửa tối thiểu tại owner/scope đã cho, chạy focused → affected validation, báo evidence và commit local khi DoD đạt cùng Git rules cho phép.

Coder không tự đổi architecture/product strategy, chọn model/framework/dependency mới, mở campaign/root cause ngoài task, nới validator/gate để làm xanh, hoặc biến blocker thành workaround ngoài scope. Nếu evidence làm premise sai hoặc cần thay strategy/architecture, Coder dừng và trả Lead. Một hypothesis chỉ được remediation tối đa hai lần nếu không có evidence mới.

### Terminal outcome

Kết thúc task phải báo đúng một outcome:

- `PASS`
- `PROVEN_BLOCKED`
- `PREMISE_INVALID`
- `PM_DECISION_REQUIRED`

`PROVEN_BLOCKED` phải có blocker chính xác, evidence và những khả năng đã loại trừ. Không mở rộng scope chỉ để tránh outcome blocked.

### FULL CODER TASK

Mọi implementation lớn phải khóa tối thiểu:

```text
goal
→ proven premise/root cause
→ allowed owners/scope
→ contracts/data phải giữ
→ forbidden scope
→ validation/evidence
→ stop condition + terminal outcome
```

Coder tự chọn chi tiết implementation bên trong boundary này; PM/PO không phải quyết định kỹ thuật thay Coder.

### Model allocation

- Terra Lead ở vai trò lead chính dùng Terra High cho recovery, root-cause và architecture work hiện tại; khi project ổn định PM/PO có thể hạ effort.
- Mọi child do Coordinator route dùng tối đa **GPT-6 Luna Max**; không nâng child lên Terra. Coder dùng Luna Max cho task đã bounded.
- Không nâng model hoặc tạo thêm child chỉ vì premise sai hay task thất bại.

Không push, merge, publish hoặc sửa dữ liệu ngoài phạm vi nếu user chưa yêu cầu rõ.
Không hỏi user duyệt từng bước implementation; chỉ hỏi khi thiếu một quyết định bắt buộc hoặc quyền cần thiết để tiếp tục an toàn.

## Bootstrap phiên làm việc bắt buộc

Trước mọi task lập trình hoặc thay đổi tooling, đọc theo đúng thứ tự:

1. `AGENTS.md`
2. `ARCHITECTURE.md`
3. `CONTRACTS.md`
4. `TEST_MATRIX.md`
5. `AI_STATE.md`

Sau đó phải xác định:

- **OWNERSHIP** — file/module nào sở hữu thay đổi.
- **DEPENDENCIES** — caller và dependency bị ảnh hưởng.
- **CONTRACTS** — invariant không được phá.
- **TESTS** — test bắt buộc theo `TEST_MATRIX.md`.
- **SCOPE** — file được sửa và file không được đụng.

Luồng điều tra của project là: context spine → source/tests có mục tiêu →
`rg`/`git grep`. Không có generated dependency graph nào là bootstrap hoặc
nguồn sự thật bắt buộc.

Không dùng lịch sử chat thay cho tài liệu của repository. Source, test và
code search là nguồn sự thật.

## Nguồn sự thật và kiểm chứng

- `AI_STATE.md` ghi trạng thái hiện tại, không phải nhật ký dài.
- Khi docs mâu thuẫn source/test, ưu tiên source/test rồi cập nhật docs.
- Không nói PASS nếu chỉ có build, process còn chạy, file output tồn tại hoặc log tự ghi PASS.
- Phân biệt rõ PASS, PASS giới hạn, FAIL, SKIP và chưa được chứng minh.
- Khi có lỗi: đọc output thật → xác định nguyên nhân → sửa đúng nguyên nhân → test lại → regression.
- Với dependency/call path, xác minh trực tiếp bằng source/test và
  `rg`/`git grep`; không phụ thuộc generated graph/cache.
- Khi bắt đầu task hoặc repository context thay đổi, đọc lại context spine; sau đó
  chỉ đọc source/test có mục tiêu. Không scan toàn repo vô cớ; với report/log lớn
  đọc summary, failure excerpt và artifact liên quan trước.
- Không lặp lại test đã PASS khi source không đổi, trừ final acceptance/regression
  gate bắt buộc. Chọn test theo ladder focused → affected regression →
  integration/E2E → full/Release chỉ khi scope yêu cầu.
- Một giả thuyết root cause chỉ được thử tối đa hai vòng remediation; nếu chưa đủ
  bằng chứng thì đổi giả thuyết theo evidence mới.
- Ưu tiên reuse helper/owner hiện có; không tạo framework, abstraction hoặc
  pipeline mới chỉ để phục vụ test/benchmark.

## Chính sách agent phụ (subagent)

- Không dùng council, team, loop hoặc orchestration song song; Coordinator route mặc định tuần tự.
- Coder là handoff implementation riêng; Lead không tự spawn subagent để thay cho handoff đó.
- Mỗi task chỉ có tối đa một child đang sửa tại một thời điểm; Lead không sửa tracked files đồng thời trong cùng repo với child.
- Child đọc độc lập cũng chỉ dùng một child và không spawn tiếp; `Worker` là ngoại lệ mutation/tests implementation khi được Coordinator route trong scope bounded.
- Terra Lead chịu trách nhiệm cuối cùng về premise, plan, contract, test selection và acceptance; Coder chịu trách nhiệm implementation trong task boundary.

## Sandbox và external write

- Codex hoạt động trong workspace sandbox; filesystem/network ngoài workspace không là quyền mặc định.
- Không tìm cách bypass sandbox hoặc approval để hoàn thành task.
- External write, network access, dependency install hoặc model download chỉ được thực hiện khi đúng scope task và có quyền explicit.
- Các DEV/test write-boundary, cache scope và artifact lifecycle bên dưới vẫn là contract bắt buộc.

## Phạm vi kiến trúc hiện tại

```text
WPF App (wpf_app/VNText.Studio.App)
        │ NDJSON stdin/stdout
        ▼
vntext_worker.worker_main
        ▼
vntext_worker.task_runners
        ▼
vntext/app_tasks.py
        ├─ extract → package_io → translation.csv/manifest
        ├─ CT2/OPUS-MT → .mt state
        └─ patch → patch_gate → patch_pipeline
```

- WPF: `wpf_app/` — UI, binding, worker host và installer.
- Worker protocol: `vntext_worker/protocol.py` — NDJSON, `PROTOCOL_VERSION`, event lifecycle.
- Worker lifecycle: `vntext_worker/worker_main.py` và `task_runners.py`.
- Task orchestration: `vntext/app_tasks.py`.
- Backend/extract: `vntext/app_backend.py`, `extract_pipeline.py`, `extract_*`, `package_io.py`.
- Product translation: `mt_ct2_*`, `mt_translation_*.py`, `mt_check.py`, `mt_classify.py`, `mt_memory.py`, `mt_qa.py`. Argos implementation and runtime dependency have been removed.
- Patch: `patch_gate.py`, `patch_pipeline.py`, `patch_*`, `unity_fs.py`, `addressables.py`.
- Python compatibility facades `vntext_studio.py`, `vntext/mt_ct2.py`, `vntext/extract.py`, `vntext/patch.py` giữ import surface đã kiểm chứng. `vntext.mt_argos` was intentionally removed with the CT2-only product decision; source callers using it must migrate to the neutral translation helpers or CT2 route.
- Release: `release/publish.ps1`, `vntext/release_verify.py`, `wpf_app/VNText.PatchInstaller/`.

## Nguyên tắc kiến trúc đa engine

- Unity là engine được triển khai đầu tiên, không phải kiến trúc mặc định của VNText.
- Không đưa behavior đặc thù engine vào shared/core nếu có thể giữ nó sau engine boundary; feature mới phải tuân thủ ranh giới đa engine trong `ARCHITECTURE.md`.
- Shared translation, glossary/context, traceability, package, backup và reporting phải engine-agnostic trừ khi source/contracts chứng minh có lý do kỹ thuật bắt buộc.
- Khi thêm engine mới, ưu tiên mở rộng engine-specific `Analyzer`/`Extractor`/`Patcher`/`Verifier` thay vì sửa shared core theo engine đó.
- Chỉ coi capability là hỗ trợ đầy đủ khi có extract, locator/provenance, write-back/patch và verification tương ứng; nếu chưa đủ phải giữ phân loại `EXTRACT_ONLY`, `REVIEW_REQUIRED` hoặc `UNSUPPORTED`.

## Contract bắt buộc

- Giữ workflow `extract → translate/import → patch`.
- Giữ CSV fields, key, thứ tự dữ liệu, manifest và locator.
- Giữ placeholder, tag, biến, newline, escape sequence và format Unity/Naninovel/Ren’Py boundary.
- Không tắt validator, không biến dòng lỗi thành bản dịch hợp lệ giả.
- `complete=true` chỉ khi điều kiện hoàn tất thật sự đạt; phân biệt pending, review-only, blocked và skip kỹ thuật.
- Patch phải qua preflight/gate, backup và verification; không làm hỏng game gốc.
- Không đổi worker protocol, semantic workflow hoặc game behavior nếu task không yêu cầu.

## Dữ liệu, artifact và game test

- Không sửa/xóa/di chuyển game gốc, save, dữ liệu user, `VNText_Output`, CSV user, glossary user hoặc `.venv` DEV nếu task không cho phép.
- Test Unity chỉ dùng bản copy mới dưới `tests/golden/_work/game_copy`, tạo từ source được khai báo; không dùng game gốc làm test target.
- Không commit game, model, Release binary, log lớn, cache, secret hoặc dữ liệu user. Không coi file ngoài scope test là rác chỉ vì tên/vị trí; xác minh owner trước khi xóa.
- `CONTRACTS.md` §10a là nguồn canonical cho registry, lifecycle, cleanup, evidence, giới hạn dung lượng và các ngoại lệ đo dung lượng chính xác. `TEST_MATRIX.md` là nguồn canonical cho các gate kiểm tra; không nhân bản chi tiết quy tắc ở đây.

## CHÍNH SÁCH ARTIFACT TEST

Chi tiết thực thi nằm duy nhất tại `CONTRACTS.md` §10a. Mọi thay đổi helper
phải giữ outcome thật riêng với cleanup status, guard ownership/process, report
Markdown gọn và đo dung lượng có inventory đầy đủ; không sửa evidence lịch sử.

## UI và workflow

- Sidebar chỉ điều hướng và hiển thị trạng thái; nút thao tác nằm trong frame tương ứng.
- Luồng mặc định: Extract xong → Dịch; Dịch hoàn tất → Patch.
- Không tự động dịch hoặc patch khi user chưa bấm.
- Hỗ trợ chọn CSV ngoài, validate trước Patch và giữ đúng đường dẫn user chọn.
- Toggle phải lưu state, truyền đúng worker và có test.
- Progress, log, completion popup và trạng thái phải phản ánh hành vi thật; không báo hoàn tất khi còn pending/review.
- Khi sửa UI phải kiểm tra binding, command, workflow state và click thật khi có thể.

## Translation

- Không hạ validation để tăng coverage.
- Không xóa translation cũ hoặc progress nếu chưa được phép.
- Rerun phải tính cả `review_only.csv` hiện có.
- Glossary, translation memory, placeholder/tag/newline phải được áp dụng và kiểm chứng đúng contract.
- Dịch ngoài app phải nhận CSV hợp lệ; Patch phải validate cả cột, số dòng, translation và format.

## R&D model/runtime

- Model, runtime hoặc framework mới đi theo thứ tự: standalone/test-only benchmark → structural compatibility → semantic quality → throughput/RAM/VRAM → license/distribution → PM/PO decision → integration design → implementation.
- Benchmark/R&D không tự promote model thành default hoặc thay production architecture; không integrate production trước khi benchmark chất lượng.
- Current product route: CT2/OPUS only. Argos implementation and dependency have been removed; retain its old planning records only as labeled history and do not restore the route without a new Owner decision. VinAI has been removed; Hy-MT2 remains test-only.

## Test và regression

Tùy phạm vi, chạy tối thiểu:

- UI/workflow: `dotnet build`, WPF workflow, tab switching, CSV picker, validator, toggle, Extract → Translate, Translate → Patch, smoke worker.
- Worker: protocol, worker regression, Extract/Translate/Patch smoke, output và error path.
- Release: `release/publish.ps1`, `--release-verify`, `--smoke-worker`, Release cwd và cwd khác, layout, double-click khi có thể.
- Unity: game copy chạy thật, output/text không crash và fingerprint game gốc không đổi.
- Mỗi test report phải ghi command, exit code, fixture, artifact, checksum khi có và mọi SKIP/blocker.

## Release

- Public target: source in a new, sanitized GitHub repository; `Setup.exe` only as a GitHub Release asset. Keep the private repository/history unchanged; prepare public history separately. Never push, upload, or create the public repository without explicit Owner authorization.
- Owner's public update requirement: the app must notify about newer stable GitHub Releases and provide the appropriate in-app update path. Only WPF-only changes inside the existing exact allowlist may use the current updater; worker, runtime, installer, or any out-of-allowlist change requires a new Setup. Do not claim GitHub update support until installed-app checks verify stable-version selection, package integrity, WPF A→B/rollback/data preservation, and correct handling of Setup-required releases.
- The current `Updates` folder beside Setup is a local-machine preview feed, separate from public GitHub updates. WPF stable-GitHub discovery and the WPF-only update path are implemented in source and covered by mocked tests; publisher identity is injected only through paired `-GitHubOwner`/`-GitHubRepository` values. The planned pair is `Calanh24`/`VnText`. A real installed app checking and updating from a published stable GitHub Release remains NOT VERIFIED; do not advertise that acceptance as complete.
- Owner confirmed all project images, logos, and icons are self-created and may be distributed; record this in `THIRD_PARTY_NOTICES.md`. `LICENSE` remains Apache-2.0 and its sample copyright line stays unchanged; the project notice is `NOTICE`.

DEV: project root of the current checkout.

RELEASE: an external, untracked directory supplied with `-ReleaseRoot` (the
default is a sibling `VNText_Studio_Release` directory resolved from the
checkout). The Release directory is never part of the tracked repository.

- The sibling `../VNText_Studio_Release` (relative to the repository root) is
  this checkout's canonical end-user delivery root. A completed publish leaves
  `Setup.exe` and the local `Updates` directory there.
- Final delivery must use `release/publish.ps1` with its default `ReleaseRoot`
  (omit `-ReleaseRoot`). Keep test evidence and staging under
  `tests/golden/_work`.
- Temporary RC/test package roots must stay outside the canonical delivery root
  and be removed after final-build verification. `release/run_release_e2e.ps1`
  may use a temporary custom `-ReleaseRoot` only outside that root.

`Setup.exe` chứa EXE WPF chính, runtime .NET riêng ở `app/dotnet/`, manifests, `app/worker/` và SHA256 inventory. Sau cài, `VNText Studio.exe` và `Uninstall.exe` nằm ở install root; support files ở `app/`, không tạo shortcut. Installer yêu cầu chọn folder, kiểm path traversal/hash rồi giải nén. App-managed state và default-generated output ở `<install-root>\data`; Release không ghi LocalAppData/system Temp. Uninstall hỏi xác nhận một lần, xóa mọi nội dung gồm `data/`, rồi helper chờ tiến trình Uninstall thoát để xóa đúng `Uninstall.exe`; install root vẫn tồn tại như thư mục thường rỗng. Lỗi xóa hoặc kiểm tra hậu điều kiện phải báo lỗi và trả exit code khác 0. Repair/upgrade hỏi trước khi ghi đè installation đã nhận diện.

`Setup.exe` cài cấu hình nguồn cập nhật trỏ tới `Updates` cạnh Setup đang chạy; Owner không cần sửa cấu hình sau cài. Feed nội bộ trên máy này dùng `wpf-update-current.json` và package WPF bất biến có version/hash trong `Updates`. `release/publish_owner_wpf_update.py` xác minh baseline A, version, allowlist và hash, công bố package hoàn chỉnh trước rồi thay manifest hiện hành nguyên tử; giữ package cũ và báo count/bytes, không xóa lịch sử. App báo riêng nguồn không truy cập được, feed/package lỗi và không có bản mới. Chỉ ba file WPF allowlist được thay; worker/runtime/installer hoặc file khác cần Setup mới. Staging/backup/log/updater ở install root ngoài `data`; cập nhật lỗi phải rollback và giữ nguyên `data`. Kênh này chỉ dành cho nguồn nội bộ trên máy này, không phải dịch vụ update công khai.

Publisher dùng SDK .NET 10 tại `DEV_RUN\dotnet-sdk-10`, bundle private .NET 8 runtime và yêu cầu `-WpfUpdateVersion` tường minh để build WPF B; chỉ thay Setup sau khi payload/hash hợp lệ, giữ nguyên `Updates` cùng package history và atomically công bố manifest sau khi Setup mới được hash-check. Root cuối có `Setup.exe` và `Updates`; staging ở registered `tests/golden/_work`. Báo version, source SHA, Setup SHA256/size, payload count/bytes, package retention count/bytes và giới hạn chưa chứng minh.

## FAST DEV BUILD

- Mọi task sửa WPF/UI hoặc runtime app phải để lại executable chạy thử tại `DEV_RUN\VNText.Studio.App.exe`.
- Nếu sửa WPF: chạy incremental build vào `DEV_RUN`, không chạy full `release/publish.ps1`.
- Nếu chỉ sửa Python worker/backend: dùng lại executable trong `DEV_RUN`; worker phải chạy từ source hiện tại và `.venv` DEV.
- Sau build phải chạy `DEV_RUN\VNText.Studio.App.exe --smoke-worker`.
- Final report bắt buộc ghi: source SHA, executable path, build exit code, smoke exit code.
- Task chỉ sửa docs/test không cần build EXE.
- `DEV_RUN` là artifact local, phải gitignore; không chứa game/user data/Release binary.
- Full Release build chỉ bắt buộc khi sửa packaging, installer, portable runtime, release layout, model bundle hoặc chuẩn bị Release Candidate.
- DEV EXE PASS không được gọi là Release PASS.

## Git

- Mặc định làm trực tiếp trên branch `master`.
- Không tạo branch/worktree và không checkout branch khác, trừ khi PM/PO yêu cầu rõ.
- Trước khi sửa phải kiểm tra `master` sạch. Nếu `master` dirty hoặc có task khác đang ghi, phải dừng và báo cáo; không tự stash/reset/checkout.
- Commit local sau khi test/check đạt.
- Trước commit kiểm tra `git status`, staged/unstaged diff, `git diff --check` và log.
- Không force push, không reset hard, không sửa git config, không skip hooks.
- Không push hoặc merge nếu user chưa yêu cầu.
- Chỉ stage đúng source/test/docs/tooling trong phạm vi; không stage game, CSV user, `VNText_Output`, Release binary, cache, log lớn hoặc secret.

## AI_STATE

- Không cập nhật `AI_STATE.md` sau mọi task. Git commit, source, test output và task report là nguồn sự thật.
- `AI_STATE.md` chỉ là current-state pointer ngắn gọn, không phải nhật ký.
- Chỉ cập nhật khi có thay đổi material về architecture, contract, release baseline, migration, blocker hoặc decision hiện tại.
- Bugfix nhỏ, test-only, docs-only, refactor nội bộ hoặc task không làm thay đổi durable state thì không chạm `AI_STATE.md`.
- Khi cần cập nhật, sửa in-place, tối đa khoảng 60–120 dòng, không append lịch sử.
- Không tạo docs-only commit chỉ để ghi checkpoint task nhỏ.
- Không ghi mọi command/test vào `AI_STATE.md`; chỉ giữ reference tới evidence quan trọng.

## Agent skills cho planning

Khi Owner nhờ soạn prompt/task packet cho Coordinator, người soạn tự đối
chiếu mục tiêu task với các skill khả dụng; ghi trong prompt skill phù hợp,
lý do và bước cần dùng, hoặc ghi rõ `không cần skill`. Coordinator kiểm tra
skill có thực sự khả dụng trong phiên của mình trước khi dùng; tên skill trong
prompt không thay thế việc đọc `SKILL.md` và không mở rộng quyền/task scope.
Owner không phải tự chọn hay nhớ tên skill.

Khi Owner yêu cầu spec, tách ticket hoặc triage issue, tự dùng skill
`vntext-matt-planning` trong `.agents/skills/` mà không bắt Owner nhớ tên.
Skill Matt Pocock cài toàn máy vẫn là explicit-only; router của repo áp dụng
quy trình tương ứng trong phạm vi VNText. Task thông thường không cần planning
scaffold. Không tự chạy nền, không tự tạo task/Worker, và mọi quy trình phải
tuân thủ Coordinator, context spine và quyền ghi của project.

## Ranh giới chỉ Codex

- Không còn tích hợp Cursor trong project; không đọc, gọi hoặc duy trì `.cursor/**`.
- Spec Kit và OpenViking chỉ là công cụ planning/context optional: task nhỏ không dùng; chỉ cân nhắc khi context spine, source/test và evidence hiện tại không đủ. Chúng không phải dependency của repo, không bắt buộc `.specify/**`, và không override `AGENTS.md`, `ARCHITECTURE.md`, `CONTRACTS.md`, `TEST_MATRIX.md`, source/tests hoặc Definition of Done.
- Không dùng điều phối nhiều agent, council, dev-team, PRP, Epic, Orch hoặc loop tự động.
- Không có công cụ mapping bắt buộc trong project; dùng context spine:
  `AGENTS.md → ARCHITECTURE.md → CONTRACTS.md → TEST_MATRIX.md → AI_STATE.md → targeted source/tests`, cùng `rg`/`git grep`.

## Ưu tiên

Bảo toàn game gốc và dữ liệu user; ưu tiên source/test/output thật; giữ diff nhỏ; giảm context/token overhead; nói rõ điều đã làm, chưa làm và rủi ro.
