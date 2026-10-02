from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MtPaths:
    package_dir: Path
    mt_dir: Path
    frozen: Path
    state: Path
    failures: Path
    whitelist: Path
    inflight: Path
    policy: Path
    qa_report: Path
    backup_dir: Path

    @property
    def rolling_backup(self) -> Path:
        return self.backup_dir / "translation.csv.prev"


def paths_for_csv(csv_path: str | Path) -> MtPaths:
    csv_file = Path(csv_path).resolve()
    package_dir = csv_file.parent
    mt_dir = package_dir / ".mt"
    return MtPaths(
        package_dir=package_dir,
        mt_dir=mt_dir,
        frozen=mt_dir / "frozen.json",
        state=mt_dir / "state.json",
        failures=mt_dir / "failures.json",
        whitelist=mt_dir / "whitelist.json",
        inflight=mt_dir / "inflight.json",
        policy=mt_dir / "policy_skipped.json",
        qa_report=mt_dir / "qa_report.txt",
        backup_dir=mt_dir / "backup",
    )


def ensure_mt_dir(paths: MtPaths) -> None:
    paths.mt_dir.mkdir(parents=True, exist_ok=True)
    paths.backup_dir.mkdir(parents=True, exist_ok=True)
