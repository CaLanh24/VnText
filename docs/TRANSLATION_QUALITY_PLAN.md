# Cải thiện chất lượng dịch sau bản phát hành đang chuẩn bị

## Owner kích hoạt Phase 1 — 2026-10-19

Owner authorizes phase 1 after the UI and release work closed: create a public,
agent-authored synthetic EN→VI benchmark of about 100 sentences, evaluator
tooling, and one actual CT2/OPUS baseline on the model already present in
`.dev-env`. This is evaluation foundation only; it does not change the product
route, model, WPF, protocol, or validators and does not claim translation
improvement, product-wide quality, human gold, or human acceptance.

### Protocol frozen before the first baseline

- One frozen 100-row dataset is split before model execution into 80
  `development` and 20 `held_out` rows. The six groups and split counts are:
  dialogue 12/4, idioms 13/4, address/register 13/4, UI 13/4, terminology
  15/2, and protected tokens 14/2 (development/held-out). Every row has a
  synthetic source, explicit scenario boundary, stable ID, and split. Rows in
  one scenario group stay in one split. Dataset validation rejects duplicate
  IDs, NFKC/case-fold/punctuation-normalized duplicate sources, and any group
  crossing the split boundary. The benchmark does not use the existing frozen
  30-row benchmark as held-out data.
- Provenance is `author=agent-generated synthetic`,
  `rights=generated-for-project`, and
  `semantic_review_status=draft/unreviewed`. No game, user, CSV, web, or
  copyrighted benchmark sentence is included. The dataset contains no gold
  Vietnamese reference. Frozen dataset SHA-256 is
  `7f75108ff031022f94b5a68965eebc6f0a99ff37d3fd1804ebec4c6d2fe9242d` and
  baseline protocol SHA-256 is
  `651edf8ed92675b533d0f3e33758aa244ec0160528090eab26407e8b17b45702`; both
  were computed by `tests/tools/translation_quality_phase1.py validate-dataset`
  before baseline execution. The protocol includes the frozen split/rubric and
  route, declared model revision, local model path, resource limits, and metric
  definitions.
- The rubric keeps semantic review separate from structural checks:
  meaning error, omitted meaning, added meaning, address/register, terminology,
  and naturalness are separate human review dimensions. Structural checks
  separately record protected-span, markup, placeholder, and newline failures.
  Because no independent semantic reviewer or human acceptance is available in
  phase 1, semantic quality and acceptance remain `UNKNOWN`; reference matching
  and structural success cannot produce a semantic score.
- The baseline is one offline CPU run of the existing
  `vntext.mt_strategies.translate_row_ct2` protected/segmented route with the
  existing `Ct2Translator` and local INT8 OPUS model. It records raw
  model calls, restored route output, row disposition, source-identical output,
  structural results, failures,
  model initialization, per-row execution and translation-loop/overall wall
  time, process peak working set, local model file hashes and declared model
  revision, runtime, and machine CPU/OS. File hashes identify the bytes used;
  the repository revision is model metadata, not separate proof of how those
  local bytes were obtained. It does not apply glossary,
  translation memory, or context and therefore is not the full product
  translation workflow. No sentence is retried. Network/model download is
  disabled; one CPU thread is used. The run has a 900-second wall deadline and
  stops before another row if observed peak working set reaches 1 GiB. The
  model/cache in `.dev-env` is read-only. Output is retained as compact evidence
  under `DEV_RUN/translation-quality-phase1`; the evaluator stops at 840 seconds
  to leave cleanup room inside the canonical wrapper's 900-second hard timeout.
  Transient files are registered under `TEST_RUN` and cleaned by the canonical
  wrapper.
- A route return equal to its source is recorded as source-identical output,
  not as a successful translation or an inferred fallback; its raw model call
  remains visible when one occurred.
- Machine metrics are limited to route-return coverage/dispositions,
  source-identical output count, structural
  outcomes, latency, and measured memory. No BLEU/reference-match/LLM or other
  semantic proxy score is reported. Baseline output includes every row as a
  completed result or explicit failure/skip/not-run disposition; it never
  fabricates model output after an error or timeout.
