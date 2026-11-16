# Current checkpoint — B1 whole-border idle strokes + Q1 resource status, 2026-11-16

## Authority / writer
Owner assigned ONE batch B1+Q1 from `TEST_RUN/agent-evidence/b18-whole-border-review.{html,json}` on clean `3deca67`: scoped idle stroke families for inputs (#E2E3E5/#394352) and selects (#D3D7DE/#445266), never changing `CtrlBorderBrush`; and the resources task terminal status on Extract. R1/R2 stay frozen. No release/push/tag/version, no game/Owner CSV writes, no download/install. Old u16-focused / r17b-focused roots are policy-blocked: not reused, not retried.
Writer: the fixed Claude DEV (agent `72329c3d-5883-4cc8-8d14-60c73886ebd3`, session `76922e45-71b2-47a9-be97-cf18b927ae26`) is sole source writer and sole UI owner; Root reviews. DEV PASS is not QA acceptance.
Git: per-command `git -c user.name=Calanh -c user.email=316325487+CaLanh24@users.noreply.github.com commit`; Git config is never edited.

## Scope and map
docs/USABILITY_2026-11-13.md section "B1 whole-border idle strokes + Q1 resource status" (`--u16-fixture` rendered edges, `--b18-fixture`). Frozen: R1 secondary buttons, R2 hosts, checkbox/radio/grid boundaries, validation/focus colours, CSV/OCR/patch data guards.

## Verification and limits
Evidence (ignored): `TEST_RUN/agent-evidence/b18-*` and `DEV_RUN/bootstrap-build/build-identity.json`; read those receipts, not this text. Pressed state NOT PROVEN. Independent QA must re-open the built app.

## Candidate / retention
Candidate `DEV_RUN/bootstrap-build/Start-DEV.cmd` (Debug; isolated data under that folder). Owner CSV remains read-only (SHA `8e5d0e849a504b3e8354f676037e2c1ee55aaf5d2635cccb1e9a95a73a1bb0ef`).
