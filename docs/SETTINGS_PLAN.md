# Settings expansion — Owner-approved scope, 2026-10-18

## Owner release continuation (2026-10-18)
Owner waives further Cockpit motion comparison and requests completion/public release. Keep the accepted motion and six frozen micro fixes. Prepare next patch0.1.6 after public0.1.5; authorization includes source/version/docs commit, push and GitHub release after required gates. No claim of exact motion/font parity. Dependencies still require explicit download/install permission under AGENTS.md; SDK10 is missing, permission requested. Existing dirty UI baseline remains authorized; one source writer. No game campaign or installer architecture changes.

Owner requests sidebar gradient/header calibration and real settings comparable to Cockpit. Explicit replies: Vietnamese/English; close exits or hides to system tray; background update checks/downloads only, installation/restart always explicit.

## Contract
- Defaults preserve Vietnamese/light theme/current update notifications and explicit install. New background download defaults OFF; close defaults Exit, start-minimized OFF, background strength100.
- Theme Light/Dark/System applies application appearance, never changes Windows settings. Strength only affects decorative canvas/sidebar; no fading controls/text.
- Language applies static application UI. User CSV/game/text, paths and logs must never be translated or rewritten as UI copy. Catalog coverage/remaining dynamic messages must be reported honestly.
- Tray keeps actual app/worker alive; restore/exit available. Explicit exit still protects Busy/unsaved CSV. Never create a hidden app without a recoverable tray icon.
- Background download reuses existing authenticated/size/hash validation and cancellation/lease. Busy/dirty gate remains; no auto apply/restart, no new endpoint. Update reminders user-configurable and skip-version respected.
- Data folder shows and opens actual current root. No migration or arbitrary relocation of release data: existing portable data-root invariant remains. Further data migration requires its own transaction/backup contract.
- Settings persist with bounded normalization and safe fallback; corrupted file never silently overwritten.

## Implementation/gates
One writer, approved dirty UI baseline retained. Source owners AppSettingsStore/MainViewModel.Settings/MainWindow and new presentation services; updater policy narrowly scoped, no package integrity change. No game/download/install/OS config/commit/release during validation. Shared .dev-env dependencies only. TEST_RUN disposable short scope for preference-specific harness; DEV_RUN/bootstrap-build remains sole app. Gates: targeted persistence/range/appearance/tray/update-policy tests, build, configured worker smoke, live Settings/tray/keyboard, cleanup. Do not relabel historical full-suite cleanup failures.

## Current
Implementation and focused technical validation complete; PM visual acceptance pending. See `DEV_RUN/preferences-expansion/REVIEW.md` and `final-receipt.json`. English static UI is implemented; dynamic diagnostic/error localization remains incomplete. Native tray harness passed; full manual tray/start-minimized/Busy sequence and real release download/install are not acceptance-proven. No migration, commit or release.

## Owner correction — Settings card/helper grammar (2026-10-18)
Settings options require a meaningful label and supporting description, e.g. “Ngôn ngữ hiển thị” / “Chọn ngôn ngữ hiển thị giao diện”. Presentation remains row-based: flat whole-row neutral-gray hover, no clickable row or added action/animation; only true card edge rows round their outside corners. Scoped Settings card border removed, row padding normalized, local label/helper hierarchy clarified. Commands, selected values, workflow and other frozen surfaces remain unchanged. Choice catalogs retain stable item identities when translating labels so refreshing language/appearance cannot clear displayed selections. No commit/release.

## Owner correction — Settings dropdowns (2026-10-18)
Use compact regular-weight Settings preference dropdowns matching the supplied reference, with subdued gray-blue fill and thin neutral border. Language150DIP/theme140DIP widths; accepted28DIP height retained. Local derived preference style keeps CSV dropdown styling unchanged. Background intensity is a percentage dropdown, not a slider:0–100% in10% steps, preserving any existing saved intermediate value and the same background-only behavior. No unrelated controls, commands or update logic changed. No commit/release.

## Owner correction — section spacing (2026-10-18)
Settings General/Data use48DIP after a completed card group before the next section heading, and12DIP from heading to its card, replacing14/24DIP. Based on supplied native crops: whitespace belongs above the next heading rather than below it. Only scoped section margins change; row/control/card geometry and behavior remain intact. No commit/release.

## Owner correction — divider/tab/card hover (2026-10-18)
Add the missing divider below update notifications. Settings tab header hover uses slightly stronger text emphasis (Bold,1.04 render scale); does not change layout. About-only four surfaces lift5DIP (was3), hover shadow32blur/12depth/.20alpha (was30/8/.13). Neutral surfaces and thin perimeter remain; reduced-motion uses immediate endpoint, with no host setting change. No command or workflow changes; no commit/release.

