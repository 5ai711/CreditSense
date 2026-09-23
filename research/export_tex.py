"""Turn results/metrics.json into LaTeX macros and tables so the paper never
carries a hand-typed number. Usage: python export_tex.py <output_dir>"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from creditsense_sim.data import ALL_FEATURES, FEATURE_LABELS

m = json.loads((Path(__file__).parent / "results" / "metrics.json").read_text())
out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
macros = []


def mac(name, value):
    macros.append(f"\\newcommand{{\\{name}}}{{{value}}}")


pct = lambda v, d=1: f"{100 * v:.{d}f}"
sgn = lambda v, d=3: f"\\ensuremath{{{v:+.{d}f}}}"


def lower_label(f):
    """Lower-case a feature label for running text, keeping acronyms such as GST and KYC."""
    return " ".join(w if w.isupper() else w.lower() for w in FEATURE_LABELS[f].split())
f3 = lambda v: f"{v:.3f}"

d = m["data"]
mac("Napp", f"{d['n']:,}".replace(",", "{,}"))
mac("Ntrain", f"{d['n_train']:,}".replace(",", "{,}"))
mac("Nvalid", f"{d['n_valid']:,}".replace(",", "{,}"))
mac("Ntest", f"{d['n_test']:,}".replace(",", "{,}"))
mac("defaultRate", pct(d["default_rate"]))
mac("oracleAUC", f3(d["oracle_auc_test"]))

t = m["tuning"]
mac("nTrials", t["n_trials"])
mac("cvAUC", f3(t["best_cv_auc"]))
mac("tuneSeconds", f"{t['seconds']:.0f}")
mac("spw", f"{t['scale_pos_weight']:.2f}")
bp = t["best_params"]
mac("bpTrees", bp["n_estimators"])
mac("bpDepth", bp["max_depth"])
mac("bpEta", f"{bp['learning_rate']:.3f}")
mac("bpSub", f"{bp['subsample']:.2f}")
mac("bpCol", f"{bp['colsample_bytree']:.2f}")
mac("bpMcw", f"{bp['min_child_weight']:.2f}")
mac("bpLambda", f"{bp['reg_lambda']:.2f}")
mac("bpAlpha", f"{bp['reg_alpha']:.2f}")
mac("bpGamma", f"{bp['gamma']:.2f}")
mac("plattA", f"{m['calibration_map']['a']:.3f}")
mac("plattB", f"{m['calibration_map']['b']:.3f}")

tm = m["test_metrics"]
for key, tag in [("lr_std", "LRs"), ("lr_woe", "LRw"), ("xgb_default", "XGd"), ("xgb_tuned_raw", "XGr"), ("creditsense", "CS")]:
    mac(f"auc{tag}", f3(tm[key]["auc"]))
    mac(f"pr{tag}", f3(tm[key]["pr_auc"]))
    mac(f"ks{tag}", f3(tm[key]["ks"]))
    mac(f"brier{tag}", f"{tm[key]['brier']:.4f}")
    mac(f"ece{tag}", f"{tm[key]['ece']:.3f}")

for base, tag in [("lr_std", "LRs"), ("lr_woe", "LRw"), ("xgb_default", "XGd")]:
    dd = m["delta_auc"][base]
    mac(f"dAUC{tag}", sgn(dd["mean"]))
    mac(f"dAUClo{tag}", sgn(dd["ci95"][0]))
    mac(f"dAUChi{tag}", sgn(dd["ci95"][1]))

br = m["bad_rate_at_approval"]
for a in ("60", "70", "80"):
    for key, tag in [("lr_std", "LRs"), ("lr_woe", "LRw"), ("xgb_default", "XGd"), ("creditsense", "CS")]:
        mac(f"bad{tag}{ {'60': 'A', '70': 'B', '80': 'C'}[a] }".replace(" ", ""), pct(br[a][key], 2))

op = m["operating_point"]
mac("opThr", f"{op['threshold']:.3f}")
mac("opRecall", pct(op["recall"]))
mac("opSpec", pct(op["specificity"]))
mac("opPrec", pct(op["precision"]))
mac("opAcc", pct(op["accuracy"]))
for k in ("tn", "fp", "fn", "tp"):
    mac(f"op{k.upper()}", f"{op[k]:,}".replace(",", "{,}"))

rb = m["risk_bands"]
for b in ("Low", "Medium", "High"):
    mac(f"share{b}", pct(rb[b]["share"]))
    mac(f"pd{b}", pct(rb[b]["mean_pd"]))
    mac(f"odr{b}", pct(rb[b]["observed_default_rate"]))
    mac(f"n{b}", f"{rb[b]['n']:,}".replace(",", "{,}"))

add = m["shap_additivity_max_abs_err"]
exp = int(np.floor(np.log10(add)))
mac("additivity", f"{add / 10**exp:.1f}\\times 10^{{{exp}}}")

fx, fl = m["explanation_fidelity"]["xgb_shap"], m["explanation_fidelity"]["lr_linear"]
for tag, f in (("X", fx), ("L", fl)):
    mac(f"fidSpear{tag}", f3(f["global_spearman"]))
    mac(f"fidMean{tag}", f3(f["mean_instance_pearson"]))
    mac(f"fidMed{tag}", f3(f["median_instance_pearson"]))
    mac(f"fidTop{tag}", pct(f["top1_agreement"]))
    mac(f"fidTopThree{tag}", pct(f["top3_overlap"]))
    mac(f"fidSign{tag}", pct(f["sign_agreement"]))

gi = m["global_importance"]
rank_true = sorted(ALL_FEATURES, key=lambda f: -gi["true_share"][f])
rank_shap = sorted(ALL_FEATURES, key=lambda f: -gi["shap_share"][f])
mac("topTrueA", lower_label(rank_true[0]))
mac("topTrueB", lower_label(rank_true[1]))
mac("topTrueC", lower_label(rank_true[2]))
mac("topShapA", lower_label(rank_shap[0]))
mac("topShapB", lower_label(rank_shap[1]))
mac("topShapC", lower_label(rank_shap[2]))

ex = m["ledger_example"]
mac("exPD", pct(ex["pd"]))
mac("exBase", pct(ex["base_pd"]))
mac("exBand", ex["band"].lower())
c = ex["contrib_calibrated_logodds"]
top = sorted(ALL_FEATURES, key=lambda f: -abs(c[f]))
mac("exTopA", lower_label(top[0]))
mac("exTopB", lower_label(top[1]))
mac("exTopAval", sgn(c[top[0]], 2))
mac("exTopBval", sgn(c[top[1]], 2))
neg = [f for f in top if c[f] < 0]
mac("exNeg", lower_label(neg[0]) if neg else "none")
mac("exNegval", sgn(c[neg[0]], 2) if neg else "0")
mac("exOutcome", "defaulted" if ex["defaulted"] else "did not default")

lt = m["latency_ms"]
mac("latCached", f"{lt['cached_median']:.1f}")
mac("latCachedP", f"{lt['cached_p95']:.1f}")
mac("latRebuild", f"{lt['rebuild_median']:.1f}")
mac("latRebuildP", f"{lt['rebuild_p95']:.1f}")
mac("latBatch", f"{lt['batch_per_applicant'] * 1000:.0f}")
mac("latSpeedup", f"{lt['rebuild_median'] / lt['cached_median']:.0f}")

lc = m["lifecycle"]
mac("lcCycles", len(lc))
mac("lcPromotions", sum(r["promoted"] for r in lc))
mac("lcSignificant", sum(r["significant"] for r in lc))
mac("lcApproval", pct(np.mean([r["approval_rate"] for r in lc])))
mac("lcFinalChamp", f3(lc[-1]["auc_champion"]))
mac("lcFinalStatic", f3(lc[-1]["auc_static"]))
gap = [r["auc_champion"] - r["auc_static"] for r in lc]
mac("lcGapFinal", sgn(gap[-1]))
mac("lcGapMax", sgn(max(gap)))
mac("lcPool", f"{lc[-1]['pool_size']:,}".replace(",", "{,}"))
mac("lcRejected", " and ".join(str(r["cycle"]) for r in lc if not r["promoted"]))
cum = [str(r["cycle"]) for r in lc if r["champion_vs_static_ci90_low"] > 0]
mac("lcCumSig", (", ".join(cum[:-1]) + ", and " + cum[-1]) if len(cum) > 2 else " and ".join(cum))
mac("lcCumLoFinal", sgn(lc[-1]["champion_vs_static_ci90_low"]))
pl = [str(r["cycle"]) for r in lc if r["promoted"]]
mac("lcPromotedList", ", ".join(pl[:-1]) + ", and " + pl[-1] if len(pl) > 2 else " and ".join(pl))

g = m["gstin"]
mac("gstN", f"{g['valid']['n']:,}".replace(",", "{,}"))
for k, tag in (("substitution", "Sub"), ("transposition", "Tr"), ("fabricated", "Fab"), ("valid", "Val")):
    mac(f"gst{tag}Shape", pct(g[k]["shape_only_accept"], 2))
    mac(f"gst{tag}Full", pct(g[k]["full_accept"], 2))
    mac(f"gst{tag}N", f"{g[k]['n']:,}".replace(",", "{,}"))

env = m["environment"]
mac("verXGB", env["xgboost"])
mac("verSHAP", env["shap"])
mac("verSK", env["scikit_learn"])
mac("verOptuna", env["optuna"])
mac("verPy", env["python"])

curves = np.load(Path(__file__).parent / "results" / "curves.npz")
mac("rawMeanPD", pct(float(curves["p_xgb_tuned_raw"].mean())))
mac("calMeanPD", pct(float(curves["p_creditsense"].mean())))
mac("brierCut", f"{100 * (1 - tm['creditsense']['brier'] / tm['xgb_tuned_raw']['brier']):.0f}")

(out / "results_macros.tex").write_text("\n".join(macros) + "\n")

# ---- sweep table
sw = m["interaction_sweep"]
rows = []
for k in sorted({r["kappa"] for r in sw}):
    rs = [r for r in sw if r["kappa"] == k]
    col = lambda key: np.array([r[key] for r in rs])
    gapv = col("auc_xgb") - col("auc_lr_std")
    rows.append(
        f"{k:.0f} & {col('auc_oracle').mean():.3f} & {col('auc_lr_woe').mean():.3f} & {col('auc_lr_std').mean():.3f} & "
        f"{col('auc_xgb').mean():.3f} & ${gapv.mean():+.3f}\\pm{gapv.std(ddof=1):.3f}$ & "
        f"{col('fid_lr').mean():.3f} & {col('fid_xgb').mean():.3f} \\\\"
    )
(out / "table_sweep.tex").write_text("\n".join(rows) + "\n")
kmax = max(r["kappa"] for r in sw)
gap_max = np.mean([r["auc_xgb"] - r["auc_lr_std"] for r in sw if r["kappa"] == kmax])
gap0 = np.mean([r["auc_xgb"] - r["auc_lr_std"] for r in sw if r["kappa"] == 0])
with open(out / "results_macros.tex", "a") as fh:
    fh.write(f"\\newcommand{{\\swGapMax}}{{{sgn(gap_max)}}}\n")
    fh.write(f"\\newcommand{{\\swGapZero}}{{{sgn(gap0)}}}\n")
    fh.write(f"\\newcommand{{\\swKmax}}{{{kmax:.0f}}}\n")
    fh.write(f"\\newcommand{{\\swSeeds}}{{{len({r['seed'] for r in sw})}}}\n")
    fx_max = np.mean([r["fid_xgb"] for r in sw if r["kappa"] == kmax])
    fl_max = np.mean([r["fid_lr"] for r in sw if r["kappa"] == kmax])
    fh.write(f"\\newcommand{{\\swFidXmax}}{{{fx_max:.3f}}}\n")
    fh.write(f"\\newcommand{{\\swFidLmax}}{{{fl_max:.3f}}}\n")

# ---- lifecycle table
lrows = []
for r in lc:
    dec = "promote" if r["promoted"] else "retain"
    sig = "yes" if r["significant"] else "no"
    lrows.append(
        f"{r['cycle']} & {100 * r['approval_rate']:.1f} & {r['pool_size']:,} & {r['auc_static']:.3f} & "
        f"{r['auc_champion']:.3f} & {r['auc_challenger']:.3f} & {dec} & {sig} \\\\".replace(",", "{,}")
    )
(out / "table_lifecycle.tex").write_text("\n".join(lrows) + "\n")
print(f"wrote {len(macros)} macros")
