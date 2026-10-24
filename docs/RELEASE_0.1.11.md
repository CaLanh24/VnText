# VNText Studio 0.1.11 — acceptance record

**Disposition: PUBLISHED — bounded acceptance.** Release `v0.1.11` is public and latest at `https://github.com/CaLanh24/VnText/releases/tag/v0.1.11`; tag peels to source SHA `6bcfde4c6d8dd596832270968e0875a2abdc8bea`. Fresh Setup and the public GitHub 0.1.10-to-0.1.11 offer/download/apply/restart passed with full target-inventory, model and data-sentinel readback. Native UX results remain bounded as stated below; this is not a claim of whole-product acceptance.

## Fresh Setup and final asset update — 2026-10-24

Owner-authorized Intel terms acceptance was completed for Setup SHA-256 `150db5ea40c34345952dd57d3b4dc76b3fd53812786893b1faf22f588bf8fb24`. The exact Setup installed into disposable `C:\b\RELEASE_RUN\candidate-0.1.11\i11`. Installed inventory matched all 7,193 payload files / 514,637,662 bytes; missing, mismatched and unexpected files were all zero. The installed worker smoke and release verifier both returned `ok: true`. Receipts: `C:\b\DEV_RUN\release-0.1.11\setup-acceptance\installed-inventory.json`, `installed-worker-smoke.json`, and `installed-release-verify.json`. The verifier reports `TRACE_NOT_ENABLED`; it proves the isolated headless workflow only. Bundled model manifest is `app/MODEL_MANIFEST.json`; 24 model files total 77,490,500 bytes, revision `c22547827b876e8ee939d6a9363965e5c9f769e1`, Apache-2.0.

Two final Vietnamese-notes updater packages were generated from the installed 0.1.11 candidate against clean 0.1.7 and 0.1.10 baselines. Both feeds and embedded manifests match package hashes, source SHA `6bcfde4c6d8dd596832270968e0875a2abdc8bea`, and source-tree SHA-256 `dd75b1cf217e3707601a2474367d4075e0b8001b964a4e23a07df9b5eb8c2f0b`; each contains 7,192 inventory entries and 24 model entries. The final notes omit the unverified manual-approval claim.

| Route | Final ZIP SHA-256 |
|---|---|
| General | `9714fa0cb7d8e2552c8e794adac11af9544791554aaef7683342e2d4e33b1ff1` |
| 0.1.10 baseline | `912f0e51ef7991fb817fba9fe116153316915cad9ac6cbc2e94e110d533bbaa0` |

Brain accepted the candidate. Final staging and public download receipts are retained under `C:\Users\VNTextDev\Downloads\VNText-0.1.11-final-assets-review-6bcfde4` and `C:\Users\VNTextDev\Downloads\VNText-0.1.11-public-readback-20261024`. Release assets include Setup, both updater ZIPs and feeds, Apache and third-party notices, provenance, and checksums. Since release assets are immutable, `THIRD_PARTY_NOTICES.md` and the revised provenance/checksum were added as revision 2 assets. Public acceptance receipt: `PUBLIC_RELEASE_ACCEPTANCE.json` in the public-readback folder.

## Post-publication public updater acceptance and cleanup — 2026-10-24

The real 0.1.10 app found the published 0.1.11 offer, downloaded the public route package, verified it, applied it and restarted. The success dialog and normal 0.1.11 UI appeared. Readback verified all 7,192 target manifest files, all 24 protected model hashes, the 0.1.11 source SHA, the downloaded package SHA, and the synthetic user-data sentinel. Before/after receipts are `C:\Users\VNTextDev\Downloads\VNText-0.1.11-public-readback-20261024\public-update-before.json` and `public-update-after.json`; the public acceptance index is `PUBLIC_RELEASE_ACCEPTANCE.json` beside them.

