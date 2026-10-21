# Product semantic quality — new Owner task, 2026-10-21

Current disposition (2026-10-21): PLAN_TEMPORARILY_CLOSED_BY_OWNER; accepted bounded whitespace fix retained, whole-app semantic acceptance NOT established. No active deferred runner/watcher or automatic resume. The original permissions/status and incremental pending reports below are historical; later recorded Owner decisions supersede them. Git delivery is separately authorized and does not reopen inference/research.

The preceding remediation/evidence campaign remains accepted. This new task
targets actual meaning in product translations; its outcome cannot be inferred
from that verdict. DEV is the sole writer on main base c9825d4 plus retained
task-owned staged changes; Brain reviews read-only. No child, install/download,
model/framework/protocol change, training, paid/cloud service, user data, push or
Release. Existing 6GiB shared / 1GiB nonexempt quotas remain.

## Premise and prioritized backlog

1. Omitted propositions and long rows: existing long-text evidence shows output
   below the decoding cap, so raising that cap is not an evidenced remedy.
   Sentence segmentation was rejected because discourse/actor/acronym errors
   remained; do not repeat it or relabel longer output a meaning gain.
2. Actor, polarity, gender and register: source-aligned residual review records
   wrong/unsupported relationships and address. Separate model errors from any
   reproducible preprocessing/cache/admission defect; do not invent context.
3. Idiom and term sense: literal readings remain. Reviewed exact memory only
   fixes matching approved occurrences; neither dictionaries nor answer banks
   establish quality on new sentences. Carrier experiments remain rejected.
4. Product boundaries: import/editor/cache must preserve source, keys, order,
   schema, locator, tokens and user authority; refusals are safety, not gains.

## First mechanism to test, not yet admitted

Read-only source inspection shows Ct2Translator._translate_token_batch calls
translate_batch without explicit search settings. Official CTranslate2 API
documents beam_size=2. Compare one deterministic beam_size=4 candidate against
the current default, unchanged weights/tokenizer/input/length policy/validators.
This tests a decoding search-space hypothesis, not a new model, prompt,
segmentation, lexical replacement or source-conditioned answer selection.
No assertion that a larger beam necessarily improves meaning.

Owner: vntext/mt_ct2_model.py; if admitted, adapter/cache identity must encode the
decoding profile so old drafts are not relabeled or silently overwritten.
Contracts: CONTRACTS sections4/4a, CSV/workflow invariants and10c lifecycle.
Gates: tokenizer/model focused tests and cache tests, affected pipeline/worker
tests, actual generated product workflow/read-back, current DEV/smoke and native
affected surface only if UI behavior changes. No product mutation before the
bounded feasibility evidence supports admission.

Reference: https://opennmt.net/CTranslate2/python/ctranslate2.Translator.html
Installed runtime signature/version must be captured as authoritative for runs.

## Frozen evaluation and stop conditions

Before any new model output, freeze 8 known residual development sources and
12 newly authored controls, rights generated-for-project. Include omission/long
propositions, actor/polarity, idiom/register and terminology/protected controls.
Freeze source text, category, expected propositions/forbidden meaning changes,
IDs and digest. Keep fresh controls unopened to tuning until the single candidate
is fixed. No human-gold/blind-review claim; source-aligned agent review records
who reviewed, uncertainty, exact outputs and major/minor errors for both arms.

One baseline and one candidate, at most 40 outputs total, no parameter sweep or
fresh-output tuning. First run only the 8 development sources: require at least
two demonstrated semantic repairs without a new major error before spending the
fresh comparison. Fresh admission requires at least two meaning improvements
across two categories, lower major-error count and no new major regression in
any control; uncertain cases cannot count as gains. Structural/source/CSV
invariants must hold, no refusal counted as semantic improvement. Record runtime,
memory and output budgets before execution using the existing registered runner.

If this mechanism fails, retain raw evidence and reject it; do not silently add
beam/penalty variants. Diagnose any actual code defect independently. If no
viable in-scope mechanism remains, present the specific data/reviewer or model
technology decision needed to Owner. Do not declare whole-app quality complete
from tests, a scoped reuse feature, this finite fixture or this plan alone.

