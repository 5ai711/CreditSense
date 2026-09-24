import math

import pytest

from creditsense_ml.features import FEATURE_NAMES
from creditsense_ml.generator import LABEL, generate

from .conftest import SAMPLE


def test_prediction_always_carries_an_additive_explanation(service):
    s = service.score(SAMPLE)
    assert 0 < s.probability_of_default < 1
    assert {c.feature for c in s.contributions} == set(FEATURE_NAMES)
    logit = math.log(s.probability_of_default / (1 - s.probability_of_default))
    assert abs(s.base_value + sum(c.shap_contribution for c in s.contributions) - logit) < 1e-4
    # ordered for the ledger: largest absolute contribution first
    mags = [abs(c.shap_contribution) for c in s.contributions]
    assert mags == sorted(mags, reverse=True)


def test_risk_moves_in_the_expected_direction(service):
    risky = dict(SAMPLE, delinquency_events=4, gst_filing_consistency=0.4, inflow_outflow_ratio=0.8)
    assert service.score(risky).probability_of_default > service.score(SAMPLE).probability_of_default


def test_metrics_are_persisted_for_both_models(service):
    info = service.info()
    for key in ("metrics", "baseline_metrics"):
        m = info[key]
        for metric in ("auc_roc", "pr_auc", "ks", "brier", "calibration_curve", "confusion_matrix"):
            assert metric in m
    assert info["model_version"].startswith("v1-")


def test_outcomes_feed_a_champion_challenger_retrain(service):
    batch = generate(600, 99).drop(columns=[LABEL])
    items = [(f"loan-{i}", row) for i, row in enumerate(batch.to_dict("records"))]
    outcomes = service.simulate_outcomes(items)
    assert len(outcomes) == 600 and {d for _, d in outcomes} <= {0, 1}
    # re-sending the same loans does not duplicate feedback rows
    service.simulate_outcomes(items[:10])
    assert len(service._feedback()) == 600

    before = service.info()["model_version"]
    result = service.retrain()
    assert result["champion_version"] == before
    assert result["promoted"] == (result["challenger_holdout_auc"] > result["champion_holdout_auc"])
    expected = result["challenger_version"] if result["promoted"] else before
    assert service.info()["model_version"] == expected
    history = service.history()["comparisons"]
    assert history[0]["event"] == "bootstrap" and history[-1]["event"] == "retrain"


def test_invalid_explanation_withholds_score(service, monkeypatch):
    from creditsense_ml.service import ExplanationUnavailable

    def broken(_):
        raise ValueError("boom")

    monkeypatch.setattr(service._explainer, "shap_values", broken)
    with pytest.raises(ExplanationUnavailable):
        service.score(SAMPLE)


def test_scoring_is_not_blocked_by_a_running_retrain(service, monkeypatch):
    import threading

    from creditsense_ml import service as service_module
    from creditsense_ml.service import RetrainInProgress

    started, release = threading.Event(), threading.Event()
    real_train = service_module.train

    def slow_train(*args, **kwargs):
        started.set()
        assert release.wait(30), "test did not release the retrain"
        return real_train(*args, **kwargs)

    monkeypatch.setattr(service_module, "train", slow_train)
    worker = threading.Thread(target=service.retrain)
    worker.start()
    try:
        assert started.wait(30)
        scored = []
        scorer = threading.Thread(target=lambda: scored.append(service.score(SAMPLE)))
        scorer.start()
        scorer.join(5)
        assert scored, "a prediction waited for the retrain to finish"
        with pytest.raises(RetrainInProgress):
            service.retrain()
    finally:
        release.set()
        worker.join(60)
    assert not worker.is_alive()
