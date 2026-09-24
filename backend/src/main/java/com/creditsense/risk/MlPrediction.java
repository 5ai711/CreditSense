package com.creditsense.risk;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;

/** The ML service's /predict response: a score and the ledger that explains it. */
@JsonIgnoreProperties(ignoreUnknown = true)
public record MlPrediction(
        @JsonProperty("probability_of_default") double probabilityOfDefault,
        @JsonProperty("risk_band") String riskBand,
        @JsonProperty("model_version") String modelVersion,
        @JsonProperty("base_value") double baseValue,
        @JsonProperty("contributions") List<Contribution> contributions) {

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Contribution(
            @JsonProperty("feature") String feature,
            @JsonProperty("feature_value") Object featureValue,
            @JsonProperty("shap_contribution") double shapContribution) {}
}
