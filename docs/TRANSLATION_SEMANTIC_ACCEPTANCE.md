# Semantic acceptance and executable feasibility — 2026-10-21

This is the next-step contract for the active semantic-quality task, not an
acceptance verdict or a new model/download/training authorization. Previous
accepted code fixes and raw failures remain intact. Agent source-aligned review
is allowed and must identify its author and uncertainty; human gold is not
required to conduct a bounded diagnostic.

## Domain rubric

Review the complete source against the complete written target, not isolated
matching words. Record source evidence for every error and proposed improvement.
Multiple valid Vietnamese phrasings are acceptable; literal target string match
is not the semantic criterion.

| Dimension | Required evidence | Major error examples | Minor / uncertain boundary |
| --- | --- | --- | --- |
| Actor and referent | Who performs each action, recipient/object, pronoun antecedent and ownership | Borrower becomes lender; giver/recipient swapped; two people merged | Awkward order with roles intact is minor; genuinely ambiguous antecedent is uncertain, never forced to one reading |
| Polarity and modality | Negation, only/unless/if, permission versus ability, obligation and timing | Prohibited becomes allowed; prerequisite reversed; may becomes must | Natural alternate construction with same condition is acceptable |
| Proposition coverage | Enumerated actions, objects, qualifiers, dates/numbers and discourse links | Missing corrected page, final clause, purpose or contrast; invented forgot/action | Redundant phrasing without lost meaning is minor; unclear source scope uncertain |
| Idiom and sense | Intended idiomatic/literal reading supported by source situation | Secret becomes physical beans/cat; danger becomes literal forest | Multiple equivalent idioms accepted; insufficient disambiguation uncertain |
| Register and address | Supplied speaker/listener facts and stated formality; unknown facts remain unknown | Unsupported gender/kinship, hostile register in explicitly gentle interaction | Slight stiffness minor; no metadata means do not require invented gender or relationship |
| Domain terminology | Event/object/relation in technical or narrative domain, not merely a term appearing | Cache hit becomes cache selection; serial identifier becomes repetition count; export becomes trade | Consistent valid terminology accepted even if different from a draft glossary; unexplained unfamiliarity uncertain |
| Exact structural fidelity | Source/key/order/schema/locator; placeholder/tag/escape/newline/name identity; patch/readback | Any loss/addition/corruption of required protected data is a hard failure | Structural correctness does not imply semantic correctness |

Domains: narrative/dialogue (roles, idiom, address), product UI/instructions
(permission, negation, action and labels), and technical workflow/prose
(terms, relations, long-clause coverage). Do not infer game-wide support from
generated text. A source longer than the tokenizer/model budget is a separate
stress stratum, not evidence of ordinary dialogue quality.

Labels per row/dimension: acceptable, minor, major, uncertain. Major means the
reader would infer a different material fact/action/relationship or lose one.
Minor preserves those facts but harms fluency/style. Uncertain is neither a
gain nor a pass. Store baseline and candidate labels, source quotation/pointer,
target span, rationale and reviewer provenance. Report both row-level any-major
counts and dimension counts, avoiding duplicate-error inflation. A refusal or
empty output is unavailable translation, not improved meaning.

## Independent source design and admission

Existing 12 fresh sources in semantic_campaign_v1/frozen.json remain unconsumed;
do not tune on them or claim they are independent human gold. A viable future
mechanism must be fixed before any of their model outputs are observed.

For broader validation after a mechanism passes development, author and seal a
new 36-source packet before output: 3domains × 6semantic dimensions × 2distinct
sources. Each domain includes short and multi-clause material. At least12rows
have protected names/tags/variables/escapes; include repeated/interior names and
unknown gender without dictating an unsupported address. Separately seal4long
stress rows (2within budget,2requiring the existing budget splitter). Pair source
facts with permissible readings and forbidden changes, not a preferred answer.
Record author/rights, IDs, exact source, metadata, expected propositions and SHA.
Do not build this new packet merely to run another unsupported mechanism.
The 36+4 packet is a design only: its actual sources and seal/digest do not yet
exist. Only the earlier explicit frozen source files have recorded digests.