- Coverage is intentionally narrow: terminology examples are mostly VNText and
  translation-tool concepts, UI examples are desktop labels/messages, and the
  dialogue is synthetic. This 100-row draft does not represent every game,
  engine, genre, or content type.

The 30-row frozen local benchmark tooling has a separate fixed-count, pinned
identity, and private runtime contract (`tests/tools/local_translation_benchmark.py`);
the 30-row worker sample exercises a different package/worker path
(`tests/tools/phase_c_ct2_sample.py`). Neither corpus is promoted or repurposed
as this benchmark's held-out set. Existing glossary/memory/context owners for
phase 2 are `vntext/glossary_v2.py`, `vntext/mt_memory.py`, and
`vntext/context_builder.py`; context sidecars remain `METADATA_ONLY` until a
separate test proves model use.

### Phase 1 baseline receipt — 2026-10-19

- Focused gate: the canonical wrapper ran
  `python -B -m unittest discover -s tests/unit -p test_translation_quality_phase1.py -v`;
  PASS, 10 tests, 0 failures/errors/skips/warnings. Dataset CLI validation also
  emitted valid JSON and PASS. Receipt: `DEV_RUN/translation-quality-phase1/focused-wrapper.json`.
- Actual baseline: one canonical-wrapper run of
  `tests/tools/translation_quality_phase1.py opus-baseline`; PASS in 23 seconds
  including cleanup, with 100/100 `ROUTE_RETURNED`, 0 row errors, 0 not-run,
  0 source-identical outputs, and 100 structural PASS. The report retained 140
  raw CT2 call records over the rows. These are route/structure measurements,
  not semantic scores or proof that every returned row is a good translation.
- Report: `DEV_RUN/translation-quality-phase1/opus-baseline.v1.json`, SHA-256
  `b92b2f9c6d6ca84c97e4eea05b0d5a50526460196e7bebf116e193af4f841c5b`.
  Wrapper/cleanup receipt:
  `DEV_RUN/translation-quality-phase1/baseline-wrapper.json`. The run used base
  Git HEAD `10873fc61db4f97db9a42d63fcac9f8b993e3570`; its uncommitted evaluator
  is bound by tool SHA-256
  `fd90586ea5d18eadc3cfd2b3cd0c762fdde22976d4ef1a46a14bb7263a8523fb`, plus
  the frozen dataset and protocol hashes above. This is not an exact-HEAD claim
  for the later source commit.
- Runtime/machine: Python 3.12.10, CTranslate2 4.8.1, Transformers 5.20.1;
  Windows 11, Intel Family 6 Model 198, 4 logical CPUs. Model declaration:
  `dekthedev/opus-mt-en-vi-ct2-int8`, revision
  `c22547827b876e8ee939d6a9363965e5c9f769e1`. The 33-file local tree hash was
  `964dd51bc39f391bee84fb94b8988073f6ee84188c986406ac9f7622080a90b4` both
  before and after the run. The revision is repository metadata; the local file
  hash identifies the bytes used.
- Measured latency: model initialization 13.361 s, sum of row executions
  5.404 s, translation-loop wall time 6.318 s, total run time 19.860 s.
  Windows PSAPI `GetProcessMemoryInfo` measured 202,620,928 bytes peak working
  set, under the 1 GiB stop threshold. No model download/copy or dependency
  installation occurred. Wrapper warning: Transformers recommends
  `sacremoses`; it was not installed. Transformers also reported PyTorch absent,
  but the local tokenizer and CTranslate2 CPU model completed the run.
- Wrapper cleanup PASS; `TEST_RUN` returned absent. Final project size was
  693,943,081 non-exempt bytes / 1,073,741,824 and 4,575,800,745 shared
  `.dev-env` bytes / 5,368,709,120.
