# Product entrypoint proposal — reviewed package translations

Current disposition (2026-10-21): bounded editor feature accepted by Brain, including strict saved-row preview/explicit confirmation and native functional evidence. Final styling-only Cancel input remained tool-refused; previous functional cancel/confirm remains the accepted evidence. The proposal and incremental reports below are chronological history; they do not indicate a currently pending implementation. See TRANSLATION_DELIVERY_20261021.md.

Status: premise/scope for Brain review before implementation. Sole DEV writer;
same zero-cost goal, OPUS/protocol/framework unchanged, no real user data touched.
The accepted synthetic strict-memory pilot proves reuse boundaries, not a usable
general import/approval UI. It must not ship its known answers as defaults.

## Existing entrypoints and gap

- WPF `MainViewModel.Workflow.cs::ImportExistingTranslation` selects a donor CSV
  and calls the existing patch/external_import worker route. This is import of
  translations, not evidence that a human reviewed their semantics.
- `csv_editor_api.save_csv` validates source/schema/order, backs up and atomically
  saves translation edits, reconciling eligible review rows. Save is not a grant
  to reuse those texts automatically outside their saved rows.
- Existing strict-memory runtime reads guard/store but creates neither through
  product UI. The synthetic helper explicitly converts a sealed decision only;
  it cannot stand in for a product feature or permission from a real user.

## Proposed user flow

1. User opens the active package CSV, optionally imports donor translations or
   edits them with existing behavior. No automatic memory approval on import or
   save. Dirty/Busy editor cannot approve; first save/reload uses existing rules.
2. Select reviewed rows, then explicit editor action “Dùng bản dịch đã duyệt
   trong gói này”. Display a preview of exact selected source/target and count;
   explain reuse is limited to this package + exact file/context/source/method,
   not training/global glossary and not a quality guarantee for other lines.
3. User confirms selected rows. Reject empty/invalid/duplicate/ambiguous scope,
   missing file/context/method, stale disk CSV baseline or pending task. Save
   original decision separately with explicit reviewer-kind=user-confirmed and
   exact accepted-row digests; human_gold/training flags remain false unless a
   separate explicit research authorization ever exists.
4. Create/extend strict memory only in the chosen package via generic backend
   owner, preserving prior approval records. A different target for an already
   approved scope is a visible conflict requiring a separate explicit replacement
   decision; no silent overwrite or whole-store reset. Other package CSV/memory,
   original source/game files and default banks remain untouched.
5. Report approved/reused counts and exact scope. Existing translate/retranslate
   consumes strict policy and existing structural/glossary gates. Export/copy to
   another package does not inherit authority; copied binding misses. Six pilot
   glossary terms are not added globally or injected into unrelated scenes.

## Ownership, transaction and permission boundary

Backend owner: existing `mt_memory.py` plus editor API caller; WPF existing editor
viewmodel/service/view command and localization. No new worker protocol/task or
second memory engine. Direct local editor service already owns CSV operations;
follow its invocation pattern after inspection, do not invent an external CLI.
Approval store writes require CAS against the reviewed CSV bytes and existing
policy/store snapshot, no concurrent writer. Stage/verify bounded JSON, preserve
backups, activate guard first (fail-closed until matching store), atomically
replace store, readback; rollback restores only exact own-written bytes, retaining
foreign mutations as a reported conflict. Explicit decision record has ownership
and immutable hash, no absolute path in portable exported labels. Malformed
strict store/guard must refuse extending, never silently learn from CSV.

Product runtime must accept both owner-delegated-agent (pilot) and user-confirmed
review kinds with checked per-entry attribution, not turn manual Save into
human-gold. User flow must clearly allow cancel with no writes. This introduces
an explicit approval action; it does not make a consent decision for a user.
Only generated fixture data may be used by DEV acceptance; no existing user store
will be approved/imported by the agent under this task.

## Gate and run budget proposal

Freeze final API/schema after Brain review and before source edits. Focused
backend red/green: selected-only semantics, disk CAS, canceled preview/no writes,
invalid structure/scope, duplicates/conflicts, unknown policy, overwrite/rollback
and concurrent mutation, strict rebuild/reopen/cache preservation. WPF harness:
selection/dirty/busy/preview/confirmation cancellation, correct backend request,
visible errors/count/scope and existing save/import unaffected. Affected editor/
external-import/memory/glossary/worker tests next. One actual generated-package
editor approval -> translate/retranslate -> patch/read-back workflow with hostile
scope controls, <=180s; no benchmark corpus or model campaign. FinalDEV build/
smoke <=600s. Native UI acceptance requires supported CU/actual UI evidence;
harness/build alone cannot grant it, and previous client CU limitation is not
desktop capability evidence. No install/auth/transport bypass to satisfy UI gate.

