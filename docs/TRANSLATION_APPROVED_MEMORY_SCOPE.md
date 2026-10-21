# Approved synthetic memory: integration prerequisite proposal

Current disposition (2026-10-21): strict-memory pilot and editor integration completed and accepted in bounded scope. The initial unsafe legacy fallback premise below describes the pre-change implementation. Exact approval scopes are enforced by the delivered strict policy; no app-wide answer bank or human-gold claim. See TRANSLATION_DELIVERY_20261021.md.

Owner delegated semantic review to Brain at turn01a158d1; recorded decision is
`evaluation/translation_owner_approval_v1/decision.json`. Agent approval is not
human gold/training or whole-app acceptance. Original pending packet unchanged.
This proposal is not permission to distribute a default bank or mutate user data.

Existing `mt_memory.py` lookup key is normalized source/import_method/context
family. Unique same-method target can fall back across context families and does
not compare file_path. `build_translation_memory` reconstructs entries from CSV
and replaces its memory file, without approval-scope metadata. Thus simply
converting these17approved targets to the current native format is unsafe for
their narrower approval boundary. Six terms likewise cannot become flat global
terms; exact complete-sentence authority must precede partial terms.

Proposed additive seam in the existing memory owner, no worker-protocol/model
or architecture replacement:

- Legacy memory behavior remains explicit and tested. A separately identifiable
  strict approval policy, used only for this approved synthetic package, requires
  exact raw source/import_method/file_path/full context and a binding to the
  intended package location/identity. No normalized-only hit, cross-family or
  cross-file fallback for approved entries; duplicate/conflicting matches miss.
- Keep approval ID/proposal hash/reviewer kind/human_gold=false/training=false
  with scoped entries. Product storage contains only the allowlisted approved
  entries; no global source-to-answer table or package auto-discovery/import.
- Loader/cache fingerprints must include the strict policy and its scope fields;
  invalid/unknown policy must miss/fail closed. A corrupt existing store cannot
  silently trigger a legacy CSV rebuild that broadens those approvals.
- Rebuild after translation/retranslate/empty-target paths preserves strict
  policy, package binding and reviewed entries; it must not learn unapproved MT
  rows or drop restrictions. Existing frozenCSV behavior/structural QA preserved.
- Test-only preparation/integration helper may instantiate a fresh registered
  synthetic package from this exact decision, not user data. Positive17matching
  sources reuse approved translations via actual product route; negatives use
  identical sources in wrong context/file/package/case or unknown policy, and
  must not reuse those targets. Include all relevant cache/reopen/rebuild paths.
- Six approved terms are verification constraints for their named occurrences;
  full approved sentence takes authority. Never apply them to new scenes/word
  senses by substring scope, or claim automatic improvement on unseen inputs.

Required gate order if Brain accepts this bounded seam: focused legacy/strict
memory + malformed/conflict/scope/rebuild/cache tests; affected glossary/retry/
worker/status gates; one actual controlled reuse/read-back probe and hostile
scope negatives; final currentDEV rebuild/smoke and complete cleanup. No broad
100row/model benchmark rerun, no new dependencies, no training/model change.
Rebuild only after actual runtime edits, not for the approval-docs step alone.

Status: Brain accepted this bounded prerequisite in the current goal, following
direct review of decision/lookup repro. Schema frozen before runtime edits:

- Existing `.mt/translation_memory.json` keeps version1.0.0; strict stores add
  `scope_policy=strict-approval-v1`, `package_binding` (SHA256 of normalized
  resolved package path, no absolute path in tracked decision), `approval_sha256`,
  `review_kind=owner-delegated-agent`, and entries with existing normalized source/
  context_family plus `source_text_exact`, `context_exact`, `file_path_exact`,
  `import_method`, reviewed `translation`, approved=true/human_gold=false/
  training_eligible=false. Strict entries are only from the explicit decision.
- Sticky `.mt/translation_memory_scope.json` has version1, same policy/binding/
  approval hash and `entries_sha256` over canonical entry JSON. Presence of either
  marker or a strict store prevents legacy rebuild. Missing/corrupt counterpart,
  unknown policy/schema, mismatch or duplicates produces no strict reuse and no
  store overwrite/downgrade. No claim against deliberate removal of all package
  policy evidence; no security/authentication protocol is introduced.