The test used the registered 0.1.10 baseline. Its payload was restored from the official 0.1.10 Setup archive and verified against all 7,193 archived payload entries, the old release metadata and executable hash. The test-only `.update`, `data`, sentinel and synthetic update-source file were removed with the artifact cleanup helper; the baseline is again 0.1.10. Registered disposable setup/staging/input trees were removed while both retained release baselines were preserved. Workspace non-exempt size remains about 1.45 GB, above the release task's 1 GiB terminal target; do not report terminal budget cleanup as PASS. Public release and update acceptance are complete independently of that storage target.

## Terminal cleanup reconciliation — 2026-10-24

Cleanup status is **REVIEW_REQUIRED** for the terminal storage target. The exact cleanup receipt is `C:\Users\VNTextDev\Downloads\VNText-0.1.11-public-readback-20261024\release-terminal-cleanup-20261024.json`. The complete project inventory measured 1,126,016,977 non-exempt bytes against 1,073,741,824 (1 GiB), an excess of 52,275,153 bytes. The candidate scope alone is 1,066,109,779 bytes. Shared `C:\v\.dev-env` is 6,354,244,836 bytes against the 6,442,450,944-byte (6 GiB) cap, leaving 88,206,108 bytes.

After removing the registered disposable baseline inputs, publisher scopes, Setup installation, test-only updater state, and local duplicate ZIP/feed folders, no remaining registered disposable child can be removed safely. A registered-only dry run completed its inventory and planned zero deletions; it blocked the disposable candidate root on the retained `release-baseline:baseline-0.1.7` record. The exact retained items are:

| Path | Bytes | Lifecycle | Why retained |
|---|---:|---|---|
| `C:\b\RELEASE_RUN\candidate-0.1.11\baseline-0.1.10` | 514,616,223 | RETAINED | Clean 0.1.10 updater baseline; restored and verified after public update acceptance |
| `C:\b\RELEASE_RUN\candidate-0.1.11\baseline-0.1.7` | 514,529,848 | RETAINED | Clean 0.1.7 updater baseline |

The following are the largest additional non-disposable paths; each is unregistered at its exact root, so I left it unchanged:

| Path | Bytes | Lifecycle | Why not eligible |
|---|---:|---|---|
| `C:\b\DEV_RUN\release-0.1.11` | 24,091,236 | UNREGISTERED | Setup/update acceptance receipts and release evidence |
| `C:\b\RELEASE_RUN\candidate-0.1.11\verify-source` | 19,854,438 | UNREGISTERED | Clean source checkout plus regression receipts and test registry history |
| `C:\b\RELEASE_RUN\candidate-0.1.11\source` | 16,913,540 | UNREGISTERED | Clean source checkout with an existing Git branch/history reference |

`C:\b\DEV_RUN\obj` is also unregistered (16,022,371 bytes), so it was not deleted based on its apparent build-cache role alone. Exact public-download duplicates and the 0.1.10 Setup extraction remain in Downloads: the cleanup helper rejected external Downloads paths at its repository write boundary, and no direct deletion fallback was used. Their hashes and the 0.1.10 payload-to-baseline comparison are recorded in `PUBLIC_ASSET_DUPLICATE_CLEANUP.json` and `RESTORE_SOURCE_CLEANUP.json` beside the public-readback receipts. Thus the release scope is fully inventoried and its current disposable paths are cleaned, but the repository-wide 1 GiB terminal target remains unmet without changing retained evidence/history or the cleanup authorization boundary.

The earlier pending Setup, unpublished release, unexercised public update, and unintegrated package paragraphs below are historical snapshots superseded by this section and the current-state summary at the top. Native UX scope and its PARTIAL/NOT_VERIFIED limits remain unchanged.


## Source and regression

- Source SHA: `6bcfde4c6d8dd596832270968e0875a2abdc8bea` (`Fix Windows regression temp path handling`).
- Post-build full regression on that exact SHA: **PASS**, 1,066 tests, 0 failures/errors, 7 skips, 223.398 seconds; wrapper exit 0 and scoped cleanup PASS. The docs-only commit that adds this report does not change or upgrade that tested SHA.
- Three explicit native OCR/model skips: `test_actual_extraction_automatically_creates_paired_images`, `test_real_windows_ocr_and_ct2`, and `test_real_worker_image_retry_protocol_twice` (`explicit native OCR/model gate`).
- Four external Unity fixture skips: `test_external_fixture_is_not_the_e2e_copy`, `test_full_workflow_game_copy`, `test_patch_without_translations_fails`, and `test_workflow_second_run` (fixture not configured; the log names `VNTEXT_GAME_FOLDER` and `VNTEXT_GAME_COPY_ASSET`).