Complete cleanup/test outputs registered, artifact<=1GiB/.dev-env<=6GiB, one DEV
executable. Brain reviews concrete implementation/evidence. Product action scope
is proposed, not already delivered; original goal cannot complete from this doc.

## Brain-approved implementation contract frozen before edits

Brain accepted bounded integration in existing editor under this goal. API owner
`vntext/mt_memory.py` (generic persistence) + `csv_editor_api.py` (disk authority);
WPF `Services/TranslationCsvEditorService.cs`, existing CsvEditor viewmodel/view,
localization and harness. No worker-task/protocol addition. Inspect actual service
invocation before binding implementation; no invented alternate transport.

Preview API takes active CSV path + selected unique keys only. Backend reads
disk rows; source/target/context supplied by UI are never approval authority.
Returns exact selected display rows plus opaque bounded preview token binding
CSV bytes, selection and current decision/guard/store snapshots. Preview performs
validation but creates no file/backup. Confirm takes the same path/keys/token,
re-reads and revalidates all scope/structure/glossary/metadata and CAS snapshots;
reject stale/missing/duplicate rows. UI blocks Busy/Dirty/Loading before both
calls. User cancel calls no confirm and writes nothing. Tokens are consistency
checks, not identity/authentication or permission to approve on another user's
behalf. No technical schema/hash displayed as product prose.

New strict entries record per-entry reviewer_kind=user-confirmed; old delegated
entries retain their attribution. Strict root allows mixed attribution only by
validated per-entry records, never relabels all prior entries. All human_gold/
training_eligible remain false. Each review decision records exact key/source/
target/file/fullcontext/method and package-binding; public exported labels omit
absolute guest paths. No hidden default synthetic IDs/target bank in runtime.

Existing strict store: retain valid entries, reject conflicting target/scope or
malformed/unknown state; no automatic replacement. Legacy store: preview explicitly
states conversion will preserve a byte-exact legacy backup but only selected
confirmed disk rows become the strict allowlist; unapproved legacy entries remain
in backup, not silently granted approval or blended into strict reuse. Confirmation
must include conversion in the preview token; no downgrade to legacy on failure.

Per-package ownership guard prevents parallel approval writers; snapshots include
CSV/store/scopeguard/decision. Stage decision/guard/store and backups in owned
bounded paths, verify, CAS immediately before each activation, guard first then
store fail-closed. Rollback restores only own exact bytes; foreign mutation
survives with conflict evidence. Final readback required; interrupted activation
refuses reuse rather than inventing approvals or repairing malformed state.

Gate ladder and budgets above now accepted for implementation: focused backend
then WPF harness/affected existing editor/import/memory, one generated workflow
<=180s/one active package (bounded negative copy), finalDEV<=600s, no broad100/
model tuning/userstore. Native UI acceptance separately remains mandatory for
claiming the interaction verified; supported skill/tool only. No source edits
for this entrypoint have occurred at this freeze checkpoint.

Implementation checkpoint after freeze: `preview_reviewed_memory` now reads only
saved disk rows selected by keys; never takes caller targets as authority. Checks
scope completeness/uniqueness across the wholeCSV, validates structural/glossary
contract, refuses corruptstrictstate; returns rows/count/conversionnotice and a
snapshot token binding CSV/policy/decision/manifest/glossary/actualwhitelistJSON.
Preview creates no files/backups. Focusedred before implementation preserved;
latest21editor testsPASS0skip/warning/cleanupPASS, including actualvalidationinput
snapshot changes and unselectedduplicate scope rejection. Confirm transaction,
reviewkind extension,legacy conversion,UI/harness/workflow and currentDEV build
are not yet implemented/verified. No production approval/import claim.

Next implementation checkpoint: confirm activation now implemented under
per-package exclusive approval ownership, regenerates preview from saved disk
and compares the user's token, preserving the exact snapshot from that preview
through activation (not a later snapshot that could admit stale rows). Selected
entries only; valid legacy preserved as exact backup but unselectedlegacyMT not
approved; malformedlegacy refuses. Guard-first activation followed by decision/
store CAS/readback; fault tests restore only ownedbytes, retainforeignmutation.
Mixedreview stores retain per-entryreviewer and checkeddecisionartifact, no
human_gold/training change.66focused/affectedbackendtestsPASS0skip/warning/
cleanupPASS. Original red and intermediategreen/fault receipts retained.