## Owner correction — actual upward card motion (2026-10-18)
Owner rejects shadow-only/immediate endpoint: About4cards must visibly slide upward slightly and return. About-only TranslateTransform now moves current Y→-5DIP/0 over160ms ease-out, including when host ClientAreaAnimation=false; this local exception implements explicit requested movement, never changes Windows settings. Other components retain prior reduced-motion policy. Shadow/layout/commands unchanged. Validate intermediate transform position and return in real WPF, not PNG alone. No commit/release.

## Owner correction — softer About hover (2026-10-18)
Owner rejects excessive lift/dark shadow. About-only lift reduced5→2DIP; local hover shadow blur22/depth4/opacity.10, replacing32/12/.20. Keep160ms real upward/return animation, neutral state, thin perimeter and commands. Supersedes previous lift/shadow amounts; no commit/release.

## Owner correction — responsive About and shadow clearance (2026-10-18)
Remove About1120DIP max width so two-column cards stretch with page width. Reserve12DIP left/right and28DIP bottom around About content for hover shadow falloff outside card bounds; use quality shadow rendering. Existing2DIP/160ms motion, shadow intensity and card commands unchanged. Verify restored/wider grid growth and inspect native hover; no commit/release.

## Owner correction — tab surface lift (2026-10-18)
Settings tab hover must lift the whole pill/background and text together, rather than text-only emphasis/scale. Move hover attachment to TabSurface; translate Y0→-1.5DIP→0 with160ms ease-out, no label-only scale or added shadow. Preserve tab selection/focus/layout; About remains2DIP. Local requested motion still works when host general animations are disabled. Screenshot endpoint alone does not prove Cockpit timing. No commit/release.

## Owner correction — centered tab zoom, supersedes tab lift (2026-10-18)
Owner rejects vertical translation: SettingsTab whole surface now scales1→1.04→1 from center over160ms, Y stays0. Background and label scale together; no extra shadow or layout-size change. About motion unchanged. No commit/release.

## Owner correction — tab hover color, no weight change (2026-10-18)
Hover on an inactive Settings tab changes gray text to primary ink (black in light theme), not Bold. Keep fixed SemiBold role in neutral/hover/selected states, selected blue and centered pill zoom. Use theme-aware ink for dark mode. Supersedes prior hover Bold instruction; no commit/release.

## Owner correction — data row balance and page rhythm (2026-10-18)
Data uses shared Settings card/row grammar,96DIP minimum rows, consistent24DIP text inset/centered actions; folder label+secondary path, status/path roles balanced, no artificial equal total height for one-row versus two-row semantic groups. Workflow page headers title-only, same title role/top band as Settings; remove breadcrumb and subtitle, retain actions/status. Increase vertical component gaps inside Extract/Translate/Patch from12/14/16 to16/20/24DIP and header-to-content32DIP; preserve order/commands/bindings/visibility/validation. No commit/release.

## Owner correction — action colors/iconography/type roles (2026-10-18)
Primary actions use existing blue; disabled-primary mint residue changed to blue-gray in light/dark. Success/status/toggle green stays semantic. Adopt licensed Lucide0.468.0 vectors for navigation and GitHub repository icon; preserve icon boxes/hit targets. Font audit retains embedded Inter family; Settings helper explicitly Normal instead of inherited tab SemiBold, labels Medium; existing title/body/nav/button sizes retained where screenshot lacks contrary measurements. Record role inventory and evidence limits, no exact Cockpit font-family claim. No commit/release.


## Owner continuation — visual parity (2026-10-18)
Owner explicitly authorizes continuing on the current uncommitted UI baseline on main. Compare all current paired captures against Cockpit; correct typography roles, color, spacing and hover without changing workflow or the accepted preference behavior. Settings language remains Vietnamese/English; background downloads require confirmation before install/restart.

Owner supplies the new blue/turquoise feather image for sidebar/About artwork; retain the existing window/application ICO unchanged (explicit correction). Current parity pass supersedes earlier data row96DIP/type-labelMedium defaults: data rows88DIP, labelsNormal, explicit tab-header-only SemiBold; About labelsBold/captionssoft,120DIP cards/16DIP gap.


