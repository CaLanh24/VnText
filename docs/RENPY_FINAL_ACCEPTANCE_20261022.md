# RenPy — kết quả bounded và tra cứu

Đây là hồ sơ audit/acceptance RenPy đã diễn ra, không phải lệnh tiếp tục game/capture campaign. Real-game E2E hiện được Owner defer, NOT TESTED cho release hiện tại; không đổi các verdict bounded, PARTIAL hay NOT_VERIFIED của từng run cũ.

- Extract/compiled/archive/writeback hiện hành: [CONTRACTS §8](../CONTRACTS.md#8-naninovel-và-renpy-boundary), source và test tương ứng.
- Gate chọn theo vùng thay đổi: [TEST_MATRIX](../TEST_MATRIX.md). Multiline/dynamic và remediation có hồ sơ riêng trong [INDEX](INDEX.md#renpy-và-extraction).
- Thiếu SDK và cancellation của release đang mở: [AI_STATE](../AI_STATE.md), [release 0.1.13](RELEASE_0.1.13.md). Không suy PASS toàn game/Release từ aggregate hoặc harness lịch sử.

## Lịch sử theo mục

Snapshot gốc: [RENPY_FINAL_ACCEPTANCE_20261022.md](history/RENPY_FINAL_ACCEPTANCE_20261022.md), origin `docs/RENPY_FINAL_ACCEPTANCE_20261022.md`, source docs `b7e842419bef`. Nội dung snapshot giữ nguyên; các đường dẫn tương đối trong đó được hiểu từ origin.

- [Aggregate checkpoint before real-game acquisition](history/RENPY_FINAL_ACCEPTANCE_20261022.md#aggregate-checkpoint-before-real-game-acquisition)
- [Frozen real-game run1 — PDL](history/RENPY_FINAL_ACCEPTANCE_20261022.md#frozen-real-game-run1--pdl)
- [Frozen real-game run2 — AquaGuardians](history/RENPY_FINAL_ACCEPTANCE_20261022.md#frozen-real-game-run2--aquaguardians)
- [Declared-sample recovery plan](history/RENPY_FINAL_ACCEPTANCE_20261022.md#declared-sample-recovery-plan)
- [Final bounded gate packet — PROVEN_BLOCKED acceptance](history/RENPY_FINAL_ACCEPTANCE_20261022.md#final-bounded-gate-packet--proven_blocked-acceptance)
- [Required candidate follow-up — concrete eligibility/access results](history/RENPY_FINAL_ACCEPTANCE_20261022.md#required-candidate-follow-up--concrete-eligibilityaccess-results)
- [Owner local archive continuation — RUN PLAN, gate2 reopened](history/RENPY_FINAL_ACCEPTANCE_20261022.md#owner-local-archive-continuation--run-plan-gate2-reopened)
- [Owner RAR terminal packet — original archived text route PASS; native visual PROVEN_BLOCKED](history/RENPY_FINAL_ACCEPTANCE_20261022.md#owner-rar-terminal-packet--original-archived-text-route-pass-native-visual-proven_blocked)
- [Owner completion continuation after978d23f](history/RENPY_FINAL_ACCEPTANCE_20261022.md#owner-completion-continuation-after978d23f)
- [Completion continuation result after978d23f — PM_DECISION_REQUIRED font scope](history/RENPY_FINAL_ACCEPTANCE_20261022.md#completion-continuation-result-after978d23f--pm_decision_required-font-scope)
- [Latest terminal ingest — run7 supported display premise exhausted](history/RENPY_FINAL_ACCEPTANCE_20261022.md#latest-terminal-ingest--run7-supported-display-premise-exhausted)
- [Plain-text replacement DEV ingest — 2026-10-23](history/RENPY_FINAL_ACCEPTANCE_20261022.md#plain-text-replacement-dev-ingest--2026-10-23)
- [Current supported diagnosis and run11 terminal — 2026-10-23](history/RENPY_FINAL_ACCEPTANCE_20261022.md#current-supported-diagnosis-and-run11-terminal--2026-10-23)

<!-- Old inbound anchors route to this historical snapshot; no active authority. -->
<a id="renpy-final-aggregate-and-real-game-acceptance"></a>
<a id="aggregate-checkpoint-before-real-game-acquisition"></a>
<a id="frozen-real-game-run1--pdl"></a>
<a id="frozen-real-game-run2--aquaguardians"></a>
<a id="declared-sample-recovery-plan"></a>
<a id="final-bounded-gate-packet--proven_blocked-acceptance"></a>
<a id="required-candidate-follow-up--concrete-eligibilityaccess-results"></a>
<a id="owner-local-archive-continuation--run-plan-gate2-reopened"></a>
<a id="owner-rar-terminal-packet--original-archived-text-route-pass-native-visual-proven_blocked"></a>
<a id="owner-completion-continuation-after978d23f"></a>
<a id="completion-continuation-result-after978d23f--pm_decision_required-font-scope"></a>
<a id="latest-terminal-ingest--run7-supported-display-premise-exhausted"></a>
<a id="plain-text-replacement-dev-ingest--2026-10-23"></a>
<a id="current-supported-diagnosis-and-run11-terminal--2026-10-23"></a>
<a id="run11-timeline-correction-and-bounded-harness-observability-remediation"></a>
<a id="run12-lifecycle-and-native-visual-outcome--2026-10-23"></a>
<a id="run13-terminal-capture-audit--2026-10-23"></a>
<a id="run13-terminal-capture-audit--2026-10-23-1"></a>
<a id="local-transport-and-renderer-source-audit--2026-10-23"></a>
<a id="sdk-safe-mode-supported-graphics-diagnostic--2026-10-23"></a>
<a id="run14-terminal--saved-gl2-preference-normal-software-rendering-fallback--2026-10-23"></a>
<a id="run15-setup-failure-and-run16-angle2-terminal--2026-10-23"></a>
<a id="run17-terminal--angle2-initialized-native-scene-capture-remained-unavailable--2026-10-23"></a>
<a id="run17-supported-capture-support-diagnostic-draft--2026-10-23-not-sent"></a>
<a id="owner-acceptance-disposition--defer-native-game-visual-verification-to-a-post-update-installed-app--2026-10-23"></a>