Status: premise/backlog and proposed mechanism submitted to Brain; no inference
or runtime change in this initial diagnostic report.

Owner steering through Brain: proceed continuously with evidence-driven work
inside these permissions, without routine approval pauses. Brain accepted the
single beam4 feasibility comparison; rejection of one hypothesis is not task
completion or permission for a parameter sweep. Continue independent diagnosis
or state a concrete missing data/technology prerequisite if one is established.
Installed CTranslate2 4.8.1 signature confirms beam_size=2, length_penalty=1 and
max_decoding_length=256. Frozen sources/semantic criteria and fixed profiles are
in evaluation/translation_semantic_campaign_v1/frozen.json before any new output.
Budget: development16 then fresh24 only if development admits; <=180seconds per
stage, process peak<=1.5GiB and fail on a memory guard rather than expanding it.

Beam feasibility terminal: development16 outputs completed in3.094seconds,
peak working set201678848bytes, wrapper/cleanup PASS. Agent source-aligned
review admits zero complete semantic repairs; checksum wording partially improves
but patch/manifest meaning remains missing, idiom errors persist and masculine
address remains unsupported. Candidate REJECTED, fresh controls not run. Raw
semantic-beam-development.json and wrapper retained in VM-Acceptance;
evaluation/translation_semantic_campaign_v1/development-review.json records review.

Next distinct read-only premise: existing required token-budget splitting in
Ct2Translator joins independently decoded pieces with an empty separator in two
places, although tokenizer decoding normally drops outer whitespace. Investigate
whether this loses source boundary spaces on actual inputs above480tokens, and
whether the default256target-token cap is reached there. This is not reviving
sentence segmentation below the model budget: splitting policy stays unchanged.
The earlier234token fixture did not hit the cap and cannot settle >480token
inputs. Freeze new long-boundary sources before output, capture actual input/
output token counts and source-aligned tail propositions. One before capture,
then only a demonstrated seam/cap defect may justify a bounded correction;
no beam/penalty sweep or arbitrary longer-output-as-quality claim. Same180second/
1.5GiB guards, <=12backend segments per arm and source/code/model identities.

Boundary baseline: frozen source538tokens splits under the existing480 budget
into480+60tokens. Actual model returns23+71tokens, neither at256cap, and joining
loses the source space (`bắc.Nadia`). This proves a separator defect, not a
decoding-cap defect; do not increase the cap. First chunk omits most propositions,
which separator repair cannot solve. Short actor-name drift Mila->Mita is also
retained, not concealed. Raw semantic-boundary-before.json/wrapper cleanup PASS.

Bounded implementation owner mt_ct2_model.py: retain only original outer
whitespace of already-required budget chunks during reassembly, without changing
split boundaries, input text, decoding or lexical output. Both reassembly seams
must follow it; hard cuts with no source separator must not invent spaces.
Adapter decoding provenance/cache profile changes to prevent stale joined output
reuse. Gate red/green long-input regression, adapter/cache/worker affected tests,
same-source actual after capture (unchanged model chunk outputs), synthetic
product readback, currentDEV/smoke/cleanup. This fixes a real code defect, not the
observed major omission or whole-app semantic quality.

Boundary delivery: red2failedsubcases retained; initial affected run48tests passed
but worker setup failed due an unconfigured default model path, not missing model
bytes. Correct configured existing model worker16PASS; focused model/cache17PASS,
final boundary8PASS includes fallback seam, split whitespace/whitespace-only and
count mismatch. Actual same-source after changes only one inserted space, exact
backend input/output token arrays and kwargs unchanged, short control unchanged.
Actual extract/translate/patch/readback PASS with source unchanged; current DEV
build/smoke and cleanup PASS, one executable, transient roots absent.
Compact evaluation/translation_semantic_campaign_v1/boundary-delivery.json binds
current files/build and external raw/receipt hashes. Optional sacremoses warning
and noPyTorch informational retained; no dependency installed.

