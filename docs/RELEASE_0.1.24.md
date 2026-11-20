# Release 0.1.24 — Ren'Py locale image overlay, Unity TMP font adapter, Unity read-back/extract fixes

Owner 2026-11-20: native ACCEPT on `603e86b` (The Wrath original, both fonts: title, first choice and the Arthur line, exact rollback); release is conditionally authorized **after the gates**. Not published by DEV (Brain reviews, then publishes). Public baseline is 0.1.23.

## Scope (source)
- `vntext/renpy_image_overlay.py` + `image_overlay_spec` worker param: known-asset, geometry-preserving locale images for imagemap/imagebutton bitmaps (CONTRACTS §8).
- `vntext/unity_tmp_adapter.py` + `wpf_app/VNText.UnityTmpAdapter/` (built by the publisher into `worker/vntext/unity_adapter/`): Mono/TMP global-fallback font adapter for validated Unity versions; MemberRef gate `tests/tools/unity_adapter_memberref_gate.ps1`.
- Installer binds player assemblies for Unity manifests (`game_checks`).
- Unity patch: v22+ TextAsset slot-fit, no `backup_original` for originals over 1 GiB, writer graph released before read-back, read-back child report channel isolated, exit/stdout diagnostics.
- Extract: Naninovel localization TextAssets are accepted by their exact header (400+ KB English chapters were silently dropped by the whole-document noise filter).
- Registry tooling: per-task scope-recovery quote, 0.1.24 budget expansion (8060 MiB) and one-shot rebaseline authority.

## Native evidence (Brain, Owner-authorized, originals untouched after rollback)
`TEST_RUN/renpy-three-game-qa/wrath-opening-*-{menu,choice,line}.png`, `wrath-v24-opening-*-undo.txt`; compact payload evidence `wrath-patch-opening-dejavu-final-evidence/` (manifest, in-pipeline read-back PASS 9/9, data.unity3d sha256 `e78c234e…b072`). Lesson/Dissonance patches: `TEST_RUN/renpy-three-game-qa/renpy-payloads-0124-receipt.json`.

## Limits
Unity text rows are slot-fitted (translations no longer than the original bytes); TMP text only; validated engine `2022.3.16f1`. Runtime font rendering is proven only by the native runs above on The Wrath.
