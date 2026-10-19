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
