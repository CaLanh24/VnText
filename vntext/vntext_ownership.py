"""Which game files are VNText's own installed patch (per the game-side ownership receipt), so a new patch can be built on top of them.

The installer records, in ``<game>/.vntext/ownership.json``, every path a VNText patch wrote and the exact bytes of each layer.  A file whose
current bytes equal the top layer's ``installed_sha256`` is ours, untouched: building patch B over an installed patch A must treat it as the slot
B replaces, not as somebody else's translation.  A file edited after installation, or a VNText overlay without a receipt, is NOT returned, so it
stays protected exactly as before.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

RECEIPT = Path(".vntext") / "ownership.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def owned_installed_files(root: str | Path) -> set[Path]:
    """Resolved paths of game files that the receipt proves are an unmodified VNText patch layer."""
    root = Path(root)
    receipt = root / RECEIPT
    if not receipt.is_file():
        return set()
    try:
        data = json.loads(receipt.read_text(encoding="utf-8"))
        paths = data.get("paths") or {}
    except (OSError, ValueError, AttributeError):
        return set()
    owned: set[Path] = set()
    base = root.resolve()
    for relative, entry in paths.items() if isinstance(paths, dict) else ():
        if not isinstance(entry, dict) or entry.get("kind", "file") != "file":
            continue
        layers = entry.get("layers") or []
        if not layers or not isinstance(layers[-1], dict):
            continue
        expected = str(layers[-1].get("installed_sha256") or "").lower()
        target = (root / str(relative)).resolve()
        if base not in target.parents or not expected or not target.is_file() or target.is_symlink():
            continue
        try:
            if _sha256(target) == expected:
                owned.add(target)
        except OSError:
            continue
    return owned
