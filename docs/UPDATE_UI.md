# UI cập nhật và Cockpit — tra cứu hiện hành

Tài liệu này là cửa tra cứu UI, không phải danh sách task đang chạy. Acceptance UI của release đang làm ở [AI_STATE](../AI_STATE.md) và [ledger 0.1.13](RELEASE_0.1.13.md).

- Hành vi/invariant hiện hành: [CONTRACTS §6](../CONTRACTS.md#6-wpf-binding-command-và-workflow-state), [§10 Release](../CONTRACTS.md#10-portable-release).
- Scope/frozen UI Owner đã chấp nhận: [SETTINGS_PLAN](SETTINGS_PLAN.md); tra đúng mục/ảnh trước đổi geometry hoặc motion. Không lấy ảnh/harness làm claim pixel/font/motion parity.
- Lịch sử dưới đây chứa các trạng thái 'current', 'pending', 'approved' tại thời điểm riêng; không tự mở lại campaign hay cấp quyền chạy task. Nguồn mới nhất và quyết định Owner hiện hành ưu tiên.

## Lịch sử theo mục

Snapshot gốc: [UPDATE_UI.md](history/UPDATE_UI.md), origin `docs/UPDATE_UI.md`, source docs `b7e842419bef`. Nội dung snapshot giữ nguyên; các đường dẫn tương đối trong đó được hiểu từ origin.

- [Owner-authorized progressive disclosure remediation — 2026-10-14](history/UPDATE_UI.md#owner-authorized-progressive-disclosure-remediation--2026-10-14)
- [Owner-authorized content density / UX-writing pass (2026-10-13)](history/UPDATE_UI.md#owner-authorized-content-density--ux-writing-pass-2026-10-13)
- [Historical result — final About and keyboard-focus pass (superseded by Owner acceptance below, 2026-10-13)](history/UPDATE_UI.md#historical-result--final-about-and-keyboard-focus-pass-superseded-by-owner-acceptance-below-2026-10-13)
- [Batch hội tụ giao diện WPF theo reference sáng — 2026-10-13](history/UPDATE_UI.md#batch-hội-tụ-giao-diện-wpf-theo-reference-sáng--2026-10-13)
- [Ủy quyền điều phối DEV không đồng bộ — 2026-10-12](history/UPDATE_UI.md#ủy-quyền-điều-phối-dev-không-đồng-bộ--2026-10-12)
- [Mục tiêu và nguồn thiết kế](history/UPDATE_UI.md#mục-tiêu-và-nguồn-thiết-kế)
- [Tham khảo app trực tiếp và bổ sung của Owner](history/UPDATE_UI.md#tham-khảo-app-trực-tiếp-và-bổ-sung-của-owner)
- [Sidebar và Cài đặt](history/UPDATE_UI.md#sidebar-và-cài-đặt)
- [Phạm vi UI được Owner duyệt triển khai — 2026-10-11](history/UPDATE_UI.md#phạm-vi-ui-được-owner-duyệt-triển-khai--2026-10-11)
- [Chi tiết Sidebar và Cài đặt](history/UPDATE_UI.md#chi-tiết-sidebar-và-cài-đặt)
- [Luồng UX đề xuất cho implementation](history/UPDATE_UI.md#luồng-ux-đề-xuất-cho-implementation)
- [Scope và boundaries](history/UPDATE_UI.md#scope-và-boundaries)
- [Bằng chứng nghiệm thu](history/UPDATE_UI.md#bằng-chứng-nghiệm-thu)
- [Corrected terminal disposition and latest Owner visual direction — 2026-10-13](history/UPDATE_UI.md#corrected-terminal-disposition-and-latest-owner-visual-direction--2026-10-13)
- [Cockpit bright visual implementation and DEV evidence — 2026-10-13](history/UPDATE_UI.md#cockpit-bright-visual-implementation-and-dev-evidence--2026-10-13)
- [Settings visual follow-up — 2026-10-13](history/UPDATE_UI.md#settings-visual-follow-up--2026-10-13)
- [Residual WPF visual pass — 2026-10-13](history/UPDATE_UI.md#residual-wpf-visual-pass--2026-10-13)
- [Historical pre-acceptance continuation — superseded by Owner freeze (2026-10-13)](history/UPDATE_UI.md#historical-pre-acceptance-continuation--superseded-by-owner-freeze-2026-10-13)
- [Owner acceptance — structural UI freeze (2026-10-13)](history/UPDATE_UI.md#owner-acceptance--structural-ui-freeze-2026-10-13)
- [Owner scope - final content-density remediation (2026-10-17)](history/UPDATE_UI.md#owner-scope---final-content-density-remediation-2026-10-17)
- [Owner scope update - measurement/reference audit only (2026-10-17)](history/UPDATE_UI.md#owner-scope-update---measurementreference-audit-only-2026-10-17)
- [Owner authorization - one shared-shell/token pass (2026-10-17)](history/UPDATE_UI.md#owner-authorization---one-shared-shelltoken-pass-2026-10-17)
- [Owner acceptance and next pass - shared components (2026-10-17)](history/UPDATE_UI.md#owner-acceptance-and-next-pass---shared-components-2026-10-17)
- [Owner authorization - final residual component pass (2026-10-17)](history/UPDATE_UI.md#owner-authorization---final-residual-component-pass-2026-10-17)
- [PM acceptance — shared visual system ACCEPTED / FROZEN (2026-10-17)](history/UPDATE_UI.md#pm-acceptance--shared-visual-system-accepted--frozen-2026-10-17)
- [Owner scope and Brain closeout — workflow composition audit (2026-10-17)](history/UPDATE_UI.md#owner-scope-and-brain-closeout--workflow-composition-audit-2026-10-17)
- [Owner authorization - Translate supplementary-tools grouping (2026-10-17)](history/UPDATE_UI.md#owner-authorization---translate-supplementary-tools-grouping-2026-10-17)
- [Owner scope and Brain closeout — visual character/page composition audit (2026-10-17)](history/UPDATE_UI.md#owner-scope-and-brain-closeout--visual-characterpage-composition-audit-2026-10-17)
- [Owner superseding criterion — visual resemblance / first-glance parity (2026-10-17)](history/UPDATE_UI.md#owner-superseding-criterion--visual-resemblance--first-glance-parity-2026-10-17)
- [Owner pause and Brain audit — visual + interaction fidelity (2026-10-17)](history/UPDATE_UI.md#owner-pause-and-brain-audit--visual--interaction-fidelity-2026-10-17)
- [Owner authorization - Cockpit fidelity Pass A only (2026-10-17)](history/UPDATE_UI.md#owner-authorization---cockpit-fidelity-pass-a-only-2026-10-17)
- [PM acceptance Pass A and authorization Pass B (2026-10-17)](history/UPDATE_UI.md#pm-acceptance-pass-a-and-authorization-pass-b-2026-10-17)
- [Brain Pass B bounded review closeout (2026-10-17)](history/UPDATE_UI.md#brain-pass-b-bounded-review-closeout-2026-10-17)
- [Owner decision - supplementary action rhythm only (2026-10-17)](history/UPDATE_UI.md#owner-decision---supplementary-action-rhythm-only-2026-10-17)
- [Brain supplementary-rhythm bounded closeout (2026-10-17)](history/UPDATE_UI.md#brain-supplementary-rhythm-bounded-closeout-2026-10-17)
- [Owner directive - Settings About and updater near-1:1 (2026-10-17)](history/UPDATE_UI.md#owner-directive---settings-about-and-updater-near-11-2026-10-17)
- [Brain About/updater checkpoint — 2026-10-17](history/UPDATE_UI.md#brain-aboutupdater-checkpoint--2026-10-17)
- [Owner correction scope — About/updater + hover, 2026-10-17](history/UPDATE_UI.md#owner-correction-scope--aboutupdater--hover-2026-10-17)
- [Correction closeout — 2026-10-17](history/UPDATE_UI.md#correction-closeout--2026-10-17)
- [Owner acceptance / Shell Fidelity resume — 2026-10-17](history/UPDATE_UI.md#owner-acceptance--shell-fidelity-resume--2026-10-17)
- [Shell Fidelity pass checkpoint — 2026-10-17](history/UPDATE_UI.md#shell-fidelity-pass-checkpoint--2026-10-17)
- [Owner correction — Settings hover and sidebar project removal (2026-10-17)](history/UPDATE_UI.md#owner-correction--settings-hover-and-sidebar-project-removal-2026-10-17)
- [Owner correction — About outline logo / hover / nav weight (2026-10-17)](history/UPDATE_UI.md#owner-correction--about-outline-logo--hover--nav-weight-2026-10-17)
- [Sidebar press feedback — Owner decision (2026-10-17)](history/UPDATE_UI.md#sidebar-press-feedback--owner-decision-2026-10-17)
- [Owner residual correction — tab weight / nav gap / About lift (2026-10-17)](history/UPDATE_UI.md#owner-residual-correction--tab-weight--nav-gap--about-lift-2026-10-17)
- [Owner correction — Settings header/edge hover and feather silhouette (2026-10-17)](history/UPDATE_UI.md#owner-correction--settings-headeredge-hover-and-feather-silhouette-2026-10-17)
- [Owner reference correction — sidebar alignment / section labels / original feather (2026-10-17)](history/UPDATE_UI.md#owner-reference-correction--sidebar-alignment--section-labels--original-feather-2026-10-17)
- [Owner functional settings expansion (2026-10-18)](history/UPDATE_UI.md#owner-functional-settings-expansion-2026-10-18)

<!-- Old inbound anchors route to this historical snapshot; no active authority. -->
<a id="thông-báo-cập-nhật-trong-app--yêu-cầu-trước-phát-hành"></a>
<a id="owner-authorized-progressive-disclosure-remediation--2026-10-14"></a>
<a id="state-matrix-and-presentation-contract"></a>
<a id="validation-and-capture-gates"></a>
<a id="owner-authorized-content-density--ux-writing-pass-2026-10-13"></a>
<a id="scoped-wording-and-disclosure-inventory"></a>
<a id="historical-result--final-about-and-keyboard-focus-pass-superseded-by-owner-acceptance-below-2026-10-13"></a>
<a id="batch-hội-tụ-giao-diện-wpf-theo-reference-sáng--2026-10-13"></a>
<a id="owner-authorization--residual-ui-pass-2026-10-13"></a>
<a id="chẩn-đoán-source-và-mốc-hiện-tại"></a>
<a id="metrics-hiện-tại--mục-tiêu"></a>
<a id="kết-quả-batch-cuối-và-bằng-chứng-native--2026-10-13"></a>
<a id="ủy-quyền-điều-phối-dev-không-đồng-bộ--2026-10-12"></a>
<a id="mục-tiêu-và-nguồn-thiết-kế"></a>
<a id="tham-khảo-app-trực-tiếp-và-bổ-sung-của-owner"></a>
<a id="sidebar-và-cài-đặt"></a>
<a id="phạm-vi-ui-được-owner-duyệt-triển-khai--2026-10-11"></a>
<a id="chi-tiết-sidebar-và-cài-đặt"></a>
<a id="luồng-ux-đề-xuất-cho-implementation"></a>
<a id="scope-và-boundaries"></a>
<a id="bằng-chứng-nghiệm-thu"></a>
<a id="checkpoint-native-transaction--2026-10-12"></a>
<a id="brain-review--settings-persistence-and-local-offer-2026-10-12"></a>
<a id="ui-follow-up--geometry-and-blocked-native-controls-2026-10-12"></a>
<a id="corrected-terminal-disposition-and-latest-owner-visual-direction--2026-10-13"></a>
<a id="cockpit-bright-visual-implementation-and-dev-evidence--2026-10-13"></a>
<a id="settings-visual-follow-up--2026-10-13"></a>
<a id="validation-and-native-observation"></a>
<a id="residual-wpf-visual-pass--2026-10-13"></a>
<a id="historical-pre-acceptance-continuation--superseded-by-owner-freeze-2026-10-13"></a>
<a id="owner-acceptance--structural-ui-freeze-2026-10-13"></a>
<a id="owner-reviewed-screenshot-and-build-provenance"></a>
<a id="owner-scope---final-content-density-remediation-2026-10-17"></a>
<a id="technical-result---2026-10-17"></a>
<a id="brain-visual-review---scoped-pass-2026-10-17"></a>
<a id="owner-scope-update---measurementreference-audit-only-2026-10-17"></a>
<a id="matched-reference-evidence-ingested---limited-audit-closeout-2026-10-17"></a>
<a id="owner-authorization---one-shared-shelltoken-pass-2026-10-17"></a>
<a id="single-shared-shelltoken-pass---technical-pass-screenshot-ready-2026-10-17"></a>
<a id="brain-post-pass-evidence-2026-10-17"></a>
<a id="owner-acceptance-and-next-pass---shared-components-2026-10-17"></a>
<a id="single-shared-component-pass---technical-pass-screenshot-ready-2026-10-17"></a>
<a id="brain-shared-component-evidence-2026-10-17"></a>
<a id="owner-authorization---final-residual-component-pass-2026-10-17"></a>
<a id="final-residual-pass---technical-pass-screenshot-ready-2026-10-17"></a>
<a id="brain-final-residual-evidence-2026-10-17"></a>
<a id="pm-acceptance--shared-visual-system-accepted--frozen-2026-10-17"></a>
<a id="owner-scope-and-brain-closeout--workflow-composition-audit-2026-10-17"></a>
<a id="owner-authorization---translate-supplementary-tools-grouping-2026-10-17"></a>
<a id="translate-supplementary-tools-grouping---technical-pass-2026-10-17"></a>
<a id="brain-scoped-acceptance--translate-supplementary-tools-2026-10-17"></a>
<a id="owner-scope-and-brain-closeout--visual-characterpage-composition-audit-2026-10-17"></a>
<a id="owner-superseding-criterion--visual-resemblance--first-glance-parity-2026-10-17"></a>
<a id="owner-pause-and-brain-audit--visual--interaction-fidelity-2026-10-17"></a>
<a id="owner-authorization---cockpit-fidelity-pass-a-only-2026-10-17"></a>
<a id="fidelity-pass-a---technical-pass-live-interaction-proof-pending-2026-10-17"></a>
<a id="brain-pass-a-scoped-acceptance-2026-10-17"></a>
<a id="pm-acceptance-pass-a-and-authorization-pass-b-2026-10-17"></a>
<a id="fidelity-pass-b-trial---technical-pass-visual-acceptance-pending-2026-10-17"></a>
<a id="brain-pass-b-bounded-review-closeout-2026-10-17"></a>
<a id="owner-decision---supplementary-action-rhythm-only-2026-10-17"></a>
<a id="supplementary-action-rhythm---technical-pass-screenshot-ready-2026-10-17"></a>
<a id="brain-supplementary-rhythm-bounded-closeout-2026-10-17"></a>
<a id="owner-directive---settings-about-and-updater-near-11-2026-10-17"></a>
<a id="brain-aboutupdater-checkpoint--2026-10-17"></a>
<a id="owner-correction-scope--aboutupdater--hover-2026-10-17"></a>
<a id="correction-closeout--2026-10-17"></a>
<a id="owner-acceptance--shell-fidelity-resume--2026-10-17"></a>
<a id="shell-fidelity-pass-checkpoint--2026-10-17"></a>
<a id="owner-correction--settings-hover-and-sidebar-project-removal-2026-10-17"></a>
<a id="owner-correction--about-outline-logo--hover--nav-weight-2026-10-17"></a>
<a id="sidebar-press-feedback--owner-decision-2026-10-17"></a>
<a id="owner-residual-correction--tab-weight--nav-gap--about-lift-2026-10-17"></a>
<a id="owner-correction--settings-headeredge-hover-and-feather-silhouette-2026-10-17"></a>
<a id="owner-reference-correction--sidebar-alignment--section-labels--original-feather-2026-10-17"></a>
<a id="owner-functional-settings-expansion-2026-10-18"></a>
