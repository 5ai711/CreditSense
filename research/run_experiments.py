"""Reproduce every number and figure reported for the CreditSense evaluation.

    python run_experiments.py            # full run (Optuna search is cached)
    python run_experiments.py --retune   # force a fresh hyperparameter search

Outputs: results/metrics.json, results/tuning.json and results/figures/*.pdf
"""
from __future__ import annotations

import argparse
import json
import warnings
import time
from pathlib import Path

import numpy as np
import optuna
import pandas as pd
import shap
import sklearn
import xgboost
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold, train_test_split

from creditsense_sim import gstin
from creditsense_sim.data import ALL_FEATURES, SECTORS, Drift, generate, matched_intercept_shift, true_shapley
from creditsense_sim.models import (
    PlattOnMargin,
    bad_rate_at_approval,
    bootstrap_auc,
    fit_lr_standardized,
    fit_lr_woe,
    one_hot,
    summary,
    xgb,
)

warnings.filterwarnings("ignore", category=FutureWarning)

SEED = 42
N_APPLICANTS = 20_000
BANDS = (0.05, 0.20)  # PD cut-offs: Low < 5 %, Medium 5-20 %, High >= 20 %
OUT = Path(__file__).parent / "results"
FIG = OUT / "figures"


def band_of(pd_):
    return np.where(pd_ < BANDS[0], "Low", np.where(pd_ < BANDS[1], "Medium", "High"))


def group_sector(contrib: pd.DataFrame) -> pd.DataFrame:
    """Sum one-hot sector columns back into a single 'sector' attribution."""
    sec_cols = [c for c in contrib.columns if c.startswith("sector_")]
    out = contrib.drop(columns=sec_cols)
    out["sector"] = contrib[sec_cols].sum(axis=1)
    return out[ALL_FEATURES]


# ----------------------------------------------------------------------------- tuning
def tune_xgb(X, y, spw, n_trials, seed):
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    folds = list(skf.split(X, y))

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
        aucs = []
        for tr, va in folds:
            m = xgb(params, spw, seed).fit(X.iloc[tr], y[tr])
            aucs.append(roc_auc_score(y[va], m.predict_proba(X.iloc[va])[:, 1]))
        return float(np.mean(aucs))

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study.optimize(objective, n_trials=n_trials)
    return study.best_params, study.best_value, [t.value for t in study.trials]


# ----------------------------------------------------------------------------- lifecycle
def lifecycle(params, base_df, base_y, n_cycles, cohort, approve_below, seed):
    """Champion/challenger retraining under gradual drift with approved-only feedback."""

    def train(df, y):
        Xo = one_hot(df)
        tr, ca = train_test_split(np.arange(len(y)), test_size=0.2, stratify=y, random_state=seed)
        spw = (y[tr] == 0).sum() / (y[tr] == 1).sum()
        m = xgb(params, spw, seed).fit(Xo.iloc[tr], y[tr])
        cal = PlattOnMargin().fit(m.predict(Xo.iloc[ca], output_margin=True), y[ca])
        return m, cal

    def score(model, df):
        m, cal = model
        return cal.predict(m.predict(one_hot(df), output_margin=True))

    static = champion = train(base_df, base_y)
    pool_df, pool_y = base_df.copy(), base_y.copy()
    rows = []
    for t in range(1, n_cycles + 1):
        drift = Drift(
            volatility_coef=1.9 + 0.25 * t,
            sector_shock={"Hospitality": 0.15 * t, "Retail": 0.10 * t},
            digital_coef=-0.22 - 0.04 * t,
        )
        new_df, new_y, _ = generate(cohort, seed + 1000 + t, drift)
        eval_df, eval_y, _ = generate(cohort, seed + 2000 + t, drift)

        approved = score(champion, new_df) < approve_below
        pool_df = pd.concat([pool_df, new_df[approved]], ignore_index=True)
        pool_y = np.concatenate([pool_y, new_y[approved]])
        challenger = train(pool_df, pool_y)

        auc_static = roc_auc_score(eval_y, score(static, eval_df))
        auc_champ = roc_auc_score(eval_y, score(champion, eval_df))
        auc_chall = roc_auc_score(eval_y, score(challenger, eval_df))
        promoted = auc_chall > auc_champ
        s_ch, s_cp, s_st = score(challenger, eval_df), score(champion, eval_df), score(static, eval_df)
        rng = np.random.default_rng(seed + t)
        diffs, gains = [], []
        for _ in range(500):
            i = rng.integers(0, len(eval_y), len(eval_y))
            a_cp = roc_auc_score(eval_y[i], s_cp[i])
            diffs.append(roc_auc_score(eval_y[i], s_ch[i]) - a_cp)
            gains.append(a_cp - roc_auc_score(eval_y[i], s_st[i]))
        lo90 = float(np.percentile(diffs, 5))
        gain_lo90 = float(np.percentile(gains, 5))
        rows.append(
            {
                "cycle": t,
                "approved": int(approved.sum()),
                "approval_rate": float(approved.mean()),
                "observed_bad_rate_approved": float(new_y[approved].mean()),
                "cohort_default_rate": float(new_y.mean()),
                "pool_size": int(len(pool_y)),
                "auc_static": float(auc_static),
                "auc_champion": float(auc_champ),
                "auc_challenger": float(auc_chall),
                "promoted": bool(promoted),
                "delta_ci90_low": lo90,
                "significant": bool(lo90 > 0),
                "champion_vs_static_ci90_low": gain_lo90,
            }
        )
        if promoted:
            champion = challenger
    return rows


