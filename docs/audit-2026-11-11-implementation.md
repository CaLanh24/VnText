# Audit implementation - 2026-11-11

Owner approved all R01-R12. Local implementation only; no push, release, version/tag/model change. Root is sole temporary writer while the fixed Claude DEV is weekly-quota blocked. Prior 10 fixes are preserved in 242b5a9. Current source implementation is being validated; build/native results will be added at terminal.

| Proposal | Implemented owner / behavior | Verification / boundary |
|---|---|---|
| R01 | vntext/csv_editor_api.py: bulk uses Save transaction, expected revision, exact-byte backup, staged review reconciliation, ownership rollback; Undo checks committed revision and restores original bytes | Fault injection + existing Save tests; native pending. Optimistic multi-file recovery is not OS-level atomic CAS against hostile writers |
| R02 | release/budget_policy.json, dev_bootstrap.py, cleanup_work_artifacts.py: explicit normal DEV default; closed Setup-only 6.75GiB remains verifiable history, release base 6.25GiB | Profile/launcher tests; no budget raise, authority rewrite or rebaseline |
| R03 | tests/lib/registry_storage.py + compact_registry_history.py + work_paths: gzip immutable logical bytes; cold missing records retain provenance; historical ID ownership; lookup | 327 snapshots compacted; 33,872 records read back exactly; 6,026,304,367 bytes freed. Epoch file-chain verification has no failures. Logical SHA/bytes and epoch authority unchanged. Unresolved cold MISSING still REVIEW_REQUIRED |
| R04 | CONTRACTS and WORKFLOW compatibility routers; docs/contracts and docs/workflows own bounded topics with origin SHA/hash | Preserve original scoped decisions; relative links rebased; no historical task resumed |
| R05 | patch_plan.py pure grouping; mt_ct2_input.py read/validate; registry_storage projection; 21 CSV workflow test methods moved unchanged to Program.CsvEditor.cs | Characterization/order/filter tests + existing pipeline/cancellation/gate tests; no broad engine/UI redesign |
| R06 | requirements/locks: Windows x64 CPython3.12/3.14 runtime + isolated builder profiles; official artifact URLs/SHA256/dependency metadata | Both target graphs resolved and closure/hash checked. Installation/native on every lock target NOT_PROVEN. tpk_ar source-only build exception documented; no installed runtime upgraded |
| R07 | Qt removed from worker requirements; requirements-legacy-qt.txt optional; explicit missing QML reports unsupported | Existing Tk/Qt code retained; no silent QML fallback. Legacy GUIs not newly native-certified |
| R08 | App.xaml.cs and csproj: Debug/EnableDevProbes compilation boundary; Release retains product smoke/verify and ImagePackageProbe reader | Caller/source inventory complete; both build configurations pending. Explicit probe-enabled Release is a harness, not shipping artifact |
| R09 | tests/tools/audit_gates.py + .github/workflows/public-tests.yml: public deterministic vs installed/native groups; skip/blocker visibility | Public groups run locally; CI not pushed or triggered. Fixture-specific installed runtime is separate; native cannot be inferred from harness |
| R10 | release/impeccable-pin.json + verify_skill.py + .agents/skills/vntext-ui adapter | Canonical shared 4.8.0 read-only; 63 files verified. Old local package had five upstream revision differences: exact legacy hashes and diff retained before duplicate removal. No shared-tool changes/download |
| R11 | tests/lib/dev_projection.py + WORKFLOW caller example | Structured latest result/cursor only; no text/history fallback; projection tests. Shared bridge unchanged/not reconnected |
| R12 | tests/golden/mt-quality/corpus.json + mt_quality_corpus.py; glossary sentinel protection in mt_ct2_io; cache strategy revision bumped | First real offline run found glossary sentinels corrupted by model. Fixed by keeping exact row glossary tokens out of model. 12 synthetic cases rerun; randomized opaque-arm review saved before unblinding. Basic Vietnamese/spans/terms PASS; power-drunk and menu wording remain semantic limitations. Single model-assisted reviewer, not human-panel or whole-game acceptance |

## Storage ownership and disposition

History/registry: retained as compressed authenticated evidence, including exact pre-compaction live registry rollback. Cold records are not deletion receipts and are not promoted. Shared .dev-env/model/runtime resources and Owner candidates/data remain protected. Local duplicate skill package removed only after exact pinned inventory comparison. Dependency-resolution scratch and synthetic MT fixtures are disposable after compact receipts are copied. New audit candidate will have its own output, not overwrite the previous candidate. Global historical cleanup remains REVIEW_REQUIRED; this task does not certify every legacy missing artifact.

Evidence: C:/vnrg/evidence/audit-followup (registry plan/receipt, initial failed and corrected tests, logs, blind MT inputs/review/map/provenance). Preexisting audit patch retained. No original game, save, CSV/glossary user file or installed app was modified by this audit.

## Acceptance still running

Focused transaction/storage regressions, glossary/context/name/cache tests and public groups have bounded evidence; full cleanup compatibility suite and final public-group rerun are in progress. Build/smoke/native are NOT_RUN until matching receipts exist. The old candidate f192638 is not acceptance for these changes. No Release acceptance is claimed.


Native followup caught a real R01 integration gap at source58c181f: WPF bulk did not forward the opened CSV SHA, although API CAS tests passed. The inert fixture proved a foreign revision was overwritten. That run is FAIL and retained in native-external-after.json/screenshot, never relabeled. The WPF caller/service now carry the loaded SHA through Apply and Undo; a service-to-Python regression reproduces the same stale opened revision. Rebuild and live retest required for this correction.