Existing CLI editor invocation and WPFservice now expose preview/confirm; editor
selection action displays scrollable exactsource/target/file/context with scope
and explicitlegacyconversionnotice; cancel no confirmcall. Dirty/busy/loading/
selection/path rechecked before confirm. HarnessPASS after correcting its own
privateproperty setup compileerror; originalfailure retained. Native dialog/UI,
actualgeneratedentrypoint workflow and finalcurrentDEVbuild/smoke pending. No
featureacceptance claim from harness alone, no realuserstore touched.

Latest technical delivery: public
`evaluation/translation_owner_approval_v1/entrypoint-delivery.json` binds current
source/test hashes and original receipts. Actual generated CLI/worker workflow
extract/import->preview(no writes)->confirm4->clear drafts via existing save->
translate reuses exact4approved targets->patch/readback PASS, originalinput and
donor unchanged, copiedpackage binding rejects reuse. First run failed only at
negativecopy of liveSQLiteWAL after positivepatch; retainedFAIL, corrected copy
uses only immutableapprovalartifacts. Localized vi/enharness and currentDEVbuild/
5stepworkersmokePASS; backenderrors remain existingVI, app-owned UI uses UiText.

Native acceptance PROVEN_BLOCKED in this client: supportedsky import/list calls
work, but list_apps returns0VNText and list_windows returns titleVNTextStudio
with appidentifierOpenAI.Codex rather than the separately verified DEVexepath.
No input/capture performed on that inconsistenttarget (CodexUI forbidden by
skill); no helper/protocol bypass. This is targetselection/integration evidence,
not appGUIFAIL. Isolatedgeneratedfixture settings/noautoupdate only; ownprocesses
stopped and canonicalcleanup/terminalpurgePASS. NativeUI NOTVERIFIED, no waiver
or feature/wholegoalPASS inferred. Brain review of delivery/remainingprerequisite
pending. No source/test rerun warranted without new concrete error/prerequisite.

Brain-reviewed supported recovery considered: `sky.launch_app({app:DEVexe})`
then refresh inventories. Documented launch API has no environment/isolated-data
option, so cannot prove preserving the prior per-process fixturedata/noautoupdate
environment. No recoverylaunch issued against defaultuserstore; exact disposition
`translation-editor-memory-native-recovery-disposition.json` retained externally.
No appfield/handle rewriting or Codexwindow activation/capture/input attempted.

Brain terminal review accepted **PASS bounded technical delivery**, directly
matching33source/test hashes,8receipt hashes,currentassembly and stageddiffcheck.
No concrete technicaldefect identified in that review. NativePROVEN_BLOCKED is
accepted as a genuine externalprerequisite; neither fullfeatureinteraction nor
wholegoalcomplete is granted. SupportedCU must return the correctappidentity
with safeisolatedfixture, or actualOwnernativeevidence must establish interaction;
do not ask Owner to repair hiddenhelper or relax the gate. Acceptance recorded
docs-only, no unchangedgate reruns. Keep currentDEV/source/evidence, no new
campaign/Release. Git authoridentity is still a separate commit prerequisite.

Fresh authorized native retry (2026-10-20) reproduced the identity conflict.
The isolated current DEV process PID12888 was verified at
`DEV_RUN/bootstrap-build/VNText.Studio.App.exe`, SHA256
`6FE96EA326BAE10F40E84EC08BF56B59BF24D11055DF263E1153FD6F86826C3D`.
Supported `sky.list_windows()` returned window3016018 titled `VNText Studio`
under `OpenAI.Codex_2p2nqsd0c76g0!App`. No window activation, input or capture
followed. Evidence is retained under
`C:/Users/VNTextDev/Downloads/VM-Acceptance/translation-editor-memory-native-fresh1-`
with suffixes `prep.json`, `launch.json`, `blocker.json`, `cleanup.json` and
`terminal.json`. Owned processes stopped, registered cleanup exit0 and terminal
purge PASS; TEST_RUN absent. Brain directly reviewed the fresh blocker and
cleanup and accepted PROVEN_BLOCKED native identity. Technical acceptance is
retained; native interaction and the whole goal remain incomplete. No further
safe action is identified until supported identity changes or actual native
evidence arrives. Do not repeat unchanged discovery, tests, builds or model runs.

On 2026-10-21, following Owner's request to accept the delivery, Brain formally
reconfirmed PASS for the bounded technical editor-approval delivery after checking
all source/test and receipt hashes in entrypoint-delivery, executable/assembly
hashes, both diffs and absent transient roots at base c9825d4. This requires no
repeat approval of those accepted parts. Full feature acceptance remains
PROVEN_BLOCKED solely at native UI target identity; no new source defect was
identified, no GUI failure inferred, and no native gate waiver or whole-quality
goal completion granted. Existing DEV and staged changes are retained.

