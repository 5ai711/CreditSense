package com.creditsense.risk;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * @param baseUrl ML service base URL
 * @param serviceToken shared secret sent as X-Service-Token
 * @param adminTimeout timeout for slow administrative calls (retraining)
 * @param approveBelow PD below which the model recommends approval
 */
@ConfigurationProperties("creditsense.ml")
public record MlProperties(String baseUrl, String serviceToken, Duration adminTimeout, double approveBelow) {

    public MlProperties {
        if (baseUrl == null) baseUrl = "http://localhost:8000";
        if (adminTimeout == null) adminTimeout = Duration.ofMinutes(3);
        if (approveBelow <= 0) approveBelow = 0.20;
    }
}
