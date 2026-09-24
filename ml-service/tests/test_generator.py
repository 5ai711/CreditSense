import numpy as np

from creditsense_ml.features import FEATURE_NAMES
from creditsense_ml.generator import LABEL, generate, simulate_outcome, true_logit


def test_generator_is_deterministic_and_documented_rate():
    a, b = generate(5000, 7), generate(5000, 7)
    assert a.equals(b)
    assert list(a.columns) == FEATURE_NAMES + [LABEL]
    assert 0.09 < a[LABEL].mean() < 0.15  # minority-class default event


def test_ground_truth_has_real_signal():
    from sklearn.metrics import roc_auc_score

    df = generate(10000, 3)
    auc = roc_auc_score(df[LABEL], true_logit(df))
    assert 0.78 < auc < 0.86  # informative but not trivially separable


def test_ground_truth_is_nonlinear():
    df = generate(1, 1).drop(columns=[LABEL])
    df = df.loc[df.index.repeat(2)].reset_index(drop=True)
    df.loc[:, "revenue_volatility"] = 0.8
    df.loc[0, "debt_to_revenue"], df.loc[1, "debt_to_revenue"] = 0.1, 1.0
    low_cv = df.copy()
    low_cv["revenue_volatility"] = 0.1
    # the leverage effect is larger for a volatile business (interaction term)
    assert np.diff(true_logit(df))[0] > np.diff(true_logit(low_cv))[0]


def test_simulated_outcomes_are_stable_per_reference():
    df = generate(50, 11).drop(columns=[LABEL])
    refs = [f"app-{i}" for i in range(50)]
    assert (simulate_outcome(df, refs) == simulate_outcome(df, refs)).all()
