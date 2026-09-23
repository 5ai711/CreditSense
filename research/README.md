# CreditSense research code

Simulation and evaluation code for the CreditSense risk-scoring core: a synthetic
MSME applicant generator with a known ground-truth default function, the model
comparison (standardized LR, WOE scorecard, XGBoost), SHAP fidelity checks, the
champion/challenger lifecycle simulation and the GSTIN check-character study.

## Run

```bash
pip install numpy pandas scipy scikit-learn xgboost shap optuna matplotlib
python run_experiments.py     # ~3 min on 4 cores; Optuna search cached in results/tuning.json
python make_figures.py        # results/figures/*.pdf
python export_tex.py <dir>    # LaTeX macros and table rows built from results/metrics.json
```

`--retune` forces a fresh hyperparameter search. All seeds are fixed, so reruns
reproduce `results/metrics.json` apart from the latency timings.

## Layout

| Path | Contents |
|------|----------|
| `creditsense_sim/data.py` | feature generator, true log-odds, closed-form true Shapley values |
| `creditsense_sim/models.py` | baselines, WOE encoder, Platt-on-margin calibrator, metrics |
| `creditsense_sim/gstin.py` | GSTIN shape check, Luhn mod-36 check character, error generators |
| `run_experiments.py` | every experiment; writes `results/metrics.json` |
| `make_figures.py` | figures from the saved results |
| `export_tex.py` | macros/tables so reported numbers always match `metrics.json` |

The data are simulated, so the metrics describe the method under a documented
generator, not performance on a real loan book.