- Semantic review and human acceptance remain `UNKNOWN` and `NOT_CONDUCTED`.
  Held-out rows have baseline outputs but no human gold or review; do not tune
  on them. Next step is independent review of development outputs, then a
  bounded experiment on the existing route before considering model changes.

### Coordinator acceptance and development review — 2026-10-19

Phase1 foundation PASS, semantic improvement NOT CLAIMED. Coordinator read the evaluator, focused and baseline receipts directly; dataset/tool/report hashes still match the receipts, and TEST_RUN is absent. DEV child stopped at its usage limit after the successful runs and before final handoff/commit; Coordinator took over the sole writer role and persisted the review. No second child/model was opened to bypass that limit. Evidence remains base10873fc plus the recorded task/tool/dataset hashes, not the eventual commit SHA.

Independent Coordinator agent review of development outputs (not human gold, no tuning on held-out outputs) found concrete semantic defects: DLG008 “save me a chair” becomes “lưu Tôi là một chiếc ghế…”, DLG012 loses “Do not run”, IDI001/005 render idioms as literal beans/cake, UI001 retains “Open”, and TERM013 mutates CSV to CNV. Structural100/100 does not establish semantic correctness. Raw calls for DLG008 receive only “Then” and “me a chair beside the back”, while UI001 receives only “the saved session”. Source inspection links this fragmentation to default lexical protection in `collect_spans`/`split_parts`; sentence-initial title-case name detection is a separate hypothesis. Model and preprocessing failures must be distinguished; no benchmark phrase lookup or validator relaxation is justified.

Next bounded Phase2 experiment is the existing CT2 route's treatment of ordinary lexical words. Preserve technical tokens/names/paths, glossary/memory contracts, validators and CSV schema. Predeclare comparison before changing the route; retain the frozen baseline and dataset, inspect development first and use held-out only after fixing the candidate. No new model, download, training, UI or Release is authorized by this experiment.

Phase2 trial A, declared before execution: use a test-only scoped override of `split_parts(..., protect_lexical=False)` for the same strategy route. All other policies/model/dataset remain fixed. This tests lexical fragmentation only; title-case name detection remains unchanged. Run the same100 rows once, retain original baseline untouched, and inspect development before opening held-out row outputs. Admission requires zero new structural failures, zero row errors and unchanged model bytes; a useful candidate must improve at least five development examples on independent Coordinator agent review without a new severe meaning loss on a reviewed development example. Agent review is qualitative evidence, never human acceptance; absent human gold, trial success alone cannot promote a product/model. Report failures/regressions as observed. One run, offline, same840/900-second and1GiB peakWS/default1GiB artifact/shared5GiB limits; canonical wrapper/terminal cleanup. No product runtime edit or DEV executable build is needed for this test-only trial.

### Phase2 trial A acceptance — reject unconditional lexical-off change

Actual `translation_quality_lexical_trial.py` execution on base28a4fd7 plus the recorded trial-script hash completed100 rows/117 raw calls, zero row errors,100 structural PASS and unchanged model tree. Total9.109s/init2.435s/peakWS201506816 bytes; startup timing is warm-cache and not a speedup claim against the baseline. Final wrapper child0/outer0/cleanupPASS/TEST_RUN absent; optional tokenizer warning remains. The first wrapper failed before model execution because the baseline evaluator only admits its exact owned report path. The trial now scopes that path to its own separate evidence filename; neither the frozen baseline nor the product report guard was overwritten. Original failed receipt retained.

Coordinator development-only qualitative review found clear improvements for DLG008 (save a chair), DLG012 (preserves “Do not run”), IDI011 (same page), UI006 (unsaved changes), and other examples. It also found new omissions: ADDR008 loses “the corrected page”, and TERM011 loses “context”. Consequently the predeclared no-new-severe-meaning-loss condition fails. Outcome **PREMISE_INVALID for treating unconditional lexical-off as an acceptable fix**, not for the narrower finding that lexical fragmentation harms some sentences. Do not ship this override, weaken validators, add benchmark phrase replacements, or claim better product/model quality. Held-out row outputs were not opened for tuning after this development gate failed.

