# Release 0.1.20 — preparation ledger

Owner 2026-11-17: review remaining issues and release if no blocking issue remains. Not published; no Release acceptance yet. Root is temporary sole writer while the fixed Claude DEV is weekly-quota blocked (cursor1940).

The prior DEV UI findings are implemented through `e72311b`; exact DEV gates/native evidence are in `TEST_RUN/agent-evidence/f23-root-final.json`. Those do not replace Release gates. Scope: preserve existing B1/R1/R2/header and all CSV/OCR/Patch safety guards. No game run or Owner data mutation.

Release preparation advances version to0.1.20 and adds only that task's5GiB temporary allocation/profile and forward19→20 handoff under standing2026-10-24 storage authority. Shared11GiB/guard48MiB unchanged; return to normal1GiB after terminal cleanup. No rebaseline or extra epoch-hop authority is granted. Record measured usage/plan before payload allocation. Preserve blocked u16/r17b/obj roots; builds use isolated artifacts only.

Open prerequisites: exact clean-source epoch, full regression and release gates, Setup/package validation, installed upgrade/rollback and native checks, authenticated GitHub publication, public readback and final cleanup. GitHub CLI was not authenticated at initial preflight; Owner was asked to log in without sending secrets.

Evidence: `TEST_RUN/agent-evidence/release-0.1.20/` (per-source command/exit/hash and limits). Publication must wait for all required gates; focused DEV PASS is insufficient.
