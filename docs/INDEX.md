# Chỉ mục tài liệu VNText Studio

Đây là bản đồ truy xuất, không phải task tracker hay danh sách phải đọc hết. [AGENTS](../AGENTS.md) + [AI_STATE](../AI_STATE.md) là bootstrap; [WORKFLOW](WORKFLOW.md) quy định cập nhật/compact/history. Owner decision mới nhất > snapshot cũ; source/test/live receipt kiểm chứng behavior. Một lịch sử có chữ 'active/current' chỉ active tại thời điểm snapshot.

## Đọc gì cho câu hỏi nào

| Câu hỏi | Đọc trước | Chỉ mở thêm nếu cần |
|---|---|---|
| Đang làm gì, quyền gì, bước kế tiếp? | AI_STATE | Receipt/live DEV delta từ cursor |
| Source owner/caller ở đâu? | ARCHITECTURE theo heading | Source/tests ở owner đó |
| Invariant/cleanup/epoch/quyền đang có? | CONTRACTS đúng § | Authority/receipt mà § trỏ tới |
| Cần chạy gate nào? | TEST_MATRIX theo vùng thay đổi | Script/harness tương ứng; không mọi history |
| Release0.1.14/0.1.13 thiếu gì? | RELEASE_0.1.14 / RELEASE_0.1.13 ledger | Exact receipt, rồi snapshot nếu cần nguồn gốc |
| Vì sao từng đổi một hành vi? | Topic router ở bảng dưới | Chọn heading/ID trong archive, không đọc toàn file |
| Khôi phục sau compact/resume? | AGENTS + AI_STATE | Delta/receipt; lịch sử chỉ cho câu hỏi chưa trả lời |

## Tài liệu theo chủ đề

## Điểm vào và invariant

| Tài liệu | Vai trò / disposition |
|---|---|
| [AGENTS.md](../AGENTS.md) | CANONICAL — tra mục liên quan |
| [AI_STATE.md](../AI_STATE.md) | HIỆN HÀNH — checkpoint, xác minh Git/live |
| [ARCHITECTURE.md](../ARCHITECTURE.md) | CANONICAL — tra mục liên quan |
| [CONTRACTS.md](../CONTRACTS.md) | CANONICAL — tra mục liên quan |
| [docs/WORKFLOW.md](WORKFLOW.md) | CANONICAL — vận hành/compact/checkpoint/history chi tiết |
| [docs/INDEX.md](INDEX.md) | ROUTER — chỉ mục này, không task tracker |
| [docs/validation/SPECIALIZED_GATES.md](validation/SPECIALIZED_GATES.md) | GATE CATALOG — tra theo owner, không chạy mọi phase |
| [README.md](../README.md) | CỬA VÀO SẢN PHẨM — không bootstrap kỹ thuật |
| [TEST_MATRIX.md](../TEST_MATRIX.md) | CANONICAL — tra mục liên quan |

## Release và vận hành

| Tài liệu | Vai trò / disposition |
|---|---|
| [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) | HƯỚNG DẪN — chỉ đọc khi chạm owner tương ứng |
| [docs/DEVELOPMENT.md](DEVELOPMENT.md) | HƯỚNG DẪN — chỉ đọc khi chạm owner tương ứng |
| [docs/DEV_VM_PLAN.md](DEV_VM_PLAN.md) | DEFERRED — không provision VM từ tài liệu này |
| [docs/RELEASE_0.1.10.md](RELEASE_0.1.10.md) | HISTORY — release/authority cũ, không tự mở lại |
| [docs/RELEASE_0.1.11.md](RELEASE_0.1.11.md) | HISTORY — release/authority cũ, không tự mở lại |
| [docs/RELEASE_0.1.12.md](RELEASE_0.1.12.md) | HISTORY — release/authority cũ, không tự mở lại |
| [docs/RELEASE_0.1.13.md](RELEASE_0.1.13.md) | ĐÃ PHÁT HÀNH v0.1.13 (đã đóng; lịch sử) |
| [docs/RELEASE_0.1.14.md](RELEASE_0.1.14.md) | ĐÃ PHÁT HÀNH v0.1.14 (triage 9 finding UI QA, acceptance, native, cleanup); xem AI_STATE |
| [docs/RELEASE_0.1.6.md](RELEASE_0.1.6.md) | HISTORY — release/authority cũ, không tự mở lại |
| [docs/RELEASE_0.1.7.md](RELEASE_0.1.7.md) | HISTORY — release/authority cũ, không tự mở lại |
| [docs/RELEASE_0.1.8.md](RELEASE_0.1.8.md) | HISTORY — release/authority cũ, không tự mở lại |
| [docs/RELEASE_0.1.9.md](RELEASE_0.1.9.md) | HISTORY — release/authority cũ, không tự mở lại |
| [docs/UPDATE_0.1.7_REPAIR.md](UPDATE_0.1.7_REPAIR.md) | HISTORY — release/authority cũ, không tự mở lại |
| [release/README.md](../release/README.md) | HƯỚNG DẪN — chỉ đọc khi chạm owner tương ứng |
| [release/licenses/intel-2025.3-provenance.md](../release/licenses/intel-2025.3-provenance.md) | HƯỚNG DẪN — chỉ đọc khi chạm owner tương ứng |

