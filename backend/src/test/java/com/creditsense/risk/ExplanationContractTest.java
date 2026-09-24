package com.creditsense.risk;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class ExplanationContractTest {

    final ExplanationContract contract = new ExplanationContract();

    @Test
    void acceptsACompleteAdditiveExplanation() {
        assertThatCode(() -> contract.validate(TestPredictions.additive(0.12, "MEDIUM", null), FeatureVectorBuilder.FEATURES))
                .doesNotThrowAnyException();
    }

    @Test
    void rejectsAScoreWithoutExplanation() {
        MlPrediction p = new MlPrediction(0.12, "MEDIUM", "v1", -2.0, List.of());
        assertThatThrownBy(() -> contract.validate(p, FeatureVectorBuilder.FEATURES))
                .isInstanceOf(ExplanationContractViolation.class).hasMessageContaining("without an explanation");
    }

    @Test
    void rejectsAnExplanationMissingAFeature() {
        MlPrediction full = TestPredictions.additive(0.12, "MEDIUM", null);
        List<MlPrediction.Contribution> cs = new ArrayList<>(full.contributions());
        cs.removeIf(c -> c.feature().equals("sector"));
        MlPrediction p = new MlPrediction(0.12, "MEDIUM", "v1", full.baseValue(), cs);
        assertThatThrownBy(() -> contract.validate(p, FeatureVectorBuilder.FEATURES))
                .hasMessageContaining("missing [sector]");
    }

    @Test
    void rejectsAnExplanationThatDoesNotAddUp() {
        MlPrediction ok = TestPredictions.additive(0.12, "MEDIUM", null);
        MlPrediction p = new MlPrediction(0.12, "MEDIUM", "v1", ok.baseValue() + 0.5, ok.contributions());
        assertThatThrownBy(() -> contract.validate(p, FeatureVectorBuilder.FEATURES)).hasMessageContaining("add up");
    }

    @Test
    void rejectsInconsistentBandAndImpossiblePd() {
        assertThatThrownBy(() -> contract.validate(TestPredictions.additive(0.12, "LOW", null), FeatureVectorBuilder.FEATURES))
                .hasMessageContaining("inconsistent");
        MlPrediction bad = new MlPrediction(1.2, "HIGH", "v1", 0, List.of());
        assertThatThrownBy(() -> contract.validate(bad, FeatureVectorBuilder.FEATURES)).hasMessageContaining("outside");
    }

    @Test
    void rejectsDuplicateFeatures() {
        MlPrediction ok = TestPredictions.additive(0.12, "MEDIUM", null);
        List<MlPrediction.Contribution> cs = new ArrayList<>(ok.contributions());
        cs.set(1, new MlPrediction.Contribution(cs.get(0).feature(), 0, cs.get(1).shapContribution()));
        MlPrediction p = new MlPrediction(0.12, "MEDIUM", "v1", ok.baseValue(), cs);
        assertThatThrownBy(() -> contract.validate(p, FeatureVectorBuilder.FEATURES)).hasMessageContaining("twice");
    }
}