## Owner-approved micro calibration (2026-10-18)
Continue current UI baseline; preserve outer geometry, no hover FontWeight transition. Nav13.5; tab optical13.5 with old14DIP measurement preserved, centered hover1.025/160ms; segmented shadow opacity.18 only; short preference selects140x30 (long values retain widths); label-helpergap8 with unchanged rowheight; About1DIP/160ms lift,1DIP edge#4063ED, same shadow; release notes show only actual offered version chip and omit duplicated caption. Exact font family/timing parity not claimed. Other broad polish deferred.


## Owner visual acceptance / freeze (2026-10-18)
Owner reviewed the new native/comparison bundle and explicitly accepted all six micro fixes and Release Notes cleanup. This is visual acceptance of the bounded micro pass, superseding its earlier visual-pending status, not whole-app parity or Release verification.

Frozen: nav13.5; tab optical13.5/centeredscale1.025/no hover FontWeight change; tab shadow opacity.18; short selects140x30; label-helpermargin8 with current rowheight; About hoverlift1DIP/current edge/shadow. Preserve card sizes/gaps, sidebar width/gutter, selected pill/tab geometry, existing hover/selected palette and brand footprint. Do not reopen these to chase estimated screenshot pixels. Empty Release Notes retain only the actual message when no offered version exists; never invent version/date/download data.

Remaining P2/P3 observations: About hero roughly4px offset; tiny grid-gap difference; page-title gradient; canvas light distribution; slight font/rendering metrics; live motion feel. These are observations, not new implementation assignments. If Owner requests a next pass, bound the audit to page-title gradient -> canvas gradient -> live motion. Do not reopen card/select/nav size/row spacing/tab geometry. PNG endpoints do not prove timing/easing, and exact Cockpit font family remains unproven. No automatic motion retuning or font replacement from screenshots.


## Owner continuation — gradients and live motion (2026-10-18)
Owner requests the bounded remaining pass: Settings page-title blue→cyan; light workspace upper-right cyan light fading to neutral bottom based on same-size reference samples. Keep all six accepted micro values, geometry/sidebar/colors and logo/ICO frozen; workflow titles and dark canvas retain existing appearance without reference. Background strength must still neutralize the decorative canvas at0. Live motion timing/easing needs continuous evidence; native post-action snapshots do not prove it, clip requested; no guessed timing changes.

## Owner correction — workspace right gutter (2026-10-18)
Owner supplied aligned whole-window reference showing VNText card right edge closer to the window than Cockpit. Sole writer clean main9ccbfbe. Bounded exception to prior geometry freeze: shared UiPageInset right24→32DIP only, left/top/bottom unchanged; applies all workflow/settings/CSV page content consistently. No card padding, typography, sidebar or motion edits. Validation one DEV build/configured worker smoke and native right-edge inspection; no game/copy/download, default1GiB/shared5GiB, TEST_RUN absent. Evidence DEV_RUN/right-gutter.

Right-gutter outcome PASS bounded correction: build-smoke.json exit0/configured five-step worker smokePASS, actual Extract/Settings inspected at32DIP right inset, captures DEV_RUN/right-gutter. Source9ccbfbe + one-token theme diff, docs follow build; no clean exact-HEAD Release claim. Shared token covers other pages by construction; no unrelated regression suite for a margin-only change. TEST_RUN absent, no games/downloads/publication.

## Owner correction — sidebar optical/color pass (2026-10-18)
Clean main751306d, sole writer. Owner explicitly requests remaining sidebar sizing/color/type/spacing alignment, bounded exception to geometry freeze. Supplied150% reference shows Cockpit selected row~62px versus VNText66px, active fill~199/212/240 versus215/223/246. Correct nav row44→42DIP, active#C9D5F0, brand15.5→15DIP, brand top44→43DIP and visible divider#D0D6E3/bottomgap10→12. Nav13.5 regular embedded Inter and brand Bold roles audited/retained; different labels cannot prove a font family mismatch, no speculative global replacement. Sidebar width/insets/logo/ICO unchanged. Gate one DEVbuild/configured worker smoke, actual sidebar normal/selected inspection. No game/copy/download; default1GiB/shared5GiB, TEST_RUN absent terminal. Evidence DEV_RUN/sidebar-polish.

Sidebar pass outcome bounded implementationPASS/Owner review pending: additional local selected foreground#2454EE (dark#8CB5FF), runtime UiAppearance selected-fill override corrected and theme-aware divider; no speculative font family replacement. Final build-smoke-accepted.json exit0/configured worker smokePASS; actual native selected/brand/divider inspected. final.png and compare.png pair Owner150% crop versus resampled native100% crop; not exact raster/font parity. Evidence source751306dd1f6396b2466d1fbe49da90118e95ca56 + task diff. TEST_RUN absent; no games/downloads/publication.