## Publisher and Setup

Publisher payload verification, release verification, WPF worker smoke and candidate quota checks passed. Setup contains 7,193 payload files / 514,637,662 bytes; SHA-256 is `150db5ea40c34345952dd57d3b4dc76b3fd53812786893b1faf22f588bf8fb24`. Read-only inspection of this retained binary’s embedded `Payload.zip` confirms `app/worker/vntext/tools/VNTextPatchInstaller.exe`, 195,730 bytes, SHA-256 `e6e87d14e882a419dca007e86c69fa83b842c99c880a0199478972dd8aa98630`, matching the payload manifest and archive entry. The candidate root measured 2,604,425,292 bytes (2.426 GiB), within the 3 GiB limit.

The native Setup window is still open at **Intel oneAPI Redistributable Terms**. No terms were accepted and no fresh Setup installation or post-install worker acceptance was performed. This is an Owner action boundary, not a Setup failure verdict. Release 0.1.11 remains **NOT PUBLISHED**.

## Production updater integration

The starting 0.1.10 payload was reconstructed from the public payload and registered as disposable; it was **not installed by Setup**. Its 7,192-file inventory matched the named 0.1.10 route package baseline. It contained 24 model files (77,490,500 bytes) and a separate data sentinel.

- **Rollback and startup recovery PASS:** a supported fault injection interrupted replacement; launching the partially updated app invoked production recovery. The 0.1.10 executable/version and inventory were restored, all 24 model hashes and the data sentinel were unchanged, and pending journal/backup/staging were removed.
- **Successful update PASS:** the production full-app apply helper used the exact staged route package and package hash. Health passed; the app exited, the updater completed, and VNText Studio restarted at 0.1.11. All 7,192 target files, executable/release metadata/source SHA, 24 models and the data sentinel matched expected values.
- The in-app public GitHub offer/download flow was not exercised; the package was staged locally for the production apply path. The success modal showed the Vietnamese fallback because this test did not persist `DownloadedUpdateNotes`. The asynchronous handoff did not capture the successful helper's exit code; log, receipt, health and restarted UI were observed.

## Eight UX groups: automated checks and native acceptance