# ----------------------------------------------------------------------------- sweep
def interaction_sweep(params, kappas, seeds, n, target_rate):
    """How the GBM-vs-LR gap and explanation fidelity change with interaction strength."""
    out = []
    for k in kappas:
        shift = matched_intercept_shift(Drift(interaction_scale=k), target_rate)
        scen = Drift(interaction_scale=k, intercept_shift=shift)
        for sd in seeds:
            df, y, z = generate(n, 10_000 + sd, scen)
            idx = np.arange(n)
            tr, rest = train_test_split(idx, test_size=0.4, stratify=y, random_state=sd)
            _, te = train_test_split(rest, test_size=0.5, stratify=y[rest], random_state=sd)
            X = one_hot(df)
            spw = (y[tr] == 0).sum() / (y[tr] == 1).sum()
            lr = fit_lr_standardized(X.iloc[tr], y[tr], sd)
            enc, lw = fit_lr_woe(df.iloc[tr], y[tr], sd)
            gb = xgb(params, spw, sd).fit(X.iloc[tr], y[tr])
            truth = true_shapley(df.iloc[te], df.iloc[tr].sample(3000, random_state=sd), scen)
            sv = group_sector(pd.DataFrame(shap.TreeExplainer(gb).shap_values(X.iloc[te]), columns=X.columns))
            sc, bt = lr.named_steps["standardscaler"], lr.named_steps["logisticregressioncv"].coef_[0]
            la = group_sector(pd.DataFrame(((X.iloc[te] - sc.mean_) / sc.scale_).values * bt, columns=X.columns))

            def inst_r(att):
                return float(np.nanmean([pearsonr(att.values[i], truth.values[i])[0] for i in range(len(te))]))

            out.append(
                {
                    "kappa": k,
                    "seed": sd,
                    "default_rate": float(y.mean()),
                    "auc_oracle": float(roc_auc_score(y[te], z[te])),
                    "auc_lr_std": float(roc_auc_score(y[te], lr.predict_proba(X.iloc[te])[:, 1])),
                    "auc_lr_woe": float(roc_auc_score(y[te], lw.predict_proba(enc.transform(df.iloc[te]))[:, 1])),
                    "auc_xgb": float(roc_auc_score(y[te], gb.predict_proba(X.iloc[te])[:, 1])),
                    "fid_xgb": inst_r(sv),
                    "fid_lr": inst_r(la),
                }
            )
    return out