Evidence: `DEV_RUN/translation-quality-phase1/{lexical-trial-wrapper.json,lexical-trial-wrapper-final.json,lexical-trial-a.v1.json,coordinator-review.json}`; the review includes14 before/after development observations and exact report/script hashes. Phase1 foundation remains PASS. Next work in step2 remains a bounded full-product-route glossary/memory/input-policy comparison with verified semantics; the failed ablation does not justify skipping to model promotion or training. The public app and release0.1.8 are unchanged.

### Phase2 full-pipeline comparison protocol — declared 2026-10-19

Owner requests continuation; Coordinator remains sole writer because the previous DEV child terminated at its usage limit. Clean base f87cebd; no retry/new child to bypass usage. Evaluation-only owners: one script `tests/tools/translation_quality_pipeline_trial.py`, this plan and AI_STATE. Product code/CSV schema/model/UI/release remain unchanged. One canonical-wrapper CPU/offline run, three independent synthetic packages from the frozen100 rows: (A) no supplied assistance; (B) six package glossary terms; (C) the same glossary plus two explicitly agent-reviewed draft memory fixtures from development. Same plain-text import boundary and stable IDs, independent package caches; no game copy or user data. Direct production `run_ct2_translate` exercises classifier, batch/retry, glossary, memory, cache, validation and CSV write-back, not worker transport or game patch proof.

Freeze glossary before execution: checksum→mã kiểm tra, manifest→bản kê khai, cache→bộ nhớ đệm, glossary→bảng thuật ngữ, CSV→CSV, placeholder→biến giữ chỗ. No complete benchmark sentence enters the glossary. Memory fixtures DLG008→“Vậy hãy để dành cho tôi một cái ghế bên cạnh cửa sau.” and IDI005→“Đối với Lin, câu đố đầu tiên rất dễ.” are deliberately in-sample, agent-reviewed synthetic data, not human gold. Their reuse demonstrates exact consistency only; exclude both from any generalization/improvement claim. Held-out gets no memory seeds and is not inspected for tuning; source/split/dataset hash cannot change.

Report all100 rows per arm including blocked/empty dispositions, explicit pipeline result, structural/quality gate reasons, assistance identities, memory hits inferred only from lookup plus exact output, and untouched source/order/schema checks. Structural PASS is not semantic acceptance. Gate existing glossary/context/cache tests before the run; then directly review development changes, separate assisted repetition from new-text term consistency, and reject regressions. Same840/900s and1GiB observed peakWS bounds; default1GiB project/shared5GiB caps. Registered temporary packages only in TEST_RUN, compact receipts under DEV_RUN/translation-quality-phase2; TEST_RUN absent at terminal. No new dependencies/downloads, product edits, full regression, executable build or publication for this evaluation-only task.

Phase2 measured baseline: focused22PASS/child-wrapper0/no skips/warnings; actual three production-pipeline arms each wrote98/100, blocked2, complete=false, zero written structural failures, separate caches/hits0, original source/order/schema unchanged. Memory arm has exactly2 lookup/output matches (both deliberately in-sample), only IDI005 changes relative to glossary arm; DLG008 was already corrected by the full pipeline. Glossary arm changes development TERM005 but leaves requested checksum/cache terms absent. Trace proves initial masked outputs mutate ZZG carriers, then retries accept unassisted translations without requested terms (TERM001/004). Parent source inspection: `collect_spans` recognizes internal sentinels when excluding lexical/name matches but omits them from emitted opaque technical spans, so batch fragment translation sends those carriers to the model. This is a concrete prerequisite defect in explicit glossary protection, distinct from the rejected generic lexical ablation. No semantic improvement or whole-product quality claim follows from98 applied rows. Report `DEV_RUN/translation-quality-phase2/pipeline-arms.v1.json`, wrapper `pipeline-wrapper.json`; peakWS342425600 bytes, model unchanged, cleanupPASS/TEST_RUN absent. Evidence basef87cebd plus recorded script/dataset hashes.

