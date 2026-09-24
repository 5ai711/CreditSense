"""The engineered feature vector shared by the ML service and the core backend.

The backend derives these values from an application; the ML service never sees
names, PAN, GSTIN or documents, only this vector.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SECTORS = ["Manufacturing", "Trading", "Services", "Retail", "Agri-allied", "Hospitality"]


@dataclass(frozen=True)
class Feature:
    name: str
    label: str
    unit: str
    lower: float
    upper: float


NUMERIC_FEATURES: list[Feature] = [
    Feature("business_vintage", "Business vintage", "years", 0.0, 100.0),
    Feature("monthly_revenue", "Monthly revenue", "INR lakh", 0.01, 100_000.0),
    Feature("revenue_volatility", "Revenue volatility", "coefficient of variation", 0.0, 5.0),
    Feature("gst_filing_consistency", "GST filing consistency", "share filed on time", 0.0, 1.0),
    Feature("debt_to_revenue", "Debt-to-revenue", "ratio", 0.0, 50.0),
    Feature("inflow_outflow_ratio", "Inflow/outflow ratio", "ratio", 0.0, 10.0),
    Feature("balance_cover", "Balance cover", "months of outflow", 0.0, 60.0),
    Feature("trade_references", "Trade references", "count", 0.0, 500.0),
    Feature("delinquency_events", "Delinquency events", "count", 0.0, 100.0),
    Feature("loan_to_revenue", "Loan-to-revenue", "ratio", 0.0, 50.0),
    Feature("kyc_completeness", "KYC completeness", "score", 0.0, 1.0),
    Feature("digital_txn_volume", "Digital transaction volume", "transactions per month", 0.0, 1_000_000.0),
]
NUMERIC_NAMES = [f.name for f in NUMERIC_FEATURES]
FEATURE_NAMES = NUMERIC_NAMES + ["sector"]
SECTOR_DUMMIES = [f"sector_{s}" for s in SECTORS[1:]]  # Manufacturing is the reference level
MODEL_COLUMNS = NUMERIC_NAMES + SECTOR_DUMMIES


def to_model_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encode the sector and order columns exactly as the models expect."""
    out = df[NUMERIC_NAMES].astype(float).copy()
    for s in SECTORS[1:]:
        out[f"sector_{s}"] = (df["sector"] == s).astype(float)
    return out[MODEL_COLUMNS]


def group_sector(contrib: np.ndarray) -> dict[str, float]:
    """Collapse per-column attributions back to one value per business feature."""
    values = dict(zip(MODEL_COLUMNS, contrib.tolist()))
    grouped = {name: values[name] for name in NUMERIC_NAMES}
    grouped["sector"] = float(sum(values[c] for c in SECTOR_DUMMIES))
    return grouped
