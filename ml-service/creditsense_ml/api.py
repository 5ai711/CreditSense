"""FastAPI surface of the ML microservice.

The service is stateless from the caller's point of view: it receives an
engineered feature vector (never personal data) and returns a probability of
default together with its per-feature explanation. A prediction whose
explanation cannot be produced is not returned at all (HTTP 503).
"""
from __future__ import annotations

import hmac
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .features import SECTORS
from .service import ExplanationUnavailable, ModelService

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("creditsense.ml")

Sector = Literal["Manufacturing", "Trading", "Services", "Retail", "Agri-allied", "Hospitality"]
assert set(Sector.__args__) == set(SECTORS)


class FeatureVector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_vintage: float = Field(ge=0, le=100, description="Years in operation")
    monthly_revenue: float = Field(gt=0, le=100_000, description="Average monthly revenue, INR lakh")
    revenue_volatility: float = Field(ge=0, le=5, description="Coefficient of variation of monthly revenue")
    gst_filing_consistency: float = Field(ge=0, le=1, description="Share of GST returns filed on time, trailing 12 months")
    debt_to_revenue: float = Field(ge=0, le=50, description="Existing debt / annual revenue")
    inflow_outflow_ratio: float = Field(ge=0, le=10, description="Bank credits / bank debits")
    balance_cover: float = Field(ge=0, le=60, description="Average balance in months of outflow")
    trade_references: float = Field(ge=0, le=500)
    delinquency_events: float = Field(ge=0, le=100, description="Prior days-past-due events")
    loan_to_revenue: float = Field(ge=0, le=50, description="Requested amount / annual revenue")
    kyc_completeness: float = Field(ge=0, le=1)
    digital_txn_volume: float = Field(ge=0, le=1_000_000, description="Digital (UPI) transactions per month")
    sector: Sector


class ScoreRequest(BaseModel):
    features: FeatureVector


class ContributionOut(BaseModel):
    feature: str
    feature_value: float | str
    shap_contribution: float


class ExplainResponse(BaseModel):
    model_version: str
    base_value: float = Field(description="Log-odds of the reference applicant; contributions add to this")
    contributions: list[ContributionOut]


class PredictResponse(ExplainResponse):
    probability_of_default: float
    risk_band: Literal["LOW", "MEDIUM", "HIGH"]


class OutcomeItem(BaseModel):
    reference_id: str = Field(min_length=1, max_length=100)
    features: FeatureVector


class OutcomeRequest(BaseModel):
    items: list[OutcomeItem] = Field(max_length=10_000)


class OutcomeOut(BaseModel):
    reference_id: str
    defaulted: bool


def _service() -> ModelService:
    return app.state.service


def require_token(x_service_token: str | None = Header(default=None)) -> None:
    expected = os.getenv("ML_SERVICE_TOKEN")
    if expected and not (x_service_token and hmac.compare_digest(x_service_token, expected)):
        raise HTTPException(status_code=401, detail="invalid service token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    service = ModelService(
        data_dir=Path(os.getenv("ML_DATA_DIR", "data")),
        bootstrap_trials=int(os.getenv("ML_BOOTSTRAP_TRIALS", "25")),
        retrain_trials=int(os.getenv("ML_RETRAIN_TRIALS", "0")),
        n_train=int(os.getenv("ML_TRAINING_ROWS", "20000")),
    )
    service.start()
    app.state.service = service
    yield


app = FastAPI(title="CreditSense ML service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    svc: ModelService | None = getattr(app.state, "service", None)
    if svc is None or not svc.ready:
        raise HTTPException(status_code=503, detail="model not loaded")
    return {"status": "UP", "model_version": svc.info()["model_version"]}


def _scored(features: FeatureVector):
    try:
        return _service().score(features.model_dump())
    except ExplanationUnavailable as exc:
        log.error("prediction withheld: %s", exc)
        raise HTTPException(status_code=503, detail=f"prediction withheld: {exc}") from exc


@app.post("/predict", response_model=PredictResponse, dependencies=[Depends(require_token)])
def predict(req: ScoreRequest):
    s = _scored(req.features)
    return PredictResponse(
        probability_of_default=s.probability_of_default, risk_band=s.risk_band, model_version=s.model_version,
        base_value=s.base_value, contributions=[ContributionOut(**c.__dict__) for c in s.contributions],
    )


@app.post("/explain", response_model=ExplainResponse, dependencies=[Depends(require_token)])
def explain(req: ScoreRequest):
    s = _scored(req.features)
    return ExplainResponse(model_version=s.model_version, base_value=s.base_value,
                           contributions=[ContributionOut(**c.__dict__) for c in s.contributions])


@app.post("/outcomes/simulate", response_model=list[OutcomeOut], dependencies=[Depends(require_token)])
def simulate(req: OutcomeRequest):
    pairs = _service().simulate_outcomes([(i.reference_id, i.features.model_dump()) for i in req.items])
    return [OutcomeOut(reference_id=r, defaulted=bool(d)) for r, d in pairs]


@app.post("/retrain", dependencies=[Depends(require_token)])
def retrain():
    return _service().retrain()


@app.get("/model-info", dependencies=[Depends(require_token)])
def model_info():
    return _service().info()


@app.get("/model-history", dependencies=[Depends(require_token)])
def model_history():
    return _service().history()
