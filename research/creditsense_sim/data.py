"""Synthetic MSME loan-applicant generator with a known ground-truth risk function.

No public MSME loan book with the features CreditSense needs is available, so the
evaluation uses simulated applicants. The generator is deliberately transparent:
every feature distribution and every term of the true default log-odds is written
out below, which also lets us compare model explanations against the true drivers.

Units: revenue is in INR lakh per month; ratios are unitless; counts are integers.
Only applicants that have already cleared the compliance gate are generated, so
KYC completeness is always at or above the gate threshold (0.80).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

SECTORS = ["Manufacturing", "Trading", "Services", "Retail", "Agri-allied", "Hospitality"]
SECTOR_PROBS = [0.24, 0.22, 0.20, 0.16, 0.10, 0.08]
BASE_SECTOR_RISK = {
    "Manufacturing": 0.00,
    "Trading": 0.15,
    "Services": -0.10,
    "Retail": 0.25,
    "Agri-allied": 0.35,
    "Hospitality": 0.45,
}

NUMERIC_FEATURES = [
    "business_vintage",
    "monthly_revenue",
    "revenue_volatility",
    "gst_filing_consistency",
    "debt_to_revenue",
    "inflow_outflow_ratio",
    "balance_cover",
    "trade_references",
    "delinquency_events",
    "loan_to_revenue",
    "kyc_completeness",
    "digital_txn_volume",
]
ALL_FEATURES = NUMERIC_FEATURES + ["sector"]

FEATURE_LABELS = {
    "business_vintage": "Business vintage",
    "monthly_revenue": "Monthly revenue",
    "revenue_volatility": "Revenue volatility",
    "gst_filing_consistency": "GST filing consistency",
    "debt_to_revenue": "Debt-to-revenue",
    "inflow_outflow_ratio": "Inflow/outflow ratio",
    "balance_cover": "Balance cover",
    "trade_references": "Trade references",
    "delinquency_events": "Delinquency events",
    "loan_to_revenue": "Loan-to-revenue",
    "kyc_completeness": "KYC completeness",
    "digital_txn_volume": "Digital txn volume",
    "sector": "Sector",
}


@dataclass
class Drift:
    """Scenario knobs: cohort drift for the lifecycle study and the interaction sweep."""

    volatility_coef: float = 1.9
    sector_shock: dict = field(default_factory=dict)  # sector -> extra log-odds
    digital_coef: float = -0.22
    interaction_scale: float = 1.0  # multiplies every pairwise interaction term
    intercept_shift: float = 0.0  # re-centres the default rate when terms change


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def sample_features(n: int, rng: np.random.Generator) -> pd.DataFrame:
    sector = rng.choice(SECTORS, size=n, p=SECTOR_PROBS)
    seasonal = np.isin(sector, ["Agri-allied", "Hospitality"]).astype(float)
    consumer = np.isin(sector, ["Retail", "Services"]).astype(float)

    vintage = np.clip(rng.gamma(2.0, 3.0, n) + 0.5, 0.5, 35.0)
    log_rev = 1.2 + 0.35 * np.log1p(vintage) + rng.normal(0.0, 0.8, n)
    revenue = np.exp(log_rev)
    volatility = np.clip(
        rng.gamma(2.2, 0.10, n) + 0.25 / np.sqrt(vintage) + 0.12 * seasonal, 0.03, 1.5
    )
    gst_a = 5.0 + 0.25 * np.minimum(vintage, 10.0)
    gst = rng.beta(gst_a, 1.4)
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
    )


def _terms(df: pd.DataFrame, drift: Drift):
    """Return (main_effects, interactions) of the true log-odds.

    main_effects: dict feature -> array (one additive term per feature)
    interactions: list of (feat_a, feat_b, a(x_a), b(x_b), coef), term = coef*a*b
    """
    v = df["business_vintage"].to_numpy()
    cv = df["revenue_volatility"].to_numpy()
    debt = df["debt_to_revenue"].to_numpy()
    dpd = df["delinquency_events"].to_numpy()
    upi = df["digital_txn_volume"].to_numpy()
    sector = df["sector"].to_numpy()
    sector_risk = {s: BASE_SECTOR_RISK[s] + drift.sector_shock.get(s, 0.0) for s in SECTORS}

    main = {
        "business_vintage": -0.55 * np.log1p(v) + 0.60 * (v < 2.0),
        "monthly_revenue": -0.25 * np.log(df["monthly_revenue"].to_numpy()),
        "revenue_volatility": drift.volatility_coef * cv,
        "gst_filing_consistency": 1.8 * _sigmoid((0.72 - df["gst_filing_consistency"].to_numpy()) * 14.0),
        "debt_to_revenue": 0.9 * debt + 1.6 * np.maximum(0.0, debt - 0.6),
        "inflow_outflow_ratio": 3.0 * np.maximum(0.0, 1.0 - df["inflow_outflow_ratio"].to_numpy())
        - 0.5 * np.maximum(0.0, df["inflow_outflow_ratio"].to_numpy() - 1.0),
        "balance_cover": -0.45 * np.log1p(3.0 * df["balance_cover"].to_numpy()),
        "trade_references": -0.14 * np.minimum(df["trade_references"].to_numpy(), 8.0),
        "delinquency_events": 0.45 * dpd,
        "loan_to_revenue": 1.3 * np.maximum(0.0, df["loan_to_revenue"].to_numpy() - 0.30),
        "kyc_completeness": -2.0 * (df["kyc_completeness"].to_numpy() - 0.90),
        "digital_txn_volume": drift.digital_coef * np.log1p(upi),
        "sector": np.array([sector_risk[s] for s in sector]),
    }
    k = drift.interaction_scale
    interactions = [
        ("revenue_volatility", "debt_to_revenue", cv, debt, 1.4 * k),
        ("delinquency_events", "business_vintage", dpd, (v < 3.0).astype(float), 0.35 * k),
        (
            "digital_txn_volume",
            "sector",
            np.log1p(upi),
            np.isin(sector, ["Retail", "Trading"]).astype(float),
            -0.15 * k,
        ),
    ]
    return main, interactions


INTERCEPT = -1.43  # tuned so that the base-population default rate is about 12 %
LATENT_SD = 0.55  # unobserved borrower quality, keeps the task realistically noisy


def true_logit(df: pd.DataFrame, drift: Drift | None = None) -> np.ndarray:
    drift = drift or Drift()
    main, inter = _terms(df, drift)
    z = INTERCEPT + drift.intercept_shift + sum(main.values())
    for _, _, a, b, c in inter:
        z = z + c * a * b
    return z


def matched_intercept_shift(drift: Drift, target_rate: float, n: int = 100_000, seed: int = 7) -> float:
    """Intercept shift that keeps the population default rate at `target_rate`."""
    rng = np.random.default_rng(seed)
    df = sample_features(n, rng)
    z = true_logit(df, Drift(**{**drift.__dict__, "intercept_shift": 0.0})) + rng.normal(0.0, LATENT_SD, n)
    lo, hi = -6.0, 6.0
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        if _sigmoid(z + mid).mean() > target_rate:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def generate(n: int, seed: int, drift: Drift | None = None):
    """Return (features, labels, true noiseless log-odds)."""
    rng = np.random.default_rng(seed)
    df = sample_features(n, rng)
    z = true_logit(df, drift)
    p = _sigmoid(z + rng.normal(0.0, LATENT_SD, n))
    y = (rng.random(n) < p).astype(int)
    return df, y, z


def true_shapley(df: pd.DataFrame, background: pd.DataFrame, drift: Drift | None = None) -> pd.DataFrame:
    """Interventional Shapley values of the noiseless true log-odds.

    Additive term f_i: phi_i = f_i(x_i) - E[f_i].
    Product term c*a(x_i)*b(x_j) (features treated as independent, as in
    interventional SHAP):
        phi_i = c/2 * [(a_i - Ea) * b_j + (a_i - Ea) * Eb]
        phi_j = c/2 * [(b_j - Eb) * a_i + (b_j - Eb) * Ea]
    which sum to c*(a_i*b_j - Ea*Eb).
    """
    drift = drift or Drift()
    main, inter = _terms(df, drift)
    bmain, binter = _terms(background, drift)
    phi = {f: main[f] - bmain[f].mean() for f in ALL_FEATURES}
    for (fa, fb, a, b, c), (_, _, ba, bb, _) in zip(inter, binter):
        ea, eb = ba.mean(), bb.mean()
        phi[fa] = phi[fa] + 0.5 * c * ((a - ea) * b + (a - ea) * eb)
        phi[fb] = phi[fb] + 0.5 * c * ((b - eb) * a + (b - eb) * ea)
    return pd.DataFrame(phi, index=df.index)[ALL_FEATURES]
