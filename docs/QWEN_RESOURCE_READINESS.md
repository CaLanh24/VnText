# Qwen resource readiness — offline diagnosis, 2026-10-21

Current disposition (2026-10-21): PLAN_TEMPORARILY_CLOSED_BY_OWNER. The resource-only microbatch8 test was not loaded; finite deferred continuation was CANCELLED_BEFORE_LOAD through its documented cancel marker, worker/launcher exited, transient roots absent. Revised850MiB physical/1.75GiBcommit is a proposed startup envelope, not a measured successful load. No watcher or automatic resume. A public clone does not require guest-only checkpoints; source, frozen protocol, provenance and limits are retained here.

Weights are acquired/hash-verified; no semantic output exists. The first guarded
transport was stopped at observed256765952byte childpeak when available physical
memory fell to168341504bytes. Starting free419794944bytes merely exceeded the
reserve; it did not include model residency. This report corrects the start gate,
not the runtime guard or semantic experiment.

## Derived allocations and explicit uncertainty

Exact local GGUF metadata: qwen2,24layers, embedding896,14query/2KV heads,
head dimension64, FFN4864, vocabulary151936. Metadata was read without tensor
load; qwen-resource-metadata.json stores it. Full file491400032bytes includes
metadata/alignment; conservatively budget the whole file as potentially resident
weights (468.64MiB), without assuming Windows will reclaim mapped pages in time.

Matching llama.cpp99db719bd source allocates K/V tensors per layer as
GQAembedding × kv_size × streams. Default K/V are F16, one sequence:
`24 × 512 × (2 × 64) × 2(K,V) × 2bytes = 6291456bytes = 6MiB`.
Context n_batch is clamped to n_ctx and n_ubatch to n_batch; the frozen batch64
therefore does not secretly allocate a512token physical batch. A possible full
FP32 vocabulary-logit slab at64positions is151936×64×4=38895616bytes (37.09MiB).
The runtime may retain fewer logits; treat this as a planning component, not a
measured compute-buffer bound. Graph/workspace/allocator and tokenizer/template/
DLL overhead are additional and must be measured in a successful guarded run.

Planning envelope (not a proof of exact peak): wholefile469MiB +KV6MiB +
compute/logit allowance256MiB +runtime/tokenizer/allocator allowance192MiB =
about923MiB. Round model-process increment upward to1GiB and preserve256MiB
free physical reserve. **Required start free physical: at least1.25GiB
(1342177280bytes); required start available commit: at least2GiB
(2147483648bytes).** Also require existing processpeak<=1.5GiB and actual
availablephysical>=256MiB/availablecommit>=1GiB throughout. On any violation,
terminate only the owned test child and retain receipts. These stronger start
gates do not guarantee OS pressure stays constant; live monitoring remains.

The measured initial419.8MB was about880MiB below the new start requirement.
The partial256.8MB peak is a lower bound on the aborted load, not total model
memory and not evidence a smaller200MB reserve would suffice. No model retry is
authorized solely because free memory crosses256MiB again.

## Avoidable allocations considered without loading

| Option | Documented effect / estimate | Decision |
| --- | --- | --- |
| Context512→256 | KV saves3MiB; would reduce input+output capacity and risk truncation | Does not address deficit; keep frozen512 |
| Physical batch64→8 | Hypothetical full-vocab FP32 slab drops37.09→4.64MiB, about32.45MiB saving; actual graph savings unknown | Too small versus headroom deficit; no config sweep or changed experiment |
| --no-warmup | Documented skips initial empty warmup, may avoid touching buffers early but real inference still needs them | Not a sustainable memory remedy; not added |
| Mmap/default file residency | May reduce private commit but mapped tensor pages must be touched; Windows cache/working set behavior not guaranteed | Do not count mapped bytes as zero RAM or use memory eviction tricks |
| KV quantization | Even eliminating6MiB entirely cannot solve deficit; quantization support/quality would need a new experiment | Not changed |

