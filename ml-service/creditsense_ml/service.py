"""Model lifecycle: bootstrap, scoring with explanations, feedback and retraining."""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import shap
from sklearn.metrics import roc_auc_score

from .features import FEATURE_NAMES, NUMERIC_NAMES, group_sector, to_model_matrix
from .generator import LABEL, generate, simulate_outcome
from .registry import ModelRecord, Registry, utcnow
from .training import TrainingResult, risk_band, train

log = logging.getLogger(__name__)

ADDITIVITY_TOLERANCE = 1e-4  # max |base + sum(contributions) - logit(pd)| before a score is withheld


def data_fingerprint(data: pd.DataFrame) -> str:
    """SHA-256 of the training pool in a canonical form, so each model version names the exact data it saw."""
    canonical = data[FEATURE_NAMES + [LABEL]].to_csv(index=False, float_format="%.10g", lineterminator="\n")
    return hashlib.sha256(canonical.encode()).hexdigest()


class ExplanationUnavailable(RuntimeError):
    """Raised when a prediction cannot be accompanied by a valid explanation."""


class RetrainInProgress(RuntimeError):
    """Raised when a retrain is requested while another one is still running."""


@dataclass
class Contribution:
    feature: str
    feature_value: float | str
    shap_contribution: float


@dataclass
class Scored:
    probability_of_default: float
    risk_band: str
    model_version: str
    base_value: float
    contributions: list[Contribution]


