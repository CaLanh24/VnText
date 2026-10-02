"""Generic, bounded discovery for Addressables bundle/catalog pairs.

The legacy Addressables writer is intentionally kept unchanged because its
binary extra-data format is a frozen compatibility seam.  This module only
decides whether a patched Unity bundle belongs to a nearby ``catalog.json``
and delegates the actual catalog rewrite to that existing writer.

Discovery is deliberately conservative: a path is treated as an Addressables
bundle only when it is below an existing catalog directory (or matches the
historical ``StreamingAssets/aa`` convention).  A random ``.bundle`` file is
therefore not silently promoted to the catalog patch route.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from vntext.addressables import (
    is_addressables_bundle_rel as _legacy_is_addressables_bundle_rel,
    patch_addressables_catalog,
)


def _relative_parts(bundle_rel: str) -> tuple[str, ...]:
    normalized = str(bundle_rel or "").replace("\\", "/").strip("/")
    return tuple(PurePosixPath(normalized).parts) if normalized else ()


def _safe_relative_parts(bundle_rel: str) -> tuple[str, ...]:
    parts = _relative_parts(bundle_rel)
    if any(part in {".", ".."} for part in parts):
        return ()
    return parts


def resolve_addressables_catalog_rel(game_base: Path, bundle_rel: str) -> Path | None:
    """Resolve the nearest existing catalog for a bundle path.

    Addressables builds commonly use ``StreamingAssets/aa`` but can also put
    catalogs under a project-specific or remote-content directory.  Walking
    only the bundle's ancestor directories keeps this check deterministic and
    bounded by path depth; it never scans or parses arbitrary files.
    """

    parts = _safe_relative_parts(bundle_rel)
    if len(parts) < 2:
        return None
    base = Path(game_base)
    for parent_length in range(len(parts) - 1, -1, -1):
        parent = Path(*parts[:parent_length]) if parent_length else Path()
        candidate = base / parent / "catalog.json"
        if candidate.is_file():
            return parent / "catalog.json" if parent_length else Path("catalog.json")
    return None


def is_addressables_bundle_candidate(game_base: Path, bundle_rel: str) -> bool:
    """Return whether a patched resource has a conservative catalog relation."""

    parts = _safe_relative_parts(bundle_rel)
    if not parts:
        return False
    if _legacy_is_addressables_bundle_rel(bundle_rel):
        return True
    suffix = Path(parts[-1]).suffix.casefold()
    # The frozen catalog writer matches the 32-hex filename form ending in
    # ``.bundle``.  Extensionless Unity resources stay in the analyzer/review
    # boundary until a writer with a proven catalog identity exists.
    if suffix != ".bundle":
        return False
    return resolve_addressables_catalog_rel(game_base, bundle_rel) is not None


def patch_catalogs_for_bundles_generic(
    game_base: Path,
    patched_root: Path,
    patched_bundles,
    report: list[str],
) -> None:
    """Update every catalog related to a patched bundle.

    The existing parser/writer remains the single implementation of the
    Addressables extra-data contract.  This wrapper only broadens safe path
    discovery and preserves explicit MISS/SKIP/ERROR reporting.
    """

    grouped: dict[str, list[tuple[str, Path]]] = {}
    for rel, target in patched_bundles:
        catalog_rel = resolve_addressables_catalog_rel(game_base, rel)
        if catalog_rel is None:
            report.append(f"SKIP Addressables catalog: khong tim thay catalog.json cho {rel}")
            continue
        grouped.setdefault(catalog_rel.as_posix(), []).append((str(rel), Path(target)))

    for catalog_rel_text, bundles in grouped.items():
        catalog_rel = Path(catalog_rel_text)
        source_catalog = Path(game_base) / catalog_rel
        target_catalog = Path(patched_root) / catalog_rel
        if not source_catalog.exists():
            report.append(f"MISS Addressables catalog: {catalog_rel}")
            continue
        try:
            count = patch_addressables_catalog(source_catalog, target_catalog, bundles)
            report.append(f"ADDRESSABLES catalog {catalog_rel}: updated {count} bundle CRC/size")
        except Exception as exc:
            report.append(f"ERROR Addressables catalog {catalog_rel}: {exc}")


__all__ = [
    "is_addressables_bundle_candidate",
    "patch_catalogs_for_bundles_generic",
    "resolve_addressables_catalog_rel",
]
