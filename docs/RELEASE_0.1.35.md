# Release 0.1.35 — one-button bug report to the developer, preview first

The Owner chose a private Discord channel as the bug-report route; Brain relayed the request and the instruction to release without further approval. This release falls under the Owner's standing permission (DEV session 2026-11-25): VNText patches are released when the mandatory gate passes, and public baselines are downloaded with hash checks. Task `release-0.1.35`, exact `RELEASE_RUN/candidate-0.1.35`, 8 GiB temporary allocation, 48 MiB reserve, shared 11 GiB, terminal 1 GiB.

## Scope
- **"Gửi báo lỗi"** sits on the Nhật ký page, next to "Tạo gói báo lỗi", only in builds that carry the channel. It builds the anonymous bundle and shows what the bundle holds, with the line "Gói đã ẩn danh sẽ được gửi tới nhà phát triển. Không có tên game/tệp/nội dung thoại/đường dẫn." The bundle is posted only after the person answers yes. Nothing is ever sent automatically. The send runs in its own process (`vntext.report_upload_cli`), so the UI never waits.
- **What is sent:** the zip plus a short message built only from the bundle's already-masked `report.json`. The message holds the app version, engine, status and severity, error count, warning codes, the number of unresolved blocks and unaccounted units, and the first 16 characters of the bundle's sha256. It mentions no one.
- **Limits and errors:**
  - bundles up to 8 MB;
  - at most 1 send per 60 s and 5 per hour on one machine;
  - 20 s timeout per attempt;
  - up to 2 retries with backoff on network errors, 429 and 5xx; any other 4xx is not retried;
  - every outcome is reported in Vietnamese, and the channel address is never echoed.
- **The address is never in the repository.** `release/embed_report_endpoint.py` reads `%USERPROFILE%\.vntext-secrets\report_webhook.txt`, or the file named by `VNTEXT_REPORT_WEBHOOK_FILE`. It refuses a file inside a Git work tree, and writes `app/worker/vntext/report_endpoint.bin` obfuscated (XOR + base64; this cannot hide the address from someone who extracts it). It never prints the address. A missing or invalid file still builds, just without the button. Publish fails if the payload holds a plain webhook address. `vntext/report_endpoint.bin` is in `.gitignore`.
- **Bug report hardening:** quoted segments in the bundle's log tail are now masked. A log line can quote game text, and the bundle can now leave the machine with one button.
- After "Tạo gói báo lỗi" the app names the manual routes: the "Gửi báo lỗi" button, or attaching the zip to a new issue at https://github.com/CaLanh24/VnText/issues/new.
- `docs/REPORT_WEBHOOK.md` covers creating the channel and webhook, where the file goes, and how to revoke or rotate the webhook. `docs/WORKFLOW.md` covers what DEV does when a bundle arrives (synth_from_report).
- Version/provenance 0.1.34 → 0.1.35 and the scoped ordinary transition `release-0.1.34` → `release-0.1.35`.

## Not done
- **No real send to the Owner's channel.** Every send test used a local fake server, with a guard that fails any non-local connection. The Owner presses "Gửi báo lỗi" once to try it.
- The extraction error screen has no button of its own. Its message already points to the bug-report tools on the Nhật ký page.

## Evidence
Receipts in `TEST_RUN/agent-evidence/release-0.1.35/`. `tests/unit/test_report_upload.py` covers:
- endpoint obfuscation round trip;
- a full multipart send to the fake server, with a leak scan of the summary, file name and bundle (fake game name, file name, a dialogue line, paths, the address);
- rate and size limits;
- retries on 5xx, no retry on 4xx, network failure;
- the CLI status;
- build embedding for valid, empty, wrong and multi-line files and for a file inside the repository;
- the app wiring (preview, then an explicit yes, then send);
- a source scan for plain addresses.
