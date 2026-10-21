# Concrete candidate feasibility — metadata only, 2026-10-21

Current disposition (2026-10-21): research PLAN_TEMPORARILY_CLOSED_BY_OWNER. Later pinned Qwen acquisition completed and was hash verified; first model load stopped at the RAM guard, no semantic output. The metadata-only/no-download wording below describes the initial stage, superseded by its later acquisition sections and QWEN_RESOURCE_READINESS.md. No product integration or automatic resume.

No weights downloaded, terms accepted, authentication changed, model loaded,
training performed or dependency installed. Public model metadata/card/license
text were read. This is a conditional test proposal, not product model selection
or evidence of better translation. Existing OPUS/DEV and failed raw are retained.

## Three shortlisted model families

| Candidate / pinned primary provenance | Published artifact and license | Existing runtime / resource fit | Disposition |
| --- | --- | --- | --- |
| Qwen/Qwen2.5-0.5B-Instruct-GGUF at `9217f5db79a29953eb74d5343926648285ec7e67` | First-party `qwen2.5-0.5b-instruct-q4_k_m.gguf`,491400032bytes; published LFS SHA256 `74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`. Apache-2.0 LICENSE11343bytes; no separate NOTICE listed. Card explicitly lists Vietnamese and instruction following. | GGUF qwen2 family; existing llama-b11724/99db719bd source lists QWEN2. No new runtime expected, actual load/template compatibility UNKNOWN until authorized test. Small context512 and output128 proposed; working-set planning range0.8–1.4GiB, not measured. | Recommended first **feasibility experiment**, because one first-party artifact fits disk and existing CPU runtime. General multilingual 0.5B capability may be inadequate; no claimed EN→VI score or guaranteed gain. |
| facebook/nllb-200-distilled-600M at `f8d333a098d19b4fd9a8b18f94170487ad3f821d` | Primary unquantized pytorch_model.bin2460457927bytes, SHA256 `c266c2cfd19758b6d09c1fc31ecdf1e485509035f6b51dfe84f1ada83eefcc42`; card declares CC-BY-NC4.0. No standalone LICENSE/NOTICE listed in captured files. | Not directly loadable as this artifact by current CT2/GGUF route; conversion needs uninstalled torch/source weights and tokenizer conversion. Artifact alone exceeds remaining disk by>1.8GB. FP32weights≈2.46GB plus activations/tokenizer/OS make4GiB unsafe without measurement. | Reject for current resource/authority and noncommercial distribution boundary; not a drop-in OPUS replacement. |
| google/translategemma-4b-it at `10042cb0e6e7fdce748996a71dc3dc432a4e0c89` | Primary safetensors shards total8600277880bytes; Gemma terms, manually gated. Pinned raw README access denied; no sign-in/terms acceptance attempted. Public card is readable. | Existing CT2 cannot load these shards; transformers multimodal path needs torch and substantial memory. Even a lower-bound4bit4Bweight estimate≈2GB exceeds remaining shared disk before runtime/KV; primary artifact8.6GB clearly fails. Community GGUF is a separate provenance/license check, not assumed equivalent. | Reject for this4GiB/6GiBguest, no gated acquisition or framework change proposed. |