Primary matching source:
[KV allocation](https://github.com/ggml-org/llama.cpp/blob/99db719bd/src/llama-kv-cache.cpp),
[batch clamp](https://github.com/ggml-org/llama.cpp/blob/99db719bd/src/llama-context.cpp),
[default cache types](https://github.com/ggml-org/llama.cpp/blob/99db719bd/common/common.h),
[runtime options](https://github.com/ggml-org/llama.cpp/blob/99db719bd/common/arg.cpp).

## Ready-to-run resource plan

Keep the verified single model copy, unchanged frozen prompt/profile and current
accepted DEV. Before a new attempt, use one small GlobalMemoryStatusEx query only
after an actual session/resource-state change or monitoring cycle. Full quota
inventory is unnecessary on each memory poll when artifact bytes have not changed;
still required before any new acquisition/mutation that affects quota.

Preferred resource alternative costs0đ and needs no model/config change: run the
same test in this guest after normal desktop/client pressure has been reduced by
a deliberate session lifecycle with work preserved, or another already-available
authorized execution environment with >=1.25GiB free RAM/2GiB commit. No such
environment is assumed available, no host inspected/changed, and this agent does
not kill ChatGPT/security/foreign processes, log out, restart the VM, alter RAM/
pagefile or discard unsaved work. A planned guest-session restart must preserve
controller access and needs orchestration; it is not an invisible test retry.

If the4GiB guest cannot meet the measured start gate while the controller runs,
the remaining requirement is a lower-footprint controlled session or explicitly
provisioned execution capacity. Do not claim that reducing tiny KV allocations
solves it, repeatedly load into the same pressure, or mark semantic quality
achieved. No new inference occurred for this resource diagnosis.

## Actual runtime estimator and resource remediation

The1.25GiB start threshold above was a conservative planning estimate, not a
measured hard minimum. Matching common/fit.cpp sets no_alloc=true and load mode
NONE; llama-fit-params --fit-print therefore provides the runtime's graph/model
estimate without loading weight tensors or inference. Actual exit0 result with
context512/logicalbatch64/physicalbatch64/CPU: `Host 434 6 38` MiB for model,
context and compute. qwen-runtime-fit-estimate.json retains the command/output.

A single resource-only alternative uses physical microbatch8, keeping logical
batch64/context512/temperature/seed/prompt/weights unchanged. Estimator exit0:
`Host 434 6 4` MiB, saves34MiB compute. Measured estimator processpeak76066816
bytes (72.54MiB), independent of actual future model residency. Source confirms
physical microbatch is clamped to logical batch. This is allocation remediation,
not a semantic parameter sweep; floating-point/token equivalence is not presumed.
qwen-runtime-fit-microbatch8.json records it. No model tensor loading occurred.

Revised justified envelope: estimated444MiB model/context/compute + measured
estimator/runtime footprint rounded to80MiB +64MiB unmeasured load/allocator
margin =588MiB incremental, plus256MiB live reserve =844MiB start physical
(885.0MB). Round upward to **850MiB start free physical**, **1.75GiB start
available commit**; retain live256MiB physical/1GiB commit/1.5GiB peak guards.
This supersedes1.25GiB as the resource plan, not as evidence of a successful load.
Before one monitored attempt, persist the physicalmicrobatch8 delta and use a
new transport receipt; keep all original semantic frozen sources/prompt/decoding.

At the measured estimator run, actual freephysical298799104bytes (~285MiB),
commit2162892800bytes. Commit fits the revised projection; physical is about
565MiB short. No repeated load or tiny memory poll can solve that deficit.
No owned model/test process remains to terminate. A new smaller quant artifact
would consume more than the153MiB remaining shared reserve while the verified
Q4 is retained; do not silently delete it or historical cache for a quant sweep.

Concrete safe resource-change steps: preserve the current staged work/receipts;
use normal guest desktop lifecycle to save work and close duplicate/unneeded
desktop sessions/apps through their supported interfaces; relaunch exactly one
controller with minimal other apps; then run one readiness query against850MiB/
1.75GiB and, if it passes, the revised monitored transport. The current agent
cannot verify/save foreign unsaved UI state or terminate its own controller while
guaranteeing reconnection, so those session-lifecycle steps require the controller
to orchestrate or the user to perform them. No arbitrary process kill, security
change, host access or RAM/pagefile modification is a substitute. If that session
still cannot fit, execute the same pinned test only on an actually available
authorized machine with the proven headroom; availability is currently UNKNOWN.
This is the exact external execution boundary; resource-only allocation research
is completed and no semantic result is claimed.
