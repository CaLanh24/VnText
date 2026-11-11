#!/bin/sh
set -e
python "$(dirname "$0")/../../../release/verify_skill.py" >/dev/null
exec "$HOME/.codex/skills/impeccable/scripts/impeccable" hook
