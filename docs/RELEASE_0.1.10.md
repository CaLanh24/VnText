# Release 0.1.10 — candidate and acceptance record

Status: stable release `v0.1.10` is published. Its annotated tag targets exact build commit `b9e2a661a58dd85979a6a10b9bb30f713107847b`; live API readback passed for exactly five approved assets and their sizes/digests. Brain candidate review and actual public installed-update acceptance from 0.1.9 passed. The registered payload cleanup and final quota measurement are complete; two cleanup reports remain `REVIEW_REQUIRED` for their quota/profile checks, with exact deletion independently recorded. `RELEASE_VERIFIED` and whole-product release acceptance are not claimed.

## Scope and distribution

Owner authorized the complete 0.1.10 release workflow, including source commits, fast-forward push, stable tag/release, the verified public assets and actual public update acceptance. The separate 3 GiB task cap applies only to the registered `RELEASE_RUN/candidate-0.1.10` scope; `.dev-env` remains capped at 6 GiB and terminal non-exempt checkout usage must return to 1 GiB or less. No history or user-data deletion is authorized.

Publish the two full-app update routes and their support files only. Do not distribute the locally built `Setup.exe`; installer, uninstaller and system-permission behavior did not change. Preserve prior immutable releases and routes. The product model remains CT2/OPUS-MT. The native game visual test remains deferred to the installed updated app; that is pending evidence, not a visual pass.

## Candidate assets

The published five-file set was `RELEASE_RUN/candidate-0.1.10/public-assets`:

| Asset | Bytes | SHA-256 |
| --- | ---: | --- |
| `full-app-update-0.1.10-bf16463459fa75f1.zip` | 3,563,875 | `bf16463459fa75f19cf095b3f6352b8f14e055027aa4856d42e102eeca514831` |
| `full-app-update-from-0.1.9-to-0.1.10-c71e94d2bcd74d56.zip` | 3,495,811 | `c71e94d2bcd74d561b7acce0739f33a880755999e684ea52fb10bb4ac587f949` |
| `BUILD-PROVENANCE.json` | 1,853 | `b7eff3dec46c9d13f98f13df2103d1813868116e561cdf27528a25be370f5e58` |
| `SHA256SUMS.txt` | 415 | `433a74e36817f3443baf21ae3ce21596d35c7e48c18db8870dd731f2547ed90f` |
| `THIRD_PARTY_NOTICES.md` | 21,080 | `00e6e9e6d5b9a1f5425f93e40feb874a582c57b8244d5b7a1e6a8676b5c51659` |

The standalone candidate audit is `RELEASE_RUN/candidate-0.1.10/evidence/candidate-review-audit.json`. Both archives pass CRC and manifest equality checks, contain only the declared add/replace operations, and carry the exact `b9e2a66` source and tree hashes. Each route preserves all 24 protected model files without including a model file in add, replace or delete operations. The notices hash matches the source snapshot and the reconstructed 0.1.9 payload. `SHA256SUMS.txt` covers every other public asset exactly.

## Validation evidence

On exact source SHA `b9e2a661a58dd85979a6a10b9bb30f713107847b`:

- Full regression: 1,058 tests, zero failures/errors, 10 explained skips; persisted cleanup PASS with no unknown, unexpected-missing, locked or error entries.
- Focused full-app publisher tests: 2 PASS. The canonical publisher and Release verification passed, as did WPF Release smoke from independent working directories.
- The exact embedded PatchInstaller binary matched the build output; its focused regression passed 2 tests. The real Release GUI close/reap test passed.
- The local 0.1.7→0.1.10 legacy route and 0.1.9→0.1.10 named route both passed app/worker health checks and preserved data and models. The 0.1.9 route's forced health failure restored the original app, data and model inventories before the successful application.
- The compact receipts retain exact commands, package hashes, source identity, test output and cleanup status. They are not promoted to a different source SHA by this documentation update.

The owned 0.1.9 fixture was `RELEASE_RUN/candidate-0.1.10/b019`. After the original reconstructed baseline directory was removed by an overly broad cleanup scope, its replacement was reconstructed from the live public 0.1.7 Setup payload and verified 0.1.8 and 0.1.9 update packages. The inert 0.1.7 payload inventory matched 7,192 files and its recorded hash; both update applications passed their app/worker health probes. The resulting 0.1.9 app inventory matched 7,190 files and 509,497,335 bytes, and its protected model snapshot hash matched both route receipts. The retained copy remained unchanged after acceptance.

## Publication and public update acceptance

GitHub release [VNText 0.1.10](https://github.com/CaLanh24/VnText/releases/tag/v0.1.10) is stable and contains exactly the five assets listed above. `public-release-readback.json` records the live API sizes and SHA-256 digests; the peeled remote tag resolves to the exact build SHA. No Setup asset is present.

`public-update-acceptance-019.json` records the actual public path on a separate registered copy of the retained fixture. The production `WpfUpdateService` queried GitHub and offered/downloaded the 0.1.9 route at the published URL and exact package digest. `GitHubUpdatePackageLease` handed the candidate to the configured isolated updater, which applied 0.1.10, passed its application/worker health check, and restarted the app. A fresh post-restart health check exited 0. The updated app inventory contains 7,191 files and 509,540,357 bytes, with source SHA `b9e2a661a58dd85979a6a10b9bb30f713107847b`. All 24 model files matched byte-for-byte. Every preexisting data file remained unchanged; app startup added only its settings and log files. The original retained fixture still reports 0.1.9. A preliminary handoff attempt timed out without changing the baseline while a modal update dialog blocked the close request; after dismissing the dialog through Windows UI Automation, the production update handoff passed. The failed attempt and its boundary are retained in the receipt.

The initial route cleanup was scoped too broadly and returned `REVIEW_REQUIRED`; a later candidate cleanup reported timeout while the deletion provenance shows the old 1,045,747,271-byte baseline-assets root was removed. The exact parent deletion record is preserved. All 32,588 registered descendant records were reconciled to `MISSING` with that parent deletion proof and the replacement fixture receipt. The old reports remain unchanged. After public acceptance, the separate disposable update copy, retained 0.1.9 fixture, and candidate build payload were removed through their registered cleanup scopes. The build payload cleanup passed. The fixture cleanup physically deleted 520,901,591 bytes with complete inventory and no locks, but its receipt is `REVIEW_REQUIRED` because the checkout was still above the default 1 GiB cap at that point. The test-copy cleanup likewise deleted the exact root, but its report is `REVIEW_REQUIRED` because its budget profile/source check failed. Neither report is relabeled as a cleanup PASS. The active registry has zero `UNKNOWN` entries.

## Terminal cleanup

Publication and public installed-update acceptance are complete. The final complete inventory measured 910,611,747 non-exempt bytes against the 1,073,741,824-byte default cap, and 6,353,209,503 `.dev-env` bytes against the 6,442,450,944-byte cap. `evidence/terminal-workspace-quota.json` preserves that receipt alongside each cleanup verdict. Visual acceptance remains explicitly deferred; this release does not claim whole-product `RELEASE_VERIFIED`.