The exact-SHA regression and WPF test harness cover implementation behavior at varying levels. They do not establish native visual acceptance for each group. Two bounded native runs on 2026-10-24 used the prebuilt 0.1.11 app at `C:\b\RELEASE_RUN\candidate-0.1.11\pub-r011d\wpf_publish\VNText.Studio.App.exe` (SHA-256 `405B218F6C6A93EEE09E970EDF2420FD0B3FA2059916D0BEE164DFDB028AA60E`), the existing local model, and supported `@oai/sky` native capture. Run 1 used scope `TEST_RUN\ux-0.1.11-native-20261024`; its first Analyze unexpectedly wrote `unity_analysis.json` under the default Documents output. That exact file was retained at `DEV_RUN\ux-0.1.11-native-20261024-evidence\unity_analysis.synthetic-renpy.json` and removed from Documents before further output-producing actions; the app output was then set to the scoped `work\output`. Run 2 used the correctly registered disposable scope `TEST_RUN\ux-0.1.11-native-20261024b` with a pre-fixture snapshot and the production smoke-fixture pattern (`NPC: Hello there`). The app-generated `manifest.json` and blank `translation.csv` matched on key `963715c609e48d84`, source `NPC: Hello there`, and `plain_text_line`; offline local translation completed, the native CSV editor saved a context edit, and strict Patch preflight/read-back completed. Run 2 receipts and SHA-256 inventory are retained at `DEV_RUN\ux-0.1.11-native-20261024-evidence\run2\`; its exact scoped cleanup returned PASS (1 deleted, 1 expected missing, 0 unexpected missing, complete inventory). Those two workflow runs did not retain screenshots. A separate registered, screenshot-only native scope captured light/dark settings, the enabled blue switch, blank-translation readiness, and the loaded CSV editor at `DEV_RUN/release-0.1.11/candidate-review-d5cee2a/screenshots/`. No missing-SDK dialog image was obtained in this follow-up. The exact scope cleanup returned PASS. These screenshots supplement the earlier observations; they do not complete all eight UX groups or establish Setup installation, release, publication, or installed-runtime acceptance.

| UX group | Automated evidence | Native visual/interaction status |
|---|---|---|
| Completion notifications use the app theme | `test_completion_notifications_use_the_app_theme_surface`; `CompletionNotification_ExactlyOncePerOutcome` | **PASS** — native local translation and Patch completion notices were visible on the light app surface |
| Enabled preference switches use the blue track | WPF `PreferencesTests` inspects the real `MainWindow` binding and switch track | **PASS** — native Remember Window switch showed blue when enabled, gray when disabled, and restored true; Start Minimized was visibly toggled on and back off |
| Recovery options appear for Ren’Py when SDK evidence is missing | `RenpySdkOptionsVisibility_FollowsSelectedGame`; `RenpySdkRecovery_StatusRequiresSuccessfulEvidence`; `RenpySdkMissing_ReportsPartialExtraction` | **PASS (UI) / PARTIAL (workflow)** — native missing-SDK prompt showed download, choose-installed-tool, and continue actions; continuing yielded an incomplete extraction with 0 dialogue rows because no Ren’Py tool was used |
| Engine recognition is clearer | `RenpyGameDetector_RequiresCredibleRecoveryEvidence` and analysis presentation checks | **PASS (label/analysis only)** — native UI identified Ren’Py and reported analysis complete with no scan errors; this did not verify extraction or write-back |
| Deep scan is absent from the default text extraction chooser | XAML selector is collapsed; `ExtractLevel_Persists` checks saved level behavior | **PASS** — native default extraction options showed “separate lines for review” and no Deep Scan option |
| Estimated time is easier to read | `WorkerEvent_FormatsNumericEta` | **PARTIAL** — Patch progress showed `Còn khoảng 0 giây` at 50%; 0%, 25%, and 99% still showed an estimating placeholder. The task completed in about a second, so ETA accuracy was not established |
| Blank translation CSV directs users to local translation and readiness/start action | `CsvValidator_RejectsEmptyTranslation` and related workflow/readiness checks | **PASS (bounded native path)** — app Extract created the matching one-row package with blank translation; the native local-translation page had an enabled start action, which ran CT2 and completed. The earlier mismatched-manifest attempt remains excluded |
| CSV editor layout and find/replace controls | `CsvEditor_SearchFiltersRows`; WPF workflow/layout checks | **PARTIAL** — Run 1 search filtered to `k2`, clearing restored both rows, and find/replace expanded/collapsed. Run 2 loaded the generated valid row, accepted a native translation edit, and saved it with the UTF-8 BOM while retaining columns. Bulk find/replace was not executed |

For Run 2, native Patch preflight reported valid 1/1 and blocked 0; `patch_verification.json` records PASS for the exact-line read-back. The output copy contained `NPC: Xin chào, bạn ơi!`; its `backup_original/sample.txt` hash matched the original fixture. The loose `wpf_publish` app used `C:\v` as its worker root, so its native missing-installer notice reflects that fixture’s lookup location. The retained Setup payload independently contains the installer at the worker lookup path with SHA-256 `e6e87d14e882a419dca007e86c69fa83b842c99c880a0199478972dd8aa98630`. In the exact-source full regression log, both `tests/unit/test_patch_installer.py` tests passed (`test_install_uninstall_restores_exact_hash` and `test_manifest_and_installer_accept_generic_unity_data_name`). Installed Setup discovery/runtime remains NOT VERIFIED because Setup terms are still awaiting Owner approval; no fresh install was performed. The incomplete Ren’Py extraction is not a PASS for extraction completeness. Fresh-install behavior, public update metadata/download, and the release notes flow also remain unverified.

## Vietnamese update packages

Two immutable packages were generated by `publish_full_app_update.py` outside the publisher output. Hash/feed/embedded manifests, provenance, target inventory (7,192 files), protected model inventory (24 files), and archive integrity passed review. The existing publisher ZIP hashes were unchanged. These packages have **not** been integrated or uploaded.

| Route | Package | SHA-256 | Size |
|---|---|---|---:|
| General feed | `full-app-update-0.1.11-dfcc80735b5015f7.zip` | `dfcc80735b5015f726d0538d8be4f1e2d0d10a882e3b13ae377ce5bd4e06c2ea` | 6,130,013 bytes |
| 0.1.10 baseline | `full-app-update-from-0.1.10-to-0.1.11-316d8438d82fbe59.zip` | `316d8438d82fbe59e0bdca654e5c68ba48db1f41775e0f1f858c6174b6d5e5c3` | 6,017,500 bytes |

Package provenance: source SHA `6bcfde4c6d8dd596832270968e0875a2abdc8bea`; source tree SHA-256 `dd75b1cf217e3707601a2474367d4075e0b8001b964a4e23a07df9b5eb8c2f0b`.

The short embedded Vietnamese notes include “hoàn thiện luồng duyệt thủ công”. Keep the ZIPs immutable and obtain Brain's accuracy review before integration; no third repack is prepared. The fuller customer-facing Vietnamese draft below avoids that claim.

## Cleanup and registry state

The disposable updater test payload (531,160,567 bytes) was deleted. The final scoped cleanup receipt is PASS: one expected missing disposable artifact, zero unexpected missing, and complete inventory.

The first registration/cleanup invocation omitted its saved `--before` snapshot and created **98 active UNKNOWN records** in the disposable checkout's `TEST_RUN\artifacts_manifest.json`. The pre-run `SCOPE_BEFORE.json` contains all 98 paths, and the separate assessment confirms 98/98 pre-existed. Based on that proof, exactly those 98 directory records were assigned RETAINED entry-by-entry; ACTIVE status and all filesystem paths were preserved, with no purpose inferred. Before/after manifest hashes and exact IDs/paths are in `DEV_RUN/release-0.1.11/candidate-review-d5cee2a/REGISTRY_REMEDIATION.json`; the original manifest, snapshot, assessment and dry-run review are retained beside it. No broad reset or migration was applied.

## Draft GitHub Release body (Vietnamese)

### Cải thiện thao tác

- Thông báo kết quả dùng giao diện đồng bộ với ứng dụng; các công tắc hiển thị rõ trạng thái bật bằng màu xanh dương.
- Làm rõ nhận diện game Ren’Py và các lựa chọn khôi phục khi thiếu SDK.
- Mặc định lấy text bằng chế độ quét sâu; lựa chọn mức lọc được ẩn khỏi màn hình thông thường.
- Cách hiển thị thời gian ước tính dễ đọc hơn.
- Khi CSV chưa có bản dịch, ứng dụng hướng dẫn chuyển sang Dịch local, hiển thị trạng thái sẵn sàng và nút bắt đầu phù hợp.
- Sắp xếp lại vùng tìm và thay thế trong Sửa CSV để các trường và thao tác rõ ràng hơn.

# VNText Studio 0.1.11

## Cải thiện thao tác

- Thông báo kết quả dùng giao diện đồng bộ với ứng dụng; công tắc bật hiển thị màu xanh dương.
- Làm rõ nhận diện game Ren’Py và các lựa chọn khôi phục khi thiếu SDK.
- Lấy text sử dụng quét sâu theo mặc định; tùy chọn mức quét được ẩn khỏi màn hình thông thường.
- Cách hiển thị thời gian ước tính dễ đọc hơn.
- Khi CSV chưa có bản dịch, ứng dụng hướng dẫn chuyển sang Dịch local, hiển thị trạng thái sẵn sàng và nút bắt đầu phù hợp.
- Sắp xếp lại vùng tìm và thay thế trong Sửa CSV để các trường và thao tác rõ ràng hơn.
