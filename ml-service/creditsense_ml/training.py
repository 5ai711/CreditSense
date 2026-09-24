"""Model training, calibration and evaluation.

Two model families are trained on the same split and scored with the same metrics:

* the primary model, an XGBoost classifier with class weighting and Optuna-tuned
  hyperparameters, recalibrated with Platt scaling on its margin, and
* a baseline weight-of-evidence (WOE) logistic scorecard, the industry-standard
  interpretable score, so the ensemble's value-add is measured rather than assumed.

Platt scaling is affine on the log-odds margin, so a SHAP decomposition of the
margin stays exactly additive on the calibrated scale after multiplying by `a`.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import optuna
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.metrics import average_precision_score, brier_score_loss, confusion_matrix, roc_auc_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from xgboost import XGBClassifier

from .features import NUMERIC_NAMES, SECTORS, to_model_matrix
from .generator import LABEL

log = logging.getLogger(__name__)

# Probability-of-default cut-offs for the risk bands shown to users.
BAND_LOW, BAND_HIGH = 0.05, 0.20
OPERATING_THRESHOLD = BAND_HIGH  # applications at or above this PD are recommended for rejection

DEFAULT_PARAMS = {
    "n_estimators": 600,
    "learning_rate": 0.028,
    "max_depth": 2,
    "min_child_weight": 1.7,
    "subsample": 0.73,
    "colsample_bytree": 0.97,
    "reg_lambda": 1.3,
    "reg_alpha": 2.0,
    "gamma": 2.1,
}


def risk_band(pd_: float) -> str:
    return "LOW" if pd_ < BAND_LOW else ("MEDIUM" if pd_ < BAND_HIGH else "HIGH")


# ----------------------------------------------------------------------------- baseline
class WoeScorecard:
    """Quantile-binned WOE encoding followed by an L2 logistic regression."""

    def __init__(self, n_bins: int = 10, smoothing: float = 0.5, seed: int = 42):
        self.n_bins, self.smoothing, self.seed = n_bins, smoothing, seed

    def _woe(self, bins, y, k, bad, good):
        out = np.zeros(k)
        for b in range(k):
            m = bins == b
            out[b] = np.log(((1 - y[m]).sum() + self.smoothing) / good / ((y[m].sum() + self.smoothing) / bad))
        return out

    def fit(self, df: pd.DataFrame, y) -> "WoeScorecard":
        y = np.asarray(y)
        bad, good = y.sum(), (1 - y).sum()
        self.edges_, self.woe_ = {}, {}
        for f in NUMERIC_NAMES:
            edges = np.unique(np.quantile(df[f], np.linspace(0, 1, self.n_bins + 1)[1:-1]))
            self.edges_[f] = edges
            self.woe_[f] = self._woe(np.digitize(df[f], edges), y, len(edges) + 1, bad, good)
        codes = pd.Categorical(df["sector"], categories=SECTORS).codes
        self.woe_["sector"] = self._woe(codes, y, len(SECTORS), bad, good)
        self.lr_ = LogisticRegressionCV(Cs=np.logspace(-3, 2, 11), cv=5, scoring="roc_auc", max_iter=5000,
                                        l1_ratios=(0,), use_legacy_attributes=False,
                                        random_state=self.seed)
        self.lr_.fit(self.transform(df), y)
        return self

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        cols = [self.woe_[f][np.digitize(df[f], self.edges_[f])] for f in NUMERIC_NAMES]
        cols.append(self.woe_["sector"][pd.Categorical(df["sector"], categories=SECTORS).codes])
        return np.column_stack(cols)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        return self.lr_.predict_proba(self.transform(df))[:, 1]


# ----------------------------------------------------------------------------- primary model
@dataclass
class CalibratedXGB:
    model: XGBClassifier
    a: float
    b: float

    def margin(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict(X, output_margin=True).astype(np.float64)

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        z = self.a * self.margin(to_model_matrix(df)) + self.b
        return 1.0 / (1.0 + np.exp(-z))


def make_xgb(params: dict, spw: float, seed: int) -> XGBClassifier:
    return XGBClassifier(**params, scale_pos_weight=spw, tree_method="hist", eval_metric="auc",
                         n_jobs=4, random_state=seed)


def tune(X: pd.DataFrame, y: np.ndarray, spw: float, n_trials: int, seed: int, folds: int = 3) -> tuple[dict, float]:
    """Optuna TPE search maximising cross-validated AUC."""
    splits = list(StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed).split(X, y))

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 100, 900, step=50),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 2, 7),
            "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 30.0, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 20.0, log=True),
            "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
            "gamma": trial.suggest_float("gamma", 0.0, 5.0),
        }
        scores = []
        for tr, va in splits:
            m = make_xgb(params, spw, seed).fit(X.iloc[tr], y[tr])
            scores.append(roc_auc_score(y[va], m.predict_proba(X.iloc[va])[:, 1]))
        return float(np.mean(scores))

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=n_trials)
    return study.best_params, float(study.best_value)


def fit_calibrated_xgb(df_fit: pd.DataFrame, y_fit, df_cal: pd.DataFrame, y_cal, params: dict, seed: int) -> CalibratedXGB:
    y_fit = np.asarray(y_fit)
    spw = float((y_fit == 0).sum() / max((y_fit == 1).sum(), 1))
    model = make_xgb(params, spw, seed).fit(to_model_matrix(df_fit), y_fit)
    margin = model.predict(to_model_matrix(df_cal), output_margin=True).astype(np.float64)
    platt = LogisticRegression(C=1e6, max_iter=1000).fit(margin.reshape(-1, 1), np.asarray(y_cal))
    return CalibratedXGB(model, float(platt.coef_[0, 0]), float(platt.intercept_[0]))


# ----------------------------------------------------------------------------- metrics
def evaluate(y, p) -> dict:
    y, p = np.asarray(y), np.asarray(p, dtype=float)
    edges = np.quantile(p, np.linspace(0, 1, 11))
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, 9)
    curve = [
        {"mean_predicted": float(p[idx == b].mean()), "observed_rate": float(y[idx == b].mean()), "count": int((idx == b).sum())}
        for b in range(10) if (idx == b).any()
    ]
    ece = sum(c["count"] * abs(c["mean_predicted"] - c["observed_rate"]) for c in curve) / len(y)
    tn, fp, fn, tp = confusion_matrix(y, (p >= OPERATING_THRESHOLD).astype(int), labels=[0, 1]).ravel()
    return {
        "auc_roc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "ks": float(ks_2samp(p[y == 1], p[y == 0]).statistic),
        "brier": float(brier_score_loss(y, p)),
        "ece": float(ece),
        "calibration_curve": curve,
        "confusion_matrix": {"threshold": OPERATING_THRESHOLD, "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "n": int(len(y)),
        "default_rate": float(y.mean()),
    }


@dataclass
class TrainingResult:
    primary: CalibratedXGB
    baseline: WoeScorecard
    params: dict
    metrics: dict
    baseline_metrics: dict
    cv_auc: float | None
    training_rows: int
    notes: dict = field(default_factory=dict)


def train(data: pd.DataFrame, seed: int = 42, n_trials: int = 0, params: dict | None = None) -> TrainingResult:
    """Train and evaluate both models on a stratified 60/20/20 split of `data`.

    With `n_trials > 0` hyperparameters are tuned on the training part; otherwise
    `params` (or the defaults found by an earlier search) are reused.
    """
    y = data[LABEL].to_numpy()
    idx = np.arange(len(data))
    tr, rest = train_test_split(idx, test_size=0.4, stratify=y, random_state=seed)
    va, te = train_test_split(rest, test_size=0.5, stratify=y[rest], random_state=seed)
    d_tr, d_va, d_te = data.iloc[tr], data.iloc[va], data.iloc[te]

    cv_auc = None
    params = dict(params or DEFAULT_PARAMS)
    if n_trials > 0:
        spw = float((y[tr] == 0).sum() / (y[tr] == 1).sum())
        params, cv_auc = tune(to_model_matrix(d_tr), y[tr], spw, n_trials, seed)
        log.info("tuned XGBoost: cv auc %.4f params %s", cv_auc, params)

    primary = fit_calibrated_xgb(d_tr, y[tr], d_va, y[va], params, seed)
    baseline = WoeScorecard(seed=seed).fit(d_tr, y[tr])
    return TrainingResult(
        primary=primary,
        baseline=baseline,
        params=params,
        metrics=evaluate(y[te], primary.predict_proba(d_te)),
        baseline_metrics=evaluate(y[te], baseline.predict_proba(d_te)),
        cv_auc=cv_auc,
        training_rows=int(len(tr)),
        notes={"split": "60/20/20 stratified", "calibration": "Platt on XGBoost margin (validation split)"},
    )
