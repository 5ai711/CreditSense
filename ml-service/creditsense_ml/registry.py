"""Versioned model registry on local disk.

Layout under the data directory:

    registry.json             index of every version, the serving pointer and the
                              champion/challenger comparison history
    models/<version>.joblib   the trained primary model, baseline and parameters

Every trained model is kept, so any past version can be inspected; exactly one
version is marked as serving at a time.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import joblib

from .training import TrainingResult


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ModelRecord:
    version: str
    created_at: str
    status: str  # champion | retired | rejected
    params: dict
    metrics: dict
    baseline_metrics: dict
    cv_auc: float | None
    training_rows: int
    feedback_rows: int
    holdout_auc: float | None = None
    parent_version: str | None = None
    notes: dict = field(default_factory=dict)


class Registry:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.models_dir = self.root / "models"
        self.index_path = self.root / "registry.json"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._index = self._read()

    # ------------------------------------------------------------------ persistence
    def _read(self) -> dict:
        if self.index_path.exists():
            return json.loads(self.index_path.read_text())
        return {"serving_version": None, "models": [], "history": []}

    def _write(self) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.root, suffix=".json")
        with os.fdopen(fd, "w") as fh:
            json.dump(self._index, fh, indent=2)
        os.chmod(tmp, 0o644)
        os.replace(tmp, self.index_path)  # atomic swap so a crash never leaves a half-written index

    # ------------------------------------------------------------------ queries
    @property
    def serving_version(self) -> str | None:
        return self._index["serving_version"]

    def records(self) -> list[dict]:
        return list(self._index["models"])

    def record(self, version: str) -> dict:
        return next(m for m in self._index["models"] if m["version"] == version)

    def history(self) -> list[dict]:
        return list(self._index["history"])

    def load(self, version: str) -> TrainingResult:
        return joblib.load(self.models_dir / f"{version}.joblib")

    # ------------------------------------------------------------------ mutations
    def next_version(self) -> str:
        n = len(self._index["models"]) + 1
        return f"v{n}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    def add(self, result: TrainingResult, record: ModelRecord) -> None:
        joblib.dump(result, self.models_dir / f"{record.version}.joblib")
        self._index["models"].append(asdict(record))
        self._write()

    def set_status(self, version: str, status: str, **extra) -> None:
        rec = self.record(version)
        rec["status"] = status
        rec.update(extra)
        self._write()

    def promote(self, version: str) -> None:
        previous = self.serving_version
        if previous and previous != version:
            self.set_status(previous, "retired")
        self.set_status(version, "champion")
        self._index["serving_version"] = version
        self._write()

    def log_comparison(self, entry: dict) -> None:
        self._index["history"].append({"at": utcnow(), **entry})
        self._write()
