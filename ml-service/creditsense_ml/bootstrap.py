"""Generate the training data and train the first champion ahead of time.

Used by the Docker build so a fresh container serves a tuned model immediately:

    python -m creditsense_ml.bootstrap --data-dir seed --trials 25
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .service import ModelService


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--trials", type=int, default=25)
    ap.add_argument("--rows", type=int, default=20_000)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    svc = ModelService(a.data_dir, bootstrap_trials=a.trials, n_train=a.rows)
    svc.start()
    info = svc.info()
    print(f"champion {info['model_version']}: test AUC {info['metrics']['auc_roc']:.3f} "
          f"(WOE baseline {info['baseline_metrics']['auc_roc']:.3f}), holdout AUC {info['holdout_auc']:.3f}")


if __name__ == "__main__":
    main()
