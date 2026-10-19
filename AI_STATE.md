# Current state pointer — 2026-10-19

## Phase9 research closed: source constraints PASS bounded; no semantic promotion
- Owner: source obligations for who-gives-to-whom, age, negation/permissions; autonomous bounded retry; product OPUS unchanged. Canonical docs/TRANSLATION_QUALITY_PLAN.md Phase9; TEST_MATRIX.md.
- Finite grammar compiles role/kinship graph and Boolean truth table/action/object, compares Vietnamese; FAIL/UNKNOWN/CONSTRAINTS_MATCH. MATCH is not full translation acceptance. No same-model judge.
-59focusedPASS. Old24fixtures10correctMATCH/11badFAIL/3UNKNOWN; fresh36(12correct/24bad) all expected statuses,0falseaccept. Agent-authored template-directed fixtures, no human gold/general-language claim.
- New16synthetic(8dev/8heldout), unique vs248prior eval strings; final22modelcalls/10propertyMATCH+6UNKNOWN/0tokenmismatch/allEOG.8/8address agent/recipient/owner correct by agent review. All16NEEDS_REVIEW,0automaticsemanticacceptance.
- Remaining: correct paraphrases outside grammar, Reject English, ambiguous eligibility. One retry may worsen ambiguity; preserve both. Agent core table OPUS7/7 vsHy1clearmajor+1ambiguous; role-only violations separate.
- Evidence DEV_RUN/translation-quality-phase9/REVIEW.md + rawselection/fixtures/summary/wrappers/terminalquota; sourcebase21e0f96+perrunhashes. Allnew sources/checkerfixtures now seen; older evidence in canonical plan.
- Allwrappers0/cleanupPASS; TEST_RUN/RELEASE_RUN absent; artifact1GiB/shared6GiB/VM4GiB unchanged. No app/model/worker/validator/dependency/system/DEV/release/push changes.

## Product/release pointers
- CT2/OPUS remains product route. Last recorded public0.1.8 bounded installed update acceptance: `docs/RELEASE_0.1.8.md` (immutable build1cd24b2); whole-product RELEASE_VERIFIED not inferred.
- UI/settings: `docs/SETTINGS_PLAN.md`, `docs/UPDATE_UI.md`; automatic images: `docs/AUTOMATIC_IMAGES.md`.
- Earlier research measurements and rejected candidates: canonical translation plan; ignored local evidence is not a public-clone prerequisite.