## UI và UX

| Tài liệu | Vai trò / disposition |
|---|---|
| [docs/APP_JOURNAL.md](APP_JOURNAL.md) | TOPIC CONTRACT/HISTORY — không task đang mở; current contracts/Owner ưu tiên |
| [docs/AUTOMATIC_IMAGES.md](AUTOMATIC_IMAGES.md) | TOPIC CONTRACT/HISTORY — không task đang mở; current contracts/Owner ưu tiên |
| [docs/POST_0.1.11_UX_REMEDIATION.md](POST_0.1.11_UX_REMEDIATION.md) | ROUTER — summary hiện hành + snapshot lịch sử |
| [docs/SETTINGS_PLAN.md](SETTINGS_PLAN.md) | TOPIC CONTRACT/HISTORY — không task đang mở; current contracts/Owner ưu tiên |
| [docs/UPDATE_UI.md](UPDATE_UI.md) | ROUTER — summary hiện hành + snapshot lịch sử |

## RenPy và extraction

| Tài liệu | Vai trò / disposition |
|---|---|
| [docs/RENPY_EXTRACTOR_COMPLETENESS_AUDIT.md](RENPY_EXTRACTOR_COMPLETENESS_AUDIT.md) | HƯỚNG DẪN — chỉ đọc khi chạm owner tương ứng |
| [docs/RENPY_FINAL_ACCEPTANCE_20261022.md](RENPY_FINAL_ACCEPTANCE_20261022.md) | ROUTER — summary hiện hành + snapshot lịch sử |
| [docs/RENPY_FONT_COMPATIBILITY_PROPOSAL_20261022.md](RENPY_FONT_COMPATIBILITY_PROPOSAL_20261022.md) | HƯỚNG DẪN — chỉ đọc khi chạm owner tương ứng |
| [docs/RENPY_MULTILINE_DYNAMIC_20261022.md](RENPY_MULTILINE_DYNAMIC_20261022.md) | HƯỚNG DẪN — chỉ đọc khi chạm owner tương ứng |
| [docs/RENPY_REMEDIATION_20261021.md](RENPY_REMEDIATION_20261021.md) | HƯỚNG DẪN — chỉ đọc khi chạm owner tương ứng |

## Translation và đánh giá

