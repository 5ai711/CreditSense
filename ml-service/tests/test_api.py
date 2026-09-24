import pytest
from fastapi.testclient import TestClient

from .conftest import SAMPLE


@pytest.fixture(scope="module")
def client(tmp_path_factory, monkeypatch_module):
    monkeypatch_module.setenv("ML_DATA_DIR", str(tmp_path_factory.mktemp("api")))
    monkeypatch_module.setenv("ML_BOOTSTRAP_TRIALS", "0")
    monkeypatch_module.setenv("ML_TRAINING_ROWS", "3000")
    monkeypatch_module.setenv("ML_SERVICE_TOKEN", "test-token")
    from creditsense_ml.api import app

    with TestClient(app) as c:
        c.headers["X-Service-Token"] = "test-token"
        yield c


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "UP"


def test_predict_returns_score_with_ledger(client):
    r = client.post("/predict", json={"features": SAMPLE})
    assert r.status_code == 200
    body = r.json()
    assert body["risk_band"] in {"LOW", "MEDIUM", "HIGH"}
    assert len(body["contributions"]) == 13
    assert set(body["contributions"][0]) == {"feature", "feature_value", "shap_contribution"}


def test_explain_matches_predict(client):
    p = client.post("/predict", json={"features": SAMPLE}).json()
    e = client.post("/explain", json={"features": SAMPLE}).json()
    assert p["contributions"] == e["contributions"] and p["base_value"] == e["base_value"]


def test_rejects_bad_input_and_missing_token(client):
    assert client.post("/predict", json={"features": dict(SAMPLE, sector="Mining")}).status_code == 422
    assert client.post("/predict", json={"features": dict(SAMPLE, gst_filing_consistency=1.5)}).status_code == 422
    assert client.post("/predict", json={"features": dict(SAMPLE, name="Acme")}).status_code == 422  # no PII fields
    assert client.post("/predict", json={"features": SAMPLE}, headers={"X-Service-Token": "wrong"}).status_code == 401


def test_model_info_and_history(client):
    info = client.get("/model-info").json()
    assert info["features"][-1] == "sector" and "auc_roc" in info["metrics"]
    assert client.get("/model-history").json()["comparisons"][0]["event"] == "bootstrap"