# ----------------------------------------------------------------------------- GSTIN
def gstin_study(n, seed):
    rng = np.random.default_rng(seed)
    valid = [gstin.random_valid(rng) for _ in range(n)]
    subs = [gstin.substitute_same_class(g, rng) for g in valid]
    trans = [t for t in (gstin.transpose_adjacent(g, rng) for g in valid) if t and t not in valid]
    fake = [gstin.fabricated(rng) for _ in range(n)]

    def accept_rate(items, fn):
        return float(np.mean([fn(g) for g in items]))

    sets = {"valid": valid, "substitution": subs, "transposition": trans, "fabricated": fake}
    return {
        k: {
            "n": len(v),
            "shape_only_accept": accept_rate(v, gstin.valid_shape),
            "full_accept": accept_rate(v, gstin.valid_full),
        }
        for k, v in sets.items()
    }


# ----------------------------------------------------------------------------- main
def main(retune: bool, n_trials: int):
    t0 = time.time()
    OUT.mkdir(exist_ok=True)
    FIG.mkdir(exist_ok=True)
    res = {
        "environment": {
            "python": __import__("platform").python_version(),
            "xgboost": xgboost.__version__,
            "shap": shap.__version__,
            "scikit_learn": sklearn.__version__,
            "optuna": optuna.__version__,
        }
    }

    # ---- data
    df, y, z = generate(N_APPLICANTS, SEED)
    idx = np.arange(len(y))
    tr, rest = train_test_split(idx, test_size=0.4, stratify=y, random_state=SEED)
    va, te = train_test_split(rest, test_size=0.5, stratify=y[rest], random_state=SEED)
    X = one_hot(df)
    res["data"] = {
        "n": int(len(y)),
        "default_rate": float(y.mean()),
        "n_train": int(len(tr)),
        "n_valid": int(len(va)),
        "n_test": int(len(te)),
        "oracle_auc_test": float(roc_auc_score(y[te], z[te])),
        "sector_share": {s: float((df["sector"] == s).mean()) for s in SECTORS},
    }
    spw = float((y[tr] == 0).sum() / (y[tr] == 1).sum())

    # ---- baselines
    lr_std = fit_lr_standardized(X.iloc[tr], y[tr], SEED)
    woe_enc, lr_woe = fit_lr_woe(df.iloc[tr], y[tr], SEED)
    p = {}
    p["lr_std"] = lr_std.predict_proba(X.iloc[te])[:, 1]
    p["lr_woe"] = lr_woe.predict_proba(woe_enc.transform(df.iloc[te]))[:, 1]

    # ---- XGBoost with library defaults (only imbalance handling set)
    xgb_def = xgb({}, spw, SEED).fit(X.iloc[tr], y[tr])
    p["xgb_default"] = xgb_def.predict_proba(X.iloc[te])[:, 1]

    # ---- tuned XGBoost
    tuning_path = OUT / "tuning.json"
    if retune or not tuning_path.exists():
        t1 = time.time()
        best, best_cv, history = tune_xgb(X.iloc[tr], y[tr], spw, n_trials, SEED)
        tuning_path.write_text(
            json.dumps(
                {"best_params": best, "best_cv_auc": best_cv, "history": history, "seconds": time.time() - t1},
                indent=2,
            )
        )
    tuning = json.loads(tuning_path.read_text())
    params = tuning["best_params"]
    res["tuning"] = {k: tuning[k] for k in ("best_params", "best_cv_auc", "seconds")}
    res["tuning"]["n_trials"] = len(tuning["history"])
    res["tuning"]["scale_pos_weight"] = spw

    champ = xgb(params, spw, SEED).fit(X.iloc[tr], y[tr])
    m_va = champ.predict(X.iloc[va], output_margin=True)
    m_te = champ.predict(X.iloc[te], output_margin=True)
    platt = PlattOnMargin().fit(m_va, y[va])
    p["xgb_tuned_raw"] = champ.predict_proba(X.iloc[te])[:, 1]
    p["creditsense"] = platt.predict(m_te)
    res["calibration_map"] = {"a": platt.a_, "b": platt.b_}

    res["test_metrics"] = {k: summary(y[te], v) for k, v in p.items()}
    boot = bootstrap_auc(y[te], p, n_boot=2000, seed=SEED)
    res["auc_ci95"] = boot["ci"]
    d = boot["draws"]
    res["delta_auc"] = {}
    for base in ("lr_std", "lr_woe", "xgb_default"):
        diff = d["creditsense"] - d[base]
        res["delta_auc"][base] = {
            "mean": float(diff.mean()),
            "ci95": [float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5))],
            "share_leq_zero": float((diff <= 0).mean()),
        }

    # ---- business view: bad rate at fixed approval rates
    res["bad_rate_at_approval"] = {
        f"{int(a*100)}": {k: bad_rate_at_approval(y[te], v, a) for k, v in p.items()} for a in (0.6, 0.7, 0.8)
    }

    # ---- operating threshold (Youden J chosen on validation)
    pv = platt.predict(m_va)
    fpr, tpr, thr = roc_curve(y[va], pv)
    t_star = float(thr[np.argmax(tpr - fpr)])
    tn, fp, fn, tp = confusion_matrix(y[te], (p["creditsense"] >= t_star).astype(int)).ravel()
    res["operating_point"] = {
        "threshold": t_star,
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        "recall": tp / (tp + fn), "specificity": tn / (tn + fp),
        "precision": tp / (tp + fp), "accuracy": (tp + tn) / (tp + tn + fp + fn),
    }

    # ---- risk bands on test
    b = band_of(p["creditsense"])
    res["risk_bands"] = {
        name: {
            "share": float((b == name).mean()),
            "n": int((b == name).sum()),
            "mean_pd": float(p["creditsense"][b == name].mean()),
            "observed_default_rate": float(y[te][b == name].mean()),
        }
        for name in ("Low", "Medium", "High")
    }

    # ---- SHAP
    explainer = shap.TreeExplainer(champ)
    sv = explainer.shap_values(X.iloc[te])
    base_margin = float(np.atleast_1d(explainer.expected_value)[0])
    res["shap_additivity_max_abs_err"] = float(np.abs(sv.sum(1) + base_margin - m_te).max())
    shap_df = group_sector(pd.DataFrame(sv, columns=X.columns, index=X.index[te]))

    background = df.iloc[tr].sample(4000, random_state=SEED)
    truth = true_shapley(df.iloc[te], background)
    # linear model's exact attribution: beta_j * (x_j - mean_j) on the standardized scale
    scaler = lr_std.named_steps["standardscaler"]
    beta = lr_std.named_steps["logisticregressioncv"].coef_[0]
    lr_contrib = group_sector(
        pd.DataFrame(((X.iloc[te] - scaler.mean_) / scaler.scale_) * beta, columns=X.columns, index=X.index[te])
    )

    def fidelity(att):
        g_model = att.abs().mean()
        g_true = truth.abs().mean()
        per = [pearsonr(att.values[i], truth.values[i])[0] for i in range(len(att))]
        top1 = np.mean(att.abs().values.argmax(1) == truth.abs().values.argmax(1))
        k = 3
        a3 = np.argsort(-att.abs().values, 1)[:, :k]
        t3 = np.argsort(-truth.abs().values, 1)[:, :k]
        overlap = np.mean([len(set(a) & set(t)) / k for a, t in zip(a3, t3)])
        sign = np.mean(np.sign(att.values) == np.sign(truth.values))
        return {
            "global_spearman": float(spearmanr(g_model, g_true)[0]),
            "mean_instance_pearson": float(np.nanmean(per)),
            "median_instance_pearson": float(np.nanmedian(per)),
            "top1_agreement": float(top1),
            "top3_overlap": float(overlap),
            "sign_agreement": float(sign),
        }

    res["explanation_fidelity"] = {"xgb_shap": fidelity(shap_df), "lr_linear": fidelity(lr_contrib)}
    g_shap = shap_df.abs().mean()
    g_true = truth.abs().mean()
    res["global_importance"] = {
        "shap_share": (g_shap / g_shap.sum()).to_dict(),
        "true_share": (g_true / g_true.sum()).to_dict(),
        "lr_share": (lr_contrib.abs().mean() / lr_contrib.abs().mean().sum()).to_dict(),
    }

    # ---- a representative high-risk applicant for the ledger figure
    order = np.argsort(p["creditsense"])
    pick_pos = int(order[int(0.93 * len(order))])
    pick = X.index[te][pick_pos]
    res["ledger_example"] = {
        "pd": float(p["creditsense"][pick_pos]),
        "band": str(band_of(p["creditsense"][pick_pos : pick_pos + 1])[0]),
        "base_pd": float(platt.predict(np.array([base_margin]))[0]),
        "features": {f: (df.loc[pick, f] if f == "sector" else float(df.loc[pick, f])) for f in ALL_FEATURES},
        "contrib_calibrated_logodds": {f: float(platt.a_ * shap_df.loc[pick, f]) for f in ALL_FEATURES},
        "true_contrib": {f: float(truth.loc[pick, f]) for f in ALL_FEATURES},
        "defaulted": int(y[pick]),
    }

    # ---- latency of one explanation (cached explainer vs. rebuilt per request)
    one = X.iloc[te[:1]]
    for _ in range(20):
        explainer.shap_values(one)
    lat_cached = []
    for i in range(1000):
        row = X.iloc[te[i : i + 1]]
        s = time.perf_counter()
        champ.predict_proba(row)
        explainer.shap_values(row)
        lat_cached.append((time.perf_counter() - s) * 1000)
    lat_rebuild = []
    for i in range(200):
        row = X.iloc[te[i : i + 1]]
        s = time.perf_counter()
        champ.predict_proba(row)
        shap.TreeExplainer(champ).shap_values(row)
        lat_rebuild.append((time.perf_counter() - s) * 1000)
    s = time.perf_counter()
    explainer.shap_values(X.iloc[te])
    batch_ms = (time.perf_counter() - s) * 1000
    res["latency_ms"] = {
        "cached_median": float(np.median(lat_cached)),
        "cached_p95": float(np.percentile(lat_cached, 95)),
        "rebuild_median": float(np.median(lat_rebuild)),
        "rebuild_p95": float(np.percentile(lat_rebuild, 95)),
        "batch_total": batch_ms,
        "batch_per_applicant": batch_ms / len(te),
        "n_trees": int(params["n_estimators"]),
    }

    # ---- lifecycle simulation
    res["lifecycle"] = lifecycle(
        params, df.iloc[tr].reset_index(drop=True), y[tr], n_cycles=6, cohort=4000, approve_below=BANDS[1], seed=SEED
    )

    # ---- interaction-strength sweep (5 seeds per setting, tuned params held fixed)
    res["interaction_sweep"] = interaction_sweep(
        params, kappas=[0.0, 1.0, 2.0, 3.0, 4.0], seeds=range(5), n=N_APPLICANTS, target_rate=res["data"]["default_rate"]
    )

    # ---- GSTIN validation study
    res["gstin"] = gstin_study(20_000, SEED)

    res["runtime_seconds"] = time.time() - t0
    (OUT / "metrics.json").write_text(json.dumps(res, indent=2, default=float))

    # keep arrays needed for figures
    np.savez(
        OUT / "curves.npz",
        y_test=y[te],
        **{f"p_{k}": v for k, v in p.items()},
        p_xgb_raw_uncal=p["xgb_tuned_raw"],
    )
    print(json.dumps({k: res[k] for k in ("data", "test_metrics", "delta_auc", "latency_ms")}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--retune", action="store_true")
    ap.add_argument("--trials", type=int, default=60)
    a = ap.parse_args()
    main(a.retune, a.trials)
