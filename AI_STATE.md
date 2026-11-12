# Current checkpoint — 0.1.18 public; DEV cleanup complete (2026-11-12)

## Authority and scope
Owner requires all VNText project work, scratch and evidence inside the checkout `C:/v`. Standard Codex/Claude application profiles remain application state, not project scratch. See docs/workflows/workspace.md. Owner requested DEV disk cleanup and removal of the external `vnrg`/`ctest` roots.

## Release and acceptance
Public release: https://github.com/CaLanh24/VnText/releases/tag/v0.1.18. Tag peels to built source `956a7046e3f960f8a08c7338c4cbe50d44cd05cc`; Setup SHA256 `454ef46fa68d6211f22bef02981b8405fa28e4bbb300898a8d3e68e9bc5e930a`. Published assets/tag were not changed by this cleanup. Subsequent local changes are maintenance/tooling and docs, not a rebuilt product.
Fresh Setup/resources/uninstall/upgrade and the public native 0.1.17 -> 0.1.18 update passed on function, including canary preservation and health. Setup visual capture, all-DPI/theme and whole-game semantic quality remain NOT_PROVEN. Offline translation is a rough draft. Release ledger: docs/RELEASE_0.1.18.md.

## Writer and cwd
Fixed Claude DEV `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26`, cursor 1709. DEV hit its session limit (reset reported 21:00 Asia/Tokyo); Root temporarily completed cleanup under the quota exception. No second writer/model/session was created.
At an idle boundary Root verified no queued/running turn, pending message, process lease, workspace lock or Claude process. A compare-and-swap changed ONLY the persisted agent cwd from `C:/ctest` to `C:/v`; ID, session, model and permissions were unchanged. Bridge inventory confirms cwd `C:/v`. One resume check returned the existing quota error, not a resume failure; productive resumed work is not proven until quota recovers. No global Claude project transcript or memory was copied/deleted. Task-owned UI/build processes are closed; the Owner's Desktop/vntextapp process and worker were not touched.

## Cleanup results
- Retired old accepted DEV candidates through the helper (about 11.6 MB). Release candidate/baselines had already been disposed.
- Removed obsolete research models, llama runtime, pip cache, duplicate SDK/Python downloads and provisioning metadata: 6,902,963,866 B. Removed exactly six unused NuGet 8.0.31 runtime/ref pack directories: 400,534,428 B. Exact reviewed target exceptions; root guards unchanged.
- Shared `.dev-env`: 11,280,156,739 -> 3,976,658,445 B. Retained configured Python environments, SDK10, Python3.12, RenPy SDK, OPUS-MT product model, pinned 8.0.30 refs, 8.0.32 packs and required host packs. One 12 KB pip wheel remains after ACL refusal (no ACL changes).
- Rehomed `C:/vnrg` byte-exact to `TEST_RUN/agent-evidence/legacy-vnrg`: 2,317 files / 194,993,360 B. Root independently verified every old/new file against the index before deletion. Original-game restore proof and saves are preserved; immutable approval/history text was not rewritten.
- Deleted exact external roots `C:/vnrg` and `C:/ctest` after hash preservation, no-reparse, no-consumer and absolute-path checks. Both are absent; removed external bytes 195,706,884. `C:/vngr` never existed. No future project writes target those roots.
- `tests/tools/original_game_guard.py` defaults now use in-checkout evidence; 14 targeted tests passed (3 new); no product build required. No external fallback was introduced.
- Project non-exempt was 627,634,604 B after rehome, below the normal 1 GiB cap; the external evidence is now honestly counted. Remaining small gap: 78 old TEST_RUN/tmp directories (~15.5 MB) were not removed because the canonical helper skips stale MISSING records. No guard/history workaround was used.

## Evidence and next boundary
Canonical evidence: `TEST_RUN/agent-evidence/`. Historical `C:/vnrg/...` references resolve through `provenance-index.json`, SHA256 `1e5d4ff9c73a95d5692c187af5ee27e09d81c7e8020b53877740d892ca8a29df`; receipt bytes and original paths remain historical. Current cleanup receipts: `dev-cleanup/external-roots-cleanup-{plan,result}.json`, shared-cleanup/nuget receipts and `cwd-apply-*.json`. Release receipts now reside at `TEST_RUN/agent-evidence/legacy-vnrg/evidence/release-0.1.18/`.
No active product/release task. Future release-profile allocation must reconcile Git/epoch; cleanup did not rebaseline or change published payloads. Return sole writing to the fixed DEV when quota recovers after reconciling current Git/checkpoint. Local cleanup commits have not been pushed.
