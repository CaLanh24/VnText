# 0.1.17 — whole-game acceptance and scoped UI repairs

Status: source preparation, NOT built, NOT released, whole-game acceptance NOT PROVEN.

Owner 2026-11-05 requested verification on the previously named original game and fixes in 0.1.17. Accepting rough offline Vietnamese did not waive whole-game E2E. Keep public 0.1.16/tag/assets unchanged until compatibility of any asset pruning is proved. No cloud, paid service, model change or full-game copy.

## Corpus evidence

Private evidence: `C:/vnrg/evidence/p2p3-summary.json`, `C:/vnrg/corpus017/README.txt`, `aligned_corpus.csv`, `t1_traces.json`.

- Independent archive scan: 25 game scripts plus 48 translation scripts; 227 dialogue statements matched, one linear start label, no choice branches found. 310 MAIN rows, 8 non-main review-screen rows, 6 technical rows: 324 unique game-owned units. The six blocked dialogue rows also present in review are duplicates, not six additional source units.
- 291 engine-common strings remain excluded from patch; 230 are potentially player-visible. This is an OPEN coverage gap, not whole-game PASS. Ten runtime expressions remain unresolved. No promotion or validator waiver is authorized.
- Exact public 0.1.16 worker sources/model were verified against its payload. Whole-corpus output found app-induced clause loss, six blank translations, an English paragraph falsely classified Vietnamese because of a foreign name accent, and a visible achievement label classified as an ID prefix.
- OCR covered 330/330 archive images plus two loose webp images; positive control passed. No readable English text found; stylized/non-Latin OCR remains a limitation.
- Candidate flags are not all defects: date-format carriers must remain exact; borrowed words and punctuation changes do not prove semantic loss. Single-row versus batched numerical differences do not by themselves prove app causality.

## Prepared changes

- Keep inferred names in sentence context rather than cutting their surrounding prose into fragments. Explicit user glossary/memory and structural safeguards remain authoritative. This prevents app-induced fragmentation; it does not guarantee the model spells every inferred name correctly.
- Sentence-by-sentence retry also applies to the quality-retry batch. Prefer validated complete sentence candidates over shorter fragments. A malformed batch response retries each source sentence without dropping rows.
- Recognize actual Vietnamese marks/syllables instead of treating every foreign combining mark as Vietnamese. Detection normalizes only a probe, never user/source bytes.
- Preserve anchored compound name spellings in residue detection; bounded generic vocabulary and UI catalog additions address the observed ordinary-word and achievement-label cases. New postprocess/cache identity; no old cache deletion or user-edit overwrite.
- About current-version banner: restrained left-aligned green surface with localized version; keep other status semantics. Journal text surface follows the active Light/Dark palette.
- Release notes/update dialog centers using the actual owner HWND frame (Window.Left/Top can be restore coordinates while maximized), including height changes during download.
- License/EULA/uninstall surfaces reuse Setup typography, header/body/footer spacing and app icon; explicit consent and safe uninstall default remain. No uninstall-data behavior change.
- Published installer filename becomes `VNTextStudio-0.1.17-Setup.exe`; Setup and Uninstall embed the app icon. Publisher layout/transaction checks use the exact versioned name.
- Remove only the redundant “Hủy rồi thoát” button. “Hủy tác vụ” and titlebar-close confirmation/terminal guards remain.

## Validation boundaries and next steps

Direct focused tests and private corpus probes are development evidence, NOT canonical wrappers, packaged/native PASS or whole-game acceptance. Initial direct retry experiments included failures/regressions; the sentinel-name experiment was rejected because OPUS mutated markers. Retain the compact probes, not a false PASS.

Latest preparation evidence: `C:/vnrg/evidence/prepare017-focused.json` records 94 direct focused tests (20 real-game fixes, 32 strategies, 13 Vietnamese homographs, 29 classifier), all child exits 0. Python AST, XAML XML and PowerShell parsing pass; this is not compilation. `draft017c_result.json` records a fresh private 310-row run: 310 nonblank, 0 blocked/pending, source CSV unchanged, 29 outputs differ from public 0.1.16. Five identities are format/symbol/borrowed-word cases; the foreign-name paragraph now translates. This probe precedes the classifier policy-version metadata bump and is not a packaged/whole-game quality verdict. Linguistic review and full extraction/runtime coverage remain open.

Remaining: complete paired linguistic review; fresh product extract/translate/patch with exact candidate provenance; resolve coverage gaps honestly; native game display/playback with a safe windowed/render strategy; exact file-and-directory restoration; scoped UI/Setup/uninstall tests; supported updater routes and public asset simplification proof. Do not launch the original game without the recorded per-file cache/save backups and before/after inventory. `PYTHONDONTWRITEBYTECODE` alone does not prevent Ren'Py cache/save writes.

## Budget / epoch

New account `release-0.1.17` is prepared under the standing measured-allocation rule: same 6.25 GiB combined project/owned-external cap, shared cache 11 GiB, no increase. Existing project about 4.36 GB includes 3.13 GB protected history; sequential candidate/build route estimated about 2.2 GB above a cleaned base. Measure completely before allocating. No artifact becomes exempt by moving it outside the checkout.

The old active epoch ends at hop 8/8 and is bound to de44d43, whereas HEAD advanced through release documentation. The new account is not a one-use rebaseline grant. A new explicit Owner no-delete metadata rebaseline authority is still required before canonical gates/build/registered allocation. Preserve CAS, rollback, prior history and the ordinary eight-hop bound. No grant has been invented or consumed. Cleanup history remains REVIEW_REQUIRED separately from scoped cleanup.

Future distribution target: Setup plus previous-supported and immutable legacy updater routes; reuse older releases for compatible intermediate hops only after testing the actual client planner. Do not delete existing public routes merely to make the asset list shorter.
