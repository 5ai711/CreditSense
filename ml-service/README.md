# CreditSense ML service

FastAPI microservice that scores MSME applications and explains every score.

* **Data**: `python -m creditsense_ml.generator` writes the documented synthetic training set
  (see the module docstring for every distribution and the ground-truth default function).
* **Models**: tuned XGBoost (class-weighted, Optuna search, Platt-calibrated) and a
  weight-of-evidence logistic scorecard baseline, evaluated on the same split with AUC-ROC,
  PR-AUC, KS, Brier/ECE, a calibration curve and a confusion matrix at PD 20%.
* **Explanations**: a TreeSHAP explainer is built once per model version and reused.
  Every prediction returns `{feature, feature_value, shap_contribution}` for all 13 features;
  contributions are on the calibrated log-odds scale and sum exactly to the score. If that
  check fails, the prediction is withheld (HTTP 503).
* **Lifecycle**: `/outcomes/simulate` records 12-month outcomes for matured loans;
  `/retrain` trains a challenger on base data plus outcomes and promotes it only if it beats
  the champion's AUC on a holdout no model trains on. Every comparison is logged.

| Endpoint | Purpose |
|---|---|
| `POST /predict` | PD, risk band, model version and the full SHAP ledger |
| `POST /explain` | the ledger only |
| `POST /outcomes/simulate` | simulate outcomes for matured loans and store them as feedback |
| `POST /retrain` | champion/challenger retraining |
| `GET /model-info` | serving version, metrics for model and baseline, features, hyperparameters |
| `GET /model-history` | every model version and every champion/challenger comparison |
| `GET /health` | readiness for the backend's circuit breaker |

All endpoints except `/health` require the `X-Service-Token` header when `ML_SERVICE_TOKEN` is set.

```bash
pip install -r requirements-dev.txt
pytest                                   # unit and API tests
ML_DATA_DIR=data uvicorn creditsense_ml.api:app --port 8000
```
