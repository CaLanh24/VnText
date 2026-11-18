# Release0.1.21 — updater hotfix in progress

Owner2026-11-18 explicitly authorized source repair, testing0.1.18->new release, push and publication. Root temporary sole writer while fixed Claude quota remains blocked at cursor1940. No other writer. Preserve Owner installed020/data and blocked roots.

Confirmed source defect: DownloadFullAppRouteAsync replaces items inside foreach(hops), invalidating the enumerator after first downloaded/validated package. Fix collects downloaded hops separately, keeps hash/baseline validation, reports aggregate route progress, tests real two-hop package download plus second-hop tamper/cancel/network/continuity and retry. Also fix Setup update-source path when installer is launched from inside install root.

Measured temporary6GiB for exact RELEASE_RUN/candidate-0.1.21 under standing2026-10-24 authority: previous publisher peak4671559876B plus extra018 baseline589MB/chained packages220MB/native reserve. Shared11GiB/guard48MiB unchanged; terminal1GiB. No rebaseline/extra hops/dependency/model/license changes. Evidence TEST_RUN/agent-evidence/release-0.1.21/.

Important compatibility constraint: the original public018 binary itself contains the enumeration bug; new-source tests do not repair that old executable. Prove fixed-client multi-hop using verified public018 input and original018 Setup upgrade separately. Do not claim original018 in-app success unless actually demonstrated. No historical release edits, route removal or unsafe binary-only downgrade of worker. User data never used as fixture.

OPEN: focused regressions, clean-source epoch, isolated package, exact payload hash, native Setup/updater/public readback and cleanup. Prior020 unrelated gates may be reused only with explicit unchanged-source basis. Not whole-game or semantic-MT acceptance.
