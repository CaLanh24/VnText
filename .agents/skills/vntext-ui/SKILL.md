---
name: vntext-ui
description: Project adapter for the pinned shared Impeccable UI skill (WPF XAML/C# UI work in wpf_app).
---
Before UI work, run `python release/verify_skill.py` from the repository. It verifies every canonical file against `release/impeccable-pin.json` without downloading or modifying shared tools. On success read `~/.codex/skills/impeccable/SKILL.md`, expanding `~` for the current user. If absent or mismatched, continue with the existing WPF styles/tokens in `wpf_app` and report the missing prerequisite; do not install automatically. The repository hook (`ui_hook.py`) only starts Impeccable when a UI file (`wpf_app/**/*.xaml|*.cs`, `*.html`, `*.css`) is touched. Respect AGENTS scope, one UI owner and native evidence boundaries. An audit report alone does not require a product redesign.
