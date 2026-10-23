# Release 0.1.10 — candidate and acceptance record

Status: exact-source candidate built from clean `main` commit `b9e2a661a58dd85979a6a10b9bb30f713107847b`. The required local release gates and candidate asset audit pass. Brain candidate review passed on 2026-10-24; publication is authorized after the action-time remote collision check. Nothing has been tagged or published yet. Public installed-update acceptance and terminal cleanup remain open. `RELEASE_VERIFIED` and whole-product release acceptance are not claimed.

## Scope and distribution

Owner authorized the complete 0.1.10 release workflow, including source commits, fast-forward push, stable tag/release, the verified public assets and actual public update acceptance. The separate 3 GiB task cap applies only to the registered `RELEASE_RUN/candidate-0.1.10` scope; `.dev-env` remains capped at 6 GiB and terminal non-exempt checkout usage must return to 1 GiB or less. No history or user-data deletion is authorized.

Publish the two full-app update routes and their support files only. Do not distribute the locally built `Setup.exe`; installer, uninstaller and system-permission behavior did not change. Preserve prior immutable releases and routes. The product model remains CT2/OPUS-MT. The native game visual test remains deferred to the installed updated app; that is pending evidence, not a visual pass.

## Candidate assets

The review-ready five-file set is `RELEASE_RUN/candidate-0.1.10/public-assets`:

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

The retained public 0.1.9 fixture is `RELEASE_RUN/candidate-0.1.10/b019`. After the original reconstructed baseline directory was removed by an overly broad cleanup scope, its replacement was reconstructed from the live public 0.1.7 Setup payload and verified 0.1.8 and 0.1.9 update packages. The inert 0.1.7 payload inventory matched 7,192 files and its recorded hash; both update applications passed their app/worker health probes. The resulting 0.1.9 app inventory matches the recorded 7,190-file/509,497,335-byte receipt, and its protected model snapshot hash matches both route receipts. Downloaded assets, live API digests, upstream SHA256SUMS, provenance and notices are retained in the evidence folder. The new 0.1.9 fixture must remain until public acceptance completes.

The initial route cleanup was scoped too broadly and returned `REVIEW_REQUIRED`; a later candidate cleanup reported timeout while the deletion provenance shows the old 1,045,747,271-byte baseline-assets root was removed. The exact parent deletion record is preserved. All 32,588 registered descendant records were reconciled to `MISSING` with that parent deletion proof and the replacement fixture receipt. The old reports remain unchanged. The active registry now has zero `UNKNOWN` entries, and the candidate audit is within the 3 GiB task cap with `.dev-env` within 6 GiB. Return to the default 1 GiB checkout cap only after public acceptance and task-scoped terminal cleanup.

## Remaining sequence

1. Immediately before publication, read back current remote `main`, the `v0.1.10` tag and release state. Push only the authorized fast-forward source. The `v0.1.10` tag must target the exact built source `b9e2a661a58dd85979a6a10b9bb30f713107847b`; any docs-only descendant remains outside that tag. Publish the stable release with exactly the five audited assets, then read back the public tag/source and every asset digest and size.
2. On a separate registered owned copy of the retained 0.1.9 fixture, perform the actual public 0.1.9 offer, download, apply, health, restart and data/model checks using supported UI/API. Preserve the original fixture and marker. Do not use a user installation or game data.
3. Record public acceptance and cleanup separately. Dispose only exact registered candidate/test artifacts after processes exit, preserve the compact receipts and return non-exempt usage to at most 1 GiB. Keep `.dev-env` at or below 6 GiB.
