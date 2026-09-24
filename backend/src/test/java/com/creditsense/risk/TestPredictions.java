package com.creditsense.risk;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Builds ML responses whose explanation adds up exactly, for tests. */
public final class TestPredictions {

    private TestPredictions() {}

    public static MlPrediction additive(double pd, String band, Map<String, Object> features) {
        double base = -2.0;
        double logit = Math.log(pd / (1 - pd));
        List<String> names = new ArrayList<>(FeatureVectorBuilder.FEATURES);
        double share = (logit - base) / names.size();
        List<MlPrediction.Contribution> cs = names.stream()
                .map(n -> new MlPrediction.Contribution(n, features == null ? 0 : features.get(n), share))
                .toList();
        return new MlPrediction(pd, band, "v-test", base, cs);
    }

    public static String json(double pd, String band) {
        StringBuilder sb = new StringBuilder();
        double base = -2.0;
        double share = (Math.log(pd / (1 - pd)) - base) / FeatureVectorBuilder.FEATURES.size();
        sb.append("{\"probability_of_default\":").append(pd).append(",\"risk_band\":\"").append(band)
                .append("\",\"model_version\":\"v-test\",\"base_value\":").append(base).append(",\"contributions\":[");
        boolean first = true;
        for (String f : FeatureVectorBuilder.FEATURES) {
            if (!first) sb.append(',');
            first = false;
            sb.append("{\"feature\":\"").append(f).append("\",\"feature_value\":0,\"shap_contribution\":")
                    .append(share).append('}');
        }
        return sb.append("]}").toString();
    }
}
