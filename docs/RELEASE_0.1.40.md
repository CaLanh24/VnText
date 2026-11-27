# Release 0.1.40 — everything found by running real games, in one release

The Owner asked (chat, 2026-11-27) to work through every item left open by 0.1.39 on the games installed on the machine, except sending a report to Discord, and to release once. The standing permission of 2026-11-25 applies. Task `release-0.1.40`, exact `RELEASE_RUN/candidate-0.1.40`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB.

Data rule (AGENTS 2026-11-21): the games were only read, or used through hard-link copies outside the repository; nothing was written to the originals (journey_check hashes them before and after). No game name, content or file name is recorded here; the corpus labels are `corpus-01` (Ren'Py, archive source, large), `corpus-02` (Ren'Py, loose source) and `corpus-03` (Unity, one 4 GB bundle).

## Changes
- **The font-size slider reached nothing.** The WPF app sent `font_scale`, the worker dropped it. Now forwarded (`test_worker_font_scale`). Checked in a running Ren'Py game: scale 0.70 visibly shrinks the generated Vietnamese font; Vietnamese diacritics render without missing glyphs and the text box does not overflow.
- **`translate` blocks that are a bare command (`nvl clear` and the like)** were reported as "unsupported" and kept the extract PARTIAL (191 of 197 in corpus-01). They hold nothing the player reads, so they are audited technical blocks. The other six shapes stay flagged on purpose.
- **A missing Unity reader no longer looks like "no text".** `extract_unity_typetree` swallowed the import error; the run ended EMPTY with 0 errors. It now fails the step with a message.
- **Large Ren'Py extract is ~40 % faster** with an identical `translation.csv` (SHA-256 compared before/after): per-unit re-decoding of archived scripts and a quadratic label search are gone; the canonical-JSON helper no longer uses the slow `typing` alias.
- **Image list names** show the image path (`gui/button/…`) instead of the percent-encoded archive reference.
- **CSV picked from another folder:** the translation and patch pages state where the file in use is, next to "Nơi lưu bản dịch".
- **Publisher:** the pre-build `release_verify` output is kept (`<scope>-release_verify.log`) and its tail is printed on failure; the Setup payload tool is in `release/` (`ResourceDump.cs`, `extract_setup_payload.py`).
- **Tests:** the single-process run of the whole Python suite had ~33 order-dependent failures. Cause: a test helper re-patched `cleanup.ROOT` after its workspace had restored it, so the deleted fixture folder stayed the module root for every later test.

## Checked on real games
Three real games through scan → extract → (image scan) → patch → install on a hard-link copy → uninstall → hash comparison, plus a running Ren'Py game and the app driven through its real file dialogs. See `AI_STATE.md` for the numbers and for what was not run.

## Published
Tag `v0.1.40` = `5d370f24549a65bde7762663e90ae4896b7ebc9c`; Setup sha256 `da2f4bffcb9092c35e8b8b83723c9d3dc9d74feec5ea12817775bf38e88236d5`; GitHub digests of the 5 assets equal the local files; update 0.1.39→0.1.40 read-back: 7341 files, 0 mismatches.
The `publish.ps1` fix for the preflight output (stdout only) is the commit right after the tag: the tagged source still has the `2>&1` variant that fails under Windows PowerShell 5.1 when Python writes a warning.