Next bounded remediation under Owner's activated existing-route plan: emit internal sentinel spans as opaque technical spans in `vntext/mt_translation_safety.py`; targeted batch glossary regression in `test_user_glossary.py`, existing strategy/structural/glossary/cache/worker regression, then repeat exactly the frozen three-arm comparison to a separate evidence file. No model, generic lexical, validator or sentence-specific translation changes. Acceptance: fake hostile adapter never receives glossary carriers, repeated/multiple term targets and source structural tokens survive; real glossary arm retains requested development terms with no extra blocked/structural-failing rows or new severe reviewed development defect. Trial source names/protected lexical policy otherwise unchanged. Runtime source edit requires one DEV build + configured worker smoke. Default1GiB/shared5GiB budget, no game copies/download/Release/push.

### Phase2 remediation acceptance — candidate rejected, original product restored

The hostile-model regression first failed as expected (one failure, cleanupPASS). Candidate opaque spans + cache-span-schema2 then passed59 focused strategy/structural/glossary/context/cache tests with child/outer0, no skips/warnings, cleanupPASS. The repeated real three-arm run also completed with98 written/2blocked per arm, zero written structural failures, model unchanged and peakWS365150208 bytes; unassisted outputs were identical to control. Nevertheless development comparison failed the semantic acceptance: TERM001 now interprets patch as a wound, TERM014 interprets stores as shops, and TERM004 can still lose the requested cache wording on retry. Do not trade technical marker retention for worse meaning or claim a model improvement.

Outcome PREMISE_INVALID for promoting this implementation as the quality fix. Coordinator reverted only the task's runtime/cache/test edits with exact inverse patches; these four files match clean base4c72525. Retained candidate patch/source hashes, red/focused/comparison receipts and14 preceding/5 current development observations remain under DEV_RUN, not shipped in the app. No held-out row output tuning, no new model/dependency, no Release/push. Candidate failed before broader regression/DEV build gate, so neither is claimed; final change is evaluation/docs only and existing DEV executable remains current. Evidence `DEV_RUN/translation-quality-phase2/{focused.json,pipeline-wrapper.json,pipeline-arms.v1.json,glossary-premise-red.json,opaque-focused.json,opaque-pipeline-wrapper.json,pipeline-arms.opaque-fix.v1.json,rejected-opaque-fix.patch,rejected-candidate-source-hashes.json,coordinator-review.json,REVIEW.md}`. Original failed and passing receipts are not relabelled. Memory assists exact consistency but provides no unseen-text quality proof; full pipeline still has independently observed idiom and meaning errors. Steps1–2 have measured results; model research is the next gated experiment, not automatic product replacement.

### Step3 concrete R&D proposal — approval pending, nothing downloaded

