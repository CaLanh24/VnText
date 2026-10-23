# Release 0.1.10 — candidate and acceptance record

Status: stable release `v0.1.10` remains on the annotated tag that targets exact build commit `b9e2a661a58dd85979a6a10b9bb30f713107847b`. Live API and downloaded-byte readback passed for the original five assets plus the 0.1.10 Setup and its separate provenance record. The earlier public installed-update acceptance from 0.1.9 passed. Fresh Setup installation and worker health acceptance is PROVEN_BLOCKED for this attempt: Setup displayed its Intel terms window, then supported UI state capture timed out twice before any input. No terms were accepted and installation did not start; this is a capture blocker, not a product install-failure verdict. This bounded Setup repair does not claim whole-product `RELEASE_VERIFIED`.

## Scope and distribution

Owner authorized this bounded Setup repair, source documentation push, and public Setup upload. The stable tag and existing update assets stay on their exact source and digest. The temporary 3 GiB task cap applies only to the registered `RELEASE_RUN/candidate-0.1.10` scope; `.dev-env` remains capped at 6 GiB and terminal non-exempt checkout usage must return to 1 GiB or less. No history or user-data deletion is authorized.

The repair adds the versioned Setup and a separate Setup provenance asset. The original update archives and support assets remain byte-for-byte unchanged. The product model remains CT2/OPUS-MT. Native game visual acceptance remains deferred to a supported installed-app capture; that is pending evidence, not a visual pass.

## Candidate assets

The original five-file set remains unchanged; the release now has seven assets. Live API and downloaded Setup readbacks are preserved in `DEV_RUN/release-0.1.10-repair/`:


| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `full-app-update-0.1.10-bf16463459fa75f1.zip` | 3,563,875 | `bf16463459fa75f19cf095b3f6352b8f14e055027aa4856d42e102eeca514831` |
| `full-app-update-from-0.1.9-to-0.1.10-c71e94d2bcd74d56.zip` | 3,495,811 | `c71e94d2bcd74d561b7acce0739f33a880755999e684ea52fb10bb4ac587f949` |
| `BUILD-PROVENANCE.json` | 1,853 | `b7eff3dec46c9d13f98f13df2103d1813868116e561cdf27528a25be370f5e58` |
| `SHA256SUMS.txt` | 415 | `433a74e36817f3443baf21ae3ce21596d35c7e48c18db8870dd731f2547ed90f` |
| `THIRD_PARTY_NOTICES.md` | 21,080 | `00e6e9e6d5b9a1f5425f93e40feb874a582c57b8244d5b7a1e6a8676b5c51659` |
| `VNTextStudio-0.1.10-Setup.exe` | 222,415,360 | `5233e604016c271efac7f8b000f3bf0a1123dfbf276f1730017cc07168d2ba10` |
| `SETUP-PROVENANCE-0.1.10.json` | 1,315 | `b66644c0793ededfee1440d7f9bbca435058ed67542d6878e3d3280f69760700` |

The standalone candidate audit is `DEV_RUN/release-0.1.10/evidence/candidate-review-audit.json`. Both archives pass CRC and manifest equality checks, contain only the declared add/replace operations, and carry the exact `b9e2a66` source and tree hashes. Each route preserves all 24 protected model files without including a model file in add, replace or delete operations. The notices hash matches the source snapshot and the reconstructed 0.1.9 payload. The original `SHA256SUMS.txt` is preserved unchanged; the separate Setup provenance asset records the Setup digest.

## Validation evidence

On exact source SHA `b9e2a661a58dd85979a6a10b9bb30f713107847b`:

- Full regression: 1,058 tests, zero failures/errors, 10 explained skips; persisted cleanup PASS with no unknown, unexpected-missing, locked or error entries.
- Focused full-app publisher tests: 2 PASS. The canonical publisher and Release verification passed, as did WPF Release smoke from independent working directories.
- The bounded 0.1.10 Setup publisher exited 0 on exact source SHA. It verified a 7,193-file/514,616,223-byte payload, passed Release verification and Release WPF smoke, and built both update routes locally from the reconstructed public 0.1.7 and 0.1.9 baselines. This did not replace or upload either existing update ZIP.
- The exact embedded PatchInstaller binary matched the build output; its focused regression passed 2 tests. The real Release GUI close/reap test passed.
- The local 0.1.7→0.1.10 legacy route and 0.1.9→0.1.10 named route both passed app/worker health checks and preserved data and models. The 0.1.9 route's forced health failure restored the original app, data and model inventories before the successful application.
- The compact receipts retain exact commands, package hashes, source identity, test output and cleanup status. They are not promoted to a different source SHA by this documentation update.