Review order: seal source/criteria → record fixed candidate/code/runtime/model
identities → run one baseline/candidate within frozen budget → source-aligned
agent review with arm labels concealed where feasible → reveal arms and compare.
If the same agent authored or saw development outputs, disclose that; do not
call it blind/human review. A second read-only Brain review can challenge facts,
but consensus is not human gold. No fresh-output tuning; fail means retain and
reject or establish a distinct causal premise before another experiment.

Admission of a bounded mechanism requires at least2 complete semantic repairs
across2dimensions, lower any-major row count, zero new major cases across all
controls, zero structural failures and no increased unavailable translations
claimed as gains. Uncertainty never counts toward the minimum. Actual product
pipeline/cache/CSV/patch/readback and runtime/cost/cleanup gates follow before
product promotion. These are minimum experimental gates, not proof every future
sentence is correct or permission to announce whole-app quality complete.

## Capability shortlist closed against installed artifacts

Read-only installed metadata: CT2 4.8.1, transformers5.20.1, sentencepiece0.2.2,
numpy2.5.4; no torch or sacremoses. Local model directories are existing OPUS
INT8 and historical Hy-MT2 GGUF; the latter remains rejected/test-only and was
not loaded or promoted. OPUS provenance/notices are in THIRD_PARTY_NOTICES.md;
public paper code licenses do not authorize copying code or distributing weights.

| Option | Concrete next evidence / existing capability | Cost and authority | Current disposition |
| --- | --- | --- | --- |
| CT2 exact target prefix | Installed API and four actual constrained outputs; initial name is exact but forgot/borrower/serial errors remain | Same weights/runtime, measured2.844s/200802304bytes; no new license artifact | Rejected semantic remedy. No additional prefix variants or fresh run |
| CT2 arbitrary positive lexical constraints | Need enforce required sequences anywhere while preserving whole context; translate_batch signature has prefix/suppression but no such argument | Would require backend/custom decoding work; no dependency or architecture authority. score_batch/generate_tokens are not a ready GBS/DBA implementation | Research only; request exact backend-extension scope before implementation, not a generic model change |
| Attention/unknown copying | Inspect whether actual failing target contains UNK before proposing replace_unknowns; retained Mila/Mita outputs are known tokens | Existing return_attention/replace_unknowns, but no semantic guarantee. A matrix alone cannot identify a safe referent rewrite | No matching premise for current failures; no new inference justified |
| Trained coverage/context mechanism | Need trained coverage/context behavior matching model architecture, then license/runtime and semantic validation | Tu et al. coverage changes learned attention; current weights lack this demonstrated mechanism. Training/new weights not authorized | Explicit external action would be authorizing a bounded trained-model/data feasibility study, not installing at will |
| Likelihood/n-best reranking | Need an independent, calibrated adequacy signal that penalizes observed role/term/omission errors | Installed score_batch ranks model probability; no independent semantic evaluator is installed. New evaluator download outside scope | No candidate selection rule justified; do not rerank by longer output or term counts |
| Reviewed correction through existing editor | Can apply explicitly approved targets only at exact package/source/file/context/method; implemented native evidence exists | No new dependency; requires actual approved targets and remains manual/exact reuse | Available product route, does not meet automatic new-sentence objective and cannot be relabeled as one |

Primary sources: [CT2 Translator API](https://opennmt.net/CTranslate2/python/ctranslate2.Translator.html),
[CT2 decoding](https://opennmt.net/CTranslate2/decoding.html),
[Grid Beam Search](https://aclanthology.org/P17-1141/),
[Dynamic Beam Allocation](https://aclanthology.org/N18-1119/),
[trained coverage model](https://aclanthology.org/P16-1008/).

## Actionable boundary

Executable now without inference: review sealed source facts/rubric, inspect
retained failures/capability signatures and identify a distinct causal code
defect if one emerges. No additional model run is justified by this shortlist
alone. Existing failed beam/carrier/segmentation/full-sentence/prefix hypotheses
stay rejected; no silent fallback to historical Hy or source answer banks.

Concrete external actions that could open a new route are (a) authorize a bounded
backend-extension feasibility for arbitrary lexical constraints with same OPUS,
or (b) after permitted read-only candidate-model/data selection, authorize a
specific weight-download or training feasibility action with resource/license
preflight. Reading public candidate metadata itself needs no new permission.
Neither is automatically a remedy for all semantic errors; the rubric above
must still reject role/meaning regressions. No action is taken on those external
changes here. The active whole-quality task remains incomplete.
