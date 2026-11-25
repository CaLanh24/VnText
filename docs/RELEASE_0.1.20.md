# Release 0.1.20 — published

Published **2026-11-18**, Latest: https://github.com/CaLanh24/VnText/releases/tag/v0.1.20 . Owner authorized review/fixes/publication/cleanup. Root was the temporary sole writer while fixed Claude DEV was quota-blocked at cursor1940; no second writer/session was created.

## Source and payload

- Annotated tag `v0.1.20` points to exact clean build source `fb2e4e394cda5936ad0822097f0dbe35c309ee17`, source tree `8ed4fb0c233e6cbe0cbfeac845eec932c36135a71b12d12486a2b9f9aa63ff95`.
- Setup `VNTextStudio-0.1.20-Setup.exe`: 286,768,128 bytes; SHA256 `384dc46178ba51fa5a0be8fa274d40ff1e550157fc673ccb21fa78b219b6ec8f`. App EXE SHA256 `a646cdb55ba5c8524fdc01372f9e316ba574712dc4d207811d6a6edb8c142ec0`.
- Five public assets only: Setup, direct019->020 ZIP/feed and legacy 007->020 ZIP/feed. All five were streamed back from public URLs and matched size/SHA256; Latest independently returned `v0.1.20`. Exact names/hashes: `assets.json`, `public-readback.json`.
- Later commits `9b88179`/`60b097b` repair tests only; no product/payload changes or rebuild. This ledger commit is documentation only and does not change tag identity.

## Verification

Evidence base: `TEST_RUN/agent-evidence/release-0.1.20/`. Final decision: `final-release-receipt.json`; prepublication scope: `root-prepublication-accept.json`.

- Regression: all189 test modules accounted for, **182 module-level PASS gates plus 7 explicit case-level compositions** (`regression-composition.json`). Reused gates retain original tested SHA, unaffected prerequisites and explicit skips; failed attempts remain FAIL, not rewritten. The seven composed modules combine unchanged passing cases with targeted repaired-case receipts. Changes: stale completion/review expectations aligned with Owner's existing product contract; Qt output fixture separated from source; runner fixture dependency included; mock protected-fragment responses fixed; Setup harness emits UTF8 and honors selected release Python; native worker integration allows bounded600s DEV quota/epoch validation. No validators or data guards were weakened. Final targeted runtime cases PASS (`fixture-runtime-recheck.json`).
- Build/package: isolated publisher finalC PASS at `fb2e4e3`; verified7328 payload files/589292393 bytes, two working-directory worker smokes, extract/translate/single-installer patch and cancellation/crash checks. Earlier attempts failed missing model environment and immutable-model guard against nine zero-byte download-cache artifacts; final build used the verified clean public 019 model, all24 model files byte-identical. No shared model changes.
- Packaged updater CLI: direct019 and legacy 007 routes both apply/health/readback7327 files with 0mismatch. Tampered ZIP/baseline drift fail closed; interrupted update recovers; forced health failure rolls back. Canary/model hashes unchanged. These backend cases used verified extracted public payloads, not Setup installations (`updater020-{A,B,N1,N2,N3,N4}.json`).
- Native agent-desktop: fresh020 Setup, actual pinned SDK download/resources ready, app About020, branded Setup/Uninstall and uninstall-empty outcome. Real public 019 Setup installed into owned fixture,020 Setup upgraded it with 3209 data files byte-preserved (`native-upgrade-result.json`).
- Public native acceptance: another real019 Setup install received GitHub020 offer/date/notes, downloaded and verified the package, enabled Restart, restarted into020 and displayed success. Health true,7327 manifest files match,3211 data files unchanged. Manual About update check remained latest020 with no re-offer (`native-public-readback.json`, `native-public-success.png`, `native-manual-check.png`). About body lacked usable UIA nodes after bounded observation, so agent-desktop fresh-screen physical click was used; text-wait timeout is retained, visual outcome verified.

No real game run (Owner excluded it), broad semantic MT-quality certification, every DPI/theme/modal combination or animation timing is claimed. Prior scoped UI QA remains separately bounded.

## Publication, data and cleanup

Main pushed fast-forward through `60b097b`, exact-source annotated tag pushed, five assets uploaded in draft then published. Existing configured Git Credential Manager authorization was used in memory; no credential was printed/stored and no new Owner login was needed.

Temporary measured 5GiB release profile used under standing 2026-10-24 authority; shared 11GiB/guard48MiB unchanged. Forward epochs038->042 only, no rebaseline/extra-hop grant. All owned processes exited normally. Canonical cleanup disposed candidate/worktree and 150 test roots, then two regenerated DEV publisher intermediates. Worktree metadata pruned. Lossless canonical registry-history compaction saved235128055 bytes, preserving48521 records and logical snapshot hashes/epoch metadata. Final non-exempt910940180 bytes (<1GiB); temporary profile closed; shared 3308934109 bytes unchanged. Receipts: `terminal-owned-cleanup.json`, `intermediates-final-cleanup.json`, `history-compaction-receipt.json`.

Owner CSV SHA256 remains `8e5d0e849a504b3e8354f676037e2c1ee55aaf5d2635cccb1e9a95a73a1bb0ef`; native CSV fixture remains `02a6408b88789aea07114184907935bd8617369c072a79364cd153dda14e4b39`. Owner installation/data/preferences untouched. Blocked u16/r17b/App obj roots preserved. Historical failed cleanup attempts retain their verdicts; final owned cleanup is a separate PASS.