## Native prerequisite correction and observed interaction — 2026-10-21

The earlier attribution was narrowed by read-only Windows process queries:
isolated DEV PID10088 actually carried Codex's AUMID and package full name.
This was inherited OS package identity, not evidence that VNText's own startup
needed an invented taskbar ID. No product startup change was made.

A single controlled direct launch used Microsoft's documented
`PROC_THREAD_ATTRIBUTE_DESKTOP_APP_POLICY` with
`PROCESS_CREATION_DESKTOP_APP_BREAKAWAY_ENABLE_PROCESS_TREE` (1), keeping the
same user/default token and explicit isolated environment/workdir. No parent,
job, mitigation, token or security attribute was changed. Constants were checked
against Microsoft's win32metadata WinBase.h at
`c16762d41f1bd641ff8c4389ebf16ee50747129f`. Contract and script were retained
before execution in VM-Acceptance as `editor-identity-launch-contract.json` and
`editor-identity-controlled-launch.py`; this is process launch only, not a UI
helper or transport. PID14568 returned NO_APPLICATION (15703) and NO_PACKAGE
(15700), and supported sky returned the exact DEV process-backed identity.

Through supported sky only, the generated two-row fixture was opened in the
editor. Selecting native-a showed its source/translation/file/context and the
package-only warning. Cancel preserved CSV/manifest hashes and created no
approval artifacts. Explicit confirmation in a new preview produced the native
success message and exactly one user-confirmed strict entry: native-a lookup
matches, native-b misses, CSV and manifest remain unchanged. Settings navigation
was observed without changing settings. No user data was approved.

External evidence: `editor-native-before.json`, `editor-native-cancel.json`,
`editor-native-confirm.json` (includes the three actual approval JSON artifacts),
and `editor-native-{preview,confirm,settings}-original.jpg`. The documented
Screenshot.url returned JPEG; these are unconverted originals, not PNG. The
initial screenshot requested for the correctly identified but hidden DEV showed
the foreground app; it was not exported. Activating the returned DEV target
resolved the screenshot mismatch. Modal cached-element errors were retained in
tool history; supported modal Raise followed by Confirm completed the action.

Owned processes stopped and registered cleanup/terminal purge PASS, TEST_RUN
absent; receipts `editor-identity-controlled-{cleanup,terminal}.json`. No product
source, model, build or repeated technical gates changed. Native evidence has
been submitted to Brain for acceptance; whole-quality completion is not implied.

Brain subsequently accepted the native functional evidence and superseded the
old identity blocker. A bounded UI delta applies existing AppFont/UiBodySize,
surface/ink resources, body/field styles and outline/blue primary button styles
to the new dialog. English counters now use count-neutral wording. Affected
localized WPF harness and current DEV build/worker smoke PASS; backend unchanged.
`entrypoint-ui-delivery.json` records current source/test and assembly hashes and
the new receipts. The original delivery receipt remains historical.

The final styled preview is retained as original JPEG in
`editor-dialog-styled-preview-original.jpg`. Escape did not close that second
modal; the supported Cancel action refused a root/modal target binding. No
approval artifacts were written and CSV/manifest hashes remained unchanged.
Do not claim that second Cancel completed. The previously accepted native
cancel/confirm evidence is separate. Owned cleanup/purge PASS; Brain final
UI/feature review remains pending. No model/backend rerun or product startup
identity patch was made.

### Brain final feature verdict — 2026-10-21

PASS bounded editor reviewed-memory feature. Brain independently matched all
33 current source/test hashes and 16 receipt hashes in entrypoint-ui-delivery,
the current assembly SHA256
`1ee94e05f467ec723639242314a9670c31f6a55b7979ad468525953bfa064821`, unchanged
base c9825d4 and successful terminal cleanup with transient roots absent. The
styled preview was visually accepted. This combines prior actual native selected
preview/cancel/confirm/readback with the current styling-only harness, build,
worker smoke and preview/no-write evidence. Final styled Cancel was tool-refused,
not a second native Cancel PASS; no unchanged backend rerun is required.

This closes the bounded feature acceptance, not the whole translation-quality
goal or residual new-sentence semantics. Training prerequisites remain unmet and
training deferred. No new campaign/publication is authorized. Commit remains
pending actual Owner author identity; no identity/config is invented.

Brain then reviewed the original four-requirement campaign matrix and accepted
the bounded remediation-and-evidence campaign as PASS, with no unmet numbered
gate identified. The stored objective was checked against that scope before
closure. This supersedes pending whole-bounded-goal review pointers above, while
retaining all semantic, human-gold, training and Release limitations.
