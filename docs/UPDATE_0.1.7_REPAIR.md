# SUPERSEDED — Owner accepts0.1.7 Setup as final baseline

Owner2026-10-19 explicitly says0.1.6 updater need not be repaired; public Setup0.1.7 is the final manual baseline, full in-app updates mandatory from0.1.8. Stop0.1.6→0.1.7 package/public-asset work. No runtime payloads, transient scopes or public mutations were created for that abandoned plan. New plan: docs/RELEASE_0.1.8.md. Earlier plan below is historical only.

# Missing0.1.7 full-app update — repair in progress

Owner explicitly requires existing0.1.6 users to receive/update in-app without reinstalling Setup. Clean main5afcb2a, single Coordinator/writer. Public0.1.7 currently only has Setup/provenance/checksums/notices; GitHub API authenticated and anonymous both list stable0.1.7. Source0.1.6 returns SetupRequired for missing update ZIP; popup only handles OfferAvailable. Reported Current on another machine is not reproduced and its cause remains UNKNOWN. Do not claim lack of a ZIP alone explains Current.

## Scope and gates

Reuse exact public0.1.6 Setup SHA25680393a825728bf5124bcafddf563f716b360675f5f67607cef535e32ff7a55f8 and exact public0.1.7 Setup SHA25682667f5333b4cdc1699e68f2ab1ccdf202f6b42f9057315693bd8912c67a90f6. No rebuilding/replacing published binaries/tag. Existing full-app publisher builds delta from their complete byte-verified inventories, models unchanged. Focused package tests, full-app/WPF harness, exact-source epoch/candidate, one installed old-app baseline and one bounded local transaction copy, actual local apply/health/readback/rollback coverage before publishing package. Then actual public0.1.6 app button: discover0.1.7, download, apply, restart; verify complete target inventory, data sentinel and model preservation, updater journal/receipt/worker. If actual public gate fails, remove only newly added package asset and report failure; no validators weakened. Public asset addition and Release/provenance/checksum correction are within Owner-authorized release repair. No game copies/dependency downloads.

## Budget and retention

Continuation of approved0.1.7 campaign uses exactly RELEASE_RUN/candidate-0.1.7, one fresh clean0.1.7 prospective epoch. Initial non-exempt681277870/shared4575800839bytes; project two~515MB payloads plus one~515MB local transaction copy and compact delta/backups below3GiB. Never duplicate environments or download Setup again; use retained hash-verified binaries. Terminal candidate/TEST_RUN absent and non-exempt<=1GiB. Retain compact receipts in DEV_RUN/update-0.1.7-repair. Existing DEV_RUN/VNText Studio.lnk stays usable. No app/runtime source edit/build is currently needed to generate the previously omitted supported update asset.
