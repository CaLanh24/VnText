# Translation delivery — 2026-10-21

Owner authorized finishing the accepted work and pushing it to the existing
repository before starting another plan. This delivery does not reopen the
paused semantic research, change the product model, or publish a Release.

## Delivered behavior

- Flat glossary masking preserves placeholders, control spelling and tags;
  malformed exact targets cannot inject or drop structural tokens.
- Required glossary wording is checked after normal translation, retry and
  synonym handling before writing or caching a candidate. Refusal is a safety
  result, not a semantic improvement.
- Sentence-initial commands and vocative titles are no longer automatically
  treated as names in the demonstrated lexical cases; genuine protected names
  remain protected.
- Reviewed memory requires the exact package, source, file, full context and
  import method. Invalid, copied or stale approval artifacts cannot authorize
  lookup, cache reuse or rebuilding from arbitrary CSV translations.
- The WPF CSV editor can preview selected saved rows and explicitly confirm or
  cancel their approval for reuse within the current package. Preview is read
  only; confirmation revalidates disk data and validation inputs, retains legacy
  backups, and rolls back only bytes owned by the operation. App strings use the
  existing Vietnamese/English resources; backend errors retain their existing
  Vietnamese limitation.
- Required token-budget chunks retain their original source whitespace when
  translated chunks are reassembled. Hard cuts do not acquire invented spaces.
  The cache decoding profile changes to prevent reuse of prior concatenation.

The product still uses CTranslate2/OPUS-MT. No Qwen weights, dependencies,
default answer bank, user/game data, generated application binary or raw large
log is included in this commit.

## Evidence and acceptance

The original four-requirement remediation/evidence campaign and bounded editor
feature were accepted by Brain. The later whitespace fix was accepted separately.
The immutable receipts preserve their original pending labels and historical
working-tree snapshots; those labels are not the current acceptance pointer.

| Evidence | Current interpretation |
| --- | --- |
| `evaluation/translation_quality_goal_v1/completion.json` | Accepted original bounded campaign, not whole-language quality |
| `evaluation/translation_owner_approval_v1/entrypoint-ui-delivery.json` | Accepted editor/UI source and native evidence; 32/33 recorded file hashes still match |
| `evaluation/translation_semantic_campaign_v1/boundary-delivery.json` | All seven later source/test hashes match; supersedes the older cache-test hash |
| `evaluation/translation_delivery_v1/manifest.json` | Final delivery audit and compact current packet-verification result |

All 17 changed runtime/WPF source files match the union of the accepted editor
and boundary receipts. The sole superseded editor source/test hash is
`tests/unit/test_translation_cache.py`, subsequently updated for the boundary
cache profile and covered by the boundary receipt. All 16 editor external
receipt/image hashes and 15 boundary external receipt hashes matched during
delivery. Public compact receipts are retained in Git; guest-only raw evidence
is optional audit material and is not a prerequisite for a public clone.

Accepted existing gates include 66 editor/backend tests, 14 strict-memory tests,
161 affected tests in the strict pilot, the localized WPF harness, generated
extract/import/approval/reuse/patch/readback, and current DEV build/worker smoke.
The boundary receipt records final 17 model/cache tests, eight boundary tests,
16 configured worker tests, generated workflow and DEV validation. These are
overlapping focused gates, not a newly summed full-suite result. Existing
failures, corrected setup attempts and raw warnings remain in their receipts.

For delivery, the exact-byte review and approval packet verifiers ran through
`tests/tools/run_with_cleanup.py`: eight tests, zero failures/errors/skips/warnings,
child exit 0 and cleanup PASS. This verifies packaging/provenance after the Git
attribute review; it does not rerun inference. Python AST and JSON parsing and
Git whitespace checks passed. Historical three external Unity fixture skips,
installer-absence caveat and optional tokenizer warning/no-PyTorch information
are not erased by this delivery.

The accepted DEV apphost SHA256 is
`6fe96ea326bae10f40e84ec08bf56b59bf24d11055df263e1153fd6f86826c3d`;
the WPF assembly SHA256 is
`1ee94e05f467ec723639242314a9670c31f6a55b7979ad468525953bfa064821`.
Both were checked unchanged. Runs used base
`c9825d466ada179b39bca7968f6f50c43e95b412` plus recorded dirty source hashes.
Committing later does not relabel those builds as exact-commit or Release builds.
Earlier native functional cancel/confirm was accepted; the final styled Cancel
input remained tool-refused. Original screenshots are JPEG, not PNG.

## Paused research and remaining limits

The 17 translations and six terms retain their separate Owner-delegated Brain
decision. They are synthetic seen examples, not human gold, training data approval
or app-wide defaults. The original pending proposal packet remains immutable.

Whole-app/new-sentence semantic quality remains NOT accepted. Idiom, omission,
actor/recipient, register/gender and technical-sense residuals persist. Beam,
full-sentence and prefix hypotheses were rejected in their recorded controls.
Pinned Qwen was acquired locally as a test-only candidate; its first load hit
the RAM guard and produced no semantic output. No fresh-control Qwen result or
product integration is claimed.

Owner explicitly paused the plan for guest RAM. The one-shot external deferred
runner ended `CANCELLED_BEFORE_LOAD`; its worker and launcher exited. TEST_RUN
and RELEASE_RUN are absent. No watcher, automatic restart or inference resume
is authorized until Owner explicitly reopens the plan. Retain current DEV,
verified model/license/ownership and all failed/raw/history evidence.
`TRANSLATION_SEMANTIC_CAMPAIGN_20261021.md`, `QWEN_RESOURCE_READINESS.md` and the
frozen protocol provide the public resume context; local checkpoint paths are
supplementary, not required repository inputs.

## Git delivery boundary

The fetched remote default branch is `main`, at
`10873fc61db4f97db9a42d63fcac9f8b993e3570`. The local base is 29 commits ahead
and zero behind. That linear outgoing range records the previously authorized
synthetic translation evaluation, zero-cost/resource research, rejected semantic
experiments, retry-carrier preservation, silver packet, glossary conflict fix and
canonical permissions/dispositions. The current commit adds the accepted bounded
runtime/editor fixes, tests and their review history. None requires force-push.

All 202 outgoing historical blobs were inspected by type/size: the largest is
272,360 bytes, with no binary delta or detected private-key/token pattern. The
new changed-file audit likewise found text-only scoped files and no detected
secret pattern. Pattern checks are evidence, not a universal secret detector.
The authenticated GitHub user is `CaLanh24`, numeric ID `316325487`, display name
`Calanh`. Commit attribution uses that verified account's public GitHub noreply
identity per command; repository/global Git configuration is not changed.

Final candidate commit and remote readback are reported in the delivery handoff
after creation. A normal push must refuse any non-fast-forward remote change;
no reset, stash, history rewrite, tag or Release publication is part of delivery.
