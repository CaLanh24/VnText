# UX sau 0.1.11 — hồ sơ và phần kế thừa

Kế hoạch này thuộc giai đoạn sau 0.1.11; công việc release hiện tại được tiếp quản bởi [RELEASE_0.1.13](RELEASE_0.1.13.md), trạng thái đang làm ở [AI_STATE](../AI_STATE.md). Những acceptance chưa khép phải nằm trong ledger hiện hành; không chạy lại toàn bộ kế hoạch cũ.

- Các kết quả cancellation/CSV/editor/UI cũ chỉ có giá trị tại source, candidate và phạm vi receipt ghi nhận.
- Invariant hiện hành: [CONTRACTS](../CONTRACTS.md); gate hiện hành: [TEST_MATRIX](../TEST_MATRIX.md).
- Lịch sử điều tra và failed attempts giữ nguyên để tra khi có câu hỏi cụ thể. Không tự biến publication/test/mock thành native hoặc semantic acceptance.

## Lịch sử theo mục

Snapshot gốc: [POST_0.1.11_UX_REMEDIATION.md](history/POST_0.1.11_UX_REMEDIATION.md), origin `docs/POST_0.1.11_UX_REMEDIATION.md`, source docs `b7e842419bef`. Nội dung snapshot giữ nguyên; các đường dẫn tương đối trong đó được hiểu từ origin.

- [Objective](history/POST_0.1.11_UX_REMEDIATION.md#objective)
- [Persisted product decision](history/POST_0.1.11_UX_REMEDIATION.md#persisted-product-decision)
- [Scope and invariants](history/POST_0.1.11_UX_REMEDIATION.md#scope-and-invariants)
- [Acceptance checklist and order](history/POST_0.1.11_UX_REMEDIATION.md#acceptance-checklist-and-order)
- [Validation boundaries and resource controls](history/POST_0.1.11_UX_REMEDIATION.md#validation-boundaries-and-resource-controls)
- [Completion record](history/POST_0.1.11_UX_REMEDIATION.md#completion-record)
- [Progress and evidence (2026-10-24)](history/POST_0.1.11_UX_REMEDIATION.md#progress-and-evidence-2026-10-24)

<!-- Old inbound anchors route to this historical snapshot; no active authority. -->
<a id="post-0111-ux-and-workflow-remediation"></a>
<a id="objective"></a>
<a id="persisted-product-decision"></a>
<a id="scope-and-invariants"></a>
<a id="acceptance-checklist-and-order"></a>
<a id="validation-boundaries-and-resource-controls"></a>
<a id="completion-record"></a>
<a id="progress-and-evidence-2026-10-24"></a>
<a id="native-cancellation-investigation-2026-10-24"></a>
<a id="updated-isolated-native-launch-attempt-2026-10-24"></a>
<a id="acceptance-follow-up-after-translate-blank-package-fix-2026-10-24"></a>
<a id="public-release-inventory-preflight-not-route-acceptance"></a>
<a id="changed-files-so-far"></a>
<a id="brain-review-reconciliation"></a>
<a id="ct2-cancellation-follow-up-2026-10-24"></a>
<a id="native-model-status-stall-localization-2026-10-24"></a>
<a id="ctranslate2-worker-startup-preload-verification-2026-10-24"></a>
<a id="final-cancel-acceptance-and-handoff-2026-10-24"></a>
<a id="follow-up-eta-presentation-and-public-route-inventory-2026-10-24"></a>
<a id="synthetic-native-extract--translate--patch-and-readinessseverity-follow-up-2026-10-25"></a>
<a id="extract-readiness-caption-follow-up-2026-10-25"></a>
<a id="final-derived-translate-status-verification-and-correction-2026-10-25"></a>
<a id="final-completion-and-release-acceptance-2026-10-25"></a>