Primary cards: [Qwen](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF),
[NLLB](https://huggingface.co/facebook/nllb-200-distilled-600M),
[TranslateGemma](https://huggingface.co/google/translategemma-4b-it).
Published language/context claims are publisher claims, not measured VNText
adequacy/latency. Exact metadata captured in VM-Acceptance/
semantic-model-candidates-metadata-corrected.json; original capture retained.
Its initial Gemma card field accidentally retained the preceding loop value
after gated retrieval failed; corrected supplement sets it null and records the
failure. Do not use that stale field. Runtime/license text capture is
semantic-candidate-runtime-license.json. No remote instructions were executed.

A preliminary Qwen3 first-party Q8 artifact check found639446688bytes, leaving
almost no reserve in this checkout; it was not selected for the three-option
shortlist. Installed historical Hy-MT2 remains rejected from prior fresh semantic
evidence; do not rerun or recommend the same weights as a new alternative.

## Disk, runtime and peak plan

Latest complete boundary DEV receipt measured shared5797429235/6442450944bytes,
remaining645021709bytes; nonexempt725565129/1073741824bytes. These are a dated
receipt, not a current acquisition preflight. Adding the Qwen Q4 file once gives
shared6288829267bytes and153621677bytes spare before small metadata. A duplicate
download/cache copy would exceed the cap. Conditional acquisition must stream
one owned `.part` in the destination, verify expected size/hash, then rename on
the same volume; no HF snapshot/cache duplication, decompression or quantization.
Reserve>=128MiB leaves about19MB for metadata; re-inventory must prove it still
fits before any acquisition. No historical cache deletion is authorized.

llama-completion.exe version0.7.0-dev build11724 commit99db719bd,
SHA256 `CAC0FB622FD8E2529DF009F459B7FA797C5D12FD0509D5801D987E2D05846A3F`.
Only --version was executed; no model invocation. Architecture support checked
against [matching runtime source](https://github.com/ggml-org/llama.cpp/blob/99db719bd/src/llama-arch.cpp).
GGUF architecture support does not prove correct chat-template/tokenizer behavior
or model quality. CPU2, GPU layers0, context512, output128, batch64, deterministic
single decoding profile and<=120seconds/call proposed. Guard process peak<=1.5GiB,
minimum free physical256MiB and available commit1GiB; terminate/refuse on failure,
never expand RAM/quota. No peak or throughput is yet measured for this candidate.

## One reviewable next experiment, not executed

Exact missing external permission: acquire only the pinned491400032byte Qwen Q4
artifact and LICENSE into one owned `.dev-env/cache/models` directory and run a
test-only comparison with the existing llama binary. This changes no product
route/framework/protocol and permits no other model, dependency, training, paid
service, account, host or publication action. License obligations/notices must
be preserved; experimental acquisition is not redistribution approval.

Before acquisition: current complete quota inventory, memory/process preflight,
exact remote revision/size/hash confirmation, ownership/disposal registration and
source identity. Fail if128MiB reserve cannot be maintained, no cleanup of old
caches to make space. Proposed generated prompt gives source/speaker facts and
asks only a Vietnamese translation, unchanged across all cases. Freeze exact
template/transport/decoding before output; transport test first must preserve
complete stdout/source echo boundaries using existing supported CLI mode.

Stage1: four already-seen relation cases from relation-frozen.json, one output
each; compare retained OPUS product baselines under the semantic rubric. At
least2complete repairs, no new major/name/structure failure required. Stop on
threshold failure; no prompt/sampling variants. Stage2 only if admitted: the
12already-frozen fresh sources, one output each, same fixed template, no tuning.
No inference on new36+4design until actual source packet/seal and justified budget
exist. Agent source-aligned review records uncertainty honestly. Runtime/semantic
failure remains valid evidence, not reason to switch secretly to another model.

If this test succeeds, product integration remains a **separate Owner decision**
with model/license/architecture/runtime gates; it is not authorized by this plan.
If it fails, retain outputs and stop this candidate. Positive lexical constraints
on OPUS are not the recommended next action: they could enforce words but the
actual prefix result already demonstrates spelling fidelity without correcting
forgot/borrower/serial meanings, so no causal whole-meaning benefit is established.

Owner authorized necessary scoped downloads/execution on2026-10-21; durable
decision in CONTRACTS section4 supersedes the earlier permission blocker.
Acquisition and inference now have separate preflights. Inference still requires
256MiB available physical/1GiB available commit and processpeak<=1.5GiB.
The initial combined preflight failed those inference thresholds; no model load.

Acquisition uses a dedicated standard-library downloader process, one64KiB
read buffer and incremental SHA256, exclusive owned .part then same-volume
rename; never read the complete weights into RAM or make another cache copy.
Ownership/part lifecycle is registered before file creation in an external
acquisition receipt and a marker in the new model directory. Cleanup may remove
only the exact owned newly created .part. Python/TLS/hash/buffer budget64MiB
processpeak, startup availablephysical>=160MiB (64budget+96reserve) and available
commit>=192MiB (64budget+128reserve); guard during transfer at96/128MiB plus
peak64MiB. These conservatively bound fixed buffer/library overhead, not model
memory; measured processpeak must confirm. No download if this gate fails.
Shared quota still reserves128MiB after exact file+metadata, no duplicate/oldcache
deletion. Download failure is retained; no automatic retry/size override.

Actual staged result: streaming acquisition completed491400032bytes, exactpinned
SHA256 matched, LICENSE retained, .part renamed to final with ownership marker.
Elapsed50.828seconds, downloaderpeak41771008bytes; external
qwen-stream-acquisition.json records bounded memory and lifecycle. No duplicate
cache or old-data deletion. qwen-experiment-frozen.json seals prompt/CLI arguments,
four-seen/conditional12fresh criteria and source/model/runtime hashes before output.

Post-acquisition inference preflight passed physical480825344/commit1386541056
bytes. The single transport attempt started with physical419794944/commit1385500672
and was terminated by the unchanged memory guard after1.266seconds when physical
fell to168341504bytes (commit1196011520, observed childpeak256765952). This is
resource failure before completed output, not semantic rejection or templatePASS.
Original stdout/stderr retained, including the control-looking </s> token-type
warning; do not silently suppress it or blame it for the measured RAM stop.
Wrapper cleanup PASS, no owned llama/python/VNText process remains. No retry until
actual memory-state change/monitoring cycle. No 4seen or fresh inference occurred.

Independent metadata preparation reads only the GGUF header (5931189bytes), no
tensor data loaded: qwen2 architecture,24layers,14query/2KV heads, context32768,
filetype15, embedded template SHA256
`d5495a1e5db0611132a97e46a65dbb64a642a499421228b9c8b93229097fa9a4`.
qwen-gguf-header.json retains exact template. Runtime/template execution remains
unverified until a guarded transport run can complete. Ready state is acquired,
hash-verified and offline-prepared; inference waits on resource prerequisite,
not permission to download. Current accepted product DEV remains unchanged.
