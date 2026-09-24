"""Synthetic MSME applicant generator with a documented ground-truth default function.

There is no public MSME loan book with the features CreditSense uses, so the
training data are simulated. Nothing here is a black box: every feature
distribution and every term of the true default log-odds is written out below,
so the risk signal a model can learn is known exactly.

Units
-----
Monetary values are in INR lakh; ratios are unitless; counts are integers.
Only applicants that have already cleared the compliance gate are simulated, so
KYC completeness is always between the gate threshold (0.80) and 1.

Ground truth
------------
The default log-odds is

    z = INTERCEPT + sum_j g_j(x_j) + sum_(j,k) c_jk * h_j(x_j) * h_k(x_k)

with nonlinear main effects g_j (thresholds, hinges, log shapes), three pairwise
interactions, and an unobserved borrower-quality term u ~ N(0, LATENT_SD^2):

    P(default within 12 months) = sigmoid(z + u).

Because u is not observable, even a perfect model cannot separate defaulters
completely; on this population the noiseless score z reaches an AUC of about 0.82.

Usage
-----
    python -m creditsense_ml.generator --n 20000 --seed 42 --out data/training.csv
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from .features import FEATURE_NAMES, SECTORS

SECTOR_PROBS = [0.24, 0.22, 0.20, 0.16, 0.10, 0.08]
SECTOR_RISK = {
    "Manufacturing": 0.00,
    "Trading": 0.15,
    "Services": -0.10,
    "Retail": 0.25,
    "Agri-allied": 0.35,
    "Hospitality": 0.45,
}
INTERCEPT = -1.43  # gives a base-population default rate of about 12 %
LATENT_SD = 0.55  # unobserved borrower quality
LABEL = "defaulted_within_12_months"


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def sample_features(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Draw applicant features. Correlations run through business age and sector."""
    sector = rng.choice(SECTORS, size=n, p=SECTOR_PROBS)
    seasonal = np.isin(sector, ["Agri-allied", "Hospitality"]).astype(float)
    consumer = np.isin(sector, ["Retail", "Services"]).astype(float)

    vintage = np.clip(rng.gamma(2.0, 3.0, n) + 0.5, 0.5, 35.0)
    revenue = np.exp(1.2 + 0.35 * np.log1p(vintage) + rng.normal(0.0, 0.8, n))
    volatility = np.clip(rng.gamma(2.2, 0.10, n) + 0.25 / np.sqrt(vintage) + 0.12 * seasonal, 0.03, 1.5)
    gst = rng.beta(5.0 + 0.25 * np.minimum(vintage, 10.0), 1.4)
    debt = np.clip(rng.gamma(1.6, 0.22, n), 0.0, 3.0)
    inflow_outflow = rng.normal(1.06, 0.09, n) - 0.05 * volatility
    balance_cover = np.clip(rng.gamma(1.8, 0.35, n), 0.0, 6.0)
    refs = rng.poisson(1.5 + 0.25 * np.minimum(vintage, 12.0))
    delinquency = rng.poisson(0.25 + 1.2 * (1.0 - gst))
    loan_to_rev = np.clip(np.exp(rng.normal(np.log(0.25), 0.55, n)), 0.02, 3.0)
    kyc = 0.80 + 0.20 * rng.beta(4.0, 1.5, n)
    digital = np.exp(3.8 + 0.5 * consumer - 0.02 * vintage + rng.normal(0.0, 0.9, n))

    return pd.DataFrame(
        {
            "business_vintage": vintage,
            "monthly_revenue": revenue,
            "revenue_volatility": volatility,
            "gst_filing_consistency": gst,
            "debt_to_revenue": debt,
            "inflow_outflow_ratio": inflow_outflow,
            "balance_cover": balance_cover,
            "trade_references": refs.astype(float),
            "delinquency_events": delinquency.astype(float),
            "loan_to_revenue": loan_to_rev,
            "kyc_completeness": kyc,
            "digital_txn_volume": digital,
            "sector": sector,
        }
    )[FEATURE_NAMES]


def true_logit(df: pd.DataFrame) -> np.ndarray:
    """Noise-free default log-odds for each applicant."""
    v = df["business_vintage"].to_numpy(float)
    cv = df["revenue_volatility"].to_numpy(float)
    debt = df["debt_to_revenue"].to_numpy(float)
    dpd = df["delinquency_events"].to_numpy(float)
    upi = df["digital_txn_volume"].to_numpy(float)
    iof = df["inflow_outflow_ratio"].to_numpy(float)
    sector = df["sector"].to_numpy()

    z = (
        INTERCEPT
        # younger businesses are riskier, with an extra penalty in the first two years
        - 0.55 * np.log1p(v) + 0.60 * (v < 2.0)
        - 0.25 * np.log(np.maximum(df["monthly_revenue"].to_numpy(float), 1e-3))
        + 1.9 * cv
        # late GST filing matters sharply once on-time filing drops below about 72 %
        + 1.8 * _sigmoid((0.72 - df["gst_filing_consistency"].to_numpy(float)) * 14.0)
        # leverage: linear, then steeper above 0.6
        + 0.9 * debt + 1.6 * np.maximum(0.0, debt - 0.6)
        # cash burn (more outflow than inflow) is penalised; surplus helps a little
        + 3.0 * np.maximum(0.0, 1.0 - iof) - 0.5 * np.maximum(0.0, iof - 1.0)
        - 0.45 * np.log1p(3.0 * df["balance_cover"].to_numpy(float))
        - 0.14 * np.minimum(df["trade_references"].to_numpy(float), 8.0)
        + 0.45 * dpd
        + 1.3 * np.maximum(0.0, df["loan_to_revenue"].to_numpy(float) - 0.30)
        - 2.0 * (df["kyc_completeness"].to_numpy(float) - 0.90)
        - 0.22 * np.log1p(upi)
        + np.array([SECTOR_RISK.get(s, 0.0) for s in sector])
        # interactions a linear score cannot express
        + 1.4 * cv * debt
        + 0.35 * dpd * (v < 3.0)
        - 0.15 * np.log1p(upi) * np.isin(sector, ["Retail", "Trading"])
    )
    return z


def generate(n: int, seed: int) -> pd.DataFrame:
    """Simulated applicants with the binary label `defaulted_within_12_months`."""
    rng = np.random.default_rng(seed)
    df = sample_features(n, rng)
    p = _sigmoid(true_logit(df) + rng.normal(0.0, LATENT_SD, n))
    df[LABEL] = (rng.random(n) < p).astype(int)
    return df


def _seed_for(reference: str) -> int:
    return int.from_bytes(hashlib.sha256(reference.encode()).digest()[:8], "big")


def simulate_outcome(features: pd.DataFrame, references: list[str]) -> np.ndarray:
    """Pretend twelve months have passed and draw each approved loan's outcome.

    The same ground-truth function (plus the same unobserved noise) that generated
    the training data decides the outcome. Seeding by the application reference
    makes the simulated outcome of a given loan stable across calls.
    """
    z = true_logit(features)
    out = np.empty(len(features), dtype=int)
    for i, ref in enumerate(references):
        rng = np.random.default_rng(_seed_for(ref))
        out[i] = int(rng.random() < _sigmoid(z[i] + rng.normal(0.0, LATENT_SD)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=20_000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("data/training.csv"))
    a = ap.parse_args()
    df = generate(a.n, a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False)
    print(f"wrote {len(df):,} applicants to {a.out} (default rate {df[LABEL].mean():.3f})")


if __name__ == "__main__":
    main()