One candidate only: Tencent Hy-MT2-1.8B Q4_K_M GGUF, pinned repository revision `a0c709d9fac510f2c807aa3af52872340dc37a4a`, file1133080448 bytes, SHA256 `dc5f44fcf1fa496ee7ad725982c0c8c553a4de00259b53af84c4b89fb0c06699`. Official [model card](https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF) lists Vietnamese and context/terminology instructions; [license](https://huggingface.co/tencent/Hy-MT2-1.8B-GGUF/blob/a0c709d9fac510f2c807aa3af52872340dc37a4a/LICENSE.txt) is Apache2.0. These are upstream capability claims, not local quality/speed/RAM proof. Low-bit STQ kernel PR22836 is open; do not assume its ARM kernel is available on this Windowsx64 guest. Proposed standardQ4 runtime is official llama.cpp WindowsCPUx64 b11724 prerelease ZIP19667407 bytes/SHA2569f575bca009b1343fb710b11efb687d771e130ea97e119af1570372844f2aba1; architecture/build compatibility still requires local preflight. No CUDA, Torch or system install proposed.

Current shared dependencies4575800745 bytes plus model~1.13GB/runtime/extraction exceed approved5GiB. Request an explicit6GiB shared cap and download permission under AGENTS before any allocation. Artifact cap stays1GiB; one shared runtime/model, no duplicate model copies. VM has4GiB physical RAM/4logicalCPUs/no discrete GPU; observed freeRAM around0.5–0.8GiB is not inference readiness. Before model load, verify runtime architecture and RAM/headroom, impose bounded resources/time and stop if unsafe; actual Windows/latency/quality support remains UNKNOWN. No implicit permission to resize VM, change host/security, train, publish or replace OPUS. After approval, first small CPU preflight; only if viable compare source+context direct translation against OPUS-draft repair with the same context/model, frozen data and explicit semantic/structural review. No training until corpus rights/review and separate budget/stop-condition approval.

## Quyết định Owner — 2026-10-11

Hoãn đợt cải thiện chất lượng dịch và nghiên cứu huấn luyện tới sau khi phát hành bản đang chuẩn bị. Trước phát hành, ưu tiên chỉnh UI và luồng thông báo cập nhật theo `docs/UPDATE_UI.md`. Không mở chiến dịch model/huấn luyện song song với task UI/updater hoặc Release.

Đây là kế hoạch, chưa phải bằng chứng chất lượng hoặc quyền tải model, huấn luyện, thuê GPU hay sử dụng dữ liệu game. Version bản phát hành tiếp theo chưa được quyết định trong kế hoạch này.

## Premise hiện tại và giới hạn

- Route sản phẩm là CT2/OPUS-MT theo CONTRACTS §4/§4a; adapter, glossary, memory và cache đã tồn tại, cần tận dụng trước khi thêm hệ thống mới.
- Hai lượt kiểm game gần nhất chứng minh pipeline mẫu, không chứng minh chất lượng dịch toàn game. Evidence `DEV_RUN/two-game-report.md` tại checkpoint `3bbe595` ghi lỗi nghĩa như `sprang to my feet` và `Lewd Girl`; không đưa dữ liệu game riêng vào Git.
- QA cấu trúc và import Cloud Repair thành công không chứng minh bản dịch đúng nghĩa. Chỉ bản dịch đã được duyệt ngữ nghĩa mới có thể làm dữ liệu chuẩn.
- Context hiện là `METADATA_ONLY`; có sidecar không chứng minh model sử dụng ngữ cảnh hiệu quả. Memory/cache hợp lệ cấu trúc cũng không tự là dữ liệu đã duyệt ngữ nghĩa.
- Plan cũ và bài tham khảo chỉ là ý tưởng R&D. Danh sách model, phần cứng, tốc độ, giấy phép và benchmark lịch sử phải xác minh lại khi cần; không lấy lịch sử private làm prerequisite.

## 1. Bộ đánh giá và dữ liệu

Bắt đầu khoảng 100 câu EN→VI có quyền sử dụng, gồm hội thoại, thành ngữ, xưng hô, UI, thuật ngữ và protected tokens. Chốt người/quy trình duyệt ngữ nghĩa và tiêu chí đánh giá trước khi so sánh. Nếu chưa có người duyệt độc lập, báo rõ mức tin cậy; không gọi điểm tự chấm của model là human acceptance.

Tách dữ liệu phát triển và held-out đánh giá; không dùng các câu đã sửa để chứng minh khả năng tổng quát. Ghi nguồn, quyền sử dụng, phiên bản dữ liệu, engine/boundary/context khi có, bản dịch duyệt và loại lỗi. Không tự đưa game, CSV riêng hoặc dữ liệu người dùng vào Git/training. Không cần copy game chỉ để đánh giá các câu được phép sử dụng.

Đo sai nghĩa, bỏ/thêm ý, xưng hô, thuật ngữ và độ tự nhiên riêng với lỗi cấu trúc; giữ baseline OPUS và output trước/sau. Frozen benchmark 30 câu hiện có có thể tái sử dụng cho regression phù hợp, chưa đủ đại diện toàn sản phẩm.

## 2. Cải thiện route hiện có

Kiểm tác dụng glossary, bộ nhớ bản dịch đã duyệt và chuẩn hóa đầu vào theo lỗi có bằng chứng. So sánh baseline và từng thay đổi trên cùng held-out; không hardcode câu benchmark hoặc nới validator để tăng điểm.

Thu thập context chỉ khi có boundary đáng tin: cùng file/cảnh/nhóm, người nói và câu liền kề. Không đoán xuyên engine/file, không nối hội thoại vào CT2 rồi mặc định là dịch có ngữ cảnh. Chưa dựng vector database hoặc retrieval phức tạp nếu exact glossary/memory chưa cho thấy giới hạn cần giải quyết.

## 3. Một thử nghiệm model có ngữ cảnh

Khi bước 1–2 đã có kết quả, đề xuất tối đa một candidate đầu tiên, kiểm lại license, Windows/deployment và RAM/VRAM trên phần cứng thực. Owner duyệt model/download/quota trước thực thi.

So sánh dịch trực tiếp từ nguồn + context với sửa draft OPUS từ cùng nguồn + context trên cùng model và dữ liệu. Dịch trực tiếp là giả thuyết ưu tiên thử, không phải kết luận đã chứng minh. Giữ OPUS làm baseline/lựa chọn nhanh; không thay model sản phẩm chỉ vì một demo tốt.

## 4. Huấn luyện có điều kiện

Chỉ đề xuất pilot SFT/LoRA khi đã có corpus được duyệt, quyền sử dụng rõ và evidence cho thấy model candidate có triển vọng nhưng còn lỗi có thể học từ dữ liệu. Output teacher/cloud là draft cần duyệt, không tự là gold. Chốt ngân sách, môi trường, dung lượng và stop condition trước khi chạy; không mở hàng loạt model/training jobs.

Đánh giá trên held-out không lọt vào training; nếu không cải thiện đủ theo tiêu chí đã chốt thì dừng để xem lại premise/dữ liệu. Không tăng quy mô chỉ vì pilot chưa đạt.

## Acceptance và đóng từng đợt

Mỗi bước là một task bounded, một writer, theo AGENTS và CONTRACTS §10a/§10c. Trước task implementation, chốt phạm vi, gate, ngân sách run/copy/disk và tiêu chí cải thiện. Kết thúc phải có so sánh ngữ nghĩa, structural regression, latency/tài nguyên thực và giới hạn bằng chứng; cleanup riêng, một DEV executable khi sửa app. Không giữ bản sao game/model trùng lặp.

Candidate chỉ được promote khi cải thiện ngữ nghĩa trên nhóm mục tiêu, không có regression nghiêm trọng mới và mọi invariant cấu trúc/dữ liệu vẫn đạt. Ngưỡng và phạm vi hỗ trợ phải chốt trước thử nghiệm. Gate DEV không thay gate Release hoặc cập nhật trên bản cài thật.

### Step3 Owner approval and bounded execution — 2026-10-19

Owner explicitly approved the proposed pinned Hy-MT2 Q4 model, official portable CPU runtime download and shared6GiB cap. Product OPUS stays unchanged. Coordinator sole writer; previous child usage-terminal, no replacement child. Preflight: verify download hashes/size and license, CLI build/architecture, free RAM and disk before loading. First attempt at most120s, context512, output128 tokens, CPU2threads, no GPU; do not load if available physical memory cannot cover model file plus512MiB headroom. Do not close unrelated apps or resize VM. If preflight fails, retain evidence and report prerequisite, no repeated blind model loads. Development-only semantic comparison follows only after viable inference, before any held-out output review. Test scripts use canonical registered TEST_RUN and cleanup; compact evidence in DEV_RUN/translation-quality-phase3. No training, product edit, release or push.

### Step3 download/preflight result — PROVEN_BLOCKED (2026-10-19)

Approved downloads completed and exact size/SHA256 matched both pinned artifacts; official Apache-2.0 model and MIT runtime license texts retained beside dependencies, receipts include their hashes. CLI --version/--help exit0:0.7.0-dev build11724 commit99db719bd, Windowsx86_64. GGUFv3 metadata parses354tensors, architecture hunyuan-dense. This proves file integrity and CLI startup only, not model-load architecture compatibility or inference. No model load attempted: measured free physical827678720bytes < fixed pre-load1669951360bytes (model1133080448 +512MiB). Guest physical4293808128bytes. Outcome PROVEN_BLOCKED for inference/semantic comparison under the bounded RAM guard; not proof the model cannot run in some other memory configuration. Safe completed alternatives: portable runtime startup and metadata parsing without loading weights. Needed prerequisite: at least the fixed1.56GiB available physical RAM, or a separately approved revised resource protocol; do not resize VM/change host/close unrelated apps automatically. No speed, translation quality, direct-versus-repair or held-out result claimed.

Focused quota gates: `python -B tests/tools/run_with_cleanup.py --timeout-seconds 180 --report DEV_RUN/translation-quality-phase3/quota-focused.json -- python -B -m unittest tests.unit.test_cleanup_work_artifacts.CleanupLifecycleTests.test_combined_exempt_cap_and_exact_baseline_roots tests.unit.test_cleanup_work_artifacts.CleanupLifecycleTests.test_project_size_measures_fixed_exemptions_and_fails_closed_on_links_and_special_nodes` using shared release-venv Python3.12:2testsPASS,0fail/error/skip/warning, child/outer0, cleanupPASS. Evidence source3808ccb plus scoped quota/doc diff, not exact latercommit validation. Final inventory complete/within_limit: non-exempt695861971/1073741824bytes, shared5778817474/6442450944bytes; TEST_RUN/RELEASE_RUN absent. Evidence `DEV_RUN/translation-quality-phase3/{downloads.json,licenses.json,runtime-version.txt,runtime-help.txt,preflight.json,quota-focused.json,terminal-quota.json}`. Product source/model and current DEV/public0.1.8 unchanged, no release/push.

### Owner-approved RAM increase — host access blocked (2026-10-19)

Owner explicitly requests increasing VM RAM sufficiently then continuing. Clean main b9d1268; Coordinator sole writer. Guest identity from Hyper-V guest registry: VM VNTextStudio-DevWin11, ID D5318551-BB01-4754-AC54-1C275BB3BACF, physical host DESKTOP-4S3QPMN. Guest has4293808128 physical bytes, free847460KiB. Get-VM/Set-VMMemory and vmms unavailable in guest; local root/virtualization/v2 query exits1 Invalid namespace. Read-only remote CIM/DCOM probe with current identity and8s operation timeout exits1: The RPC server is unavailable. Host free RAM/configuration UNKNOWN, no safe allocation selected; no VM changes, shutdown, firewall/security/service changes or model load attempted. Outcome PROVEN_BLOCKED: host management session/access required to execute authorized RAM increase; guest cannot allocate its own physical RAM. This is an access prerequisite, not another request for permission. Already downloaded verified model/runtime retained under6GiB cap, product OPUS unchanged. Once host access is available, inspect host memory, increase only this VM allocation, then repeat fixed RAM preflight and bounded inference.

### Guest-only memory reclamation — 2026-10-19

Owner clarifies host has insufficient spare RAM; keep VM4GiB, authorizes closing VNText app/test processes then retrying preflight. This replaces the proposed RAM-increase next step; no other app/system process termination authorized. On clean342773e, process inventory by executable name plus absolute checkout executable paths finds no VNText app, Python worker, llama or project test process running; nothing can be closed within scope. Free physical702423040bytes remains below unchanged1669951360byte guard, so no model load/inference attempted. Highest working sets belong to Codex/ChatGPT and Windows, not VNText; these were left running. Outcome PROVEN_BLOCKED, exact evidence DEV_RUN/translation-quality-phase3/close-vntext-preflight.json; prior receipts preserved. No source/runtime/dependency changes, download, build or test run. Need additional available memory or a separately bounded alternate execution environment before inference.
