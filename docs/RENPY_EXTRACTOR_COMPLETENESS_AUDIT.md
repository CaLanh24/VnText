# Ren’Py extractor completeness audit — 2026-10-21

## 1. CURRENT RENPY PIPELINE

Investigation only, source `0344b882066dffd501236769530d90f466c2157b`.
No production, extractor, patcher, CSV schema, validator or engine boundary changed.
No translation model, Unity audit, user game or existing game data was used.

`renpy_adapter.detect_engine` discovers loose scripts, compiled scripts and RPA members.
`app_tasks.run_extract_task` selects either SDK/native-template extraction, the explicitly
partial no-SDK line fallback, or inert compiled AST extraction.
`renpy_toolchain.copy_template_workspace` prepares an isolated source slice and
`generate_empty_vietnamese_template` runs the pinned official SDK8.5.3.
`renpy_extract.parse_renpy_translation_templates` parses native units; source enrichment,
source/container hashes and native IDs produce Entry/native contracts.
`package_io` and `mt_classify` filter candidates and emit CSV/manifest/coverage.
`patch_pipeline` dispatches to `patch_renpy`: source/hash/identity preflight,
transactional native overlays, activation and read-back report. Generated payload is
`game/tl/vietnamese/vntext.rpy` plus `game/zzz_vntext_vietnamese.rpy`.

## 2. CURRENT SUPPORTED SURFACE

| Surface | Observed scope and limitation |
|---|---|
| `.rpy` / `.rpym` | SDK-generated dialogue/menu/marked strings; NOT every legal Say or screen statement |
| No SDK | Regex fallback; dialogue lacks authoritative IDs, review/partial; not a completeness path |
| `.rpyc` / `.rpymc` | RPC2 slot2, unlocked version5003000, inert opcode traversal; static TranslateSay subset only |
| `.rpa` | Bounded RPA2.0/3.0 index/member reader with hash identity; workspace member-root gap below |
| Existing translations | SDK units are reused; parser assumes tightly generated formatting even for pre-existing overlays |
| Dynamic text | Literal templates may be recoverable; computed final values are outside static extraction |

Unsupported pickle opcodes, AST schemas, attributes/arguments and archive headers fail closed.
Compiled unresolved nodes are reported PARTIAL, not silently COMPLETE. Loose SDK accounting
closes over SDK-produced units, not all visible text: basic fixture reports COMPLETE while
two unmarked static UI literals are absent. This distinction must remain visible in claims.

## 3. REFERENCE TOOLS USED

* Official Ren’Py8.5.3 installed SDK: actual template generation, archive-loader readback,
  native dialogue/string lookup and lint. Current web docs are8.5.4; they are conceptual
  references, not substituted for the executed8.5.3 oracle.
* unrpyc `3ae8334ed71a05535927dcc559663d3aca51215b`: actual CLI recovered the generated
  compiled basic script, exit0. MIT, bundled codegen BSD; only isolated tool use.
* rpatool `74f26d5dfdd645483e02552aa766ca447ad6b191`: independently created RPA2/3;
  VNText recovered exact bytes/nested members. WTFPL. Repository says development migrated
  to Codeberg; this historical GitHub commit is pinned, not described as latest maintained.
* Independent substitute for RPG_Translator: yschdxm/renpy-translator
  `4cbb00cee29c73a66437cc0828ba0a88bcb40873`, MIT. Actual `RenpyParser.parse_file`
  on the same frozen scripts, `extract_ui=True`; raw outputs retained.
* Translator++ repository `ec99c9841eca230e2c1291cba617d142658b1d0d`, GPL3:
  repository tree contains no Ren’Py implementation to execute in this checkout.
  Documentation/declared capability only; **D inventory NOT AVAILABLE**, no fabricated delta.
  The independent MIT comparator supplies an executable P1 view, not a claim of equivalence.
* huchukato/RenPy-Translator was considered but rejected as the executable comparator:
  root license was unspecified and its archive wrapper deletes extracted archives. Not run.

