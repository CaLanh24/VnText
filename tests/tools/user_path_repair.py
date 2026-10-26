"""One-time, narrowly scoped repair of the persistent USER PATH polluted by repo-owned temporary .NET CLI homes.

Owner exception (2026-10-27, see CONTRACTS.md).  Before the explicit guard (``DOTNET_ADD_GLOBAL_TOOLS_TO_PATH=0``), first use of a
fresh ``DOTNET_CLI_HOME`` appended ``<home>\\.dotnet\\tools`` to the persistent User PATH.  This tool removes ONLY entries that

  * belong to the exact families in ``tests/lib/path_hygiene.py`` (the temporary homes this repository creates under its
    ``TEST_RUN``/``RELEASE_RUN``; never ``.dev-env``, another repository, a lookalike prefix or ``%USERPROFILE%\\.dotnet\\tools``), and
  * whose directory no longer exists.

Every other item keeps its exact text, order and empty items; the registry kind is preserved.  Only HKCU is ever opened, and
the Machine PATH is never touched.  Default is a dry run.

Honest limits: the Windows registry has NO atomic compare-and-set.  ``apply`` therefore (1) compares the SHA-256 of the raw value
with the one the reviewer saw, (2) creates the backup exclusively, (3) re-reads the raw value AND kind immediately before the
write and refuses if anything differs, then (4) writes once and re-reads.  That narrows the race window; it does not remove it.
If the read-back differs from what was written, the tool writes NOTHING more (it never overwrites a value it did not write)
and reports; undoing is a separate explicit ``--restore`` that only acts while the current value is still exactly the one this
tool wrote.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Callable, Protocol

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO_ROOT / "tests" / "lib")]
import path_hygiene  # noqa: E402


class PathStore(Protocol):
    def read(self) -> tuple[str, int]: ...
    def write(self, value: str, kind: int) -> None: ...


SUPPORTED_KINDS = (1, 2)  # REG_SZ, REG_EXPAND_SZ


def check_raw(value: object, kind: object) -> tuple[str, int]:
    """Only a raw ``str`` value of REG_SZ/REG_EXPAND_SZ is ever planned from or written; anything else is refused."""

    if not isinstance(value, str) or isinstance(kind, bool) or kind not in SUPPORTED_KINDS:
        raise RuntimeError(f"unsupported User PATH registry value (type={type(value).__name__}, kind={kind!r}); nothing written")
    return value, kind


class UserRegistryPath:
    """The persistent USER PATH (HKCU\\Environment).  There is deliberately no Machine accessor in this module."""

    def read(self) -> tuple[str, int]:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, kind = winreg.QueryValueEx(key, "Path")
        return check_raw(value, kind)

    def write(self, value: str, kind: int) -> None:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "Path", 0, kind, value)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def plan(
    user_path: str,
    repo_root: Path | str = REPO_ROOT,
    exists: Callable[[str], bool] = os.path.exists,
) -> dict:
    """Pure planning: which items are removed, which stay and why.  Never touches the registry."""

    items = user_path.split(";")
    removed: list[dict] = []
    kept_dotnet: list[dict] = []
    keep: list[str] = []
    for index, item in enumerate(items):
        if path_hygiene.is_stale_entry(item, repo_root):
            if exists(item):
                keep.append(item)
                kept_dotnet.append({"index": index, "entry": item, "reason": "directory still exists"})
            else:
                removed.append({"index": index, "entry": item})
            continue
        keep.append(item)
        if item.lower().rstrip("\\/").endswith(r".dotnet\tools"):
            kept_dotnet.append({"index": index, "entry": item, "reason": "not in an exact stale family"})
    new_value = ";".join(keep)
    # Proof: the result is the original with exactly the removed items taken out, order and text untouched.
    removed_indexes = {r["index"] for r in removed}
    assert [i for n, i in enumerate(items) if n not in removed_indexes] == keep
    return {
        "before": {"chars": len(user_path), "entries": len([i for i in items if i]), "sha256": sha256_text(user_path)},
        "after": {"chars": len(new_value), "entries": len([i for i in keep if i]), "sha256": sha256_text(new_value)},
        "removed": removed,
        "kept_dotnet_tools": kept_dotnet,
        "new_value": new_value,
    }


def apply(
    store: PathStore,
    *,
    expected_sha256: str,
    backup_path: Path,
    repo_root: Path | str = REPO_ROOT,
    exists: Callable[[str], bool] = os.path.exists,
) -> dict:
    """User PATH only.  Not atomic: see the module docstring."""

    value, kind = check_raw(*store.read())
    if sha256_text(value) != expected_sha256.lower():
        raise RuntimeError("user PATH changed since the dry run (SHA-256 mismatch); nothing written")
    result = plan(value, repo_root, exists)
    if not result["removed"]:
        raise RuntimeError("nothing to remove; nothing written")
    backup_path = Path(backup_path)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "scope": "user", "registry_kind": kind, "sha256": sha256_text(value), "value": value,
        "planned_sha256": result["after"]["sha256"],
    }
    try:
        with open(backup_path, "x", encoding="utf-8") as handle:        # exclusive create: never overwrite a backup
            json.dump(record, handle, indent=2)
    except FileExistsError as error:
        raise RuntimeError(f"refusing to overwrite an existing backup: {backup_path}") from error
    # Re-read raw value AND kind immediately before the write; a foreign change since the first read aborts without writing.
    again_value, again_kind = check_raw(*store.read())
    if (again_value, again_kind) != (value, kind):
        raise RuntimeError("user PATH (value or kind) changed between planning and the write; nothing written")
    store.write(result["new_value"], kind)
    after_value, after_kind = check_raw(*store.read())
    if (after_value, after_kind) != (result["new_value"], kind):
        # Never write again: whatever is there now was not written by this tool and must not be overwritten.
        raise RuntimeError(
            "read-back differs from the value this tool wrote (possible foreign change); nothing further written. "
            f"observed sha256={sha256_text(after_value)} kind={after_kind}; backup kept at {backup_path}"
        )
    return {k: v for k, v in result.items() if k != "new_value"} | {"registry_kind": kind, "backup": str(backup_path)}


def restore(store: PathStore, *, backup_path: Path) -> dict:
    """Undo ``apply`` from its backup, but only while the current value is still exactly the one ``apply`` wrote."""

    record = json.loads(Path(backup_path).read_text(encoding="utf-8"))
    original_value, original_kind = check_raw(record["value"], record["registry_kind"])
    current, kind = check_raw(*store.read())
    # BOTH the value hash and the registry kind must still be exactly what apply left; otherwise a foreign change happened.
    if sha256_text(current) != record["planned_sha256"] or kind != original_kind:
        raise RuntimeError("user PATH (value or kind) is not what this tool wrote (foreign change); nothing restored")
    store.write(original_value, original_kind)
    back, back_kind = check_raw(*store.read())
    if (back, back_kind) != (record["value"], record["registry_kind"]):
        raise RuntimeError("read-back after restore differs; nothing further written")
    return {"restored_sha256": sha256_text(back), "registry_kind": back_kind}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true", help="write the repair (default is a dry run)")
    group.add_argument("--restore", action="store_true", help="undo --apply from --backup (only if the value is still the one written)")
    parser.add_argument("--expect-sha256", default="", help="exact SHA-256 of the current raw User PATH (required with --apply)")
    parser.add_argument("--backup", default="", help="backup file (created with --apply, read with --restore)")
    parser.add_argument("--output", default="", help="write the report here")
    args = parser.parse_args(argv)
    store = UserRegistryPath()
    if args.apply:
        if not args.expect_sha256 or not args.backup:
            parser.error("--apply requires --expect-sha256 and --backup")
        report = apply(store, expected_sha256=args.expect_sha256, backup_path=Path(args.backup)) | {"mode": "applied"}
    elif args.restore:
        if not args.backup:
            parser.error("--restore requires --backup")
        report = restore(store, backup_path=Path(args.backup)) | {"mode": "restored"}
    else:
        value, kind = check_raw(*store.read())
        report = {k: v for k, v in plan(value).items() if k != "new_value"} | {"registry_kind": kind, "mode": "dry_run"}
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