Read-only loss localization (no inference): source chunks rejoin byte-for-byte,
tokenizer roundtrip retains each source tail with existing declared >>vie<<
prefix, input lengths480/60 match the captured backend call. Backend result
already has23/71targettokens before app decode/reassembly; omission is upstream
of assembly/cache/patch for this fixture. Initial metadata assertion omitted the
existing prefix (479/59); corrected without rerunning inference. This does not
prove target meaning and does not admit a cap/search/segmentation remedy.

Remaining product objective: actual new-sentence meaning still incomplete.
Idioms, actor/gender/register, term-sense and long discourse remain demonstrated
limits. Existing context sidecar is explicitly metadata-only; a context-conditioned
model or trained data route is not an authorized silent implementation change.
Continue examining reproducible caller/code loss independently; do not convert
this bounded separator delivery into whole-app quality PASS.

Brain accepted the bounded boundary fix after direct source/raw/hash review:
7source/test hashes and15receipt hashes match, actual readback/source preservation
and terminal cleanup verified. No repeated gate is required for this verdict.

Important diagnostic qualification: the direct translator probe bypassed the
product's protected-name splitting. Existing product fixture has40protected actor
names and40text fragments, maximum18tokens, so it preserves far more clauses
than the direct480token call. Product output still has major errors (letters as
alphabet characters, lender/borrower reversal, offered-meal predicate lost,
serial number mistranslated). The direct collapse cannot stand for every product
input. Existing model-declared >>vie<< is applied once in both routes; no prefix
mismatch demonstrated. Source-only mechanical removal of the fixture's names
leaves one568token text fragment, showing long unmarked prose can reach the
budget splitter. That variant was not translated or treated as a benchmark.
Fresh F10 is one95token fragment; F09 splits into3fragments, maximum73tokens.
No fresh outputs were produced. External diagnostic receipts:
semantic-product-direct-comparison.json and semantic-input-category-diagnosis.json.
Tokenizer-only full-row count emits the expected >512token warning; no oversized
input was sent to the model. No new segmentation/cap/search policy is admitted.

## Targeted caller/context audit and next prerequisite

Read-only routing audit records exact callsites in external
semantic-routing-audit.json. collect_spans/split_parts deliberately protects
proper names; relational F05 yields `handed the spare key to`, `, but`,
`returned it to`, `before leaving.` with names restored separately. F08 splits
`did not ask` from the requested action. All source bytes reconstruct exactly;
there is no demonstrated transport deletion. F10 has no protected names and
remains a single95token model fragment, so not every semantic error has this
cause. Source-only evidence cannot prove a role-error counterfactual.

Pipeline accepts structurally/finite-quality-valid first-pass candidates before
full-sentence retry; full-sentence calls are selective for rejected rows. These
validators are not meaning oracles. Routing every output through extra retries
or choosing a longer draft would be an unsupported quality policy. Cache carries
context/model/decoding identities and revalidates hits; no missing context flag
or stale profile defect was demonstrated in this audit. context_builder emits
bounded/insufficient_metadata records but explicitly METADATA_ONLY for model use;
it does not falsely claim to feed speaker/neighbour context into OPUS.

No further production correction is admitted from this audit. A new mechanism
must demonstrate joint relational context while preserving exact protected
names/tokens on independently frozen controls; existing rejected carrier and
segmentation experiments do not provide that evidence. If current-model
context-preserving inference cannot satisfy this, the concrete technology/data
decision is permission for a separately bounded alternative-model or training
feasibility study with licensed/provenanced data and independent bilingual
acceptance. No such model/download/training is authorized by this task. This is
a remaining prerequisite for whole-app quality, not a request to repeat approval
of completed code fixes or a claim that changing technology guarantees success.

Brain accepted one next discriminator: at most4 already-seen relation failures,
current product split versus existing full-sentence retry, same source/OPUS/
defaults, no other substitutions. Exact comparison not found in targeted old
artifacts (the earlier full long paragraph is not equivalent to single sentences).
relation-frozen.json seals4source cases/actor-polarity-name criteria before new
outputs; budget8backend outputs/120seconds/1.5GiB. Any new major/name corruption
rejects, seen gains alone never authorize production admission or whole quality.