No reference implementation was transplanted into VNText. Downloaded tool code was confined
to registered disposable TEST_RUN fixtures; only URLs, hashes and observations are retained.

Sources: [Ren’Py translation](https://www.renpy.org/doc/html/translation.html),
[dialogue](https://www.renpy.org/doc/html/dialogue.html),
[unrpyc](https://github.com/CensoredUsername/unrpyc),
[rpatool](https://github.com/shizmob/rpatool),
[independent parser](https://github.com/yschdxm/renpy-translator),
[Translator++](https://github.com/dreamsavior/TranslatorPlusPlus).

## 4. FIXTURE / CORPUS USED

Generated project-owned scripts only, no external-game corpus. Canonical frozen input:
`evaluation/renpy_completeness_audit_v1/ground_truth.json`, SHA256
`39e9a61a37d47f660ba8a3ebea244a423a99daae5353373821be2cd89a953491`.
Expectations were written before extraction and remained byte-identical across continuation.

Six cases: basic, multiline, single-quote, literal-speaker, Say-suffix, existing old/new.
Basic includes narration, characters, nested menus, screen text/button/tooltip, repeated
dialogue/speakers and repeated UI string, Japanese, colon/brackets, escaped quotes,
`[name]`, `[name.upper()]`, `{b}/{i}/{color}/{w}/{p}`, whitespace, paths, identifiers,
Python/code/internal strings and a dynamic concatenation. Old/new and runtime fragments
are explicitly conditional. Empty lexical string has no independent fixture: NOT COVERED.
Compiled-only case uses the actual SDK-produced `.rpyc`. Two RPA versions each contain
two archives with nested paths; a separate root probe compares standard vs `game/` prefix.
Original literal line numbers, speakers, native IDs and contexts are in raw inventories;
ground truth's generic context labels are not a complete hand-authored branch-context oracle.

## 5. COVERAGE RESULT

**Bounded six-case translation-unit recall: 15/19 = 78.95%.** Dialogue occurrences count
separately; identical string-translation sources count once, matching Ren’Py's global old/new
identity. This is not sentence sampling or whole-game recall. By case: basic12/14,
multiline1/1, single-quote1/1, literal-speaker0/1, Say-suffix0/1, old/new baseline1/1.
The two existing old/new values and the dynamic fragment are excluded, not relabeled misses.

Basic B inventory and A agree on native units except filtered whitespace; B also does not
discover the two unmarked UI literals. Thus A=B does not establish user-visible completeness.
Compiled version of basic: A retains6 dialogue rows, while unrpyc recovers the menu, screen
and Python source as well. Do not translate every recovered literal: code/path/internal
negatives remain negatives. Both RPA source fixtures initially emit0 rows; root probe proves
0 for standard member vs1 for identical `game/`-prefixed member. Those archive comparisons
are separate from the19-unit loose-source denominator.

## 6. PRECISION RESULT

Against the locked negative policy:15 positives/16 emitted loose-source rows =93.75%.
The extra row is `images/bg.png` inside `text _(...)`. **This is a policy-sensitive candidate,
not a confirmed classifier bug**: it is visibly displayed text despite resembling a path.
Changing the frozen label would inflate the metric; therefore retain the number but mark
semantic precision NOT CONCLUSIVE. Plain code `INTERNAL_KEY_001`, raw path and variable
identifier are absent; whitespace-only marked text is filtered. No confirmed technical-code
false positive warrants a shared-classifier change from this corpus.

## 7. PATCHABLE / ROUND-TRIP RESULT

* Basic13 emitted rows: native readback confirms6 distinct dialogue identities and7 global
  string mappings, including preserved placeholders/tags/expression syntax. Original source
  script hash unchanged; SDK lint exit0. Synthetic target is `VI ` plus exact source, not MT.
* Duplicate dialogue native IDs remain distinct (`start_6d82fa01`, suffix`_1`, different-speaker
  `start_f5c93d47`). Repeated UI source intentionally maps once; source line26 retained,
  line27 not separately represented. Global patch affects both; this is not a confirmed
  duplicate-patch bug, but full occurrence/screen context is not preserved.
* Extract→patch→apply overlay to disposable copy→extract again **FAILS**:
  `vntext.rpy:3: native translation block must have a blank line after header`.
* Multiline/single-quoted rows have native IDs but enrichment MISMATCH, no exact source_span
  or adjacent context. Not an extraction miss; patchability beyond admitted basic rows was
  not runtime-tested. Do not count complete contract-shaped rows as full patch acceptance.
* PATCHABLE_RECALL over all required cases: **NOT_MEASURABLE** with this coverage/readback set.
  Structural/native lookup is demonstrated for the13-row basic subset only; no visual UI,
  gameplay, arbitrary-Python evaluation or whole-game round-trip claim.

## 8. VNTEXT MISSES

| ID | Category / frozen location | Observed delta |
|---|---|---|
| R1 | DIALOGUE; literal-speaker script:2 | SDK yields `Literal speaker dialogue`; A aborts entire extraction |
| R2 | DIALOGUE; Say-suffix script:3 | SDK yields `Timed dialogue` with `with dissolve`; A aborts |
| R3 | SCREEN_UI; basic script:23–24 | Static plain screen/button literals absent despite COMPLETE; B misses them too |
| R4 | USER_TEXT / archive recovery | Standard nested RPA member is readable, but omitted from workspace/source recovery |
| R5 | LOCALIZATION_STRING / re-extract | Own valid applied overlay makes subsequent extraction fail |
| R6 | MENU_CHOICE/SCREEN_UI/LOCALIZATION_STRING compiled | Recoverable compiled nodes excluded; accurately PARTIAL, declared limitation |

## 9. VNTEXT FALSE POSITIVES

One path-shaped, explicitly displayed localized string conflicts with locked negative policy.
Disposition UNKNOWN / product policy, not automatic bug. No code/variable/label name leak
was observed. No classifier or validator relaxation is proposed.

## 10. REFERENCE TOOL MISSES

Official translation generation omits unmarked UI literals. The MIT independent parser
finds literal speaker/Say-suffix and plain screen text, but misses single-quoted dialogue,
multiline dialogue, wrapped tooltip/button and local `_()` strings in this invocation;
menu labels are classified as narration, escaped source remains escaped, and its UI scan
adds Character/default names. It is not a patch/location oracle. unrpyc reconstructs source,
including code negatives, without classifying translation eligibility. rpatool's create API
refuses3.2; this is NOT an executed3.2 compatibility verdict. Translator++ D-A remains UNKNOWN.

## 11. ROOT CAUSE PER CONFIRMED ISSUE

* R1/R2: `renpy_extract._statement` takes the first double-quoted slot and only accepts
  identifier words before it and a comment after it. Literal speakers and legal trailing
  clauses violate this narrow template grammar. Parser is all-or-nothing, so unrelated units
  in the same selected template cannot survive. `_parse_native_block` propagates the error.
* R3: SDK scans translatable native dialogue and marked/menu strings, not every screen
  literal. VNText adds no screen-language candidate inventory and COMPLETE checks only the
  generated native accounting. Completeness premise is smaller than the requested surface.
* R4: `renpy_toolchain.copy_template_workspace` requires member first component`game`,
  while `renpy_adapter.detect_engine` accepts any `.rpy` member and the archive reader and
  official loader accept game-relative names. Member-root interpretation differs across seams.
* R5: `patch_renpy._render_overlay` emits no blank line immediately after translate headers
  and no generated provenance comments. Workspace copies existing `tl`; template parser
  scans every selected-language `.rpy` and requires both generated shapes. Adding one blank
  line alone is not sufficient because source provenance expectations also differ.
* R6: `renpy_compiled.compiled_dialogues` explicitly admits only TranslateSay and a tiny
  non-text AST allowlist. Menu, Screen, Python etc. populate unresolved errors, not candidates.
* Context limitation: `_resolve_source_enrichment` is line/double-quote based; screens are
  not modeled and multiline/single quote enrichment fails. Native IDs still bind dialogue.

## 12. REMEDIATION CANDIDATES — NOT IMPLEMENTED

| Owner / minimal proposal | Gain / risk / decision |
|---|---|
| `renpy_extract` native Say grammar | R1/R2; retain native identity, speaker/expression and suffix semantics; risk wrong speaker/arguments. Bounded implementation task needs PM approval |
| `renpy_toolchain` archive namespace + provenance mapping | R4; map game-relative vs legacy-prefixed names explicitly, preserve raw member/hash, reject alias collisions/traversal; risk hash/patch-path drift. PM approval |
| `renpy_toolchain` + `renpy_extract` existing-language input separation | R5; distinguish new generator artifacts from existing native overlays, validate existing mappings separately; preserve IDs/conflict/rollback. PM approval; no generic format relaxation |
| `renpy_extract`/toolchain screen candidate ledger | R3; inventory static unmarked UI without admitting unproven rows; native patch proof or REVIEW_REQUIRED. PM chooses supported scope/write-back strategy |
| `renpy_compiled` typed node coverage | R6; first Menu/static marked strings, retain inert parsing/version bounds and explicit PARTIAL. Separate PM implementation scope; never execute recovered game code |
| Source enrichment owner | Richer source spans/screen/branch context without changing source_text/native identity. Context benefit; no demonstrated patch failure yet |

All are Ren’Py-specific; no Unity change, schema change, copied reference code, broad rewrite,
shared-validator loosening or production fix is authorized by this investigation.

## 13. TESTS TO ADD

Use existing Ren’Py suites: `test_renpy_adapter`, `test_renpy_archive`, `test_renpy_extract`,
`test_renpy_native_template`, `test_renpy_native_extract`, `test_renpy_native_sdk`,
`test_renpy_compiled`, `test_renpy_patch`, `test_renpy_extract_task`, patch-delivery/worker gates.
Add frozen literal speaker, trailing Say clause, whole-package failure accounting; standard
RPA2/3 member roots and cross-archive alias collisions; own-overlay re-extract with existing
strings/conflicts; plain/wrapped screen text/button/tooltip; repeated source in two screens;
empty strings, `{#context}` distinctions, multiline/source normalization and compiled Menu/UI.
Native lookup must verify exact speaker/ID/string targets; runtime-only concatenation must
remain explicit and must not generate fabricated static text. Then affected Ren’Py regression.

## 14. RISKS / UNKNOWNS

No real-game corpus; conditional existing translations and runtime concatenation are not
scored. Generated empty-string and `{#context}` cases remain untested. Full screen/branch
context oracle is incomplete. RPA source readability is proven, not proof that Ren’Py executes
archived `.rpy` directly (official lint reports no dialogue for the archive-only loader probe).
Therefore R4 is a discovery/recovery contract gap, not an asserted observed gameplay omission.
RPYC older schemas/locked scripts/compiled archives and RPA1/3.2 are not runtime validated.
No direct runtime-string observation or visual rendering acceptance. No full regression/build
was run: production files unchanged. Initial audit harness failed on a self-generated RPA3
protocol2 bytes reducer; corrected fixture encoding to protocol5, preserved original failure,
resumed required stages. This was not mislabeled a product RPA bug.

Raw results/reference inventories/native readback/commands are in the adjacent evaluation
folder. Canonical wrapper receipts are retained in `DEV_RUN/renpy-audit-*.json`; first child
exit1 cleanup PASS, continued/reference/archive/native probes child0 cleanup PASS. All runtime
tools/copies were registered and disposed; terminal inventory is separately recorded.

## 15. FINAL VERDICT

**RENPY_EXTRACTOR_GAPS_CONFIRMED**.

Do not claim RENPY_EXTRACTOR_COMPLETE. R1/R2 and R5 are directly reproduced supported-source
and round-trip failures. R3/R4 are demonstrated static coverage/recovery limitations; R6 is
an honest declared partial surface. Next action: PM selects a bounded implementation task,
preferably R5 round-trip first, then R1/R2 grammar, R4 namespace and the UI/compiled scope.
No remediation was implemented in this campaign.
