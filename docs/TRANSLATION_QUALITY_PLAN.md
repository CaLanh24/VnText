# Chất lượng dịch — disposition và tra cứu

Nghiên cứu semantic/model đang paused theo quyết định Owner cho release 0.1.13. Giữ CT2/OPUS-MT và các giới hạn đã được chấp nhận cho release này; đây không phải semantic quality PASS và không là quyền mở lại research/training/model campaign.

- Trạng thái task: [AI_STATE](../AI_STATE.md); authority sản phẩm: [CONTRACTS §4](../CONTRACTS.md#4-translation-states-và-memory) và [§4a](../CONTRACTS.md#4a-local-translation-v2-classifier-model-cache-glossary-và-context).
- Delivery bounded đã ghi: [TRANSLATION_DELIVERY_20261021](TRANSLATION_DELIVERY_20261021.md).
- Campaign semantic có disposition riêng: [TRANSLATION_SEMANTIC_CAMPAIGN_20261021](TRANSLATION_SEMANTIC_CAMPAIGN_20261021.md). Chỉ tra khi task hiện tại yêu cầu.
- 'Memory' trong các proposal translation là dữ liệu sản phẩm, không phải bộ nhớ Coordinator. Không dùng synthetic approval làm human gold hoặc ngân hàng câu trả lời toàn app.

## Lịch sử theo mục

Snapshot gốc: [TRANSLATION_QUALITY_PLAN.md](history/TRANSLATION_QUALITY_PLAN.md), origin `docs/TRANSLATION_QUALITY_PLAN.md`, source docs `b7e842419bef`. Nội dung snapshot giữ nguyên; các đường dẫn tương đối trong đó được hiểu từ origin.

- [Active goal quality campaign — Owner continued2026-10-20](history/TRANSLATION_QUALITY_PLAN.md#active-goal-quality-campaign--owner-continued2026-10-20)
- [Product seam0đ — terminal2026-10-20, PASS bounded feature](history/TRANSLATION_QUALITY_PLAN.md#product-seam0đ--terminal2026-10-20-pass-bounded-feature)
- [M1–M4 offline0đ đã thực thi — 2026-10-20](history/TRANSLATION_QUALITY_PLAN.md#m1m4-offline0đ-đã-thực-thi--2026-10-20)
- [Owner quyết định ngân sách0đ — 2026-10-20](history/TRANSLATION_QUALITY_PLAN.md#owner-quyết-định-ngân-sách0đ--2026-10-20)
- [Disposition hiện hành — 2026-10-20](history/TRANSLATION_QUALITY_PLAN.md#disposition-hiện-hành--2026-10-20)
- [Owner kích hoạt Phase 1 — 2026-10-19](history/TRANSLATION_QUALITY_PLAN.md#owner-kích-hoạt-phase-1--2026-10-19)
- [Quyết định Owner — 2026-10-11](history/TRANSLATION_QUALITY_PLAN.md#quyết-định-owner--2026-10-11)
- [Premise hiện tại và giới hạn](history/TRANSLATION_QUALITY_PLAN.md#premise-hiện-tại-và-giới-hạn)
- [1. Bộ đánh giá và dữ liệu](history/TRANSLATION_QUALITY_PLAN.md#1-bộ-đánh-giá-và-dữ-liệu)
- [2. Cải thiện route hiện có](history/TRANSLATION_QUALITY_PLAN.md#2-cải-thiện-route-hiện-có)
- [3. Một thử nghiệm model có ngữ cảnh](history/TRANSLATION_QUALITY_PLAN.md#3-một-thử-nghiệm-model-có-ngữ-cảnh)
- [4. Huấn luyện có điều kiện](history/TRANSLATION_QUALITY_PLAN.md#4-huấn-luyện-có-điều-kiện)
- [Acceptance và đóng từng đợt](history/TRANSLATION_QUALITY_PLAN.md#acceptance-và-đóng-từng-đợt)
- [Research plan disposition — 2026-10-20](history/TRANSLATION_QUALITY_PLAN.md#research-plan-disposition--2026-10-20)
- [Phase20 active — six observed semantic classes](history/TRANSLATION_QUALITY_PLAN.md#phase20-active--six-observed-semantic-classes)
- [Phase21 activation — constrained terminology transport / finite source normalization](history/TRANSLATION_QUALITY_PLAN.md#phase21-activation--constrained-terminology-transport--finite-source-normalization)
- [Phase22 activation — composition/opaque density prerequisite remediation](history/TRANSLATION_QUALITY_PLAN.md#phase22-activation--compositionopaque-density-prerequisite-remediation)

<!-- Old inbound anchors route to this historical snapshot; no active authority. -->
<a id="cải-thiện-chất-lượng-dịch-sau-bản-phát-hành-đang-chuẩn-bị"></a>
<a id="active-goal-quality-campaign--owner-continued2026-10-20"></a>
<a id="proposed-measurable-goal-acceptance-brain-review-required-before-complete"></a>
<a id="final-bounded-goal-evidence-matrix--2026-10-21-brain-accepted"></a>
<a id="initial-backlog-and-first-implementation-owner"></a>
<a id="current-measured-semantic-disposition-and-remaining-acceptance"></a>
<a id="product-seam0đ--terminal2026-10-20-pass-bounded-feature"></a>
<a id="activation-và-gate-history-giữ-nguyên-failure-evidence"></a>
<a id="m1m4-offline0đ-đã-thực-thi--2026-10-20"></a>
<a id="owner-quyết-định-ngân-sách0đ--2026-10-20"></a>
<a id="disposition-hiện-hành--2026-10-20"></a>
<a id="khép-prerequisite-retry-phase22"></a>
<a id="owner-kích-hoạt-phase-1--2026-10-19"></a>
<a id="protocol-frozen-before-the-first-baseline"></a>
<a id="phase-1-baseline-receipt--2026-10-19"></a>
<a id="coordinator-acceptance-and-development-review--2026-10-19"></a>
<a id="phase2-trial-a-acceptance--reject-unconditional-lexical-off-change"></a>
<a id="phase2-full-pipeline-comparison-protocol--declared-2026-10-19"></a>
<a id="phase2-remediation-acceptance--candidate-rejected-original-product-restored"></a>
<a id="step3-concrete-rd-proposal--approval-pending-nothing-downloaded"></a>
<a id="quyết-định-owner--2026-10-11"></a>
<a id="premise-hiện-tại-và-giới-hạn"></a>
<a id="1-bộ-đánh-giá-và-dữ-liệu"></a>
<a id="2-cải-thiện-route-hiện-có"></a>
<a id="3-một-thử-nghiệm-model-có-ngữ-cảnh"></a>
<a id="4-huấn-luyện-có-điều-kiện"></a>
<a id="acceptance-và-đóng-từng-đợt"></a>
<a id="step3-owner-approval-and-bounded-execution--2026-10-19"></a>
<a id="step3-downloadpreflight-result--proven_blocked-2026-10-19"></a>
<a id="owner-approved-ram-increase--host-access-blocked-2026-10-19"></a>
<a id="guest-only-memory-reclamation--2026-10-19"></a>
<a id="low-memory-alternate-protocol-fixed-before-inference-2026-10-19"></a>
<a id="low-memory-result--pass-bounded-feasibility-no-quality-promotion"></a>
<a id="promptcontext-refinement-task--owner-activated2026-10-19"></a>
<a id="phase4-terminal-result--pass-bounded-evaluation-product-admission-rejected"></a>
<a id="phase5-owner-activation--protection-first-then-meaning-new-evaluation-2026-10-19"></a>
<a id="phase5-terminal--pass-bounded-protectionevaluation-no-app-promotion"></a>
<a id="phase6-bounded-protocol--owner-activation-2026-10-19"></a>
<a id="phase6-terminal--pass-bounded-measurement-semantic-admission-rejected"></a>
<a id="phase7-activation--target-isolation--logic--roles-2026-10-19"></a>
<a id="phase7-terminal--pass-bounded-experiment-carrier-candidate-rejected"></a>
<a id="phase8-activation--bounded-natural-translationauditretry-2026-10-19"></a>
<a id="phase8-terminal--pass-bounded-pipelineevaluation-automatic-semantic-admission-rejected"></a>
<a id="phase9-activation--source-derived-constraint-checker-2026-10-19"></a>
<a id="phase9-terminal--pass-bounded-constraint-implementationevaluation-no-semantic-promotion"></a>
<a id="phase10-activation--remaining-abstentions-critical-terminology-stable-revision-2026-10-19"></a>
<a id="phase10-terminal--pass-bounded-implementation-no-product-promotion"></a>
<a id="phase11-activation--added-prohibition-and-three-named-abstentions-2026-10-19"></a>
<a id="phase11-terminal--pass-named-old3remediation-product-unchanged"></a>
<a id="phase12-activation--close-three-named-phase11-review-cases-2026-10-20"></a>
<a id="phase12-terminal--pass-bounded-named3-opus-unchanged"></a>
<a id="phase13-activation--unresolved-versus-unfinished-2026-10-20"></a>
<a id="phase13-terminal--pass-named-unresolved-nuance-opus-unchanged"></a>
<a id="phase14-activation--frozen-mixed-regression-audit-2026-10-20"></a>
<a id="phase14-terminal--pass-mixed-audit-remaining-translation-defects-explicit"></a>
<a id="final-research-closure-activation--phase15-owner2026-10-20"></a>
<a id="phase15-terminal--pass-bounded-execution-candidate-admission-rejected"></a>
<a id="research-plan-disposition--2026-10-20"></a>
<a id="phase16-activation--owner-continues-named-residual-precision-2026-10-20"></a>
<a id="phase16-checkpoint-and-continuing-compound-precision--phase17-2026-10-20"></a>
<a id="phase17-terminal--pass-named-compound-repairsevaluation-admission-still-rejected"></a>
<a id="phase18-prerequisite-remediation-within-ongoing-control-acceptance"></a>
<a id="phase18-terminal--pass-residualcontrol-prerequisite-repairs-and-affected-validation"></a>
<a id="phase19-activation--frozen-broad-fresh-comparison-and-blind-separate-agent-review"></a>
<a id="phase19-terminal--pass-frozen-broad-evaluationreviewer-separation-admission-rejected"></a>
<a id="phase20-active--six-observed-semantic-classes"></a>
<a id="phase20-terminal--premise_invalid-for-semantic-hint-sufficiency"></a>
<a id="phase21-activation--constrained-terminology-transport--finite-source-normalization"></a>
<a id="phase21-terminal--pass-mechanism-evaluation-admission-rejected"></a>
<a id="phase22-activation--compositionopaque-density-prerequisite-remediation"></a>
<a id="phase22-terminal--premise_invalid-for-no-major-fresh-generalization"></a>
