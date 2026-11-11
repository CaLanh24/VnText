---
name: vntext-ui
description: Project adapter for the pinned shared Impeccable UI skill.
---
Before UI work, run `python release/verify_skill.py` from the repository. It verifies every canonical file against `release/impeccable-pin.json` without downloading or modifying shared tools. On success read `~/.codex/skills/impeccable/SKILL.md`, expanding `~` for the current user. If absent or mismatched, use existing PRODUCT/DESIGN and report the missing prerequisite; do not install automatically. Respect AGENTS scope, one UI owner and native evidence boundaries. An audit report alone does not require a product redesign.
