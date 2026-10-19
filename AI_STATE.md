# Current state pointer — 2026-10-19

## Research task closed: Phase5 PASS bounded guard/evaluation
- Owner: protect placeholders/symbols first, improve meaning, fresh corpus; keep OPUS in app.
- Canonical protocol/results: `docs/TRANSLATION_QUALITY_PLAN.md` (Phase5); gates: `TEST_MATRIX.md`.
- Dataset: `evaluation/translation_quality_phase5/dataset.v1.json`, 60 synthetic sentences /40dev+20heldout; hash199d5bde7dcf9b7ff9f2e08e0782a7ff88d39563b8cb0ec1a645c6570082759d.
- 23focusedPASS; actual old14guard/28comparison/17refinement calls and new60Hy calls completed. New60:0guardreject/0tokenmismatch/0existingstructuralfailure; no source guessing. Child/outer0/cleanupPASS, model hashes unchanged.
- Meaning agent review only: newheldout20 OPUSdefault7major vsHy3; Hyintroduces2newmajor. All60 OPUS17major+2blocked vsHy9major. Human acceptance NOT_CONDUCTED; no product promotion.
- Remaining: negation/outside eligibility inversion, idioms, software nouns, role address. Newheldout now seen: future tuning cannot reuse it as unseen.
- Evidence: `DEV_RUN/translation-quality-phase5/REVIEW.md`, raw/selection/wrapper/summary/terminal receipts there. Base2438c5c+perrun code/data hashes; later docs commit is not exact-HEAD app validation.
- Research-only `tests/tools/translation_quality_guard.py` and `translation_quality_phase5.py`; app/worker/model/framework/defaultOPUS unchanged, no DEV rebuild or release/push.
- TEST_RUN/RELEASE_RUN absent; non-exempt701307532<=1GiB/shared5778817474<=6GiB. Existing DEV executable retained. VM4GiB/no host changes.

## Product/release pointers
- CT2/OPUS remains product route. Last recorded public0.1.8 bounded installed update acceptance: `docs/RELEASE_0.1.8.md` (immutable build1cd24b2); whole-product RELEASE_VERIFIED not inferred.
- UI/settings: `docs/SETTINGS_PLAN.md`, `docs/UPDATE_UI.md`; automatic images: `docs/AUTOMATIC_IMAGES.md`.
- Earlier research measurements and rejected candidates: canonical translation plan; ignored local evidence is not a public-clone prerequisite.