Relation comparison terminal:4cases/8outputs,2.781seconds,peak200220672bytes,
wrapper/cleanup PASS. Full sentence restores offered-action/messenger-recipient
in R21, an actual seen gain. But R15 corrupts Mila->Mita and introduces forgot
instead of left, a new major case. R22 still reverses the borrowed-ladder role;
R37 still loses serial-number meaning. Candidate REJECTED under the frozen rule,
not admitted behind a new selection heuristic. Exact review in relation-review.json;
raw semantic-relation-comparison.json/wrapper retained. No new runtime change,
no fresh outputs, no name substitution or parameter variant.

## Known-residual inventory disposition

residual-inventory.json maps all17 reviewed residual IDs plus long-events and
the4relation comparisons to investigated callsites, accepted code fixes and
unresolved meaning. It separates proven G1/G2/G5/strict-memory/budget-whitespace
repairs from semantic errors without a proven additional code defect. Not every
residual has a per-case causal experiment; this is not an exhaustive proof that
all possible code defects are absent. No concrete unexamined code-defect premise
was identified in the audited caller/context/cache/strategy paths.

Outcome for the broader request remains PM_DECISION_REQUIRED, not completed:
need a demonstrated context-preserving mechanism with exact protected identity,
independent bilingual meaning criteria/data for intended domains, and—if OPUS
cannot satisfy those criteria—explicit scope for a licensed alternative-model
or training/data feasibility route. Current rights do not permit installing,
downloading, changing model or training. Existing agent-generated controls and
agent review are useful diagnostics, not human linguistic gold. Keep current
accepted fixes and do not launch another unsupported hypothesis to appear busy.

## Continued primary-source feasibility research

Owner requires continued evidence-driven work; public papers/docs and installed
metadata research are permitted without model/download/training authority. Agent
semantic review is valid diagnostic evidence when attributed; human gold is not
a prerequisite for every experiment. The earlier prerequisite disposition does
not terminate this research.

Installed metadata: CT2 4.8.1, transformers5.20.1, sentencepiece0.2.2,
numpy2.5.4; torch/sacremoses absent. No installation requested or performed.

| Mechanism / primary reference | Causal fit / installed support | Cost, risks and disposition |
| --- | --- | --- |
| Forced target prefix, CT2 decoding docs https://opennmt.net/CTranslate2/decoding.html | Installed translate_batch exposes target_prefix. A sentence-initial exact source name can be forced while the model sees the unmodified whole sentence, addressing Mila->Mita during decoding rather than post-hoc string replacement or source carriers. | Same licensed existing model/runtime, no new artifact/license. Only initial names, not arbitrary interior names; forcing order may distort meaning. One fixed 4seen-case diagnostic, same default beam/length, max4new outputs,120seconds/1.5GiB, exact names/full meaning required; no parameter variants. No admission from mere name presence. |
| Arbitrary lexical constraints: Hokamp/Liu2017 https://aclanthology.org/P17-1141/ and Post/Vilar2018 https://aclanthology.org/N18-1119/ | Constrains required phrases anywhere rather than prefixes, potentially interior names/approved terms. Installed CT2 Python API lacks a general positive lexical-constraint argument; score_batch is not an incremental constrained decoder API. | Custom decoder/backend or another runtime would need implementation/license/runtime evaluation and broader architectural scope; do not vendor a decoder or infer support from papers. Inclusion alone does not ensure actor/polarity. Not immediately executable in product scope. |
| return_attention / replace_unknowns, official CT2 Translator API | Installed; unknown-token copying can copy source token aligned to UNK. Observed Mita is fluent known-token corruption, not a demonstrated UNK, so this option does not address the actual failure. | Attention is not a semantic oracle; post-hoc name replacement risks replacing the wrong referent. Read-only possibility, no inference or mutation justified yet. |
| Model scoring / n-best reranking | Installed score_batch/return_scores; can rank target likelihood. | Neither likelihood nor length proves adequacy; no independent semantic scorer is installed. Rejected as an ungrounded selection heuristic rather than a new semantic remedy. |

