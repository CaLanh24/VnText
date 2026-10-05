---
name: vntext-matt-planning
description: For VNText requests to write a feature spec, split an approved plan into tickets, or triage an issue; choose the appropriate local Markdown workflow without requiring the user to name a skill. Do not use for ordinary coding or status questions.
---

# VNText planning

Choose one workflow matching the Owner's request:

- **Spec:** synthesize the agreed problem, acceptance, constraints, affected
  seams and explicit unknowns. Publish under `.scratch/<feature>/spec.md` only
  when the Owner asks for a durable spec.
- **Tickets:** split an approved plan into small verifiable end-to-end slices;
  record real blocking dependencies in separate numbered ticket files. Do not
  convert ticket creation into permission to execute them.
- **Triage:** check evidence and classify an existing issue using the local
  status vocabulary. Distinguish missing information from a proven blocker.

Read `docs/agents/issue-tracker.md`, `docs/agents/triage-labels.md` and
`docs/agents/domain.md` for the selected workflow. Follow `AGENTS.md` and
its context spine; source/test/evidence and Owner decisions outrank planning
artifacts. No background run, new Coordinator, Worker, release action or
external publication follows from using this skill.
