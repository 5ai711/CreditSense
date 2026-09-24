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

The platform measurements come from the running system rather than from the simulation:

```bash
docker compose up -d --build --wait          # from the repository root
python platform_bench.py --n 200             # results/platform.json; stops and restarts ml-service
```

It submits applications through the web proxy as the browser does, then stops the ML
service to measure the fallback to manual review and the circuit breaker's recovery.

## Layout

| Path | Contents |
|------|----------|
| `creditsense_sim/data.py` | feature generator, true log-odds, closed-form true Shapley values |
| `creditsense_sim/models.py` | baselines, WOE encoder, Platt-on-margin calibrator, metrics |
| `creditsense_sim/gstin.py` | GSTIN shape check, Luhn mod-36 check character, error generators |
| `run_experiments.py` | every experiment; writes `results/metrics.json` |
| `make_figures.py` | figures from the saved results |
| `platform_bench.py` | end-to-end latency and outage behaviour of the running stack; writes `results/platform.json` |
| `export_tex.py` | macros/tables so reported numbers always match `metrics.json` and `platform.json` |

The generator is identical to the ML service's (`ml-service/creditsense_ml/generator.py`). The data are
simulated, so the metrics describe the method under a documented
generator, not performance on a real loan book.
