import pytest

from creditsense_ml.service import ModelService

SAMPLE = {
    "business_vintage": 6.5,
    "monthly_revenue": 8.0,
    "revenue_volatility": 0.30,
    "gst_filing_consistency": 0.9,
    "debt_to_revenue": 0.3,
    "inflow_outflow_ratio": 1.05,
    "balance_cover": 0.6,
    "trade_references": 3,
    "delinquency_events": 0,
    "loan_to_revenue": 0.25,
    "kyc_completeness": 0.95,
    "digital_txn_volume": 60,
    "sector": "Services",
}


@pytest.fixture(scope="session")
def service(tmp_path_factory):
    """A small, untuned service so the suite runs in seconds."""
    svc = ModelService(tmp_path_factory.mktemp("ml"), bootstrap_trials=0, n_train=4000, n_holdout=1500)
    svc.start()
    return svc