- Loader attaches runtime package context for lookup binding checks; never stores
  guest absolute paths in tracked approval. Reopen/lookup validate binding and
  guard/store agreement. Rebuild retains the strict allowlist, never learns from
  rows and never repairs invalid approval evidence by guessing.
- Per-entry `approval_id` and `proposal_sha256` must map one-to-one to guard
  `approval_records` (proposal digest + digest of exact source/file/context/
  importmethod/target); root/guard also bind `proposal_file_sha256`. Missing,
  unknown, duplicate IDs, changed wording/scope or mismatched proposal metadata
  fail closed. The explicit fixture-preparation helper validates those records
  against the sealed decision/proposal; runtime validates local consistency,
  not external identity authentication or a new signature/security protocol.
- Existing whole-memory hash covers policy/binding/approvalset; strict cache
  additionally hashes exact raw context/file_path/import_method, so changing a
  file with stable key/source/context cannot replay approved cached text. Legacy
  fingerprints/precedence remain unchanged unless explicitly versioned.

Ownerfiles: `mt_memory.py`, `mt_ct2_pipeline.py`, `translation_cache.py` and
existing tests/new bounded synthetic helper. No worker protocol/model/framework
change. Gate order: focused red/green first, then affected glossary/cache/status/
worker suites; one registered actual product-route probe <=180s,17matching rows
plus<=6hostile scope/reopen cases, one primary disposable package and one bounded
copy for wrong-package binding (no game/model copies); then finalDEVbuild/smoke
<=600s and complete cleanup. No broad100 or additional model inference campaign.
Approval-doc8tests alreadyPASS; all runtime acceptance is still pending.

Implementation checkpoint: runtime owner/callers/cache updated, focused red
retained, coregreen then67focused/affectedtestsPASS0skip/warning/cleanupPASS.
Intermediate65test run had one legacy-context argument error; fixed by keeping
the dynamic approval snapshot out of legacy cache context and fingerprint args.
Latest receipt `translation-strict-memory-green-provenance.json`. Strict cache
hash includes exact file/context/method; legacy fingerprint keys unchanged.
Runtime rechecks guard/store before lookup and cached writes; stale snapshot
disables cache reads. Per-entry approvalID/proposal and scope-record checks now
implemented. Actual17matchingreuse/hostile scope probe, remaining affected worker
gates and final currentDEVbuild/smoke are pending. No complete/import claim.

Latest delivery: `evaluation/translation_owner_approval_v1/scoped-delivery.json`
supersedes that pending checkpoint. Actual registered synthetic probe17/17
reviewed targets reused through product selective route with0modelcalls;5wrong
context/file/rawcase/rawspacing/method misses exercise realOPUS; copiedpackage
binding rejects memory/cache; fullrun rebuild preserves exactpolicy/storebytes.
One negative unassisted row remains blocked (not a memory success claim).
161affectedtestsPASS0skip/warning; final14strictPASS adds samekey rawcasecachemiss
afterpositivecachehit. First161run had one testsetup missingargument, preserved.
CurrentDEVrecoverybuild/workersmokePASS, missingpatchinstaller caveat. Previous
wrapper interrupted without terminalreport; missingprocess/session recorded,
canonicalcleanupPASS then justifiedrerun; originalRUNNING never relabeledPASS.
Finalcompleteinventory UNKNOWN0/LOCKED0/errors0,oneDEVexe, quotaswithinlimits.
No global/userstore or newscene termbank installed; explicit syntheticfixture
only. Brain scoped/whole-goal acceptance and commitidentity remain separate.

Brain subsequently accepted **PASS scoped strict-approved-memory delivery** after
direct source/test/probe review and matching23currentruntime/test hashes plus
4canonicalreceipt/probe/executable hashes. No additional seam identified in this
bounded pilot. Acceptance does not mean human gold, model learning, unseen
quality, installer acceptance, exact-commit build or whole-app goal completion.
No gates rerun for this documentation-only acceptance record. Original raw
reports/approval packets remain unchanged. Next prerequisite is a concrete
real-user entrypoint for reviewed data: current instantiation uses a test helper,
not a general product import/UI. Inspect existing entrypoints and propose scope/
gates to Brain before source edits; no silent promotion of this synthetic bank.