| Tài liệu | Vai trò / disposition |
|---|---|
| [docs/QWEN_RESOURCE_READINESS.md](QWEN_RESOURCE_READINESS.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [docs/TRANSLATION_APPROVED_MEMORY_ENTRYPOINT.md](TRANSLATION_APPROVED_MEMORY_ENTRYPOINT.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [docs/TRANSLATION_APPROVED_MEMORY_SCOPE.md](TRANSLATION_APPROVED_MEMORY_SCOPE.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [docs/TRANSLATION_CANDIDATE_FEASIBILITY.md](TRANSLATION_CANDIDATE_FEASIBILITY.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [docs/TRANSLATION_DELIVERY_20261021.md](TRANSLATION_DELIVERY_20261021.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [docs/TRANSLATION_QUALITY_PLAN.md](TRANSLATION_QUALITY_PLAN.md) | ROUTER — summary hiện hành + snapshot lịch sử |
| [docs/TRANSLATION_SEMANTIC_ACCEPTANCE.md](TRANSLATION_SEMANTIC_ACCEPTANCE.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [docs/TRANSLATION_SEMANTIC_CAMPAIGN_20261021.md](TRANSLATION_SEMANTIC_CAMPAIGN_20261021.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [docs/TRANSLATION_TRAINING_PILOT_PROPOSAL.md](TRANSLATION_TRAINING_PILOT_PROPOSAL.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [evaluation/translation_owner_approval_v1/README.md](../evaluation/translation_owner_approval_v1/README.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [evaluation/translation_owner_review_v1/REVIEW.md](../evaluation/translation_owner_review_v1/REVIEW.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [evaluation/translation_quality_goal_v1/README.md](../evaluation/translation_quality_goal_v1/README.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [evaluation/translation_quality_goal_v1/SEMANTIC_DECISION.md](../evaluation/translation_quality_goal_v1/SEMANTIC_DECISION.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |
| [evaluation/translation_silver_packet_v1/README.md](../evaluation/translation_silver_packet_v1/README.md) | TRA CỨU — product translation memory/evaluation; research paused, không agent memory |

## Planning cục bộ

| Tài liệu | Vai trò / disposition |
|---|---|
| [.agent/SKILL.md](../.agent/SKILL.md) | ON DEMAND — spec/ticket/triage khi Owner yêu cầu; không runtime authority |
| [docs/agents/domain.md](agents/domain.md) | ON DEMAND — spec/ticket/triage khi Owner yêu cầu; không runtime authority |
| [docs/agents/issue-tracker.md](agents/issue-tracker.md) | ON DEMAND — spec/ticket/triage khi Owner yêu cầu; không runtime authority |
| [docs/agents/triage-labels.md](agents/triage-labels.md) | ON DEMAND — spec/ticket/triage khi Owner yêu cầu; không runtime authority |

## Hướng dẫn chuyên biệt

| Tài liệu | Vai trò / disposition |
|---|---|
| [tests/README.md](../tests/README.md) | HƯỚNG DẪN — chỉ đọc khi chạm owner tương ứng |
| [wpf_app/README.md](../wpf_app/README.md) | HƯỚNG DẪN — chỉ đọc khi chạm owner tương ứng |

## Snapshot lịch sử đã tách

Chỉ đọc theo câu hỏi/task ID. Nội dung evidence của snapshot giữ nguyên; ba relative link của translation history đã rebase theo vị trí mới. SHA trong bảng là Git blob gốc tại origin/commit, không phải hash file sau sửa link điều hướng. Không dùng một raw snapshot làm bootstrap/authority hiện tại. Origin và commit đủ để tìm lại lịch sử Git, không cần giữ binary/game/cache.

| Origin / topic | Snapshot | Original Git-blob bytes SHA256 |
|---|---|---|
| `docs/UPDATE_UI.md` @ `b7e842419bef` | [docs/history/UPDATE_UI.md](history/UPDATE_UI.md) | `11361a440c972cc20d6b0b96d395a90cdeafe9311aafc60ac756fe913825ce43` |
| `docs/TRANSLATION_QUALITY_PLAN.md` @ `b7e842419bef` | [docs/history/TRANSLATION_QUALITY_PLAN.md](history/TRANSLATION_QUALITY_PLAN.md) | `aa557f60e683e8f8ca199a9f7db44ed5262e2cd329b9deacdc53e724d60bb27f` |
| `docs/RENPY_FINAL_ACCEPTANCE_20261022.md` @ `b7e842419bef` | [docs/history/RENPY_FINAL_ACCEPTANCE_20261022.md](history/RENPY_FINAL_ACCEPTANCE_20261022.md) | `d5abe7f04d0d39d6f73df10dce3fa6207f515bb14653e1bde1616f7bbe5cd2e8` |
| `docs/POST_0.1.11_UX_REMEDIATION.md` @ `b7e842419bef` | [docs/history/POST_0.1.11_UX_REMEDIATION.md](history/POST_0.1.11_UX_REMEDIATION.md) | `766a93b9c033e9b623afe682d0b7fab5bd8fc9b32f480acc757307273bfdda26` |
| `docs/RELEASE_0.1.13.md` @ `b7e842419bef` | [docs/history/RELEASE_0.1.13.md](history/RELEASE_0.1.13.md) | `cb17777780ce59529ddf010a7eac74c73bc7f1a33dc2ea32da6e5c82c8e947ef` |

| `TEST_MATRIX.md` @ `b7e842419bef` | [docs/history/TEST_MATRIX.md](history/TEST_MATRIX.md) | `8bb010300480cdbe648b5b63d783b4b44a015b867e24d191047afcad94ccd059` |

## Duy trì bản đồ

Khi thêm/đổi disposition tài liệu, cập nhật đúng hàng này và con trỏ task hiện hành; không thêm một tracker/summary thứ hai. Landing page giữ kết quả/contract còn hiệu lực và đường dẫn archive; archive bất biến, không làm mới chữ pending/current cũ. Lịch sử chưa tách vẫn tra theo heading/câu hỏi; không nhập toàn bộ vào session.
