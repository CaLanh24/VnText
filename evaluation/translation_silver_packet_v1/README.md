# Phase19 silver research packet — M1–M4, 2026-10-20

This is an offline packaging of existing agent-authored synthetic sources and
historical model outputs, **not new inference, human gold, training data approval,
translation memory approval, product acceptance or an unseen benchmark**.
Owner authorized this bounded execution after the zero-cost proposal. DEV is the
only implementation writer; Brain performs read-only acceptance. No child or
paid service was used. Product CT2/OPUS and all product stores remain unchanged.

## Contents and offline verification

Run from repository root with existing Python, without model/dependencies/network:

```
python -B tests/tools/translation_silver_packet.py verify
```

The verifier uses only this tracked packet and the tracked source dataset
`evaluation/translation_quality_phase19/dataset.v1.json`; it does not read
`DEV_RUN` or instantiate an inference library. A fresh public clone can verify
source rights/projections, content hashes, A/B mapping/seal, original grades,
adjustments, selection policy and exact memory provenance. It cannot rerun or
cryptographically prove the historic model execution from these compact values.
Scoped `.gitattributes` preserve packet bytes, source-dataset CRLF and verifier
LF across checkouts so automatic line-ending conversion cannot invalidate hashes.

| File | Meaning |
| --- | --- |
| `manifest.json` | Build base SHA, source rights pointer/digest, builder digest, all payload file hashes/counts and restricted use. Manifest itself is not self-hashed; final receipt/Git commit anchors it. |
| `evidence/outputs.json` | Exact JSON-value projection: all60 original candidate records including raw/history/role edits/selection; all60 records from each original OPUS unassisted/glossary arm; original48-term bank. No output post-edit. |
| `evidence/run-identities.json` | Historic full-file hashes, source/code/model identities and canonical projection hashes. Original ignored full-file hashes are provenance references, not recomputable from projections. |
| `evidence/run-receipts.json` | Compact historic wrapper exit/test/cleanup projections with full original receipt hashes; not a new run or exact-current-HEAD test claim. |
| `evidence/blind-*.json`, `sealed-label-map.json` | Exact byte snapshots of original blind input/review/rubric/seal and original mapping. Original review said mapping_seen=false; mapping is public now. |
| `evidence/coordinator-blind-audit.json`, `unmasked-review.json`, `selection.json` | Exact historic adjustments, unmasked summary and frozen run identity. Four severity adjustments are kept separately from original grades/preferences. |
| `curation.json` | All60 source/context/right records, three output arms, original review, mapping, historical adjustments, per-arm dispositions and conservative current notes. All sources are seen development/regression; original split fields are historical only. |
| `audit12.json` | The12 current DEV source/mapping/severity audit IDs/notes for Brain cross-check. No new categorical severity replaces the originals. |
| `term-audit.json` | All48 terms: domain/counter-sense design, occurrences, exact positive observations and disposition. Counter-sense notes are manual scope proposals, **not model-tested negative controls**. |
| `candidate-bank.json` | Three domain-scoped silver term candidates: checksum, migration, copy. All need human review; no production import/training permission. |
| `memory-candidate.json` | Nine exact-source/context/scenario-key candidates from original OPUS glossary output, with typed resolvable provenance. Not approved translation memory. |

Schema/locator convention: dataset `rights_pointer=/provenance` is a JSON Pointer
into the tracked dataset; `bank_provenance=evidence/outputs.json#/term_bank` is a
file plus RFC6901 pointer. Memory `provenance` is a typed object containing
`file=curation.json`, `json_pointer=/rows/<array index>`, `record_id=<stable ID>`;
verification resolves it and checks ID/source/target. An `occurrence_ids` or
`positive_observations[].id` is a **record ID**, resolved against `curation.rows`,
not a JSON Pointer. Historic `historical_locator` is an optional original path,
never a required public-clone input. Row source/output hashes refer to values in
embedded evidence; original file hashes refer to bytes, without newline conversion.

## Positive reuse policy and exclusions

Source rights are `generated-for-project`, from the tracked dataset's top-level
provenance (Coordinator-agent synthetic). There are no unknown source-right rows
in this packet. This declaration concerns synthetic source rights, not human
authorship/approval of targets. Historical Hy model is pinned Q4 hash
`dc5f44fcf1fa496ee7ad725982c0c8c553a4de00259b53af84c4b89fb0c06699`;
OPUS repo/revision/file identities are in run-identities. Historical license
provenance is documented in `docs/TRANSLATION_QUALITY_PLAN.md` (Phase3 Hy Apache2.0)
and `THIRD_PARTY_NOTICES.md` (OPUS/CT2). No distribution/training permission is
inferred merely from a generated-for-project source label. All targets stay
research drafts with human review absent.

Per-arm original reviews are mapped first, then four explicit historic overrides
produce separate audited grades. Across120 reviewed outputs:51 retain_silver,
66 reject_positive_reuse (includes minor/major/unusable),3 uncertain. These are
output counts, not a new quality score or60-row PASS count. Unassisted OPUS has no
original blind semantic review; it is retained as raw reference, not a positive.

Memory uses a stricter fixed rule: **both** reviewed arms must be acceptable after
historical adjustments, then keep original OPUS glossary output by deterministic
source order (not aggregate model score or pairwise winner). Current conservative
concerns for Q19-ui-04 (undo versus cancellation) and Q19-dialogue-06 (masculine
listener address despite empty address context, identified in Brain's memory
membership review) exclude both despite original acceptable/acceptable. Nine
remain, not padded to20. The second is M3 membership review, not a thirteenth
M2 major/uncertain audit or new categorical verdict. Major, uncertain, rejected,
minor, unusable and current-concern rows never enter positive memory. Exact key
includes source, domain, address context and scenario boundary. No wildcard,
cross-scene reuse or product-store write is allowed.

Terms: six of48 occur in source with word boundaries;42 have no source occurrence
here and are excluded pending evidence. Of six, checksum/migration/copy have
exact target-phrase observations in historically acceptable drafts; archive has
unresolved file/repository sense, backup's row has the current undo concern, and
cancel target is only a larger phrase rather than the exact bank target. Those
three are excluded. Positive term observation does not approve the entire row
or establish counter-sense robustness; e.g. copy has a valid candidate draft but
OPUS is empty, so this row is excluded from memory.

## Twelve rows for read-only Brain audit

Q19-dialogue-08; Q19-idiom-06; Q19-address-02; Q19-address-08;
Q19-address-10; Q19-ui-04; Q19-ui-08; Q19-terminology-04;
Q19-terminology-05; Q19-terminology-06; Q19-terminology-08;
Q19-protected_tokens-02. See audit12 and the joined row for original A/B/raw/
overrides. All four historic overrides are covered. The empty OPUS record is
workflow noncoverage, not a wrong written translation; raw preference remains
unchanged even when severity was adjusted. This audit is agent work, not blind
human semantic acceptance.

M1–M4 deliverables are present. This ends the authorized offline packet work;
training is **NOT_TRIGGERED / DEFERRED**, Hy admission REJECTED, OPUS unchanged.
No new held-out/generalization, gold, quality gain or training feasibility is
claimed. Missing human/compute prerequisites do not require hiring/rental to
close the research disposition. No further prompt/model campaign is implied.
