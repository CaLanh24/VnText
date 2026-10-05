# -*- coding: utf-8 -*-
"""Copy Release Output package into RELEASE_RUN (read-only source)."""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from work_paths import assert_artifact_under_work, new_scope_id, register_artifact

WORK_DEFAULT = Path(__file__).resolve().parents[2] / "RELEASE_RUN" / "vh_parity" / "work_package"

COPY_NAMES = (
    "translation.csv",
    "review_only.csv",
    "manifest.json",
    "extract_report.txt",
    "import_report.txt",
    "stats_snapshot.json",
    "translate_status.json",
)


def mirror(
    src: Path,
    dest: Path,
    *,
    scope_id: str | None = None,
    run_id: str | None = None,
) -> list[str]:
    src = src.expanduser().resolve()
    dest = assert_artifact_under_work(dest.expanduser().resolve(), "Release mirror destination")
    if not src.is_dir():
        raise RuntimeError(f"Release mirror source is not a directory: {src}")
    scope_id = scope_id or new_scope_id("release-mirror")
    run_id = run_id or scope_id
    register_artifact(
        artifact_id=f"release-mirror:{scope_id}",
        path=dest,
        kind="release_mirror",
        created_by="mirror_release_package.py",
        owner="mirror_release_package.py",
        purpose="disposable Release package mirror for parity/regression tests",
        lifecycle="DISPOSABLE",
        scope_id=scope_id,
        run_id=run_id,
    )
    dest.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in COPY_NAMES:
        s = src / name
        if s.is_file():
            shutil.copy2(s, dest / name)
            copied.append(name)
    for extra in src.glob("*.json"):
        if extra.name not in {n for n in COPY_NAMES}:
            d = dest / extra.name
            if not d.is_file():
                shutil.copy2(extra, d)
                copied.append(extra.name)
    return copied


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, default=None)
    ap.add_argument("--dest", type=Path, default=WORK_DEFAULT)
    args = ap.parse_args()
    source_value = args.src or os.environ.get("VNTEXT_RELEASE_PACKAGE")
    if not source_value:
        raise SystemExit("set --src or VNTEXT_RELEASE_PACKAGE to the external Release package")
    source = Path(source_value).expanduser()
    if not (source / "translation.csv").is_file():
        raise SystemExit(f"missing translation.csv under {source}")
    files = mirror(source, args.dest)
    print(f"mirrored {len(files)} files -> {args.dest}")
    for f in files:
        print(f"  {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
