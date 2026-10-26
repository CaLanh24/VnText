"""Exact families of stale repo-owned ``.dotnet\\tools`` PATH entries, and a process-only sanitiser for child environments.

Background: before the explicit ``DOTNET_ADD_GLOBAL_TOOLS_TO_PATH=0`` guard, first use of a fresh ``DOTNET_CLI_HOME`` appended
``<home>\\.dotnet\\tools`` to the persistent User PATH.  The retained entries are inherited by every new process, which inflates
every child environment.  This module recognises ONLY the temporary homes this repository creates:

  family A  ``<repo>\\TEST_RUN\\wpf_workflow_<32 hex>\\runtime\\dotnet``
  family B  ``<repo>\\TEST_RUN\\wpf_workflow_<32 hex>\\update-version-fixtures\\(baseline|candidate)\\runtime\\dotnet``
  family C  ``<repo>\\RELEASE_RUN\\candidate-<version>\\<scope>\\_dotnet\\cli_home``

each followed by ``\\.dotnet\\tools`` (optional trailing backslash).  Nothing else matches: not ``.dev-env``, not another
repository, not ``%USERPROFILE%\\.dotnet\\tools``, not lookalike prefixes.

Pure functions, standard library only; ``sanitize_env_path`` changes a COPY of a child environment (process-only) and never
touches the registry.
"""
from __future__ import annotations

import ntpath
import re
from pathlib import Path

_TAIL = r"\\\.dotnet\\tools\\?"
_FAMILIES = (
    r"test_run\\wpf_workflow_[0-9a-f]{32}\\runtime\\dotnet",
    r"test_run\\wpf_workflow_[0-9a-f]{32}\\update-version-fixtures\\(?:baseline|candidate)\\runtime\\dotnet",
    r"release_run\\candidate-[0-9]+(?:\.[0-9]+)*\\[a-z0-9][a-z0-9_.-]*\\_dotnet\\cli_home",
)


def _norm(value: str) -> str:
    return ntpath.normcase(value.replace("/", "\\"))


def stale_pattern(repo_root: Path | str) -> re.Pattern[str]:
    """Compiled pattern (matched against a normalised, lower-cased entry) of the exact stale families under ``repo_root``."""

    root = re.escape(_norm(str(repo_root)).rstrip("\\"))
    return re.compile(rf"^{root}\\(?:{'|'.join(_FAMILIES)}){_TAIL}$")


def is_stale_entry(entry: str, repo_root: Path | str) -> bool:
    return bool(entry) and stale_pattern(repo_root).match(_norm(entry)) is not None


def sanitize_path_value(value: str, repo_root: Path | str) -> tuple[str, list[str]]:
    """Return (value without the stale-family entries, removed entries).  All other items keep exact text and order."""

    pattern = stale_pattern(repo_root)
    kept, removed = [], []
    for item in value.split(";"):
        (removed if item and pattern.match(_norm(item)) else kept).append(item)
    return ";".join(kept), removed


def sanitize_env_path(env: dict[str, str], repo_root: Path | str) -> list[str]:
    """Process-only: drop stale-family entries from ``env``'s PATH (case-insensitive key).  Returns what was removed."""

    key = next((k for k in env if k.upper() == "PATH"), None)
    if key is None:
        return []
    new_value, removed = sanitize_path_value(env[key], repo_root)
    if removed:
        env[key] = new_value
    return removed
