# VNText Studio 0.1.11 — acceptance record

**Disposition: MORE EVIDENCE REQUIRED.** The local technical gates below are recorded at their actual source SHA. Brain review, completion of native acceptance for the eight UX groups, and fresh Setup acceptance remain open. No public release or asset upload has occurred.

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