class ModelService:
    """Owns the serving model, its cached explainer and the training data."""

    def __init__(self, data_dir: Path, bootstrap_trials: int = 25, retrain_trials: int = 0,
                 n_train: int = 20_000, n_holdout: int = 4_000, seed: int = 42):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.training_path = self.data_dir / "training.csv"
        self.holdout_path = self.data_dir / "holdout.csv"
        self.feedback_path = self.data_dir / "feedback.csv"
        self.bootstrap_trials, self.retrain_trials = bootstrap_trials, retrain_trials
        self.n_train, self.n_holdout, self.seed = n_train, n_holdout, seed
        self.registry = Registry(self.data_dir)
        # _lock guards the serving triple and the feedback file and is only ever held briefly, so
        # scoring never waits for training. _retrain_lock serialises retrains (and registry writes).
        self._lock = threading.RLock()
        self._retrain_lock = threading.Lock()
        self._model: TrainingResult | None = None
        self._explainer: shap.TreeExplainer | None = None
        self._version: str | None = None

    # ------------------------------------------------------------------ startup
    def start(self) -> None:
        """Load the serving model, bootstrapping data and a first champion if needed."""
        with self._lock:
            if not self.training_path.exists():
                generate(self.n_train, self.seed).to_csv(self.training_path, index=False)
                # an independent sample that no model ever trains on
                generate(self.n_holdout, self.seed + 1).to_csv(self.holdout_path, index=False)
            if self.registry.serving_version is None:
                self._bootstrap()
            self._activate(self.registry.serving_version)

    def _bootstrap(self) -> None:
        log.info("no serving model: training the first champion (%d tuning trials)", self.bootstrap_trials)
        data = pd.read_csv(self.training_path)
        fingerprint = data_fingerprint(data)
        result = train(data, seed=self.seed, n_trials=self.bootstrap_trials)
        version = self.registry.next_version()
        holdout_auc = self._holdout_auc(result, self._holdout())
        self.registry.add(result, ModelRecord(
            version=version, created_at=utcnow(), status="champion", params=result.params,
            metrics=result.metrics, baseline_metrics=result.baseline_metrics, cv_auc=result.cv_auc,
            training_rows=result.training_rows, feedback_rows=0, holdout_auc=holdout_auc, notes=result.notes,
            data_sha256=fingerprint,
        ))
        self.registry.promote(version)
        self.registry.log_comparison({
            "event": "bootstrap", "champion_version": None, "challenger_version": version,
            "champion_holdout_auc": None, "challenger_holdout_auc": holdout_auc, "promoted": True,
            "holdout_rows": int(len(self._holdout())), "feedback_rows": 0,
        })

    def _activate(self, version: str) -> None:
        model = self.registry.load(version)
        # Building the explainer is the expensive part, so it happens once per version, before the
        # swap: requests keep using the previous model until the new one is fully ready.
        explainer = shap.TreeExplainer(model.primary.model)
        with self._lock:
            self._model, self._explainer, self._version = model, explainer, version
        log.info("serving model %s", version)

    @property
    def ready(self) -> bool:
        return self._model is not None

    @property
    def version(self) -> str | None:
        return self._version

    # ------------------------------------------------------------------ scoring
    def score(self, features: dict) -> Scored:
        with self._lock:
            model, explainer, version = self._model, self._explainer, self._version
        if model is None or explainer is None:
            raise ExplanationUnavailable("model not loaded")

        row = pd.DataFrame([features])[FEATURE_NAMES]
        X = to_model_matrix(row)
        cal = model.primary
        margin = float(cal.margin(X)[0])
        logit = cal.a * margin + cal.b
        pd_ = float(1.0 / (1.0 + np.exp(-logit)))

        try:
            phi = np.asarray(explainer.shap_values(X), dtype=np.float64)[0]
            base_margin = float(np.atleast_1d(explainer.expected_value)[0])
        except Exception as exc:  # the score must never leave without its explanation
            raise ExplanationUnavailable(f"SHAP computation failed: {exc}") from exc

        grouped = group_sector(phi)
        base_value = cal.a * base_margin + cal.b
        contributions = [
            Contribution(
                feature=name,
                feature_value=(features[name] if name == "sector" else float(features[name])),
                shap_contribution=float(cal.a * grouped[name]),
            )
            for name in FEATURE_NAMES
        ]
        gap = abs(base_value + sum(c.shap_contribution for c in contributions) - logit)
        if not np.isfinite(gap) or gap > ADDITIVITY_TOLERANCE:
            raise ExplanationUnavailable(f"explanation does not add up to the score (gap {gap:.2e})")
        contributions.sort(key=lambda c: abs(c.shap_contribution), reverse=True)
        return Scored(pd_, risk_band(pd_), version, float(base_value), contributions)

    # ------------------------------------------------------------------ feedback loop
    def _feedback(self) -> pd.DataFrame:
        with self._lock:
            if self.feedback_path.exists():
                return pd.read_csv(self.feedback_path)
        return pd.DataFrame(columns=["reference_id", "recorded_at", *FEATURE_NAMES, LABEL])

    @staticmethod
    def _is_holdout(reference: str) -> bool:
        # One in five matured loans is reserved for evaluation and never used for training.
        return int(hashlib.sha256(reference.encode()).hexdigest(), 16) % 5 == 0

    def _holdout(self, fb: pd.DataFrame | None = None) -> pd.DataFrame:
        base = pd.read_csv(self.holdout_path)
        fb = self._feedback() if fb is None else fb
        if len(fb):
            fb = fb[fb["reference_id"].astype(str).map(self._is_holdout)]
            base = pd.concat([base, fb[FEATURE_NAMES + [LABEL]]], ignore_index=True)
        return base

    def simulate_outcomes(self, items: list[tuple[str, dict]]) -> list[tuple[str, int]]:
        """Draw 12-month outcomes for matured loans and append them to the feedback store."""
        if not items:
            return []
        refs = [r for r, _ in items]
        frame = pd.DataFrame([f for _, f in items])[FEATURE_NAMES]
        outcomes = simulate_outcome(frame, refs)
        with self._lock:
            fb = self._feedback()
            new = frame.copy()
            new.insert(0, "recorded_at", utcnow())
            new.insert(0, "reference_id", refs)
            new[LABEL] = outcomes
            known = set(fb["reference_id"].astype(str)) if len(fb) else set()
            new = new[~new["reference_id"].isin(known)]
            tmp = self.feedback_path.with_suffix(".csv.tmp")
            pd.concat([fb, new], ignore_index=True).to_csv(tmp, index=False)
            tmp.replace(self.feedback_path)  # readers never see a half-written file
        return list(zip(refs, outcomes.tolist()))

    def _holdout_auc(self, result: TrainingResult, holdout: pd.DataFrame) -> float:
        return float(roc_auc_score(holdout[LABEL], result.primary.predict_proba(holdout)))

    def retrain(self) -> dict:
        """Train a challenger on base data plus accumulated outcomes; promote only if it wins."""
        if not self._retrain_lock.acquire(blocking=False):
            raise RetrainInProgress("a retrain is already running")
        try:
            return self._retrain()
        finally:
            self._retrain_lock.release()

    def _retrain(self) -> dict:
        started = time.perf_counter()
        with self._lock:  # a consistent snapshot; training itself runs without the lock
            fb = self._feedback()
            champion_version, champion = self._version, self._model
        fb_train = fb[~fb["reference_id"].astype(str).map(self._is_holdout)] if len(fb) else fb
        data = pd.concat([pd.read_csv(self.training_path), fb_train[FEATURE_NAMES + [LABEL]]], ignore_index=True)
        data[NUMERIC_NAMES] = data[NUMERIC_NAMES].astype(float)
        data[LABEL] = data[LABEL].astype(int)
        fingerprint = data_fingerprint(data)
        challenger = train(data, seed=self.seed + len(self.registry.records()), n_trials=self.retrain_trials,
                           params=champion.params)
        holdout = self._holdout(fb)
        champ_auc = self._holdout_auc(champion, holdout)
        chall_auc = self._holdout_auc(challenger, holdout)
        promoted = chall_auc > champ_auc

        version = self.registry.next_version()
        self.registry.add(challenger, ModelRecord(
            version=version, created_at=utcnow(), status="challenger", params=challenger.params,
            metrics=challenger.metrics, baseline_metrics=challenger.baseline_metrics, cv_auc=challenger.cv_auc,
            training_rows=challenger.training_rows, feedback_rows=int(len(fb_train)), holdout_auc=chall_auc,
            parent_version=champion_version, notes=challenger.notes, data_sha256=fingerprint,
        ))
        if promoted:
            self.registry.promote(version)
            self._activate(version)
        else:
            self.registry.set_status(version, "rejected")
        entry = {
            "event": "retrain", "champion_version": champion_version, "challenger_version": version,
            "champion_holdout_auc": champ_auc, "challenger_holdout_auc": chall_auc, "promoted": promoted,
            "holdout_rows": int(len(holdout)), "feedback_rows": int(len(fb_train)),
            "seconds": round(time.perf_counter() - started, 2),
        }
        self.registry.log_comparison(entry)
        return {**entry, "serving_version": self._version,
                "challenger_metrics": challenger.metrics, "champion_metrics": champion.metrics}

    # ------------------------------------------------------------------ introspection
    def info(self) -> dict:
        rec = self.registry.record(self._version)
        fb = self._feedback()
        return {
            "model_version": self._version,
            "trained_at": rec["created_at"],
            "algorithm": "XGBoost (Platt-calibrated) with TreeSHAP explanations",
            "baseline": "Weight-of-evidence logistic scorecard",
            "features": FEATURE_NAMES,
            "hyperparameters": rec["params"],
            "cv_auc": rec["cv_auc"],
            "metrics": rec["metrics"],
            "baseline_metrics": rec["baseline_metrics"],
            "holdout_auc": rec["holdout_auc"],
            "training_rows": rec["training_rows"],
            "training_data_sha256": rec.get("data_sha256"),
            "feedback_rows": int(len(fb)),
            "risk_bands": {"LOW": "PD < 5%", "MEDIUM": "5% <= PD < 20%", "HIGH": "PD >= 20%"},
        }

    def history(self) -> dict:
        return {"serving_version": self._version, "comparisons": self.registry.history(),
                "models": [{k: m[k] for k in ("version", "created_at", "status", "holdout_auc", "feedback_rows",
                                               "parent_version")} | {"data_sha256": m.get("data_sha256"),
                                                                     "auc_roc": m["metrics"]["auc_roc"],
                                                                     "baseline_auc_roc": m["baseline_metrics"]["auc_roc"]}
                           for m in self.registry.records()]}
