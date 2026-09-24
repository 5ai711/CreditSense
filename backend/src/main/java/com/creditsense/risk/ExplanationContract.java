package com.creditsense.risk;

import com.creditsense.domain.RiskBand;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.springframework.stereotype.Component;

/**
 * Enforces, on the backend side, that no black-box score is ever accepted: the explanation
 * must cover every feature exactly once and add up to the score on the log-odds scale.
 */
@Component
public class ExplanationContract {

    public static final double ADDITIVITY_TOLERANCE = 1e-3;

    public void validate(MlPrediction p, Set<String> expectedFeatures) {
        double pd = p.probabilityOfDefault();
        if (!(pd > 0 && pd < 1)) {
            throw new ExplanationContractViolation("probability of default outside (0, 1): " + pd);
        }
        if (p.modelVersion() == null || p.modelVersion().isBlank()) {
            throw new ExplanationContractViolation("response does not name the model version");
        }
        List<MlPrediction.Contribution> contributions = p.contributions();
        if (contributions == null || contributions.isEmpty()) {
            throw new ExplanationContractViolation("score arrived without an explanation");
        }
        Set<String> seen = new HashSet<>();
        double sum = 0;
        for (MlPrediction.Contribution c : contributions) {
            if (c.feature() == null || !seen.add(c.feature())) {
                throw new ExplanationContractViolation("explanation lists a feature twice or without a name");
            }
            if (!Double.isFinite(c.shapContribution())) {
                throw new ExplanationContractViolation("non-finite contribution for " + c.feature());
            }
            sum += c.shapContribution();
        }
        if (!seen.equals(expectedFeatures)) {
            Set<String> missing = new HashSet<>(expectedFeatures);
            missing.removeAll(seen);
            throw new ExplanationContractViolation("explanation does not cover the feature vector; missing " + missing);
        }
        double logit = Math.log(pd / (1 - pd));
        double gap = Math.abs(p.baseValue() + sum - logit);
        if (!(gap <= ADDITIVITY_TOLERANCE)) {
            throw new ExplanationContractViolation(String.format("explanation does not add up to the score (gap %.2e)", gap));
        }
        if (!bandFor(pd, 0.05, 0.20).name().equals(p.riskBand())) {
            throw new ExplanationContractViolation("risk band " + p.riskBand() + " is inconsistent with PD " + pd);
        }
    }

    public static RiskBand bandFor(double pd, double low, double high) {
        return pd < low ? RiskBand.LOW : pd < high ? RiskBand.MEDIUM : RiskBand.HIGH;
    }
}
