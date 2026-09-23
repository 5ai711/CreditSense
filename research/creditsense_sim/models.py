"""Model builders and evaluation metrics used by the experiment runner."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from .data import NUMERIC_FEATURES, SECTORS


def one_hot(df: pd.DataFrame) -> pd.DataFrame:
    out = df[NUMERIC_FEATURES].copy()
    for s in SECTORS[1:]:  # Manufacturing is the reference level
        out[f"sector_{s}"] = (df["sector"] == s).astype(float)
    return out


# ----------------------------------------------------------------------------- baselines
def fit_lr_standardized(X: pd.DataFrame, y, seed: int):
    model = make_pipeline(
        StandardScaler(),
        LogisticRegressionCV(Cs=np.logspace(-3, 2, 11), cv=5, scoring="roc_auc", max_iter=5000, random_state=seed),
    )
    return model.fit(X, y)


class WoeEncoder:
    """Quantile-binned weight-of-evidence encoding, the classic scorecard transform."""

    def __init__(self, n_bins: int = 10, smoothing: float = 0.5):
        self.n_bins, self.smoothing = n_bins, smoothing

    def fit(self, df: pd.DataFrame, y):
        y = np.asarray(y)
        self.edges_, self.woe_ = {}, {}
        tot_bad, tot_good = y.sum(), (1 - y).sum()
        for f in NUMERIC_FEATURES:
            edges = np.unique(np.quantile(df[f], np.linspace(0, 1, self.n_bins + 1)[1:-1]))
            self.edges_[f] = edges
            self.woe_[f] = self._woe(np.digitize(df[f], edges), y, len(edges) + 1, tot_bad, tot_good)
        codes = pd.Categorical(df["sector"], categories=SECTORS).codes
        self.woe_["sector"] = self._woe(codes, y, len(SECTORS), tot_bad, tot_good)
        return self

    def _woe(self, bins, y, k, tot_bad, tot_good):
        w = np.zeros(k)
        for b in range(k):
            m = bins == b
            bad = y[m].sum() + self.smoothing
            good = (1 - y[m]).sum() + self.smoothing
            w[b] = np.log((good / tot_good) / (bad / tot_bad))
        return w

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = {f: self.woe_[f][np.digitize(df[f], self.edges_[f])] for f in NUMERIC_FEATURES}
        out["sector"] = self.woe_["sector"][pd.Categorical(df["sector"], categories=SECTORS).codes]
        return pd.DataFrame(out, index=df.index)


def fit_lr_woe(df: pd.DataFrame, y, seed: int):
    enc = WoeEncoder().fit(df, y)
    lr = LogisticRegressionCV(Cs=np.logspace(-3, 2, 11), cv=5, scoring="roc_auc", max_iter=5000, random_state=seed)
    lr.fit(enc.transform(df), y)
    return enc, lr


def xgb(params: dict, spw: float, seed: int) -> XGBClassifier:
    return XGBClassifier(
        **params,
        scale_pos_weight=spw,
        tree_method="hist",
        eval_metric="auc",
        n_jobs=4,
        random_state=seed,
    )


class PlattOnMargin:
    """Affine recalibration of the XGBoost log-odds margin.

    Because the map is affine (a*m + b), SHAP values stay exactly additive on the
    calibrated log-odds scale after multiplying them by a.
    """

    def fit(self, margin, y):
        lr = LogisticRegression(C=1e6, max_iter=1000).fit(np.asarray(margin).reshape(-1, 1), y)
        self.a_, self.b_ = float(lr.coef_[0, 0]), float(lr.intercept_[0])
        return self

    def logit(self, margin):
        return self.a_ * np.asarray(margin) + self.b_

    def predict(self, margin):
        return 1.0 / (1.0 + np.exp(-self.logit(margin)))


# ----------------------------------------------------------------------------- metrics
def ks_stat(y, p) -> float:
    y = np.asarray(y)
    return float(ks_2samp(p[y == 1], p[y == 0]).statistic)


def ece(y, p, n_bins: int = 10) -> float:
    y, p = np.asarray(y), np.asarray(p)
    edges = np.quantile(p, np.linspace(0, 1, n_bins + 1))
    idx = np.clip(np.digitize(p, edges[1:-1]), 0, n_bins - 1)
    err = 0.0
    for b in range(n_bins):
        m = idx == b
        if m.any():
            err += m.mean() * abs(p[m].mean() - y[m].mean())
    return float(err)


def summary(y, p, probabilistic: bool = True) -> dict:
    out = {
        "auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "ks": ks_stat(y, p),
    }
    if probabilistic:
        out["brier"] = float(brier_score_loss(y, p))
        out["ece"] = ece(y, p)
    return out


def bootstrap_auc(y, scores: dict, n_boot: int, seed: int) -> dict:
    """Percentile CIs for each model's AUC and paired CIs for AUC differences."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    names = list(scores)
    draws = {k: [] for k in names}
    n = len(y)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        if y[idx].min() == y[idx].max():
            continue
        for k in names:
            draws[k].append(roc_auc_score(y[idx], scores[k][idx]))
    draws = {k: np.array(v) for k, v in draws.items()}
    ci = {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] for k, v in draws.items()}
    return {"ci": ci, "draws": draws}


def bad_rate_at_approval(y, p, approval_rate: float) -> float:
    """Observed default rate among the lowest-risk `approval_rate` share of applicants."""
    y, p = np.asarray(y), np.asarray(p)
    k = int(round(approval_rate * len(y)))
    order = np.argsort(p, kind="stable")
    return float(y[order[:k]].mean())
