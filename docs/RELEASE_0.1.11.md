# VNText Studio 0.1.11 — acceptance record

**Disposition: MORE EVIDENCE REQUIRED.** The local technical gates below are recorded at their actual source SHA. Brain review, native acceptance of the eight UX groups, fresh Setup acceptance, and resolution of the updater test registry records remain open. No public release or asset upload has occurred.

## Source and regression

- Source SHA: `6bcfde4c6d8dd596832270968e0875a2abdc8bea` (`Fix Windows regression temp path handling`).
- Post-build full regression on that exact SHA: **PASS**, 1,066 tests, 0 failures/errors, 7 skips, 223.398 seconds; wrapper exit 0 and scoped cleanup PASS. The docs-only commit that adds this report does not change or upgrade that tested SHA.
- Three explicit native OCR/model skips: `test_actual_extraction_automatically_creates_paired_images`, `test_real_windows_ocr_and_ct2`, and `test_real_worker_image_retry_protocol_twice` (`explicit native OCR/model gate`).
- Four external Unity fixture skips: `test_external_fixture_is_not_the_e2e_copy`, `test_full_workflow_game_copy`, `test_patch_without_translations_fails`, and `test_workflow_second_run` (fixture not configured; the log names `VNTEXT_GAME_FOLDER` and `VNTEXT_GAME_COPY_ASSET`).

## Publisher and Setup

Publisher payload verification, release verification, WPF worker smoke and candidate quota checks passed. Setup contains 7,193 payload files / 514,637,662 bytes; SHA-256 is `150db5ea40c34345952dd57d3b4dc76b3fd53812786893b1faf22f588bf8fb24`. The candidate root measured 2,604,425,292 bytes (2.426 GiB), within the 3 GiB limit.

The native Setup window is still open at **Intel oneAPI Redistributable Terms**. No terms were accepted and no fresh Setup installation or post-install worker acceptance was performed. This is an Owner action boundary, not a Setup failure verdict. Release 0.1.11 remains **NOT PUBLISHED**.

## Production updater integration

The starting 0.1.10 payload was reconstructed from the public payload and registered as disposable; it was **not installed by Setup**. Its 7,192-file inventory matched the named 0.1.10 route package baseline. It contained 24 model files (77,490,500 bytes) and a separate data sentinel.

- **Rollback and startup recovery PASS:** a supported fault injection interrupted replacement; launching the partially updated app invoked production recovery. The 0.1.10 executable/version and inventory were restored, all 24 model hashes and the data sentinel were unchanged, and pending journal/backup/staging were removed.
- **Successful update PASS:** the production full-app apply helper used the exact staged route package and package hash. Health passed; the app exited, the updater completed, and VNText Studio restarted at 0.1.11. All 7,192 target files, executable/release metadata/source SHA, 24 models and the data sentinel matched expected values.
- The in-app public GitHub offer/download flow was not exercised; the package was staged locally for the production apply path. The success modal showed the Vietnamese fallback because this test did not persist `DownloadedUpdateNotes`. The asynchronous handoff did not capture the successful helper's exit code; log, receipt, health and restarted UI were observed.

## Eight UX groups: automated checks and native acceptance

The exact-SHA regression and WPF test harness cover implementation behavior at varying levels. They do not establish native visual acceptance for each group. In the live 0.1.11 app, the only observed UI states were the main window after restart and the Vietnamese “Cập nhật thành công” modal. No saved native screenshot receipt exists for the groups below.

| UX group | Automated evidence | Native visual/interaction status |
|---|---|---|
| Completion notifications use the app theme | `test_completion_notifications_use_the_app_theme_surface`; `CompletionNotification_ExactlyOncePerOutcome` | **NOT TESTED** in the release app |
| Enabled preference switches use the blue track | WPF `PreferencesTests` inspects the real `MainWindow` binding and switch track | **NOT TESTED** in the release app |
| Recovery options appear for Ren’Py when SDK evidence is missing | `RenpySdkOptionsVisibility_FollowsSelectedGame`; `RenpySdkRecovery_StatusRequiresSuccessfulEvidence`; `RenpySdkMissing_ReportsPartialExtraction` | **NOT TESTED** with a native Ren’Py game flow |
| Engine recognition is clearer | `RenpyGameDetector_RequiresCredibleRecoveryEvidence` and analysis presentation checks | **NOT TESTED** with a real game in the release app |
| Deep scan is absent from the default text extraction chooser | XAML selector is collapsed; `ExtractLevel_Persists` checks saved level behavior | **NOT TESTED** by native screenshot/interaction |
| Estimated time is easier to read | `WorkerEvent_FormatsNumericEta` | **NOT TESTED** during a live work task |
| Blank translation CSV directs users to local translation and readiness/start action | `CsvValidator_RejectsEmptyTranslation` and related workflow/readiness checks | **NOT TESTED** with a real CSV in the release app |
| CSV editor layout and find/replace controls | `CsvEditor_SearchFiltersRows`; WPF workflow/layout checks | **NOT TESTED** with a real CSV in the release app |

The live restart/modal observation verifies that the updated app launched and rendered the success state. It does not verify the eight feature groups, fresh-install behavior, public update metadata/download, or the release notes flow.

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

The first registration/cleanup invocation omitted its saved `--before` snapshot and created **98 active UNKNOWN records** in the disposable checkout's `TEST_RUN\artifacts_manifest.json`. The pre-run `SCOPE_BEFORE.json` contains all 98 paths, and a separate assessment confirms 98/98 pre-existed. Keep the records UNKNOWN pending an approved per-entry registry remediation route. Do not reset/rebaseline, promote them to PASS, or apply a broad archive/migration. The final scoped cleanup PASS does not mean the entire test registry is terminal or free of UNKNOWN records. The shared `C:\v` registry was not changed.

## Draft GitHub Release body (Vietnamese)

### Cải thiện thao tác

- Thông báo kết quả dùng giao diện đồng bộ với ứng dụng; các công tắc hiển thị rõ trạng thái bật bằng màu xanh.
- Làm rõ nhận diện game Ren’Py và các lựa chọn khôi phục khi thiếu SDK.
- Đưa tùy chọn quét sâu khỏi màn hình lấy text mặc định để giao diện gọn hơn.
- Cách hiển thị thời gian ước tính dễ đọc hơn.
- Khi CSV chưa có bản dịch, ứng dụng hướng dẫn chuyển sang Dịch local, hiển thị trạng thái sẵn sàng và nút bắt đầu phù hợp.
- Sắp xếp lại vùng tìm và thay thế trong Sửa CSV để các trường và thao tác rõ ràng hơn.