The owned 0.1.9 fixture was `RELEASE_RUN/candidate-0.1.10/b019`. After the original reconstructed baseline directory was removed by an overly broad cleanup scope, its replacement was reconstructed from the live public 0.1.7 Setup payload and verified 0.1.8 and 0.1.9 update packages. The inert 0.1.7 payload inventory matched 7,192 files and its recorded hash; both update applications passed their app/worker health probes. The resulting 0.1.9 app inventory matched 7,190 files and 509,497,335 bytes, and its protected model snapshot hash matched both route receipts. The retained copy remained unchanged after acceptance.

## Publication and public update acceptance

GitHub release [VNText 0.1.10](https://github.com/CaLanh24/VnText/releases/tag/v0.1.10) remains on the exact build tag and contains the seven assets listed above. Live API readback confirms every original asset digest stayed unchanged. A fresh download of the Setup matched its API SHA-256 digest and size. `SETUP-PROVENANCE-0.1.10.json` separates the new Setup receipt from the older `BUILD-PROVENANCE.json`.

`DEV_RUN/release-0.1.10/evidence/public-update-acceptance-019.json` records the actual public path on a separate registered copy of the retained fixture. The production `WpfUpdateService` queried GitHub and offered/downloaded the 0.1.9 route at the published URL and exact package digest. `GitHubUpdatePackageLease` handed the candidate to the configured isolated updater, which applied 0.1.10, passed its application/worker health check, and restarted the app. A fresh post-restart health check exited 0. The updated app inventory contains 7,191 files and 509,540,357 bytes, with source SHA `b9e2a661a58dd85979a6a10b9bb30f713107847b`. All 24 model files matched byte-for-byte. Every preexisting data file remained unchanged; app startup added only its settings and log files. The original fixture remained at 0.1.9 through acceptance and was then disposed. A preliminary handoff attempt timed out without changing the baseline while a modal update dialog blocked the close request; after dismissing the dialog through Windows UI Automation, the production update handoff passed. The failed attempt and its boundary are retained in the receipt.

The initial route cleanup was scoped too broadly and returned `REVIEW_REQUIRED`; a later candidate cleanup reported timeout while the deletion provenance shows the old 1,045,747,271-byte baseline-assets root was removed. The exact parent deletion record is preserved. All 32,588 registered descendant records were reconciled to `MISSING` with that parent deletion proof and the replacement fixture receipt. The old reports remain unchanged. After public acceptance, the separate disposable update copy, retained 0.1.9 fixture, candidate build payload, and both run roots were disposed. The build payload and final root cleanups passed. The fixture cleanup physically deleted 520,901,591 bytes with complete inventory and no locks, but its historical receipt remains `REVIEW_REQUIRED` because the checkout was still above the default 1 GiB cap at that point. The test-copy cleanup likewise deleted the exact root, but its report remains `REVIEW_REQUIRED` because its budget profile/source check failed. Neither report is relabeled as a cleanup PASS. The transferred final registry snapshot has zero `UNKNOWN` entries.


## Setup repair

The Setup asset was built from exact source SHA `b9e2a661a58dd85979a6a10b9bb30f713107847b` in a registered 0.1.10 candidate using the clean 24-file model input from the verified public baseline. The model revision is `c22547827b876e8ee939d6a9363965e5c9f769e1` under Apache-2.0. No shared model cache files or downloads were changed. The public Setup is 222,415,360 bytes with SHA-256 `5233e604016c271efac7f8b000f3bf0a1123dfbf276f1730017cc07168d2ba10`; its embedded payload contains 7,193 files and 514,616,223 bytes. `SETUP-PROVENANCE-0.1.10.json` is the companion receipt.

Publisher, Release verification, Release WPF smoke, both local full-app route builds, and the public Setup download readback passed. The Setup UI displayed the Intel terms window, but supported `sky.get_window_state` timed out twice before any interaction. No terms were accepted, the target stayed empty, and no installation or worker smoke ran. The exact attempt is recorded as `PROVEN_BLOCKED` in `DEV_RUN/release-0.1.10-repair/setup-install-ui-blocked.json`; this is a capture/tool blocker and not an installer failure verdict. The prior actual 0.1.9 public update acceptance remains separate evidence.
## Terminal cleanup

Publication and public installed-update acceptance are complete. `DEV_RUN/release-0.1.10/terminal-cleanup.json` records the final `TEST_RUN`/`RELEASE_RUN` absence and complete quota inventory. The exact epoch files, final registry and append-only cleanup history were copied byte-for-byte into `DEV_RUN/release-0.1.10/terminal-control-evidence`; the copy hashes and the canonical epoch verifier’s docs-only source-SHA mismatch are recorded separately. Native game visual acceptance remains explicitly deferred; this release does not claim whole-product `RELEASE_VERIFIED`.