The forced-prefix discriminator differs from rejected unconstrained full sentence:
the exact initial name is constrained during inference, with unchanged source
context and no translated answer prefix. Frozen relation sources/criteria remain;
freeze candidate definition before4outputs. Compare against existing product/full
raw outputs. Any new major, name corruption or no complete meaning repair rejects;
independent fresh controls only after a justified development result. No claim
that prefix constraints solve omitted discourse, idioms or all product categories.

Prefix diagnostic completed4newoutputs in2.844seconds,peak200802304bytes,
wrapper/cleanup PASS. Names now exact in all4cases, but R15 still invents forgot
for left; R22 borrower and R37serial sense remain wrong. R21 retains the same
single predicate gain already observed, no new general adequacy gain. Rejected
as a semantic remedy in prefix-review.json; no runtime promotion or fresh run.
This is evidence that supported prefix constraints address the spelling failure
but do not solve the rejected full-sentence method's meaning regression.

Further primary references: Tu et al.2016 coverage model
https://aclanthology.org/P16-1008/ feeds a learned coverage vector into attention;
it is not a drop-in metadata switch for current OPUS weights. CT2 exposes a
coverage_penalty option, but no evidence yet ties observed role/term errors to
attention undercoverage; do not run penalty variants without that discriminator.
Attention interpretation itself is contested: Jain/Wallace2019
https://aclanthology.org/N19-1357/ and Wiegreffe/Pinter2019
https://aclanthology.org/D19-1002/ motivate controlled tests rather than treating
an attention matrix as proof of semantic alignment. Neither source establishes
that post-hoc copying a source name to an attended target span preserves referents.
No attention-based rewrite, new dependency or training was implemented.

Research/data-criteria continuation is consolidated in
docs/TRANSLATION_SEMANTIC_ACCEPTANCE.md: domain rubric, severity/uncertainty,
independent36source+4stress design before outputs, fixed admission and a closed
capability shortlist tied to installed artifacts and retained rejections. This
is actionable planning/feasibility, not another claimed translation gain. No
inference, build or test was run to produce that document.

Owner permission update: necessary scoped acquisition/execution now authorized
without routine reapproval, durable decision recorded in CONTRACTS section4.
Actual Qwen preflight (qwen-acquisition-preflight.json) passes projected shared
disk reserve but fails memory: physical available206204928bytes, available
commit648069120bytes, below256MiB/1GiB guards. No weight download/model load
started. Read-only process inventory finds no python/llama/VNText test process
to clean; largest working sets belong to memory compression and desktop/client
processes, not this task's disposable children. No unrelated process stopped,
security change, RAM expansion or weakened guard. Resource prerequisite must
change before model acquisition/execution under this fixed preflight.

## Owner pause — 2026-10-21

PLAN_TEMPORARILY_CLOSED_BY_OWNER. Owner: “Cứ thiếu ram vậy sẽ kẹt mãi k giải quyết dc, chắc tạm thời đóng plan thôi.” Deferred one-shot was cancelled through its documented cancel file; actual terminal state CANCELLED_BEFORE_LOAD, no transport/model load, owned worker/launcher exited, TEST_RUN and RELEASE_RUN absent. No active tool goal exists to pause. Whole-app/new-sentence quality is NOT accepted: idiom, actor/role, omission, register and technical-sense residuals remain. Retain previously accepted bounded code/editor/boundary fixes, current DEV, pinned Qwen/LICENSE/ownership, frozen controls and all evidence. No automatic retry, watcher, model/build/test campaign or resume until explicit Owner reopening.

Resume: Downloads/VM-Acceptance/qwen-resume-checkpoint-20261021.md and qwen-deferred-once/state.json. The one-shot claim is terminal and must never be blindly reused; any later authorized run needs a new reviewed lifecycle and resource preflight.
