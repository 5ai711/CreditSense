"""Render the evaluation figures from results/metrics.json and results/curves.npz."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import precision_recall_curve, roc_curve

from creditsense_sim.data import ALL_FEATURES, FEATURE_LABELS

OUT = Path(__file__).parent / "results"
FIG = OUT / "figures"

# Validated categorical order (blue, orange, aqua, yellow); line styles give a
# second encoding so the figures survive grayscale printing.
C = {"blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100"}
RISK_UP, RISK_DOWN = "#e34948", "#2a78d6"
INK, MUTED, GRID = "#1a1a1a", "#555555", "#d9d9d9"

plt.rcParams.update(
    {
        "font.family": "STIXGeneral",
        "mathtext.fontset": "stix",
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "legend.fontsize": 7,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "axes.edgecolor": MUTED,
        "axes.linewidth": 0.6,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "axes.labelcolor": INK,
        "text.color": INK,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.4,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
    }
)
COL_W = 3.45  # IEEE single-column width in inches

MODELS = [
    ("lr_std", "LR (standardized)", C["yellow"], (0, (1, 1.2))),
    ("lr_woe", "LR (WOE scorecard)", C["aqua"], (0, (4, 1.5))),
    ("xgb_default", "XGBoost (default)", C["orange"], (0, (6, 1.5, 1, 1.5))),
    ("creditsense", "CreditSense (tuned, calibrated)", C["blue"], "-"),
]


def roc_pr(m, cv):
    y = cv["y_test"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(COL_W, 2.25))
    for key, label, color, ls in MODELS:
        p = cv[f"p_{key}"]
        fpr, tpr, _ = roc_curve(y, p)
        a1.plot(fpr, tpr, color=color, ls=ls, lw=1.2, label=f"{label}")
        pr, rc, _ = precision_recall_curve(y, p)
        a2.plot(rc, pr, color=color, ls=ls, lw=1.2)
    a1.plot([0, 1], [0, 1], color=MUTED, lw=0.6, ls=":")
    a2.axhline(y.mean(), color=MUTED, lw=0.6, ls=":")
    a1.set(xlabel="False positive rate", ylabel="True positive rate", xlim=(0, 1), ylim=(0, 1))
    a2.set(xlabel="Recall", ylabel="Precision", xlim=(0, 1), ylim=(0, 1))
    a1.set_title("(a) ROC", pad=3)
    a2.set_title("(b) Precision-recall", pad=3)
    for a in (a1, a2):
        a.set_aspect("equal")
        a.set_xticks([0, 0.5, 1])
        a.set_yticks([0, 0.5, 1])
    h, l = a1.get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=2, bbox_to_anchor=(0.5, 0.0), handlelength=2.6, columnspacing=1.2)
    fig.subplots_adjust(wspace=0.45, bottom=0.36)
    fig.savefig(FIG / "roc_pr.pdf")
    plt.close(fig)


def reliability(m, cv):
    y = cv["y_test"]
    fig, ax = plt.subplots(figsize=(COL_W, 2.0))
    series = [
        ("xgb_tuned_raw", "Tuned XGBoost, uncalibrated", C["orange"], (0, (6, 1.5, 1, 1.5)), "s"),
        ("lr_woe", "LR (WOE scorecard)", C["aqua"], (0, (4, 1.5)), "^"),
        ("creditsense", "CreditSense (Platt on margin)", C["blue"], "-", "o"),
    ]
    for key, label, color, ls, mk in series:
        p = cv[f"p_{key}"]
        edges = np.quantile(p, np.linspace(0, 1, 11))
        idx = np.clip(np.digitize(p, edges[1:-1]), 0, 9)
        xs = [p[idx == b].mean() for b in range(10)]
        ys = [y[idx == b].mean() for b in range(10)]
        brier = m["test_metrics"][key]["brier"]
        ax.plot(xs, ys, color=color, ls=ls, lw=1.1, marker=mk, ms=3.2, label=f"{label} (Brier {brier:.3f})")
    ax.plot([0, 1], [0, 1], color=MUTED, lw=0.6, ls=":", label="Perfect calibration")
    ax.set(xlabel="Mean predicted probability of default", ylabel="Observed default rate", xlim=(0, 0.9), ylim=(0, 0.6))
    ax.legend(loc="upper left", handlelength=2.6, frameon=True, facecolor="white", edgecolor="none", framealpha=1.0)
    fig.savefig(FIG / "reliability.pdf")
    plt.close(fig)


def importance(m):
    g = m["global_importance"]
    feats = sorted(ALL_FEATURES, key=lambda f: g["true_share"][f])
    yv = np.arange(len(feats))
    h = 0.26
    fig, ax = plt.subplots(figsize=(COL_W, 2.9))
    ax.barh(yv + h, [g["true_share"][f] for f in feats], h * 0.92, color=INK, label="Ground truth (known generator)")
    ax.barh(yv, [g["shap_share"][f] for f in feats], h * 0.92, color=C["blue"], label="XGBoost + TreeSHAP")
    ax.barh(yv - h, [g["lr_share"][f] for f in feats], h * 0.92, color=C["aqua"], label="Logistic regression")
    ax.set_yticks(yv, [FEATURE_LABELS[f] for f in feats])
    ax.set_xlabel("Share of mean absolute attribution")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right")
    fig.savefig(FIG / "importance.pdf")
    plt.close(fig)


def fmt_value(f, v):
    if f == "sector":
        return str(v)
    if f in ("trade_references", "delinquency_events"):
        return f"{int(v)}"
    if f in ("gst_filing_consistency", "kyc_completeness"):
        return f"{100 * v:.0f}%"
    if f == "monthly_revenue":
        return f"{v:.1f} lakh"
    if f == "business_vintage":
        return f"{v:.1f} yr"
    if f == "digital_txn_volume":
        return f"{v:.0f}/mo"
    return f"{v:.2f}"


def ledger(m):
    ex = m["ledger_example"]
    c = ex["contrib_calibrated_logodds"]
    feats = sorted(ALL_FEATURES, key=lambda f: abs(c[f]), reverse=True)
    top = feats[:8]
    rest = sum(c[f] for f in feats[8:])
    rows = [(f"{FEATURE_LABELS[f]} = {fmt_value(f, ex['features'][f])}", c[f]) for f in top]
    rows.append((f"{len(feats) - 8} other features", rest))
    rows = rows[::-1]
    fig, ax = plt.subplots(figsize=(COL_W, 2.35))
    yv = np.arange(len(rows))
    vals = np.array([r[1] for r in rows])
    ax.barh(yv, vals, 0.62, color=[RISK_UP if v > 0 else RISK_DOWN for v in vals])
    lim = np.abs(vals).max() * 1.45
    for yy, v in zip(yv, vals):
        ax.text(v + (0.03 * lim if v >= 0 else -0.03 * lim), yy, f"{v:+.2f}", va="center",
                ha="left" if v >= 0 else "right", fontsize=6.5, family="DejaVu Sans Mono", color=INK)
    ax.axvline(0, color=INK, lw=0.7)
    ax.set_yticks(yv, [r[0] for r in rows])
    ax.set_xlim(-lim, lim)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Contribution to calibrated log-odds of default")
    ax.set_title(
        f"Reference PD {100 * ex['base_pd']:.1f}%  $\\rightarrow$  applicant PD {100 * ex['pd']:.1f}%  ({ex['band']} risk)",
        pad=4,
    )
    ax.text(0.98, 0.02, "raises risk", transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5, color=RISK_UP)
    ax.text(0.02, 0.02, "lowers risk", transform=ax.transAxes, ha="left", va="bottom", fontsize=6.5, color=RISK_DOWN)
    fig.savefig(FIG / "ledger.pdf")
    plt.close(fig)


def lifecycle(m):
    rows = m["lifecycle"]
    t = np.array([r["cycle"] for r in rows])
    fig, ax = plt.subplots(figsize=(COL_W, 1.85))
    ax.plot(t, [r["auc_static"] for r in rows], color=C["orange"], ls=(0, (4, 1.5)), marker="s", ms=3.5, lw=1.1,
            label="Static model (never retrained)")
    ax.plot(t, [r["auc_champion"] for r in rows], color=C["blue"], marker="o", ms=3.5, lw=1.2,
            label="Serving champion")
    ax.plot(t, [r["auc_challenger"] for r in rows], color=C["aqua"], ls=(0, (1, 1.2)), marker="^", ms=3.5, lw=1.1,
            label="Challenger")
    for r in rows:
        if r["promoted"]:
            ax.annotate("P", (r["cycle"], r["auc_challenger"]), textcoords="offset points", xytext=(0, 5),
                        ha="center", fontsize=6.5, color=INK)
    ax.set(xlabel="Retraining cycle", ylabel="AUC-ROC on current cohort")
    ax.set_xticks(t)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=3, handlelength=2.2, columnspacing=0.9)
    fig.savefig(FIG / "lifecycle.pdf")
    plt.close(fig)


def main():
    m = json.loads((OUT / "metrics.json").read_text())
    cv = np.load(OUT / "curves.npz")
    roc_pr(m, cv)
    reliability(m, cv)
    importance(m)
    ledger(m)
    lifecycle(m)


if __name__ == "__main__":
    main()
